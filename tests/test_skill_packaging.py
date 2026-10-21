#!/usr/bin/env python3
"""Skill 包自检：文档里写出的路径必须真实存在，命令映射必须都指向存在的脚本。

这两类问题此前靠人工发现：SKILL.md 让 Agent 在 scripts/ 下跑测试（实际在 tests/），
结果是 `Ran 0 tests ... OK`，一条假的通过。
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "project-lifecycle"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import importlib

entry = importlib.import_module("project-lifecycle")


class DocumentedPathsTest(unittest.TestCase):
    def test_skill_md_paths_exist(self) -> None:
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        missing = sorted(
            path
            for path in re.findall(r"`((?:references|scripts|examples)/[\w./-]+)`", text)
            if not (SKILL_DIR / path).exists()
        )
        self.assertEqual(missing, [], f"SKILL.md 引用了不存在的路径：{missing}")

    def test_relative_markdown_links_exist(self) -> None:
        missing = []
        for page in SKILL_DIR.rglob("*.md"):
            for target in re.findall(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)", page.read_text(encoding="utf-8")):
                if not (page.parent / target).exists():
                    missing.append(f"{page.relative_to(SKILL_DIR)} -> {target}")
        self.assertEqual(missing, [], f"死链：{missing}")

    def test_documented_test_command_matches_layout(self) -> None:
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("-s tests", text)
        self.assertTrue(list((ROOT / "tests").glob("test_*.py")))


class CommandMapTest(unittest.TestCase):
    def test_every_command_targets_an_existing_script(self) -> None:
        for command, (script, _) in entry.COMMANDS.items():
            self.assertTrue((SKILL_DIR / "scripts" / script).exists(), f"{command} -> {script} 不存在")

    def test_entry_adapters_exist(self) -> None:
        self.assertTrue((SKILL_DIR / "scripts" / "project-lifecycle.ps1").exists())
        self.assertTrue((SKILL_DIR / "scripts" / "project-lifecycle.sh").exists())


if __name__ == "__main__":
    unittest.main()
