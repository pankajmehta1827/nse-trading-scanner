# NSE Trading Scanner

Tools for scanning Indian (NSE) stocks on fundamentals + technicals for swing
and positional trades. Moved here from NovaRagAgent, where it did not belong.

| folder | what |
| --- | --- |
| [`scanner/`](scanner/README.md) | Web app: React page + Python (FastAPI) backend on TradingView data. Scores Nifty 500 (or Nifty 50/100/200, Midcap 150, Smallcap 250) stocks out of 100 and gives each pick a rupee trade plan. |
| [`.claude/skills/nse-swing/`](.claude/skills/nse-swing/SKILL.md) | The `/nse-swing` Claude Code skill. Its `score.py` holds the scoring rules; the web app imports it, so the two always agree. |
| [`trader/`](trader/README.md) | The third-party Day Trader skill pack (US stocks only, MIT, from Jakeschincariol/day-trader-skill), kept for reference. |

## Run it on your computer (Windows)

1. **Get the code.** Either
   - on GitHub: **Code → Download ZIP**, then right-click the ZIP → **Extract All**, or
   - with Git: `git clone https://github.com/pankajmehta1827/nse-trading-scanner.git`
2. **Double-click `start.bat`** in the folder.
   - If Python or Node.js is missing, it offers to install it. Say **Y**, then
     double-click `start.bat` again when it says so.
   - The first start sets everything up (a few minutes). Later starts take seconds.
3. Your browser opens the scanner. Press **Run scan**.

Keep the black window open while you use the scanner; closing it stops the app.

**To update** after changes: double-click `update.bat` if you used Git, or
download the ZIP again. The page rebuilds itself when its code has changed.

macOS / Linux: `python3 scanner/launch.py`. Options: `--port 8001`,
`--no-browser`, `--rebuild`. Full details, the API and offline mode are in
[`scanner/README.md`](scanner/README.md).

If something goes wrong, the window says what and how to fix it; it stays open
so you can read it or take a screenshot.

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
