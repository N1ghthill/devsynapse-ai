"""Tests for core/project_path_resolver.py."""


from core.project_path_resolver import ProjectPathResolver


class TestPathResolution:
    """Test path resolution with allowed directories."""

    def test_resolve_path_in_repos_root(self, tmp_path):
        """Path within repos_root should be valid."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path(str(repos_root / "my-project"))
        assert result.is_valid is True
        assert result.project_name == "my-project"

    def test_resolve_path_in_workspace_root(self, tmp_path):
        """Path within workspace_root should be valid."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path(str(workspace_root / "my-app"))
        assert result.is_valid is True
        assert result.project_name == "my-app"

    def test_resolve_path_outside_allowed_dirs(self, tmp_path):
        """Path outside allowed directories should be invalid."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        other_dir = tmp_path / "other"
        other_dir.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path(str(other_dir / "some-project"))
        assert result.is_valid is False
        assert "fora dos diretórios permitidos" in result.error_message
        assert result.project_name == "some-project"

    def test_relative_dot_path_uses_configured_default_cwd(self, tmp_path):
        """Dot-relative paths should resolve from default_cwd."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        default_cwd = workspace_root / "current"
        default_cwd.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
            default_cwd=default_cwd,
        )

        result = resolver.resolve_path("./my-project")

        assert result.is_valid is True
        assert result.absolute_path == (default_cwd / "my-project").resolve()
        assert result.project_name == "my-project"

    def test_existing_git_repo_outside_allowed_dirs_is_valid(self, tmp_path):
        """Explicit Git repos should be valid even outside preferred roots."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        external_repo = tmp_path / "external" / "client-app"
        (external_repo / ".git").mkdir(parents=True)
        (external_repo / "src").mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path(str(external_repo / "src"))

        assert result.is_valid is True
        assert result.absolute_path == external_repo.resolve()
        assert result.project_name == "client-app"
        assert result.source == "git_discovery"

    def test_resolve_path_in_etc_blocked(self, tmp_path):
        """System directories should be blocked."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path("/etc/my-project")
        assert result.is_valid is False

    def test_resolve_path_in_usr_blocked(self, tmp_path):
        """System directories should be blocked."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path("/usr/local/my-project")
        assert result.is_valid is False

    def test_resolve_relative_path_to_repos(self, tmp_path):
        """Relative path should resolve to repos_root."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        # Relative path without ./ or ../ should resolve to repos_root
        result = resolver.resolve_path("my-project")
        assert result.is_valid is True
        assert result.project_name == "my-project"

    def test_empty_path(self, tmp_path):
        """Empty path should be invalid."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path("")
        assert result.is_valid is False

    def test_whitespace_path(self, tmp_path):
        """Whitespace-only path should be invalid."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path("   ")
        assert result.is_valid is False


class TestPathExtraction:
    """Test path extraction from user messages."""

    def test_extract_path_with_em(self, tmp_path):
        """Extract path from 'em ~/path'."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        # Test with a path that will be in allowed directory
        result = resolver.resolve_from_message(f"Crie um projeto em {repos_root}/myapp")
        assert result.is_valid is True
        assert result.project_name == "myapp"

    def test_extract_path_with_para(self, tmp_path):
        """Extract path from 'para ~/path'."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_from_message(f"Crie para {repos_root}/backend")
        assert result.is_valid is True

    def test_extract_path_with_at(self, tmp_path):
        """Extract path from 'at ~/path'."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_from_message(f"Create project at {repos_root}/frontend")
        assert result.is_valid is True

    def test_extract_path_with_in(self, tmp_path):
        """Extract path from 'in ~/path'."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_from_message(f"Build app in {repos_root}/myapp")
        assert result.is_valid is True

    def test_no_path_in_message(self, tmp_path):
        """Message without path should return invalid."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_from_message("Crie uma calculadora")
        assert result.is_valid is False

    def test_current_git_project_is_discovered_without_forcing_message_resolution(self, tmp_path):
        """Current cwd Git context is available without hijacking pathless requests."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        current_repo = tmp_path / "elsewhere" / "active-repo"
        (current_repo / ".git").mkdir(parents=True)

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
            default_cwd=current_repo,
        )

        assert resolver.resolve_from_message("Crie uma calculadora").is_valid is False
        current = resolver.resolve_current_git_project()
        assert current.is_valid is True
        assert current.absolute_path == current_repo.resolve()
        assert current.source == "current_git"

    def test_extract_project_name_only(self, tmp_path):
        """Extract project name when no path specified."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_from_message("Crie o projeto myapp")
        # Should resolve to repos_root/myapp
        assert result.project_name == "myapp"


class TestSecurity:
    """Test security-related path resolution."""

    def test_symlink_escape_blocked(self, tmp_path):
        """Symlinks pointing outside allowed dirs should be blocked."""
        # Create a symlink inside repos that points to /etc
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        evil_link = allowed_dir / "evil"
        evil_link.symlink_to("/etc")

        resolver = ProjectPathResolver(
            repos_root=allowed_dir,
            workspace_root=tmp_path / "other",
            allowed_directories=[allowed_dir],
        )

        # The resolved path should be /etc, which is outside allowed_dir
        result = resolver.resolve_path(str(evil_link))
        # After resolution, the path is /etc which is not under allowed_dir
        assert result.is_valid is False

    def test_parent_traversal_blocked(self, tmp_path):
        """Path traversal with ../ should be blocked if it escapes allowed dirs."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        # Try to escape with ../
        result = resolver.resolve_path(str(repos_root / "../../etc/passwd"))
        # After resolution, this should be /etc/passwd which is not allowed
        assert result.is_valid is False

    def test_custom_allowed_directory(self, tmp_path):
        """Custom allowed directory should work."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()

        resolver = ProjectPathResolver(
            repos_root=tmp_path / "repos",
            workspace_root=tmp_path / "workspace",
            allowed_directories=[custom_dir],
        )

        result = resolver.resolve_path(str(custom_dir / "my-project"))
        assert result.is_valid is True

    def test_path_outside_custom_allowed(self, tmp_path):
        """Path outside custom allowed directory should be blocked."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        other_dir = tmp_path / "other"
        other_dir.mkdir()

        resolver = ProjectPathResolver(
            repos_root=tmp_path / "repos",
            workspace_root=tmp_path / "workspace",
            allowed_directories=[custom_dir],
        )

        result = resolver.resolve_path(str(other_dir / "my-project"))
        assert result.is_valid is False


class TestProjectNameExtraction:
    """Test project name extraction from paths."""

    def test_extract_name_from_simple_path(self, tmp_path):
        """Extract last directory name."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        result = resolver.resolve_path(str(repos_root / "my-project"))
        assert result.project_name == "my-project"

    def test_extract_name_from_nested_path(self, tmp_path):
        """Extract last directory name from nested path."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        nested = repos_root / "group" / "subgroup" / "my-app"
        nested.mkdir(parents=True)
        result = resolver.resolve_path(str(nested))
        assert result.project_name == "my-app"

    def test_extract_name_from_deep_path(self, tmp_path):
        """Extract last directory name from deep path."""
        repos_root = tmp_path / "repos"
        repos_root.mkdir()
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        resolver = ProjectPathResolver(
            repos_root=repos_root,
            workspace_root=workspace_root,
            allowed_directories=[repos_root, workspace_root],
        )

        deep = repos_root / "a" / "b" / "c" / "d" / "e" / "final-project"
        deep.mkdir(parents=True)
        result = resolver.resolve_path(str(deep))
        assert result.project_name == "final-project"
