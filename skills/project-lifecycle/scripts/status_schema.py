#!/usr/bin/env python3
"""project_status 的常量定义（schema_version、阶段/状态标签、追踪与任务正则、文档体积预算）。

从 project_status.py 抽出，作为单一事实源；project_status 与 status_parsing 都从这里导入。
"""

from __future__ import annotations

import re


ARTIFACTS = ("requirements", "proposal", "design", "tasks")
PHASE_LABELS = {
    "requirements": "需求讨论",
    "proposal": "方案选择",
    "design": "详细设计",
    "tasks": "实施计划",
    "implementation": "开发实现",
    "verification": "测试验收",
    "completed": "完成沉淀",
}
STATE_LABELS = {
    "not_started": "尚未开始",
    "draft": "草稿",
    "awaiting_approval": "等待确认",
    "stale": "需要修订",
    "needs_attention": "需要处理",
    "ready": "可以开始",
    "in_progress": "进行中",
    "blocked": "已阻塞",
    "partial": "部分通过",
    "failed": "未通过",
    "complete": "已完成",
}
WORK_ID_PATTERN = re.compile(r"WORK-\d+", re.IGNORECASE)
WORKFLOW_MODES = {"full", "compact"}
LIFECYCLE_MODES = {"lite", "managed", "strict"}
MODE_LABELS = {"lite": "轻量", "managed": "受管理", "strict": "严格"}
STATUS_SCHEMA_VERSION = "2"
# 已批准工件的签署时间戳格式；接受 `2026-09-20 14:32:07 +0800`、ISO 和纯日期。
APPROVED_AT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?: ?[+-]\d{4}|Z)?)?$"
)
# 需求追踪：`REQ-001`、`AC-006~AC-009`（第二段可省略前缀）、四种定义写法、任务行
# 单次扫描的引用模式：区间和单个 id 一起匹配，这样结果顺序与原文一致。
TRACE_REF_PATTERN = re.compile(
    r"\b(REQ|AC|TASK)-(\d+)\s*(?:[~～]\s*(?:[A-Za-z]+-)?(\d+))?", re.IGNORECASE
)
# 定义写法在真实项目里有四种，粗体可有可无，所以先取列表项、再从行首取 id。
TRACE_LIST_ITEM_PATTERN = re.compile(r"^\s*[-*]\s+(.*?)\s*$", re.MULTILINE)
TRACE_ID_AT_START = re.compile(r"^(?:\*\*)?(REQ|AC)-(\d+)\b(.*)$", re.IGNORECASE)
TRACE_TASK_PATTERN = re.compile(
    r"^###\s+(TASK-\d+)\s*\|\s*([a-z_]+)\s*\|\s*(.*)$", re.IGNORECASE | re.MULTILINE
)
DOCUMENT_LIMITS = {
    "per_file_bytes": 20_000,
    "work_item_bytes": 80_000,
    "file_count": 6,
}
