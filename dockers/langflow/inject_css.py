"""Inject Flowsdone's stylesheet into Langflow's frontend index.html.

Run at image build time. Langflow's own files are otherwise untouched: only a
<style> block is added to the page. Fails the build if the page can't be
found or patched, so a Langflow upgrade that changes it is noticed there.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MARKER = "<!-- flowsdone-css -->"


def inject(index: Path, css: str) -> bool:
    """Inline `css` at the end of the page's <head> (idempotent).

    Args:
        index (Path): Langflow's frontend index.html.
        css (str): The stylesheet.

    Returns:
        bool: True if the page was patched, False if it already was.

    Raises:
        ValueError: If the page has no </head>.
    """
    html = index.read_text(encoding="utf-8")
    if MARKER in html:
        return False
    if "</head>" not in html:
        raise ValueError(f"no </head> in {index}")
    index.write_text(html.replace("</head>", f"{MARKER}<style>{css}</style></head>", 1), encoding="utf-8")
    return True


def main(css_path: str) -> None:
    """Locate Langflow's index.html and inject the stylesheet.

    Args:
        css_path (str): The stylesheet to inject.
    """
    # find_spec locates the package without importing it (importing langflow is slow).
    spec = importlib.util.find_spec("langflow")
    if spec is None or spec.origin is None:
        sys.exit("inject_css: langflow package not found")
    index = Path(spec.origin).parent / "frontend" / "index.html"
    try:
        patched = inject(index, Path(css_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        sys.exit(f"inject_css: {exc}")
    print(f"inject_css: {'patched' if patched else 'already patched'} {index}")


if __name__ == "__main__":
    main(sys.argv[1])
