#!/usr/bin/env python3
"""Fallback collector for the public FFD river-state HTML page.

The primary collector uses the pm-dashboard JSON API. This fallback parses the
station objects embedded in https://ffd.pmd.gov.pk/river-state?zoom=6 when the
primary workflow fails, then writes the same latest.json shape and SQLite
telemetry rows used by remote_collector.py.
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


def fetch_html(url: str) -> str:
    import requests

    response = requests.get(url, timeout=60, headers=UA)
    response.raise_for_status()
    if not response.text.strip():
        raise RuntimeError(f"Empty HTML response from {url}")
    return response.text


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


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


def parse_stations(html: str) -> List[Dict[str, Any]]:
    stations = [parse_station_object(item) for item in iter_station_object_literals(html)]
    stations = [station for station in stations if station.get("name")]
    if not stations:
        raise RuntimeError("No FFD station objects found in HTML")
    return stations


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
    parser.add_argument("--html-file", help="Read FFD river-state HTML from this path")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Source URL, default: {DEFAULT_URL}")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate without writing latest.json or DB")
    parser.add_argument("--output", default=OUT_FILE, help=f"Output JSON path, default: {OUT_FILE}")
    parser.add_argument("--min-stations", type=int, default=1, help="Fail if fewer stations are parsed")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    html_text: Optional[str] = None
    if args.fetch_html:
        html_text = fetch_html(args.url)
        write_text(args.fetch_html, html_text)
        print(f"[HTML] Saved fetched river-state HTML to {args.fetch_html}")
        if not args.html_file and not args.dry_run:
            return 0

    if args.html_file:
        html_text = read_text(args.html_file)
    elif html_text is None:
        html_text = fetch_html(args.url)

    stations = parse_stations(html_text)
    if len(stations) < args.min_stations:
        raise RuntimeError(f"Expected at least {args.min_stations} stations, parsed {len(stations)}")

    payload, dams, headworks = build_payload(stations)
    print_summary(stations, dams, headworks)

    if args.dry_run:
        print("[DRY-RUN] Parsed HTML successfully; latest.json and database were not modified.")
        return 0

    init_db()
    store_to_database(dams, headworks)
    write_payload(args.output, payload)
    print(
        f"[JSON] Wrote {args.output}: "
        f"dams={len(dams.get('dams', []))} headworks={len(headworks.get('headworks', []))}"
    )
    print("[DONE] Collected via FFD river-state HTML fallback (JSON + DB updated).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
