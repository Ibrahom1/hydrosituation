# Hybrid Data Collection Approach

Your frontend + main API stay local. A lightweight external cron job (e.g. GitHub Actions, cron-job.org calling raw file host) produces a JSON snapshot every 6 hours that your local app ingests when opened.

## Flow
1. External collector runs every 6h -> fetches FFD APIs -> writes `latest.json` to a public URL (e.g. GitHub raw file).
2. You open dashboard locally -> frontend calls `/api/sync-remote?url=...` (auto via `config.js`) -> remote dataset merged into local SQLite.
3. Charts use enriched local history.

## Remote JSON Format
```
{
  "generated_at": "2025-08-11T12:00:00Z",
  "dams": {"dams": [...]},
  "headworks": {"headworks": [...]}
}
```

## Setting Remote URL
In `index.html` add before loading `config.js`:
```
<script>window.REMOTE_DATA_URL = 'https://raw.githubusercontent.com/<user>/<repo>/main/latest.json';</script>
```

## Manual Sync
```
GET http://localhost:5000/api/sync-remote?url=<encoded json url>
```

If successful, response: `{ success: true, message: "Applied remote dataset..." }`

## Next Step
GitHub Actions workflow & `remote_collector.py` already added:

1. Push this project to a GitHub repo.
2. Enable Actions (first run may require approval).
3. After first scheduled run, find `latest.json` at:
  `https://raw.githubusercontent.com/<your-user>/<repo>/main/latest.json`
4. Add to `index.html`:
```
<script>window.REMOTE_DATA_URL='https://raw.githubusercontent.com/<your-user>/<repo>/main/latest.json';</script>
<script src="config.js"></script>
```
5. Open dashboard locally -> it auto syncs new data.

Manual trigger: Go to Actions tab -> Run workflow.
