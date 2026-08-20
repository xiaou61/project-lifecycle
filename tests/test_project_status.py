from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_SCRIPT = ROOT / "scripts" / "project_status.py"
INIT_SCRIPT = ROOT / "scripts" / "init_project.py"


def load_status_module():
    spec = importlib.util.spec_from_file_location("project_status", STATUS_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 project_status.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


project_status = load_status_module()


def artifact(
    path: Path,
    kind: str,
    status: str,
    body: str = "",
    *,
    work: str = "login",
    work_id: str | None = None,
    depends_on: tuple[str, ...] = (),
    related_to: tuple[str, ...] = (),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    identity = f"work_id: {work_id}\n" if work_id else ""
    relations = ""
    if kind == "requirements":
        relations = (
            f"depends_on: [{', '.join(depends_on)}]\n"
            f"related_to: [{', '.join(related_to)}]\n"
        )
    path.write_text(
        f"---\n{identity}work: {work}\nartifact: {kind}\nstatus: {status}\n"
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

    def approve_through_tasks(self, task_body: str = "") -> Path:
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
        task_body: str = "### TASK-001 | pending | 实现需求",
        depends_on: tuple[str, ...] = (),
        related_to: tuple[str, ...] = (),
    ) -> Path:
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
                depends_on=depends_on,
                related_to=related_to,
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

    def test_finished_tasks_move_to_verification(self) -> None:
        work = self.approve_through_tasks("### TASK-001 | done | 实现登录")
        (work / "testing").mkdir()
        (work / "testing" / "plan.md").write_text("# 测试计划\n", encoding="utf-8")

        item = project_status.inspect_project(self.project)["work_items"][0]
        self.assertEqual(item["phase"], "verification")
        self.assertEqual(item["state"], "ready")

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
            rules.write_text("# 用户自定义项目规范\n\n## MUST\n\n- 保留此规则\n", encoding="utf-8")
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
            self.assertEqual(rules.read_text(encoding="utf-8"), "# 用户自定义项目规范\n\n## MUST\n\n- 保留此规则\n")
            self.assertTrue((project / ".agent" / "scripts" / "generate_core_history.py").is_file())

    def test_new_project_explains_natural_language_workflow(self) -> None:
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
            agents = (project / "AGENTS.md").read_text(encoding="utf-8")
            workspace_readme = (project / ".agent" / "README.md").read_text(encoding="utf-8")
            rules = (project / ".agent" / "rules" / "always.md").read_text(encoding="utf-8")
            self.assertIn("自然语言", agents)
            self.assertIn("当前 / 本次 / 下一步", agents)
            self.assertIn("用户点名 `WORK-*`", agents)
            self.assertIn("接力", agents)
            self.assertIn("自然语言", workspace_readme)
            self.assertIn("跨对话接力", workspace_readme)
            self.assertIn("继续实施 WORK-003", workspace_readme)
            self.assertIn("MUST / SHOULD / MAY", rules)
            self.assertIn("上下文压缩", rules)
            status = project_status.inspect_project(project)
            self.assertTrue(status["rules"]["ready"])
            self.assertFalse(status["rules"]["configured"])
            self.assertTrue(status["rules"]["notices"])


if __name__ == "__main__":
    unittest.main()
