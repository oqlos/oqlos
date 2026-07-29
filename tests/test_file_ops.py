"""Unit tests for oqlos.shared.file_ops."""

from __future__ import annotations

import pytest

from oqlos.shared.file_ops import PathEscapeError, delete_file, read_file, write_file


def test_delete_file_removes_existing_file(tmp_path):
    write_file(tmp_path, "demo.oql", "VERSION: 4\n")
    delete_file(tmp_path, "demo.oql")
    with pytest.raises(FileNotFoundError):
        read_file(tmp_path, "demo.oql")


def test_delete_file_rejects_directories(tmp_path):
    (tmp_path / "archive").mkdir()
    with pytest.raises(IsADirectoryError):
        delete_file(tmp_path, "archive")


def test_delete_file_rejects_path_escape(tmp_path):
    with pytest.raises(PathEscapeError):
        delete_file(tmp_path, "../outside.oql")


def test_write_file_rejects_sibling_with_shared_directory_prefix(tmp_path):
    base = tmp_path / "scenarios"
    base.mkdir()
    sibling_target = tmp_path / "scenarios-private" / "leak.oql"

    with pytest.raises(PathEscapeError):
        write_file(base, "../scenarios-private/leak.oql", "password=hunter2")

    assert not sibling_target.exists()
