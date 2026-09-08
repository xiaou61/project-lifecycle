# 需求深挖访谈

当一个想法涉及多个模块、用户流程或关键取舍时，可以先让 Agent “把需求问透”。这是需求阶段的可选模式，不会把每个小修复都变成长问卷。

## 怎么触发

可以直接说：

```text
$project-lifecycle 把这个需求问透，确认后再生成 PRD 和 Task。
```

也可以说“详细调查这个需求”或“先访谈再生成 PRD/Task”。Agent 会先读取项目规则、状态、源码和已有资料，再询问代码无法代替用户决定的问题。

## 流程图

<div class="interview-flow" role="img" aria-label="需求深挖访谈流程">
  <div class="flow-node fact"><span>1</span><strong>调查事实</strong><small>规则、源码、接口、测试、资料</small></div>
  <div class="flow-arrow" aria-hidden="true">→</div>
  <div class="flow-node decision"><span>2</span><strong>建立决策树</strong><small>只保留会改变交付结果的选择</small></div>
  <div class="flow-arrow" aria-hidden="true">→</div>
  <div class="flow-node ask"><span>3</span><strong>逐轮提问</strong><small>一次一个问题，给出推荐和影响</small></div>
  <div class="flow-arrow" aria-hidden="true">→</div>
  <div class="flow-node record"><span>4</span><strong>同步 PRD</strong><small>立即记录决定，保留阻塞问题</small></div>
  <div class="flow-arrow" aria-hidden="true">→</div>
  <div class="flow-node confirm"><span>5</span><strong>最终确认</strong><small>确认后才进入 compact 或 full 流程</small></div>
</div>

对应的可编辑 draw.io 源文件：[需求深挖访谈架构图](https://github.com/xiaou61/project-lifecycle/blob/main/output/project-lifecycle-requirements-interview.drawio)。

## Agent 会问什么

只问会改变交付边界的问题：

- 谁在什么场景触发功能，成功结果是什么；
- 本次包含什么，明确不包含什么，是否需要拆成多个工作项；
- 主流程、异常流程、权限和安全边界是什么；
- 数据归谁、是否持久化、是否涉及外部集成或公共接口；
- 兼容性、性能、部署、迁移和回滚有哪些硬约束；
- 验收时能观察到什么结果，哪些测试证据算通过。

代码、配置或测试可以直接回答的内容由 Agent 调查，不会反过来让用户填写。

## 共享词汇和具体场景

如果一个业务词有多个叫法，或同一个词在项目里可能代表不同概念，Agent 会先提出候选定义，再用具体的“触发条件 → 用户可见结果”场景检查边界。确认后的业务词可以写入 `requirements.md` 的“术语与边界”，实现名称不会被当成业务术语。

如果源码、稳定规格和你的描述互相矛盾，Agent 会先指出冲突，暂停受影响的决策，避免把错误理解带进 PRD。

## 每一轮怎么进行

1. Agent 先简短复述已确认结论。
2. 只提出一个当前最重要的问题，通常给出 2-4 个具体选项和自定义回答入口。
3. 你回答后，结论会写入当前工作项的 `requirements.md`，对应问题从待确认列表移除。
4. Agent 重新计算决策树，再进入下一轮。

因此，换对话后可以从 `WORK-*` 恢复，不需要重新讲一遍已经确认的内容。

## 什么时候结束

当没有待调查事实、没有可提问的决策节点、目标和验收标准都已写入 PRD，且没有阻塞问题时，Agent 会给出最终摘要。你明确确认摘要后，需求才会变成 `approved`。

## PRD 和 Task 的关系

`requirements.md` 就是本项目的 PRD，不再复制一份内容相同的 `prd.md`。

| 流程 | 访谈确认后的动作 |
| --- | --- |
| `compact` | 生成 `tasks.md` 草稿，等待你确认任务计划 |
| `full` | 先生成并确认 `proposal.md`，再完成 `design.md`，最后拆 `tasks.md` |

“访谈结束”“继续”“开始做”都不等于批准任务，也不会绕过方案、设计或安全门槛。后续如果新增目标、接口、数据、安全、部署或架构要求，会回到最早受影响阶段。

任务计划确认时，Agent 会优先把工作拆成可独立演示或验证的纵向切片，并列出每项真正的阻塞关系。只有一次机械重构无法切片时，才采用“扩展旧形式 → 分批迁移 → 删除旧形式”的顺序。

<style>
.interview-flow { display: flex; align-items: stretch; gap: 10px; margin: 24px 0 30px; overflow-x: auto; padding: 4px 2px 12px; }
.flow-node { min-width: 150px; flex: 1; padding: 14px; border: 1px solid var(--vp-c-divider); border-radius: 8px; background: var(--vp-c-bg-soft); }
.flow-node span { display: block; color: var(--vp-c-text-2); font-size: 12px; margin-bottom: 8px; }
.flow-node strong, .flow-node small { display: block; }
.flow-node strong { color: var(--vp-c-text-1); margin-bottom: 6px; }
.flow-node small { color: var(--vp-c-text-2); line-height: 1.45; }
.flow-node.fact { border-top: 3px solid #2f855a; }
.flow-node.decision { border-top: 3px solid #805ad5; }
.flow-node.ask { border-top: 3px solid #dd6b20; }
.flow-node.record { border-top: 3px solid #3182ce; }
.flow-node.confirm { border-top: 3px solid #d53f8c; }
.flow-arrow { display: grid; place-items: center; color: var(--vp-c-text-3); font-size: 22px; }
@media (max-width: 720px) { .interview-flow { align-items: center; } .flow-node { min-width: 180px; } }
</style>
