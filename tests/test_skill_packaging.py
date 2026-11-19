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


class DocumentedCommandsTest(unittest.TestCase):
    """面向使用者的文档里出现的每条 `$lifecycle <cmd>` 都必须是真实命令。

    这补上了此前缺失的一环：命令被删掉后，README/docs/examples 里的调用示例
    没有任何测试覆盖，只能靠人工发现（update_history 相关命令就是这么留下来的）。
    历史记录（CHANGELOG.md、wiki/ 下的 ADR）有意保留旧命令名以如实记录当时决策，
    因此不纳入扫描范围。
    """

    # 匹配 `$lifecycle <cmd>`、`project-lifecycle.ps1 <cmd>`、
    # `project-lifecycle.sh <cmd>`、`project-lifecycle.py <cmd>`，允许命令前带 --flag。
    INVOCATION = re.compile(
        r"(?:project-lifecycle(?:\.(?:ps1|sh|py))?|\$lifecycle)"
        r"\s+(?:--?[\w-]+\s+)*([a-zA-Z][\w-]*)"
    )

    def _user_facing_docs(self) -> list[Path]:
        docs = [ROOT / "README.md", ROOT / "desktop" / "README.md"]
        docs += sorted((ROOT / "docs").rglob("*.md"))
        docs += sorted(SKILL_DIR.rglob("*.md"))
        return [path for path in docs if path.exists()]

    def test_documented_commands_are_known(self) -> None:
        bad = []
        for page in self._user_facing_docs():
            for lineno, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
                for match in self.INVOCATION.finditer(line):
                    command = match.group(1)
                    if command not in entry.COMMANDS:
                        rel = page.relative_to(ROOT)
                        bad.append(f"{rel}:{lineno}: `{command}` —— {line.strip()}")
        self.assertEqual(bad, [], "文档里出现了不存在的命令：\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
