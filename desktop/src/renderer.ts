// 渲染进程：只做展示，不读文件、不执行命令。所有数据经 window.api 取回。
// 本文件没有 import/export，因此 tsc 会把它编译成浏览器可直接加载的普通脚本。

const ui = {
  root: "",
  status: null as StatusView | null,
  selected: null as WorkItemView | null,
  artifacts: [] as ArtifactView[],
  selectedArtifact: null as ArtifactView | null,
  validate: null as ValidateView | null,
  history: null as HistoryEntry[] | null,
  workspace: null as WorkspaceView | null,
  resources: null as ResourceGroup[] | null,
  resourceFile: null as ResourceFile | null,
  view: "project" as "project" | "workspace" | "resources" | "relations",
  tab: "overview",
};

const NODE_W = 176;
const NODE_H = 86;
const NODE_GAP_X = 96;
const NODE_GAP_Y = 26;
const GRAPH_PAD = 20;
/** 同层关联的弧线会绕到节点右侧，画布要留出这段余量，否则会被 viewBox 裁掉。 */
const EDGE_MARGIN = 80;
const EDGE_BULGE = 46;

const APPROVAL_STATUS_TEXT: Record<string, string> = {
  approved: "已批准",
  draft: "草稿",
  stale: "需修订",
  missing: "缺失",
  unknown: "状态无法识别",
};

const REPORT_STATUS_TEXT: Record<string, string> = {
  passed: "验证通过",
  partial: "部分通过",
  failed: "未通过",
  stale: "需重跑",
  missing: "未验证",
};

/** 流程顺序；compact 模式没有方案和设计两道门，不显示比显示成"缺失"更诚实。 */
const GATE_ORDER = [
  { key: "requirements", label: "需求", approval: true, compact: true },
  { key: "proposal", label: "方案", approval: true, compact: false },
  { key: "design", label: "设计", approval: true, compact: false },
  { key: "tasks", label: "任务", approval: true, compact: true },
  { key: "implementation", label: "实现", approval: false, compact: true },
  { key: "verification", label: "验证", approval: false, compact: true },
  { key: "completed", label: "完成", approval: false, compact: true },
];

type GateStatus = "done" | "current" | "blocked" | "pending" | "skipped";

interface Gate {
  key: string;
  label: string;
  satisfied: boolean;
  status: GateStatus;
  statusText: string;
  signer: string;
  reasons: string[];
}

interface GraphNode {
  key: string;
  kind: "work" | "module";
  item: WorkItemView | null;
  module: ModuleView | null;
  x: number;
  y: number;
  vx: number;
  vy: number;
  w: number;
  h: number;
}

interface GraphEdge {
  from: string;
  to: string;
  kind: "depends" | "related" | "module";
}

function byId<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`页面缺少元素 #${id}`);
  return node as T;
}

function clear(node: HTMLElement): void {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function attr(text: string): string {
  return escapeHtml(text).replace(/"/g, "&quot;");
}

/** 工件里的时间是本地时间字符串或 ISO；两者都要能显示成人能读的形式。 */
function formatDate(value: string): string {
  if (!value) return "";
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(value)) return value;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const pad = (input: number) => String(input).padStart(2, "0");
  return (
    `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} ` +
    `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
  );
}

/** 门槛卡片里位置紧，只留月日时分。 */
function shortDate(value: string): string {
  const match = /^\d{4}-(\d{2})-(\d{2}) (\d{2}:\d{2})/.exec(value);
  return match ? `${match[1]}-${match[2]} ${match[3]}` : formatDate(value);
}

function stateColor(state: string): string {
  if (["complete", "passed", "ready"].includes(state)) return "#0f7a4a";
  if (["blocked", "stale", "needs_attention", "failed"].includes(state)) return "#c0342f";
  if (["in_progress", "awaiting_approval", "partial"].includes(state)) return "#2f6fd0";
  return "#7b8a9c";
}

/** 两侧分隔符可能不同（path.resolve 给反斜杠，配置里可能是正斜杠）。 */
function samePath(left: string, right: string): boolean {
  if (!left || !right) return false;
  const normalize = (value: string) => value.split("\\").join("/").replace(/\/$/, "").toLowerCase();
  return normalize(left) === normalize(right);
}

/** 绝对路径在标题里太长；项目内显示相对路径，项目外保持原样。 */
function shortPath(absolute: string): string {
  if (!ui.root) return absolute;
  const normalized = absolute.split("\\").join("/");
  const root = ui.root.split("\\").join("/").replace(/\/$/, "");
  if (!normalized.toLowerCase().startsWith(root.toLowerCase())) return absolute;
  return normalized.slice(root.length).replace(/^\//, "");
}

let toastTimer: number | undefined;

function toast(message: string): void {
  const node = byId("toast");
  node.textContent = message;
  node.classList.remove("hidden");
  if (toastTimer !== undefined) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => node.classList.add("hidden"), 6000);
}

function showEmpty(title: string, detail: string): void {
  const empty = byId("empty-state");
  clear(empty);
  empty.appendChild(element("h2", undefined, title));
  empty.appendChild(element("p", undefined, detail));
  empty.classList.remove("hidden");
  byId("detail-body").classList.add("hidden");
}

function setBusy(busy: boolean): void {
  byId<HTMLButtonElement>("refresh").disabled = busy;
  byId<HTMLButtonElement>("pick").disabled = busy;
}

async function loadProject(root: string): Promise<void> {
  ui.root = root;
  byId("project-path").textContent = root;
  showView("project");
  setBusy(true);
  try {
    const result = await window.api.loadStatus(root);
    if (!result.ok || !result.data) {
      ui.status = null;
      showEmpty("无法读取项目状态", result.error || "未知错误");
      clear(byId("work-list"));
      byId("work-count").textContent = "0";
      toast(result.error || "无法读取项目状态");
      return;
    }
    ui.status = result.data;
    if (result.data.scope === "workspace") {
      // 外层 .agent 只做多仓库导航，不承载工作项；打开它就该直接看工作区。
      ui.selected = null;
      await loadWorkspace();
      return;
    }
    renderSidebar();
    const items = result.data.work_items;
    if (items.length === 0) {
      ui.selected = null;
      showEmpty("这个项目还没有工作项", result.data.next_action);
      return;
    }
    await selectWorkItem(items[0]);
  } finally {
    setBusy(false);
  }
}

function renderSidebar(): void {
  const status = ui.status;
  const list = byId("work-list");
  clear(list);
  if (!status) return;
  const active = status.work_items.filter((item) => !item.archived);
  const archived = status.work_items.filter((item) => item.archived);
  byId("work-count").textContent = archived.length
    ? `${active.length} + ${archived.length} 归档`
    : String(active.length);

  const renderItem = (item: WorkItemView): void => {
    const li = element("li", "work-item");
    li.dataset.workId = item.work_id;
    if (ui.selected && ui.selected.work_id === item.work_id) li.classList.add("selected");

    if (item.archived) li.classList.add("archived");
    const head = element("div", "row");
    head.appendChild(element("span", "id", item.work_id + (item.archived ? " · 已归档" : "")));
    head.appendChild(element("span", `badge ${item.state}`, item.state_label));
    li.appendChild(head);
    li.appendChild(element("div", "name", item.name));

    const meta = element("div", "meta");
    meta.appendChild(element("span", undefined, item.phase_label));
    meta.appendChild(element("span", undefined, item.mode_label));
    const tasks = item.tasks;
    const total = tasks.pending + tasks.in_progress + tasks.done + tasks.blocked;
    if (total > 0) {
      meta.appendChild(element("span", undefined, `任务 ${tasks.done}/${total}`));
    }
    const signed = Object.keys(item.approval.artifacts).length;
    if (item.approval.status === "invalid") {
      meta.appendChild(element("span", "chip bad", "签署异常"));
    } else if (item.approval.unsigned.length > 0) {
      meta.appendChild(element("span", "chip warn", `待补签 ${item.approval.unsigned.length}`));
    } else if (signed > 0) {
      meta.appendChild(element("span", "chip ok", `已签署 ${signed}`));
    }
    li.appendChild(meta);
    li.addEventListener("click", () => {
      void selectWorkItem(item);
    });
    list.appendChild(li);
  };

  for (const item of active) renderItem(item);
  if (archived.length > 0) {
    // 归档项只供查阅：Python 侧不会把归档工作项当作可恢复对象
    const divider = element("li", "work-divider", `已归档 ${archived.length}`);
    list.appendChild(divider);
    for (const item of archived) renderItem(item);
  }

  const warnings = byId("project-warnings");
  clear(warnings);
  for (const warning of status.warnings) {
    warnings.appendChild(element("div", undefined, `· ${warning}`));
  }
  if (status.git.warning) {
    warnings.appendChild(element("div", undefined, `· ${status.git.warning}`));
  }
}

async function selectWorkItem(item: WorkItemView): Promise<void> {
  ui.selected = item;
  ui.selectedArtifact = null;
  renderSidebar();
  byId("empty-state").classList.add("hidden");
  byId("detail-body").classList.remove("hidden");
  renderSummary();
  renderOverview();

  const result = await window.api.loadArtifacts(ui.root, item);
  if (!result.ok || !result.data) {
    toast(result.error || "无法读取工件");
    ui.artifacts = [];
  } else {
    ui.artifacts = result.data;
  }
  renderArtifacts();
  if (ui.tab === "read") await openPreferredArtifact();
}

async function openPreferredArtifact(): Promise<void> {
  const preferred =
    ui.artifacts.find((artifact) => artifact.key === "requirements" && artifact.exists) ??
    ui.artifacts.find((artifact) => artifact.exists);
  if (preferred) await selectArtifact(preferred);
  else renderDocument(null);
}

function renderSummary(): void {
  const item = ui.selected;
  if (!item) return;
  byId("work-title").textContent = `${item.work_id} · ${item.name}`;
  byId("work-subtitle").textContent =
    `${item.phase_label} · ${item.mode}（${item.mode_label}） · ${item.path}`;
  const stateBadge = byId("work-state");
  stateBadge.textContent = item.state_label;
  stateBadge.className = `badge ${item.state}`;

  const stats = byId("work-stats");
  clear(stats);
  const tasks = item.tasks;
  const total = tasks.pending + tasks.in_progress + tasks.done + tasks.blocked;
  const pairs: Array<[string, string]> = [
    ["任务完成", `${tasks.done}/${total}`],
    ["进行中", String(tasks.in_progress)],
    ["阻塞", String(tasks.blocked)],
    ["已签署工件", String(Object.keys(item.approval.artifacts).length)],
  ];
  for (const [label, value] of pairs) {
    const block = element("div");
    block.appendChild(element("b", undefined, value));
    block.appendChild(element("span", undefined, label));
    stats.appendChild(block);
  }

  byId("work-next").textContent = item.next_action ? `下一步：${item.next_action}` : "";

  const approvalRow = byId("work-approval");
  clear(approvalRow);
  const approvalStatus = item.approval.status;
  const signedCount = Object.keys(item.approval.artifacts).length;
  const chipClass =
    approvalStatus === "complete"
      ? "chip ok"
      : approvalStatus === "invalid"
        ? "chip bad"
        : approvalStatus === "not_required"
          ? "chip"
          : "chip warn";
  approvalRow.appendChild(
    element(
      "span",
      chipClass,
      signedCount === 0 && item.approval.unsigned.length === 0
        ? "尚无签署"
        : `已签署 ${signedCount} 个工件` +
            (item.approval.unsigned.length > 0 ? ` · 待补签 ${item.approval.unsigned.length}` : ""),
    ),
  );
  if (item.approval.acceptance) {
    approvalRow.appendChild(
      element(
        "span",
        "chip ok",
        `业务验收：${item.approval.acceptance.accepted_by} · ${shortDate(item.approval.acceptance.accepted_at)}`,
      ),
    );
  }
  const evidence = item.state_evidence;
  approvalRow.appendChild(
    element("span", "chip", `代码核对：${evidence.code_sync} · 结算：${evidence.settlement_status}`),
  );
}

/** 把工件状态和任务/验证进度翻译成七道门的可见状态。 */
function buildGates(item: WorkItemView): { gates: Gate[]; otherWarnings: string[] } {
  const compact = item.mode === "managed";
  const definitions = GATE_ORDER.filter((gate) => (compact ? gate.compact : true));
  const approval = item.approval;
  const attributed = new Set<string>();
  const take = (list: string[]): string[] => {
    for (const warning of list) attributed.add(warning);
    return list;
  };

  const gates: Gate[] = definitions.map((definition) => {
    const reasons: string[] = [];
    let satisfied = false;
    let statusText = "";
    let signer = "";

    if (definition.approval) {
      const raw = item.artifacts[definition.key] ?? "missing";
      const unsigned = approval.unsigned.includes(definition.key);
      const invalid = approval.invalid.includes(definition.key);
      const record = approval.artifacts[definition.key];
      if (record) {
        signer =
          `${record.approved_by}${record.approver_role ? `（${record.approver_role}）` : ""}` +
          ` · ${shortDate(record.approved_at)}`;
      } else if (unsigned) {
        signer = "已批准但未签署";
      }
      satisfied = raw === "approved" && !unsigned && !invalid;
      statusText = APPROVAL_STATUS_TEXT[raw] ?? raw;
      if (definition.key === "requirements") reasons.push(...take(item.source_coverage.warnings));
      if (unsigned) reasons.push("已批准但缺少签署记录，请用 approve 补签。");
      if (invalid) reasons.push("签署时间戳格式无效，请重新盖章。");
    } else if (definition.key === "implementation") {
      const tasks = item.tasks;
      const total = tasks.pending + tasks.in_progress + tasks.done + tasks.blocked;
      satisfied = total > 0 && tasks.pending + tasks.in_progress + tasks.blocked === 0;
      statusText = total === 0 ? "无任务" : `${tasks.done}/${total} 完成`;
      if (tasks.blocked > 0) reasons.push(`${tasks.blocked} 个任务处于 blocked。`);
    } else if (definition.key === "verification") {
      const report = item.artifacts.test_report ?? "missing";
      const evidence = item.test_evidence.status;
      // 报告写 passed 但结构化证据不完整时这道门并没有过：门是绿的却挂红字原因会自相矛盾。
      const broken = ["incomplete", "invalid"].includes(evidence);
      satisfied = report === "passed" && !broken;
      statusText = broken
        ? evidence === "invalid"
          ? "证据格式无效"
          : "证据不完整"
        : (REPORT_STATUS_TEXT[report] ?? report);
      if (broken) reasons.push(...take(item.test_evidence.warnings));
      // partial/failed/stale 是明确的失败态，不是"还没做"，必须点红。
      if (["partial", "failed", "stale"].includes(report)) {
        reasons.push(`验证报告状态为 ${report}，不能作为完成证据。`);
      }
    } else {
      satisfied = item.phase === "completed" && item.state === "complete";
      statusText = satisfied ? "已沉淀" : item.state_label;
      reasons.push(...take(item.document_budget.warnings), ...take(item.workspace_attribution.warnings));
    }
    return { key: definition.key, label: definition.label, satisfied, status: "pending", statusText, signer, reasons };
  });

  // 位置决定红点：上游没满足却已经走到后面，就是卡住。
  const currentIndex = gates.findIndex((gate) => gate.key === item.phase);
  gates.forEach((gate, index) => {
    if (gate.satisfied) gate.status = "done";
    else if (index < currentIndex) gate.status = "blocked";
    else if (index === currentIndex) gate.status = gate.reasons.length > 0 ? "blocked" : "current";
    else gate.status = gate.reasons.length > 0 ? "blocked" : "pending";
  });

  const otherWarnings = item.warnings.filter((warning) => !attributed.has(warning));
  return { gates, otherWarnings };
}

function renderGates(): void {
  const strip = byId("gate-strip");
  clear(strip);
  if (!ui.selected) return;
  const { gates, otherWarnings } = buildGates(ui.selected);

  gates.forEach((gate, index) => {
    const li = element("li", `gate ${gate.status}`);
    const top = element("div", "gate-top");
    top.appendChild(element("span", "gate-index", String(index + 1)));
    top.appendChild(element("span", "gate-label", gate.label));
    top.appendChild(element("span", "gate-status", gate.statusText));
    li.appendChild(top);
    if (gate.signer) li.appendChild(element("div", "gate-signer", gate.signer));
    for (const reason of gate.reasons) li.appendChild(element("div", "gate-reason", reason));
    strip.appendChild(li);
  });

  const panel = byId("other-warnings-panel");
  const container = byId("other-warnings");
  clear(container);
  for (const warning of otherWarnings) container.appendChild(element("div", "issue warning", warning));
  panel.classList.toggle("hidden", otherWarnings.length === 0);
}

const MODULE_W = 152;
const MODULE_H = 50;
/** 图的视图状态放在模块级：重新选工作项不该把用户拖好的位置和缩放重置。 */
const graphState = {
  signature: "",
  nodes: [] as GraphNode[],
  edges: [] as GraphEdge[],
  k: 1,
  tx: 0,
  ty: 0,
  showDepends: true,
  // Paideia 这类项目的 related_to 比依赖多一个量级（26 项 170+ 条），全开就是面条；先只看硬依赖。
  showRelated: false,
  // 模块索引通常有 20 多条，默认叠进来会让 26 个工作项的图挤成一团；想看再开。
  showModules: false,
  onlyAttention: false,
  drag: null as { key: string; startX: number; startY: number; originX: number; originY: number; moved: boolean } | null,
  pan: null as { x: number; y: number; tx: number; ty: number } | null,
  suppressClick: false,
};

function needsAttention(item: WorkItemView): boolean {
  return (
    ["blocked", "needs_attention", "stale", "failed"].includes(item.state) ||
    item.approval.unsigned.length > 0
  );
}

function buildGraphModels(): void {
  const items = (ui.status?.work_items ?? []).filter(
    (item) => !graphState.onlyAttention || needsAttention(item),
  );
  const visible = new Set(items.map((item) => item.work_id));
  const nodes: GraphNode[] = items.map((item) => ({
    key: item.work_id,
    kind: "work",
    item,
    module: null,
    x: 0,
    y: 0,
    vx: 0,
    vy: 0,
    w: NODE_W,
    h: NODE_H,
  }));
  const edges: GraphEdge[] = [];

  for (const item of items) {
    if (graphState.showDepends) {
      for (const dependency of item.relations.depends_on) {
        if (visible.has(dependency.work_id)) {
          edges.push({ from: item.work_id, to: dependency.work_id, kind: "depends" });
        }
      }
    }
    if (graphState.showRelated) {
      for (const related of item.relations.related) {
        if (visible.has(related.work_id)) {
          edges.push({ from: item.work_id, to: related.work_id, kind: "related" });
        }
      }
    }
  }

  if (graphState.showModules) {
    for (const module of ui.status?.modules ?? []) {
      const hits = module.work_ids.filter((workId) => visible.has(workId));
      if (hits.length === 0) continue;
      const key = `M:${module.name}`;
      nodes.push({
        key,
        kind: "module",
        item: null,
        module,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        w: MODULE_W,
        h: MODULE_H,
      });
      for (const workId of hits) edges.push({ from: key, to: workId, kind: "module" });
    }
  }

  graphState.nodes = nodes;
  graphState.edges = edges;
  layoutForce(nodes, edges);
}

/** 小型力导向：节点按矩形外接尺寸互相排斥、边当弹簧、弱向心力防止散开。 */
function layoutForce(nodes: GraphNode[], edges: GraphEdge[]): void {
  const byKey = new Map(nodes.map((node) => [node.key, node]));
  const work = nodes.filter((node) => node.kind === "work");
  const modules = nodes.filter((node) => node.kind === "module");
  work.forEach((node, index) => {
    // 黄金角螺旋起步：比圆周均布更不容易在早期步里叠在一起。
    const angle = index * 2.39996;
    const radius = 90 + Math.sqrt(index + 1) * 118;
    node.x = Math.cos(angle) * radius;
    node.y = Math.sin(angle) * radius * 0.78;
  });
  modules.forEach((node, index) => {
    const angle = index * 2.39996 + 0.9;
    const radius = 360 + Math.sqrt(index + 1) * 120;
    node.x = Math.cos(angle) * radius;
    node.y = Math.sin(angle) * radius * 0.8;
  });

  // 矩形不相交所需的最小中心距：取宽高中更紧的一维，再加透气量。
  const clearance = (a: GraphNode, b: GraphNode): number =>
    Math.max((a.w + b.w) / 2, (a.h + b.h) / 2) + 26;

  const rest: Record<GraphEdge["kind"], number> = { depends: 235, related: 275, module: 185 };
  const steps = 900;
  for (let step = 0; step < steps; step += 1) {
    const cooling = 1 - step / steps;
    for (let left = 0; left < nodes.length; left += 1) {
      for (let right = left + 1; right < nodes.length; right += 1) {
        const a = nodes[left];
        const b = nodes[right];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distance = Math.hypot(dx, dy);
        if (distance < 0.01) {
          dx = ((left % 7) - 3) || 1;
          dy = ((right % 5) - 2) || 1;
          distance = Math.hypot(dx, dy);
        }
        const needed = clearance(a, b);
        // 只在碰撞带附近排斥：库仑项会让整张图溢出画布，反而把 fit 缩放压到看不清。
        const push = distance < needed * 1.5 ? (needed * 1.5 - distance) * 0.5 * cooling : 0;
        const fx = (dx / distance) * push;
        const fy = (dy / distance) * push;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }
    for (const edge of edges) {
      const a = byKey.get(edge.from);
      const b = byKey.get(edge.to);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const distance = Math.hypot(dx, dy) || 0.01;
      const pull = (distance - rest[edge.kind]) * 0.02;
      const fx = (dx / distance) * pull;
      const fy = (dy / distance) * pull;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }
    for (const node of nodes) {
      node.vx -= node.x * 0.004;
      node.vy -= node.y * 0.004;
      node.vx *= 0.84;
      node.vy *= 0.84;
      node.x += node.vx;
      node.y += node.vy;
    }
  }
  // 收尾：最后几轮只解重叠，让观感干净。
  for (let pass = 0; pass < 40; pass += 1) {
    for (let left = 0; left < nodes.length; left += 1) {
      for (let right = left + 1; right < nodes.length; right += 1) {
        const a = nodes[left];
        const b = nodes[right];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distance = Math.hypot(dx, dy) || 0.01;
        const needed = clearance(a, b);
        if (distance >= needed) continue;
        const shift = (needed - distance) / 2;
        const fx = (dx / distance) * shift;
        const fy = (dy / distance) * shift;
        a.x -= fx;
        a.y -= fy;
        b.x += fx;
        b.y += fy;
      }
    }
  }
}

/** 线从矩形边框出发，避免压在节点文字上。 */
function boundaryPoint(from: GraphNode, to: GraphNode): { x: number; y: number } {
  const dx = to.x + to.w / 2 - (from.x + from.w / 2);
  const dy = to.y + to.h / 2 - (from.y + from.h / 2);
  const scale = Math.min(
    Math.abs(dx) < 0.01 ? Infinity : from.w / 2 / Math.abs(dx),
    Math.abs(dy) < 0.01 ? Infinity : from.h / 2 / Math.abs(dy),
  );
  const ratio = Number.isFinite(scale) ? scale : 0;
  return { x: from.x + from.w / 2 + dx * ratio, y: from.y + from.h / 2 + dy * ratio };
}

function graphEdgesMarkup(): string {
  const byKey = new Map(graphState.nodes.map((node) => [node.key, node]));
  return graphState.edges
    .map((edge) => {
      const from = byKey.get(edge.from);
      const to = byKey.get(edge.to);
      if (!from || !to) return "";
      const start = boundaryPoint(from, to);
      const finish = boundaryPoint(to, from);
      const marker = edge.kind === "depends" ? ' marker-end="url(#graph-arrow)"' : "";
      let path = `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} L ${finish.x.toFixed(1)} ${finish.y.toFixed(1)}`;
      if (edge.kind !== "depends") {
        // 关联和模块线画成轻微弧线：平直虚线在密集区会糊在一起。
        const mx = (start.x + finish.x) / 2 + (finish.y - start.y) * 0.12;
        const my = (start.y + finish.y) / 2 - (finish.x - start.x) * 0.12;
        path = `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} Q ${mx.toFixed(1)} ${my.toFixed(1)} ${finish.x.toFixed(1)} ${finish.y.toFixed(1)}`;
      }
      return (
        `<path class="edge ${edge.kind}" data-from="${attr(edge.from)}" data-to="${attr(edge.to)}"` +
        ` d="${path}"${marker} />`
      );
    })
    .join("");
}

function clip(text: string, max: number): string {
  const chars = Array.from(text);
  return chars.length > max ? `${chars.slice(0, max).join("")}…` : text;
}

function graphNodeMarkup(node: GraphNode): string {
  if (node.kind === "module") {
    const module = node.module as ModuleView;
    return (
      `<g class="gnode module" data-key="${attr(node.key)}" data-module="${attr(module.name)}"` +
      ` transform="translate(${node.x.toFixed(1)} ${node.y.toFixed(1)})">` +
      `<rect class="gnode-box" width="${MODULE_W}" height="${MODULE_H}" rx="8" />` +
      `<text class="gnode-module-name" x="11" y="21">${escapeHtml(clip(module.name, 9))}</text>` +
      `<text class="gnode-module-meta" x="11" y="37">${escapeHtml(clip(module.path, 15))} · ${module.work_ids.length} 项</text>` +
      `</g>`
    );
  }
  const item = node.item as WorkItemView;
  const tasks = item.tasks;
  const total = tasks.pending + tasks.in_progress + tasks.done + tasks.blocked;
  const signed = Object.keys(item.approval.artifacts).length;
  const unsigned = item.approval.unsigned.length;
  const sign = unsigned > 0 ? ` · 待补签 ${unsigned}` : signed > 0 ? ` · 已签 ${signed}` : "";
  const selected = ui.selected?.work_id === item.work_id;
  return (
    `<g class="gnode work${selected ? " selected" : ""}" data-key="${attr(node.key)}"` +
    ` data-work-id="${attr(item.work_id)}" transform="translate(${node.x.toFixed(1)} ${node.y.toFixed(1)})">` +
    `<rect class="gnode-box" width="${NODE_W}" height="${NODE_H}" rx="10" />` +
    `<rect width="4" height="${NODE_H}" rx="2" fill="${stateColor(item.state)}" />` +
    `<text class="gnode-id" x="14" y="20">${escapeHtml(item.work_id)}</text>` +
    `<text class="gnode-name" x="14" y="41">${escapeHtml(clip(item.name, 11))}</text>` +
    `<text class="gnode-meta" x="14" y="60">${escapeHtml(item.phase_label)}${total > 0 ? ` · 任务 ${tasks.done}/${total}` : ""}</text>` +
    `<text class="gnode-meta" x="14" y="77">${escapeHtml(item.state_label + sign)}</text>` +
    `</g>`
  );
}

function paintGraphPositions(): void {
  const edgeLayer = document.getElementById("graph-edges");
  const nodeLayer = document.getElementById("graph-nodes");
  if (!edgeLayer || !nodeLayer) return;
  edgeLayer.innerHTML = graphEdgesMarkup();
  nodeLayer.innerHTML = graphState.nodes.map(graphNodeMarkup).join("");
}

function applyGraphTransform(): void {
  const world = document.getElementById("graph-world");
  if (world) {
    world.setAttribute(
      "transform",
      `translate(${graphState.tx.toFixed(1)} ${graphState.ty.toFixed(1)}) scale(${graphState.k.toFixed(3)})`,
    );
  }
}

function fitGraph(): void {
  const container = byId("graph");
  if (graphState.nodes.length === 0) return;
  const width = container.clientWidth || 900;
  const height = container.clientHeight || 560;
  const minX = Math.min(...graphState.nodes.map((node) => node.x));
  const minY = Math.min(...graphState.nodes.map((node) => node.y));
  const maxX = Math.max(...graphState.nodes.map((node) => node.x + node.w));
  const maxY = Math.max(...graphState.nodes.map((node) => node.y + node.h));
  const margin = 30;
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const fitted = Math.min((width - margin * 2) / spanX, (height - margin * 2) / spanY);
  // 缩放下限保证 10px 文字仍可读；图超出视野就靠平移看，不把它压成看不清的一团。
  graphState.k = Math.max(0.55, Math.min(1.15, fitted));
  const scaledX = spanX * graphState.k;
  const scaledY = spanY * graphState.k;
  graphState.tx =
    scaledX <= width - margin * 2 ? (width - scaledX) / 2 - minX * graphState.k : margin - minX * graphState.k;
  graphState.ty =
    scaledY <= height - margin * 2 ? (height - scaledY) / 2 - minY * graphState.k : margin - minY * graphState.k;
  applyGraphTransform();
}

function zoomGraph(factor: number, clientX?: number, clientY?: number): void {
  const container = byId("graph");
  const rect = container.getBoundingClientRect();
  const anchorX = clientX === undefined ? rect.width / 2 : clientX - rect.left;
  const anchorY = clientY === undefined ? rect.height / 2 : clientY - rect.top;
  const next = Math.max(0.15, Math.min(3, graphState.k * factor));
  // 缩放前光标下的世界坐标保持不变，观感上才是“朝那个点放大”。
  graphState.tx = anchorX - ((anchorX - graphState.tx) / graphState.k) * next;
  graphState.ty = anchorY - ((anchorY - graphState.ty) / graphState.k) * next;
  graphState.k = next;
  applyGraphTransform();
}

function highlightGraph(activeKey: string): void {
  const neighbours = new Set<string>();
  for (const edge of Array.from(document.querySelectorAll<SVGPathElement>("#graph-edges .edge"))) {
    const from = edge.getAttribute("data-from") ?? "";
    const to = edge.getAttribute("data-to") ?? "";
    const hot = Boolean(activeKey) && (from === activeKey || to === activeKey);
    edge.classList.toggle("hot", hot);
    if (hot) {
      neighbours.add(from === activeKey ? to : from);
    }
  }
  for (const node of Array.from(document.querySelectorAll<SVGGElement>("#graph .gnode"))) {
    const key = node.getAttribute("data-key") ?? "";
    node.classList.toggle("hot", Boolean(activeKey) && (key === activeKey || neighbours.has(key)));
    node.classList.toggle("dim", Boolean(activeKey) && key !== activeKey && !neighbours.has(key));
  }
}

function describeGraphNode(key: string): string {
  const node = graphState.nodes.find((candidate) => candidate.key === key);
  if (!node) return "";
  if (node.kind === "module") {
    const module = node.module as ModuleView;
    const linked = module.work_ids
      .map((workId) => {
        const item = ui.status?.work_items.find((candidate) => candidate.work_id === workId);
        return item ? `${workId} ${item.name}` : workId;
      })
      .join("、");
    return `<b>模块 · ${escapeHtml(module.name)}</b><br>源码：${escapeHtml(module.path || "—")}<br>相关工作项：${escapeHtml(linked)}`;
  }
  const item = node.item as WorkItemView;
  const dependencies = item.relations.depends_on.filter((dep) => !dep.missing).map((dep) => dep.work_id);
  const dependents = item.relations.dependents.map((dep) => dep.work_id);
  const related = item.relations.related.map((dep) => dep.work_id);
  const modules = (ui.status?.modules ?? [])
    .filter((module) => module.work_ids.includes(item.work_id))
    .map((module) => module.name);
  const tasks = item.tasks;
  return (
    `<b>${escapeHtml(item.work_id)} · ${escapeHtml(item.name)}</b> · ${escapeHtml(item.state_label)}<br>` +
    `依赖：${dependencies.length ? dependencies.join("、") : "无"}　被依赖：${dependents.length ? dependents.join("、") : "无"}　关联：${related.length ? related.join("、") : "无"}<br>` +
    `模块：${modules.length ? escapeHtml(modules.join("、")) : "索引里没有登记"}　任务：${tasks.done}/${tasks.pending + tasks.in_progress + tasks.done + tasks.blocked}<br>` +
    `待补签：${item.approval.unsigned.length}　缺少证据的验收：${item.traceability.acceptance_without_evidence.length}`
  );
}

function renderGraph(): void {
  const container = byId("graph");
  const status = ui.status;
  if (!status || status.work_items.length === 0) {
    clear(container);
    container.appendChild(element("p", "muted", "没有工作项。"));
    graphState.signature = "";
    return;
  }
  // 只在数据或图层开关变化时重建；单纯选中工作项只改高亮，保留用户的缩放和拖动。
  const signature = [
    status.project_root,
    status.work_items.length,
    graphState.showDepends,
    graphState.showRelated,
    graphState.showModules,
    graphState.onlyAttention,
  ].join("|");
  if (signature === graphState.signature) {
    for (const node of Array.from(container.querySelectorAll<SVGGElement>(".gnode.work"))) {
      node.classList.toggle("selected", node.getAttribute("data-work-id") === (ui.selected?.work_id ?? ""));
    }
    return;
  }
  graphState.signature = signature;
  buildGraphModels();
  container.innerHTML =
    `<svg class="graph-svg" id="graph-svg">` +
    `<defs><marker id="graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">` +
    `<path d="M 0 0 L 10 5 L 0 10 z" fill="#2f6fd0" /></marker></defs>` +
    `<g id="graph-world"><g id="graph-edges"></g><g id="graph-nodes"></g></g>` +
    `</svg>`;
  paintGraphPositions();
  fitGraph();
  const workCount = graphState.nodes.filter((node) => node.kind === "work").length;
  const moduleCount = graphState.nodes.filter((node) => node.kind === "module").length;
  byId("graph-count").textContent =
    `${workCount} 个工作项 · ${moduleCount} 个模块 · ${graphState.edges.length} 条连线`;
  byId("graph-detail").textContent = "悬停节点看关系，拖节点调整位置，滚轮缩放，空白处拖动平移。";
}


/* ---------- 关系图谱（3D 力导向，独立页面） ---------- */

interface RelNode {
  key: string;
  kind: "work" | "module";
  item: WorkItemView | null;
  module: ModuleView | null;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  r: number;
}

interface RelEdge {
  from: string;
  to: string;
  kind: "depends" | "related" | "module";
}

const relState = {
  nodes: [] as RelNode[],
  edges: [] as RelEdge[],
  /** 绕 Y 轴（左右转）与 X 轴（上下俯仰）的角度。 */
  yaw: 0.62,
  pitch: -0.34,
  zoom: 1,
  signature: "",
  showDepends: true,
  // 3D 里关联边比 2D 更容易糊成一片，默认只画硬依赖。
  showRelated: false,
  showModules: false,
  onlyAttention: false,
  dragging: false,
  moved: false,
  suppressClickUntil: 0,
  lastX: 0,
  lastY: 0,
  spin: false,
  spinRaf: 0,
  hot: "",
};

function relViewport(): { width: number; height: number } {
  const container = document.getElementById("relations-graph");
  return { width: container?.clientWidth || 900, height: container?.clientHeight || 620 };
}

/** 透视投影：先绕 Y 再绕 X，越远的节点越小越淡。 */
function relProject(
  node: RelNode,
  width: number,
  height: number,
): { sx: number; sy: number; scale: number; depth: number } {
  const cosY = Math.cos(relState.yaw);
  const sinY = Math.sin(relState.yaw);
  const x1 = node.x * cosY + node.z * sinY;
  const z1 = -node.x * sinY + node.z * cosY;
  const cosX = Math.cos(relState.pitch);
  const sinX = Math.sin(relState.pitch);
  const y1 = node.y * cosX - z1 * sinX;
  const depth = node.y * sinX + z1 * cosX;
  const camera = 2400;
  const scale = (relState.zoom * camera) / (camera + depth);
  return { sx: width / 2 + x1 * scale, sy: height / 2 + y1 * scale, scale, depth };
}

function buildRelModels(): void {
  const items = (ui.status?.work_items ?? []).filter(
    (item) => !relState.onlyAttention || needsAttention(item),
  );
  const visible = new Set(items.map((item) => item.work_id));
  const nodes: RelNode[] = items.map((item) => {
    const tasks = item.tasks;
    const total = tasks.pending + tasks.in_progress + tasks.done + tasks.blocked;
    return {
      key: item.work_id,
      kind: "work",
      item,
      module: null,
      x: 0,
      y: 0,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      // 节点大小编码工作量：任务多的工作项自然更大，一眼看出重心在哪。
      r: 8 + Math.sqrt(Math.max(0, total)) * 2.9,
    };
  });
  const edges: RelEdge[] = [];
  for (const item of items) {
    if (relState.showDepends) {
      for (const dependency of item.relations.depends_on) {
        if (visible.has(dependency.work_id)) {
          edges.push({ from: item.work_id, to: dependency.work_id, kind: "depends" });
        }
      }
    }
    if (relState.showRelated) {
      for (const related of item.relations.related) {
        if (visible.has(related.work_id)) {
          edges.push({ from: item.work_id, to: related.work_id, kind: "related" });
        }
      }
    }
  }
  if (relState.showModules) {
    for (const module of ui.status?.modules ?? []) {
      const hits = module.work_ids.filter((workId) => visible.has(workId));
      if (hits.length === 0) continue;
      const key = `M:${module.name}`;
      nodes.push({
        key,
        kind: "module",
        item: null,
        module,
        x: 0,
        y: 0,
        z: 0,
        vx: 0,
        vy: 0,
        vz: 0,
        r: 7,
      });
      for (const workId of hits) edges.push({ from: key, to: workId, kind: "module" });
    }
  }
  relState.nodes = nodes;
  relState.edges = edges;
  layoutRel3D(nodes, edges);
}

/** 3D 力导向：球面起步，碰撞排斥 + 边弹簧 + 轻度向心力。 */
function layoutRel3D(nodes: RelNode[], edges: RelEdge[]): void {
  const byKey = new Map(nodes.map((node) => [node.key, node]));
  // 斐波那契球面：点均匀铺在球上，避免初始扎堆。
  nodes.forEach((node, index) => {
    const phi = Math.acos(1 - (2 * (index + 0.5)) / Math.max(1, nodes.length));
    const theta = Math.PI * (1 + Math.sqrt(5)) * index;
    // 半径按节点数放大：26 个节点挤在半径 260 的球里，斥力再大也解不开。
    const radius = 210 + Math.sqrt(nodes.length) * 44 + (index % 4) * 22;
    node.x = Math.sin(phi) * Math.cos(theta) * radius;
    node.y = Math.cos(phi) * radius * 0.82;
    node.z = Math.sin(phi) * Math.sin(theta) * radius;
  });

  const rest: Record<RelEdge["kind"], number> = { depends: 320, related: 380, module: 240 };
  const steps = 760;
  for (let step = 0; step < steps; step += 1) {
    const cooling = 1 - step / steps;
    for (let left = 0; left < nodes.length; left += 1) {
      for (let right = left + 1; right < nodes.length; right += 1) {
        const a = nodes[left];
        const b = nodes[right];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let dz = b.z - a.z;
        let distance = Math.hypot(dx, dy, dz);
        if (distance < 0.01) {
          dx = ((left % 5) - 2) || 1;
          dy = ((right % 5) - 2) || 1;
          dz = 1;
          distance = Math.hypot(dx, dy, dz);
        }
        const needed = a.r + b.r + 130;
        const push = distance < needed * 1.55 ? (needed * 1.55 - distance) * 0.46 * cooling : 0;
        const fx = (dx / distance) * push;
        const fy = (dy / distance) * push;
        const fz = (dz / distance) * push;
        a.vx -= fx;
        a.vy -= fy;
        a.vz -= fz;
        b.vx += fx;
        b.vy += fy;
        b.vz += fz;
      }
    }
    for (const edge of edges) {
      const a = byKey.get(edge.from);
      const b = byKey.get(edge.to);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dz = b.z - a.z;
      const distance = Math.hypot(dx, dy, dz) || 0.01;
      const pull = (distance - rest[edge.kind]) * 0.016;
      const fx = (dx / distance) * pull;
      const fy = (dy / distance) * pull;
      const fz = (dz / distance) * pull;
      a.vx += fx;
      a.vy += fy;
      a.vz += fz;
      b.vx -= fx;
      b.vy -= fy;
      b.vz -= fz;
    }
    for (const node of nodes) {
      // 向心力只防飘散，压强了会把节点挤回中心再次重叠。
      node.vx -= node.x * 0.0011;
      node.vy -= node.y * 0.0011;
      node.vz -= node.z * 0.0011;
      node.vx *= 0.84;
      node.vy *= 0.84;
      node.vz *= 0.84;
      node.x += node.vx;
      node.y += node.vy;
      node.z += node.vz;
    }
  }
  // 收尾只解穿插：力导向收敛后仍可能有一两对贴在一起。
  for (let pass = 0; pass < 60; pass += 1) {
    for (let left = 0; left < nodes.length; left += 1) {
      for (let right = left + 1; right < nodes.length; right += 1) {
        const a = nodes[left];
        const b = nodes[right];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dz = b.z - a.z;
        const distance = Math.hypot(dx, dy, dz) || 0.01;
        const needed = a.r + b.r + 96;
        if (distance >= needed) continue;
        const shift = (needed - distance) / 2;
        const fx = (dx / distance) * shift;
        const fy = (dy / distance) * shift;
        const fz = (dz / distance) * shift;
        a.x -= fx;
        a.y -= fy;
        a.z -= fz;
        b.x += fx;
        b.y += fy;
        b.z += fz;
      }
    }
  }
}

function relNodeMarkup(
  node: RelNode,
  projection: { sx: number; sy: number; scale: number; depth: number },
  hot: boolean,
  dim: boolean,
): string {
  const selected = node.item !== null && ui.selected?.work_id === node.item.work_id;
  const opacity = Math.max(0.34, Math.min(1, 0.72 + projection.depth / 1600));
  if (node.kind === "module") {
    const module = node.module as ModuleView;
    return (
      `<g class="rnode module${hot ? " hot" : ""}${dim ? " dim" : ""}" data-rel-key="${attr(node.key)}"` +
      ` data-rel-module="${attr(module.name)}" opacity="${opacity.toFixed(2)}"` +
      ` transform="translate(${projection.sx.toFixed(1)} ${projection.sy.toFixed(1)}) scale(${projection.scale.toFixed(3)})">` +
      `<rect x="${-node.r}" y="${-node.r}" width="${node.r * 2}" height="${node.r * 2}" rx="3"` +
      ` class="rnode-box" transform="rotate(45)" />` +
      `<text class="rnode-label module" x="0" y="${node.r + 15}" text-anchor="middle">${escapeHtml(clip(module.name, 10))}</text>` +
      `</g>`
    );
  }
  const item = node.item as WorkItemView;
  const tasks = item.tasks;
  const total = tasks.pending + tasks.in_progress + tasks.done + tasks.blocked;
  // 名称只在高亮或选中时出现：26 个节点长期挂两行字必然互相压字。
  const showName = hot || selected;
  return (
    `<g class="rnode work${selected ? " selected" : ""}${hot ? " hot" : ""}${dim ? " dim" : ""}"` +
    ` data-rel-key="${attr(node.key)}" data-work-id="${attr(item.work_id)}"` +
    ` opacity="${opacity.toFixed(2)}"` +
    ` transform="translate(${projection.sx.toFixed(1)} ${projection.sy.toFixed(1)}) scale(${projection.scale.toFixed(3)})">` +
    `<circle class="rnode-halo" r="${(node.r + 4).toFixed(1)}" />` +
    `<circle class="rnode-dot" r="${node.r.toFixed(1)}" fill="${stateColor(item.state)}" />` +
    `<text class="rnode-id" x="0" y="${(node.r + 13).toFixed(1)}" text-anchor="middle">${escapeHtml(item.work_id)}</text>` +
    (showName
      ? `<text class="rnode-name" x="0" y="${(node.r + 25).toFixed(1)}" text-anchor="middle">${escapeHtml(clip(item.name, 10))}</text>`
      : "") +
    `<title>${escapeHtml(`${item.work_id} · ${item.name} · ${item.state_label} · 任务 ${tasks.done}/${total}`)}</title>` +
    `</g>`
  );
}

/** 按当前视角把整张图缩放到视口内：3D 旋转后包围盒变化很大，靠固定 zoom 一定会出画。 */
function fitRelations(): void {
  const { width, height } = relViewport();
  if (relState.nodes.length === 0 || width < 10 || height < 10) return;
  const saved = relState.zoom;
  relState.zoom = 1;
  const points = relState.nodes.map((node) => relProject(node, width, height));
  relState.zoom = saved;
  const pad = 40;
  const minX = Math.min(...points.map((point) => point.sx));
  const maxX = Math.max(...points.map((point) => point.sx));
  const minY = Math.min(...points.map((point) => point.sy));
  const maxY = Math.max(...points.map((point) => point.sy));
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  // 节点/模块多时缩得太小字就没了：给一个随规模收紧的下限，多余部分靠滚轮平移看。
  const load = relState.nodes.length;
  const floor = load > 40 ? 0.62 : load > 25 ? 0.72 : 0.5;
  relState.zoom = Math.max(floor, Math.min(2.2, Math.min((width - pad * 2) / spanX, (height - pad * 2) / spanY)));
}

function paintRelations(): void {
  const svg = document.getElementById("rel-svg");
  if (!svg) return;
  const { width, height } = relViewport();
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const projections = new Map(relState.nodes.map((node) => [node.key, relProject(node, width, height)]));
  // 悬停时的邻域：亮该节点的边，其余节点压暗。
  const neighbours = new Set<string>();
  if (relState.hot) {
    for (const edge of relState.edges) {
      if (edge.from === relState.hot) neighbours.add(edge.to);
      else if (edge.to === relState.hot) neighbours.add(edge.from);
    }
  }

  const edgeMarkup = relState.edges
    .map((edge) => {
      const a = projections.get(edge.from);
      const b = projections.get(edge.to);
      if (!a || !b) return "";
      const hot = Boolean(relState.hot) && (edge.from === relState.hot || edge.to === relState.hot);
      const dim = Boolean(relState.hot) && !hot;
      const opacity = dim ? 0.04 : hot ? 0.95 : edge.kind === "depends" ? 0.4 : 0.14;
      return (
        `<line class="redge ${edge.kind}${hot ? " hot" : ""}"` +
        ` x1="${a.sx.toFixed(1)}" y1="${a.sy.toFixed(1)}"` +
        ` x2="${b.sx.toFixed(1)}" y2="${b.sy.toFixed(1)}"` +
        ` opacity="${opacity}" />`
      );
    })
    .join("");

  // 画家算法：远的先画，近的盖在上面。
  const nodeMarkup = [...relState.nodes]
    .sort((left, right) => {
      const a = projections.get(left.key)?.depth ?? 0;
      const b = projections.get(right.key)?.depth ?? 0;
      return b - a;
    })
    .map((node) => {
      const projection = projections.get(node.key);
      if (!projection) return "";
      const hot = relState.hot === node.key || neighbours.has(node.key);
      const dim = Boolean(relState.hot) && !hot;
      return relNodeMarkup(node, projection, hot, dim);
    })
    .join("");

  svg.innerHTML = edgeMarkup + nodeMarkup;
  const workCount = relState.nodes.filter((node) => node.kind === "work").length;
  const moduleCount = relState.nodes.length - workCount;
  byId("relations-source").textContent =
    `${ui.root}/.agent · ${workCount} 个工作项` +
    (moduleCount > 0 ? ` · ${moduleCount} 个模块` : "") +
    ` · ${relState.edges.length} 条关系`;
}

/** 状态/阶段分布条形图：只数可见工作项，和图保持一致。 */
function relBars(targetId: string, counts: Map<string, number>, colors: Map<string, string>): void {
  const container = byId(targetId);
  clear(container);
  const entries = [...counts.entries()].sort((left, right) => right[1] - left[1]);
  if (entries.length === 0) {
    container.appendChild(element("p", "muted small", "没有数据。"));
    return;
  }
  const max = Math.max(...entries.map((entry) => entry[1]));
  for (const [label, count] of entries) {
    const row = element("div", "bar-row");
    row.appendChild(element("span", "bar-label", label));
    const track = element("span", "bar-track");
    const fill = element("span", "bar-fill");
    fill.style.width = `${Math.round((count / max) * 100)}%`;
    const color = colors.get(label);
    if (color) fill.style.background = color;
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(element("span", "bar-count", String(count)));
    container.appendChild(row);
  }
}

function renderRelStats(): void {
  const items = relState.nodes
    .filter((node) => node.kind === "work")
    .map((node) => node.item as WorkItemView);
  const states = new Map<string, number>();
  const phases = new Map<string, number>();
  const colors = new Map<string, string>();
  for (const item of items) {
    states.set(item.state_label, (states.get(item.state_label) ?? 0) + 1);
    colors.set(item.state_label, stateColor(item.state));
    phases.set(item.phase_label, (phases.get(item.phase_label) ?? 0) + 1);
  }
  relBars("rel-state-bars", states, colors);
  relBars("rel-phase-bars", phases, new Map());
}

function describeRelNode(key: string): string {
  const node = relState.nodes.find((candidate) => candidate.key === key);
  if (!node) return "";
  if (node.kind === "module") {
    const module = node.module as ModuleView;
    return (
      `<b>模块 · ${escapeHtml(module.name)}</b><br>` +
      `源码：${escapeHtml(module.path || "—")}<br>` +
      `工作项：${escapeHtml(module.work_ids.join("、"))}`
    );
  }
  const item = node.item as WorkItemView;
  const depends = item.relations.depends_on.filter((dep) => !dep.missing).map((dep) => dep.work_id);
  const dependents = item.relations.dependents.map((dep) => dep.work_id);
  const related = item.relations.related.map((dep) => dep.work_id);
  const modules = (ui.status?.modules ?? [])
    .filter((module) => module.work_ids.includes(item.work_id))
    .map((module) => module.name);
  const tasks = item.tasks;
  const total = tasks.pending + tasks.in_progress + tasks.done + tasks.blocked;
  return (
    `<b>${escapeHtml(item.work_id)} · ${escapeHtml(item.name)}</b><br>` +
    `${escapeHtml(item.phase_label)} · ${escapeHtml(item.state_label)} · ${total > 0 ? `任务 ${tasks.done}/${total}` : "无任务"}<br>` +
    `依赖：${depends.length ? escapeHtml(depends.join("、")) : "无"}<br>` +
    `被依赖：${dependents.length ? escapeHtml(dependents.join("、")) : "无"}<br>` +
    `关联：${related.length ? escapeHtml(related.join("、")) : "无"}<br>` +
    `模块：${modules.length ? escapeHtml(modules.join("、")) : "索引里没有登记"}` +
    `<br><span class="bad-text">点一下进入该工作项</span>`
  );
}

function renderRelations(): void {
  if (!ui.status) return;
  const signature = [
    ui.status.project_root,
    ui.status.work_items.length,
    relState.showDepends,
    relState.showRelated,
    relState.showModules,
    relState.onlyAttention,
    (ui.status.modules ?? []).length,
  ].join("|");
  if (signature !== relState.signature) {
    relState.signature = signature;
    buildRelModels();
    fitRelations();
  }
  paintRelations();
  renderRelStats();
}

function startSpin(): void {
  if (relState.spinRaf) return;
  const step = (): void => {
    if (!relState.spin) {
      relState.spinRaf = 0;
      return;
    }
    relState.yaw += 0.0045;
    paintRelations();
    relState.spinRaf = requestAnimationFrame(step);
  };
  relState.spinRaf = requestAnimationFrame(step);
}

function stopSpin(): void {
  if (relState.spinRaf) cancelAnimationFrame(relState.spinRaf);
  relState.spinRaf = 0;
}

async function loadRelations(): Promise<void> {
  const root = ui.root || (await window.api.lastProject()) || "";
  if (!root) {
    toast("先选择一个项目，再打开关系图谱。");
    return;
  }
  ui.root = root;
  byId("project-path").textContent = root;
  if (!ui.status) {
    const result = await window.api.loadStatus(root);
    if (!result.ok || !result.data) {
      toast(result.error || "无法读取项目状态");
      return;
    }
    ui.status = result.data;
    renderSidebar();
  }
  showView("relations");
  renderRelations();
}

function bindRelations(): void {
  const container = byId("relations-graph");

  container.addEventListener("pointerdown", (event) => {
    if ((event.target as Element).closest(".rnode")) return;
    relState.dragging = true;
    // 每次按下都是一次新手势：上一次拖拽的抑制标记必须清掉，否则下一次点击会被吞。
    relState.moved = false;
    relState.lastX = event.clientX;
    relState.lastY = event.clientY;
    container.classList.add("dragging");
    if (relState.spin) {
      relState.spin = false;
      stopSpin();
      byId("rel-spin").classList.remove("active");
    }
    try {
      container.setPointerCapture(event.pointerId);
    } catch {
      // 合成事件没有活动指针，捕获失败不影响拖动。
    }
    event.preventDefault();
  });

  container.addEventListener("pointermove", (event) => {
    if (!relState.dragging) return;
    const dx = event.clientX - relState.lastX;
    const dy = event.clientY - relState.lastY;
    relState.lastX = event.clientX;
    relState.lastY = event.clientY;
    if (Math.abs(dx) + Math.abs(dy) > 2) relState.moved = true;
    relState.yaw += dx * 0.006;
    // 俯仰限制在 ±80°，越过极点视角会翻转。
    relState.pitch = Math.max(-1.4, Math.min(1.4, relState.pitch + dy * 0.006));
    paintRelations();
  });

  const endDrag = (event: PointerEvent): void => {
    relState.dragging = false;
    // 抑制标记只对紧接着的那次 click 有效（拖拽结束浏览器会补发 click）；
    // 用时间窗口而不是布尔位，免得之后正常点击被永久吞掉。
    relState.suppressClickUntil = relState.moved ? Date.now() + 250 : 0;
    container.classList.remove("dragging");
    try {
      if (container.hasPointerCapture(event.pointerId)) container.releasePointerCapture(event.pointerId);
    } catch {
      // 同上：合成事件无需释放。
    }
  };
  container.addEventListener("pointerup", endDrag);
  container.addEventListener("pointercancel", endDrag);

  container.addEventListener("wheel", (event) => {
    event.preventDefault();
    relState.zoom = Math.max(0.35, Math.min(3.2, relState.zoom * (event.deltaY < 0 ? 1.1 : 1 / 1.1)));
    paintRelations();
  }, { passive: false });

  // 悬停：mousemove 负责在节点间移动，mouseover 负责进入画布的第一步（合成事件只有后者）。
  const updateHover = (event: Event): void => {
    if (relState.dragging) return;
    const node = (event.target as Element).closest(".rnode");
    const key = node ? (node.getAttribute("data-rel-key") ?? "") : "";
    if (key === relState.hot) return;
    relState.hot = key;
    paintRelations();
    if (key) byId("rel-detail").innerHTML = describeRelNode(key);
  };
  container.addEventListener("mousemove", updateHover);
  container.addEventListener("mouseover", updateHover);

  container.addEventListener("mouseleave", () => {
    if (!relState.hot) return;
    relState.hot = "";
    paintRelations();
  });

  container.addEventListener("click", (event) => {
    // 拖拽结束时浏览器会补发一次 click，那一次不该当成"选中节点"。
    if (relState.suppressClickUntil && Date.now() <= relState.suppressClickUntil) {
      relState.suppressClickUntil = 0;
      relState.moved = false;
      return;
    }
    const node = (event.target as Element).closest("[data-work-id]");
    if (!node) return;
    const workId = node.getAttribute("data-work-id") ?? "";
    const item = (ui.status?.work_items ?? []).find((candidate) => candidate.work_id === workId);
    if (!item) return;
    showView("project");
    void selectWorkItem(item);
  });

  container.addEventListener("dblclick", (event) => {
    if ((event.target as Element).closest(".rnode")) return;
    relState.yaw = 0.62;
    relState.pitch = -0.34;
    fitRelations();
    paintRelations();
  });

  const toggle = (id: string, key: "showDepends" | "showRelated" | "showModules" | "onlyAttention") => {
    byId(id).addEventListener("click", () => {
      relState[key] = !relState[key];
      byId(id).classList.toggle("active", relState[key]);
      relState.signature = "";
      renderRelations();
    });
  };
  toggle("rel-depends", "showDepends");
  toggle("rel-related", "showRelated");
  toggle("rel-modules", "showModules");
  toggle("rel-attention", "onlyAttention");

  byId("rel-spin").addEventListener("click", () => {
    relState.spin = !relState.spin;
    byId("rel-spin").classList.toggle("active", relState.spin);
    if (relState.spin) startSpin();
    else stopSpin();
  });
  byId("rel-flat").addEventListener("click", () => {
    relState.pitch = 0;
    relState.yaw = 0;
    byId("rel-flat").classList.toggle("active", true);
    paintRelations();
  });
  byId("rel-zoom-in").addEventListener("click", () => {
    relState.zoom = Math.min(3.2, relState.zoom * 1.18);
    paintRelations();
  });
  byId("rel-zoom-out").addEventListener("click", () => {
    relState.zoom = Math.max(0.35, relState.zoom / 1.18);
    paintRelations();
  });
  byId("rel-reset").addEventListener("click", () => {
    relState.yaw = 0.62;
    relState.pitch = -0.34;
    byId("rel-flat").classList.remove("active");
    fitRelations();
    paintRelations();
  });
}

/* ---------- 项目资料视图 ---------- */

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function loadResources(): Promise<void> {
  const root = ui.root || (await window.api.lastProject()) || "";
  if (!root) {
    toast("先选择一个项目，再打开项目资料。");
    return;
  }
  ui.root = root;
  byId("project-path").textContent = root;
  showView("resources");
  byId("resources-count").textContent = "读取中";
  const result = await window.api.loadResources(root);
  if (!result.ok || !result.data) {
    byId("resources-count").textContent = "读取失败";
    toast(result.error || "无法读取项目资料");
    return;
  }
  ui.resources = result.data;
  ui.resourceFile = null;
  renderResources();
  renderResourceDocument(null);
}

function renderResources(): void {
  const groups = ui.resources ?? [];
  const container = byId("resource-groups");
  clear(container);
  const total = groups.reduce((sum, group) => sum + group.files.length, 0);
  byId("resources-source").textContent = `${ui.root}/.agent`;
  byId("resources-count").textContent = `${total} 个文件 / ${groups.length} 个分类`;

  for (const group of groups) {
    const section = element("section", "resource-group");
    const head = element("div", "resource-group-head");
    head.appendChild(element("h4", undefined, group.label));
    head.appendChild(element("span", undefined, group.files.length ? `${group.files.length}` : "空"));
    section.appendChild(head);
    section.appendChild(element("p", "resource-group-hint", group.hint));

    if (group.files.length === 0) {
      section.appendChild(element("p", "resource-empty", "这个位置还没有内容。"));
      container.appendChild(section);
      continue;
    }
    const list = element("ul", "resource-files");
    for (const file of group.files) {
      const li = element("li", "resource-file");
      li.dataset.resourcePath = file.path;
      if (ui.resourceFile && ui.resourceFile.path === file.path) li.classList.add("selected");
      li.appendChild(element("span", "file-label", file.label));
      li.appendChild(
        element(
          "span",
          "file-meta",
          `${humanSize(file.size)} · ${shortDate(file.gitDate || file.mtime)}`,
        ),
      );
      list.appendChild(li);
    }
    section.appendChild(list);
    container.appendChild(section);
  }
}

async function renderResourceDocument(file: ResourceFile | null): Promise<void> {
  const title = byId("resource-title");
  const content = byId("resource-content");
  const frontmatter = byId("resource-frontmatter");
  const dates = byId("resource-dates");
  const reveal = byId<HTMLButtonElement>("resource-reveal");
  clear(content);
  clear(frontmatter);
  dates.textContent = "";
  if (!file) {
    title.textContent = "未选择文件";
    reveal.disabled = true;
    content.appendChild(element("p", "muted", "点左边的文件在这里查看内容。"));
    return;
  }
  ui.resourceFile = file;
  title.textContent = file.label;
  title.title = file.path;
  reveal.disabled = false;
  const parts: string[] = [];
  if (file.gitDate) parts.push(`Git ${formatDate(file.gitDate)}`);
  if (file.mtime) parts.push(`修改 ${formatDate(file.mtime)}`);
  parts.push(humanSize(file.size));
  dates.textContent = parts.join(" · ");

  const result = await window.api.readDocument(file.path);
  if (!result.ok || !result.data) {
    content.appendChild(element("p", "issue error", result.error || "无法读取文件"));
    return;
  }
  if (file.path.toLowerCase().endsWith(".html")) {
    // 理解材料是完整 HTML，这里只提示它不替代源码，不当页面加载
    content.appendChild(
      element("p", "muted", "这是一份 HTML 理解材料。用「在资源管理器中显示」打开，或用浏览器直接打开它。"),
    );
    return;
  }
  if (result.data.frontmatter.length > 0) {
    const table = element("table");
    for (const entry of result.data.frontmatter) {
      const row = element("tr");
      row.appendChild(element("td", undefined, entry.key));
      row.appendChild(element("td", undefined, entry.value));
      table.appendChild(row);
    }
    frontmatter.appendChild(table);
  }
  content.innerHTML = result.data.html;
}

/* ---------- 工作区视图 ---------- */

function showView(view: "workspace" | "project" | "resources" | "relations"): void {
  ui.view = view;
  byId("workspace-view").classList.toggle("hidden", view !== "workspace");
  byId("resources-view").classList.toggle("hidden", view !== "resources");
  byId("relations-view").classList.toggle("hidden", view !== "relations");
  byId("detail-body").classList.toggle("hidden", view !== "project" || !ui.selected);
  byId("empty-state").classList.toggle("hidden", view !== "project" || Boolean(ui.selected));
  document.body.classList.toggle("in-workspace", view === "workspace");
  document.body.classList.toggle("in-resources", view === "resources");
  document.body.classList.toggle("in-relations", view === "relations");
}

async function loadWorkspace(): Promise<void> {
  const root = ui.root || (await window.api.lastProject()) || "";
  if (!root) {
    toast("先选择一个项目，再打开工作区。");
    return;
  }
  ui.root = root;
  byId("project-path").textContent = root;
  showView("workspace");
  byId("workspace-state").textContent = "读取中";
  const result = await window.api.loadWorkspace(root);
  if (!result.ok || !result.data) {
    byId("workspace-state").textContent = "读取失败";
    toast(result.error || "无法读取工作区");
    return;
  }
  ui.workspace = result.data;
  renderWorkspace();
}

function renderWorkspace(): void {
  const workspace = ui.workspace;
  const list = byId("workspace-list");
  clear(list);
  if (!workspace) return;
  byId("workspace-source").textContent =
    workspace.source === "index"
      ? `清单来自工作区索引：${workspace.sourcePath}`
      : `清单来自应用记录（没有 PROJECT-INDEX.md）：${workspace.sourcePath}`;
  byId("workspace-state").textContent = `${workspace.totals.projects} 个项目`;

  const totals = byId("workspace-totals");
  clear(totals);
  const pairs: Array<[string, string]> = [
    ["项目", String(workspace.totals.projects)],
    ["工作项", String(workspace.totals.workItems)],
    ["需要处理", String(workspace.totals.attention)],
    ["待补签工件", String(workspace.totals.unsigned)],
    ["缺证据验收", String(workspace.totals.acceptanceGaps)],
  ];
  for (const [label, value] of pairs) {
    const block = element("div");
    block.appendChild(element("b", undefined, value));
    block.appendChild(element("span", undefined, label));
    totals.appendChild(block);
  }

  if (workspace.projects.length === 0) {
    list.appendChild(
      element(
        "li",
        "muted",
        "清单里没有可用项目。用「选择项目」打开一个，或在该目录的 .agent/PROJECT-INDEX.md 里登记。",
      ),
    );
    return;
  }

  for (const project of workspace.projects) {
    const card = element("li", "project-card");
    card.dataset.projectRoot = project.root;
    if (samePath(project.root, ui.root)) card.classList.add("current");
    if (!project.ok) card.classList.add("broken");

    const head = element("div", "card-head");
    head.appendChild(element("span", "card-name", project.name));
    const headRight = element("div", "card-head-right");
    headRight.appendChild(
      element(
        "span",
        `badge ${project.ok && project.workItems > 0 ? "ready" : "not_started"}`,
        project.ok ? `${project.workItems} 个工作项` : "读取失败",
      ),
    );
    if (workspace.source === "app") {
      // 索引来源的清单由 PROJECT-INDEX.md 管，这里只让用户清理应用自己记住的条目。
      const forget = element("button", "button small", "移出清单");
      forget.type = "button";
      forget.addEventListener("click", (event) => {
        event.stopPropagation();
        void (async () => {
          await window.api.forgetProject(project.root);
          await loadWorkspace();
        })();
      });
      headRight.appendChild(forget);
    }
    head.appendChild(headRight);
    card.appendChild(head);
    card.appendChild(element("p", "card-path", project.root));

    if (project.ok) {
      const metrics = element("div", "card-metrics");
      const metric = (label: string, value: string, hot = false) => {
        const block = element("div", hot && value !== "0" ? "hot" : undefined);
        block.appendChild(element("b", undefined, value));
        block.appendChild(element("span", undefined, label));
        metrics.appendChild(block);
      };
      metric("需要处理", String(project.attention));
      metric("进行中", String(project.running));
      metric("已完成", String(project.done));
      metric("待补签", String(project.unsigned), true);
      metric("缺证据验收", String(project.acceptanceGaps), true);
      card.appendChild(metrics);

      const foot = element("div", "card-foot");
      foot.appendChild(
        element(
          "span",
          `chip ${project.rulesReady ? "ok" : "warn"}`,
          project.rulesReady ? "规范已确认" : "规范待确认",
        ),
      );
      if (project.unsignedItems > 0) {
        foot.appendChild(element("span", "chip warn", `${project.unsignedItems} 个工作项待补签`));
      }
      if (project.gitStatus && project.gitStatus !== "clean") {
        foot.appendChild(element("span", "chip", `Git ${project.gitStatus}`));
      }
      foot.appendChild(
        element(
          "span",
          "muted small",
          project.lastActivity
            ? `最后活动（${project.lastActivitySource === "git" ? "提交" : "记录"}）${formatDate(project.lastActivity)}`
            : "没有提交记录，也没有更新历史",
        ),
      );
      card.appendChild(foot);
    } else {
      card.appendChild(element("p", "card-note", project.error));
    }

    card.addEventListener("click", () => {
      void loadProject(project.root);
    });
    list.appendChild(card);
  }
}

/* ---------- 需求追踪图 ---------- */

const CHIP_W = 190;
const CHIP_H = 30;
const CHIP_GAP = 8;
const CHIP_PER_ROW = 4;
const TASK_W = 176;
const TASK_H = 56;
const TASK_GAP_X = 14;
const TASK_GAP_Y = 12;
const TASK_PER_ROW = 4;
/** 芯片里 id 之后留给标题的宽度：约 11 个中文字，超了就截断。 */
const CHIP_TITLE_CHARS = 10;
/** 分层之间的留白要放得下连线。 */
const BAND_GAP = 46;

interface TraceNode {
  id: string;
  kind: "REQ" | "AC" | "TASK";
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  state: string;
  gap: boolean;
  bad: boolean;
}

interface TraceEdge {
  from: string;
  to: string;
  kind: "maps" | "depends" | "link";
}

interface TraceLayout {
  nodes: TraceNode[];
  edges: TraceEdge[];
  width: number;
  height: number;
}

function traceId(value: string): string {
  return /^\d+$/.test(value) ? String(Number(value)).padStart(3, "0") : value;
}

function layoutTrace(trace: TraceabilityView): TraceLayout {
  const nodes: TraceNode[] = [];
  const edges: TraceEdge[] = [];
  const withoutEvidence = new Set(trace.acceptance_without_evidence);
  const unmapped = new Set(trace.unmapped_tasks);

  const placeChips = (
    definitions: TraceDefinition[],
    kind: "REQ" | "AC",
    top: number,
  ): number => {
    definitions.forEach((definition, index) => {
      const column = index % CHIP_PER_ROW;
      const row = Math.floor(index / CHIP_PER_ROW);
      nodes.push({
        id: definition.id,
        kind,
        x: GRAPH_PAD + column * (CHIP_W + CHIP_GAP),
        y: top + row * (CHIP_H + CHIP_GAP),
        w: CHIP_W,
        h: CHIP_H,
        title: definition.title,
        state: "",
        gap: kind === "AC" && withoutEvidence.has(definition.id),
        bad: false,
      });
    });
    const rows = Math.max(1, Math.ceil(definitions.length / CHIP_PER_ROW));
    return top + rows * (CHIP_H + CHIP_GAP);
  };

  const requirementBottom = placeChips(trace.requirements, "REQ", GRAPH_PAD);
  const acceptanceBottom = placeChips(trace.acceptance, "AC", requirementBottom + BAND_GAP);
  const taskTop = acceptanceBottom + BAND_GAP;
  trace.tasks.forEach((task, index) => {
    const column = index % TASK_PER_ROW;
    const row = Math.floor(index / TASK_PER_ROW);
    nodes.push({
      id: task.id,
      kind: "TASK",
      x: GRAPH_PAD + column * (TASK_W + TASK_GAP_X),
      y: taskTop + row * (TASK_H + TASK_GAP_Y),
      w: TASK_W,
      h: TASK_H,
      title: task.title,
      state: task.state,
      gap: unmapped.has(task.id),
      bad: task.state === "blocked",
    });
  });

  const known = new Set(nodes.map((node) => node.id));
  for (const task of trace.tasks) {
    for (const target of task.maps_to) {
      // 引用了未定义的 id 时不画边，改由摘要行报告
      if (known.has(target)) edges.push({ from: task.id, to: target, kind: "maps" });
    }
    for (const dependency of task.depends_on) {
      if (known.has(dependency)) edges.push({ from: task.id, to: dependency, kind: "depends" });
    }
  }
  for (const pair of trace.requirement_acceptance_links) {
    const [requirement, acceptance] = pair;
    if (known.has(requirement) && known.has(acceptance)) {
      edges.push({ from: requirement, to: acceptance, kind: "link" });
    }
  }

  const taskRows = Math.max(1, Math.ceil(trace.tasks.length / TASK_PER_ROW));
  const width =
    GRAPH_PAD * 2 +
    Math.max(CHIP_PER_ROW * (CHIP_W + CHIP_GAP), TASK_PER_ROW * (TASK_W + TASK_GAP_X)) +
    EDGE_MARGIN;
  const height = taskTop + taskRows * (TASK_H + TASK_GAP_Y) + GRAPH_PAD;
  return { nodes, edges, width, height };
}

function traceNodeMarkup(node: TraceNode): string {
  const classes = ["node", node.kind.toLowerCase()];
  if (node.gap) classes.push("gap");
  if (node.bad) classes.push("bad");
  const limit = node.kind === "TASK" ? 14 : CHIP_TITLE_CHARS;
  const title = node.title.length > limit ? `${node.title.slice(0, limit)}…` : node.title;
  const label = node.id;
  if (node.kind === "TASK") {
    return (
      `<g class="${classes.join(" ")}" data-node="${attr(node.id)}">` +
      `<rect class="task-box" x="${node.x}" y="${node.y}" width="${node.w}" height="${node.h}" rx="8" />` +
      `<rect x="${node.x}" y="${node.y}" width="3" height="${node.h}" rx="1.5" fill="${stateColor(node.state)}" />` +
      `<text class="task-id" x="${node.x + 12}" y="${node.y + 17}">${escapeHtml(node.id)} · ${escapeHtml(node.state)}</text>` +
      `<text class="task-title" x="${node.x + 12}" y="${node.y + 35}">${escapeHtml(title)}</text>` +
      `<text class="task-state" x="${node.x + 12}" y="${node.y + 49}">${escapeHtml(node.gap ? "未映射到需求" : "")}</text>` +
      `</g>`
    );
  }
  return (
    `<g class="${classes.join(" ")}" data-node="${attr(node.id)}">` +
    `<rect class="chip-box" x="${node.x}" y="${node.y}" width="${node.w}" height="${node.h}" rx="7" />` +
    `<text class="chip-label" x="${node.x + 10}" y="${node.y + 19}">${escapeHtml(label)}</text>` +
    `<text class="chip-title" x="${node.x + 68}" y="${node.y + 19}">${escapeHtml(title)}</text>` +
    `</g>`
  );
}

function traceEdgeMarkup(edge: TraceEdge, nodes: Map<string, TraceNode>): string {
  const from = nodes.get(edge.from);
  const to = nodes.get(edge.to);
  if (!from || !to) return "";
  const fromCenter = { x: from.x + from.w / 2, y: from.y + from.h / 2 };
  const toCenter = { x: to.x + to.w / 2, y: to.y + to.h / 2 };
  let start = fromCenter;
  let end = toCenter;
  if (Math.abs(fromCenter.y - toCenter.y) > from.h) {
    // 跨层：从源的上/下边出发，到目标的下/上边，避免线穿过节点
    const upward = toCenter.y < fromCenter.y;
    start = { x: fromCenter.x, y: upward ? from.y : from.y + from.h };
    end = { x: toCenter.x, y: upward ? to.y + to.h : to.y };
  } else {
    const rightward = toCenter.x > fromCenter.x;
    start = { x: rightward ? from.x + from.w : from.x, y: fromCenter.y };
    end = { x: rightward ? to.x : to.x + to.w, y: toCenter.y };
  }
  const bend = Math.abs(end.y - start.y) / 2 + 12;
  const control = `${start.x} ${start.y + (end.y > start.y ? bend : -bend)}, ${end.x} ${end.y - (end.y > start.y ? bend : -bend)}`;
  return (
    `<path class="edge ${edge.kind}" data-from="${attr(edge.from)}" data-to="${attr(edge.to)}" ` +
    `d="M ${start.x} ${start.y} C ${control}, ${end.x} ${end.y}" />`
  );
}

function renderTraceSummary(trace: TraceabilityView): void {
  const summary = byId("trace-summary");
  clear(summary);
  const counts = [
    `需求 ${trace.requirements.length}`,
    `验收 ${trace.acceptance.length}`,
    `任务 ${trace.tasks.length}`,
    `直连边 ${trace.requirement_acceptance_links.length}`,
  ];
  for (const value of counts) summary.appendChild(element("span", "chip", value));
  if (trace.unmapped_tasks.length > 0) {
    summary.appendChild(
      element("span", "chip warn", `未映射到需求的任务 ${trace.unmapped_tasks.length}：${trace.unmapped_tasks.join("、")}`),
    );
  }
  if (trace.acceptance_without_evidence.length > 0) {
    summary.appendChild(
      element(
        "span",
        "chip warn",
        `无结构化证据的验收 ${trace.acceptance_without_evidence.length}/${trace.acceptance.length}：` +
          trace.acceptance_without_evidence.join("、"),
      ),
    );
  }
  if (trace.undefined_refs.length > 0) {
    summary.appendChild(
      element("span", "chip bad", `引用了未定义的需求：${trace.undefined_refs.join("、")}`),
    );
  }
  if (trace.requirements.length === 0 && trace.tasks.length === 0) {
    summary.appendChild(element("span", "chip", "这个工作项还没有 REQ/AC/TASK 标识"));
  }
}

function traceDetail(trace: TraceabilityView, id: string): string {
  const requirement = trace.requirements.find((item) => item.id === id);
  const acceptance = trace.acceptance.find((item) => item.id === id);
  const task = trace.tasks.find((item) => item.id === id);
  const implementsIt = trace.tasks.filter((item) => item.maps_to.includes(id)).map((item) => item.id);
  const coveredBy = trace.tasks
    .filter((item) => item.depends_on.includes(id))
    .map((item) => item.id);
  if (requirement) {
    const linked = trace.requirement_acceptance_links
      .filter((pair) => pair[0] === id)
      .map((pair) => pair[1]);
    return (
      `<b>${escapeHtml(requirement.id)} ${escapeHtml(requirement.title)}</b><br>` +
      `被任务实现：${implementsIt.length ? implementsIt.join("、") : "<span class=\"muted-text\">没有任务声明实现它</span>"}<br>` +
      `来源覆盖表直连的验收：${linked.length ? linked.join("、") : "<span class=\"muted-text\">没有来源覆盖表，REQ 与 AC 只能通过任务间接关联</span>"}`
    );
  }
  if (acceptance) {
    const gap = trace.acceptance_without_evidence.includes(id);
    return (
      `<b>${escapeHtml(acceptance.id)} ${escapeHtml(acceptance.title)}</b><br>` +
      `由任务覆盖：${implementsIt.length ? implementsIt.join("、") : "<span class=\"muted-text\">没有任务声明覆盖它</span>"}<br>` +
      `结构化证据：${gap ? "<span class=\"bad-text\">缺少——验证报告里没有覆盖它的证据表行</span>" : "已有"}`
    );
  }
  if (task) {
    return (
      `<b>${escapeHtml(task.id)} ${escapeHtml(task.title)}</b> · ${escapeHtml(task.state)}<br>` +
      `对应：${task.maps_to.length ? task.maps_to.join("、") : "<span class=\"muted-text\">没有写对应的 REQ/AC</span>"}` +
      (task.legacy.length ? `（其中 ${task.legacy.join("、")} 标为旧版）` : "") +
      `<br>依赖：${task.depends_on.length ? task.depends_on.join("、") : "无"}` +
      (coveredBy.length ? `<br>被这些任务依赖：${coveredBy.join("、")}` : "")
    );
  }
  return "未找到该节点。";
}

function highlightTrace(activeId: string): void {
  const container = byId("trace-graph");
  const neighbours = new Set<string>();
  for (const edge of Array.from(container.querySelectorAll<SVGPathElement>(".edge"))) {
    const from = edge.getAttribute("data-from") ?? "";
    const to = edge.getAttribute("data-to") ?? "";
    const hot = !activeId || from === activeId || to === activeId;
    edge.classList.toggle("hot", Boolean(activeId) && hot);
    if (activeId && hot) {
      neighbours.add(from === activeId ? to : from);
    }
  }
  for (const node of Array.from(container.querySelectorAll<SVGGElement>(".node"))) {
    const id = node.getAttribute("data-node") ?? "";
    node.classList.toggle("hot", Boolean(activeId) && (id === activeId || neighbours.has(id)));
    node.classList.toggle("dim", Boolean(activeId) && id !== activeId && !neighbours.has(id));
  }
}

function renderTrace(): void {
  const container = byId("trace-graph");
  clear(container);
  const detail = byId("trace-detail");
  if (!ui.selected) {
    detail.textContent = "点一个节点查看它的关系。";
    return;
  }
  const trace = ui.selected.traceability;
  renderTraceSummary(trace);
  detail.textContent = "点一个节点查看它的关系。";
  if (trace.requirements.length === 0 && trace.acceptance.length === 0 && trace.tasks.length === 0) {
    container.appendChild(element("p", "muted", "这个工作项还没有可追踪的 REQ/AC/TASK。"));
    return;
  }
  const { nodes, edges, width, height } = layoutTrace(trace);
  const byNodeId = new Map(nodes.map((node) => [node.id, node]));
  container.innerHTML =
    `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
    `<g class="trace-edges">${edges.map((edge) => traceEdgeMarkup(edge, byNodeId)).join("")}</g>` +
    `<g class="trace-nodes">${nodes.map(traceNodeMarkup).join("")}</g>` +
    `</svg>`;
}



function renderOverview(): void {
  renderGates();
  renderTrace();
  renderGraph();
}

function renderArtifacts(): void {
  const list = byId("artifact-list");
  clear(list);
  for (const artifact of ui.artifacts) {
    const li = element("li", `artifact${artifact.exists ? "" : " missing"}`);
    if (ui.selectedArtifact && ui.selectedArtifact.key === artifact.key) li.classList.add("selected");

    const label = element("div", "label");
    label.appendChild(element("span", undefined, artifact.label));
    label.appendChild(element("span", `badge ${artifact.status}`, artifact.status || "缺失"));
    li.appendChild(label);

    if (artifact.acceptedBy) {
      li.appendChild(
        element("div", "signer signed", `验收：${artifact.acceptedBy} · ${formatDate(artifact.acceptedAt)}`),
      );
    } else if (artifact.approvedBy) {
      const role = artifact.approverRole ? `（${artifact.approverRole}）` : "";
      li.appendChild(
        element("div", "signer signed", `签署：${artifact.approvedBy}${role} · ${formatDate(artifact.approvedAt)}`),
      );
    } else if (artifact.exists && artifact.status === "approved") {
      li.appendChild(element("div", "signer unsigned", "已批准但未签署"));
    }
    const date = artifact.gitDate || artifact.mtime;
    if (artifact.exists && date) {
      li.appendChild(element("div", "signer", `${artifact.gitDate ? "Git" : "修改"} ${formatDate(date)}`));
    }
    li.addEventListener("click", () => {
      void selectArtifact(artifact);
    });
    list.appendChild(li);
  }
}

async function selectArtifact(artifact: ArtifactView): Promise<void> {
  ui.selectedArtifact = artifact;
  renderArtifacts();
  if (!artifact.exists) {
    renderDocument(null, `文件不存在：${artifact.path}`);
    return;
  }
  const result = await window.api.readDocument(artifact.path);
  if (!result.ok || !result.data) {
    renderDocument(null, result.error || "无法读取文件");
    return;
  }
  renderDocument(result.data);
}

/** 数据面板里点 *.md 路径：认识的工件走工件卡片，不认识的临时构造一张。 */
function openPath(absolute: string): void {
  selectTab("read");
  const normalized = absolute.split("\\").join("/").toLowerCase();
  const known = ui.artifacts.find(
    (artifact) => artifact.path.split("\\").join("/").toLowerCase() === normalized,
  );
  if (known) {
    void selectArtifact(known);
    return;
  }
  void selectArtifact({
    key: "external",
    label: "文件",
    path: absolute,
    status: "",
    approvedBy: "",
    approvedAt: "",
    approverRole: "",
    acceptedBy: "",
    acceptedAt: "",
    gitDate: "",
    mtime: "",
    exists: true,
  });
}

function renderDocument(document_: DocumentView | null, error?: string): void {
  const title = byId("doc-title");
  const content = byId("doc-content");
  const frontmatter = byId("doc-frontmatter");
  const dates = byId("doc-dates");
  clear(content);
  clear(frontmatter);
  dates.textContent = "";
  const reveal = byId<HTMLButtonElement>("reveal");

  if (error) {
    title.textContent = ui.selectedArtifact ? ui.selectedArtifact.label : "文档";
    content.appendChild(element("p", "issue error", error));
    reveal.disabled = true;
    return;
  }
  if (!document_ || !ui.selectedArtifact) {
    title.textContent = "—";
    reveal.disabled = true;
    return;
  }
  const artifact = ui.selectedArtifact;
  title.textContent = `${artifact.label} · ${shortPath(artifact.path)}`;
  title.title = artifact.path;
  reveal.disabled = false;

  const parts: string[] = [];
  if (artifact.gitDate) parts.push(`Git ${formatDate(artifact.gitDate)}`);
  if (artifact.mtime) parts.push(`修改 ${formatDate(artifact.mtime)}`);
  if (artifact.approvedAt) parts.push(`签署 ${formatDate(artifact.approvedAt)}`);
  if (artifact.acceptedAt) parts.push(`验收 ${formatDate(artifact.acceptedAt)}`);
  dates.textContent = parts.join(" · ");

  if (document_.frontmatter.length > 0) {
    const table = element("table");
    for (const entry of document_.frontmatter) {
      const row = element("tr");
      row.appendChild(element("td", undefined, entry.key));
      row.appendChild(element("td", undefined, entry.value));
      table.appendChild(row);
    }
    frontmatter.appendChild(table);
  }
  // CSP 已经禁掉脚本，这里的 HTML 只用于排版。
  content.innerHTML = document_.html;
  for (const link of Array.from(content.querySelectorAll("a[href]"))) {
    const href = link.getAttribute("href") ?? "";
    if (/^https?:\/\//i.test(href)) {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        void window.api.openExternal(href);
      });
    } else {
      link.removeAttribute("href");
    }
  }
}

/** 给 JSON 上色，并把 work_id 和 .md 路径变成可点跳转的锚。 */
function highlightJson(text: string): string {
  const token =
    /("(?:[^"\\]|\\.)*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|\b(true|false|null)\b/g;
  return escapeHtml(text).replace(
    token,
    (match: string, str?: string, colon?: string, num?: string, literal?: string) => {
      if (str !== undefined) {
        if (colon !== undefined) return `<span class="j-key">${str}</span>${colon}`;
        const inner = str.slice(1, -1);
        if (/^WORK-\d+$/i.test(inner)) {
          return `<span class="j-link" data-work="${attr(inner)}">${str}</span>`;
        }
        if (/\.md$/i.test(inner)) {
          return `<span class="j-link" data-file="${attr(inner)}">${str}</span>`;
        }
        return `<span class="j-str">${str}</span>`;
      }
      if (num !== undefined) return `<span class="j-num">${num}</span>`;
      if (literal !== undefined) return `<span class="j-lit">${literal}</span>`;
      return match;
    },
  );
}

function renderData(): void {
  const body = byId("data-body");
  if (!ui.status) {
    body.textContent = "尚未加载项目。";
    return;
  }
  body.innerHTML = highlightJson(JSON.stringify(ui.status, null, 2));
}

async function renderValidateTab(): Promise<void> {
  const body = byId("validate-body");
  clear(body);
  body.appendChild(element("p", "muted", "正在校验…"));
  const result = await window.api.loadValidate(ui.root);
  clear(body);
  if (!result.ok || !result.data) {
    body.appendChild(element("p", "issue error", result.error || "校验失败"));
    return;
  }
  ui.validate = result.data;
  const data = result.data;
  const verdict = element("p", `verdict ${data.valid ? "ok" : "bad"}`);
  verdict.textContent = data.valid
    ? "校验通过"
    : `校验未通过：${data.errors.length} 个错误、${data.warnings.length} 个警告`;
  body.appendChild(verdict);
  body.appendChild(element("p", "muted small", "普通校验保留兼容性警告；发布前用 --strict 把警告视为失败。"));
  const issue = (kind: "error" | "warning", entry: ValidateIssue) => {
    body.appendChild(
      element(
        "div",
        `issue ${kind}`,
        `${kind === "error" ? "错误" : "警告"}｜${entry.work_id ?? "项目"}：${entry.message}`,
      ),
    );
  };
  for (const entry of data.errors) issue("error", entry);
  for (const entry of data.warnings) issue("warning", entry);
  if (data.errors.length === 0 && data.warnings.length === 0) {
    body.appendChild(element("div", "issue", "未发现结构、引用或证据问题。"));
  }
}

async function renderHistoryTab(): Promise<void> {
  const body = byId("history-body");
  clear(body);
  body.appendChild(element("p", "muted", "正在读取更新历史…"));
  const result = await window.api.loadHistory(ui.root);
  clear(body);
  if (!result.ok || !result.data) {
    body.appendChild(element("p", "issue error", result.error || "无法读取更新历史"));
    return;
  }
  ui.history = result.data;
  if (result.data.length === 0) {
    body.appendChild(element("p", "muted", "当前没有更新记录。"));
    return;
  }
  for (const entry of result.data) {
    const wrapper = element("div", "history-entry");
    wrapper.appendChild(element("h4", undefined, entry.title));
    wrapper.appendChild(element("pre", undefined, entry.body));
    body.appendChild(wrapper);
  }
}

function selectTab(tab: string): void {
  ui.tab = tab;
  for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>(".tab"))) {
    button.classList.toggle("active", button.dataset.tab === tab);
  }
  for (const name of ["overview", "read", "validate", "history", "data"]) {
    byId(`tab-${name}`).classList.toggle("hidden", name !== tab);
  }
  if (tab === "overview") renderOverview();
  if (tab === "read" && !ui.selectedArtifact) void openPreferredArtifact();
  if (tab === "validate") void renderValidateTab();
  if (tab === "history") void renderHistoryTab();
  if (tab === "data") renderData();
}

/** 把窗口坐标换成世界坐标：拖动和缩放都要在同一套坐标里算。 */
function toWorld(event: { clientX: number; clientY: number }): { x: number; y: number } {
  const rect = byId("graph").getBoundingClientRect();
  return {
    x: (event.clientX - rect.left - graphState.tx) / graphState.k,
    y: (event.clientY - rect.top - graphState.ty) / graphState.k,
  };
}

function bindGraphInteraction(): void {
  const graph = byId("graph");

  graph.addEventListener("mouseover", (event) => {
    if (graphState.drag) return;
    const node = (event.target as Element).closest(".gnode");
    const key = node ? (node.getAttribute("data-key") ?? "") : "";
    highlightGraph(key);
    if (key) {
      byId("graph-detail").innerHTML = describeGraphNode(key);
    }
  });
  graph.addEventListener("mouseleave", () => {
    highlightGraph("");
    byId("graph-detail").textContent = "悬停节点看关系，拖节点调整位置，滚轮缩放，空白处拖动平移。";
  });

  graph.addEventListener("pointerdown", (event) => {
    const element = event.target as Element;
    const node = element.closest(".gnode");
    const world = toWorld(event);
    if (node) {
      const key = node.getAttribute("data-key") ?? "";
      const model = graphState.nodes.find((candidate) => candidate.key === key);
      if (!model) return;
      graphState.drag = {
        key,
        startX: world.x,
        startY: world.y,
        originX: model.x,
        originY: model.y,
        moved: false,
      };
    } else {
      graphState.pan = { x: event.clientX, y: event.clientY, tx: graphState.tx, ty: graphState.ty };
    }
    graph.setPointerCapture(event.pointerId);
    event.preventDefault();
  });

  graph.addEventListener("pointermove", (event) => {
    if (graphState.drag) {
      const world = toWorld(event);
      const model = graphState.nodes.find((candidate) => candidate.key === graphState.drag?.key);
      if (!model || !graphState.drag) return;
      const dx = world.x - graphState.drag.startX;
      const dy = world.y - graphState.drag.startY;
      if (Math.abs(dx) * graphState.k > 2 || Math.abs(dy) * graphState.k > 2) graphState.drag.moved = true;
      model.x = graphState.drag.originX + dx;
      model.y = graphState.drag.originY + dy;
      paintGraphPositions();
      highlightGraph(graphState.drag.key);
      return;
    }
    if (graphState.pan) {
      graphState.tx = graphState.pan.tx + (event.clientX - graphState.pan.x);
      graphState.ty = graphState.pan.ty + (event.clientY - graphState.pan.y);
      applyGraphTransform();
    }
  });

  const endDrag = (event: PointerEvent): void => {
    if (graphState.drag?.moved) graphState.suppressClick = true;
    graphState.drag = null;
    graphState.pan = null;
    if (graph.hasPointerCapture(event.pointerId)) graph.releasePointerCapture(event.pointerId);
  };
  graph.addEventListener("pointerup", endDrag);
  graph.addEventListener("pointercancel", endDrag);

  graph.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomGraph(event.deltaY < 0 ? 1.12 : 1 / 1.12, event.clientX, event.clientY);
  }, { passive: false });

  graph.addEventListener("click", (event) => {
    if (graphState.suppressClick) {
      graphState.suppressClick = false;
      return;
    }
    const node = (event.target as Element).closest("[data-work-id]");
    if (!node) return;
    const workId = node.getAttribute("data-work-id") ?? "";
    const item = (ui.status?.work_items ?? []).find((candidate) => candidate.work_id === workId);
    if (item) void selectWorkItem(item);
  });

  graph.addEventListener("dblclick", (event) => {
    if ((event.target as Element).closest(".gnode")) fitGraph();
  });

  // 图层开关：只要有变化就重建模型，fit 后回到全图视野。
  const toggle = (id: string, key: "showDepends" | "showRelated" | "showModules" | "onlyAttention") => {
    byId(id).addEventListener("click", () => {
      graphState[key] = !graphState[key];
      byId(id).classList.toggle("active", graphState[key]);
      graphState.signature = "";
      renderGraph();
    });
  };
  toggle("graph-depends", "showDepends");
  toggle("graph-related", "showRelated");
  toggle("graph-modules", "showModules");
  toggle("graph-attention", "onlyAttention");
  byId("graph-fit").addEventListener("click", () => fitGraph());
  byId("graph-zoom-in").addEventListener("click", () => zoomGraph(1.2));
  byId("graph-zoom-out").addEventListener("click", () => zoomGraph(1 / 1.2));
}

function bind(): void {
  byId("pick").addEventListener("click", () => {
    void (async () => {
      const root = await window.api.pickProject();
      if (root) await loadProject(root);
    })();
  });
  byId("refresh").addEventListener("click", () => {
    if (ui.view === "workspace") void loadWorkspace();
    else if (ui.view === "resources") void loadResources();
    else if (ui.view === "relations") {
      relState.signature = "";
      void loadRelations();
    } else if (ui.root) void loadProject(ui.root);
  });
  byId("workspace").addEventListener("click", () => {
    void loadWorkspace();
  });
  byId("resources").addEventListener("click", () => {
    void loadResources();
  });
  byId("relations").addEventListener("click", () => {
    void loadRelations();
  });
  bindRelations();
  byId("resource-groups").addEventListener("click", (event) => {
    const row = (event.target as Element).closest("[data-resource-path]");
    if (!row) return;
    const target = row.getAttribute("data-resource-path") ?? "";
    const file = (ui.resources ?? [])
      .flatMap((group) => group.files)
      .find((candidate) => candidate.path === target);
    if (!file) return;
    for (const item of Array.from(document.querySelectorAll(".resource-file"))) {
      item.classList.toggle("selected", item.getAttribute("data-resource-path") === target);
    }
    void renderResourceDocument(file);
  });
  byId("resource-reveal").addEventListener("click", () => {
    if (ui.resourceFile) void window.api.revealInExplorer(ui.resourceFile.path);
  });
  byId("reveal").addEventListener("click", () => {
    if (ui.selectedArtifact) void window.api.revealInExplorer(ui.selectedArtifact.path);
  });
  for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>(".tab"))) {
    button.addEventListener("click", () => selectTab(button.dataset.tab ?? "overview"));
  }
  // 关联图谱：悬停高亮邻域、点节点联动、拖节点改位、滚轮缩放、空白拖动平移。
  bindGraphInteraction();
  // 追踪图：悬停亮出该节点的连线，点击把关系写成文字。
  const traceGraph = byId("trace-graph");
  traceGraph.addEventListener("mouseover", (event) => {
    const node = (event.target as Element).closest("[data-node]");
    highlightTrace(node ? (node.getAttribute("data-node") ?? "") : "");
  });
  traceGraph.addEventListener("mouseleave", () => highlightTrace(""));
  traceGraph.addEventListener("click", (event) => {
    const node = (event.target as Element).closest("[data-node]");
    if (!node || !ui.selected) return;
    byId("trace-detail").innerHTML = traceDetail(
      ui.selected.traceability,
      node.getAttribute("data-node") ?? "",
    );
    highlightTrace(node.getAttribute("data-node") ?? "");
  });
  byId("data-body").addEventListener("click", (event) => {
    const target = event.target as Element;
    const work = target.closest("[data-work]");
    if (work) {
      const workId = work.getAttribute("data-work") ?? "";
      const item = (ui.status?.work_items ?? []).find((candidate) => candidate.work_id === workId);
      if (item) {
        selectTab("overview");
        void selectWorkItem(item);
      }
      return;
    }
    const file = target.closest("[data-file]");
    if (file) openPath(file.getAttribute("data-file") ?? "");
  });
}

async function main(): Promise<void> {
  bind();
  const root = await window.api.lastProject();
  if (root) {
    await loadProject(root);
  } else {
    showEmpty("选择一个项目目录开始", "目录里需要有 .agent/。查看器只读取工件，不修改任何文件。");
  }
}

void main();
