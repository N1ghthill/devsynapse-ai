"""Tests for core.prompts module."""

from core.prompts import build_system_prompt


class TestBuildSystemPrompt:
    def test_basic_prompt_structure(self):
        result = build_system_prompt(
            assistant_user_name="developer",
            user_prefs="test prefs",
            projects_info="test projects",
            agent_learning="test learning",
            procedural_memory="test memory",
            skills_context="test skills",
            agent_run_context="test agent run",
            stuck_context="",
            active_project_name=None,
            active_project_path=None,
            workspace_root="/workspace",
            repos_root="/repos",
            default_cwd="/workspace",
        )

        assert "DevSynapse" in result
        assert "developer" in result
        assert "test prefs" in result
        assert "test projects" in result
        assert "test learning" in result
        assert "test memory" in result
        assert "test skills" in result
        assert "test agent run" in result
        assert "YOUR ROLE" in result
        assert "CAPABILITIES" in result
        assert "RESPONSE FORMAT" in result

    def test_active_project_section_included(self):
        result = build_system_prompt(
            assistant_user_name="dev",
            user_prefs="",
            projects_info="",
            agent_learning="",
            procedural_memory="",
            skills_context="",
            agent_run_context="",
            stuck_context="",
            active_project_name="my-project",
            active_project_path="/repos/my-project",
            workspace_root="/workspace",
            repos_root="/repos",
            default_cwd="/workspace",
        )

        assert "CURRENT WORKSPACE" in result
        assert "my-project" in result
        assert "/repos/my-project" in result
        assert "default working boundary" in result

    def test_active_project_section_missing_when_no_project(self):
        result = build_system_prompt(
            assistant_user_name="dev",
            user_prefs="",
            projects_info="",
            agent_learning="",
            procedural_memory="",
            skills_context="",
            agent_run_context="",
            stuck_context="",
            active_project_name=None,
            active_project_path=None,
            workspace_root="/workspace",
            repos_root="/repos",
            default_cwd="/workspace",
        )

        assert "CURRENT WORKSPACE" not in result

    def test_plan_mode_is_read_only(self):
        result = build_system_prompt(
            assistant_user_name="dev",
            user_prefs="",
            projects_info="",
            agent_learning="",
            procedural_memory="",
            skills_context="",
            agent_run_context="",
            stuck_context="",
            active_project_name=None,
            active_project_path=None,
            workspace_root="/workspace",
            repos_root="/repos",
            default_cwd="/workspace",
            agent_mode="plan",
        )

        assert "Mode: Plan" in result
        assert "Read-only analysis mode" in result
        assert "Build mode is required" in result

    def test_stuck_context_included(self):
        stuck = "\n## STUCK AWARENESS\n- As últimas 2 tentativas falharam."
        result = build_system_prompt(
            assistant_user_name="dev",
            user_prefs="",
            projects_info="",
            agent_learning="",
            procedural_memory="",
            skills_context="",
            agent_run_context="",
            stuck_context=stuck,
            active_project_name=None,
            active_project_path=None,
            workspace_root="/workspace",
            repos_root="/repos",
            default_cwd="/workspace",
        )

        assert stuck in result

    def test_default_user_name_when_empty(self):
        result = build_system_prompt(
            assistant_user_name="",
            user_prefs="",
            projects_info="",
            agent_learning="",
            procedural_memory="",
            skills_context="",
            agent_run_context="",
            stuck_context="",
            active_project_name=None,
            active_project_path=None,
            workspace_root="/workspace",
            repos_root="/repos",
            default_cwd="/workspace",
        )

        assert "the user" in result

    def test_workspace_paths_included(self):
        result = build_system_prompt(
            assistant_user_name="dev",
            user_prefs="",
            projects_info="",
            agent_learning="",
            procedural_memory="",
            skills_context="",
            agent_run_context="",
            stuck_context="",
            active_project_name=None,
            active_project_path=None,
            workspace_root="/custom/workspace",
            repos_root="/custom/repos",
            default_cwd="/custom/cwd",
        )

        assert "/custom/workspace" in result
        assert "/custom/repos" in result
        assert "/custom/cwd" in result
        assert "repositories root is only the default location" in result
        assert "Do not assume the repositories root contains all user projects" in result

    def test_current_git_project_context_included_without_target_path(self):
        result = build_system_prompt(
            assistant_user_name="dev",
            user_prefs="",
            projects_info="",
            agent_learning="",
            procedural_memory="",
            skills_context="",
            agent_run_context="",
            stuck_context="",
            active_project_name=None,
            active_project_path=None,
            workspace_root="/workspace",
            repos_root="/repos",
            default_cwd="/elsewhere/client-app",
            current_git_project={
                "display_path": "/elsewhere/client-app",
                "path": "/elsewhere/client-app",
                "project_name": "client-app",
            },
        )

        assert "DISCOVERED CURRENT GIT PROJECT" in result
        assert "/elsewhere/client-app" in result
        assert "Do not force new unrelated projects into this Git repository" in result
