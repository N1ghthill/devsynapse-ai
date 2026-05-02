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

    await page.getByLabel('Usuário').fill(username);
    await page.getByLabel('Senha').fill(password);
    await Promise.all([
      page.waitForURL(/\/chat$/, { timeout }),
      page.getByRole('button', { name: 'Entrar' }).click(),
    ]);
    await expectVisible(page.getByText('Workspace local'), 'chat workspace header');
    await expectVisible(page.getByRole('heading', { name: 'Escolha um fluxo' }), 'chat empty state');

    await page.getByRole('button', { name: 'Projetos' }).click();
    await expectVisible(page.getByRole('dialog', { name: 'Escolher projeto' }), 'project manager');
    await page.getByRole('button', { name: 'Adicionar projeto' }).click();
    await page.getByLabel('Nome').fill('smoke-ui-project');
    await Promise.all([
      page.getByRole('dialog', { name: 'Escolher projeto' }).waitFor({ state: 'hidden', timeout }),
      page.getByRole('button', { name: 'Adicionar projeto' }).click(),
    ]);
    await expectVisible(page.getByText('smoke-ui-project').first(), 'created project selection');

    await page.getByRole('link', { name: 'Painel' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Painel' }), 'dashboard heading');
    await expectVisible(page.locator('.stat-label', { hasText: 'Comandos' }).first(), 'dashboard totals');

    await page.getByRole('link', { name: 'Ajustes' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Ajustes' }), 'settings heading');
    await page.getByRole('button', { name: 'Salvar alterações' }).click();
    await expectVisible(page.getByText('Ajustes salvos com sucesso'), 'settings save confirmation');

    await page.getByRole('link', { name: 'Admin' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Administração', exact: true }), 'admin heading');
    await expectVisible(page.getByRole('button', { name: 'Salvar permissões' }).first(), 'admin permissions');

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
