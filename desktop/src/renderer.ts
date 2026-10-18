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
  view: "project" as "project" | "workspace" | "resources",
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
  item: WorkItemView;
  x: number;
  y: number;
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

function computeDepths(items: WorkItemView[]): Map<string, number> {
  const byWorkId = new Map(items.map((item) => [item.work_id, item]));
  const depth = new Map<string, number>();
  const compute = (workId: string, seen: Set<string>): number => {
    const cached = depth.get(workId);
    if (cached !== undefined) return cached;
    // 依赖环由 Python 侧的 relations 检查报告；这里只防止递归失控。
    if (seen.has(workId)) return 0;
    seen.add(workId);
    const item = byWorkId.get(workId);
    const deps = item
      ? item.relations.depends_on.filter((dep) => !dep.missing).map((dep) => dep.work_id)
      : [];
    const value = deps.length === 0 ? 0 : 1 + Math.max(...deps.map((dep) => compute(dep, seen)));
    depth.set(workId, value);
    return value;
  };
  for (const item of items) compute(item.work_id, new Set());
  return depth;
}

function edgePath(from: GraphNode, to: GraphNode, kind: "depends" | "related"): string {
  const marker = kind === "depends" ? ' marker-end="url(#graph-arrow)"' : "";
  const y1 = from.y + NODE_H / 2;
  const y2 = to.y + NODE_H / 2;
  if (from.x === to.x) {
    // 同列：从右侧绕出去，避免穿过节点
    const x = from.x + NODE_W;
    return `<path class="edge ${kind}"${marker} d="M ${x} ${y1} C ${x + EDGE_BULGE} ${y1}, ${x + EDGE_BULGE} ${y2}, ${x} ${y2}" />`;
  }
  const forward = to.x > from.x;
  const x1 = forward ? from.x + NODE_W : from.x;
  const x2 = forward ? to.x : to.x + NODE_W;
  const bend = Math.max(50, Math.abs(x2 - x1) * 0.45);
  const c1 = forward ? x1 + bend : x1 - bend;
  const c2 = forward ? x2 - bend : x2 + bend;
  return `<path class="edge ${kind}"${marker} d="M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}" />`;
}

interface GraphLayout {
  nodes: Map<string, GraphNode>;
  width: number;
  height: number;
}

function layoutGraph(items: WorkItemView[]): GraphLayout {
  const depth = computeDepths(items);
  const sorted = [...items].sort((left, right) => left.work_id.localeCompare(right.work_id));
  const maxLevel = Math.max(...items.map((item) => depth.get(item.work_id) ?? 0), 0);
  const nodes = new Map<string, GraphNode>();

  if (maxLevel === 0) {
    // 没有硬依赖时按深度分列会退化成一列长条，改成网格铺开。
    const columns = Math.max(1, Math.ceil(Math.sqrt(sorted.length)));
    sorted.forEach((item, index) => {
      nodes.set(item.work_id, {
        item,
        x: GRAPH_PAD + (index % columns) * (NODE_W + NODE_GAP_X),
        y: GRAPH_PAD + Math.floor(index / columns) * (NODE_H + NODE_GAP_Y),
      });
    });
    const rows = Math.ceil(sorted.length / columns);
    return {
      nodes,
      width: GRAPH_PAD * 2 + columns * NODE_W + (columns - 1) * NODE_GAP_X + EDGE_MARGIN,
      height: GRAPH_PAD * 2 + rows * NODE_H + (rows - 1) * NODE_GAP_Y,
    };
  }

  const columns = new Map<number, WorkItemView[]>();
  for (const item of sorted) {
    const level = depth.get(item.work_id) ?? 0;
    const bucket = columns.get(level) ?? [];
    bucket.push(item);
    columns.set(level, bucket);
  }
  for (const [level, bucket] of columns) {
    bucket.forEach((item, index) => {
      nodes.set(item.work_id, {
        item,
        x: GRAPH_PAD + level * (NODE_W + NODE_GAP_X),
        y: GRAPH_PAD + index * (NODE_H + NODE_GAP_Y),
      });
    });
  }
  const rows = Math.max(...Array.from(columns.values()).map((bucket) => bucket.length), 1);
  return {
    nodes,
    width: GRAPH_PAD * 2 + (maxLevel + 1) * NODE_W + maxLevel * NODE_GAP_X + EDGE_MARGIN,
    height: GRAPH_PAD * 2 + rows * NODE_H + (rows - 1) * NODE_GAP_Y + EDGE_MARGIN,
  };
}

function renderGraph(): void {
  const container = byId("graph");
  clear(container);
  const items = ui.status?.work_items ?? [];
  if (items.length === 0) {
    container.appendChild(element("p", "muted", "没有工作项。"));
    return;
  }
  const { nodes, width, height } = layoutGraph(items);

  const edges: string[] = [];
  const drawn = new Set<string>();
  for (const item of items) {
    const from = nodes.get(item.work_id);
    if (!from) continue;
    for (const dependency of item.relations.depends_on) {
      const to = nodes.get(dependency.work_id);
      if (!to) continue;
      const key = `depends:${item.work_id}->${dependency.work_id}`;
      if (drawn.has(key)) continue;
      drawn.add(key);
      edges.push(edgePath(from, to, "depends"));
    }
    for (const related of item.relations.related) {
      const to = nodes.get(related.work_id);
      if (!to) continue;
      const key = `related:${[item.work_id, related.work_id].sort().join("-")}`;
      if (drawn.has(key)) continue;
      drawn.add(key);
      edges.push(edgePath(from, to, "related"));
    }
  }

  const markup = Array.from(nodes.values())
    .map((node) => nodeMarkup(node, ui.selected?.work_id === node.item.work_id))
    .join("");
  container.innerHTML =
    `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
    `<defs><marker id="graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">` +
    `<path d="M 0 0 L 10 5 L 0 10 z" fill="#2f6fd0" /></marker></defs>` +
    edges.join("") +
    markup +
    `</svg>`;
}
function nodeMarkup(node: GraphNode, selected: boolean): string {
  const item = node.item;
  const tasks = item.tasks;
  const total = tasks.pending + tasks.in_progress + tasks.done + tasks.blocked;
  const signed = Object.keys(item.approval.artifacts).length;
  const unsigned = item.approval.unsigned.length;
  const name = item.name.length > 11 ? `${item.name.slice(0, 11)}…` : item.name;
  const sign = unsigned > 0 ? ` · 待补签 ${unsigned}` : signed > 0 ? ` · 已签署 ${signed}` : "";
  return (
    `<g class="node${selected ? " selected" : ""}" data-work-id="${attr(item.work_id)}">` +
    `<rect class="node-box" x="${node.x}" y="${node.y}" width="${NODE_W}" height="${NODE_H}" rx="9" />` +
    `<rect x="${node.x}" y="${node.y}" width="3" height="${NODE_H}" rx="1.5" fill="${stateColor(item.state)}" />` +
    `<text class="node-id" x="${node.x + 14}" y="${node.y + 20}">${escapeHtml(item.work_id)}</text>` +
    `<text class="node-name" x="${node.x + 14}" y="${node.y + 40}">${escapeHtml(name)}</text>` +
    `<text class="node-meta" x="${node.x + 14}" y="${node.y + 58}">${escapeHtml(item.phase_label)}${total > 0 ? ` · 任务 ${tasks.done}/${total}` : ""}</text>` +
    `<text class="node-meta" x="${node.x + 14}" y="${node.y + 74}">${escapeHtml(item.state_label + sign)}</text>` +
    `</g>`
  );
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

function showView(view: "workspace" | "project" | "resources"): void {
  ui.view = view;
  byId("workspace-view").classList.toggle("hidden", view !== "workspace");
  byId("resources-view").classList.toggle("hidden", view !== "resources");
  byId("detail-body").classList.toggle("hidden", view !== "project" || !ui.selected);
  byId("empty-state").classList.toggle("hidden", view !== "project" || Boolean(ui.selected));
  document.body.classList.toggle("in-workspace", view === "workspace");
  document.body.classList.toggle("in-resources", view === "resources");
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
    else if (ui.root) void loadProject(ui.root);
  });
  byId("workspace").addEventListener("click", () => {
    void loadWorkspace();
  });
  byId("resources").addEventListener("click", () => {
    void loadResources();
  });
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
  byId("graph").addEventListener("click", (event) => {
    const target = (event.target as Element).closest("[data-work-id]");
    if (!target) return;
    const workId = target.getAttribute("data-work-id") ?? "";
    const item = (ui.status?.work_items ?? []).find((candidate) => candidate.work_id === workId);
    if (item) void selectWorkItem(item);
  });
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
