#!/usr/bin/env python3
"""Manage release versioning and packaging for python-hilo."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys

# Pattern for Calendar Versioning: YYYY.M.N (e.g. 2026.10.1)
# with an optional pre-release suffix (e.g. 2026.10.1b1).
VERSION_PATTERN = re.compile(r"^[0-9]{4}\.[0-9]{1,2}\.[0-9]+(b[0-9]+)?$")
ROOT = Path(__file__).resolve().parent.parent


def clean_version_from_tag(tag: str) -> str:
    """Validate a release tag and strip the leading 'v' prefix.

    Raises ValueError if the tag does not follow the expected CalVer format.
    """
    version = tag.removeprefix("v")
    if not VERSION_PATTERN.match(version):
        raise ValueError(
            f"Release tag '{tag}' must match version format vYYYY.M.N "
            "(e.g. v2026.10.1 or v2026.10.1b1)"
        )
    return version


def get_next_version(reference_date: datetime | None = None) -> str:
    """Calculate the next version name (YYYY.M.N) from existing git tags.

    Inspects git tags for the current UTC year and month. If tags exist, increments
    the highest patch number; otherwise starts at patch 1 (e.g. 2026.10.1).
    """
    now = reference_date or datetime.now(timezone.utc)
    prefix = f"{now.year}.{now.month}"

    try:
        output = subprocess.check_output(
            ["git", "tag", "--list", f"v{prefix}.*", f"{prefix}.*"],
            cwd=ROOT,
            text=True,
        )
        tags = output.splitlines()
    except (subprocess.SubprocessError, FileNotFoundError):
        tags = []

    # Only match final/stable releases so pre-releases (e.g. v2026.10.1b1)
    # do not consume the stable patch number for draft releases.
    pattern = re.compile(rf"^v?{re.escape(prefix)}\.([0-9]+)$")
    patches = [int(m.group(1)) for tag in tags if (m := pattern.match(tag.strip()))]
    next_patch = max(patches, default=0) + 1
    return f"{prefix}.{next_patch}"


def set_package_version(tag_or_version: str, root_dir: Path = ROOT) -> str:
    """Validate and update the version in pyproject.toml and pyhilo/const.py."""
    version = clean_version_from_tag(tag_or_version)

    pyproject_path = root_dir / "pyproject.toml"
    if not pyproject_path.is_file():
        raise FileNotFoundError(f"Missing {pyproject_path}")
    content = pyproject_path.read_text(encoding="utf-8")
    new_content, count = re.subn(
        r'(?m)^version = "[^"]*"',
        f'version = "{version}"',
        content,
        count=1,
    )
    if count == 0:
        raise ValueError(f"Could not find 'version' field in {pyproject_path}")
    pyproject_path.write_text(new_content, encoding="utf-8")

    const_path = root_dir / "pyhilo" / "const.py"
    if not const_path.is_file():
        raise FileNotFoundError(f"Missing {const_path}")
    content = const_path.read_text(encoding="utf-8")
    new_content, count = re.subn(
        r'PYHILO_VERSION: Final = "[^"]*"',
        f'PYHILO_VERSION: Final = "{version}"',
        content,
    )
    if count == 0:
        raise ValueError(f"Could not find 'PYHILO_VERSION' constant in {const_path}")
    const_path.write_text(new_content, encoding="utf-8")

    return version


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for release automation."""
    parser = argparse.ArgumentParser(
        description="Manage release versions for python-hilo."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--next-version",
        action="store_true",
        help="Calculate the next CalVer version from git tags",
    )
    group.add_argument(
        "--set-version",
        metavar="TAG",
        help="Set package version in pyproject.toml and pyhilo/const.py",
    )

    args = parser.parse_args(argv)

    if args.next_version:
        sys.stdout.write(f"{get_next_version()}\n")
    elif args.set_version:
        version = set_package_version(args.set_version)
        sys.stdout.write(f"Updated package version to {version}\n")


if __name__ == "__main__":
    main()
