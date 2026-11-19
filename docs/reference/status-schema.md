# status JSON 契约（schema_version = "2"）

`$lifecycle status --json`（以及 `$lifecycle brief --json`）输出的对象是**公共契约**：
桌面查看器 `desktop/src/main.ts` 按 D-007 直接消费它并渲染，其他脚本也会据此判断阶段。
因此这里记录的字段集合由 `tests/test_status_contract.py` 固化——**增删字段必须同步改这个测试和本文档**。

当前 `schema_version`：`"2"`。字段示例与含义如下（值为只读快照，随项目状态变化）。

## 顶层字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `schema_version` | string | JSON 结构版本，当前 `"2"`；结构变更时递增 |
| `generated_at` | string | 生成时间（ISO 8601） |
| `initialized` | bool | 目标项目是否已初始化出 `.agent/` |
| `state` | string | 项目整体状态（如 `uninitialized` / `active` / `idle`） |
| `project_root` | string | 目标项目根目录绝对路径 |
| `next_work_id` | string | 建议的下一个工作项编号，如 `WORK-012` |
| `next_action` | string | 面向人的下一步建议 |
| `warnings` | string[] | 项目级警告（不影响结构，仅提示） |
| `scope` | object | 当前查询范围（含 `work` / `slug` 等过滤信息） |
| `catalog` | object | 全部工作项的精简目录（id/title/state 等），供列表导航 |
| `rules` | object | 项目常驻规则（`rules/always.md`）的生效状态 |
| `git` | object | Git 工作区状态（分支、tracking、dirty 计数、逐文件归属） |
| `resume` | object | 恢复上下文：`mode`（如 `auto_resume`）、可恢复项、阻塞原因、续接路径 |
| `workspace` | object | 工作区归属与并发提示 |
| `work_items` | object[] | 工作项数组，每项字段见下节 |

## work-item 字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `work_id` | string | 工作项编号 `WORK-###` |
| `slug` / `name` | string | 目录 slug / 人类可读名 |
| `directory` / `path` | string | 工作项目录 |
| `archived` | bool | 是否已归档 |
| `phase` / `phase_label` | string | 阶段（如 `implementation`）与中文标签 |
| `state` / `state_label` | string | 状态（如 `in_progress`）与中文标签 |
| `next_action` | string | 该工作项的下一步建议 |
| `workflow` | string | 工作流档位 `full` / `compact` |
| `mode` / `mode_label` / `mode_raw` / `mode_source` / `mode_valid` / `mode_reason` | string/bool | 风险模式（`lite`/`managed`/`strict`）的解析结果与来源 |
| `approval` | object | 各工件的签署状态（requirements/proposal/design/tasks/testing） |
| `artifacts` | object | 各工件路径与状态 |
| `source_coverage` | object | 需求来源覆盖检查结果 |
| `test_evidence` | object | 验证报告证据矩阵结果 |
| `traceability` | object | REQ/AC/任务的可追溯性 |
| `tasks` | object | 任务统计（总数、各状态计数、warnings） |
| `document_budget` | object | 文档体积预算检查 |
| `relations` | object | `depends_on` / `dependents` / `related` 关系 |
| `depends_on_ids` / `related_to_ids` | string[] | 依赖 / 相关的工作项编号 |
| `workspace_attribution` | object | 本工作项相对 Git 工作的归属判定 |
| `state_evidence` | object | 支撑当前状态判定的证据 |
| `hygiene` / `advice` | string[] | 可读性整理项 / 计划质量建议（不阻断恢复） |
| `warnings` | string[] | 该工作项的警告 |

## 变更流程

1. 改 `scripts/project_status.py` 的输出结构（新增/改名/删除字段）。
2. 同步更新 `tests/test_status_contract.py` 的 `TOP_LEVEL_KEYS` / `WORK_ITEM_KEYS`。
3. 同步更新本文档。
4. 若是不兼容变更（删字段、改类型），递增 `STATUS_SCHEMA_VERSION` 并检查 `desktop/` 渲染代码。
