# Plano Arquitetural: DevSynapse AI - Sistema de Agentes Configurável

## Visão Geral

Sistema de agentes de código local-first com arquitetura modular, multi-tenant e 100% configurável via YAML/JSON, com controle granular de custos e sistema de plugins extensível.

---

## 1. Diagrama de Arquitetura (Texto)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE APRESENTAÇÃO                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   TUI        │  │   CLI        │  │  API REST    │  │  Web UI      │     │
│  │  (Textual)   │  │  (Typer)     │  │  (FastAPI)   │  │  (Future)    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │                 │              │
│         └─────────────────┴─────────────────┴─────────────────┘              │
│                                    │                                         │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAMADA DE ORQUESTRAÇÃO                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    AGENT ORCHESTRATOR                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ Workflow    │  │ Agent       │  │ Task        │  │ Approval    │  │   │
│  │  │ Engine      │  │ Dispatcher  │  │ Scheduler   │  │ Manager     │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│         ┌─────────────────────────┼─────────────────────────┐                │
│         ▼                         ▼                         ▼                │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐        │
│  │  Router     │           │   Event     │           │   State     │        │
│  │  Engine     │◄─────────►│   Bus       │◄─────────►│   Manager   │        │
│  └──────┬──────┘           └─────────────┘           └─────────────┘        │
│         │                                                                    │
└─────────┼────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAMADA DE AGENTES                                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      AGENT RUNTIME                                   │   │
│  │                                                                      │   │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │   │ Code     │  │ Review   │  │ Test     │  │ Docs     │            │   │
│  │   │ Agent    │  │ Agent    │  │ Agent    │  │ Agent    │            │   │
│  │   │ (Built-in│  │ (Built-in│  │ (Built-in│  │ (Built-in│            │   │
│  │   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │   │
│  │        │             │             │             │                   │   │
│  │   ┌────┴─────────────┴─────────────┴─────────────┴────┐             │   │
│  │   │              PLUGIN SYSTEM                         │             │   │
│  │   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │             │   │
│  │   │  │ Custom  │ │ Custom  │ │ Custom  │ │ Custom  │  │             │   │
│  │   │  │ Agent 1 │ │ Agent 2 │ │ Agent N │ │ Agent N │  │             │   │
│  │   │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │             │   │
│  │   └───────────────────────────────────────────────────┘             │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAMADA DE MODELOS (LLM)                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MODEL MANAGER                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ Registry    │  │ Pricing     │  │ Fallback    │  │ Budget      │  │   │
│  │  │ Service     │  │ Calculator  │  │ Handler     │  │ Controller  │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  │                                                                      │   │
│  │   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐             │   │
│  │   │OpenAI   │   │DeepSeek │   │Anthropic│   │ Ollama  │   ...       │   │
│  │   │Provider │   │Provider │   │Provider │   │Provider │             │   │
│  │   └─────────┘   └─────────┘   └─────────┘   └─────────┘             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAMADA DE INFRAESTRUTURA                            │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Config Store │  │ Event Store  │  │ Audit Log    │  │ Metrics      │     │
│  │ (YAML/JSON)  │  │ (SQLite)     │  │ (SQLite)     │  │ (Prometheus) │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Multi-tenant │  │ Hot Reload   │  │ Rate Limiter │  │ Secret       │     │
│  │ Manager      │  │ Service      │  │ (Redis/SQL)  │  │ Manager      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Estrutura de Configuração YAML (Exemplo Completo)

```yaml
# config/system.yaml - Configuração Global do Sistema
system:
  version: "2.0.0"
  environment: "production"

  # Hot reload configuration
  hot_reload:
    enabled: true
    watch_paths:
      - "./config/agents/"
      - "./config/workflows/"
      - "./config/providers/"
    debounce_ms: 500

  # Multi-tenant configuration
  multi_tenant:
    enabled: true
    isolation_level: "strict"  # strict | shared_db | shared_schema
    default_tenant: "default"

  # Event system
  event_bus:
    backend: "sqlite"  # sqlite | redis | memory
    persistence: true
    retention_days: 90

# config/providers/models.yaml - Registro Dinâmico de Modelos
providers:
  # Fonte primária: API externa
  registry_source:
    type: "api"  # api | file | database
    url: "https://api.openrouter.ai/models"
    refresh_interval: "1h"
    cache_ttl: "30m"

  # Fallback: arquivo local
  fallback_registry: "./config/providers/models-local.yaml"

  # Provedores configuráveis
  openai:
    enabled: true
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    models:
      - id: "gpt-4o"
        alias: "gpt-4o"
        context_window: 128000
        cost_per_1k_input: 0.005
        cost_per_1k_output: 0.015
        capabilities: ["code", "chat", "vision"]
        rate_limit: 10000  # requests per minute
      - id: "gpt-4o-mini"
        alias: "gpt-4o-mini"
        context_window: 128000
        cost_per_1k_input: 0.00015
        cost_per_1k_output: 0.0006
        capabilities: ["code", "chat"]
        rate_limit: 30000

    # Dynamic pricing overrides
    pricing_overrides:
      - model: "gpt-4o"
        multiplier: 1.0  # Can be updated dynamically

  deepseek:
    enabled: true
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: "https://api.deepseek.com"
    models:
      - id: "deepseek-chat"
        alias: "deepseek-v3"
        context_window: 64000
        cost_per_1k_input: 0.00027
        cost_per_1k_output: 0.0011
        capabilities: ["code", "chat"]
        rate_limit: 1000

  anthropic:
    enabled: true
    api_key: "${ANTHROPIC_API_KEY}"
    models:
      - id: "claude-3-5-sonnet-20241022"
        alias: "claude-sonnet"
        context_window: 200000
        cost_per_1k_input: 0.003
        cost_per_1k_output: 0.015
        capabilities: ["code", "chat", "vision", "long_context"]
        rate_limit: 4000

  # Local/Ollama provider
  ollama:
    enabled: true
    base_url: "http://localhost:11434"
    models:
      - id: "codellama"
        alias: "local-codellama"
        context_window: 16000
        cost_per_1k_input: 0.0
        cost_per_1k_output: 0.0
        capabilities: ["code"]

# config/budget/global.yaml - Controles de Orçamento Globais
budget:
  # Orçamento global do sistema
  global:
    monthly_limit: 1000.00
    currency: "USD"
    alert_thresholds: [50, 75, 90, 100]
    alert_channels: ["email", "slack", "in_app"]

  # Rate limiting global
  rate_limits:
    requests_per_minute: 1000
    tokens_per_minute: 1000000
    cost_per_minute: 10.00

  # Estratégia de fallback por custo
  fallback_strategy:
    enabled: true
    max_cost_per_request: 0.50
    fallback_chain:
      - "gpt-4o"
      - "claude-sonnet"
      - "deepseek-v3"
      - "gpt-4o-mini"
      - "local-codellama"

# config/agents/code-agent.yaml - Definição de Agente
agents:
  code_generator:
    name: "Code Generator"
    description: "Gera código a partir de descrições em linguagem natural"
    version: "1.0.0"

    # Nível de autonomia
    autonomy_level: "supervised"  # autonomous | supervised | manual

    # Modelo preferido e alternativas
    model:
      primary: "gpt-4o"
      fallbacks: ["claude-sonnet", "deepseek-v3"]
      budget_model: "gpt-4o-mini"
      local_model: "local-codellama"

    # Prompts customizáveis
    prompts:
      system: |
        Você é um desenvolvedor sênior especializado em {language}.
        Siga as convenções do projeto e as melhores práticas.

        Contexto do projeto:
        {project_context}

        Estilo de código:
        {code_style}

      templates_dir: "./prompts/code-generator/"

      # Templates específicos por tarefa
      templates:
        generate_function:
          file: "generate_function.md"
          variables: ["language", "description", "existing_code"]
        refactor_code:
          file: "refactor_code.md"
          variables: ["code", "goal", "constraints"]

    # Ferramentas disponíveis
    tools:
      - name: "file_reader"
        enabled: true
        config:
          allowed_extensions: [".py", "*.js", "*.ts", "*.md"]
          max_file_size: "1MB"

      - name: "file_writer"
        enabled: true
        requires_approval: true  # Precisa de aprovação para escrita
        config:
          allowed_paths: ["./src/", "./tests/"]
          backup_before_write: true

      - name: "shell_executor"
        enabled: false  # Desabilitado por padrão por segurança

    # Regras de aprovação específicas do agente
    approval_rules:
      file_write:
        condition: "always"  # always | on_change | never
        approvers: ["user", "senior_dev"]

      code_execution:
        condition: "on_change"
        max_auto_execute: 3  # Número de execuções automáticas permitidas

    # Budget específico do agente
    budget:
      daily_limit: 50.00
      per_task_limit: 5.00
      alert_at: 80  # Percentual

    # Métricas e telemetria
    telemetry:
      enabled: true
      track_tokens: true
      track_latency: true
      track_cost: true

  # Outro agente exemplo
  code_reviewer:
    name: "Code Reviewer"
    autonomy_level: "autonomous"  # Pode revisar sem supervisão

    model:
      primary: "claude-sonnet"  # Prefere Claude para análise
      budget_model: "gpt-4o-mini"

    prompts:
      system: |
        Você é um revisor de código experiente. Analise o código para:
        - Bugs e vulnerabilidades de segurança
        - Performance e eficiência
        - Legibilidade e manutenibilidade
        - Conformidade com padrões do projeto

    # Esse agente pode delegar para outros
    delegation:
      enabled: true
      can_delegate_to: ["code_generator", "test_writer"]
      max_delegation_depth: 2

# config/workflows/main.yaml - Workflows Configuráveis
workflows:
  feature_development:
    name: "Feature Development"
    description: "Fluxo completo de desenvolvimento de feature"

    # Checkpoints definidos pelo usuário
    checkpoints:
      - id: "review_design"
        name: "Revisar Design"
        description: "Pausar para revisão do design proposto"
        position: "after:design_phase"

      - id: "review_implementation"
        name: "Revisar Implementação"
        description: "Pausar antes de aplicar mudanças"
        position: "after:generate_code"
        condition: "has_changes > 50"  # Só pausa se > 50 linhas mudaram

    # Definição do fluxo
    steps:
      - id: "analyze_requirements"
        name: "Analyze Requirements"
        agent: "requirements_analyzer"
        input: "{{ user_request }}"
        output: "requirements_analysis"

      - id: "design_phase"
        name: "Design Solution"
        agent: "architect"
        input: "{{ requirements_analysis }}"
        output: "design_doc"
        # Branching condicional
        condition: "{{ requirements_analysis.complexity }} > 'medium'"

      - id: "generate_code"
        name: "Generate Code"
        agent: "code_generator"
        input:
          requirements: "{{ requirements_analysis }}"
          design: "{{ design_doc }}"
        output: "generated_code"
        parallelism: 1  # Pode paralelizar em múltiplos arquivos

      - id: "review_code"
        name: "Review Code"
        agent: "code_reviewer"
        input: "{{ generated_code }}"
        output: "review_feedback"
        # Loop: se houver issues críticas, volta para geração
        on_failure: "retry_with_feedback"
        max_retries: 3

      - id: "generate_tests"
        name: "Generate Tests"
        agent: "test_writer"
        input:
          code: "{{ generated_code }}"
          review: "{{ review_feedback }}"
        output: "test_code"
        condition: "{{ config.auto_generate_tests }} == true"

      - id: "apply_changes"
        name: "Apply Changes"
        agent: "code_applier"
        input:
          code: "{{ generated_code }}"
          tests: "{{ test_code }}"
        action: "write_files"
        requires_approval: true

  # Workflow de bugfix simples
  bugfix:
    name: "Quick Bugfix"
    description: "Fluxo simplificado para correção de bugs"

    steps:
      - id: "analyze_bug"
        agent: "debugger"
        output: "root_cause"

      - id: "fix_bug"
        agent: "code_generator"
        input: "{{ root_cause }}"
        context:
          mode: "bugfix"
        output: "fix"
        requires_approval: true

# config/projects/myproject.yaml - Configuração por Projeto
projects:
  myproject:
    name: "My Awesome Project"
    path: "/home/user/projects/myproject"

    # Isolamento multi-tenant
    tenant_id: "myproject"

    # Budget específico do projeto
    budget:
      monthly_limit: 200.00
      alert_thresholds: [50, 80, 95]

      # Rate limiting por projeto
      rate_limits:
        requests_per_hour: 100
        cost_per_hour: 10.00

    # Configurações de agentes específicas do projeto
    agents:
      code_generator:
        # Override de prompts
        prompts:
          system: |
            Você está trabalhando no projeto MyProject.
            Stack: Python 3.11, FastAPI, PostgreSQL, React
            Padrões: Clean Architecture, DDD

        # Override de ferramentas
        tools:
          file_writer:
            config:
              allowed_paths: ["./backend/", "./frontend/src/"]
              banned_paths: ["./backend/migrations/"]

        # Override de aprovações
        approval_rules:
          file_write:
            condition: "on_change"  # Mais permissivo que global

    # Variáveis de contexto do projeto
    context:
      language: "python"
      framework: "fastapi"
      database: "postgresql"
      code_style: "pep8"
      architecture: "clean_architecture"
      existing_patterns: |
        - Use dependency injection
        - Repository pattern para acesso a dados
        - Pydantic para validação

    # Workflows habilitados
    workflows:
      - "feature_development"
      - "bugfix"
      - "refactoring"

    # Regras de negócio
    rules:
      - name: "No production deploy on friday"
        condition: "day_of_week == 'friday'"
        action: "block"
        message: "Deploys em produção são bloqueados nas sextas-feiras"

      - name: "Require review for large changes"
        condition: "lines_changed > 100"
        action: "require_approval"
        approvers: ["tech_lead"]

# config/approval/roles.yaml - Sistema de Aprovação
approval_system:
  roles:
    - id: "user"
      name: "User"
      permissions: ["approve_own", "reject_any"]

    - id: "senior_dev"
      name: "Senior Developer"
      permissions: ["approve_any", "override_budget"]
      requires: "2fa"

    - id: "tech_lead"
      name: "Tech Lead"
      permissions: ["approve_any", "modify_workflows", "change_budget"]

    - id: "admin"
      name: "Administrator"
      permissions: ["*"]

  # Políticas de aprovação
  policies:
    budget_override:
      approvers: ["tech_lead", "admin"]
      requires_reason: true

    workflow_modification:
      approvers: ["admin"]
      requires_review: true

# config/plugins/registry.yaml - Sistema de Plugins
plugins:
  # Diretórios de plugins
  directories:
    - "./plugins/official/"
    - "./plugins/community/"
    - "~/.devsynapse/plugins/"

  # Plugins ativos
  active:
    - name: "security-scanner"
      version: "1.2.0"
      source: "pypi"
      config:
        severity_threshold: "medium"
        ignore_rules: ["SQL100"]

    - name: "custom-linter"
      source: "local"
      path: "./plugins/custom-linter"
      config: {}

  # Hooks disponíveis para plugins
  hooks:
    - "pre_agent_execute"
    - "post_agent_execute"
    - "pre_file_write"
    - "post_file_write"
    - "on_budget_alert"
    - "on_error"
    - "on_workflow_complete"

  # Sandbox de plugins
  sandbox:
    enabled: true
    allow_network: false
    allow_filesystem: ["./temp/"]
    max_memory: "512MB"
    timeout: 30
```

---

## 3. Componentes Principais e Interfaces

### 3.1 Core Components

#### Agent Orchestrator
```python
# Interface principal
class AgentOrcstrator:
    def __init__(self, config: OrchestratorConfig):
        self.workflow_engine = WorkflowEngine()
        self.agent_dispatcher = AgentDispatcher()
        self.approval_manager = ApprovalManager()
        self.event_bus = EventBus()

    async def execute_workflow(
        self,
        workflow_id: str,
        context: ExecutionContext,
        tenant_id: str
    ) -> WorkflowResult:
        """Executa um workflow configurável"""
        pass

    async def execute_agent(
        self,
        agent_id: str,
        task: Task,
        autonomy_level: AutonomyLevel
    ) -> AgentResult:
        """Executa um agente com nível de autonomia específico"""
        pass
```

#### Model Manager
```python
class ModelManager:
    def __init__(self, registry: ModelRegistry):
        self.pricing_calculator = PricingCalculator()
        self.fallback_handler = FallbackHandler()
        self.budget_controller = BudgetController()

    async def get_model_for_task(
        self,
        task: Task,
        budget: BudgetConstraints,
        preferences: ModelPreferences
    ) -> ModelSelection:
        """Seleciona o melhor modelo considerando custo e disponibilidade"""
        pass

    async def calculate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        region: str = "us"
    ) -> CostEstimate:
        """Calcula custo em tempo real com preços dinâmicos"""
        pass

    async def handle_fallback(
        self,
        failed_model: str,
        error: Exception,
        fallback_chain: List[str]
    ) -> Optional[str]:
        """Gerencia fallback automático entre modelos"""
        pass
```

#### Plugin System
```python
class PluginManager:
    def __init__(self):
        self.hooks: Dict[str, List[Plugin]] = {}
        self.sandbox = PluginSandbox()

    def register_plugin(self, plugin: Plugin) -> None:
        """Registra um plugin com validação de segurança"""
        pass

    async def execute_hook(
        self,
        hook_name: str,
        context: HookContext
    ) -> HookResult:
        """Executa todos os plugins registrados para um hook"""
        pass

    def hot_reload(self, plugin_id: str) -> bool:
        """Recarrega um plugin sem restart do sistema"""
        pass
```

### 3.2 Data Models

```python
# Modelos de dados principais

@dataclass
class ModelInfo:
    id: str
    alias: str
    provider: str
    capabilities: List[str]
    context_window: int
    pricing: DynamicPricing  # Preço pode mudar em runtime
    rate_limit: RateLimit
    availability: AvailabilityStatus

@dataclass
class DynamicPricing:
    base_input_cost: Decimal
    base_output_cost: Decimal
    multiplier: float = 1.0
    last_updated: datetime

    def get_current_cost(self, region: str) -> Tuple[Decimal, Decimal]:
        # Aplica multiplicadores regionais/dinâmicos
        pass

@dataclass
class Agent:
    id: str
    name: str
    version: str
    autonomy_level: AutonomyLevel
    model_config: ModelConfig
    prompts: PromptConfig
    tools: List[Tool]
    approval_rules: Dict[str, ApprovalRule]
    budget: BudgetConfig

@dataclass
class Workflow:
    id: str
    name: str
    steps: List[WorkflowStep]
    checkpoints: List[Checkpoint]
    variables: Dict[str, Any]
    parallelism_config: ParallelismConfig

@dataclass
class BudgetState:
    tenant_id: str
    project_id: str
    monthly_limit: Decimal
    current_usage: Decimal
    forecast: Decimal  # Projeção baseada em uso atual
    alerts_sent: List[Alert]
```

### 3.3 Event System

```python
# Eventos do sistema para audit trail e integração

class Events:
    # Model events
    MODEL_PRICING_UPDATED = "model.pricing_updated"
    MODEL_UNAVAILABLE = "model.unavailable"
    MODEL_FALLBACK_TRIGGERED = "model.fallback_triggered"

    # Agent events
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_AWAITING_APPROVAL = "agent.awaiting_approval"

    # Budget events
    BUDGET_THRESHOLD_REACHED = "budget.threshold_reached"
    BUDGET_EXCEEDED = "budget.exceeded"
    COST_ATTRIBUTED = "cost.attributed"

    # Workflow events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_CHECKPOINT_REACHED = "workflow.checkpoint_reached"
    WORKFLOW_COMPLETED = "workflow.completed"

    # Plugin events
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_HOOK_EXECUTED = "plugin.hook_executed"
    PLUGIN_ERROR = "plugin.error"
```

---

## 4. Estratégia para Volatilidade de Preços

### 4.1 Arquitetura de Preços Dinâmicos

```
┌─────────────────────────────────────────────────────────────────┐
│                    DYNAMIC PRICING ENGINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   External   │    │   Local      │    │   Predictive │      │
│  │   API Feed   │    │   Overrides  │    │   Cache      │      │
│  │   (Primary)  │    │   (Manual)   │    │   (Smart)    │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │                │
│         └───────────────────┼───────────────────┘                │
│                             │                                    │
│                             ▼                                    │
│                  ┌────────────────────┐                         │
│                  │  Pricing Resolver  │                         │
│                  │  - Merge sources   │                         │
│                  │  - Apply multipliers│                        │
│                  │  - Regional adjust │                         │
│                  └──────────┬─────────┘                         │
│                             │                                    │
│         ┌───────────────────┼───────────────────┐               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Real-time   │    │  Budget      │    │  Cost        │      │
│  │  Calculator  │    │  Controller  │    │  Forecaster  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Implementação

```python
class PricingManager:
    def __init__(self):
        self.api_client = PricingAPIClient()
        self.cache = PricingCache()
        self.local_overrides = LocalOverrideStore()
        self.predictor = CostPredictor()

    async def get_current_pricing(self, model_id: str, region: str) -> Pricing:
        """
        Estratégia de resolução de preços:
        1. Verifica cache (TTL curto, 5-10 min)
        2. Aplica overrides locais (prioridade máxima)
        3. Se cache expirado, busca da API
        4. Se API falha, usa último valor + predição
        """
        # Tenta cache primeiro
        cached = await self.cache.get(model_id, region)
        if cached and not cached.is_stale():
            return self.apply_overrides(cached)

        # Busca da API em background
        try:
            fresh_pricing = await self.api_client.fetch(model_id, region)
            await self.cache.set(model_id, region, fresh_pricing)
            return self.apply_overrides(fresh_pricing)
        except APIError:
            # Fallback: usa cache mesmo se stale + predição
            if cached:
                predicted = self.predictor.adjust_for_time(cached)
                return self.apply_overrides(predicted)
            raise PricingUnavailable()

    def apply_overrides(self, pricing: Pricing) -> Pricing:
        """Aplica overrides locais configurados pelo usuário"""
        override = self.local_overrides.get(pricing.model_id)
        if override:
            pricing.multiplier = override.multiplier
            pricing.min_cost = override.min_cost
        return pricing

class CostPredictor:
    """Prediz custos baseado em padrões de uso"""

    def forecast_project_cost(
        self,
        project_id: str,
        days_ahead: int = 30
    ) -> CostForecast:
        """
        Usa ML simples ou heurísticas para prever custos futuros
        considerando:
        - Histórico de uso
        - Padrões sazonais
        - Tendências de crescimento
        - Preços dinâmicos esperados
        """
        pass

    def suggest_budget_adjustment(
        self,
        current_budget: Decimal,
        forecast: CostForecast,
        risk_tolerance: float
    ) -> BudgetRecommendation:
        """Sugere ajustes de budget baseado em previsões"""
        pass

class FallbackStrategy:
    """Gerencia fallback inteligente entre modelos"""

    def __init__(self):
        self.health_checker = ModelHealthChecker()
        self.cost_optimizer = CostOptimizer()

    async def select_fallback(
        self,
        original_model: str,
        error: Exception,
        task_requirements: TaskRequirements,
        budget_remaining: Decimal
    ) -> Optional[str]:
        """
        Seleciona o melhor modelo de fallback considerando:
        1. Modelos saudáveis disponíveis
        2. Capacidades necessárias para a tarefa
        3. Custo em relação ao budget restante
        4. Latência aceitável
        """
        candidates = await self.health_checker.get_healthy_models(
            capabilities=task_requirements.capabilities
        )

        # Filtra por budget
        affordable = [
            m for m in candidates
            if await self.cost_optimizer.estimate_cost(m, task_requirements) <= budget_remaining
        ]

        # Score por custo-benefício
        scored = [
            (m, self.score_model(m, task_requirements))
            for m in affordable
        ]

        return max(scored, key=lambda x: x[1])[0] if scored else None
```

### 4.3 Cache Inteligente de Preços

```python
class PricingCache:
    """Cache com estratégia de atualização inteligente"""

    def __init__(self):
        self.redis = Redis()
        self.local_cache = {}
        self.update_queue = asyncio.Queue()

    async def get(self, model_id: str, region: str) -> Optional[Pricing]:
        key = f"pricing:{model_id}:{region}"

        # Tenta cache local primeiro (mais rápido)
        if key in self.local_cache:
            entry = self.local_cache[key]
            if not self.is_stale(entry):
                return entry.pricing

        # Tenta Redis (shared entre instâncias)
        cached = await self.redis.get(key)
        if cached:
            pricing = Pricing.from_json(cached)
            self.local_cache[key] = CacheEntry(pricing)
            return pricing

        return None

    def is_stale(self, entry: CacheEntry) -> bool:
        """Determina se entrada está obsoleta baseado em volatilidade"""
        age = datetime.now() - entry.timestamp

        # Modelos voláteis: TTL mais curto
        if entry.pricing.volatility_score > 0.7:
            return age > timedelta(minutes=5)

        # Modelos estáveis: TTL mais longo
        return age > timedelta(minutes=30)
```

---

## 5. Sistema de Plugins

### 5.1 Arquitetura de Plugins

```
┌─────────────────────────────────────────────────────────────────┐
│                     PLUGIN SYSTEM                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Plugin Loader                         │  │
│  │  - Discovery (dirs, pypi, git)                          │  │
│  │  - Validation (schema, security)                        │  │
│  │  - Dependency resolution                                 │  │
│  │  - Hot-reload support                                    │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│         ┌─────────────┼─────────────┐                          │
│         ▼             ▼             ▼                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
│  │ Official │  │ Community│  │ Local    │                     │
│  │ Registry │  │ Registry │  │ Plugins  │                     │
│  │ (Signed) │  │ (Sandbox)│  │ (Dev)    │                     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                     │
│       │             │             │                            │
│       └─────────────┴─────────────┘                            │
│                     │                                          │
│                     ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Plugin Sandbox                         │  │
│  │                                                          │  │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│  │   │ Agent    │  │ Tool     │  │ Workflow │              │  │
│  │   │ Hooks    │  │ Provider │  │ Step     │              │  │
│  │   └──────────┘  └──────────┘  └──────────┘              │  │
│  │                                                          │  │
│  │   Resource Limits:                                       │  │
│  │   - Memory: 512MB                                        │  │
│  │   - CPU: 1 core                                          │  │
│  │   - Network: Restricted                                  │  │
│  │   - Filesystem: Isolated                                 │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Implementação do Plugin System

```python
# Interface base para plugins
class Plugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @abstractmethod
    def initialize(self, context: PluginContext) -> None:
        """Chamado quando plugin é carregado"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Chamado quando plugin é descarregado"""
        pass

    def get_hooks(self) -> Dict[str, Callable]:
        """Retorna hooks implementados pelo plugin"""
        return {}

# Exemplo de plugin de agente
class SecurityScannerPlugin(Plugin):
    name = "security-scanner"
    version = "1.0.0"

    def initialize(self, context: PluginContext):
        self.config = context.config
        self.logger = context.logger

    def get_hooks(self):
        return {
            "pre_file_write": self.scan_for_secrets,
            "post_agent_execute": self.scan_generated_code,
            "on_workflow_complete": self.generate_security_report
        }

    async def scan_for_secrets(
        self,
        context: HookContext
    ) -> HookResult:
        """Scans code for secrets before writing to disk"""
        file_content = context.data["content"]

        findings = await self.scanner.scan(file_content)

        if findings.critical:
            return HookResult(
                action=HookAction.BLOCK,
                reason=f"Secrets detected: {findings.critical}"
            )

        return HookResult(action=HookAction.CONTINUE)

# Sistema de hooks
class HookManager:
    def __init__(self):
        self.hooks: Dict[str, List[HookRegistration]] = defaultdict(list)
        self.execution_order = HookExecutionOrder()

    def register_hook(
        self,
        hook_name: str,
        handler: Callable,
        plugin: Plugin,
        priority: int = 100
    ):
        """Registra um handler para um hook"""
        registration = HookRegistration(
            handler=handler,
            plugin=plugin,
            priority=priority
        )
        self.hooks[hook_name].append(registration)
        self.hooks[hook_name].sort(key=lambda x: x.priority)

    async def execute_hook(
        self,
        hook_name: str,
        context: HookContext
    ) -> HookResult:
        """Executa todos os handlers registrados para um hook"""

        for registration in self.hooks[hook_name]:
            try:
                result = await registration.handler(context)

                if result.action == HookAction.BLOCK:
                    return result
                elif result.action == HookAction.MODIFY:
                    context = result.new_context

            except Exception as e:
                logger.error(f"Hook error in {registration.plugin.name}: {e}")
                if not registration.plugin.config.get("fail_silent", False):
                    raise

        return HookResult(action=HookAction.CONTINUE)

# Sandbox para execução segura
class PluginSandbox:
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.process_pool = ProcessPoolExecutor()

    async def execute_plugin_code(
        self,
        plugin: Plugin,
        code: str,
        context: ExecutionContext
    ) -> SandboxResult:
        """Executa código de plugin em ambiente isolado"""

        # Cria ambiente restrito
        restricted_globals = {
            "__builtins__": self.get_restricted_builtins(),
            "context": context,
            "PluginAPI": PluginAPI
        }

        # Executa com timeout e limites de recurso
        loop = asyncio.get_event_loop()

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self.process_pool,
                    self._run_in_subprocess,
                    code,
                    restricted_globals
                ),
                timeout=self.config.timeout
            )
            return SandboxResult(success=True, data=result)

        except asyncio.TimeoutError:
            return SandboxResult(
                success=False,
                error="Plugin execution timeout"
            )
        except Exception as e:
            return SandboxResult(success=False, error=str(e))

    def get_restricted_builtins(self):
        """Retorna builtins permitidos para plugins"""
        allowed = {
            "len", "str", "int", "float", "bool",
            "list", "dict", "set", "tuple",
            "print", "range", "enumerate", "zip",
            "map", "filter", "sorted", "sum",
            "min", "max", "abs", "round",
            "isinstance", "hasattr", "getattr"
        }

        return {
            name: __builtins__[name]
            for name in allowed
            if name in __builtins__
        }

# Loader com hot-reload
class PluginLoader:
    def __init__(self):
        self.loaded_plugins: Dict[str, Plugin] = {}
        self.watchers: Dict[str, FileWatcher] = {}
        self.hook_manager = HookManager()

    async def load_plugin(
        self,
        source: PluginSource,
        hot_reload: bool = False
    ) -> Plugin:
        """Carrega um plugin de várias fontes"""

        # Valida plugin
        manifest = await self.validate_plugin(source)

        # Resolve dependências
        await self.resolve_dependencies(manifest.dependencies)

        # Instancia plugin
        plugin_class = await self.load_plugin_class(source)
        plugin = plugin_class()

        # Inicializa
        plugin.initialize(PluginContext(config=manifest.config))

        # Registra hooks
        for hook_name, handler in plugin.get_hooks().items():
            self.hook_manager.register_hook(hook_name, handler, plugin)

        # Armazena
        self.loaded_plugins[manifest.id] = plugin

        # Configura hot-reload se solicitado
        if hot_reload and source.type == "local":
            self.setup_hot_reload(manifest.id, source.path)

        return plugin

    def setup_hot_reload(self, plugin_id: str, path: str):
        """Configura hot-reload para plugin local"""

        async def on_file_change(event):
            logger.info(f"Plugin {plugin_id} changed, reloading...")

            # Descarrega plugin antigo
            old_plugin = self.loaded_plugins[plugin_id]
            old_plugin.shutdown()

            # Remove hooks antigos
            self.hook_manager.unregister_plugin(plugin_id)

            # Recarrega
            await self.load_plugin(
                PluginSource(type="local", path=path),
                hot_reload=True
            )

        watcher = FileWatcher(path, on_file_change)
        self.watchers[plugin_id] = watcher
        watcher.start()
```

### 5.3 Exemplo de Plugin Completo

```python
# plugins/security-scanner/plugin.py

from devsynapse.plugins import Plugin, HookContext, HookResult, HookAction
from typing import Dict, List
import re

class SecurityScannerPlugin(Plugin):
    """
    Plugin de exemplo que escaneia código gerado por agents
    em busca de vulnerabilidades de segurança e secrets
    """

    name = "security-scanner"
    version = "2.1.0"
    author = "DevSynapse Team"

    # Padrões de secrets para detectar
    SECRET_PATTERNS = {
        "api_key": re.compile(r'[a-zA-Z0-9]{32,}'),
        "password": re.compile(r'password\s*=\s*["\'][^"\']+["\']'),
        "secret": re.compile(r'secret\s*=\s*["\'][^"\']+["\']'),
        "private_key": re.compile(r'-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----'),
        "aws_key": re.compile(r'AKIA[0-9A-Z]{16}'),
    }

    def initialize(self, context):
        self.config = context.config
        self.severity_threshold = context.config.get(
            "severity_threshold",
            "medium"
        )
        self.ignore_rules = set(context.config.get("ignore_rules", []))

    def get_hooks(self) -> Dict[str, callable]:
        return {
            "pre_file_write": self.scan_before_write,
            "post_agent_execute": self.scan_generated_code,
            "on_budget_alert": self.log_security_cost
        }

    async def scan_before_write(self, context: HookContext) -> HookResult:
        """Hook chamado antes de escrever arquivo no disco"""

        file_path = context.data.get("path", "")
        content = context.data.get("content", "")

        findings = await self.scan_content(content, file_path)

        # Filtra por severidade configurada
        critical = [f for f in findings if f.severity == "critical"]
        high = [f for f in findings if f.severity == "high"]

        if critical:
            return HookResult(
                action=HookAction.BLOCK,
                reason=f"Critical security issues found: {len(critical)}",
                metadata={"findings": critical}
            )

        if high and self.severity_threshold in ["low", "medium"]:
            return HookResult(
                action=HookAction.BLOCK,
                reason=f"High severity issues found: {len(high)}",
                metadata={"findings": high}
            )

        # Retorna findings como warning
        return HookResult(
            action=HookAction.CONTINUE,
            metadata={"security_findings": findings}
        )

    async def scan_content(
        self,
        content: str,
        file_path: str
    ) -> List[SecurityFinding]:
        """Escaneia conteúdo em busca de vulnerabilidades"""

        findings = []

        # Procura por secrets
        for secret_type, pattern in self.SECRET_PATTERNS.items():
            if secret_type in self.ignore_rules:
                continue

            for match in pattern.finditer(content):
                findings.append(SecurityFinding(
                    type="secret_exposure",
                    severity="critical",
                    message=f"Possible {secret_type} exposed",
                    line=content[:match.start()].count('\n') + 1,
                    file=file_path,
                    rule_id=f"SECRET_{secret_type.upper()}"
                ))

        # Verifica SQL injection
        sql_patterns = [
            r'execute\s*\(\s*["\'].*%s',
            r'cursor\.execute\s*\(\s*["\'].*\+',
            r'f["\']SELECT.*{.*}',
        ]

        for pattern in sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                findings.append(SecurityFinding(
                    type="sql_injection",
                    severity="high",
                    message="Possible SQL injection vulnerability",
                    line=1,  # Simplificado
                    file=file_path,
                    rule_id="SQL_INJECTION_001"
                ))

        return findings

    async def log_security_cost(self, context: HookContext) -> HookResult:
        """Log especial quando alerta de budget está relacionado a security"""

        # Verifica se há muitas interrupções por segurança
        recent_blocks = await self.get_recent_security_blocks(
            hours=24
        )

        if len(recent_blocks) > 10:
            logger.warning(
                f"High number of security blocks: {len(recent_blocks)}. "
                "Consider reviewing agent prompts or security rules."
            )

        return HookResult(action=HookAction.CONTINUE)

# plugins/security-scanner/manifest.yaml
plugin:
  id: "security-scanner"
  name: "Security Scanner"
  version: "2.1.0"
  description: "Scans code for security vulnerabilities and secrets"
  author: "DevSynapse Team"
  license: "MIT"

  entry_point: "plugin.py"

  requirements:
    - "devsynapse-plugins>=2.0.0"

  permissions:
    - "read:files"
    - "hook:pre_file_write"
    - "hook:post_agent_execute"

  hooks:
    - name: "pre_file_write"
      description: "Scan files before writing to disk"
      blocking: true
      priority: 100

    - name: "post_agent_execute"
      description: "Scan generated code"
      blocking: false
      priority: 50

  config_schema:
    type: object
    properties:
      severity_threshold:
        type: string
        enum: ["low", "medium", "high", "critical"]
        default: "medium"
      ignore_rules:
        type: array
        items:
          type: string
        default: []
      max_file_size:
        type: integer
        default: 1048576  # 1MB
```

---

## 6. Fluxos de Dados e Interações

### 6.1 Fluxo de Execução de Workflow

```
Usuário → TUI/CLI
    │
    ▼
┌─────────────────────────────────────┐
│  WorkflowEngine.load_workflow()     │
│  - Carrega configuração YAML        │
│  - Valida estrutura                 │
│  - Resolve variáveis                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Para cada step no workflow:        │
│                                     │
│  1. Check Budget                    │
│     → BudgetController.check()      │
│     → Se excedido: bloqueia/pede    │
│       aprovação                     │
│                                     │
│  2. Checkpoint?                     │
│     → Se sim: pausa, notifica UI    │
│     → Aguarda aprovação do usuário  │
│                                     │
│  3. Dispatch Agent                  │
│     → AgentDispatcher.select()      │
│     → Considera modelo, custo, carga│
│                                     │
│  4. Execute Agent                   │
│     → Carrega prompts customizados  │
│     → Injeta contexto do projeto    │
│     → Chama ModelManager            │
│                                     │
│  5. Process Result                  │
│     → Executa plugins (hooks)       │
│     → Valida resultado              │
│     → Atualiza estado               │
│                                     │
│  6. Atualiza Budget                 │
│     → Registra custo real           │
│     → Atualiza forecast             │
│     → Checa alertas                 │
│                                     │
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │  Próximo step ou     │
    │  Workflow completo   │
    └──────────────────────┘
```

### 6.2 Fluxo de Seleção de Modelo

```
Task Recebida
    │
    ▼
┌─────────────────────────────────────┐
│  ModelManager.select_model()        │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│Passo 1 │ │Passo 2 │ │Passo 3 │
│        │ │        │ │        │
│Filtrar │ │Calcular│ │Aplicar │
│por     │ │custo   │ │fallback│
│capacida│ │estimado│ │se      │
│dade    │ │        │ │necessár│
│        │ │        │ │io      │
└────┬───┘ └────┬───┘ └────┬───┘
     │          │          │
     └──────────┼──────────┘
                ▼
┌─────────────────────────────────────┐
│  Modelo Selecionado                 │
│  - ID: gpt-4o                       │
│  - Custo estimado: $0.023           │
│  - Latência estimada: 2.3s          │
└─────────────────────────────────────┘
```

---

## 7. Considerações de Implementação

### 7.1 Estrutura de Diretórios Recomendada

```
devsynapse/
├── devsynapse/                    # Código fonte principal
│   ├── __init__.py
│   ├── cli.py                     # CLI interface
│   ├── tui/                       # Terminal UI (Textual)
│   │   ├── app.py
│   │   ├── screens/
│   │   └── widgets/
│   ├── core/                      # Lógica de negócio
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # Agent Orchestrator
│   │   ├── workflow.py            # Workflow Engine
│   │   ├── agents/                # Agent implementations
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── code_generator.py
│   │   │   ├── code_reviewer.py
│   │   │   └── ...
│   │   ├── models/                # Model management
│   │   │   ├── __init__.py
│   │   │   ├── manager.py
│   │   │   ├── pricing.py
│   │   │   ├── fallback.py
│   │   │   └── registry.py
│   │   ├── budget/                # Budget control
│   │   │   ├── __init__.py
│   │   │   ├── controller.py
│   │   │   ├── forecaster.py
│   │   │   └── alerts.py
│   │   ├── plugins/               # Plugin system
│   │   │   ├── __init__.py
│   │   │   ├── manager.py
│   │   │   ├── loader.py
│   │   │   ├── sandbox.py
│   │   │   └── hooks.py
│   │   ├── approval/              # Approval system
│   │   │   ├── __init__.py
│   │   │   ├── manager.py
│   │   │   └── roles.py
│   │   ├── events/                # Event system
│   │   │   ├── __init__.py
│   │   │   ├── bus.py
│   │   │   └── store.py
│   │   └── persistence/           # Data persistence
│   │       ├── __init__.py
│   │       ├── database.py
│   │       └── migrations/
│   └── config/                    # Configurações
│       ├── __init__.py
│       ├── loader.py
│       ├── validator.py
│       └── defaults.py
├── config/                        # Configurações do usuário
│   ├── system.yaml
│   ├── providers/
│   │   ├── models.yaml
│   │   └── pricing-overrides.yaml
│   ├── agents/
│   │   ├── code-agent.yaml
│   │   └── review-agent.yaml
│   ├── workflows/
│   │   ├── feature-dev.yaml
│   │   └── bugfix.yaml
│   ├── projects/
│   │   └── myproject.yaml
│   └── plugins/
│       └── registry.yaml
├── plugins/                       # Plugins instalados
│   ├── official/
│   │   └── security-scanner/
│   └── custom/
├── prompts/                       # Templates de prompts
│   ├── code-generator/
│   │   ├── system.md
│   │   └── templates/
│   └── review-agent/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
├── scripts/
├── Makefile
├── pyproject.toml
└── README.md
```

### 7.2 Tecnologias Recomendadas

| Componente | Tecnologia | Justificativa |
|------------|-----------|---------------|
| **TUI** | Textual | Python-native, widgets ricos, assíncrono |
| **CLI** | Typer | Type hints, geração automática de help |
| **API** | FastAPI | Performance, validação automática, docs |
| **DB** | SQLite (local) / PostgreSQL (multi-tenant) | Zero-config, portátil |
| **Cache** | diskcache / Redis | TTL flexível, persistência opcional |
| **Config** | Pydantic + YAML | Validação, tipagem, hot-reload |
| **Eventos** | asyncio + SQLite | Simplicidade, audit trail embutido |
| **Plugins** | importlib + subprocess | Isolamento, segurança |
| **Sandbox** | RestrictedPython / subprocess | Execução segura de código não-confiável |

### 7.3 Roadmap Sugerido

**Fase 1 - Foundation (Semanas 1-4)**
- [ ] Core architecture e interfaces
- [ ] Config loader com hot-reload
- [ ] Model registry básico
- [ ] Agent orchestrator simples
- [ ] SQLite persistence

**Fase 2 - Intelligence (Semanas 5-8)**
- [ ] Dynamic pricing engine
- [ ] Fallback system
- [ ] Budget controller
- [ ] Cost forecasting
- [ ] Multi-tenant isolation

**Fase 3 - Collaboration (Semanas 9-12)**
- [ ] Workflow engine completo
- [ ] Approval system
- [ ] Autonomy levels
- [ ] Checkpoint system
- [ ] Event bus

**Fase 4 - Extensibility (Semanas 13-16)**
- [ ] Plugin system
- [ ] Plugin sandbox
- [ ] Hook system
- [ ] Official plugins
- [ ] Plugin marketplace

**Fase 5 - Polish (Semanas 17-20)**
- [ ] TUI completa
- [ ] API REST
- [ ] Documentation
- [ ] Testing (80%+ coverage)
- [ ] Performance optimization

---

## 8. Métricas e Observabilidade

### 8.1 Métricas Principais

```python
# Métricas de sistema
SYSTEM_METRICS = {
    # Performance
    "request_latency_ms": Histogram,
    "tokens_per_second": Gauge,
    "queue_depth": Gauge,

    # Financeiro
    "cost_per_request": Histogram,
    "daily_cost": Counter,
    "budget_utilization": Gauge,
    "cost_forecast_accuracy": Gauge,

    # Qualidade
    "fallback_rate": Gauge,
    "approval_rate": Gauge,
    "workflow_success_rate": Gauge,
    "agent_error_rate": Gauge,

    # Utilização
    "active_workflows": Gauge,
    "active_agents": Gauge,
    "plugin_execution_time": Histogram,
}
```

### 8.2 Audit Trail

```python
@dataclass
class AuditEvent:
    event_id: str
    timestamp: datetime
    tenant_id: str
    project_id: str
    user_id: str
    event_type: str
    resource_type: str
    resource_id: str
    action: str
    before_state: Optional[Dict]
    after_state: Optional[Dict]
    metadata: Dict
    ip_address: str
    session_id: str
```

---

## Resumo

Esta arquitetura fornece:

1. **✅ Modelos Voláteis**: Registry dinâmico, pricing calculator em tempo real, fallback automático, budget controls
2. **✅ Configurabilidade Total**: Agents, workflows, prompts e regras de aprovação 100% configuráveis via YAML
3. **✅ Sistema Colaborativo**: Níveis de autonomia, checkpoints, feedback loop
4. **✅ Arquitetura Extensível**: Plugin system, hot-reload, multi-tenant, audit trail
5. **✅ Controle Financeiro**: Budget por projeto, alertas, rate limiting, cost attribution

A arquitetura é modular, escalável e pronta para evoluir conforme novas necessidades surgirem.
