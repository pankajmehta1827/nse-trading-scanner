# NSE Trading Scanner

Tools for scanning Indian (NSE) stocks on fundamentals + technicals for swing
and positional trades. Moved here from NovaRagAgent, where it did not belong.

| folder | what |
| --- | --- |
| [`scanner/`](scanner/README.md) | Web app: React page + Python (FastAPI) backend on TradingView data. Scores Nifty 500 (or Nifty 50/100/200, Midcap 150, Smallcap 250) stocks out of 100 and gives each pick a rupee trade plan. |
| [`.claude/skills/nse-swing/`](.claude/skills/nse-swing/SKILL.md) | The `/nse-swing` Claude Code skill. Its `score.py` holds the scoring rules; the web app imports it, so the two always agree. |
| [`trader/`](trader/README.md) | The third-party Day Trader skill pack (US stocks only, MIT, from Jakeschincariol/day-trader-skill), kept for reference. |

## Quick start (Windows)

```bat
cd scanner\backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd ..\frontend
npm install
npm run build
cd ..\backend
.venv\Scripts\uvicorn app:app --port 8000
```

Open http://localhost:8000 and press **Run scan**. Full details, the API and
offline mode are in [`scanner/README.md`](scanner/README.md).

## Tests

```bat
python -m unittest discover -s .claude\skills\nse-swing\tests
cd scanner\backend
.venv\Scripts\python -m unittest discover -s tests
```

Not investment advice. Nothing here places orders.
