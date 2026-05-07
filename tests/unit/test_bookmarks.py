"""Tests for bookmarks."""
from __future__ import annotations

import pytest

from core.bookmarks import BookmarkStore


@pytest.fixture
def bookmark_store(tmp_path):
    db_path = tmp_path / "bookmarks.db"
    return BookmarkStore(str(db_path))


class TestBookmarkStore:
    def test_add_bookmark(self, bookmark_store):
        bookmark = bookmark_store.add_bookmark(
            "git status",
            "git status",
            "Check git status",
        )
        assert bookmark["name"] == "git status"
        assert bookmark["command"] == "git status"
        assert bookmark["description"] == "Check git status"

    def test_get_bookmark(self, bookmark_store):
        bookmark_store.add_bookmark("git status", "git status")
        bookmark = bookmark_store.get_bookmark("git status")
        assert bookmark is not None
        assert bookmark["name"] == "git status"

    def test_get_nonexistent_bookmark(self, bookmark_store):
        bookmark = bookmark_store.get_bookmark("nonexistent")
        assert bookmark is None

    def test_list_bookmarks(self, bookmark_store):
        bookmark_store.add_bookmark("cmd1", "command 1")
        bookmark_store.add_bookmark("cmd2", "command 2")
        bookmarks = bookmark_store.list_bookmarks()
        assert len(bookmarks) == 2

    def test_delete_bookmark(self, bookmark_store):
        bookmark_store.add_bookmark("to-delete", "command")
        result = bookmark_store.delete_bookmark("to-delete")
        assert result is True
        bookmark = bookmark_store.get_bookmark("to-delete")
        assert bookmark is None

    def test_delete_nonexistent_bookmark(self, bookmark_store):
        result = bookmark_store.delete_bookmark("nonexistent")
        assert result is False

    def test_increment_use_count(self, bookmark_store):
        bookmark_store.add_bookmark("frequent", "command")
        bookmark_store.increment_use_count("frequent")
        bookmark_store.increment_use_count("frequent")
        bookmark = bookmark_store.get_bookmark("frequent")
        assert bookmark["use_count"] == 2
        assert bookmark["last_used_at"] is not None

    def test_duplicate_bookmark_raises(self, bookmark_store):
        bookmark_store.add_bookmark("unique", "command")
        with pytest.raises(Exception):
            bookmark_store.add_bookmark("unique", "command 2")
