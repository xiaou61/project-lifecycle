#!/usr/bin/env python3
"""文档死链检查：README 与 VitePress docs 里的站内链接必须指向真实文件。

VitePress 用 clean URL（省略 .md 后缀），所以解析时同时尝试 原路径 /
+".md" / +"/index.md" / +".html"。外链（http/mailto/tel）与纯锚点跳过。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LINK = re.compile(r"\]\(([^)\s]+)\)")
EXTERNAL = re.compile(r"^(https?:|mailto:|tel:|#)")


def candidate_paths(page: Path, target: str) -> list[Path]:
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return []
    if target.startswith("/"):
        raw = DOCS / target.lstrip("/")
    else:
        raw = page.parent / target
    return [raw, Path(str(raw) + ".md"), raw / "index.md", Path(str(raw) + ".html")]


class DocumentLinksTest(unittest.TestCase):
    def test_relative_links_resolve(self) -> None:
        pages = [ROOT / "README.md", *sorted(DOCS.rglob("*.md"))]
        broken: list[str] = []
        for page in pages:
            if not page.exists():
                continue
            for lineno, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
                for match in LINK.finditer(line):
                    target = match.group(1)
                    if EXTERNAL.match(target):
                        continue
                    candidates = candidate_paths(page, target)
                    if candidates and not any(path.exists() for path in candidates):
                        broken.append(f"{page.relative_to(ROOT)}:{lineno}: {target}")
        self.assertEqual(broken, [], "文档存在死链：\n" + "\n".join(broken))


if __name__ == "__main__":
    unittest.main()
