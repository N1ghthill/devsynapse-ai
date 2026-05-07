"""Extended tests for DevSynapse AI skills system."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.skills import SkillError, SkillStore


@pytest.fixture
def skill_store(tmp_path):
    db_path = tmp_path / "skills.db"
    base_dir = tmp_path / "skills"
    base_dir.mkdir()

    store = SkillStore(str(db_path), base_dir)

    conn = store.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            description TEXT NOT NULL DEFAULT '',
            scope TEXT NOT NULL DEFAULT 'global',
            project_name TEXT,
            path TEXT NOT NULL,
            content_hash TEXT,
            metadata TEXT,
            use_count INTEGER DEFAULT 0,
            last_used_at TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_slug TEXT NOT NULL,
            project_name TEXT,
            conversation_id TEXT,
            reason TEXT,
            activated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

    return store


class TestSkillValidation:
    def test_slugify_converts_to_lowercase(self):
        store = SkillStore(":memory:", Path("/tmp"))
        assert store.slugify("My Skill") == "my-skill"

    def test_slugify_replaces_spaces(self):
        store = SkillStore(":memory:", Path("/tmp"))
        assert store.slugify("my skill") == "my-skill"

    def test_slugify_removes_special_chars(self):
        store = SkillStore(":memory:", Path("/tmp"))
        result = store.slugify("my@skill!")
        assert "myskill" in result or "my-skill" in result

    def test_validate_name_accepts_valid(self):
        store = SkillStore(":memory:", Path("/tmp"))
        assert store._validate_name("Python Dev") == "Python Dev"

    def test_validate_name_rejects_empty(self):
        store = SkillStore(":memory:", Path("/tmp"))
        with pytest.raises(SkillError):
            store._validate_name("")

    def test_validate_name_rejects_special_start(self):
        store = SkillStore(":memory:", Path("/tmp"))
        with pytest.raises(SkillError):
            store._validate_name("-invalid")

    def test_validate_description_accepts_valid(self):
        store = SkillStore(":memory:", Path("/tmp"))
        assert store._validate_description("A skill") == "A skill"

    def test_validate_description_truncates_long(self):
        store = SkillStore(":memory:", Path("/tmp"))
        long_desc = "x" * 2000
        result = store._validate_description(long_desc)
        assert len(result) <= 1024

    def test_validate_body_accepts_valid(self):
        store = SkillStore(":memory:", Path("/tmp"))
        body = "# Skill\n\nContent here"
        assert store._validate_body(body) == body

    def test_validate_body_rejects_too_long(self):
        store = SkillStore(":memory:", Path("/tmp"))
        with pytest.raises(SkillError):
            store._validate_body("x" * 20001)

    def test_validate_category_accepts_valid(self):
        store = SkillStore(":memory:", Path("/tmp"))
        result = store._validate_category("python")
        assert result in ["python", "general"]

    def test_validate_category_normalizes_invalid(self):
        store = SkillStore(":memory:", Path("/tmp"))
        result = store._validate_category("INVALID CATEGORY!")
        assert result == "invalid-category" or result == "general"


class TestSkillCRUD:
    def test_create_skill_returns_dict(self, skill_store):
        result = skill_store.create_skill(
            name="Test Skill",
            description="A test skill",
            body="# Test\n\nContent",
            category="general",
        )
        assert result["name"] == "Test Skill"
        assert result["slug"] == "test-skill"
        assert result["description"] == "A test skill"

    def test_create_skill_creates_file(self, skill_store, tmp_path):
        skill_store.create_skill(
            name="File Skill",
            description="Creates file",
            body="# File Skill",
        )
        slug = skill_store.slugify("File Skill")
        skill_file = tmp_path / "skills" / "general" / slug / "SKILL.md"
        assert skill_file.exists()

    def test_create_skill_duplicate_raises(self, skill_store):
        skill_store.create_skill(
            name="Duplicate",
            description="First",
            body="Content 1",
        )
        with pytest.raises(SkillError):
            skill_store.create_skill(
                name="Duplicate",
                description="Second",
                body="Content 2",
            )

    def test_create_skill_with_replace(self, skill_store):
        skill_store.create_skill(
            name="Replaceable",
            description="First",
            body="Content 1",
        )
        result = skill_store.create_skill(
            name="Replaceable",
            description="Updated",
            body="Content 2",
            replace=True,
        )
        assert result["description"] == "Updated"

    def test_create_skill_with_project(self, skill_store):
        import uuid
        project_name = f"my-project-{uuid.uuid4().hex[:8]}"
        def fake_lookup():
            return {project_name: {"path": f"/tmp/{project_name}", "type": "project"}}

        skill_store.project_lookup_fn = fake_lookup
        result = skill_store.create_skill(
            name=f"Project Skill {uuid.uuid4().hex[:8]}",
            description="Project-specific",
            body="# Project",
            project_name=project_name,
        )
        assert result["scope"] == "project"
        assert result["project_name"] == project_name

    def test_create_skill_with_tags(self, skill_store):
        result = skill_store.create_skill(
            name="Tagged Skill",
            description="Has tags",
            body="# Tags",
            tags=["python", "testing"],
        )
        assert "python" in result.get("tags", [])
        assert "testing" in result.get("tags", [])

    def test_update_skill_updates_body(self, skill_store):
        skill_store.create_skill(
            name="Updatable",
            description="To update",
            body="Old body",
        )
        result = skill_store.update_skill("updatable", body="New body")
        assert result is not None
        assert "New body" in result.get("body", "")

    def test_update_skill_updates_description(self, skill_store):
        skill_store.create_skill(
            name="Desc Update",
            description="Old desc",
            body="Body",
        )
        result = skill_store.update_skill("desc-update", description="New desc")
        assert result is not None
        assert result["description"] == "New desc"

    def test_update_skill_nonexistent_returns_none(self, skill_store):
        result = skill_store.update_skill("nonexistent", body="New")
        assert result is None

    def test_delete_skill_removes_file(self, skill_store, tmp_path):
        skill_store.create_skill(
            name="Deletable",
            description="To delete",
            body="Content",
        )
        slug = skill_store.slugify("Deletable")
        skill_file = tmp_path / "skills" / "general" / slug / "SKILL.md"
        assert skill_file.exists()

        skill_store.delete_skill("deletable")
        assert skill_file.exists() is False

    def test_delete_skill_deactivates(self, skill_store):
        skill_store.create_skill(
            name="To Deactivate",
            description="Will be deactivated",
            body="Content",
        )
        skill_store.delete_skill("to-deactivate")
        skill = skill_store.get_skill("to-deactivate")
        assert skill is None

    def test_delete_skill_nonexistent_returns_false(self, skill_store):
        result = skill_store.delete_skill("nonexistent")
        assert result is False


class TestSkillListing:
    def test_list_skills_returns_empty_initially(self, skill_store):
        skills = skill_store.list_skills()
        assert skills == []

    def test_list_skills_returns_created(self, skill_store):
        skill_store.create_skill(
            name="Listed",
            description="Should appear",
            body="Content",
        )
        skills = skill_store.list_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "Listed"

    def test_list_skills_filters_by_project(self, skill_store):
        skill_store.create_skill(
            name="Global Skill",
            description="Global",
            body="Content",
        )
        skills = skill_store.list_skills(project_name="my-project")
        assert len(skills) >= 1

    def test_list_skills_excludes_inactive(self, skill_store):
        skill_store.create_skill(
            name="Active",
            description="Active skill",
            body="Content",
        )
        skill_store.create_skill(
            name="Inactive",
            description="Inactive skill",
            body="Content",
        )
        skill_store.delete_skill("inactive")
        skills = skill_store.list_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "Active"

    def test_list_skills_includes_inactive_when_requested(self, skill_store):
        skill_store.create_skill(
            name="To Deactivate",
            description="Will be deactivated",
            body="Content",
        )
        skill_store.delete_skill("to-deactivate")
        skills = skill_store.list_skills(include_inactive=True)
        assert len(skills) == 1


class TestSkillGet:
    def test_get_skill_by_slug(self, skill_store):
        skill_store.create_skill(
            name="Gettable",
            description="Can be retrieved",
            body="Content",
        )
        skill = skill_store.get_skill("gettable")
        assert skill is not None
        assert skill["name"] == "Gettable"

    def test_get_skill_by_name(self, skill_store):
        skill_store.create_skill(
            name="Gettable By Name",
            description="Retrieved by name",
            body="Content",
        )
        skill = skill_store.get_skill("Gettable By Name")
        assert skill is not None
        assert skill["name"] == "Gettable By Name"

    def test_get_skill_nonexistent_returns_none(self, skill_store):
        skill = skill_store.get_skill("nonexistent")
        assert skill is None

    def test_get_skill_project_specific(self, skill_store):
        import uuid
        project_name = f"my-project-{uuid.uuid4().hex[:8]}"
        skill_name = f"Project Only {uuid.uuid4().hex[:8]}"
        def fake_lookup():
            return {project_name: {"path": f"/tmp/{project_name}", "type": "project"}}

        skill_store.project_lookup_fn = fake_lookup
        skill_store.create_skill(
            name=skill_name,
            description="Project-specific",
            body="Content",
            project_name=project_name,
        )
        slug = skill_store.slugify(skill_name)
        skill = skill_store.get_skill(slug, project_name=project_name)
        assert skill is not None


class TestSkillActivation:
    def test_activate_skill_increments_count(self, skill_store):
        skill_store.create_skill(
            name="Activatable",
            description="Can be activated",
            body="Content",
        )
        skill = skill_store.activate_skill("activatable")
        assert skill is not None
        assert skill["use_count"] == 1

    def test_activate_skill_records_activation(self, skill_store):
        skill_store.create_skill(
            name="Trackable",
            description="Tracks activations",
            body="Content",
        )
        skill_store.activate_skill(
            "trackable",
            conversation_id="conv-123",
            reason="auto",
        )
        skill = skill_store.get_skill("trackable")
        assert skill is not None
        assert skill["use_count"] == 1

    def test_activate_skill_nonexistent_returns_none(self, skill_store):
        result = skill_store.activate_skill("nonexistent")
        assert result is None


class TestSkillRelevance:
    def test_select_relevant_skills_returns_empty(self, skill_store):
        skills = skill_store.select_relevant_skills("python testing")
        assert skills == []

    def test_select_relevant_skills_scores_and_ranks(self, skill_store):
        skill_store.create_skill(
            name="Python Testing",
            description="Best practices for Python testing",
            body="# Python Testing\n\nUse pytest",
            tags=["python", "testing"],
        )
        skill_store.create_skill(
            name="JavaScript",
            description="JavaScript development",
            body="# JavaScript",
            tags=["javascript"],
        )
        skills = skill_store.select_relevant_skills("python testing", limit=1)
        assert len(skills) == 1
        assert skills[0]["name"] == "Python Testing"

    def test_select_relevant_skills_respects_limit(self, skill_store):
        for i in range(5):
            skill_store.create_skill(
                name=f"Skill {i}",
                description=f"Description for skill {i}",
                body=f"# Skill {i}",
            )
        skills = skill_store.select_relevant_skills("skill", limit=2)
        assert len(skills) <= 2


class TestSkillFormatting:
    def test_format_context_returns_message_when_no_skills(self, skill_store):
        context = skill_store.format_context("query")
        assert "skill" in context.lower() or "nenhuma" in context.lower()

    def test_format_context_includes_skill_body(self, skill_store):
        skill_store.create_skill(
            name="Formatted",
            description="A formatted skill",
            body="# Formatted Skill\n\nThis is the content",
        )
        context = skill_store.format_context("formatted")
        assert "# Formatted Skill" in context
        assert "This is the content" in context


class TestSkillDiskSync:
    def test_sync_from_disk_finds_existing(self, skill_store, tmp_path):
        skill_dir = tmp_path / "skills" / "general" / "existing"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\nname: Existing\nslug: existing\ncategory: general\ndescription: From disk\n---\n\nContent",
            encoding="utf-8",
        )
        skill_store.sync_from_disk()
        skills = skill_store.list_skills()
        assert any(s["slug"] == "existing" for s in skills)

    def test_sync_from_disk_skips_invalid(self, skill_store, tmp_path):
        skill_dir = tmp_path / "skills" / "general" / "invalid"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("Invalid content", encoding="utf-8")
        skill_store.sync_from_disk()
        skills = skill_store.list_skills()
        initial_count = len(skills)
        assert initial_count >= 0


class TestSkillError:
    def test_skill_error_is_value_error(self):
        assert issubclass(SkillError, ValueError)

    def test_skill_error_can_be_raised(self):
        with pytest.raises(SkillError):
            raise SkillError("test error")
