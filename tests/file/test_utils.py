"""Tests for file utility functions."""

from pathlib import Path
import tempfile
import time

import pytest

from provide.foundation.file.utils import (
    backup_file,
    find_files,
    get_mtime,
    get_size,
    touch,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


def test_get_size_existing_file(temp_dir) -> None:
    """Test getting size of existing file."""
    path = temp_dir / "test.txt"
    content = b"Hello, World!"
    path.write_bytes(content)

    size = get_size(path)
    assert size == len(content)


def test_get_size_missing_file(temp_dir) -> None:
    """Test getting size of missing file returns 0."""
    path = temp_dir / "nonexistent.txt"

    size = get_size(path)
    assert size == 0


def test_get_size_empty_file(temp_dir) -> None:
    """Test getting size of empty file."""
    path = temp_dir / "empty.txt"
    path.touch()

    size = get_size(path)
    assert size == 0


def test_get_size_with_string_path(temp_dir) -> None:
    """Test get_size accepts string path."""
    path = temp_dir / "test.txt"
    path.write_bytes(b"test")

    size = get_size(str(path))
    assert size == 4


def test_get_mtime_existing_file(temp_dir) -> None:
    """Test getting modification time of existing file."""
    path = temp_dir / "test.txt"
    before = time.time()
    path.write_text("content")
    after = time.time()

    mtime = get_mtime(path)
    assert mtime is not None
    assert before <= mtime <= after


def test_get_mtime_missing_file(temp_dir) -> None:
    """Test getting mtime of missing file returns None."""
    path = temp_dir / "nonexistent.txt"

    mtime = get_mtime(path)
    assert mtime is None


def test_get_mtime_with_string_path(temp_dir) -> None:
    """Test get_mtime accepts string path."""
    path = temp_dir / "test.txt"
    path.write_text("test")

    mtime = get_mtime(str(path))
    assert mtime is not None


def test_touch_creates_file(temp_dir) -> None:
    """Test touch creates new file."""
    path = temp_dir / "new.txt"

    touch(path)

    assert path.exists()
    assert path.is_file()
    assert path.stat().st_size == 0


def test_touch_updates_existing_file(temp_dir) -> None:
    """Test touch updates timestamp of existing file."""
    path = temp_dir / "existing.txt"
    path.write_text("content")

    # Get original mtime
    original_mtime = path.stat().st_mtime

    # Wait a bit and touch
    time.sleep(0.01)
    touch(path)

    # mtime should be updated
    new_mtime = path.stat().st_mtime
    assert new_mtime > original_mtime

    # Content should be preserved
    assert path.read_text() == "content"


def test_touch_with_mode(temp_dir) -> None:
    """Test touch creates file with specific mode."""

    path = temp_dir / "test.txt"
    mode = 0o600

    touch(path, mode=mode)

    assert path.exists()
    assert path.stat().st_mode & 0o777 == mode


def test_touch_exist_not_ok(temp_dir) -> None:
    """Test touch raises when exist_ok=False."""
    path = temp_dir / "test.txt"
    path.write_text("content")

    with pytest.raises(FileExistsError):
        touch(path, exist_ok=False)


def test_touch_creates_parent_dirs(temp_dir) -> None:
    """Test touch creates parent directories."""
    path = temp_dir / "subdir" / "nested" / "file.txt"

    touch(path)

    assert path.exists()
    assert path.parent.exists()
    assert path.parent.parent.exists()


def test_find_files_basic(temp_dir) -> None:
    """Test finding files with basic pattern."""
    # Create test files
    (temp_dir / "test1.py").write_text("code")
    (temp_dir / "test2.py").write_text("code")
    (temp_dir / "test.txt").write_text("text")
    (temp_dir / "subdir").mkdir()
    (temp_dir / "subdir" / "test3.py").write_text("code")

    # Find Python files
    files = find_files("*.py", root=temp_dir)

    assert len(files) == 3
    names = {f.name for f in files}
    assert names == {"test1.py", "test2.py", "test3.py"}


def test_find_files_non_recursive(temp_dir) -> None:
    """Test non-recursive file finding."""
    # Create test files
    (temp_dir / "test1.py").write_text("code")
    (temp_dir / "test2.py").write_text("code")
    (temp_dir / "subdir").mkdir()
    (temp_dir / "subdir" / "test3.py").write_text("code")

    # Find Python files non-recursively
    files = find_files("*.py", root=temp_dir, recursive=False)

    assert len(files) == 2
    names = {f.name for f in files}
    assert names == {"test1.py", "test2.py"}


def test_find_files_nested_pattern(temp_dir) -> None:
    """Test finding files with nested pattern."""
    # Create test structure
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").write_text("code")
    (temp_dir / "tests").mkdir()
    (temp_dir / "tests" / "test_main.py").write_text("test")
    (temp_dir / "docs").mkdir()
    (temp_dir / "docs" / "readme.md").write_text("docs")

    # Find files in tests directory
    files = find_files("tests/*.py", root=temp_dir)

    assert len(files) == 1
    assert files[0].name == "test_main.py"


def test_find_files_missing_root(temp_dir) -> None:
    """Test find_files with non-existent root."""
    root = temp_dir / "nonexistent"

    files = find_files("*.py", root=root)

    assert files == []


def test_find_files_excludes_directories(temp_dir) -> None:
    """Test find_files excludes directories."""
    # Create files and directories
    (temp_dir / "file.txt").write_text("content")
    (temp_dir / "dir.txt").mkdir()  # Directory with .txt name

    files = find_files("*.txt", root=temp_dir)

    assert len(files) == 1
    assert files[0].name == "file.txt"


def test_backup_file_basic(temp_dir) -> None:
    """Test basic file backup."""
    path = temp_dir / "test.txt"
    content = "Original content"
    path.write_text(content)

    backup_path = backup_file(path)

    assert backup_path is not None
    assert backup_path.exists()
    assert backup_path.name == "test.txt.bak"
    assert backup_path.read_text() == content
    assert path.exists()  # Original still exists


def test_backup_file_with_timestamp(temp_dir) -> None:
    """Test backup with timestamp."""
    path = temp_dir / "test.txt"
    content = "Original content"
    path.write_text(content)

    backup_path = backup_file(path, timestamp=True)

    assert backup_path is not None
    assert backup_path.exists()
    # Should have format like test.20231225_143022.bak
    assert backup_path.name.startswith("test.")
    assert backup_path.name.endswith(".bak")
    assert len(backup_path.name) > len("test..bak")  # Has timestamp
    assert backup_path.read_text() == content


def test_backup_file_custom_suffix(temp_dir) -> None:
    """Test backup with custom suffix."""
    path = temp_dir / "test.txt"
    path.write_text("content")

    backup_path = backup_file(path, suffix=".backup")

    assert backup_path is not None
    assert backup_path.name == "test.txt.backup"


def test_backup_file_multiple_backups(temp_dir) -> None:
    """Test creating multiple backups."""
    path = temp_dir / "test.txt"
    path.write_text("version 1")

    # First backup
    backup1 = backup_file(path)
    assert backup1.name == "test.txt.bak"

    # Modify original
    path.write_text("version 2")

    # Second backup should get a different name
    backup2 = backup_file(path)
    assert backup2.name == "test.txt.bak.1"

    # Third backup
    path.write_text("version 3")
    backup3 = backup_file(path)
    assert backup3.name == "test.txt.bak.2"

    # Check all backups exist
    assert backup1.exists()
    assert backup2.exists()
    assert backup3.exists()


def test_backup_file_missing_source(temp_dir) -> None:
    """Test backup of non-existent file returns None."""
    path = temp_dir / "nonexistent.txt"

    backup_path = backup_file(path)

    assert backup_path is None


def test_backup_file_preserves_metadata(temp_dir) -> None:
    """Test backup preserves file metadata."""
    import os

    path = temp_dir / "test.txt"
    path.write_text("content")
    os.chmod(path, 0o600)

    backup_path = backup_file(path)

    assert backup_path is not None
    # shutil.copy2 should preserve permissions
    assert backup_path.stat().st_mode & 0o777 == 0o600
