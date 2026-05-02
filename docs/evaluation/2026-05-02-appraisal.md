# Avaliacao do DevSynapse AI - 2026-05-02

## Escopo

Esta avaliacao foi feita com cuidado para nao tocar nos repositorios reais do usuario. O
laboratorio usado foi criado em `/tmp/devsynapse-eval-final-2026-05-02`, com runtime,
SQLite, workspace e dois repositorios Git descartaveis:

- `react-widget-lab`: fixture Node.js com testes `node --test` e um build check.
- `python-service-lab`: fixture Python com testes `pytest`.

Nao houve push para GitHub. O teste nao usou repositorios reais do operador
como alvo de execucao do DevSynapse.

## Artefatos

- Resultado estruturado da bateria de API/execucao: [2026-05-02-api-execution-results.json](2026-05-02-api-execution-results.json)
- Capturas:
  - [login](screenshots/2026-05-02-login.png)
  - [chat empty state](screenshots/2026-05-02-chat-empty-state.png)
  - [seletor de projetos](screenshots/2026-05-02-project-selector.png)
  - [dashboard de telemetria](screenshots/2026-05-02-dashboard-telemetry.png)
  - [admin/permissoes](screenshots/2026-05-02-admin-project-permissions.png)
  - [settings/modelos/orcamento](screenshots/2026-05-02-settings-budget-models.png)

## Validacao Executada

### Baseline do repositorio

`make verify` passou localmente:

- Ruff: passou.
- Backend: `225 passed in 4.48s`.
- Shell/Python script checks: passaram.
- Frontend ESLint: passou.
- Frontend production build: passou.

`make ui-smoke` tambem passou com runtime temporario:

- migrations aplicadas em bancos temporarios;
- frontend buildado para API temporaria;
- Playwright validou login, chat, projetos, dashboard, settings e admin;
- resultado: `ui-smoke-ok`.

### Testes praticos com DevSynapse em projetos descartaveis

Resultados principais:

| Cenario | Resultado |
| --- | --- |
| API operacional | `GET /api` retornou `status=operational` |
| Login admin e usuario comum | OK |
| Descoberta/listagem de projetos | `python-service-lab` e `react-widget-lab` listados |
| Permissao de mutacao por projeto | `eval-user` liberado apenas para `react-widget-lab` |
| CWD do comando travado no projeto | `bash "pwd"` executou em `/tmp/.../react-widget-lab` |
| Testes Node no projeto React | `2 pass` |
| Build check Node | `build-check-ok` |
| Escrita permitida no projeto liberado | criou `DEV_EVIDENCE.md` em `react-widget-lab` |
| Escrita em projeto sem permissao | bloqueada com `authorization_failed` |
| Escrita escapando com `../` | bloqueada com `project_scope_mismatch` |
| Padrao destrutivo `rm -rf` | bloqueado com `validation_failed` |
| Testes Python como admin | `2 passed` |
| Memoria project-scoped | criada para `react-widget-lab` |
| Telemetria | dashboard registrou comandos, falhas bloqueadas, memoria e alertas |
| Auditoria admin | registrou atualizacao de escopo de mutacao do usuario |

Esses testes dao evidencia objetiva de que o nucleo de orquestracao local esta funcionando:
ele resolve projeto, executa no diretorio correto, separa papel admin/usuario, exige allowlist
para mutacoes, bloqueia caminhos fora do projeto e registra telemetria.

## Pontos Fortes

1. **Modelo local-first coerente.** O app roda em FastAPI + React + SQLite, com runtime local e
configuracao separada do checkout. Isso combina bem com a proposta de "controle local sobre
um agente de codigo".

2. **Orquestrador com controles reais.** A validacao pratica confirmou comandos em cwd do projeto,
mutacoes por allowlist, bloqueio de escape de path e blacklist de padroes destrutivos.

3. **Evidencia de maturidade de engenharia.** A suite atual passou com 225 testes backend, lint,
script checks, frontend lint/build e smoke browser. Para um produto local-first, isso e uma base
boa.

4. **Telemetria e custo como parte do produto.** Dashboard registra comandos, falhas, alertas,
memorias, uso LLM e orcamento diario/mensal. Essa combinacao e um diferencial em relacao a
ferramentas que focam so no chat/agente.

5. **Permissoes por projeto sao um diferencial pratico.** O fluxo admin mostrou escopo global para
admin e allowlist para usuario comum. Isso e mais defensavel do que dar shell irrestrito para todo
operador local.

6. **UI ja passa sensacao de produto.** Login, seletor de projetos, painel, admin e settings estao
funcionais e relativamente consistentes. O seletor de projetos e a pagina admin deixam claro o
estado operacional do sistema.

## Onde Trabalhar

1. **Ampliar benchmarks com LLM real.** A bateria complementar em
[real-llm/2026-05-02-real-deepseek-evidence.md](real-llm/2026-05-02-real-deepseek-evidence.md)
ja validou um fluxo real com DeepSeek corrigindo testes em um projeto descartavel.
O proximo nivel e repetir esse padrao com mais tarefas: bug fix, feature pequena,
refactor, documentacao e bloqueio de comando perigoso.

2. **Separar "falha esperada" de "falha operacional".** O dashboard marcou bloqueios de seguranca
como falhas e alertas. Isso e tecnicamente correto, mas em demos e operacao seria melhor distinguir
`blocked_by_policy` de erro real, para nao parecer que o sistema esta instavel quando ele esta
protegendo o usuario.

3. **Internacionalizacao inconsistente.** A UI mistura portugues e ingles: `Painel`, `Ajustes`,
`Escolher projeto`, mas tambem `Settings`, `Save Changes`, `Project Mutation Allowlist`, `Warning`.
Para demonstracao publica, isso reduz polimento percebido.

4. **Comparativo competitivo pede benchmarks repetiveis.** Hoje ja ha smoke e testes, mas falta uma
suite de tarefas agenticas: "corrigir bug", "adicionar teste", "refatorar pequena funcao", "explicar
repo", "bloquear comando perigoso", sempre em fixtures descartaveis e com relatorio automatico.

5. **Automacao de screenshots poderia virar gate.** Ja existe `capture-doc-screenshots`, mas a
avaliacao mostrou valor em ter uma rotina de captura para cenarios de seguranca/orquestracao,
incluindo dashboard depois dos testes.

6. **Ainda nao compete em background/PR automation.** DevSynapse esta forte como agente local
controlado. Ele ainda nao oferece o mesmo fluxo de branch/PR/background worker de Copilot cloud
agent, Cursor Background Agents ou Claude Code web/cloud.

## Comparacao Com Ferramentas Semelhantes

Referencias consultadas em 2026-05-02:

- GitHub Copilot cloud agent: <https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent>
- Cursor Background Agents: <https://docs.cursor.com/en/background-agents>
- Claude Code: <https://code.claude.com/docs>
- OpenHands: <https://docs.openhands.dev/overview/introduction>
- OpenCode: <https://dev.opencode.ai/docs/>
- Continue: <https://docs.continue.dev/index>

| Produto | Forca principal | Comparacao com DevSynapse |
| --- | --- | --- |
| GitHub Copilot cloud agent | Trabalha em ambiente GitHub Actions, cria branch, testa e pode abrir PR | Mais forte em fluxo colaborativo GitHub/PR; DevSynapse e mais local-first e controlavel no host do usuario |
| Cursor Background Agents | Agentes remotos assincronos em ambiente Ubuntu, integrados a GitHub e Slack/Linear | Mais forte em background remoto; DevSynapse e mais simples, local e explicito em permissoes por projeto |
| Claude Code | Agente maduro em terminal/IDE/desktop/web, edita arquivos, roda comandos, usa MCP e subagentes | Mais forte em ecossistema e autonomia; DevSynapse se diferencia em BYOK DeepSeek, SQLite local, dashboard de custo e autorizacao por projeto |
| OpenHands | Plataforma agentica com SDK, CLI, GUI local, cloud, enterprise, RBAC, uso e budgeting | Mais ampla como plataforma; DevSynapse e mais focado e leve para Linux/local-first com DeepSeek |
| OpenCode | Agente open source terminal/desktop/IDE, multi-provider | Mais maduro como CLI agent; DevSynapse agrega UI operacional, permissao, auditoria e telemetria local |
| Continue | Fluxos de checks AI em PR e automacao de revisao | Mais voltado a checks/review; DevSynapse atua como operador local de desenvolvimento com execucao controlada |

## Leitura de Maturidade

Minha avaliacao: **maduro para MVP/local-first e promissor como orquestrador controlado**.

O DevSynapse ja tem sinais fortes de produto: arquitetura limpa, contrato documentado, testes,
smoke de UI, dashboard, permissoes, auditoria, execucao por projeto e uma primeira evidencia
real com DeepSeek corrigindo um fixture descartavel. A maior lacuna nao e o nucleo de engenharia,
mas sim transformar essa evidencia em uma suite de benchmark recorrente e comparavel.

## Norte Recomendado

1. Criar `make eval-agent` para subir runtime descartavel, criar fixtures, rodar comandos,
capturar screenshots e gerar relatorio JSON/Markdown.
2. Expandir a bateria com DeepSeek real opcional, ativada apenas quando
`DEEPSEEK_API_KEY` estiver presente, cobrindo mais classes de tarefa.
3. Criar fixtures padrao de benchmark:
   - bug pequeno com teste falhando;
   - feature pequena com teste esperado;
   - refactor sem mudanca de comportamento;
   - comando perigoso que deve ser bloqueado;
   - tentativa de escrita fora do projeto que deve ser bloqueada.
4. Separar no dashboard bloqueios de politica de falhas operacionais.
5. Padronizar idioma da UI antes de demonstracao publica.
6. Publicar uma pagina "Evidence" no docs/showcase com screenshots atuais, comandos rodados e
resultados reproduziveis.

## Conclusao

O DevSynapse nao parece apenas um prototipo. A evidencia local mostra um produto com um bom
orquestrador de execucao e uma preocupacao real com seguranca, auditoria e custo. A execucao
real com DeepSeek reforca que o produto ja consegue diagnosticar, editar e validar codigo em
um projeto descartavel. O proximo passo para provar maturidade fora do ambiente do autor e
transformar esta avaliacao manual em uma suite reproduzivel, com modo sem LLM para
seguranca/orquestracao e modo com LLM real para medir qualidade agentica.
