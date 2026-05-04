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

async function expectNoHorizontalOverflow(page, label) {
  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
    header: (document.querySelector('.chat-header')?.scrollWidth || 0)
      - (document.querySelector('.chat-header')?.clientWidth || 0),
    input: (document.querySelector('.chat-input-wrapper')?.scrollWidth || 0)
      - (document.querySelector('.chat-input-wrapper')?.clientWidth || 0),
  }));
  const failures = Object.entries(overflow).filter(([, value]) => value > 1);
  if (failures.length > 0) {
    throw new Error(`${label} has horizontal overflow: ${JSON.stringify(overflow)}`);
  }
}

async function expectCompactTextControls(page, label) {
  const wrappingControls = await page.evaluate(() => {
    const selectors = [
      '.nav-item',
      '.logout-btn',
      '.new-chat-btn',
      '.top-new-chat-btn',
      '.project-manager-open',
      '.project-create-toggle',
      '.project-action-btn',
      '.project-status-tabs button',
      '.dashboard-filter-btn',
      '.save-btn',
      '.auto-approve-toggle',
      '.command-status-badge',
      '.context-pill',
      '.scope-chip',
      '.status-badge',
      '.model-chip',
    ];
    return selectors.flatMap((selector) =>
      Array.from(document.querySelectorAll(selector))
        .filter((element) => {
          const text = (element.textContent || '').replace(/\s+/g, ' ').trim();
          if (!text) return false;
          return getComputedStyle(element).whiteSpace !== 'nowrap';
        })
        .map((element) => ({
          selector,
          text: (element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80),
          className: element.className?.toString?.() || '',
        }))
    );
  });
  if (wrappingControls.length > 0) {
    throw new Error(`${label} has wrapping compact controls: ${JSON.stringify(wrappingControls)}`);
  }
}

async function checkLayout(page, label) {
  await expectNoHorizontalOverflow(page, label);
  await expectCompactTextControls(page, label);
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
    await checkLayout(page, 'chat desktop');

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
    await expectVisible(page.locator('.command-timeline-row.status-success').first(), 'command timeline success');
    await expectVisible(page.getByText('smoke-chat-ok', { exact: true }), 'chat command output');
    await expectHidden(page.locator('.typing-indicator'), 'chat typing indicator');
    if (!interceptedChatStream) {
      throw new Error('chat stream was not exercised during smoke');
    }
    await page.unroute('**/chat/stream');

    const longToken = 'x'.repeat(260);
    await page.route('**/chat/stream', async (route) => {
      const events = [
        {
          type: 'text',
          content: `Texto longo sem espaços ${longToken}\n\nhttps://example.com/${longToken}`,
        },
        {
          type: 'done',
          usage: null,
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
    await page.getByRole('button', { name: 'Nova conversa' }).click();
    await page
      .getByPlaceholder('Peça uma análise, refatoração, teste ou comando local...')
      .fill('responda com texto grande');
    await page.getByTitle('Enviar mensagem').click();
    await expectVisible(page.getByText('Texto longo sem espaços'), 'long unbroken chat text');
    const chatOverflow = await page.locator('.message-ai .message-content').last().evaluate((el) => ({
      message: el.scrollWidth - el.clientWidth,
      body: (el.querySelector('.message-body')?.scrollWidth || 0)
        - (el.querySelector('.message-body')?.clientWidth || 0),
    }));
    if (chatOverflow.message > 1 || chatOverflow.body > 1) {
      throw new Error(`long chat content overflows horizontally: ${JSON.stringify(chatOverflow)}`);
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
    await checkLayout(page, 'project manager desktop');

    await page.getByRole('link', { name: 'Painel' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Painel' }), 'dashboard heading');
    await expectVisible(page.locator('.stat-label', { hasText: 'Comandos' }).first(), 'dashboard totals');
    await checkLayout(page, 'dashboard desktop');

    await page.getByRole('link', { name: 'Ajustes' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Ajustes' }), 'settings heading');
    await page.getByRole('button', { name: 'Salvar alterações' }).click();
    await expectVisible(page.getByText('Ajustes salvos com sucesso'), 'settings save confirmation');
    await checkLayout(page, 'settings desktop');

    await page.getByRole('link', { name: 'Admin' }).click();
    await expectVisible(page.getByRole('heading', { name: 'Administração', exact: true }), 'admin heading');
    await expectVisible(page.getByRole('button', { name: 'Salvar permissões' }).first(), 'admin permissions');
    await checkLayout(page, 'admin desktop');

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${baseURL}/chat`, { waitUntil: 'domcontentloaded' });
    await expectVisible(page.getByRole('heading', { name: 'Escolha um fluxo' }), 'mobile chat empty state');
    await checkLayout(page, 'chat mobile');

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
