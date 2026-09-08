# Work Identity And Relationships

创建工作项、查询状态或判断两个需求是否互相影响时读取本参考。

## Stable Identity And Name

每个受管理需求有两个不同用途的标识：

- `work_id`：稳定的机器标识，如 `WORK-003`，用于关系和查询，不能复用。
- `work`：用户可读的简短中文名称，如 `用户登录`，贯穿讨论、设计、实现和验收。

新需求首次讨论时：

1. 先提出结果导向的中文名称；只有存在两个实质不同的解释时才询问名称。
2. 运行 `scripts/project_status.py <project-root> --json`，使用返回的 `next_work_id`，不要从可见活动列表猜编号。
3. 立即创建 `.agent/changes/WORK-003-用户登录/requirements.md`，写入用户原始目标和当前问题。
4. 所有工件复用同一 `work_id` 和 `work`；状态中优先显示中文名，存在歧义时补充编号。

目录名必须兼容文件系统；不要使用保留字符、尾部空格/句点或“新需求”等泛名。已持久化工作项不静默改名；用户改变含义时保留编号并按漂移规则处理。

新陈述如果仍服务同一结果，就更新当前工作项；能独立批准、交付和验收时才创建新工作项。无法判断时只问一个聚焦问题。

## Artifact Frontmatter

```yaml
---
work_id: WORK-003
work: 用户登录
artifact: requirements | proposal | design | tasks | test-plan | test-report
status: draft | approved | stale
depends_on: [WORK-001]
related_to: [WORK-002]
updated: YYYY-MM-DD
---
```

`depends_on` 与 `related_to` 只写在 `requirements.md`；测试报告使用自己的验证状态。旧工件缺少 `work_id` 时保持兼容，不做只改元数据的迁移。

## Relationship Types

| 类型 | 含义 | 流程影响 |
| --- | --- | --- |
| `depends_on` | 没有另一个工作项的结果就不能正确实现或验收 | 实现前硬阻塞，状态查询显示未完成依赖 |
| `related_to` | 共享行为、契约、模块、数据或决策，但可独立交付 | 不阻塞；跨阶段前检查影响 |

关系引用 `WORK-*` 而非名称或路径。依赖是单向的；关联概念上对称，状态检查器会解析反向关系。Agent 根据活动工作项和稳定规格提出关系与理由，用户可在批准前修正；在 `requirements.md` 的 `## 关联工作项` 说明连接的契约、模块或验收。

## Link Or Merge

按以下顺序判断：

1. 同一结果或不能独立批准/验收：合并范围，不伪造依赖图。
2. 一个必须等待另一个的具体结果：分开并使用 `depends_on`。
3. 可独立交付但共享行为或所有权：使用 `related_to`。
4. 只有文件重叠而无共享行为或决策：不建立关系。

已批准工作不能自动合并；报告重叠并保留被淘汰工作项的历史。

## Impact And Drift

批准、实现或验证有关系的工作项前：

1. 查询出向和入向关系，比较共享需求、规格、接口、数据、安全约束、路径和验收。
2. 若当前变更影响另一活动工作项依赖的事实，将对方最早受影响工件退回 `draft`，下游标为 `stale`。
3. 若无实质影响，在当前 proposal、design 或验证报告中简要记录结论，不因“有关联”而修改对方。

依赖环是无效状态：合并无法独立验收的工作，或抽出共同前置工作项；环未解除前不得实现。共享长期契约放 `.agent/specs/`，工作项只引用它，不复制全文。
