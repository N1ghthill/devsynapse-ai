# DeepSeek Cost Optimization Plan

Documento gerado em 27 de abril de 2026.

Base: DeepSeek V4 + arquitetura atual do DevSynapse AI.

Objetivo: transformar o DevSynapse AI em um agente de baixo custo para
desenvolvedores sem recursos, mantendo qualidade suficiente para trabalho real.

Fontes operacionais:

- DeepSeek Models & Pricing: <https://api-docs.deepseek.com/quick_start/pricing>
- DeepSeek Context Caching: <https://api-docs.deepseek.com/guides/kv_cache/>
- DeepSeek Reasoning Model: <https://api-docs.deepseek.com/guides/reasoning_model>

## Status de Implementação

Implementado:

- roteamento Flash/Pro por heurística de complexidade;
- fallback Flash -> Pro quando a chamada Flash falha;
- modo economia automático quando o budget entra em estado crítico;
- perfil semântico de tarefa (`task_type` + `task_signature`) para decisões
  reutilizáveis;
- aprendizado persistente a partir de feedback do usuário e resultado de
  comandos executados;
- histórico de decisões de rota para auditar por que um modelo foi escolhido;
- métricas de cache hit/miss e cache hit rate no dashboard;
- preços padrão atualizados para a tabela oficial vigente em 27 de abril de 2026;
- configurações administrativas para modelo Flash, modelo Pro, roteamento,
  economia automática e threshold de cache.

Ainda pendente:

- cache de respostas frequentes;
- R1 Harvest com governança de custo e latência;
- gestão de contexto estendido de 1M tokens;
- previsão de esgotamento de orçamento.
- avaliação de qualidade automática por tarefa, além do feedback explícito.

## 1. Cache de Prefixo

O Context Caching da DeepSeek é ativado por padrão. O que o DevSynapse precisa
fazer é manter prefixos estáveis e rastrear se a API está de fato retornando
cache hit.

Ordem de prompt:

1. system prompt estável;
2. preferências e contexto de projeto;
3. histórico recente;
4. pergunta atual.

Métricas:

- `prompt_cache_hit_tokens`;
- `prompt_cache_miss_tokens`;
- `cache_hit_rate_pct`;
- custo estimado por chamada.

Alvo: cache hit rate acima de 70% em uso normal.

## 2. Roteamento Flash/Pro

Regra base:

- Simple: Flash;
- Medium: Flash com fallback para Pro;
- Complex: Pro;
- Budget crítico: Flash sem fallback automático.

Sinais de complexidade:

- arquitetura, segurança, autorização, cache, migrações, concorrência;
- pedidos longos ou com múltiplos arquivos;
- reclamação explícita de qualidade da resposta anterior.

O roteamento é intencionalmente determinístico para ser barato, auditável e
testável. Classificação por LLM só deve entrar se o ganho justificar custo e
latência.

O agente também registra `agent_route_decisions` e aprende em `agent_learning`.
Quando feedback negativo ou falha de comando aparece para uma assinatura de
tarefa, o roteador passa a poder promover tarefas similares para Pro. Feedback
positivo reforça o modelo que resolveu bem a tarefa.

## 2.1 Aprendizado do Agente

O aprendizado atual é local, explícito e auditável:

- feedback positivo reforça o modelo usado naquela assinatura de tarefa;
- feedback negativo ensina preferência por Pro para tarefas similares;
- comando bem-sucedido reforça a decisão que levou ao comando;
- comando falho cria sinal de cautela e preferência por modelo mais forte;
- padrões com confiança suficiente entram no prompt como contexto operacional.

Isso ainda não substitui avaliação humana, mas já deixa o agente diferente de um
passador de prompts: ele carrega memória de decisões e muda o roteamento futuro.

## 3. R1 Harvest

O `deepseek-reasoner` expõe `reasoning_content`, mas a própria documentação
informa que o campo não deve ser reenviado dentro da sequência de mensagens da
próxima chamada. A implementação futura deve transformar o raciocínio em um
brief operacional curto antes de injetar no V4.

Usar somente em:

- decisões de arquitetura;
- debugging multi-step;
- refatorações grandes;
- falhas repetidas do Flash.

Não usar em modo economia crítico.

## 4. Cache de Respostas Frequentes

Próxima etapa depois do roteamento:

- hashing semântico leve;
- tabela SQLite própria;
- TTL por tipo de pergunta;
- invalidação por versão de dependência ou mudança de projeto;
- métricas de acerto e tokens economizados.

TTLs sugeridos:

| Tipo | TTL |
| --- | --- |
| Conceitos | 90 dias |
| Erros comuns | 180 dias |
| Boilerplate | 30 dias |
| API específica | 7 dias |
| Debug específico | 1 dia |

## 5. Modo Economia

Quando o orçamento atinge estado crítico:

- bloquear Pro no roteador;
- manter Flash;
- desativar R1 Harvest;
- aumentar agressividade do cache de respostas quando ele existir;
- comunicar o estado no dashboard.

## 6. Contexto de 1M Tokens

O contexto longo deve ser tratado como recurso caro, não como desculpa para
injetar tudo sempre.

Prioridade:

1. arquivos modificados recentemente;
2. arquivos citados na conversa;
3. documentação do projeto;
4. logs recentes;
5. restante do código, sob demanda.

## Métricas Globais

| Métrica | Alvo |
| --- | --- |
| Custo médio mensal por usuário | < R$ 10/mês |
| Cache hit rate | > 70% |
| Distribuição Flash/Pro | 80% / 20% |
| Alertas de orçamento | zero surpresas |
| Latência Flash | < 5 segundos |
| Latência Pro | < 15 segundos |

## Princípios

1. nada de modelo local como requisito;
2. DeepSeek-first, mas com desenho adaptável;
3. orçamento é requisito de produto;
4. transparência de custo no dashboard;
5. acesso acima de tudo.
