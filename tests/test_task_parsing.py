#!/usr/bin/env python3
"""任务解析自检：四种真实写法都要数出任务，且不能把示例表格算进去。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "project-lifecycle" / "scripts"))

import project_status


class TaskParsingTest(unittest.TestCase):
    def parse(self, text: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tasks.md"
            path.write_text(text, encoding="utf-8")
            return project_status.task_counts(path)

    def test_heading_format(self) -> None:
        counts = self.parse(
            "### TASK-001 | done | 建表\n\n- 验证：建表跑通\n\n"
            "## TASK-002 | in_progress | 接口\n"
        )
        self.assertEqual((counts["done"], counts["in_progress"], counts["total"]), (1, 1, 2))
        self.assertTrue(counts["state_known"])

    def test_table_with_status_column(self) -> None:
        counts = self.parse(
            "| # | 任务 | 状态 | 验证 |\n| --- | --- | --- | --- |\n"
            "| T-01 | 建表 | done | 通过 |\n| T-02 | 接口 | pending | 待跑 |\n"
        )
        self.assertEqual((counts["done"], counts["pending"], counts["total"]), (1, 1, 2))

    def test_table_without_status_column_reports_unknown(self) -> None:
        counts = self.parse(
            "| # | 任务 | 依赖 | 验证 |\n| --- | --- | --- | --- |\n"
            "| T-01 | 建表 | — | 通过 |\n| T-02 | 接口 | T-01 | 通过 |\n"
        )
        self.assertEqual(counts["total"], 2)
        self.assertFalse(counts["state_known"])
        self.assertTrue(counts["warnings"])

    def test_section_checkboxes(self) -> None:
        counts = self.parse(
            "## T-01 清单\n\n- [x] 标注注解\n- [x] 排除 fixture\n\n"
            "## T-02 闸门\n\n- [x] 建测试\n- [ ] 接 CI\n"
        )
        self.assertEqual((counts["done"], counts["in_progress"], counts["total"]), (1, 1, 2))

    def test_heading_tasks_win_over_stray_checkboxes(self) -> None:
        counts = self.parse(
            "### TASK-001 | done | 甲\n\n- [ ] 子步骤一\n- [x] 子步骤二\n\n"
            "### TASK-002 | pending | 乙\n"
        )
        self.assertEqual((counts["pending"], counts["done"], counts["total"]), (1, 1, 2))

    def test_missing_file(self) -> None:
        counts = project_status.task_counts(Path("no-such-tasks.md"))
        self.assertEqual(counts["total"], 0)
        self.assertEqual(counts["format"], "missing")

    def test_unparseable_task_ids_are_reported(self) -> None:
        counts = self.parse("## 任务\n\n任务一 TASK-100 待做\n任务二 TASK-101 做完\n")
        self.assertEqual(counts["total"], 0)
        self.assertTrue(any("没有" in warning for warning in counts["warnings"]))


if __name__ == "__main__":
    unittest.main()
