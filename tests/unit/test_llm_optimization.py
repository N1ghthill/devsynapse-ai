from core.llm_optimization import (
    ModelRouter,
    build_task_profile,
    cache_hit_rate_pct,
    classify_task_complexity,
)


def test_classify_simple_conceptual_question():
    complexity, reason = classify_task_complexity("O que é dependency injection?")

    assert complexity == "simple"
    assert reason == "simple_keyword"


def test_classify_complex_architecture_request():
    complexity, reason = classify_task_complexity(
        "Preciso de uma arquitetura com cache, auth e migração de schema"
    )

    assert complexity == "complex"
    assert reason == "complex_keyword"


def test_router_uses_flash_for_simple_and_pro_for_complex():
    router = ModelRouter(
        flash_model="deepseek-v4-flash",
        pro_model="deepseek-v4-pro",
        default_model="deepseek-v4-pro",
    )

    simple_route = router.select_model("Explique async/await")
    complex_route = router.select_model("Debug complexo com race condition async")

    assert simple_route.model == "deepseek-v4-flash"
    assert simple_route.fallback_model == "deepseek-v4-pro"
    assert complex_route.model == "deepseek-v4-pro"
    assert complex_route.fallback_model is None


def test_router_forces_flash_during_critical_budget():
    router = ModelRouter(
        flash_model="deepseek-v4-flash",
        pro_model="deepseek-v4-pro",
        default_model="deepseek-v4-pro",
    )

    route = router.select_model(
        "Desenhe uma arquitetura multi-arquivo",
        budget_status={"overall_status": "critical"},
    )

    assert route.model == "deepseek-v4-flash"
    assert route.budget_mode == "economy"
    assert route.fallback_model is None


def test_router_uses_confident_learned_preference():
    router = ModelRouter(
        flash_model="deepseek-v4-flash",
        pro_model="deepseek-v4-pro",
        default_model="deepseek-v4-pro",
    )

    route = router.select_model(
        "Explique esse erro simples",
        learned_policy={
            "preferred_model": "deepseek-v4-pro",
            "confidence": 0.8,
            "learned_reason": "feedback_negative",
        },
    )

    assert route.model == "deepseek-v4-pro"
    assert route.learned_preference == "deepseek-v4-pro"
    assert route.reason == "learned_preference:feedback_negative"


def test_task_profile_has_stable_semantic_signature():
    first = build_task_profile("Erro no arquivo /tmp/app123.py linha 42")
    second = build_task_profile("Erro no arquivo /home/dev/app999.py linha 99")

    assert first.task_type == "debug"
    assert first.signature == second.signature


def test_cache_hit_rate_pct():
    assert cache_hit_rate_pct({
        "prompt_cache_hit_tokens": 70,
        "prompt_cache_miss_tokens": 30,
    }) == 70.0
    assert cache_hit_rate_pct({}) == 0.0
