#!/usr/bin/env python3
"""status --json 的字段契约测试（schema_version = "2"）。

桌面查看器 desktop/src/main.ts 按 D-007 直接渲染本 JSON，所以「顶层键集合」与
「work-item 键集合」是公开契约：新增/删除字段必须同步更新本测试与
docs/reference/status-schema.md，否则下游（桌面/脚本）可能静默拿到缺失字段。
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "project-lifecycle"
STATUS_SCRIPT = SKILL_ROOT / "scripts" / "project_status.py"

# 顶层字段（schema_version = "2"）。缺失或改名会让桌面查看器/JSON 消费者读不到。
TOP_LEVEL_KEYS = {
    "catalog",
    "generated_at",
    "git",
    "initialized",
    "next_action",
    "next_work_id",
    "project_root",
    "resume",
    "rules",
    "schema_version",
    "scope",
    "state",
    "warnings",
    "work_items",
    "workspace",
}

# 单个 work-item 的字段（schema_version = "2"）。
WORK_ITEM_KEYS = {
    "advice",
    "approval",
    "archived",
    "artifacts",
    "depends_on_ids",
    "directory",
    "document_budget",
    "hygiene",
    "mode",
    "mode_label",
    "mode_raw",
    "mode_reason",
    "mode_source",
    "mode_valid",
    "name",
    "next_action",
    "path",
    "phase",
    "phase_label",
    "related_to_ids",
    "relations",
    "slug",
    "source_coverage",
    "state",
    "state_evidence",
    "state_label",
    "tasks",
    "test_evidence",
    "traceability",
    "warnings",
    "work_id",
    "workflow",
    "workspace_attribution",
}


def load_status_module():
    spec = importlib.util.spec_from_file_location("project_status", STATUS_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 project_status.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


project_status = load_status_module()


def build_project(root: Path) -> None:
    """构造一个含单个 work-item 的最小项目，足以触发完整 status 结构。"""
    rules = root / ".agent" / "rules" / "always.md"
    rules.parent.mkdir(parents=True, exist_ok=True)
    rules.write_text(
        "---\nartifact: project_rules\nstatus: active\nconfigured: true\n---\n\n"
        "# 规则\n\n- 运行测试\n",
        encoding="utf-8",
    )
    work = root / ".agent" / "changes" / "WORK-001-测试"
    work.mkdir(parents=True, exist_ok=True)
    (work / "requirements.md").write_text(
        "---\nwork_id: WORK-001\nwork: 测试\nartifact: requirements\n"
        "status: approved\nworkflow: full\nupdated: 2026-08-19\n---\n\n"
        "# 需求\n\n## 验收标准\n\n- AC-001 能登录\n",
        encoding="utf-8",
    )


class StatusContractTest(unittest.TestCase):
    def test_status_schema_version_and_keys_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            build_project(project)
            status = project_status.inspect_project(project)

            self.assertEqual(status["schema_version"], "2")
            self.assertEqual(set(status), TOP_LEVEL_KEYS, "顶层字段集合变化，请同步 status-schema.md")

            items = status["work_items"]
            self.assertEqual(len(items), 1, "夹具应产生一个 work-item")
            self.assertEqual(set(items[0]), WORK_ITEM_KEYS, "work-item 字段集合变化，请同步 status-schema.md")


if __name__ == "__main__":
    unittest.main()
