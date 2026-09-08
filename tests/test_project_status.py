from __future__ import annotations

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
UPDATE_SCRIPT = SKILL_ROOT / "scripts" / "update_history.py"


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


def load_update_module():
    spec = importlib.util.spec_from_file_location("update_history", UPDATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 update_history.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["project_status"] = project_status
    spec.loader.exec_module(module)
    return module


update_history = load_update_module()


def artifact(
    path: Path,
    kind: str,
    status: str,
    body: str = "",
    *,
    work: str = "login",
    work_id: str | None = None,
    workflow: str | None = None,
    depends_on: tuple[str, ...] = (),
    related_to: tuple[str, ...] = (),
    source_coverage: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    identity = f"work_id: {work_id}\n" if work_id else ""
    relations = ""
    workflow_field = f"workflow: {workflow}\n" if kind == "requirements" and workflow else ""
    source_coverage_field = "source_coverage: required\n" if kind == "requirements" and source_coverage else ""
    if kind == "requirements":
        relations = (
            f"depends_on: [{', '.join(depends_on)}]\n"
            f"related_to: [{', '.join(related_to)}]\n"
        )
    path.write_text(
        f"---\n{identity}work: {work}\nartifact: {kind}\nstatus: {status}\n{workflow_field}{source_coverage_field}"
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

    def test_resume_context_requires_selection_for_multiple_active_work_items(self) -> None:
        self.managed_work("WORK-011", "恢复登录")
        self.managed_work("WORK-012", "恢复权限")

        resume = project_status.inspect_project(self.project)["resume"]
        self.assertEqual(resume["mode"], "ask_user")
        self.assertEqual({item["work_id"] for item in resume["candidates"]}, {"WORK-011", "WORK-012"})

    def test_dirty_git_workspace_requires_attribution_before_resume(self) -> None:
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
        self.assertEqual(status["git"]["attribution"], "unclassified")
        self.assertEqual(status["resume"]["mode"], "ask_user")
        self.assertTrue(any("归因" in blocker for blocker in status["resume"]["blockers"]))

    def test_workspace_attribution_completes_resume(self) -> None:
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
        self.assertEqual(status["work_items"][0]["workspace_attribution"]["status"], "complete")
        self.assertEqual(status["resume"]["mode"], "auto_resume")

    def test_unknown_workspace_attribution_still_blocks_resume(self) -> None:
        self.managed_work("WORK-014", "未知归因")
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
        work = self.project / ".agent" / "changes" / "WORK-014-未知归因"
        (work / "workspace.md").write_text(
            f"---\nbase_commit: {status['git']['head']}\n---\n\n## 工作区归因\n\n"
            "| 路径 | 归属 | 说明 |\n| --- | --- | --- |\n"
            "| src/login.py | unknown | 等待确认 |\n",
            encoding="utf-8",
        )
        status = project_status.inspect_project(self.project)
        self.assertEqual(status["work_items"][0]["workspace_attribution"]["status"], "incomplete")
        self.assertEqual(status["resume"]["mode"], "ask_user")

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
        self.assertEqual(status["schema_version"], "1")
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
        self.assertEqual(item["tasks"], {"pending": 1, "in_progress": 0, "done": 1, "blocked": 0})
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
    def test_update_history_record_and_list(self) -> None:
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
            record = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(UPDATE_SCRIPT),
                    str(project),
                    "--record",
                    "--work",
                    "WORK-001",
                    "--title",
                    "记录一次变更",
                    "--change",
                    "修改实现",
                    "--decision",
                    "复用现有入口",
                    "--basis",
                    ".agent/changes/WORK-001/tasks.md",
                    "--verification",
                    "单元测试通过",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(record.returncode, 0, record.stderr)
            history = (project / ".agent" / "history" / "updates.md").read_text(encoding="utf-8")
            self.assertIn("WORK-001 · 记录一次变更", history)
            self.assertIn("本地提交：待用户授权/未提交", history)
            listed = subprocess.run(
                [sys.executable, "-X", "utf8", str(UPDATE_SCRIPT), str(project), "--list", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(len(json.loads(listed.stdout)["entries"]), 1)

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
            self.assertTrue((project / ".agent" / "memory.md").is_file())
            self.assertTrue((project / ".agent" / "html").is_dir())
            self.assertTrue((project / ".agent" / "history" / "updates.md").is_file())
            self.assertEqual(index.read_text(encoding="utf-8"), "# 用户维护的项目索引\n")
            self.assertEqual(rules.read_text(encoding="utf-8"), "# 用户自定义项目规范\n\n## MUST\n\n- 保留此规则\n")
            self.assertTrue((project / ".agent" / "scripts" / "generate_core_history.py").is_file())

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
            self.assertIn(".agent/html/", project_index)
            self.assertIn("project-lifecycle.ps1 status", project_index)
            self.assertNotIn(".agent/scripts/project_status.py", project_index)
            update_history = project / ".agent" / "history" / "updates.md"
            self.assertIn("artifact: update-history", update_history.read_text(encoding="utf-8"))
            self.assertIn("本地提交", update_history.read_text(encoding="utf-8"))
            status = project_status.inspect_project(project)
            self.assertFalse((project / ".agent" / "rules" / "always.md").exists())
            self.assertFalse(status["rules"]["ready"])
            self.assertFalse(status["rules"]["configured"])
            self.assertTrue(status["rules"]["confirmation_required"])
            self.assertTrue(any("用户确认" in warning for warning in status["rules"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
