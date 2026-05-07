"""Tests for skill templates."""
from __future__ import annotations

from core.skill_templates import SKILL_TEMPLATES


class TestSkillTemplates:
    def test_has_templates(self):
        assert len(SKILL_TEMPLATES) > 0

    def test_python_dev_template(self):
        template = SKILL_TEMPLATES.get("python-dev")
        assert template is not None
        assert template["name"] == "Python Development"
        assert "python" in template["tags"]

    def test_rust_dev_template(self):
        template = SKILL_TEMPLATES.get("rust-dev")
        assert template is not None
        assert template["name"] == "Rust Development"
        assert "rust" in template["tags"]

    def test_web_frontend_template(self):
        template = SKILL_TEMPLATES.get("web-frontend")
        assert template is not None
        assert template["name"] == "Web Frontend Development"

    def test_api_design_template(self):
        template = SKILL_TEMPLATES.get("api-design")
        assert template is not None
        assert template["name"] == "API Design"

    def test_git_workflow_template(self):
        template = SKILL_TEMPLATES.get("git-workflow")
        assert template is not None
        assert template["name"] == "Git Workflow"

    def test_all_templates_have_required_fields(self):
        for slug, template in SKILL_TEMPLATES.items():
            assert "name" in template
            assert "description" in template
            assert "category" in template
            assert "tags" in template
            assert "body" in template
            assert len(template["name"]) > 0
            assert len(template["description"]) > 0
            assert len(template["body"]) > 0

    def test_all_templates_have_unique_slugs(self):
        slugs = list(SKILL_TEMPLATES.keys())
        assert len(slugs) == len(set(slugs))
