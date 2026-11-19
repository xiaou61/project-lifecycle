// 主进程与渲染进程共用的数据形状。本文件是全局脚本（没有 import/export），
// 这样渲染进程的 .ts 可以不带模块系统直接编译成浏览器可用的普通脚本。

interface ArtifactView {
  key: string;
  label: string;
  path: string;
  /** 工件 frontmatter 里的状态；没有 frontmatter 时为空。 */
  status: string;
  /** 已批准的签署人 / 时间 / 角色。 */
  approvedBy: string;
  approvedAt: string;
  approverRole: string;
  /** 业务验收（仅验证报告）。 */
  acceptedBy: string;
  acceptedAt: string;
  /** 该文件最近一次 Git 提交时间；不在版本控制里时为空。 */
  gitDate: string;
  /** 文件系统修改时间，作为 Git 时间缺失时的回退。 */
  mtime: string;
  exists: boolean;
}

interface ApprovalView {
  status: string;
  unsigned: string[];
  invalid: string[];
  artifacts: Record<
    string,
    { approved_by: string; approved_at: string; approver_role: string }
  >;
  acceptance: { accepted_by: string; accepted_at: string } | null;
}

interface TaskCounts {
  pending: number;
  in_progress: number;
  done: number;
  blocked: number;
}

interface CoverageView {
  required: boolean;
  status: string;
  level: string;
  path: string;
  warnings: string[];
}

interface EvidenceView {
  required: boolean;
  status: string;
  path: string;
  warnings: string[];
}

interface BudgetView {
  status: string;
  total_bytes: number;
  file_count: number;
  warnings: string[];
}

interface AttributionView {
  status: string;
  path: string;
  warnings: string[];
}

interface StateEvidenceView {
  documented_state: string;
  documented_phase: string;
  test_evidence: string;
  code_sync: string;
  settlement_status: string;
  confidence: string;
  requires_reconciliation: boolean;
  note: string;
  git_status: string;
}

interface TraceDefinition {
  id: string;
  kind: string;
  title: string;
}

interface TraceTask {
  id: string;
  state: string;
  title: string;
  maps_to: string[];
  legacy: string[];
  depends_on: string[];
}

interface TraceabilityView {
  requirements: TraceDefinition[];
  acceptance: TraceDefinition[];
  tasks: TraceTask[];
  /** 来自来源覆盖表的显式 REQ↔AC 直连；没有那张表时为空。 */
  requirement_acceptance_links: string[][];
  /** 任务引用了但需求里没定义的 id。 */
  undefined_refs: string[];
  unmapped_tasks: string[];
  acceptance_without_evidence: string[];
}

interface WorkItemView {
  work_id: string;
  name: string;
  slug: string;
  path: string;
  phase: string;
  phase_label: string;
  state: string;
  state_label: string;
  mode: string;
  mode_label: string;
  archived: boolean;
  next_action: string;
  artifacts: Record<string, string>;
  tasks: TaskCounts;
  approval: ApprovalView;
  traceability: TraceabilityView;
  source_coverage: CoverageView;
  test_evidence: EvidenceView;
  document_budget: BudgetView;
  workspace_attribution: AttributionView;
  state_evidence: StateEvidenceView;
  warnings: string[];
  relations: {
    depends_on: Array<{ work_id: string; name: string; phase_label: string; state: string; missing: boolean }>;
    dependents: Array<{ work_id: string; name: string; phase_label: string; state: string; missing: boolean }>;
    related: Array<{ work_id: string; name: string; phase_label: string; state: string; missing: boolean }>;
  };
}

/** INDEX.md「模块索引」表的一行：模块名、源码路径、相关工作项。 */
interface ModuleView {
  name: string;
  path: string;
  work_ids: string[];
}

interface StatusView {
  schema_version: string;
  generated_at: string;
  project_root: string;
  /** 主进程从 .agent/INDEX.md 解析后附加；Python 状态里没有这一段。 */
  modules?: ModuleView[];
  workspace: string;
  scope: string;
  initialized: boolean;
  state: string;
  next_work_id: string;
  next_action: string;
  rules: { ready: boolean; configured: boolean; path: string; warnings: string[] };
  warnings: string[];
  work_items: WorkItemView[];
  git: { status: string; changed_files: number; warning: string | null };
  resume: { mode: string; blockers: string[]; warnings: string[] } | null;
}

interface ValidateIssue {
  work_id: string | null;
  message: string;
}

interface ValidateView {
  valid: boolean;
  strict: boolean;
  project_root: string;
  errors: ValidateIssue[];
  warnings: ValidateIssue[];
}

interface HistoryEntry {
  title: string;
  body: string;
}

interface DocumentView {
  /** 去掉 frontmatter 后的正文渲染结果。 */
  html: string;
  /** frontmatter 的键值，按文件出现顺序。 */
  frontmatter: Array<{ key: string; value: string }>;
  /** 正文行数，用于提示空文件。 */
  lines: number;
}

interface LoadResult<T> {
  ok: boolean;
  data: T | null;
  error: string;
}

interface ProjectSummary {
  root: string;
  name: string;
  ok: boolean;
  error: string;
  initialized: boolean;
  scope: string;
  /** 工作项数量（不含归档）。 */
  workItems: number;
  /** 工作项状态分桶：需要处理 / 进行中 / 已完成。 */
  attention: number;
  running: number;
  done: number;
  /** 待补签的工件数，以及涉及的工作项数。 */
  unsigned: number;
  unsignedItems: number;
  /** 缺少结构化证据的验收标准数。 */
  acceptanceGaps: number;
  rulesReady: boolean;
  gitStatus: string;
  /** 最后一次活动：取 Git 提交时间；没有提交时为空。 */
  lastActivity: string;
  lastActivitySource: string;
}

interface WorkspaceView {
  /** index = 来自 PROJECT-INDEX.md，app = 来自应用自己记住的清单。 */
  source: string;
  /** 索引文件或工作区根路径，用于说明清单从哪来。 */
  sourcePath: string;
  projects: ProjectSummary[];
  totals: {
    projects: number;
    workItems: number;
    attention: number;
    unsigned: number;
    acceptanceGaps: number;
  };
}

interface ResourceFile {
  label: string;
  name: string;
  path: string;
  size: number;
  mtime: string;
  gitDate: string;
}

interface ResourceGroup {
  key: string;
  label: string;
  hint: string;
  files: ResourceFile[];
}

interface DesktopApi {
  pickProject(): Promise<string | null>;
  lastProject(): Promise<string | null>;
  listProjects(root: string): Promise<LoadResult<{ source: string; sourcePath: string; roots: string[] }>>;
  loadWorkspace(root: string): Promise<LoadResult<WorkspaceView>>;
  forgetProject(root: string): Promise<void>;
  loadResources(root: string): Promise<LoadResult<ResourceGroup[]>>;
  loadStatus(root: string): Promise<LoadResult<StatusView>>;
  loadValidate(root: string): Promise<LoadResult<ValidateView>>;
  loadHistory(root: string): Promise<LoadResult<HistoryEntry[]>>;
  loadArtifacts(root: string, item: WorkItemView): Promise<LoadResult<ArtifactView[]>>;
  readDocument(path: string): Promise<LoadResult<DocumentView>>;
  revealInExplorer(path: string): Promise<void>;
  openExternal(url: string): Promise<void>;
}

interface Window {
  api: DesktopApi;
}
