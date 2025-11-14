"""Generate API reference pages for MkDocs documentation.

This module auto-generates markdown files with mkdocstrings references
for Python source code at MkDocs build time.

Usage in mkdocs.yml:
    plugins:
      - gen-files:
          scripts:
            - gen:provide.foundry.docs.gen_ref_pages
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

from provide.foundation import logger


def generate_reference_pages() -> None:
    """Generate API reference markdown files from Python source.

    Scans the src/ directory for Python files and generates corresponding
    markdown documentation files with mkdocstrings references. Creates
    SUMMARY.md for literate-nav navigation.

    Works in both standalone and monorepo contexts by using MKDOCS_CONFIG_DIR
    environment variable to locate the correct source directory.

    The function:
    - Skips __pycache__ directories
    - Skips private modules (except __init__.py)
    - Converts __init__.py to index.md
    - Generates navigation structure
    - Sets edit paths to source files
    """
    import os

    nav = mkdocs_gen_files.Nav()  # type: ignore[attr-defined,no-untyped-call]

    # Get the directory containing mkdocs.yml (works in both standalone and monorepo)
    config_dir = Path(os.getenv("MKDOCS_CONFIG_DIR", "."))
    src_root = config_dir / "src"

    # Debug logging
    try:
        logger.debug(
            "gen_ref_pages starting",
            cwd=str(Path.cwd()),
            mkdocs_config_dir=os.getenv("MKDOCS_CONFIG_DIR", "NOT_SET"),
            config_dir=str(config_dir.absolute()),
            src_root=str(src_root.absolute()),
            src_root_exists=src_root.exists(),
        )
    except Exception:
        # Logger might not be available in gen-files plugin context
        pass

    # Fallback if source directory not found
    if not src_root.exists():
        # Try current directory (for standalone builds)
        src_root = Path("src")
        try:
            logger.debug(
                "gen_ref_pages fallback to current directory",
                fallback_src_root=str(src_root.absolute()),
                fallback_exists=src_root.exists(),
            )
        except Exception:
            pass
        if not src_root.exists():
            try:
                logger.warning("gen_ref_pages: No source files found, skipping generation")
            except Exception:
                pass
            return  # No source files to document

    for path in sorted(src_root.rglob("*.py")):
        # Skip __pycache__ directories
        if "__pycache__" in str(path):
            continue

        # Skip files in directories that aren't Python packages (no __init__.py)
        # Check all parent directories from src_root to file location
        current_dir = path.parent
        is_package = True
        while current_dir != src_root and current_dir > src_root:
            if not (current_dir / "__init__.py").exists():
                is_package = False
                break
            current_dir = current_dir.parent

        if not is_package:
            continue

        module_path = path.relative_to(src_root).with_suffix("")
        doc_path = Path("reference") / module_path.with_suffix(".md")
        full_doc_path = Path("reference") / module_path.with_suffix(".md")

        parts = tuple(module_path.parts)

        # Skip private modules (but allow __init__)
        if any(part.startswith("_") and part != "__init__" for part in parts):
            continue

        # Handle __init__.py files -> index.md
        if parts[-1] == "__init__":
            parts = parts[:-1]
            doc_path = doc_path.with_name("index.md")
            full_doc_path = full_doc_path.with_name("index.md")

        # Skip empty parts
        if not parts:
            continue

        # Strip "reference/" prefix from nav paths
        nav_path = str(doc_path)
        if nav_path.startswith("reference/"):
            nav_path = nav_path[10:]  # Remove "reference/" prefix
        nav[parts] = nav_path

        # Create markdown file with mkdocstrings reference
        with mkdocs_gen_files.open(full_doc_path, "w") as fd:
            identifier = ".".join(parts)
            print(f"::: {identifier}", file=fd)

        # Set edit path to source file
        mkdocs_gen_files.set_edit_path(full_doc_path, path)

    # Generate SUMMARY.md for literate-nav
    with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
        nav_file.writelines(nav.build_literate_nav())


# Support direct execution for testing/debugging
if __name__ == "__main__":
    generate_reference_pages()
