"""Start the NSE Swing Scanner with one command.

    python scanner/launch.py [--port 8000] [--no-browser] [--rebuild]

On the first run it creates the Python environment and builds the page; later
runs skip whatever is already up to date (it rebuilds the page by itself after
an update changes its source). Then it starts the app and opens the browser.
Windows users double-click start.bat in the repository root, which runs this.
Standard library only, so it works before anything is installed.
"""
import argparse
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(HERE, "backend")
FRONTEND = os.path.join(HERE, "frontend")
DIST = os.path.join(FRONTEND, "dist")
VENV = os.path.join(BACKEND, ".venv")
REQUIREMENTS = os.path.join(BACKEND, "requirements.txt")
PAGE_SOURCES = ["src", "index.html", "package.json", "package-lock.json", "vite.config.ts", "tsconfig.json"]
WINDOWS = os.name == "nt"


class Problem(Exception):
    """Something the user has to fix; the message says how."""


def step(msg):
    print("\n==> " + msg, flush=True)


def run(cmd, cwd, what):
    try:
        code = subprocess.call(cmd, cwd=cwd)
    except OSError as e:
        raise Problem("%s could not start: %s" % (what, e))
    if code != 0:
        raise Problem("%s failed (exit code %s). The lines above say why." % (what, code))


def venv_python():
    return os.path.join(VENV, "Scripts", "python.exe") if WINDOWS else os.path.join(VENV, "bin", "python")


def file_hash(paths, root):
    h = hashlib.sha256()
    for rel in paths:
        full = os.path.join(root, rel)
        files = [full] if os.path.isfile(full) else sorted(
            os.path.join(d, f) for d, _, fs in os.walk(full) for f in fs)
        for f in files:
            h.update(os.path.relpath(f, root).replace(os.sep, "/").encode())
            with open(f, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def ensure_backend():
    """Python environment with the backend's packages, reinstalled when requirements.txt changes."""
    if not os.path.exists(venv_python()):
        step("Creating the Python environment (first run only)")
        venv.create(VENV, with_pip=True)
    stamp = os.path.join(VENV, ".requirements-hash")
    want = file_hash(["requirements.txt"], BACKEND)
    if read(stamp) != want:
        step("Installing Python packages")
        run([venv_python(), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", REQUIREMENTS],
            BACKEND, "Installing Python packages")
        write(stamp, want)


def ensure_page(force=False):
    """Build the React page when it is missing or its source changed since the last build."""
    stamp = os.path.join(DIST, ".build-hash")
    want = file_hash(PAGE_SOURCES, FRONTEND)
    if not force and read(stamp) == want and os.path.exists(os.path.join(DIST, "index.html")):
        return
    npm = shutil.which("npm")
    if not npm:
        if os.path.exists(os.path.join(DIST, "index.html")):
            print("\nNote: the page may be out of date. Install Node.js (https://nodejs.org) so it can be rebuilt.")
            return
        raise Problem("Node.js is needed to build the page the first time. Install the LTS version from "
                      "https://nodejs.org, then run this again.")
    step("Installing page packages")
    run([npm, "install", "--no-audit", "--no-fund"], FRONTEND, "Installing page packages")
    vite = os.path.join(FRONTEND, "node_modules", ".bin", "vite.cmd" if WINDOWS else "vite")
    if not os.path.exists(vite):   # npm sometimes crashes yet reports success
        raise Problem("Installing page packages did not finish. Check your internet connection and run this again.")
    step("Building the page")
    run([npm, "run", "build"], FRONTEND, "Building the page")
    write(stamp, want)


def app_responds(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/health" % port, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def choose_port(preferred):
    """(port, already_running). Reuses a scanner that is already up; else the first free port."""
    if app_responds(preferred):
        return preferred, True
    for port in range(preferred, preferred + 20):
        if port_free(port):
            return port, False
    raise Problem("Ports %d-%d are all busy. Close some programs or pass --port." % (preferred, preferred + 19))


def open_when_ready(port, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if app_responds(port):
            webbrowser.open("http://localhost:%d" % port)
            return
        time.sleep(0.5)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Set up (if needed) and start the NSE Swing Scanner.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--rebuild", action="store_true", help="rebuild the page even if it looks up to date")
    ap.add_argument("--setup-only", action="store_true", help="install and build, then stop")
    a = ap.parse_args(argv)

    if sys.version_info < (3, 10):
        raise Problem("Python 3.10 or newer is needed (this is %d.%d). Install it from https://www.python.org/downloads/"
                      % sys.version_info[:2])
    print("NSE Swing Scanner")
    ensure_backend()
    ensure_page(a.rebuild)
    if a.setup_only:
        print("\nSetup complete.")
        return 0

    port, running = choose_port(a.port)
    url = "http://localhost:%d" % port
    if running:
        print("\nThe scanner is already running at %s" % url)
        if not a.no_browser:
            webbrowser.open(url)
        return 0
    if not a.no_browser:
        threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()
    print("\n" + "=" * 60)
    print("  The scanner is starting at %s" % url)
    print("  Keep this window open while you use it. Press Ctrl+C to stop.")
    print("=" * 60, flush=True)
    try:
        return subprocess.call([venv_python(), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
                               cwd=BACKEND)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Problem as e:
        print("\nPROBLEM: %s" % e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
