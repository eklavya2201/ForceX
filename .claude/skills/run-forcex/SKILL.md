---
name: run-forcex
description: Run, test, and drive the ForceX Share Flask application (web server + PySide6 desktop client)
---

# ForceX Share — Run Skill

ForceX is a Flask-based private file sharing application with a web UI and optional PySide6 desktop client. This skill covers:
- **Web server** (`run.py` → Waitress on `127.0.0.1:5000`) — driven with `curl`/`chromium-cli`
- **Desktop client** (`browser/forcex_browser.py`) — driven with Playwright `_electron` REPL under xvfb

Unit: `ForceX/` (repo root). Paths in this file are relative to `ForceX/`.

## Prerequisites (Ubuntu/Debian)

```bash
apt-get update && apt-get install -y \
  python3.12 python3.12-venv \
  libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
  libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
  xvfb
```

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python -m pip install playwright
.venv/bin/playwright install chromium
.venv/bin/playwright install-deps chromium
```

Copy `.env.example` to `.env` and generate keys:

```bash
cp .env.example .env
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"  # FORCEX_SECRET_KEY
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"  # FORCEX_CLIENT_KEY
# Edit .env with both values
```

## Build (Desktop Client)

```bash
.venv/bin/python -m pip install pyinstaller
.venv/bin/python build_desktop.py --url http://127.0.0.1:5000 --key $(grep FORCEX_CLIENT_KEY .env | cut -d= -f2)
# Output: dist/ForceX.exe
```

## Run: Web Server (Agent Path — `curl` Smoke Test)

```bash
# Terminal 1: start server in background
.venv/bin/python run.py &
SERVER_PID=$!
sleep 3  # wait for Waitress to bind

# Terminal 2: smoke test
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/  # expect 200
curl -s http://127.0.0.1:5000/register | grep -q "Register" && echo "OK"

# Stop
kill $SERVER_PID
```

## Run: Web Server (Agent Path — `chromium-cli` for Full Flows)

Create a script `e2e-web.mjs` (committed alongside this skill):

```javascript
// .claude/skills/run-forcex/e2e-web.mjs
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:5000';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

// Helper: wait for navigation + screenshot
async function go(url, label) {
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.screenshot({ path: `screenshots/${label}.png`, fullPage: true });
  console.log(`[${label}] ${page.url()}`);
}

await go(BASE + '/', '01-landing');
await go(BASE + '/register', '02-register');
// Fill registration form
await page.fill('input[name="email"]', 'test@example.com');
await page.fill('input[name="password"]', 'testpass123');
await page.fill('input[name="password2"]', 'testpass123');
await page.click('button[type="submit"]');
await page.waitForURL('**/dashboard');
await page.screenshot({ path: 'screenshots/03-dashboard.png', fullPage: true });

// Create a share
await page.click('a[href="/new"]');
await page.waitForURL('**/new');
await page.setInputFiles('input[name="file"]', 'tests/fixtures/sample.txt');
await page.fill('input[name="expiry"]', '1'); // 1 hour
await page.click('button[type="submit"]');
await page.waitForURL('**/shares/**');
await page.screenshot({ path: 'screenshots/04-share-created.png', fullPage: true });

// Extract share link and test receiver flow
const shareUrl = page.url();
console.log('Share URL:', shareUrl);

await browser.close();
```

Run it:

```bash
mkdir -p screenshots tests/fixtures
echo "hello" > tests/fixtures/sample.txt
.venv/bin/python run.py &
SERVER_PID=$!
sleep 3
.venv/bin/node .claude/skills/run-forcex/e2e-web.mjs
kill $SERVER_PID
```

Screenshots land in `screenshots/`.

## Run: Desktop Client (Agent Path — Playwright `_electron` REPL)

Create `driver-electron.mjs` (committed alongside this skill):

```javascript
// .claude/skills/run-forcex/driver-electron.mjs
import { _electron } from 'playwright';
import { spawn } from 'child_process';

const EXE = 'dist/ForceX.exe';
const URL = 'http://127.0.0.1:5000';
const KEY = process.env.FORCEX_CLIENT_KEY;

let electronProc;
let app;

async function launch() {
  electronProc = spawn('wine', [EXE], {
    env: { ...process.env, FORCEX_URL: URL, FORCEX_CLIENT_KEY: KEY },
    stdio: ['pipe', 'pipe', 'pipe']
  });
  // Wait for window to appear
  await new Promise(r => setTimeout(r, 3000));
  app = await _electron.connect({ executablePath: 'wine', args: [EXE] });
  const window = await app.firstWindow();
  return window;
}

async function screenshot(window, name) {
  await window.screenshot({ path: `screenshots/electron-${name}.png` });
}

async function type(window, selector, text) {
  await window.fill(selector, text);
}

async function click(window, selector) {
  await window.click(selector);
}

async function quit() {
  await app.close();
  electronProc.kill();
}

// REPL-style exports for tmux send-keys
export { launch, screenshot, type, click, quit };
```

Run under xvfb + tmux:

```bash
# Terminal 1: xvfb-run tmux session
xvfb-run -a tmux new-session -d -s forcex-electron
tmux send-keys -t forcex-electron "cd ForceX && .venv/bin/python run.py" Enter
sleep 5
tmux send-keys -t forcex-electron "cd ForceX && .venv/bin/node .claude/skills/run-forcex/driver-electron.mjs" Enter

# Interact via tmux send-keys to the REPL
# tmux send-keys -t forcex-electron "await launch()" Enter
# tmux send-keys -t forcex-electron "await screenshot(window, '01-launch')" Enter
# tmux capture-pane -t forcex-electron -p
```

## Run: Human Path

```bash
# Web
.venv/bin/python run.py
# Open http://127.0.0.1:5000 in browser

# Desktop
.venv/bin/python -m browser.forcex_browser
# Or run built EXE:
wine dist/ForceX.exe
```

## Test Suite

```bash
.venv/bin/python -m pytest tests/ -v
```

## Gotchas

| Issue | Workaround |
|-------|------------|
| `FORCEX_SECRET_KEY must be set` | Ensure `.env` has both keys (64 hex chars each) |
| Port 5000 in use | `kill $(lsof -ti:5000)` or change `PORT` in `.env` |
| Desktop client needs Wine on Linux | Install `wine64` and run under `xvfb-run` |
| UniversalDRM requires Chromium | `playwright install chromium` + deps |
| Database not created | First run auto-creates `forcex.db`; delete to reset |
| Cleanup scheduler removes shares | Set `FORCEX_SCHEDULER=0` in `.env` for testing |
| `FORCEX_COOKIE_SECURE=1` breaks local HTTP | Keep `0` for local dev; only `1` behind HTTPS proxy |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: backend` | Run from repo root (`ForceX/`) with venv active |
| `waitress` not found | `.venv/bin/python -m pip install -r requirements.txt` |
| Electron window blank | Ensure `xvfb-run -a` and `playwright install-deps chromium` |
| Share links return 404 | Check `FORCEX_CLIENT_KEY` matches between server and client |
| Tests fail with DB errors | Delete `forcex.db` and re-run; migrations are auto |