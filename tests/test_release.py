"""Unit tests for scripts/release.py."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.release import (
    clean_version_from_tag,
    get_next_version,
    main,
    set_package_version,
)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v2026.10.1", "2026.10.1"),
        ("2026.10.1", "2026.10.1"),
        ("v2026.10.1b2", "2026.10.1b2"),
        ("v2025.5.12", "2025.5.12"),
    ],
)
def test_clean_version_from_tag_valid(tag: str, expected: str) -> None:
    """Test valid version tags are parsed correctly."""
    assert clean_version_from_tag(tag) == expected


@pytest.mark.parametrize(
    "invalid_tag",
    [
        "v1.0.0",
        "invalid",
        "v2026.10",
        "v2026.10.",
        "v2026.10.1rc1",
        "v2026.10.1-beta",
    ],
)
def test_clean_version_from_tag_invalid(invalid_tag: str) -> None:
    """Test invalid version tags raise ValueError."""
    with pytest.raises(ValueError, match="must match version format"):
        clean_version_from_tag(invalid_tag)


@pytest.mark.parametrize(
    ("existing_tags", "expected_version"),
    [
        ("", "2026.10.1"),
        ("v2026.10.1\n", "2026.10.2"),
        ("v2026.10.1\nv2026.10.2\n", "2026.10.3"),
        ("v2026.10.1b1\n", "2026.10.1"),
        ("v2026.10.1\nv2026.10.2b1\n", "2026.10.2"),
        ("v2026.9.5\n", "2026.10.1"),
    ],
)
def test_get_next_version(existing_tags: str, expected_version: str) -> None:
    """Test next version calculation with various existing tag states."""
    ref_date = datetime(2026, 10, 15, tzinfo=timezone.utc)
    with patch("subprocess.check_output", return_value=existing_tags):
        assert get_next_version(reference_date=ref_date) == expected_version


def test_set_package_version_success(tmp_path: Path) -> None:
    """Test successfully updating pyproject.toml and pyhilo/const.py versions."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "python-hilo"\nversion = "2026.9.1"\n', encoding="utf-8"
    )

    const_dir = tmp_path / "pyhilo"
    const_dir.mkdir()
    const_file = const_dir / "const.py"
    const_file.write_text('PYHILO_VERSION: Final = "2026.9.01"\n', encoding="utf-8")

    version = set_package_version("v2026.10.1", root_dir=tmp_path)
    assert version == "2026.10.1"
    assert 'version = "2026.10.1"' in pyproject.read_text(encoding="utf-8")
    assert 'PYHILO_VERSION: Final = "2026.10.1"' in const_file.read_text(
        encoding="utf-8"
    )


def test_set_package_version_missing_files(tmp_path: Path) -> None:
    """Test that missing target files raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Missing"):
        set_package_version("v2026.10.1", root_dir=tmp_path)


def test_set_package_version_missing_pattern(tmp_path: Path) -> None:
    """Test that unmatched version patterns raise ValueError."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "python-hilo"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Could not find 'version' field"):
        set_package_version("v2026.10.1", root_dir=tmp_path)


def test_main_cli(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint flags."""
    with patch("scripts.release.get_next_version", return_value="2026.10.1"):
        main(["--next-version"])
        assert capsys.readouterr().out == "2026.10.1\n"

    with patch("scripts.release.set_package_version", return_value="2026.10.1"):
        main(["--set-version", "v2026.10.1"])
        assert capsys.readouterr().out == "Updated package version to 2026.10.1\n"
