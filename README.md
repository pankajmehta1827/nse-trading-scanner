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

## Host it online (Render, free)

The repo carries a [`Dockerfile`](Dockerfile) and a Render Blueprint
([`render.yaml`](render.yaml)), so Render builds and runs it with no other setup.

1. Sign up at https://render.com with your GitHub account.
2. **New → Blueprint**, pick `nse-trading-scanner`, and allow Render to read it.
3. When asked for `NSE_SCANNER_PASSWORD`, type a password of your choice. The
   app is on the public internet, so anyone without it gets "Password required".
4. Click **Apply**. The first build takes about 5 minutes.
5. Open the `https://nse-trading-scanner-….onrender.com` address Render shows.
   Your browser asks for a user name and password: any user name, your password.

Good to know:
- The free plan sleeps after 15 minutes without visits; the next visit takes
  about a minute to wake it.
- Each push to `main` redeploys automatically.
- TradingView's screener is unofficial. If it refuses requests from Render's
  servers, scans show "502"; the page and everything else still work.

Any other Docker host works too:

```bash
docker build -t nse-scanner .
docker run -p 8000:8000 -e NSE_SCANNER_PASSWORD=choose-one nse-scanner
```

## Tests

```bat
python -m unittest discover -s .claude\skills\nse-swing\tests
cd scanner\backend
.venv\Scripts\python -m unittest discover -s tests
```

Not investment advice. Nothing here places orders.
