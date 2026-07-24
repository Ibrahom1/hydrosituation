#!/usr/bin/env python3
"""Fallback collector for the public FFD river-state HTML page.

The primary collector uses the pm-dashboard JSON API. This fallback parses the
station objects from https://ffd.pmd.gov.pk/river-state when the primary
workflow fails, then writes the same latest.json shape and SQLite telemetry
rows used by remote_collector.py.

=== NEW (July 2026) ===
The FFD river-state page no longer embeds station data as inline `var s = {…}`
JS objects.  Station data is now fetched client-side from a **token-gated
JSON endpoint** (`/river-state/data`) that requires:
  1. Session cookies from the page load (Cloudflare / server cookies).
  2. An `X-FW-Token` header whose value is embedded in the HTML as
     `var RS_TOKEN = "…";`.

This collector replicates that browser flow:
  fetch HTML page → capture cookies + extract RS_TOKEN
  → fetch /river-state/data with cookies + X-FW-Token header
  → parse the JSON `{ "stations": [...] }` response.

The legacy `var s = {…}` parser is kept as a secondary fallback in case the
page format reverts.
"""

import argparse
import ast
import datetime
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

from remote_collector import init_db, store_to_database


DEFAULT_URL = "https://ffd.pmd.gov.pk/river-state?zoom=6"
DATA_ENDPOINT = "https://ffd.pmd.gov.pk/river-state/data"
OUT_FILE = os.environ.get("OUT_FILE", "latest.json")
UA = {"User-Agent": "HybridHydroHTMLFallback/1.0"}

NAME_ALIASES = {
    "Kala Bagh": "Kalabagh",
    "Qadirabad": "Q.Abad",
    "New Rasul": "Rasul",
    "Nowshera": "KABUL",
    "Partab Bridge": "Partab Bridge (Bunji)",
    "Besham": "Besham ",
}

DAM_NAMES = {"Tarbela Dam", "Mangla Dam", "Chashma"}


# ─────────────────────────────────────────────────────────────────────────────
# Network helpers
# ─────────────────────────────────────────────────────────────────────────────


def fetch_html(url: str) -> str:
    import requests

    response = requests.get(url, timeout=60, headers=UA)
    response.raise_for_status()
    if not response.text.strip():
        raise RuntimeError(f"Empty HTML response from {url}")
    return response.text


def fetch_token_gated_stations(page_url: str, data_url: str) -> List[Dict[str, Any]]:
    """Fetch station data from the token-gated JSON endpoint.

    Flow:
        1. GET the river-state page → capture session cookies from the response.
        2. Extract the embedded RS_TOKEN from the page HTML.
        3. GET /river-state/data with the session cookies + X-FW-Token header.
        4. Return the parsed ``stations`` list.
    """
    import requests

    session = requests.Session()
    session.headers.update(UA)

    # Step 1 – fetch the page to get cookies (Cloudflare, ASP.NET, etc.)
    page_response = session.get(page_url, timeout=60)
    page_response.raise_for_status()
    html = page_response.text
    if not html.strip():
        raise RuntimeError(f"Empty HTML response from {page_url}")

    # Step 2 – extract RS_TOKEN from the page.
    # Pattern: var RS_TOKEN = "timestamp.hexhash";
    token_match = re.search(r'var\s+RS_TOKEN\s*=\s*["\']([^"\']+)["\']', html)
    if not token_match:
        raise RuntimeError(
            "Could not find RS_TOKEN in the river-state HTML. "
            "The page format may have changed again."
        )
    rs_token = token_match.group(1)
    print(f"[HTML] Extracted RS_TOKEN: {rs_token[:20]}…")

    # Step 3 – fetch the gated data endpoint in the same session
    data_headers = {
        "X-Requested-With": "XMLHttpRequest",
        "X-FW-Token": rs_token,
        "Referer": page_url,
    }
    data_response = session.get(data_url, timeout=60, headers=data_headers)
    if data_response.status_code == 403:
        raise RuntimeError(
            "403 Forbidden from /river-state/data – token or cookies were rejected."
        )
    data_response.raise_for_status()

    payload = data_response.json()
    stations = payload.get("stations") or []
    if not stations:
        raise RuntimeError("Token-gated endpoint returned zero stations.")

    print(f"[HTML] Token-gated endpoint returned {len(stations)} stations.")
    return stations


# ─────────────────────────────────────────────────────────────────────────────
# File I/O
# ─────────────────────────────────────────────────────────────────────────────


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


# ─────────────────────────────────────────────────────────────────────────────
# Legacy `var s = {…}` HTML parser (kept as fallback)
# ─────────────────────────────────────────────────────────────────────────────


def find_matching_brace(text: str, start_index: int) -> int:
    depth = 0
    quote: Optional[str] = None
    escaped = False

    for index in range(start_index, len(text)):
        char = text[index]

        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index

    raise ValueError("Could not find matching closing brace for station object")


def iter_station_object_literals(html: str) -> Iterable[str]:
    marker = "var s ="
    offset = 0
    while True:
        marker_index = html.find(marker, offset)
        if marker_index == -1:
            break
        object_start = html.find("{", marker_index)
        if object_start == -1:
            break
        object_end = find_matching_brace(html, object_start)
        yield html[object_start : object_end + 1]
        offset = object_end + 1


def split_top_level_entries(object_literal: str) -> List[str]:
    body = object_literal.strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]

    entries: List[str] = []
    start = 0
    brace_depth = 0
    bracket_depth = 0
    quote: Optional[str] = None
    escaped = False

    for index, char in enumerate(body):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
            continue

        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char == "," and brace_depth == 0 and bracket_depth == 0:
            entry = body[start:index].strip()
            if entry:
                entries.append(entry)
            start = index + 1

    tail = body[start:].strip()
    if tail:
        entries.append(tail)
    return entries


def split_key_value(entry: str) -> Tuple[str, str]:
    quote: Optional[str] = None
    escaped = False
    for index, char in enumerate(entry):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
            continue

        if char == ":":
            return entry[:index].strip(), entry[index + 1 :].strip()

    raise ValueError(f"Station entry is missing ':' separator: {entry[:80]}")


def parse_js_value(raw_value: str) -> Any:
    value = raw_value.strip().rstrip(",").strip()
    if value == "null":
        return None
    if value in ("true", "false"):
        return value == "true"
    if not value:
        return ""

    if value[0] in ("'", '"'):
        return ast.literal_eval(value)

    if value[0] in ("[", "{"):
        return json.loads(value)

    if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return float(value) if "." in value else int(value)

    return value


def parse_station_object(object_literal: str) -> Dict[str, Any]:
    station: Dict[str, Any] = {}
    for entry in split_top_level_entries(object_literal):
        key, raw_value = split_key_value(entry)
        station[key] = parse_js_value(raw_value)
    return station


def parse_stations_from_html(html: str) -> List[Dict[str, Any]]:
    """Legacy parser: extract inline `var s = {…}` station objects from HTML."""
    stations = [parse_station_object(item) for item in iter_station_object_literals(html)]
    stations = [station for station in stations if station.get("name")]
    return stations


# ─────────────────────────────────────────────────────────────────────────────
# Unified station parser (try token-gated first, then legacy fallback)
# ─────────────────────────────────────────────────────────────────────────────


def parse_stations(
    html: Optional[str] = None,
    page_url: str = DEFAULT_URL,
    data_url: str = DATA_ENDPOINT,
    *,
    prefer_token_gated: bool = True,
) -> List[Dict[str, Any]]:
    """Return station dicts from the FFD river-state page.

    Strategy:
        1. Try the token-gated JSON endpoint (new page format).
        2. If that fails, fall back to legacy `var s = {…}` HTML parsing.
    """
    # ── Approach 1: Token-gated JSON endpoint ────────────────────────────
    if prefer_token_gated:
        try:
            stations = fetch_token_gated_stations(page_url, data_url)
            if stations:
                return stations
        except Exception as exc:
            print(f"[HTML] Token-gated fetch failed: {exc}")
            print("[HTML] Falling back to legacy inline HTML parser…")

    # ── Approach 2: Legacy `var s = {…}` inline parsing ──────────────────
    if html is None:
        html = fetch_html(page_url)

    stations = parse_stations_from_html(html)
    if not stations:
        raise RuntimeError(
            "No FFD station objects found via either token-gated endpoint or "
            "legacy HTML parsing. The page format may have changed."
        )
    return stations


# ─────────────────────────────────────────────────────────────────────────────
# Data normalisation (shared by both approaches)
# ─────────────────────────────────────────────────────────────────────────────


def clean_name(name: str) -> str:
    stripped = str(name or "").strip()
    return NAME_ALIASES.get(stripped, stripped)


def as_display_number(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_coordinate(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return f"{float(value):.7f}"
    except Exception:
        text = str(value).strip()
        return text or None


def find_gauge(station: Dict[str, Any], gauge_type: str) -> Dict[str, Any]:
    target = gauge_type.upper()
    gauges = station.get("gauges") or []
    if not isinstance(gauges, list):
        return {}
    for gauge in gauges:
        if not isinstance(gauge, dict):
            continue
        if str(gauge.get("type", "")).upper() == target:
            return gauge
    return {}


def station_to_item(station: Dict[str, Any], index: int) -> Dict[str, Any]:
    name = clean_name(station.get("name", ""))
    inflow = find_gauge(station, "INFLOW")
    outflow = find_gauge(station, "OUTFLOW")
    recording_time = as_display_number(station.get("recording_time")) or "n/a"

    item: Dict[str, Any] = {
        "id": index,
        "name": name,
        "status": as_display_number(station.get("status")) or "NORMAL",
        # The dashboard map expects latest.json lat/long as [longitude, latitude].
        "lat": as_coordinate(station.get("longitude")),
        "long": as_coordinate(station.get("latitude")),
        "recording_time": recording_time,
        "area_name": as_display_number(station.get("area_name")),
        "height": as_display_number(station.get("height")),
        "latitude": station.get("latitude"),
        "longitude": station.get("longitude"),
        "level": as_display_number(station.get("level")),
        "reservoir_level": as_display_number(station.get("level")),
        "cyp_discharge": as_display_number(station.get("cyp_discharge")),
        "cyp_status": as_display_number(station.get("cyp_status")),
        "cyp_date": as_display_number(station.get("cyp_date")),
        "forecast_status": as_display_number(station.get("forecast_status")),
        "forecast_qual": as_display_number(station.get("forecast_qual")),
        "forecast_quant": as_display_number(station.get("forecast_quant")),
    }

    # Also capture the 'discharge' field directly from the station object
    # (used by the new JSON format where discharge is a top-level field).
    discharge = as_display_number(station.get("discharge"))
    if discharge:
        item["discharge"] = discharge

    # Also capture 'shape' if present (river polygon data)
    shape = station.get("shape")
    if shape:
        item["shape"] = shape

    if inflow:
        item["inflow_discharge"] = as_display_number(inflow.get("discharge"))
        item["inflow_time"] = recording_time
        item["inflow_trend"] = as_display_number(inflow.get("trend"))
    if outflow:
        item["outflow_discharge"] = as_display_number(outflow.get("discharge"))
        item["outflow_time"] = recording_time
        item["outflow_trend"] = as_display_number(outflow.get("trend"))

    # Drop only empty optional values; preserve zero-like strings such as "0".
    return {key: value for key, value in item.items() if value is not None and value != ""}


def categorize_items(items: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    dams: List[Dict[str, Any]] = []
    headworks: List[Dict[str, Any]] = []

    for item in items:
        if item.get("name") in DAM_NAMES:
            dams.append(item)
        else:
            headworks.append(item)

    return {"dams": dams}, {"headworks": headworks}


def build_payload(stations: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    items = [station_to_item(station, index + 1) for index, station in enumerate(stations)]
    dams, headworks = categorize_items(items)
    payload = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source": "ffd_river_state_html_fallback",
        "dams": dams,
        "headworks": headworks,
    }
    return payload, dams, headworks


def write_payload(path: str, payload: Dict[str, Any]) -> None:
    tmp_file = path + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    os.replace(tmp_file, path)


def print_summary(stations: List[Dict[str, Any]], dams: Dict[str, Any], headworks: Dict[str, Any]) -> None:
    gauge_count = sum(len(station.get("gauges") or []) for station in stations)
    cyp_count = sum(1 for station in stations if station.get("cyp_discharge"))
    print(
        "[HTML] Parsed "
        f"stations={len(stations)} gauges={gauge_count} cyp_discharge={cyp_count} "
        f"dams={len(dams.get('dams', []))} headworks={len(headworks.get('headworks', []))}"
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FFD river-state HTML fallback collector")
    parser.add_argument("--fetch-html", help="Fetch FFD river-state HTML and save it to this path")
    parser.add_argument("--html-file", help="Read FFD river-state HTML from this path (legacy mode only)")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Source URL, default: {DEFAULT_URL}")
    parser.add_argument("--data-url", default=DATA_ENDPOINT, help=f"Token-gated data URL, default: {DATA_ENDPOINT}")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate without writing latest.json or DB")
    parser.add_argument("--output", default=OUT_FILE, help=f"Output JSON path, default: {OUT_FILE}")
    parser.add_argument("--min-stations", type=int, default=1, help="Fail if fewer stations are parsed")
    parser.add_argument(
        "--legacy-only", action="store_true",
        help="Skip the token-gated endpoint; only try legacy var s = parsing"
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    html_text: Optional[str] = None
    if args.fetch_html:
        html_text = fetch_html(args.url)
        write_text(args.fetch_html, html_text)
        print(f"[HTML] Saved fetched river-state HTML to {args.fetch_html}")
        if not args.html_file and not args.dry_run and not args.legacy_only:
            # In new mode we still need to proceed to fetch the token-gated data
            pass

    if args.html_file:
        html_text = read_text(args.html_file)

    stations = parse_stations(
        html=html_text,
        page_url=args.url,
        data_url=args.data_url,
        prefer_token_gated=not args.legacy_only,
    )

    if len(stations) < args.min_stations:
        raise RuntimeError(f"Expected at least {args.min_stations} stations, parsed {len(stations)}")

    payload, dams, headworks = build_payload(stations)
    print_summary(stations, dams, headworks)

    if args.dry_run:
        print("[DRY-RUN] Parsed successfully; latest.json and database were not modified.")
        return 0

    init_db()
    store_to_database(dams, headworks)
    write_payload(args.output, payload)
    print(
        f"[JSON] Wrote {args.output}: "
        f"dams={len(dams.get('dams', []))} headworks={len(headworks.get('headworks', []))}"
    )
    print("[DONE] Collected via FFD river-state fallback (JSON + DB updated).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
