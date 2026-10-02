// .claude/skills/run-forcex/driver-electron.mjs
// Playwright _electron REPL driver for ForceX desktop client (PySide6 built with PyInstaller)
// Run under: xvfb-run -a node driver-electron.mjs

import { _electron } from 'playwright';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const EXE = process.env.FORCEX_EXE || path.resolve('dist/ForceX.exe');
const URL = process.env.FORCEX_URL || 'http://127.0.0.1:5000';
const KEY = process.env.FORCEX_CLIENT_KEY;

const SCREENSHOT_DIR = 'screenshots';
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

let electronProc;
let app;
let window;

async function launch() {
  if (!fs.existsSync(EXE)) {
    throw new Error(`ForceX.exe not found at ${EXE}. Run build_desktop.py first.`);
  }

  console.log(`[driver] Launching ${EXE} with FORCEX_URL=${URL}`);

  electronProc = spawn('wine', [EXE], {
    env: { ...process.env, FORCEX_URL: URL, FORCEX_CLIENT_KEY: KEY },
    stdio: ['pipe', 'pipe', 'pipe']
  });

  await new Promise(r => setTimeout(r, 3000));

  app = await _electron.connect({ executablePath: 'wine', args: [EXE] });
  window = await app.firstWindow();

  console.log('[driver] Connected to Electron/PySide6 window');
  return window;
}

async function screenshot(name) {
  if (!window) throw new Error('Not launched. Call launch() first.');
  const filepath = path.join(SCREENSHOT_DIR, `electron-${name}.png`);
  await window.screenshot({ path: filepath });
  console.log(`[driver] Screenshot saved to ${filepath}`);
  return filepath;
}

async function type(selector, text) {
  if (!window) throw new Error('Not launched. Call launch() first.');
  await window.fill(selector, text);
  console.log(`[driver] Typed into ${selector}`);
}

async function click(selector) {
  if (!window) throw new Error('Not launched. Call launch() first.');
  await window.click(selector);
  console.log(`[driver] Clicked ${selector}`);
}

async function waitForSelector(selector, timeout = 10000) {
  if (!window) throw new Error('Not launched. Call launch() first.');
  await window.waitForSelector(selector, { timeout });
  console.log(`[driver] Found ${selector}`);
}

async function evaluate(fn) {
  if (!window) throw new Error('Not launched. Call launch() first.');
  return await window.evaluate(fn);
}

async function quit() {
  if (app) {
    await app.close();
    console.log('[driver] App closed');
  }
  if (electronProc) {
    electronProc.kill();
    console.log('[driver] Electron process killed');
  }
}

const REPL_HELP = `
ForceX Desktop Driver — REPL commands:
  await launch()                    — Launch and connect to ForceX.exe
  await screenshot('name')          — Save screenshot to screenshots/
  await type('selector', 'text')    — Fill input
  await click('selector')           — Click element
  await waitForSelector('selector') — Wait for element
  await evaluate(() => ...)         — Run code in renderer
  await quit()                      — Close app and cleanup
`;

console.log(REPL_HELP);

export { launch, screenshot, type, click, waitForSelector, evaluate, quit };