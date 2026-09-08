---
layout: home

hero:
  name: Project Lifecycle
  text: 把项目做成可恢复的流程
  tagline: 从需求讨论、方案和设计，到实现、验证与跨会话接力，所有关键事实都留在项目里。
  actions:
    - theme: brand
      text: 开始全流程教程
      link: /guide/getting-started
    - theme: alt
      text: 我已经有工作项
      link: /guide/resume

features:
  - title: 按风险选择流程
    details: 小修复走短路径，跨模块、公共接口、数据、安全和架构工作走完整工作项。
    link: /guide/getting-started
  - title: 每一步都有事实依据
    details: 需求、批准、任务、测试和阻塞写入 .agent/，不用依赖旧聊天记录。
    link: /guide/full-workflow
  - title: 换个对话也能继续
    details: 用 WORK-* 和恢复探针重新定位工作项，先处理 Git 归因，再继续当前阶段。
    link: /guide/resume
  - title: 先把需求问透
    details: 需要详细调查时，按决策树逐轮确认关键选择，再生成 PRD 和任务计划。
    link: /guide/requirements-interview
---

## 这套教程适合谁

如果你希望 Agent 能在几天后、换一个对话后，仍然知道“这项工作做到哪一步、为什么还不能继续、下一步要读什么”，就从这里开始。

教程默认以 Windows PowerShell 命令示例说明；Skill 本身只依赖 Python 标准库，其他系统只需替换路径写法。

## 最短入口

1. 安装 `project-lifecycle` Skill。
2. 对项目运行初始化器。
3. 确认项目常驻规则。
4. 用自然语言讨论需求，或用 `WORK-*` 恢复已有工作。

下一步阅读：[开始使用](/guide/getting-started)，或者先看[总索引](/reference/)了解每个模块应该改哪里、到哪里查看。
