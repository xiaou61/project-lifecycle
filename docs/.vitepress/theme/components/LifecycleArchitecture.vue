<script setup lang="ts">
import { computed, ref } from 'vue'

type Node = {
  id: string
  step: string
  title: string
  eyebrow: string
  summary: string
  input: string
  process: string[]
  output: string
  guard: string
  owner: string
  files: string[]
  link: string
  color: string
}

const nodes: Node[] = [
  {
    id: 'request', step: '01', title: '用户请求', eyebrow: '入口层',
    summary: '自然语言描述目标，Agent 先识别意图与风险。',
    input: '“我想加一个功能”“继续 WORK-003”“测试一下”',
    process: ['判断是讨论、恢复、实现、验证还是状态查询', '识别是否涉及跨会话、多人协作或明显风险'],
    output: '动作类型 + 目标项目 + 可能的工作项', guard: '单文件、低风险、边界清楚的小修复可走短路径。',
    owner: 'SKILL.md', files: ['skills/project-lifecycle/SKILL.md'], link: '/guide/getting-started', color: '#14b8a6'
  },
  {
    id: 'route', step: '02', title: '风险路由', eyebrow: '决策层',
    summary: '决定是否创建 WORK-*，以及使用 compact 还是 full 流程。',
    input: '目标、影响范围、用户可见行为、风险类型',
    process: ['小修复 → 确认目标 → 修改 → 窄验证', '普通功能 → WORK-* + compact', '跨模块/接口/数据/安全/架构 → full'],
    output: '流程模式 + 是否创建持久化工件', guard: '不能为了形式把小修复包装成完整工作项。',
    owner: 'workflow.md', files: ['skills/project-lifecycle/SKILL.md', 'skills/project-lifecycle/references/workflow.md'], link: '/guide/full-workflow', color: '#22c55e'
  },
  {
    id: 'restore', step: '03', title: '恢复事实', eyebrow: '恢复层',
    summary: '先定位真实项目，再从规则、状态和 Git 归因恢复上下文。',
    input: '项目路径、PROJECT-INDEX.md、WORK-*（可选）',
    process: ['读取 AGENTS 与 .agent/rules/always.md', '运行 project_status.py --json 与 --resume --json', '检查工作区改动是否已归因'],
    output: '当前阶段、阻塞、建议读取路径、接力提示', guard: '多工作项、未知归因、规则未确认或漂移时返回 ask_user。',
    owner: 'project_status.py', files: ['skills/project-lifecycle/scripts/project_status.py', '.agent/INDEX.md', '.agent/rules/always.md'], link: '/guide/resume', color: '#3b82f6'
  },
  {
    id: 'interview', step: '04', title: '需求深挖', eyebrow: '需求层 · 可选',
    summary: '只追问会改变交付结果的用户决策，不让用户填写实现细节。',
    input: '待确认目标、范围、行为、约束和验收',
    process: ['区分事实、用户决定、Agent 实现选择', '建立最小决策树，一轮只问一个问题', '每次回答立即写入 requirements.md'],
    output: '稳定术语、用户决定、无阻塞的需求摘要', guard: '访谈完成不等于批准；必须由用户确认最终摘要。',
    owner: 'requirements-interview.md', files: ['skills/project-lifecycle/references/requirements-interview.md', '.agent/changes/WORK-*/requirements.md'], link: '/guide/requirements-interview', color: '#a855f7'
  },
  {
    id: 'artifacts', step: '05', title: '阶段工件', eyebrow: '事实层',
    summary: '把需求、方案、设计、任务和测试证据写进项目，而不是留在聊天里。',
    input: '已确认的范围、来源、约束、关系和验收标准',
    process: ['requirements.md：目标、范围、REQ/AC、来源覆盖', 'proposal.md / design.md：方案与技术边界', 'tasks.md：纵向切片、依赖、任务状态'],
    output: '可批准、可恢复、可验证的项目事实', guard: '每个阶段必须明确批准；重大变化使下游工件 stale。',
    owner: '阶段参考文件', files: ['skills/project-lifecycle/references/requirements.md', 'proposal.md', 'design.md', 'tasks.md', 'testing.md'], link: '/guide/requirements', color: '#f59e0b'
  },
  {
    id: 'gate', step: '06', title: '门槛与关系', eyebrow: '控制层',
    summary: '检查批准状态、硬依赖、软关联、项目规则和范围漂移。',
    input: '工件状态、depends_on、related_to、规则和 Git 状态',
    process: ['按最早未满足阶段决定下一步', '硬依赖未完成 → 阻断实现和验收', '关系影响 → 对受影响工作项回退阶段'],
    output: '允许动作，或明确的 blockers', guard: '“继续”“开始做”“执行 WORK-*”本身不等于批准。',
    owner: 'workflow + relationships', files: ['skills/project-lifecycle/references/workflow.md', 'skills/project-lifecycle/references/relationships.md', 'skills/project-lifecycle/references/rules.md'], link: '/reference/boundaries', color: '#f97316'
  },
  {
    id: 'implement', step: '07', title: '实现与测试', eyebrow: '执行层',
    summary: '在任务计划批准、规则确认且没有阻塞后修改代码，并记录真实结果。',
    input: '已批准 tasks.md、源码、项目命令、测试计划',
    process: ['按任务切片修改源码和测试', '同步任务状态，不把计划当成完成事实', '按 AC-* 运行检查并保留证据'],
    output: '代码、测试、验证报告和剩余风险', guard: 'passed 只代表检查证据通过，不等于用户验收或发布授权。',
    owner: 'Agent + project tools', files: ['.agent/changes/WORK-*/tasks.md', '.agent/changes/WORK-*/testing/report.md', 'tests/'], link: '/guide/full-workflow', color: '#ef4444'
  },
  {
    id: 'handoff', step: '08', title: '完成沉淀 / 接力', eyebrow: '持续层',
    summary: '把稳定知识沉淀到 specs、memory，并用 WORK-* 在新对话继续。',
    input: '验证结果、当前事实、未完成事项和下一步',
    process: ['验证通过后核对规格和长期记忆', '需要继续时输出真实 WORK-* 接力句', '新对话重新读取事实，不搬运旧聊天'],
    output: '可交接的完成状态或下一轮恢复入口', guard: '不能凭时间戳或上一轮聊天猜测当前工作项。',
    owner: 'workflow.md + project_status.py', files: ['.agent/specs/', '.agent/memory.md', 'skills/project-lifecycle/references/workflow.md'], link: '/guide/resume', color: '#ec4899'
  },
]

const selectedId = ref('request')
const view = ref<'flow' | 'layers'>('flow')
const selected = computed(() => nodes.find((node) => node.id === selectedId.value) ?? nodes[0])

function selectNode(id: string) {
  selectedId.value = id
}
</script>

<template>
  <section class="architecture-shell" aria-labelledby="architecture-title">
    <div class="architecture-intro">
      <div>
        <p class="architecture-kicker">TECHNICAL FLOW MAP · v1</p>
        <h2 id="architecture-title">一次请求，如何穿过整个生命周期</h2>
        <p class="architecture-lede">点击节点查看“输入 → 处理 → 输出 → 阻塞条件”，再跳转到对应的用户教程和真实文件。</p>
      </div>
      <div class="architecture-legend" aria-label="图例">
        <span><i class="legend-dot legend-flow" />执行流</span>
        <span><i class="legend-dot legend-fact" />事实源</span>
        <span><i class="legend-dot legend-gate" />门槛</span>
      </div>
    </div>

    <div class="architecture-tabs" role="tablist" aria-label="架构图视图">
      <button type="button" role="tab" :aria-selected="view === 'flow'" :class="{ active: view === 'flow' }" @click="view = 'flow'">执行流</button>
      <button type="button" role="tab" :aria-selected="view === 'layers'" :class="{ active: view === 'layers' }" @click="view = 'layers'">分层关系</button>
    </div>

    <div v-if="view === 'flow'" class="architecture-workspace">
      <div class="flow-panel" aria-label="项目生命周期执行流">
        <div class="flow-caption"><span>用户意图</span><span>事实恢复</span><span>受控交付</span></div>
        <div class="flow-grid">
          <template v-for="(node, index) in nodes" :key="node.id">
            <button type="button" class="flow-node" :class="{ selected: node.id === selectedId }" :style="{ '--node-color': node.color }" :aria-label="`${node.step} ${node.title}`" :aria-pressed="node.id === selectedId" @click="selectNode(node.id)">
              <span class="node-step">{{ node.step }}</span>
              <span class="node-eyebrow">{{ node.eyebrow }}</span>
              <strong>{{ node.title }}</strong>
              <small>{{ node.summary }}</small>
            </button>
            <span v-if="index < nodes.length - 1" class="flow-connector" aria-hidden="true">{{ index % 2 === 0 ? '→' : '↙' }}</span>
          </template>
        </div>
        <div class="flow-footer"><span>↺ 发生目标 / 接口 / 数据 / 安全 / 架构变化</span><span>返回最早受影响阶段，令下游工件 stale</span></div>
      </div>

      <aside class="detail-panel" aria-live="polite">
        <div class="detail-topline"><span class="detail-step" :style="{ color: selected.color }">{{ selected.step }}</span><span>{{ selected.eyebrow }}</span></div>
        <h3>{{ selected.title }}</h3>
        <p class="detail-summary">{{ selected.summary }}</p>
        <div class="detail-block"><span>输入</span><p>{{ selected.input }}</p></div>
        <div class="detail-block"><span>内部处理</span><ul><li v-for="item in selected.process" :key="item">{{ item }}</li></ul></div>
        <div class="detail-block"><span>输出</span><p>{{ selected.output }}</p></div>
        <div class="detail-guard"><span>门槛</span><p>{{ selected.guard }}</p></div>
        <div class="detail-files"><span>真实位置 · {{ selected.owner }}</span><code v-for="file in selected.files" :key="file">{{ file }}</code></div>
        <a class="detail-link" :href="selected.link">阅读对应 Markdown 说明 <span>↗</span></a>
      </aside>
    </div>

    <div v-else class="layer-map" aria-label="项目生命周期分层架构">
      <div class="layer-row layer-request"><span class="layer-label">交互入口</span><strong>用户自然语言 / Codex 对话</strong><small>描述目标、批准阶段、恢复 WORK-*、请求验证</small></div>
      <div class="layer-arrow">↓ 识别意图与风险</div>
      <div class="layer-row layer-skill"><span class="layer-label">Skill 协议层</span><strong>SKILL.md + references/workflow.md</strong><small>路由流程、恢复顺序、门槛、批准、漂移和完成语义</small><a href="/guide/full-workflow">查看全流程</a></div>
      <div class="layer-arrow">↓ 读取并写入事实</div>
      <div class="layer-row layer-facts"><span class="layer-label">项目事实层</span><strong>.agent/</strong><small>rules · INDEX · changes/WORK-* · specs · memory · html</small><a href="/reference/">查看总索引</a></div>
      <div class="layer-arrow split">↙ 状态恢复　　　　　　　　　↘ 阶段执行</div>
      <div class="layer-row layer-tools"><span class="layer-label">确定性工具层</span><strong>project_status.py · project_validate.py · init_project.py</strong><small>状态推导、恢复探针、严格校验、幂等初始化</small><a href="/reference/commands">查看命令</a></div>
      <div class="layer-arrow">↓ 证据回写</div>
      <div class="layer-row layer-output"><span class="layer-label">交付与理解层</span><strong>源码 / 测试 / testing/report.md / VitePress / html</strong><small>实现结果可验证，知识可复用，下一轮可接力</small><a href="/guide/resume">查看恢复与接力</a></div>
    </div>

    <p class="architecture-note"><strong>读图方式：</strong>先看执行流理解“什么时候做什么”，再切到分层关系理解“哪一层负责什么”。所有状态来自项目工件和确定性脚本，教程只负责解释。</p>
  </section>
</template>
