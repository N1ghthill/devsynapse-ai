"""Tests for core/intent_detector.py."""

from core.intent_detector import IntentDetector, IntentMode


class TestIntentDetector:
    def setup_method(self):
        self.detector = IntentDetector()

    def test_detect_question_as_chat(self):
        result = self.detector.detect("O que é JWT?")
        assert result.mode == IntentMode.CHAT
        assert result.confidence > 0.5

    def test_detect_explanation_as_chat(self):
        result = self.detector.detect("Explique como funciona o sistema de autenticação")
        assert result.mode == IntentMode.CHAT

    def test_detect_greeting_as_chat(self):
        result = self.detector.detect("Olá, bom dia!")
        assert result.mode == IntentMode.CHAT

    def test_detect_complex_task_as_planning(self):
        result = self.detector.detect("Crie uma API REST completa com autenticação")
        assert result.mode == IntentMode.PLANNING

    def test_detect_architecture_as_planning(self):
        result = self.detector.detect("Vamos planejar a arquitetura do sistema")
        assert result.mode == IntentMode.PLANNING

    def test_detect_refactoring_as_planning(self):
        result = self.detector.detect("Preciso refatorar o módulo de pagamentos")
        assert result.mode == IntentMode.PLANNING

    def test_detect_simple_file_creation_as_build(self):
        result = self.detector.detect("Crie um arquivo main.py")
        assert result.mode == IntentMode.BUILD

    def test_detect_run_command_as_build(self):
        result = self.detector.detect("Rode os testes do projeto")
        assert result.mode == IntentMode.BUILD

    def test_detect_edit_command_as_build(self):
        result = self.detector.detect("Edite o arquivo config.py")
        assert result.mode == IntentMode.BUILD

    def test_explicit_plan_command(self):
        result = self.detector.detect("/plan Criar sistema completo")
        assert result.mode == IntentMode.PLANNING
        assert result.confidence == 0.95

    def test_explicit_build_command(self):
        result = self.detector.detect("/build Execute o plano")
        assert result.mode == IntentMode.BUILD
        assert result.confidence == 0.95

    def test_explicit_chat_command(self):
        result = self.detector.detect("/chat Vamos conversar")
        assert result.mode == IntentMode.CHAT
        assert result.confidence == 0.95

    def test_extract_path_from_message(self):
        result = self.detector.detect("Crie projeto em ~/ruas/repositorios/calc_py")
        assert result.target_path == "~/ruas/repositorios/calc_py"

    def test_extract_project_name(self):
        result = self.detector.detect("Crie o projeto minha-api")
        assert result.project_name == "minha-api"

    def test_empty_message_defaults_to_chat(self):
        result = self.detector.detect("")
        assert result.mode == IntentMode.CHAT
        assert result.confidence == 0.5

    def test_long_message_boosts_planning(self):
        long_message = "Eu preciso criar um sistema completo de e-commerce com autenticação, carrinho de compras, gateway de pagamento, gestão de estoque, relatórios e dashboard administrativo, tudo integrado com banco de dados PostgreSQL e cache Redis"
        result = self.detector.detect(long_message)
        assert result.mode == IntentMode.PLANNING

    def test_short_message_boosts_build(self):
        result = self.detector.detect("Crie main.py")
        assert result.mode == IntentMode.BUILD

    def test_reasoning_is_informative(self):
        result = self.detector.detect("O que é Python?")
        assert "chat" in result.reasoning.lower()
        assert "score" in result.reasoning.lower()
