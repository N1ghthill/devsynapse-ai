"""Tests for core/project_resolver.py."""

from pathlib import Path
from unittest.mock import Mock

from core.project_resolver import ProjectResolver

PROJECT_NAME = "devsynapse-ai"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _mock_settings(tmp_path=None):
    repos_root = tmp_path or PROJECT_ROOT
    settings = Mock()
    settings.dev_repos_root = repos_root
    settings.default_execution_cwd = tmp_path or PROJECT_ROOT
    return settings


def _resolver(known_projects=None, tmp_path=None):
    if known_projects is None:
        known_projects = {
            PROJECT_NAME: {"path": str(PROJECT_ROOT), "type": "project", "priority": "medium"},
        }
    return ProjectResolver(
        known_projects=known_projects,
        get_settings=lambda: _mock_settings(tmp_path),
    )


class TestResolveFromReposPath:
    def test_valid_repos_path(self, tmp_path):
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        r = _resolver(tmp_path=repos_root)
        result = r.resolve_from_repos_path(str(repos_root / "myapp" / "src" / "main.rs"))
        assert result == "myapp"

    def test_outside_repos(self, tmp_path):
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        r = _resolver(tmp_path=repos_root)
        result = r.resolve_from_repos_path("/other/file.txt")
        assert result is None

    def test_non_path_text(self, tmp_path):
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        r = _resolver(tmp_path=repos_root)
        result = r.resolve_from_repos_path("python")
        assert result is None


class TestExtractPathReferences:
    def test_extract_absolute_path_from_sentence(self):
        result = ProjectResolver.extract_path_references(
            "Use o diretório /home/irving/ruas/repositorios/calc_py/ agora"
        )
        assert result == ["/home/irving/ruas/repositorios/calc_py/"]


class TestLooksLikePathReference:
    def test_absolute_path(self):
        assert ProjectResolver._looks_like_path_reference("/foo/bar") is True

    def test_relative_dir(self):
        assert ProjectResolver._looks_like_path_reference("./src") is True

    def test_home_path(self):
        assert ProjectResolver._looks_like_path_reference("~/projects") is True

    def test_plain_text(self):
        assert ProjectResolver._looks_like_path_reference("python") is False

    def test_empty(self):
        assert ProjectResolver._looks_like_path_reference("") is False


class TestResolveFromText:
    def test_project_name_in_path(self):
        r = _resolver()
        result = r.resolve_from_text(f"{PROJECT_ROOT}/src/main.py")
        assert result == PROJECT_NAME

    def test_project_name_in_text(self):
        r = _resolver()
        result = r.resolve_from_text(f"work on {PROJECT_NAME} project")
        assert result == PROJECT_NAME

    def test_no_match(self):
        r = _resolver()
        result = r.resolve_from_text("something completely unrelated")
        assert result is None

    def test_repos_path_in_free_form_text(self, tmp_path):
        repos_root = tmp_path / "repos"
        project_root = repos_root / "calc_py"
        project_root.mkdir(parents=True)
        r = _resolver(known_projects={}, tmp_path=repos_root)

        result = r.resolve_from_text(f"Trabalhe em {project_root}/ e crie uma calculadora")

        assert result == "calc_py"

    def test_git_path_outside_repos_in_free_form_text(self, tmp_path):
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        external_repo = tmp_path / "external" / "client-app"
        (external_repo / ".git").mkdir(parents=True)
        (external_repo / "src").mkdir()
        r = _resolver(known_projects={}, tmp_path=repos_root)

        result = r.resolve_from_text(f"Trabalhe em {external_repo}/src agora")

        assert result == "client-app"

    def test_empty_text(self):
        r = _resolver()
        result = r.resolve_from_text("")
        assert result is None


class TestResolveCwd:
    def test_registered_project(self):
        r = _resolver()
        result = r.resolve_cwd(PROJECT_NAME)
        assert result == str(PROJECT_ROOT)

    def test_unknown_project(self, tmp_path):
        settings = _mock_settings(tmp_path=tmp_path)
        r = ProjectResolver(known_projects={}, get_settings=lambda: settings)
        result = r.resolve_cwd("unknown")
        assert result == str(tmp_path)

    def test_none_project(self, tmp_path):
        settings = _mock_settings(tmp_path=tmp_path)
        r = ProjectResolver(known_projects={}, get_settings=lambda: settings)
        result = r.resolve_cwd(None)
        assert result == str(tmp_path)


class TestInferProjectName:
    def test_from_file_path_arg(self):
        r = _resolver()
        result = r.infer_project_name("read", [f"{PROJECT_ROOT}/src/main.py"], None)
        assert result == PROJECT_NAME

    def test_explicit_project_wins(self):
        r = _resolver()
        result = r.infer_project_name("read", ["/some/unknown/path"], PROJECT_NAME)
        assert result == PROJECT_NAME

    def test_no_args_returns_explicit(self):
        r = _resolver()
        result = r.infer_project_name("bash", [], PROJECT_NAME)
        assert result == PROJECT_NAME

    def test_no_args_no_explicit_returns_none(self):
        r = _resolver()
        result = r.infer_project_name("bash", [], None)
        assert result is None

    def test_infers_git_project_outside_repos(self, tmp_path):
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        external_repo = tmp_path / "external" / "client-app"
        (external_repo / ".git").mkdir(parents=True)
        r = _resolver(known_projects={}, tmp_path=repos_root)

        result = r.infer_project_name("bash", [f"git -C {external_repo} status"], None)

        assert result == "client-app"
