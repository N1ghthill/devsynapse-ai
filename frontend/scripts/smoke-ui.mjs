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

async function expectHidden(locator, label) {
  await locator.waitFor({ state: 'hidden', timeout });
  if (await locator.isVisible()) {
    throw new Error(`${label} is still visible`);
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

    let interceptedChatStream = false;
    await page.route('**/chat/stream', async (route) => {
      interceptedChatStream = true;
      const events = [
        {
          type: 'command',
          command: 'bash "echo smoke-chat-ok"',
          auto_execute: true,
        },
        {
          type: 'command_status',
          command: 'bash "echo smoke-chat-ok"',
          status: 'running',
        },
        {
          type: 'command_result',
          command: 'bash "echo smoke-chat-ok"',
          success: true,
          message: 'Comando executado com sucesso (exit code: 0)',
          output: 'smoke-chat-ok\n',
          status: 'success',
          reason_code: null,
          project_name: null,
        },
        {
          type: 'done',
          usage: {
            provider: 'smoke',
            model: 'smoke-model',
            prompt_tokens: 1,
            completion_tokens: 1,
            total_tokens: 2,
            prompt_cache_hit_tokens: 0,
            prompt_cache_miss_tokens: 1,
            reasoning_tokens: 0,
            estimated_cost_usd: 0,
          },
          project_name: null,
        },
      ];
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
      });
    });

    await page.getByRole('button', { name: /Revisão manual/ }).click();
    await page
      .getByPlaceholder('Peça uma análise, refatoração, teste ou comando local...')
      .fill('rode um comando rápido de validação');
    await page.getByTitle('Enviar mensagem').click();
    await expectVisible(
      page.getByText('Execução concluída. O resultado do comando está disponível abaixo.'),
      'chat command completion summary'
    );
    await expectVisible(
      page.locator('.command-status-badge.status-success', { hasText: 'Executado' }).first(),
      'chat command success badge'
    );
    await expectVisible(page.getByText('smoke-chat-ok', { exact: true }), 'chat command output');
    await expectHidden(page.locator('.typing-indicator'), 'chat typing indicator');
    if (!interceptedChatStream) {
      throw new Error('chat stream was not exercised during smoke');
    }
    await page.unroute('**/chat/stream');

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
