# DevSynapse AI — Tauri Desktop App

## Estrutura final do projeto

```
devsynapse-ai/
├── api/                    # FastAPI routes + models
├── core/                   # Business logic + memory stores
│   ├── deepseek.py         # DeepSeekClient (transporte LLM)
│   ├── brain.py            # DevSynapseBrain (orquestrador)
│   └── memory/             # Persistence layer (facade + 3 stores)
├── config/                 # Settings (pydantic-settings)
├── frontend/               # React + Vite + TypeScript
│   ├── src/                # Frontend source
│   ├── package.json        # Scripts: dev, build, tauri, desktop:dev, desktop:build
│   ├── vite.config.ts      # Vite config (Tauri-aware)
│   └── index.html          # Tauri entry point
│   └── src-tauri/          # Tauri v2 Rust project
│       ├── Cargo.toml      # Rust dependencies
│       ├── tauri.conf.json # Window, bundle, sidecar config
│       ├── capabilities/   # Tauri permissions
│       ├── icons/          # App icons (32x32, 128x128, .icns, .ico)
│       ├── binaries/       # PyInstaller sidecar output
│       │   └── devsynapse-backend-{target-triple}
│       └── src/            # Backend lifecycle + Tauri commands
├── backend-entry.py        # PyInstaller entry point
├── backend.spec            # PyInstaller spec file
├── scripts/
│   └── build-backend.sh    # Build Python sidecar with PyInstaller
└── requirements.txt        # Python dependencies
```

## Pré-requisitos

| Software    | Versão mínima | Verificar com        |
|-------------|--------------|----------------------|
| Rust        | 1.80+        | `rustc --version`    |
| Node.js     | 20+          | `node --version`     |
| npm         | 10+          | `npm --version`      |
| Python      | 3.11+        | `python3 --version`  |
| PyInstaller | 6+           | `pip install pyinstaller` |

### Instalação de dependências de sistema

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install -y build-essential curl wget file \
    libwebkit2gtk-4.1-dev libappindicator3-dev \
    librsvg2-dev patchelf libssl-dev libgtk-3-dev \
    libayatana-appindicator3-dev javascriptcoregtk-4.1 \
    libsoup-3.0-dev
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup default stable
```

**macOS:**
```bash
xcode-select --install
curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh
```

**Windows:**
```powershell
winget install Rustlang.Rustup Microsoft.VisualStudio.2022.BuildTools
```

## Setup rápido

```bash
cd devsynapse-ai

# 1. Python backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edite DEEPSEEK_API_KEY no .env

# 2. Frontend (Vite + React + Tauri JS API)
cd frontend
npm install
cd ..
```

## Como testar localmente (dev mode)

No modo dev, o Tauri pode iniciar o backend sidecar se ele já tiver sido
compilado. Para trabalhar sem sidecar, rode o backend Python manualmente em
`127.0.0.1:8000`; o frontend usa esse fallback quando está em Vite dev.

```bash
# Opção A — com sidecar
make desktop-dev

# Opção B — backend Python manual
source venv/bin/activate
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload

cd frontend
npm run tauri:dev
```

Em builds desktop, o frontend chama o comando Tauri `get_backend_status` apenas
para descobrir a porta local dinâmica. As chamadas de produto continuam sendo
HTTP para `http://127.0.0.1:PORT`.

## Build de produção

O caminho recomendado é o alvo do `Makefile`, que compila o sidecar Python e em
seguida roda o build Tauri:

```bash
make desktop-build
```

O equivalente manual é:

```bash
source venv/bin/activate
make desktop-backend
cd frontend
npm run tauri:build
```

`make desktop-backend` gera `dist/devsynapse-backend` e copia o executável para
`frontend/src-tauri/binaries/devsynapse-backend-{target-triple}`. Para builds
cross-target, defina `TAURI_TARGET_TRIPLE` ou `CARGO_BUILD_TARGET`, mas gere o
binário Python no próprio sistema operacional de destino.

### Updater desktop

O app Tauri tem comandos nativos para checar e instalar atualização pela tela
Settings. Builds locais normais deixam o updater desabilitado até que uma chave
pública seja embutida no binário:

```bash
export DEVSYNAPSE_UPDATER_PUBLIC_KEY="conteúdo da public key do Tauri signer"
export DEVSYNAPSE_UPDATER_ENDPOINT="https://github.com/N1ghthill/devsynapse-ai/releases/latest/download/latest.json"
```

Para gerar artefatos assinados de atualização, exporte a chave privada do signer
e use o alvo de release com updater:

```bash
cd frontend
npm run tauri signer generate -- -w ~/.tauri/devsynapse-updater.key

export TAURI_SIGNING_PRIVATE_KEY="$(cat "$HOME/.tauri/devsynapse-updater.key")"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD=""

cd ..
make desktop-build-updates
```

Depois gere e publique `latest.json` com:

```bash
python3 scripts/generate-tauri-update-manifest.py \
  --version 0.5.2 \
  --platform linux-x86_64 \
  --url "https://github.com/N1ghthill/devsynapse-ai/releases/download/v0.5.2/DevSynapse_AI_0.5.2_amd64.deb" \
  --signature-file "frontend/src-tauri/target/release/bundle/deb/DevSynapse AI_0.5.2_amd64.deb.sig" \
  --notes "Release notes" \
  --output latest.json
```

### Ícones

Os ícones versionados em `frontend/src-tauri/icons/` já são suficientes para o
build. Quando trocar o ícone fonte em `assets/Favcon.png`, regenere os formatos
nativos:

```bash
cd frontend
npm run icons:tauri
#     └─ gera todos os formatos (32x32, 128x128, .icns, .ico)
```

No Linux, `tauri.linux.conf.json` limita o build padrão a `deb` e `rpm`, porque
AppImage depende de `linuxdeploy` e pode falhar por ambiente. Para tentar
AppImage explicitamente, use `npm exec tauri build -- --bundles appimage`.

Status dos artefatos para downloads públicos:

| Plataforma | Artefato | Status |
|------------|----------|--------|
| Linux x86_64 | `frontend/src-tauri/target/release/bundle/deb/DevSynapse AI_0.5.2_amd64.deb` | validado em 2026-04-28 |
| Linux x86_64 | `frontend/src-tauri/target/release/bundle/rpm/DevSynapse AI-0.5.2-1.x86_64.rpm` | validado em 2026-04-28 |
| Linux x86_64 | AppImage | opt-in/experimental |
| macOS | `.dmg` / `.app` | configurado, ainda não validado |
| Windows x86_64 | NSIS `.exe` | validado via GitHub Actions em 2026-04-27 |

Para a landing page, use [docs/deployment/desktop-distribution.md](docs/deployment/desktop-distribution.md)
como fonte de verdade dos links que podem ser publicados.

## Arquitetura de comunicação

```
┌─────────────────────────────────────────────────┐
│               Tauri Desktop App                  │
│                                                  │
│  ┌──────────────────┐   ┌────────────────────┐  │
│  │  React + Vite    │   │  Python/FastAPI    │  │
│  │  (webview)       │───│  (sidecar proc)    │  │
│  │                  │   │                    │  │
│  │  localhost:5173  │   │  localhost:PORT    │  │
│  │  (dev)           │   │  (dynamic)         │  │
│  │  file:///dist/   │   │                    │  │
│  │  (production)    │   │  SQLite .db files  │  │
│  └──────────────────┘   └────────────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  Rust main.rs                            │   │
│  │  • spawns Python sidecar                 │   │
│  │  • health check (TCP connect :PORT)      │   │
│  │  • system tray (show/hide/quit)          │   │
│  │  • kills Python on app exit              │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

O frontend usa IPC do Tauri somente para descobrir a porta do sidecar. A
comunicação funcional com a API é HTTP puro (`localhost:PORT`). O Tauri gerencia
o ciclo de vida (spawn/kill), porta dinâmica e bandeja.

## Fluxo de inicialização

1. Tauri main.rs detecta uma porta livre com `TcpListener::bind("127.0.0.1:0")`
2. Spawn `devsynapse-backend --port PORT --data-dir /app/data`
3. Poll TCP connect em `127.0.0.1:PORT` até 15s de timeout
4. Cria janela webview carregando `frontend/dist/index.html`
5. Frontend chama `get_backend_status`, resolve `http://127.0.0.1:PORT` e faz health check
6. Ao fechar janela → esconde na bandeja (tray)
7. Ao sair pelo tray → `process.kill()` no sidecar Python

## Variáveis de ambiente

O backend aceita as mesmas variáveis do `.env.example`. Em produção, o Tauri as define
antes de spawnar o sidecar:

```
API_PORT              → definido pelo Rust (porta dinâmica)
DEVSYNAPSE_DATA_DIR   → {app_data}/devsynapse-ai/data
DEVSYNAPSE_LOGS_DIR   → {app_data}/devsynapse-ai/logs
DEVSYNAPSE_CONFIG_DIR → {app_data}/devsynapse-ai/config
```

As demais (DEEPSEEK_API_KEY, modelo, budgets) devem ser configuradas no arquivo
`.env` dentro do diretório de configuração do app, ou passadas como variáveis de
ambiente do sistema.

## Troubleshooting

### "Python não achou" / "Backend binary not found"

O sidecar não foi compilado ou copiado para `frontend/src-tauri/binaries/`.

```bash
# Verifique se o binário existe com o nome correto:
ls -la frontend/src-tauri/binaries/
# Deve mostrar: devsynapse-backend-x86_64-unknown-linux-gnu (Linux)
#              devsynapse-backend-x86_64-apple-darwin     (macOS)
#              devsynapse-backend-x86_64-pc-windows-msvc.exe (Windows)
```

Se o target-triple estiver errado, confira com:
```bash
rustc -vV | grep host
```

### "Porta já em uso"

Algum processo está usando a porta que o Tauri escolheu. O Rust escolhe uma porta
livre automaticamente, mas se outra instância do app já estiver rodando, feche-a
primeiro. Em dev mode, certifique-se de que o backend não está rodando na mesma
porta que o Vite (5173).

### "Blocked by CORS policy"

O `tauri.conf.json` inclui `connect-src 'self' http://127.0.0.1:* http://localhost:*`
no CSP. Se o backend estiver em outra interface, ajuste o CSP.

### "uvicorn module not found" (PyInstaller)

PyInstaller não encontrou os internals do uvicorn. Execute com:
```bash
python -m PyInstaller --clean backend.spec
```

### "libssl.so / libcrypto.so not found" (Linux)

Instale as dependências de sistema:
```bash
sudo apt install -y libssl-dev
```

### "DevSynapse AI quit unexpectedly" (macOS)

Verifique o Console.app para logs. O binary Python pode precisar de permissão de
execução no pacote .app:
```bash
chmod +x frontend/src-tauri/binaries/devsynapse-backend-*
codesign --force --sign - frontend/src-tauri/binaries/devsynapse-backend-*
```

### Modo verbose para debug

```bash
RUST_LOG=debug cd frontend && npm run tauri:dev
```
Isso mostra todos os logs de spawn, health check e encerramento do sidecar.
