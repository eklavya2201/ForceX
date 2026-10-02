// .claude/skills/run-forcex/e2e-web.mjs
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = 'http://127.0.0.1:5000';
const SCREENSHOT_DIR = 'screenshots';

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

async function go(url, label) {
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${label}.png`), fullPage: true });
  console.log(`[${label}] ${page.url()}`);
}

try {
  await go(BASE + '/', '01-landing');
  await go(BASE + '/register', '02-register');

  // Fill registration form
  await page.fill('input[name="email"]', 'test@example.com');
  await page.fill('input[name="password"]', 'testpass123');
  await page.fill('input[name="password2"]', 'testpass123');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard');
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03-dashboard.png'), fullPage: true });

  // Create a share
  await page.click('a[href="/new"]');
  await page.waitForURL('**/new');

  // Create a test file to upload
  const testFile = 'tests/fixtures/sample.txt';
  if (!fs.existsSync(testFile)) {
    fs.mkdirSync('tests/fixtures', { recursive: true });
    fs.writeFileSync(testFile, 'hello from forcex test');
  }

  await page.setInputFiles('input[name="file"]', testFile);
  await page.fill('input[name="expiry"]', '1'); // 1 hour
  await page.click('button[type="submit"]');
  await page.waitForURL('**/shares/**');
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04-share-created.png'), fullPage: true });

  // Extract share link and test receiver flow
  const shareUrl = page.url();
  console.log('Share URL:', shareUrl);

  // Test receiver landing page
  await page.goto(shareUrl, { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05-receiver-landing.png'), fullPage: true });

  // Try to open the share (may need passcode)
  const openBtn = page.locator('button[type="submit"], a[href*="/open"]').first();
  if (await openBtn.count() > 0) {
    await openBtn.click();
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06-receiver-open.png'), fullPage: true });
  }

  console.log('E2E web flow completed successfully');
} catch (err) {
  console.error('E2E web flow failed:', err);
  process.exitCode = 1;
} finally {
  await browser.close();
}