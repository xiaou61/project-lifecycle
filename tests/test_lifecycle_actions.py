#!/usr/bin/env python3
"""approve / archive 自检：批量签署只写一条历史；归档只动目录且拒绝未完成项。"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "project-lifecycle" / "scripts"))

import project_status
import update_history


FRONTMATTER = """---
work_id: WORK-001
work: 示例功能
artifact: {artifact}
status: {status}
---

# 示例
"""


def build_project(root: Path) -> Path:
    """搭一个最小可用的 .agent：工作项四件工件 + 空更新历史。"""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    work_dir = root / ".agent" / "changes" / "WORK-001-示例功能"
    work_dir.mkdir(parents=True)
    (root / ".agent" / "history").mkdir()
    (root / ".agent" / "history" / "updates.md").write_text(
        "# 更新历史\n\n当前暂无更新记录。\n", encoding="utf-8"
    )
    (root / ".agent" / "rules").mkdir()
    (root / ".agent" / "rules" / "always.md").write_text(
        "---\nstatus: active\nconfigured: true\n---\n\n# 规范\n", encoding="utf-8"
    )
    for artifact in ("requirements", "proposal", "design", "tasks"):
        (work_dir / f"{artifact}.md").write_text(
            FRONTMATTER.format(artifact=artifact, status="draft"), encoding="utf-8"
        )
    return work_dir


def history_entries(root: Path) -> int:
    path = root / ".agent" / "history" / "updates.md"
    return path.read_text(encoding="utf-8").count("\n## 20")


class ApproveAllTest(unittest.TestCase):
    def test_single_history_entry_for_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work_dir = build_project(root)
            args = argparse.Namespace(
                work="WORK-001", artifact="all", by="张三", role="产品", json=False
            )
            update_history.approve(args, root)
            for artifact in ("requirements", "proposal", "design", "tasks"):
                text = (work_dir / f"{artifact}.md").read_text(encoding="utf-8")
                self.assertIn("approved_by: 张三", text)
                self.assertIn("status: approved", text)
            self.assertEqual(history_entries(root), 1)

    def test_single_artifact_keeps_other_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work_dir = build_project(root)
            args = argparse.Namespace(
                work="WORK-001", artifact="requirements", by="张三", role="", json=False
            )
            update_history.approve(args, root)
            self.assertIn(
                "status: approved",
                (work_dir / "requirements.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "status: draft",
                (work_dir / "design.md").read_text(encoding="utf-8"),
            )

    def test_test_report_still_requires_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work_dir = build_project(root)
            testing = work_dir / "testing"
            testing.mkdir()
            (testing / "report.md").write_text(
                FRONTMATTER.format(artifact="test-report", status="partial"), encoding="utf-8"
            )
            args = argparse.Namespace(
                work="WORK-001", artifact="test-report", by="李四", role="", json=False
            )
            with self.assertRaises(RuntimeError):
                update_history.approve(args, root)

    def test_by_falls_back_to_project_approver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work_dir = build_project(root)
            (root / ".agent" / "rules" / "always.md").write_text(
                "---\nstatus: active\nconfigured: true\napprover: 王五\n---\n\n# 规范\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                work="WORK-001", artifact="requirements", by=None, role="", json=False
            )
            update_history.approve(args, root)
            self.assertIn(
                "approved_by: 王五",
                (work_dir / "requirements.md").read_text(encoding="utf-8"),
            )

    def test_by_missing_everywhere_refuses_to_guess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_project(root)
            args = argparse.Namespace(
                work="WORK-001", artifact="requirements", by=None, role="", json=False
            )
            with self.assertRaises(RuntimeError):
                update_history.approve(args, root)


class ArchiveTest(unittest.TestCase):
    def test_refuses_unfinished_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_project(root)
            args = argparse.Namespace(work="WORK-001", json=False)
            update_history.archive_completed(args, root)
            self.assertTrue((root / ".agent" / "changes" / "WORK-001-示例功能").is_dir())
            self.assertFalse((root / ".agent" / "changes" / "archive").exists())


class EvidenceDetailTest(unittest.TestCase):
    def test_incomplete_row_names_the_row_and_the_missing_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.md"
            report.write_text(
                "---\nartifact: test-report\nstatus: passed\nevidence: required\n---\n\n"
                "## 验证结果\n\n"
                "| 检查项 | 命令 | 退出码 | 结果 | 证据 |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| AC-001 登录 | `pytest -q` | 0 | 通过 | logs/a.txt |\n"
                "| AC-002 注册 |  | 0 | 通过 | logs/b.txt |\n",
                encoding="utf-8",
            )
            result = project_status.testing_evidence_status(report, {"AC-001", "AC-002"})
            self.assertEqual(result["status"], "incomplete")
            message = " ".join(result["warnings"])
            self.assertIn("第 2 个数据行", message)
            self.assertIn("AC-002 注册", message)
            self.assertIn("命令", message)
            self.assertNotIn("AC-001 登录", message)


class PlanHygieneTest(unittest.TestCase):
    def write_tasks(self, work_dir: Path, body: str) -> dict[str, object]:
        (work_dir / "tasks.md").write_text(body, encoding="utf-8")
        tasks = {"total": 1, "state_known": True, "warnings": []}
        return tasks

    def test_missing_review_focus_flagged_while_implementing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            tasks = self.write_tasks(work_dir, "### TASK-001 | done | 甲\n")
            hygiene = project_status.plan_hygiene(
                work_dir, "strict", {"tasks": "approved", "test_report": "missing"}, tasks
            )
            self.assertTrue(hygiene)
            self.assertIn("评审焦点", hygiene[0])

    def test_present_review_focus_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            tasks = self.write_tasks(
                work_dir, "## 评审焦点\n\n| 失败模式 | 任务 | 测试 |\n\n### TASK-001 | done | 甲\n"
            )
            self.assertEqual(
                project_status.plan_hygiene(
                    work_dir, "strict", {"tasks": "approved", "test_report": "missing"}, tasks
                ),
                [],
            )

    def test_finished_item_not_nagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            tasks = self.write_tasks(work_dir, "### TASK-001 | done | 甲\n")
            self.assertEqual(
                project_status.plan_hygiene(
                    work_dir, "strict", {"tasks": "approved", "test_report": "passed"}, tasks
                ),
                [],
            )

    def test_managed_mode_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            tasks = self.write_tasks(work_dir, "### TASK-001 | done | 甲\n")
            self.assertEqual(
                project_status.plan_hygiene(
                    work_dir, "managed", {"tasks": "approved", "test_report": "missing"}, tasks
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
