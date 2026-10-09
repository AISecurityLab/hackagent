#!/usr/bin/env python3
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check the links that only exist inside modals.

Modal content renders on click, so the Docusaurus build never sees the
``href`` of a glossary term or a ``<Modal href="...">``. Run after
``npm run build``: every such link must name a built page, and an anchor
on that page when it has one.

Usage: python docs/scripts/check_modal_links.py [docs_dir]
"""

import re
import sys
from pathlib import Path


def modal_links(docs_dir: Path) -> list[tuple[str, str]]:
    terms = docs_dir / "src" / "components" / "Glossary" / "terms.tsx"
    links = [
        (href, str(terms)) for href in re.findall(r"href: '([^']+)'", terms.read_text())
    ]
    for page in (docs_dir / "docs").rglob("*.mdx"):
        if "hackagent" in page.relative_to(docs_dir / "docs").parts[:1]:
            continue
        for href in re.findall(r'<Modal[^>]*\bhref="([^"]+)"', page.read_text()):
            links.append((href, str(page.relative_to(docs_dir))))
    return links


def main(docs_dir: Path) -> int:
    build = docs_dir / "build"
    broken = []
    links = modal_links(docs_dir)
    for href, source in links:
        path, _, anchor = href.partition("#")
        page = build / f"{path.strip('/')}.html"
        if not page.is_file():
            page = build / path.strip("/") / "index.html"
        if not page.is_file():
            broken.append(f"{source}: {href} (no such page)")
        elif anchor and f'id="{anchor}"' not in page.read_text(encoding="utf-8"):
            broken.append(f"{source}: {href} (no such anchor)")
    for line in broken:
        print(f"❌ {line}")
    print(f"Checked {len(links)} modal links, {len(broken)} broken.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(
        main(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent))
    )
