from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "project-lifecycle"
STATUS_SCRIPT = SKILL_ROOT / "scripts" / "project_status.py"
INIT_SCRIPT = SKILL_ROOT / "scripts" / "init_project.py"
ARTIFACTS_SCRIPT = SKILL_ROOT / "scripts" / "artifacts.py"
LIFECYCLE_ENTRY = SKILL_ROOT / "scripts" / "project-lifecycle.py"


def load_status_module():
    spec = importlib.util.spec_from_file_location("project_status", STATUS_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 project_status.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_validate_module():
    validate_path = SKILL_ROOT / "scripts" / "project_validate.py"
    spec = importlib.util.spec_from_file_location("project_validate", validate_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 project_validate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["project_status"] = project_status
    spec.loader.exec_module(module)
    return module


project_status = load_status_module()
project_validate = load_validate_module()


def load_artifacts_module():
    spec = importlib.util.spec_from_file_location("artifacts", ARTIFACTS_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 artifacts.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["project_status"] = project_status
    spec.loader.exec_module(module)
    return module


artifacts = load_artifacts_module()


def artifact(
    path: Path,
    kind: str,
    status: str,
    body: str = "",
    *,
    work: str = "login",
    work_id: str | None = None,
    workflow: str | None = None,
    mode: str | None = None,
    mode_reason: str | None = None,
    depends_on: tuple[str, ...] = (),
    related_to: tuple[str, ...] = (),
    source_coverage: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    identity = f"work_id: {work_id}\n" if work_id else ""
    relations = ""
    workflow_field = f"workflow: {workflow}\n" if kind == "requirements" and workflow else ""
    mode_field = f"mode: {mode}\n" if kind == "requirements" and mode else ""
    mode_reason_field = f"mode_reason: {mode_reason}\n" if kind == "requirements" and mode_reason else ""
    source_coverage_field = "source_coverage: required\n" if kind == "requirements" and source_coverage else ""
    if kind == "requirements":
        relations = (
            f"depends_on: [{', '.join(depends_on)}]\n"
            f"related_to: [{', '.join(related_to)}]\n"
        )
    path.write_text(
        f"---\n{identity}work: {work}\nartifact: {kind}\nstatus: {status}\n{workflow_field}{mode_field}{mode_reason_field}{source_coverage_field}"
        f"{relations}updated: 2026-08-19\n---\n\n{body}\n",
        encoding="utf-8",
    )


class ProjectStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def work_dir(self) -> Path:
        work = self.project / ".agent" / "changes" / "login"
        work.mkdir(parents=True, exist_ok=True)
        return work

    def confirm_rules(self) -> None:
        rules = self.project / ".agent" / "rules" / "always.md"
        rules.parent.mkdir(parents=True, exist_ok=True)
        rules.write_text(
            "---\nartifact: project_rules\nstatus: active\nconfigured: true\n---\n\n"
            "# 项目常驻规范\n\n## MUST：所有任务\n\n- 运行测试\n",
            encoding="utf-8",
        )

    def approve_through_tasks(self, task_body: str = "") -> Path:
        self.confirm_rules()
        work = self.work_dir()
        for kind in ("requirements", "proposal", "design", "tasks"):
            artifact(work / f"{kind}.md", kind, "approved", task_body if kind == "tasks" else "")
        return work

    def managed_work(
        self,
        work_id: str,
        name: str,
        *,
        requirements_status: str = "approved",
        workflow: str = "full",
        mode: str | None = None,
        mode_reason: str | None = None,
        task_body: str = "### TASK-001 | pending | 实现需求",
        depends_on: tuple[str, ...] = (),
        related_to: tuple[str, ...] = (),
        source_coverage: bool = False,
    ) -> Path:
        self.confirm_rules()
        work_dir = self.project / ".agent" / "changes" / f"{work_id}-{name}"
        for kind in ("requirements", "proposal", "design", "tasks"):
            status = requirements_status if kind == "requirements" else "approved"
            artifact(
                work_dir / f"{kind}.md",
                kind,
                status,
                task_body if kind == "tasks" else "",
                work=name,
                work_id=work_id,
                workflow=workflow,
                mode=mode,
                mode_reason=mode_reason,
                depends_on=depends_on,
                related_to=related_to,
                source_coverage=source_coverage,
            )
        return work_dir

    def test_uninitialized_and_idle_project(self) -> None:
        status = project_status.inspect_project(self.project)
        self.assertFalse(status["initialized"])
        self.assertEqual(status["state"], "uninitialized")
        self.assertFalse(status["rules"]["present"])

        (self.project / ".agent" / "changes").mkdir(parents=True)
        status = project_status.inspect_project(self.project)
        self.assertTrue(status["initialized"])
        self.assertEqual(status["state"], "idle")
        self.assertEqual(status["next_work_id"], "WORK-001")
        self.assertFalse(status["rules"]["ready"])
        self.assertTrue(any("always.md" in warning for warning in status["warnings"]))

    def test_project_rules_are_reported_when_valid(self) -> None:
        rules = self.project / ".agent" / "rules" / "always.md"
        rules.parent.mkdir(parents=True)
        rules.write_text(
            "---\nartifact: project_rules\nstatus: active\n---\n\n"
            "# 项目常驻规范\n\n## MUST：所有任务\n\n- 运行测试\n",
            encoding="utf-8",
        )

        status = project_status.inspect_project(self.project)
        self.assertTrue(status["rules"]["present"])
        self.assertTrue(status["rules"]["ready"])
        self.assertTrue(status["rules"]["configured"])
        self.assertEqual(status["rules"]["status"], "active")
        self.assertNotIn("项目常驻规范", "\n".join(status["warnings"]))

    def test_uninitialized_status_uses_project_root_for_rules_path(self) -> None:
        (self.project / ".git").mkdir()
        nested = self.project / "src"
        nested.mkdir()
        status = project_status.inspect_project(nested)
        self.assertEqual(
            status["rules"]["path"],
            str(self.project / ".agent" / "rules" / "always.md"),
        )

    def test_missing_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "目标路径不存在"):
            project_status.inspect_project(self.project / "missing")

    def test_earliest_unmet_phase_wins(self) -> None:
        work = self.work_dir()
        artifact(work / "requirements.md", "requirements", "draft")
        artifact(work / "proposal.md", "proposal", "approved")

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "requirements")
        self.assertEqual(item["state"], "draft")
        self.assertTrue(item["warnings"])

    def test_draft_proposal_waits_for_approval(self) -> None:
        work = self.work_dir()
        artifact(work / "requirements.md", "requirements", "approved")
        artifact(work / "proposal.md", "proposal", "draft")

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "proposal")
        self.assertEqual(item["state"], "awaiting_approval")

    def test_pending_tasks_mean_implementation(self) -> None:
        work = self.approve_through_tasks(
            "### TASK-001 | pending | 实现登录\n\n### TASK-002 | done | 建立模型"
        )

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "implementation")
        self.assertEqual(item["state"], "in_progress")
        self.assertEqual(item["tasks"]["pending"], 1)
        self.assertEqual(item["tasks"]["done"], 1)

    def test_required_source_coverage_blocks_implementation_until_mapped(self) -> None:
        work = self.managed_work("WORK-010", "导入需求", source_coverage=True)

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["state"], "blocked")
        self.assertEqual(item["source_coverage"]["status"], "incomplete")

        requirements = work / "requirements.md"
        requirements.write_text(
            requirements.read_text(encoding="utf-8")
            + "\n## 来源覆盖\n\n| 来源 | 锚点 | REQ | AC | 状态 |\n"
            + "| --- | --- | --- | --- | --- |\n"
            + "| PRD.md | 第 12-18 行 | REQ-001 | AC-001 | verified |\n",
            encoding="utf-8",
        )
        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["state"], "in_progress")
        self.assertEqual(item["source_coverage"]["status"], "complete")

    def test_resume_context_auto_selects_one_active_work_item(self) -> None:
        self.managed_work("WORK-011", "恢复登录")

        status = project_status.inspect_project(self.project)
        resume = status["resume"]
        self.assertEqual(resume["mode"], "auto_resume")
        self.assertEqual(resume["work_item"]["work_id"], "WORK-011")
        self.assertIn("requirements.md", "\n".join(resume["read_paths"]))
        self.assertIn("WORK-011", resume["handoff_prompt"])

    def test_resume_context_carries_goal_acceptance_and_constraints(self) -> None:
        work = self.managed_work("WORK-011", "恢复登录")
        requirements = work / "requirements.md"
        requirements.write_text(
            requirements.read_text(encoding="utf-8")
            + "\n## 目标\n恢复登录后进入首页，并保留会话。\n"
            + "\n## 验收标准\n- AC-001：登录成功后进入首页\n- AC-002：刷新后仍保留会话\n"
            + "\n## 约束与依赖\n- 不修改现有登录接口\n- 必须兼容 Windows 客户端\n",
            encoding="utf-8",
        )

        resume = project_status.inspect_project(self.project)["resume"]
        work_item = resume["work_item"]
        self.assertEqual(work_item["goal"], "恢复登录后进入首页，并保留会话。")
        self.assertEqual(
            work_item["acceptance_criteria"],
            ["- AC-001：登录成功后进入首页", "- AC-002：刷新后仍保留会话"],
        )
        self.assertEqual(
            work_item["constraints"],
            ["- 不修改现有登录接口", "- 必须兼容 Windows 客户端"],
        )
        self.assertEqual(work_item["goal_status"], "present")
        self.assertFalse(resume["warnings"])
        self.assertIn("requirements.md 中的目标", resume["handoff_prompt"])
        rendered = project_status.render_resume(project_status.inspect_project(self.project))
        self.assertIn("目标：恢复登录后进入首页，并保留会话。", rendered)
        self.assertIn("AC-001：登录成功后进入首页", rendered)
        self.assertIn("约束：- 不修改现有登录接口", rendered)
        self.assertEqual(work_item["state_evidence"]["code_sync"], "unknown")
        self.assertTrue(work_item["state_evidence"]["requires_reconciliation"])
        self.assertIn("源码同步：unknown", rendered)

    def test_resume_context_warns_when_goal_or_acceptance_is_missing(self) -> None:
        self.managed_work("WORK-011", "缺少恢复事实")

        resume = project_status.inspect_project(self.project)["resume"]
        self.assertEqual(resume["work_item"]["goal_status"], "missing")
        self.assertEqual(resume["work_item"]["goal"], "")
        self.assertEqual(resume["work_item"]["acceptance_criteria"], [])
        self.assertTrue(any("目标" in warning for warning in resume["warnings"]))
        self.assertTrue(any("验收标准" in warning for warning in resume["warnings"]))
        self.assertIn("恢复提示：", project_status.render_resume(project_status.inspect_project(self.project)))

    def test_document_budget_warns_without_blocking_work(self) -> None:
        work = self.managed_work("WORK-017", "文档预算")
        (work / "requirements.md").write_text(
            (work / "requirements.md").read_text(encoding="utf-8")
            + "\n"
            + ("说明内容。" * 5000),
            encoding="utf-8",
        )

        item = project_status.inspect_project(self.project)["work_items"][0]
        budget = item["document_budget"]
        self.assertEqual(budget["status"], "warning")
        self.assertGreater(budget["total_bytes"], project_status.DOCUMENT_LIMITS["per_file_bytes"])
        self.assertEqual(item["state"], "in_progress")
        self.assertEqual(project_status.inspect_project(self.project)["resume"]["mode"], "auto_resume")
        self.assertTrue(any("核心 Markdown" in warning for warning in project_status.inspect_project(self.project)["resume"]["warnings"]))

    def test_verification_anchor_distinguishes_current_and_stale_snapshots(self) -> None:
        work = self.managed_work("WORK-018", "验证锚点")
        report = work / "testing" / "report.md"
        report.parent.mkdir()
        report.write_text(
            "---\nstatus: passed\nverified_commit: abcdef1234567\nverified_at: 2026-09-09 15:00:00 +0800\n---\n",
            encoding="utf-8",
        )

        clean = project_status.verification_anchor(
            work,
            {"head": "abcdef1234567890", "status": "clean"},
        )
        self.assertEqual(clean["status"], "verified")

        changed = project_status.verification_anchor(
            work,
            {"head": "1234567890abcdef", "status": "clean"},
        )
        self.assertEqual(changed["status"], "stale")

        dirty = project_status.verification_anchor(
            work,
            {"head": "abcdef1234567890", "status": "dirty"},
        )
        self.assertEqual(dirty["status"], "stale")

        # 只知道"脏"、取不到路径清单时按保守口径；能取到路径且全是 .agent/ 工件时不误判。
        dirty_docs_only = project_status.verification_anchor(
            work,
            {
                "head": "abcdef1234567890",
                "status": "dirty",
                "entries": [{"index": "M", "worktree": " ", "path": ".agent/history/updates.md"}],
            },
        )
        self.assertEqual(dirty_docs_only["status"], "verified")

        dirty_with_source = project_status.verification_anchor(
            work,
            {
                "head": "abcdef1234567890",
                "status": "dirty",
                "entries": [{"index": "M", "worktree": " ", "path": "src/app.ts"}],
            },
        )
        self.assertEqual(dirty_with_source["status"], "drift")

    def test_document_only_report_commit_can_remain_verified(self) -> None:
        source = self.project / "src" / "login.py"
        source.parent.mkdir(parents=True)
        source.write_text("VALUE = 1\n", encoding="utf-8")
        subprocess.run(["git", "init", "-b", "main"], cwd=self.project, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.project, check=True)
        subprocess.run(["git", "add", "src"], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-m", "code"], cwd=self.project, capture_output=True, check=True)
        code_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project, capture_output=True, text=True, check=True
        ).stdout.strip()

        work = self.managed_work("WORK-019", "报告提交", task_body="### TASK-001 | done | 完成")
        report = work / "testing" / "report.md"
        report.parent.mkdir()
        report.write_text(
            f"---\nstatus: passed\nverified_commit: {code_commit}\n---\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", ".agent"], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-m", "record verification"], cwd=self.project, capture_output=True, check=True)

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["state"], "complete")
        self.assertEqual(item["state_evidence"]["code_sync"], "verified")

    def test_resume_context_requires_selection_for_multiple_active_work_items(self) -> None:
        self.managed_work("WORK-011", "恢复登录")
        self.managed_work("WORK-012", "恢复权限")

        resume = project_status.inspect_project(self.project)["resume"]
        self.assertEqual(resume["mode"], "ask_user")
        self.assertEqual({item["work_id"] for item in resume["candidates"]}, {"WORK-011", "WORK-012"})

    def test_dirty_git_workspace_does_not_block_resume(self) -> None:
        """归因机制已于 2026-10-10 停用：未提交改动不再阻止自动恢复。"""
        self.managed_work("WORK-013", "恢复归因")
        result = subprocess.run(
            ["git", "init"],
            cwd=self.project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        status = project_status.inspect_project(self.project)
        self.assertEqual(status["git"]["status"], "dirty")
        self.assertEqual(status["work_items"][0]["workspace_attribution"]["status"], "not_required")
        self.assertEqual(status["resume"]["mode"], "auto_resume")

    def test_worktree_question_only_when_workspace_is_dirty(self) -> None:
        """干净工作区直接 proceed；有未提交改动才问一次；已隔离到 worktree 不再问。"""
        self.managed_work("WORK-014", "隔离实施")
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True, capture_output=True)
        for args in (
            ["git", "config", "user.email", "t@example.com"],
            ["git", "config", "user.name", "t"],
            ["git", "add", "."],
            ["git", "commit", "-qm", "init"],
        ):
            subprocess.run(args, cwd=self.project, check=True, capture_output=True)

        clean = project_status.inspect_project(self.project)
        self.assertFalse(clean["git"]["worktree"]["linked"])
        self.assertEqual(clean["resume"]["worktree"]["decision"], "proceed")

        # 新文件引用在 .gitignore 之外，确保算作未提交改动。
        (self.project / "note.txt").write_text("dirty\n", encoding="utf-8")
        dirty = project_status.inspect_project(self.project)
        self.assertEqual(dirty["git"]["status"], "dirty")
        self.assertEqual(dirty["resume"]["worktree"]["decision"], "ask_user")
        (self.project / "note.txt").unlink()

        linked = Path(tempfile.mkdtemp(prefix="pl-worktree-")) / "wt"
        subprocess.run(
            ["git", "worktree", "add", "-q", str(linked), "-b", "work/WORK-014"],
            cwd=self.project,
            check=True,
            capture_output=True,
        )
        try:
            inside = project_status.inspect_project(linked)
            self.assertTrue(inside["git"]["worktree"]["linked"])
            self.assertEqual(inside["resume"]["worktree"]["decision"], "active")
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(linked)],
                cwd=self.project, capture_output=True, check=False,
            )


    def test_legacy_workspace_attribution_is_ignored(self) -> None:
        """旧项目里的 workspace.md 不再被校验，也不再阻止恢复。"""
        self.managed_work("WORK-014", "归因完成")
        (self.project / "src").mkdir()
        (self.project / "src" / "login.py").write_text("VALUE = 1\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=self.project, capture_output=True, check=True)
        subprocess.run(["git", "add", "."], cwd=self.project, capture_output=True, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "base"],
            cwd=self.project,
            capture_output=True,
            check=True,
        )
        (self.project / "src" / "login.py").write_text("VALUE = 2\n", encoding="utf-8")
        status = project_status.inspect_project(self.project)
        head = status["git"]["head"]
        work = self.project / ".agent" / "changes" / "WORK-014-归因完成"
        (work / "workspace.md").write_text(
            f"---\nbase_commit: {head}\n---\n\n## 工作区归因\n\n"
            "| 路径 | 归属 | 说明 |\n| --- | --- | --- |\n"
            "| src/login.py | current_work | TASK-001 的实现 |\n",
            encoding="utf-8",
        )
        status = project_status.inspect_project(self.project)
        self.assertEqual(status["work_items"][0]["workspace_attribution"]["status"], "not_required")
        self.assertEqual(status["resume"]["mode"], "auto_resume")

    def test_structured_evidence_covers_all_acceptance_criteria(self) -> None:
        work = self.managed_work("WORK-015", "证据矩阵", task_body="### TASK-001 | done | 完成")
        requirements = work / "requirements.md"
        requirements.write_text(
            requirements.read_text(encoding="utf-8")
            + "\n## 目标\n目标\n\n## 验收标准\n- AC-001：登录成功\n- AC-002：退出成功\n",
            encoding="utf-8",
        )
        report = work / "testing" / "report.md"
        report.parent.mkdir()
        report.write_text(
            "---\nstatus: passed\nevidence: required\n---\n\n# 验证报告\n\n"
            "## 检查证据\n\n| 检查项 | 命令 | 退出码 | 结果 | 证据 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| AC-001 | pytest tests/test_login.py -q | 0 | passed | testing/logs/login.txt |\n"
            "| AC-002 | pytest tests/test_logout.py -q | 0 | passed | testing/logs/logout.txt |\n",
            encoding="utf-8",
        )
        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["test_evidence"]["status"], "complete")
        self.assertEqual(item["test_evidence"]["missing_acceptance"], [])
        self.assertEqual(item["phase"], "completed")

    def test_status_json_has_stable_metadata(self) -> None:
        status = project_status.inspect_project(self.project)
        self.assertEqual(status["schema_version"], "2")
        self.assertRegex(status["generated_at"], r"^20\d\d-")

    def test_strict_validator_reports_duplicate_identifier(self) -> None:
        work = self.managed_work("WORK-016", "严格校验")
        requirements = work / "requirements.md"
        requirements.write_text(
            requirements.read_text(encoding="utf-8")
            + "\n## 目标\n目标\n\n## 验收标准\n- AC-001：一次\n- AC-001：重复\n",
            encoding="utf-8",
        )
        result = project_validate.validate_project(self.project)
        self.assertFalse(result["valid"])
        self.assertTrue(any("AC-001" in error["message"] for error in result["errors"]))

    def test_compact_workflow_skips_optional_design_stages(self) -> None:
        self.confirm_rules()
        work = self.project / ".agent" / "changes" / "WORK-004-快速修复"
        artifact(work / "requirements.md", "requirements", "approved", work="快速修复", work_id="WORK-004", workflow="compact")
        artifact(work / "tasks.md", "tasks", "approved", "### TASK-001 | pending | 修改实现", work="快速修复", work_id="WORK-004")

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["workflow"], "compact")
        self.assertEqual(item["phase"], "implementation")
        self.assertEqual(item["state"], "in_progress")

    def test_lifecycle_mode_compatibility_defaults_from_workflow(self) -> None:
        compact = self.managed_work("WORK-004", "兼容受管理", workflow="compact")
        full = self.managed_work("WORK-005", "兼容严格", workflow="full")

        items = {
            item["work_id"]: item
            for item in project_status.inspect_project(self.project)["work_items"]
        }
        self.assertEqual(items["WORK-004"]["mode"], "managed")
        self.assertEqual(items["WORK-004"]["mode_source"], "workflow 兼容推导")
        self.assertEqual(items["WORK-005"]["mode"], "strict")
        self.assertEqual(items["WORK-005"]["mode_source"], "workflow 兼容推导")

    def test_explicit_lifecycle_mode_and_reason_are_reported(self) -> None:
        self.managed_work(
            "WORK-006",
            "轻量记录",
            mode="lite",
            mode_reason="单文件且不涉及公共行为",
        )

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["mode"], "lite")
        self.assertEqual(item["mode_label"], "轻量")
        self.assertEqual(item["mode_reason"], "单文件且不涉及公共行为")
        self.assertEqual(item["mode_source"], "requirements.md")
        self.assertTrue(item["mode_valid"])

    def test_invalid_mode_and_missing_reason_are_warnings(self) -> None:
        self.managed_work("WORK-007", "非法模式", mode="fast")
        invalid = project_status.inspect_project(self.project)["work_items"][0]
        self.assertFalse(invalid["mode_valid"])
        self.assertTrue(any("mode 必须为 lite、managed 或 strict" in warning for warning in invalid["warnings"]))

        self.temp.cleanup()
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        self.managed_work("WORK-008", "缺少理由", mode="managed")
        missing_reason = project_status.inspect_project(self.project)["work_items"][0]
        self.assertTrue(any("mode_reason" in warning for warning in missing_reason["warnings"]))

    def test_status_and_resume_render_lifecycle_mode(self) -> None:
        self.managed_work("WORK-009", "输出模式", mode="managed", mode_reason="跨对话任务")
        status = project_status.inspect_project(self.project)
        self.assertIn("模式：managed（受管理）", project_status.render_text(status))
        self.assertIn("模式：managed（受管理）", project_status.render_resume(status))

    def test_validate_entry_does_not_force_strict_mode(self) -> None:
        # 命令映射现在只在 project-lifecycle.py：validate 不得自带 --strict。
        entry = LIFECYCLE_ENTRY.read_text(encoding="utf-8")
        self.assertIn('"validate": ("project_validate.py", [])', entry)
        self.assertNotIn('"validate": ("project_validate.py", ["--strict"]', entry)

    def test_strict_validation_is_opt_in_for_compatibility_warnings(self) -> None:
        self.confirm_rules()
        work = self.project / ".agent" / "changes" / "WORK-010-可选严格校验"
        artifact(
            work / "requirements.md",
            "requirements",
            "approved",
            "## 目标\n目标\n\n## 验收标准\n- AC-001：目标可验证\n",
            work="可选严格校验",
            work_id="WORK-010",
            mode="managed",
            workflow="compact",
        )
        artifact(
            work / "tasks.md",
            "tasks",
            "approved",
            "### TASK-001 | pending | 实现目标",
            work="可选严格校验",
            work_id="WORK-010",
        )

        normal = project_validate.validate_project(self.project)
        strict = project_validate.validate_project(self.project, strict=True)
        self.assertTrue(normal["valid"])
        self.assertFalse(strict["valid"])
        self.assertTrue(any("mode_reason" in warning["message"] for warning in normal["warnings"]))

    def test_archive_move_reports_stale_references(self) -> None:
        self.confirm_rules()
        workspace = self.project / ".agent"
        archived = workspace / "changes" / "archive" / "2026-09-01-WORK-011-登录"
        archived.mkdir(parents=True)
        (archived / "requirements.md").write_text("# 登录需求\n", encoding="utf-8")
        (workspace / "INDEX.md").write_text(
            "| 需求 | `.agent/changes/WORK-011-登录/requirements.md` |\n", encoding="utf-8"
        )
        history = workspace / "history"
        history.mkdir(parents=True, exist_ok=True)
        (history / "updates.md").write_text(
            "## 2026-09-01 · WORK-011 · 归档\n\n- 变更：`.agent/changes/WORK-011-登录/` 移入归档。\n",
            encoding="utf-8",
        )

        messages = [warning["message"] for warning in project_validate.validate_project(self.project)["warnings"]]
        self.assertTrue(any("归档前路径" in message and "INDEX.md" in message for message in messages))
        self.assertFalse(any("history" in message for message in messages), messages)

    def test_finished_tasks_move_to_verification(self) -> None:
        work = self.approve_through_tasks("### TASK-001 | done | 实现登录")
        (work / "testing").mkdir()
        (work / "testing" / "plan.md").write_text("# 测试计划\n", encoding="utf-8")

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "verification")
        self.assertEqual(item["state"], "ready")

    def test_unconfirmed_rules_block_implementation(self) -> None:
        self.approve_through_tasks("### TASK-001 | pending | 实现登录")
        (self.project / ".agent" / "rules" / "always.md").unlink()

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "implementation")
        self.assertEqual(item["state"], "blocked")
        self.assertTrue(any("用户确认" in warning for warning in item["warnings"]))

    def test_unconfirmed_rules_allow_read_only_verification_but_not_settlement(self) -> None:
        work = self.approve_through_tasks("### TASK-001 | done | 实现登录")
        plan = work / "testing" / "plan.md"
        plan.parent.mkdir()
        plan.write_text("# 测试计划\n", encoding="utf-8")
        (self.project / ".agent" / "rules" / "always.md").unlink()

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "verification")
        self.assertEqual(item["state"], "ready")
        self.assertTrue(any("只读验证" in warning for warning in item["warnings"]))

        (work / "testing" / "report.md").write_text(
            "# 验证报告\n\n状态：passed\n", encoding="utf-8"
        )
        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "completed")
        self.assertEqual(item["state"], "needs_attention")
        self.assertIn("确认项目常驻规范", item["next_action"])

    def test_passed_report_completes_work(self) -> None:
        work = self.approve_through_tasks("### TASK-001 | done | 实现登录")
        report = work / "testing" / "report.md"
        report.parent.mkdir()
        report.write_text("# 验证报告\n\n状态：passed\n", encoding="utf-8")

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "completed")
        self.assertEqual(item["state"], "complete")

    def test_chinese_name_and_work_id_are_queryable(self) -> None:
        self.managed_work(
            "WORK-003",
            "用户登录",
            task_body="### TASK-001 | pending | 接入登录\n\n### TASK-002 | done | 建立会话",
        )

        status = project_status.inspect_project(self.project, work="用户登录")
        item = status["work_items"][0]
        self.assertEqual(item["work_id"], "WORK-003")
        self.assertEqual(item["name"], "用户登录")
        self.assertEqual(
            {key: item["tasks"][key] for key in ("pending", "in_progress", "done", "blocked")},
            {"pending": 1, "in_progress": 0, "done": 1, "blocked": 0},
        )
        self.assertEqual(item["tasks"]["total"], 2)
        self.assertTrue(item["tasks"]["state_known"])
        self.assertIn("WORK-003 · 用户登录", project_status.render_text(status))

        by_id = project_status.inspect_project(self.project, work="work-003")
        self.assertEqual(by_id["work_items"][0]["name"], "用户登录")

    def test_identity_drift_is_reported(self) -> None:
        work = self.managed_work("WORK-003", "用户登录")
        artifact(
            work / "design.md",
            "design",
            "approved",
            work="账户登录",
            work_id="WORK-009",
        )

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertTrue(any("work_id" in warning for warning in item["warnings"]))
        self.assertTrue(any("中文名称" in warning for warning in item["warnings"]))

    def test_unfinished_hard_dependency_blocks_implementation(self) -> None:
        self.managed_work("WORK-001", "账户基础", requirements_status="draft")
        self.managed_work("WORK-002", "用户登录", depends_on=("WORK-001",))

        status = project_status.inspect_project(self.project)
        items = {item["work_id"]: item for item in status["work_items"]}
        login = items["WORK-002"]
        account = items["WORK-001"]
        self.assertEqual(login["state"], "blocked")
        self.assertIn("WORK-001", login["next_action"])
        self.assertEqual(login["relations"]["depends_on"][0]["name"], "账户基础")
        self.assertEqual(account["relations"]["dependents"][0]["work_id"], "WORK-002")

    def test_soft_relation_is_bidirectional_without_blocking(self) -> None:
        self.managed_work("WORK-001", "账户基础")
        self.managed_work("WORK-002", "权限管理", related_to=("WORK-001",))

        items = {
            item["work_id"]: item
            for item in project_status.inspect_project(self.project)["work_items"]
        }
        self.assertEqual(items["WORK-002"]["state"], "in_progress")
        self.assertEqual(items["WORK-001"]["relations"]["related"][0]["work_id"], "WORK-002")
        self.assertEqual(items["WORK-002"]["relations"]["related"][0]["work_id"], "WORK-001")

    def test_dependency_cycle_blocks_both_work_items(self) -> None:
        self.managed_work("WORK-001", "账户基础", depends_on=("WORK-002",))
        self.managed_work("WORK-002", "用户登录", depends_on=("WORK-001",))

        items = project_status.inspect_project(self.project)["work_items"]
        self.assertTrue(all(item["state"] == "blocked" for item in items))
        self.assertTrue(all(any("形成循环" in warning for warning in item["warnings"]) for item in items))

    def test_self_relation_is_reported(self) -> None:
        self.managed_work(
            "WORK-001",
            "账户基础",
            depends_on=("WORK-001",),
            related_to=("WORK-001",),
        )

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["state"], "blocked")
        self.assertTrue(any("不能依赖自身" in warning for warning in item["warnings"]))
        self.assertTrue(any("不能关联自身" in warning for warning in item["warnings"]))

    def test_archived_completed_dependency_does_not_block(self) -> None:
        foundation = self.managed_work(
            "WORK-001",
            "账户基础",
            task_body="### TASK-001 | done | 完成账户基础",
        )
        report = foundation / "testing" / "report.md"
        report.parent.mkdir()
        report.write_text("# 验证报告\n\n状态：passed\n", encoding="utf-8")
        archive = self.project / ".agent" / "changes" / "archive"
        archive.mkdir()
        foundation.rename(archive / "2026-08-19-WORK-001-账户基础")
        self.managed_work("WORK-002", "用户登录", depends_on=("WORK-001",))

        current = project_status.inspect_project(self.project)
        login = current["work_items"][0]
        self.assertEqual(current["next_work_id"], "WORK-003")
        self.assertEqual(login["work_id"], "WORK-002")
        self.assertEqual(login["state"], "in_progress")
        self.assertTrue(login["relations"]["depends_on"][0]["archived"])

        historical = project_status.inspect_project(self.project, work="账户基础")
        self.assertTrue(historical["work_items"][0]["archived"])


class InitializationTests(unittest.TestCase):
    def test_init_does_not_create_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            init = subprocess.run(
                [sys.executable, "-X", "utf8", str(INIT_SCRIPT), str(project)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertFalse((project / ".agent" / "history").exists())

    def test_existing_project_is_preserved_and_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            agents = project / "AGENTS.md"
            agents.write_text("# 用户原有规则\n", encoding="utf-8")
            source = project / "src" / "app.py"
            source.parent.mkdir()
            source.write_text("VALUE = 1\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(INIT_SCRIPT), str(project)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            rules = project / ".agent" / "rules" / "always.md"
            index = project / ".agent" / "INDEX.md"
            rules.write_text("# 用户自定义项目规范\n\n## MUST\n\n- 保留此规则\n", encoding="utf-8")
            index.write_text("# 用户维护的项目索引\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(INIT_SCRIPT), str(project)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            self.assertEqual(agents.read_text(encoding="utf-8"), "# 用户原有规则\n")
            self.assertEqual(source.read_text(encoding="utf-8"), "VALUE = 1\n")
            self.assertFalse((project / ".agent" / "memory.md").exists())
            self.assertFalse((project / ".agent" / "html").exists())
            self.assertFalse((project / ".agent" / "history").exists())
            self.assertEqual(index.read_text(encoding="utf-8"), "# 用户维护的项目索引\n")
            self.assertEqual(rules.read_text(encoding="utf-8"), "# 用户自定义项目规范\n\n## MUST\n\n- 保留此规则\n")
            # .agent/scripts/ 是留给目标项目自己的辅助脚本；Skill 的脚本不得复制进去，
            # 否则每个项目都会多一份会随 Skill 升级而过期的副本。
            self.assertFalse((project / ".agent" / "scripts" / "project_status.py").exists())

    def test_new_project_explains_lifecycle_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(INIT_SCRIPT), str(project)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("不会写入固定项目规则", result.stdout)
            agents = (project / "AGENTS.md").read_text(encoding="utf-8")
            workspace_readme = (project / ".agent" / "README.md").read_text(encoding="utf-8")
            project_index = (project / ".agent" / "INDEX.md").read_text(encoding="utf-8")
            self.assertIn("project-lifecycle", agents)
            self.assertIn("PROJECT-INDEX.md", agents)
            self.assertIn("references/workflow.md", agents)
            self.assertIn("WORK-*", workspace_readme)
            self.assertIn("阶段批准", workspace_readme)
            self.assertIn("references/workflow.md", workspace_readme)
            self.assertIn("## 模块索引", project_index)
            self.assertIn(".agent/specs/", project_index)
            self.assertIn("project-lifecycle.ps1 status", project_index)
            self.assertNotIn(".agent/scripts/project_status.py", project_index)
            status = project_status.inspect_project(project)
            self.assertFalse((project / ".agent" / "rules" / "always.md").exists())
            self.assertFalse(status["rules"]["ready"])
            self.assertFalse(status["rules"]["configured"])
            self.assertTrue(status["rules"]["confirmation_required"])
            self.assertTrue(any("用户确认" in warning for warning in status["rules"]["warnings"]))


class ApprovalSigningTests(unittest.TestCase):
    """签署：字段只能由 approve 入口盖章，缺失和格式错误分开报告。"""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        rules = self.project / ".agent" / "rules" / "always.md"
        rules.parent.mkdir(parents=True, exist_ok=True)
        rules.write_text(
            "---\nartifact: project_rules\nstatus: active\nconfigured: true\n---\n\n"
            "# 项目常驻规范\n\n## MUST：所有任务\n\n- 运行测试\n",
            encoding="utf-8",
        )
        self.work = self.project / ".agent" / "changes" / "WORK-001-登录超时"
        artifact(
            self.work / "requirements.md",
            "requirements",
            "approved",
            "## 目标\n修复登录超时。\n\n## 验收标准\n- AC-001 会话超时后重新登录成功。\n",
            work="登录超时",
            work_id="WORK-001",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def approve_args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "work": "WORK-001",
            "artifact": "requirements",
            "by": "张三",
            "role": "产品",
            "json": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_approve_stamps_signer(self) -> None:
        self.assertEqual(0, artifacts.approve(self.approve_args(), self.project))
        fields = project_status.frontmatter_fields(
            (self.work / "requirements.md").read_text(encoding="utf-8-sig")
        )
        self.assertEqual("approved", fields["status"])
        self.assertEqual("张三", fields["approved_by"])
        self.assertEqual("产品", fields["approver_role"])
        self.assertTrue(project_status.APPROVED_AT_PATTERN.match(fields["approved_at"]))
        self.assertFalse((self.project / ".agent" / "history").exists())

    def test_approve_records_business_acceptance_only_for_passed_report(self) -> None:
        report = self.work / "testing" / "report.md"
        artifact(report, "test-report", "partial", work="登录超时", work_id="WORK-001")
        with self.assertRaises(RuntimeError):
            artifacts.approve(self.approve_args(artifact="test-report", by="李四"), self.project)
        report.write_text(
            report.read_text(encoding="utf-8").replace("status: partial", "status: passed"),
            encoding="utf-8",
        )
        self.assertEqual(
            0, artifacts.approve(self.approve_args(artifact="test-report", by="李四"), self.project)
        )
        fields = project_status.frontmatter_fields(report.read_text(encoding="utf-8-sig"))
        self.assertEqual("passed", fields["status"])
        self.assertEqual("李四", fields["accepted_by"])
        self.assertTrue(project_status.APPROVED_AT_PATTERN.match(fields["accepted_at"]))

    def test_approve_unknown_work_item_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            artifacts.approve(self.approve_args(work="WORK-999"), self.project)

    def test_unsigned_approval_is_a_compatibility_warning(self) -> None:
        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual("incomplete", item["approval"]["status"])
        self.assertEqual(["requirements"], item["approval"]["unsigned"])
        normal = project_validate.validate_project(self.project)
        self.assertTrue(any("缺少签署记录" in warning["message"] for warning in normal["warnings"]))
        self.assertTrue(normal["valid"])
        self.assertFalse(project_validate.validate_project(self.project, strict=True)["valid"])

    def test_signed_artifact_has_no_approval_warning(self) -> None:
        artifacts.approve(self.approve_args(), self.project)
        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual("complete", item["approval"]["status"])
        self.assertEqual("张三", item["approval"]["artifacts"]["requirements"]["approved_by"])
        messages = [
            warning["message"]
            for warning in project_validate.validate_project(self.project)["warnings"]
        ]
        self.assertFalse(any("签署" in message for message in messages))

    def test_invalid_signature_timestamp_is_an_error(self) -> None:
        path = self.work / "requirements.md"
        text = path.read_text(encoding="utf-8-sig").replace(
            "status: approved", "status: approved\napproved_by: 张三\napproved_at: 昨天下午"
        )
        path.write_bytes(text.encode("utf-8"))
        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual("invalid", item["approval"]["status"])
        result = project_validate.validate_project(self.project)
        self.assertFalse(result["valid"])
        self.assertTrue(any("时间戳格式无效" in error["message"] for error in result["errors"]))

    def test_stamp_preserves_bom_crlf_and_other_keys(self) -> None:
        path = self.work / "requirements.md"
        path.write_bytes(
            b"\xef\xbb\xbf"
            + (
                "---\r\nwork_id: WORK-001\r\nwork: 登录超时\r\nstatus: draft\r\n"
                "updated: 2026-08-19\r\n---\r\n\r\n# 需求\r\n"
            ).encode("utf-8")
        )
        text, bom, newline = artifacts.load_artifact(path)
        stamped = artifacts.stamp_frontmatter(
            text, {"status": "approved", "approved_by": "张三", "approver_role": ""}, newline
        )
        artifacts.save_artifact(path, stamped, bom)
        raw = path.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        fields = project_status.frontmatter_fields(raw.decode("utf-8-sig"))
        self.assertEqual("approved", fields["status"])
        self.assertEqual("2026-08-19", fields["updated"])
        self.assertEqual("WORK-001", fields["work_id"])
        self.assertEqual("张三", fields["approved_by"])


class TraceabilityTests(unittest.TestCase):
    """需求追踪：真实工件里的四种定义写法、区间语法、同行依赖、旧版标记。"""

    def test_expand_trace_ids_handles_ranges_and_plain_ids(self) -> None:
        values = project_status.expand_trace_ids("`REQ-001`、`REQ-004`、`AC-001~AC-003`")
        self.assertEqual(["AC-001", "AC-002", "AC-003", "REQ-001", "REQ-004"], sorted(values))
        # 区间第二段省略前缀也要认
        self.assertEqual(
            ["AC-006", "AC-007", "AC-008", "AC-009"],
            project_status.expand_trace_ids("AC-006~009"),
        )
        # 前缀过滤
        self.assertEqual(["REQ-002"], project_status.expand_trace_ids("`REQ-002`、`TASK-003`", ("REQ",)))
        # 笔误写成超长区间时按 100 截断，不撑爆节点数
        self.assertEqual(100, len(project_status.expand_trace_ids("AC-001~AC-999")))

    def test_trace_definitions_accepts_all_four_writing_styles(self) -> None:
        text = (
            "- **REQ-001 结果上传**：支持两种入口。\n"
            "- **AC-001** 一个真实仓库能端到端跑通：验证对象为 demo。\n"
            "- **AC-002**：粘贴一份合法 JSON，平台正确解析。\n"
            "- REQ-002：建立自动化的模块接缝检查，覆盖全部 36 个模块。\n"
        )
        found = {item["id"]: item["title"] for item in project_status.trace_definitions(text)}
        self.assertEqual("结果上传", found["REQ-001"])
        self.assertEqual("一个真实仓库能端到端跑通", found["AC-001"])
        self.assertEqual("粘贴一份合法 JSON，平台正确解析", found["AC-002"])
        self.assertEqual("建立自动化的模块接缝检查，覆盖全部 36 个模块", found["REQ-002"])

    def make_work(self, tasks_body: str, requirements_body: str = "") -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        work = Path(temp.name) / ".agent" / "changes" / "WORK-001-演示"
        work.mkdir(parents=True)
        (work / "requirements.md").write_text(
            "---\nwork_id: WORK-001\nwork: 演示\nstatus: approved\n---\n\n"
            "## 功能需求\n\n"
            "- **REQ-001 结果上传**：支持两种入口。\n"
            "- **REQ-002 结果展示**：展示接口清单。\n\n"
            "## 验收标准\n\n"
            "- **AC-001**：合法 JSON 可上传并展示。\n"
            "- **AC-002**：失败结果显示修复建议。\n" + requirements_body,
            encoding="utf-8",
        )
        (work / "tasks.md").write_text(
            "---\nwork_id: WORK-001\nwork: 演示\nstatus: approved\n---\n\n"
            "# 演示实施任务\n\n" + tasks_body,
            encoding="utf-8",
        )
        return work

    def trace_of(self, work: Path) -> dict[str, object]:
        coverage = project_status.source_coverage_status(work / "requirements.md")
        evidence = project_status.testing_evidence_status(
            work / "testing" / "report.md",
            project_status.requirement_acceptance_ids(work / "requirements.md"),
        )
        return project_status.traceability_status(work, evidence, coverage)

    def test_traceability_reads_mapping_and_dependencies(self) -> None:
        work = self.make_work(
            "### TASK-001 | done | 项目骨架\n\n- 对应：基础设施\n- 依赖：无\n\n"
            "### TASK-002 | done | 上传 API\n\n- 对应：旧版 `REQ-001`、`AC-001~AC-002`\n- 依赖：`TASK-001`\n\n"
            "### TASK-003 | pending | 前端\n\n- 对应：`REQ-002`；依赖：`TASK-002`、`TASK-003`\n"
        )
        trace = self.trace_of(work)
        self.assertEqual(["REQ-001", "REQ-002"], [item["id"] for item in trace["requirements"]])
        self.assertEqual(["AC-001", "AC-002"], [item["id"] for item in trace["acceptance"]])
        tasks = {task["id"]: task for task in trace["tasks"]}
        # 没有写 id 的任务算未映射，不是错误
        self.assertEqual([], tasks["TASK-001"]["maps_to"])
        self.assertEqual(["TASK-001"], trace["unmapped_tasks"])
        self.assertEqual(["REQ-001", "AC-001", "AC-002"], tasks["TASK-002"]["maps_to"])
        self.assertEqual(["REQ-001", "AC-001", "AC-002"], tasks["TASK-002"]["legacy"])
        self.assertEqual(["TASK-001"], tasks["TASK-002"]["depends_on"])
        # 同行写法和独立写法都要取到依赖；自引用要被剔除
        self.assertEqual(["REQ-002"], tasks["TASK-003"]["maps_to"])
        self.assertEqual(["TASK-002"], tasks["TASK-003"]["depends_on"])
        self.assertEqual([], tasks["TASK-003"]["legacy"])

    def test_traceability_reports_undefined_refs_and_evidence_gaps(self) -> None:
        work = self.make_work("### TASK-001 | done | 上传\n\n- 对应：`REQ-009`\n- 依赖：无\n")
        trace = self.trace_of(work)
        # 引用了不存在的需求要报出来，而不是静默丢掉
        self.assertEqual(["REQ-009"], trace["undefined_refs"])
        # 报告不存在时所有验收标准都没有结构化证据
        self.assertEqual(["AC-001", "AC-002"], trace["acceptance_without_evidence"])
        self.assertEqual([], trace["requirement_acceptance_links"])

    def test_requirement_acceptance_links_come_only_from_coverage_table(self) -> None:
        work = self.make_work(
            "### TASK-001 | done | 上传\n\n- 对应：`REQ-001`\n",
            requirements_body=(
                "\nsource_coverage: required\n\n## 来源覆盖\n\n"
                "| 来源 | 锚点 | REQ | AC | 状态 |\n| --- | --- | --- | --- | --- |\n"
                "| PRD.md | 第 1 节 | REQ-001、REQ-002 | AC-001 | verified |\n"
            ),
        )
        # frontmatter 里没有 source_coverage: required 时不该产出直连边
        self.assertEqual([], self.trace_of(work)["requirement_acceptance_links"])

        path = work / "requirements.md"
        text = path.read_text(encoding="utf-8").replace(
            "status: approved", "status: approved\nsource_coverage: required"
        )
        path.write_text(text, encoding="utf-8")
        trace = self.trace_of(work)
        self.assertEqual(
            [["REQ-001", "AC-001"], ["REQ-002", "AC-001"]],
            trace["requirement_acceptance_links"],
        )


if __name__ == "__main__":
    unittest.main()
