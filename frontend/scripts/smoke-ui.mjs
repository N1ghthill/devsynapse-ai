import { chromium } from 'playwright';

const baseURL = process.env.DEVSYNAPSE_SMOKE_BASE_URL || 'http://127.0.0.1:8000';
const username = process.env.DEVSYNAPSE_SMOKE_USERNAME || 'admin';
const password = process.env.DEVSYNAPSE_SMOKE_PASSWORD || 'admin';
const timeout = Number(process.env.DEVSYNAPSE_SMOKE_TIMEOUT_MS || '15000');
const screenshotPath = process.env.DEVSYNAPSE_SMOKE_SCREENSHOT || 'smoke-ui-failure.png';

const failedResponses = [];
const pageErrors = [];

function trackPageFailures(page) {
  page.on('response', (response) => {
    const status = response.status();
    if (status >= 500) {
      failedResponses.push(`${status} ${response.url()}`);
    }
  });
  page.on('pageerror', (error) => {
    pageErrors.push(error.message);
  });
}

async function expectVisible(locator, label) {
  await locator.waitFor({ state: 'visible', timeout });
  if (!(await locator.isVisible())) {
    throw new Error(`${label} is not visible`);
  }
}

async function runSmoke() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(timeout);
  trackPageFailures(page);

  try {
    await page.goto(baseURL, { waitUntil: 'domcontentloaded' });

    await page.getByLabel('Username').fill(username);
    await page.getByLabel('Password').fill(password);
    await Promise.all([
      page.waitForURL(/\/chat$/, { timeout }),
      page.getByRole('button', { name: 'Sign In' }).click(),
    ]);
    await expectVisible(page.getByRole('heading', { name: 'DevSynapse Chat' }), 'chat heading');

    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Dashboard' }), 'dashboard heading');
    await expectVisible(page.getByText('Total Commands'), 'dashboard totals');

    await page.getByRole('link', { name: 'Settings' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Settings' }), 'settings heading');
    await page.getByRole('button', { name: 'Save Changes' }).click();
    await expectVisible(page.getByText('Settings saved successfully'), 'settings save confirmation');

    await page.getByRole('link', { name: 'Admin' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Admin', exact: true }), 'admin heading');
    await expectVisible(page.getByRole('button', { name: 'Save Permissions' }).first(), 'admin permissions');

    if (failedResponses.length > 0) {
      throw new Error(`HTTP 5xx responses during smoke: ${failedResponses.join(', ')}`);
    }
    if (pageErrors.length > 0) {
      throw new Error(`Browser page errors during smoke: ${pageErrors.join('; ')}`);
    }

    console.log('ui-smoke-ok');
  } catch (error) {
    await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});
    throw error;
  } finally {
    await browser.close();
  }
}

runSmoke().catch((error) => {
  console.error(error);
  process.exit(1);
});
