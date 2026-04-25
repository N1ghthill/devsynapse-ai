import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..');
const screenshotDir = path.join(repoRoot, 'docs', 'screenshots');
const baseUrl = process.env.DEVSYNAPSE_UI_URL || 'http://127.0.0.1:5173';
const apiUrl = process.env.DEVSYNAPSE_API_URL || 'http://127.0.0.1:8000';

async function loadLocalEnv() {
  try {
    const content = await fs.readFile(path.join(repoRoot, '.env'), 'utf8');
    return Object.fromEntries(
      content
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line && !line.startsWith('#') && line.includes('='))
        .map((line) => {
          const [key, ...valueParts] = line.split('=');
          return [key.trim(), valueParts.join('=').trim()];
        })
    );
  } catch {
    return {};
  }
}

function readConfig(localEnv, key, fallback) {
  return process.env[key] || localEnv[key] || fallback;
}

async function apiPost(route, payload, token) {
  const response = await fetch(`${apiUrl}${route}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`${route} failed with ${response.status}`);
  }

  return response.json();
}

async function login(username, password) {
  const data = await apiPost('/auth/login', { username, password });
  return data.token || data.access_token;
}

async function seedConversation(token, conversationId) {
  await apiPost(
    '/chat',
    {
      conversation_id: conversationId,
      message: 'List my projects and summarize them in one short paragraph.',
    },
    token
  );

  const listResponse = await apiPost(
    '/chat',
    {
      conversation_id: conversationId,
      message: 'Use ls -la na pasta repos.',
    },
    token
  );
  const listCommand = listResponse.command || listResponse.opencode_command;
  if (listCommand) {
    await apiPost(
      '/execute',
      { conversation_id: conversationId, command: listCommand, confirm: true },
      token
    );
  }

  const blockedResponse = await apiPost(
    '/chat',
    {
      conversation_id: conversationId,
      message: 'Agora use o docker ps.',
    },
    token
  );
  const blockedCommand = blockedResponse.command || blockedResponse.opencode_command;
  if (blockedCommand) {
    await apiPost(
      '/execute',
      { conversation_id: conversationId, command: blockedCommand, confirm: true },
      token
    );
  }
}

async function createContext(browser) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1024 },
    deviceScaleFactor: 1,
  });

  return context;
}

async function primeAuth(page, token, extraStorage = {}) {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(
    ({ authToken, storage }) => {
      localStorage.setItem('auth_token', authToken);
      for (const [key, value] of Object.entries(storage)) {
        if (typeof value === 'string') {
          localStorage.setItem(key, value);
        }
      }
    },
    { authToken: token, storage: extraStorage }
  );
}

async function captureLogin(browser) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1024 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' });
  await page.locator('.login-card').waitFor();
  await page.screenshot({
    path: path.join(screenshotDir, '2026-04-24-login-screen.png'),
    fullPage: false,
  });
  await context.close();
}

async function captureChat(browser, token, conversationId) {
  const context = await createContext(browser);
  const page = await context.newPage();
  await primeAuth(page, token, {
    devsynapse_conversation_id: conversationId,
  });
  await page.goto(`${baseUrl}/chat`, { waitUntil: 'networkidle' });
  await page.locator('.chat-rail').waitFor();
  await page.locator('.message-command').last().waitFor();
  await page.screenshot({
    path: path.join(screenshotDir, '2026-04-24-chat-command-execution.png'),
    fullPage: false,
  });
  await context.close();
}

async function captureDashboard(browser, token) {
  const context = await createContext(browser);
  const page = await context.newPage();
  await primeAuth(page, token);
  await page.goto(`${baseUrl}/dashboard`, { waitUntil: 'networkidle' });
  await page.locator('.dashboard-page').waitFor();
  await page.locator('.stat-card').first().waitFor();
  await page.screenshot({
    path: path.join(screenshotDir, '2026-04-24-dashboard-llm-usage.png'),
    fullPage: false,
  });
  await context.close();
}

async function captureSettings(browser, token) {
  const context = await createContext(browser);
  const page = await context.newPage();
  await primeAuth(page, token);
  await page.goto(`${baseUrl}/settings`, { waitUntil: 'networkidle' });
  await page.locator('.settings-page').waitFor();
  await page.locator('.settings-card').first().waitFor();
  await page.screenshot({
    path: path.join(screenshotDir, '2026-04-24-settings-project-access.png'),
    fullPage: false,
  });
  await context.close();
}

async function captureAdmin(browser, token) {
  const context = await createContext(browser);
  const page = await context.newPage();
  await primeAuth(page, token);
  await page.goto(`${baseUrl}/admin`, { waitUntil: 'networkidle' });
  await page.locator('.settings-page').waitFor();
  await page.locator('.admin-card-header').first().waitFor();
  await page.screenshot({
    path: path.join(screenshotDir, '2026-04-24-admin-project-permissions.png'),
    fullPage: false,
  });
  await context.close();
}

async function main() {
  await fs.mkdir(screenshotDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
  });

  try {
    const localEnv = await loadLocalEnv();
    const userToken = await login(
      readConfig(localEnv, 'DEFAULT_USER_USERNAME', 'irving'),
      readConfig(localEnv, 'DEFAULT_USER_PASSWORD', 'n1ghthill2026')
    );
    const adminToken = await login(
      readConfig(localEnv, 'DEFAULT_ADMIN_USERNAME', 'admin'),
      readConfig(localEnv, 'DEFAULT_ADMIN_PASSWORD', 'devsynapse2026')
    );
    const conversationId = `docs-shot-${Date.now()}`;

    await seedConversation(userToken, conversationId);
    await captureLogin(browser);
    await captureChat(browser, userToken, conversationId);
    await captureDashboard(browser, userToken);
    await captureSettings(browser, userToken);
    await captureAdmin(browser, adminToken);

    console.log(
      JSON.stringify(
        {
          conversationId,
          screenshots: [
            '2026-04-24-login-screen.png',
            '2026-04-24-chat-command-execution.png',
            '2026-04-24-dashboard-llm-usage.png',
            '2026-04-24-settings-project-access.png',
            '2026-04-24-admin-project-permissions.png',
          ],
        },
        null,
        2
      )
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
