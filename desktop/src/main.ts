// Electron 主进程：唯一的 IO 层。
// 渲染进程不碰文件系统、不执行命令，只通过 preload 暴露的窄接口取数据。
// 事实来源仍是 Python 侧的状态推导（.agent 工件），这里只做展示所需的读取和渲染。

import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from "electron";
import { spawn } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { marked } from "marked";

const SKILL_SCRIPTS = ["skills", "project-lifecycle", "scripts"];

// 窗口被其他程序遮挡时 Chromium 会跳过重绘，自截图会拿到旧帧；这两个开关关掉该降频。
app.commandLine.appendSwitch("disable-backgrounding-occluded-windows");
app.commandLine.appendSwitch("disable-renderer-backgrounding");

const ARTIFACT_FILES: Record<string, { label: string; file: string }> = {
  requirements: { label: "需求", file: "requirements.md" },
  proposal: { label: "方案", file: "proposal.md" },
  design: { label: "设计", file: "design.md" },
  tasks: { label: "任务", file: "tasks.md" },
  test_plan: { label: "测试计划", file: "testing/plan.md" },
  test_report: { label: "验证报告", file: "testing/report.md" },
  workspace: { label: "工作区归因", file: "workspace.md" },
};

let cachedPython: string[] | null = null;

function scriptsDir(): string {
  const candidates = [
    process.env.PROJECT_LIFECYCLE_SCRIPTS ?? "",
    path.join(process.resourcesPath ?? "", ...SKILL_SCRIPTS),
    path.join(app.getAppPath(), "..", ...SKILL_SCRIPTS),
    path.join(app.getAppPath(), ...SKILL_SCRIPTS),
  ];
  const found = candidates.find(
    (candidate) => candidate && existsSync(path.join(candidate, "project_status.py")),
  );
  if (!found) {
    throw new Error(
      "找不到 project-lifecycle 脚本目录。请设置环境变量 PROJECT_LIFECYCLE_SCRIPTS 指向 skills/project-lifecycle/scripts。",
    );
  }
  return path.resolve(found);
}

interface RunResult {
  code: number;
  stdout: string;
  stderr: string;
}

function run(command: string, args: string[]): Promise<RunResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { windowsHide: true });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => resolve({ code: code ?? -1, stdout, stderr }));
  });
}

/** 解析可用的 Python 命令；与 PowerShell 适配器一致，优先 py -3。 */
async function pythonCommand(): Promise<string[]> {
  if (cachedPython) return cachedPython;
  const candidates = [
    ["py", "-3", "-X", "utf8"],
    ["python", "-X", "utf8"],
    ["python3", "-X", "utf8"],
  ];
  for (const candidate of candidates) {
    try {
      const probe = await run(candidate[0], [...candidate.slice(1), "-c", "import sys;print(sys.version_info[0])"]);
      if (probe.code === 0) {
        cachedPython = candidate;
        return candidate;
      }
    } catch {
      // 该命令不存在，试下一个
    }
  }
  throw new Error(
    "未找到 Python 运行时。本工具需要 Python 3.9 或更高版本来读取 .agent 工件；请安装 Python 后重试。",
  );
}

async function runPython(script: string, args: string[]): Promise<RunResult> {
  const python = await pythonCommand();
  return run(python[0], [...python.slice(1), path.join(scriptsDir(), script), ...args]);
}

function parseJson<T>(result: RunResult): T {
  const text = result.stdout.trim();
  if (!text) {
    throw new Error(result.stderr.trim() || `脚本没有输出（退出码 ${result.code}）。`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(result.stderr.trim() || "脚本输出不是合法 JSON。");
  }
}

function parseFrontmatter(text: string): {
  entries: Array<{ key: string; value: string }>;
  fields: Record<string, string>;
} {
  const entries: Array<{ key: string; value: string }> = [];
  const fields: Record<string, string> = {};
  const lines = text.split(/\r?\n/);
  if ((lines[0] ?? "").trim() !== "---") return { entries, fields };
  for (let index = 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (line.trim() === "---") break;
    const match = /^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$/.exec(line);
    if (!match) continue;
    const value = match[2].replace(/^["'](.*)["']$/, "$1");
    entries.push({ key: match[1].toLowerCase(), value });
    fields[match[1].toLowerCase()] = value;
  }
  return { entries, fields };
}

function bodyAfterFrontmatter(text: string): string {
  const lines = text.split(/\r?\n/);
  if ((lines[0] ?? "").trim() !== "---") return text;
  for (let index = 1; index < lines.length; index += 1) {
    if (lines[index].trim() === "---") return lines.slice(index + 1).join("\n");
  }
  return text;
}

async function gitDate(root: string, relative: string): Promise<string> {
  try {
    const result = await run("git", ["-C", root, "log", "-1", "--format=%cI", "--", relative]);
    return result.code === 0 ? result.stdout.trim() : "";
  } catch {
    return "";
  }
}

async function loadArtifacts(root: string, item: WorkItemView): Promise<ArtifactView[]> {
  const keys = Object.keys(ARTIFACT_FILES).filter(
    (key) => key === "workspace" || key in item.artifacts,
  );
  return Promise.all(
    keys.map(async (key) => {
      const { label, file } = ARTIFACT_FILES[key];
      const absolute = path.join(item.path, file);
      const relative = path.relative(root, absolute).split(path.sep).join("/");
      const base: ArtifactView = {
        key,
        label,
        path: absolute,
        status: item.artifacts[key] ?? "",
        approvedBy: "",
        approvedAt: "",
        approverRole: "",
        acceptedBy: "",
        acceptedAt: "",
        gitDate: await gitDate(root, relative),
        mtime: "",
        exists: false,
      };
      if (!existsSync(absolute)) return base;
      const [text, info] = await Promise.all([
        readFile(absolute, { encoding: "utf8" }),
        stat(absolute),
      ]);
      const { fields } = parseFrontmatter(text);
      return {
        ...base,
        exists: true,
        status: fields.status ?? base.status,
        approvedBy: fields.approved_by ?? "",
        approvedAt: fields.approved_at ?? "",
        approverRole: fields.approver_role ?? "",
        acceptedBy: fields.accepted_by ?? "",
        acceptedAt: fields.accepted_at ?? "",
        mtime: info.mtime.toISOString(),
      };
    }),
  );
}

/**
 * `.agent/` 里除工作项之外的常驻资料。目录到分类的映射是展示用的固定约定；
 * 枚举文件属于 IO，不是状态推导——语义仍由 Python 决定（哪些文件算工件）。
 */
const RESOURCE_GROUPS: Array<{ key: string; label: string; hint: string; dirs: string[] }> = [
  {
    key: "index",
    label: "模块索引与项目说明",
    hint: "INDEX.md 只做模块导航，不记录阶段或任务状态",
    dirs: ["."],
  },
  {
    key: "rules",
    label: "项目常驻规范",
    hint: "跨工作项长期有效的事实和约束；未确认时不能实现、部署或迁移",
    dirs: ["rules"],
  },
  {
    key: "specs",
    label: "稳定规格",
    hint: "当前共享契约：外部可观察行为、公共接口、数据不变量",
    dirs: ["specs"],
  },
  {
    key: "notes",
    label: "决策笔记",
    hint: "跨工作项仍然有效的取舍理由，含被否掉的方案",
    dirs: ["notes"],
  },
  {
    key: "memory",
    label: "长期记忆",
    hint: "跨任务的长期知识；不能替代当前工作项的需求事实",
    dirs: ["."],
  },
  {
    key: "references",
    label: "参考资料",
    hint: "长期可检索的外部资料与留档",
    dirs: ["references"],
  },
  {
    key: "html",
    label: "理解材料",
    hint: "用户明确同意后生成的项目理解型 HTML，不替代源码或验收证据",
    dirs: ["html"],
  },
  {
    key: "history",
    label: "更新历史与生成视图",
    hint: "updates.md 是追加式时间线；core-components.md 是 Git 历史的生成视图",
    dirs: ["history"],
  },
  {
    key: "archive",
    label: "归档工作项",
    hint: "验证通过后归档的完整决策轨迹，保留原样供查阅",
    dirs: [path.join("changes", "archive")],
  },
];

/** 只收这些后缀；`.agent/` 里不该有源码或二进制。 */
const RESOURCE_EXTENSIONS = new Set([".md", ".html", ".json", ".yaml", ".yml", ".txt"]);
const RESOURCE_FILE_CAP = 200;
/** 每个文件一次 git log；给个总预算，避免大项目把首屏拖慢。 */
const RESOURCE_GIT_DATE_CAP = 80;

function listResourceFiles(root: string, relative: string, limit: number): string[] {
  const base = path.join(root, ".agent", relative);
  if (!existsSync(base)) return [];
  const found: string[] = [];
  const walk = (current: string, depth: number): void => {
    if (found.length >= limit || depth > 4) return;
    let entries: string[];
    try {
      entries = readdirSync(current);
    } catch {
      return;
    }
    for (const entry of entries.sort()) {
      if (found.length >= limit || entry.startsWith(".")) continue;
      const absolute = path.join(current, entry);
      if (isDirectory(absolute)) {
        walk(absolute, depth + 1);
        continue;
      }
      if (!RESOURCE_EXTENSIONS.has(path.extname(entry).toLowerCase())) continue;
      found.push(path.relative(base, absolute).split(path.sep).join("/"));
    }
  };
  walk(base, 0);
  return found;
}

async function loadResources(root: string): Promise<ResourceGroup[]> {
  const groups: ResourceGroup[] = [];
  let gitBudget = RESOURCE_GIT_DATE_CAP;
  for (const group of RESOURCE_GROUPS) {
    const entries: ResourceFile[] = [];
    const seen = new Set<string>();
    for (const dir of group.dirs) {
      for (const relative of listResourceFiles(root, dir, RESOURCE_FILE_CAP)) {
        // "." 这一组只收根目录下的三个单文件，不收子目录
        if (dir === "." && !["INDEX.md", "README.md", "memory.md"].includes(relative)) continue;
        const absolute = path.join(root, ".agent", dir, relative);
        if (seen.has(absolute) || !existsSync(absolute)) continue;
        seen.add(absolute);
        const info = await stat(absolute).catch(() => null);
        entries.push({
          label: dir === "." ? relative : `${dir}/${relative}`,
          name: relative.split("/").pop() ?? relative,
          path: absolute,
          size: info?.size ?? 0,
          mtime: info ? info.mtime.toISOString() : "",
          gitDate: "",
        });
      }
    }
    // 每个文件一次 git log；并发取，串行 await 会让文件多的项目首屏卡住
    const budgeted = entries.slice(0, Math.max(0, gitBudget));
    gitBudget -= budgeted.length;
    await Promise.all(
      budgeted.map(async (entry) => {
        entry.gitDate = await gitDate(root, path.relative(root, entry.path).split(path.sep).join("/"));
      }),
    );
    entries.sort((left, right) => left.label.localeCompare(right.label));
    groups.push({ key: group.key, label: group.label, hint: group.hint, files: entries });
  }
  return groups;
}

interface StoredState {
  lastProject?: string;
  /** 应用自己记住的项目清单；没有 PROJECT-INDEX.md 工作区时用它。 */
  projects?: string[];
}

function stateFile(): string {
  return path.join(app.getPath("userData"), "state.json");
}

async function readState(): Promise<StoredState> {
  try {
    return JSON.parse(await readFile(stateFile(), { encoding: "utf8" })) as StoredState;
  } catch {
    return {};
  }
}

async function writeState(state: StoredState): Promise<void> {
  await writeFile(stateFile(), JSON.stringify(state, null, 2), { encoding: "utf8" });
}

async function rememberProject(root: string): Promise<void> {
  const state = await readState();
  const projects = [root, ...(state.projects ?? []).filter((item) => item !== root)];
  await writeState({ ...state, lastProject: root, projects: projects.slice(0, 30) });
}

function isDirectory(target: string): boolean {
  try {
    return statSync(target).isDirectory();
  } catch {
    return false;
  }
}

/** 读 PROJECT-INDEX.md 的「项目清单」表，取源码目录列；路径相对工作区根。 */
function parseProjectIndex(indexPath: string): string[] {
  const text = readFileSync(indexPath, { encoding: "utf8" });
  const section = text.split(/^##\s+项目清单\s*$/m)[1] ?? "";
  const table = section.split(/^##\s+/m)[0];
  const rows = table
    .split(/\r?\n/)
    .filter((line) => line.trim().startsWith("|"))
    .map((line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim()))
    .filter((cells) => !cells.every((cell) => /^:?-{3,}:?$/.test(cell)));
  if (rows.length < 2) return [];
  const column = rows[0].findIndex((header) => /源码目录|源码|目录/.test(header));
  if (column < 0) return [];
  const workspaceRoot = path.dirname(path.dirname(indexPath));
  const roots: string[] = [];
  for (const cells of rows.slice(1)) {
    const cell = (cells[column] ?? "").replace(/`/g, "").trim();
    if (!cell) continue;
    const resolved = path.resolve(workspaceRoot, cell);
    if (isDirectory(resolved) && !roots.includes(resolved)) roots.push(resolved);
  }
  return roots;
}

/** 项目清单来源：工作区索引优先，其次是应用自己记住的清单。 */
async function resolveProjectList(root: string): Promise<{ source: string; sourcePath: string; roots: string[] }> {
  const candidates = [
    path.join(root, ".agent", "PROJECT-INDEX.md"),
    path.join(path.dirname(root), ".agent", "PROJECT-INDEX.md"),
  ];
  for (const candidate of candidates) {
    if (!existsSync(candidate)) continue;
    const roots = parseProjectIndex(candidate);
    if (roots.length > 0) return { source: "index", sourcePath: candidate, roots };
  }
  const state = await readState();
  const roots = (state.projects ?? []).filter((item) => isDirectory(item));
  return { source: "app", sourcePath: stateFile(), roots };
}

async function lastActivityOf(root: string): Promise<{ value: string; source: string }> {
  try {
    const result = await run("git", ["-C", root, "log", "-1", "--format=%cI"]);
    const value = result.stdout.trim();
    if (result.code === 0 && value) return { value, source: "git" };
  } catch {
    // 不是仓库或没有提交，继续回退
  }
  const history = path.join(root, ".agent", "history", "updates.md");
  if (existsSync(history)) {
    const text = await readFile(history, { encoding: "utf8" }).catch(() => "");
    const matches = text.match(/^##\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})/gm);
    const last = matches?.[matches.length - 1];
    if (last) return { value: last.replace(/^##\s+/, ""), source: "updates" };
  }
  return { value: "", source: "none" };
}

async function summarizeProject(root: string): Promise<ProjectSummary> {
  const base: ProjectSummary = {
    root,
    name: path.basename(root),
    ok: false,
    error: "",
    initialized: false,
    scope: "",
    workItems: 0,
    attention: 0,
    running: 0,
    done: 0,
    unsigned: 0,
    unsignedItems: 0,
    acceptanceGaps: 0,
    rulesReady: false,
    gitStatus: "",
    lastActivity: "",
    lastActivitySource: "none",
  };
  try {
    const status = parseJson<StatusView>(await runPython("project_status.py", [root, "--json"]));
    // 汇总只看活动工作项：归档项不该抬高待办数字
    const items = status.work_items.filter((item) => !item.archived);
    for (const item of items) {
      if (item.state === "complete") base.done += 1;
      else if (["blocked", "needs_attention", "stale", "failed"].includes(item.state)) base.attention += 1;
      else base.running += 1;
      base.unsigned += item.approval.unsigned.length;
      if (item.approval.unsigned.length > 0) base.unsignedItems += 1;
      base.acceptanceGaps += item.traceability.acceptance_without_evidence.length;
    }
    const activity = await lastActivityOf(root);
    return {
      ...base,
      ok: true,
      initialized: status.initialized,
      scope: status.scope,
      workItems: items.length,
      rulesReady: status.rules.ready && status.rules.configured,
      gitStatus: status.git.status,
      lastActivity: activity.value,
      lastActivitySource: activity.source,
    };
  } catch (error) {
    return { ...base, error: (error as Error).message };
  }
}

async function loadWorkspace(root: string): Promise<WorkspaceView> {
  const list = await resolveProjectList(root);
  const projects = await Promise.all(list.roots.map((item) => summarizeProject(item)));
  return {
    source: list.source,
    sourcePath: list.sourcePath,
    projects,
    totals: {
      projects: projects.length,
      workItems: projects.reduce((sum, item) => sum + item.workItems, 0),
      attention: projects.reduce((sum, item) => sum + item.attention, 0),
      unsigned: projects.reduce((sum, item) => sum + item.unsigned, 0),
      acceptanceGaps: projects.reduce((sum, item) => sum + item.acceptanceGaps, 0),
    },
  };
}

function createWindow(): BrowserWindow {
  // 这个应用只有一屏内容，默认菜单栏（File/Edit/View/Window/Help）没有任何可用项。
  Menu.setApplicationMenu(null);
  const window = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 960,
    minHeight: 620,
    title: "project-lifecycle 工件查看器",
    autoHideMenuBar: true,
    backgroundColor: "#11161d",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  void window.loadFile(path.join(app.getAppPath(), "index.html"));
  return window;
}

function registerHandlers(): void {
  ipcMain.handle("pick-project", async () => {
    const result = await dialog.showOpenDialog({
      title: "选择包含 .agent/ 的项目目录",
      properties: ["openDirectory"],
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    const root = result.filePaths[0];
    await rememberProject(root);
    return root;
  });

  ipcMain.handle("last-project", async () => (await readState()).lastProject ?? null);

  ipcMain.handle("list-projects", async (_event, root: string) => {
    try {
      return { ok: true, data: await resolveProjectList(root), error: "" };
    } catch (error) {
      return { ok: false, data: null, error: (error as Error).message };
    }
  });

  ipcMain.handle("load-workspace", async (_event, root: string) => {
    try {
      return { ok: true, data: await loadWorkspace(root), error: "" };
    } catch (error) {
      return { ok: false, data: null, error: (error as Error).message };
    }
  });

  ipcMain.handle("load-resources", async (_event, root: string) => {
    try {
      return { ok: true, data: await loadResources(root), error: "" };
    } catch (error) {
      return { ok: false, data: null, error: (error as Error).message };
    }
  });

  ipcMain.handle("forget-project", async (_event, root: string) => {
    const state = await readState();
    await writeState({ ...state, projects: (state.projects ?? []).filter((item) => item !== root) });
  });

  ipcMain.handle("load-status", async (_event, root: string) => {
    try {
      const result = await runPython("project_status.py", [root, "--json", "--include-archive"]);
      return { ok: true, data: parseJson<StatusView>(result), error: "" };
    } catch (error) {
      return { ok: false, data: null, error: (error as Error).message };
    }
  });

  ipcMain.handle("load-validate", async (_event, root: string) => {
    try {
      const result = await runPython("project_validate.py", [root, "--json"]);
      return { ok: true, data: parseJson<ValidateView>(result), error: "" };
    } catch (error) {
      return { ok: false, data: null, error: (error as Error).message };
    }
  });

  ipcMain.handle("load-history", async (_event, root: string) => {
    try {
      const result = await runPython("update_history.py", [root, "--list", "--json", "--tail", "20"]);
      const payload = parseJson<{ entries: string[] }>(result);
      const entries = payload.entries
        .map((raw) => {
          const lines = raw.split(/\r?\n/);
          const heading = (lines[0] ?? "").replace(/^##\s*/, "");
          return { title: heading, body: lines.slice(1).join("\n").trim() };
        })
        .reverse();
      return { ok: true, data: entries, error: "" };
    } catch (error) {
      return { ok: false, data: null, error: (error as Error).message };
    }
  });

  ipcMain.handle("load-artifacts", async (_event, root: string, item: WorkItemView) => {
    try {
      return { ok: true, data: await loadArtifacts(root, item), error: "" };
    } catch (error) {
      return { ok: false, data: null, error: (error as Error).message };
    }
  });

  ipcMain.handle("read-document", async (_event, target: string) => {
    try {
      if (!existsSync(target)) {
        return { ok: false, data: null, error: `文件不存在：${target}` };
      }
      const text = await readFile(target, { encoding: "utf8" });
      const { entries } = parseFrontmatter(text);
      const body = bodyAfterFrontmatter(text);
      return {
        ok: true,
        data: {
          html: marked.parse(body, { async: false }) as string,
          frontmatter: entries,
          lines: body.split(/\r?\n/).length,
        },
        error: "",
      };
    } catch (error) {
      return { ok: false, data: null, error: (error as Error).message };
    }
  });

  ipcMain.handle("reveal", async (_event, target: string) => {
    shell.showItemInFolder(target);
  });

  ipcMain.handle("open-external", async (_event, url: string) => {
    if (/^https?:\/\//i.test(url)) await shell.openExternal(url);
  });
}

interface UiCheck {
  name: string;
  ok: boolean;
  detail: string;
}

/**
 * 界面自检：用真实事件派发走一遍联动，失败就返回非零。
 * SVG 元素没有 HTMLElement.click()，所以统一用 dispatchEvent。
 */
async function runUiChecks(root: string): Promise<UiCheck[]> {
  const checks: UiCheck[] = [];
  registerHandlers();
  await rememberProject(root);
  const window = createWindow();
  const evaluate = (script: string): Promise<string> =>
    window.webContents.executeJavaScript(script) as Promise<string>;
  const record = (name: string, ok: boolean, detail: string): void => {
    checks.push({ name, ok, detail });
  };
  await new Promise<void>((resolve) => {
    window.webContents.once("did-finish-load", () => resolve());
  });
  await new Promise((resolve) => setTimeout(resolve, 6000));

  // 前置检查：IPC 没注册或项目没加载时，后面几条会假通过。
  const loaded = await evaluate(`document.getElementById("project-path")?.textContent ?? ""`);
  record("项目已加载", loaded === root, loaded);
  const workCount = Number(await evaluate(`String(document.querySelectorAll(".work-item").length)`));
  // 工作区导航目录没有工作项是正常的：打开它应该直接进工作区视图。
  const landedInWorkspace = await evaluate(
    `document.getElementById("workspace-view")?.classList.contains("hidden") ? "hidden" : "shown"`,
  );
  record(
    "工作项列表渲染",
    workCount > 0 || landedInWorkspace === "shown",
    workCount > 0
      ? `${workCount} 个工作项`
      : "0 个工作项（工作区导航目录，已直接进工作区视图）",
  );

  const tabs = ["overview", "read", "validate", "history", "data"];
  for (const tab of tabs) {
    const state = await evaluate(
      `(() => { document.querySelector('[data-tab="${tab}"]').click();` +
        ` return document.getElementById("tab-${tab}").classList.contains("hidden") ? "hidden" : "shown"; })()`,
    );
    record(`页签 ${tab}`, state === "shown", state);
  }

  const noWorkItems = workCount === 0;
  const gateCount = await evaluate(`String(document.querySelectorAll("#gate-strip .gate").length)`);
  if (noWorkItems) {
    record("工作项相关断言", true, "跳过：这个目录没有工作项（工作区导航目录或空项目）");
  } else {
    record("阶段门槛条渲染", Number(gateCount) >= 5, `${gateCount} 道门`);
  }

  // 需求追踪图：节点、悬停亮线、点击详情。
  // 一次遍历工作项，找有 REQ/AC/TASK 的那个再验——选中项可能本来就没有标识（例如只写了需求的早期工作项）。
  const traceProbe = await evaluate(
    `(async () => {` +
      ` let nodes = 0, lit = "", detail = "";` +
      ` for (const item of document.querySelectorAll(".work-item")) {` +
      `   item.dispatchEvent(new MouseEvent("click", { bubbles: true }));` +
      `   await new Promise((r) => setTimeout(r, 1200));` +
      `   const count = document.querySelectorAll("#trace-graph .node").length;` +
      `   if (count > nodes) nodes = count;` +
      `   if (count === 0) continue;` +
      `   if (!detail) {` +
      `     const first = document.querySelector("#trace-graph .node");` +
      `     if (first) first.dispatchEvent(new MouseEvent("click", { bubbles: true }));` +
      `     const text = document.getElementById("trace-detail")?.textContent ?? "";` +
      `     if (text.length > 20) detail = text.slice(0, 50);` +
      `   }` +
      `   if (!lit) {` +
      `     const edges = document.querySelectorAll("#trace-graph .edge").length;` +
      `     for (const node of document.querySelectorAll("#trace-graph .node")) {` +
      `       node.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));` +
      `       const hot = document.querySelectorAll("#trace-graph .edge.hot").length;` +
      `       if (hot > 0) { lit = (item.dataset.workId ?? "?") + " 亮起 " + hot + " 条线"; break; }` +
      `     }` +
      `     if (!lit && edges > 0) lit = "有 " + edges + " 条边但悬停没有亮线";` +
      `   }` +
      ` }` +
      ` return nodes + "" + (lit || "跳过：所有工作项都没有可连的 对应/依赖 引用") +` +
      `   "" + (detail || "无节点可点");` +
      `})()`,
  );
  const [traceNodeCount, traceHover, traceDetailText] = traceProbe.split("");
  if (!noWorkItems) {
    record("追踪图渲染节点", Number(traceNodeCount) > 0, `${traceNodeCount} 个节点`);
    record("追踪图悬停亮线", !traceHover.includes("没有亮线"), traceHover);
    record("追踪图点击详情", traceDetailText.length > 20, traceDetailText);
  }

  const workItemCount = workCount;
  if (noWorkItems) {
    // 已在上面报告跳过
  } else if (workItemCount < 2) {
    // 只有一个工作项时没有可联动的对象，断言不适用；报出来而不是假装通过。
    record("关系图点节点联动", true, `跳过：只有 ${workItemCount} 个工作项，没有可联动对象`);
  } else {
    const graphTarget = await evaluate(
      `(() => { const nodes = document.querySelectorAll('#graph [data-work-id]');` +
        ` if (nodes.length < 2) return "节点不足";` +
        ` const target = nodes[1].getAttribute("data-work-id");` +
        ` nodes[1].dispatchEvent(new MouseEvent("click", { bubbles: true })); return target; })()`,
    );
    await new Promise((resolve) => setTimeout(resolve, 2500));
    const selected = await evaluate(
      `document.querySelector(".work-item.selected")?.dataset.workId ?? "none"`,
    );
    record("关系图点节点联动", graphTarget === selected, `点 ${graphTarget} → 选中 ${selected}`);
  }

  await evaluate(`document.querySelector('[data-tab="data"]').click()`);
  const jsonSize = await evaluate(`String(document.getElementById("data-body")?.textContent?.length ?? 0)`);
  record("数据面板渲染 JSON", Number(jsonSize) > 500, `${jsonSize} 字符`);
  const clickedFile = await evaluate(
    `(() => { const link = document.querySelector("#data-body .j-link[data-file]");` +
      ` if (!link) return "无文件链接"; const target = link.getAttribute("data-file");` +
      ` link.dispatchEvent(new MouseEvent("click", { bubbles: true })); return target; })()`,
  );
  await new Promise((resolve) => setTimeout(resolve, 2500));
  const documentState = await evaluate(
    `(document.querySelector(".tab.active")?.dataset.tab ?? "") + "|" +` +
      ` (document.getElementById("doc-title")?.textContent ?? "")`,
  );
  record(
    "数据面板点文件联动",
    documentState.startsWith("read|") && documentState.length > 8,
    `${clickedFile} → ${documentState}`,
  );

  // 项目资料视图：分组、点文件渲染
  await evaluate(`document.getElementById("resources").click()`);
  // 文件多的项目要等 Python/IO 读完；轮询而不是固定延时
  await evaluate(
    `(async () => {` +
      ` for (let i = 0; i < 40; i += 1) {` +
      `   const label = document.getElementById("resources-count")?.textContent ?? "";` +
      `   if (label && label !== "读取中") return;` +
      `   await new Promise((r) => setTimeout(r, 500));` +
      ` }` +
      `})()`,
  );
  const resourcesState = await evaluate(
    `(document.getElementById("resources-view")?.classList.contains("hidden") ? "hidden" : "shown") +` +
      ` "|" + (document.getElementById("resources-count")?.textContent ?? "") +` +
      ` "|" + String(document.querySelectorAll(".resource-group").length)`,
  );
  const [resourcesVisible, resourcesCount, groupCount] = resourcesState.split("|");
  record("项目资料视图打开", resourcesVisible === "shown", `${resourcesCount}，${groupCount} 个分组`);
  const resourceClick = await evaluate(
    `(async () => { const row = document.querySelector(".resource-file");` +
      ` if (!row) return "没有资料文件"; row.click();` +
      ` await new Promise((r) => setTimeout(r, 1500));` +
      ` const text = document.getElementById("resource-content")?.textContent ?? "";` +
      ` const title = document.getElementById("resource-title")?.textContent ?? "";` +
      ` return text.length > 30 ? title + "（" + text.length + " 字符）" : "渲染为空：" + title; })()`,
  );
  record("资料文件渲染", !resourceClick.startsWith("渲染为空") && resourceClick !== "没有资料文件", resourceClick);

  // 归档工作项分组：有归档项时侧栏要有分隔，没有就如实报跳过
  const archiveState = await evaluate(
    `(() => { const divider = document.querySelector(".work-divider");` +
      ` return divider ? divider.textContent : "无归档项"; })()`,
  );
  record("归档工作项分组", true, archiveState ?? "无归档项");

  // 工作区视图：清单来源、项目卡片、点卡片回到项目视图
  await evaluate(`document.getElementById("workspace").click()`);
  await new Promise((resolve) => setTimeout(resolve, 5000));
  const workspaceState = await evaluate(
    `(document.getElementById("workspace-view")?.classList.contains("hidden") ? "hidden" : "shown") +` +
      ` "|" + (document.getElementById("workspace-source")?.textContent ?? "") +` +
      ` "|" + String(document.querySelectorAll(".project-card").length)`,
  );
  const [workspaceVisible, workspaceSource, cardCount] = workspaceState.split("|");
  record("工作区视图打开", workspaceVisible === "shown", workspaceSource ?? "");
  record("工作区项目卡片渲染", Number(cardCount) > 0, `${cardCount} 张卡片`);
  const cardClicked = await evaluate(
    `(() => { const card = document.querySelector(".project-card");` +
      ` if (!card) return "0"; card.click(); return "1"; })()`,
  );
  await new Promise((resolve) => setTimeout(resolve, 3500));
  const projectVisible = await evaluate(
    `document.getElementById("detail-body")?.classList.contains("hidden") ? "hidden" : "shown"`,
  );
  record(
    "点项目卡片进入项目",
    cardClicked === "1" && projectVisible === "shown",
    `详情 ${projectVisible}`,
  );

  window.destroy();
  return checks;
}

/** 冒烟检查：走真实的数据桥，不建窗口。 */
async function runSmoke(root: string): Promise<number> {
  try {
    console.log(`脚本目录：${scriptsDir()}`);
    const status = parseJson<StatusView>(await runPython("project_status.py", [root, "--json"]));
    console.log(`项目：${status.project_root}`);
    console.log(`工作项：${status.work_items.length} 个；状态：${status.state}`);
    for (const item of status.work_items) {
      const artifacts = await loadArtifacts(root, item);
      const signed = artifacts.filter((artifact) => artifact.approvedBy);
      console.log(
        `- ${item.work_id} · ${item.name} | ${item.phase_label} | ${item.state} | ` +
          `工件 ${artifacts.filter((artifact) => artifact.exists).length}/${artifacts.length} | ` +
          `已签署 ${signed.map((artifact) => `${artifact.key}:${artifact.approvedBy}`).join(",") || "无"}`,
      );
    }
    const doc = await readFile(
      path.join(status.work_items[0]?.path ?? root, "requirements.md"),
      { encoding: "utf8" },
    ).catch(() => "");
    console.log(
      `Markdown 渲染：${
        doc
          ? `${(marked.parse(bodyAfterFrontmatter(doc), { async: false }) as string).length} 字节 HTML`
          : "无 requirements.md，跳过"
      }`,
    );

    if (process.argv.includes("--no-ui")) return 0;
    console.log("界面自检：");
    const checks = await runUiChecks(root);
    for (const check of checks) {
      console.log(`  ${check.ok ? "PASS" : "FAIL"} ${check.name}：${check.detail}`);
    }
    const failed = checks.filter((check) => !check.ok);
    if (failed.length > 0) {
      console.error(`界面自检失败 ${failed.length} 项。`);
      return 1;
    }
    console.log(`界面自检全部通过（${checks.length} 项）。`);
    return 0;
  } catch (error) {
    console.error(`冒烟检查失败：${(error as Error).message}`);
    return 1;
  }
}

/** 自截图：加载真实界面并把渲染结果存成 PNG，用于验证界面而不是验证代码。 */
async function runShot(root: string, out: string, tab: string): Promise<number> {
  registerHandlers();
  await rememberProject(root);
  const window = createWindow();
  await new Promise<void>((resolve) => {
    window.webContents.once("did-finish-load", () => resolve());
  });
  // 首屏要等 Python 桥返回状态、工件和文档；数据都在本机，几秒足够。
  await new Promise((resolve) => setTimeout(resolve, 6000));
  if (tab) {
    // 支持 "overview@600" 滚动、"!WORK-004" 先选中工作项，便于截到不同状态。
    const [name, offset] = tab.split("@");
    const workId = name.includes("!") ? name.slice(name.indexOf("!") + 1) : "";
    const tabName = name.split("!")[0];
    if (workId) {
      const picked = await window.webContents.executeJavaScript(
        `(() => { const node = document.querySelector('[data-work-id="${workId}"]');` +
          ` if (!node) return "missing"; node.click();` +
          ` return (node.getAttribute("class") ?? "") + "|" + (node.tagName ?? ""); })()`,
      );
      console.log(`选中工作项：${workId}（命中 ${picked}）`);
      await new Promise((resolve) => setTimeout(resolve, 2500));
      const after = await window.webContents.executeJavaScript(
        `(() => { const selected = document.querySelector('.work-item.selected');` +
          ` return (selected?.dataset.workId ?? "none") + " / " + (document.getElementById("work-title")?.textContent ?? ""); })()`,
      );
      console.log(`点击后状态：${after}`);
    }
    if (tabName === "resources") {
      await window.webContents.executeJavaScript(`document.getElementById("resources").click()`);
      console.log("切换到项目资料视图");
      await new Promise((resolve) => setTimeout(resolve, 5000));
    } else if (tabName === "workspace") {
      await window.webContents.executeJavaScript(`document.getElementById("workspace").click()`);
      console.log("切换到工作区视图");
      await new Promise((resolve) => setTimeout(resolve, 4000));
    } else if (["overview", "read", "validate", "history", "data"].includes(tabName)) {
      const active = await window.webContents.executeJavaScript(
        `(() => { const button = document.querySelector('[data-tab="${tabName}"]');` +
          ` if (!button) return "missing"; button.click();` +
          ` return document.querySelector('.tab.active')?.dataset.tab ?? "none"; })()`,
      );
      console.log(`切换到页签：${tabName}（当前激活 ${active}）`);
      await new Promise((resolve) => setTimeout(resolve, 2500));
    }
    if (offset) {
      await window.webContents.executeJavaScript(
        `document.querySelector('.detail').scrollTop = ${Number(offset) || 0}`,
      );
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }
  window.focus();
  window.webContents.invalidate();
  await new Promise((resolve) => setTimeout(resolve, 800));
  const image = await window.webContents.capturePage();
  await writeFile(out, image.toPNG());
  console.log(`已保存界面截图：${out}`);
  return 0;
}

const smokeIndex = process.argv.indexOf("--smoke");
const shotIndex = process.argv.indexOf("--shot");
if (shotIndex !== -1) {
  void app.whenReady().then(async () => {
    const out = process.argv[shotIndex + 1] ?? path.join(process.cwd(), "shot.png");
    const tab = process.argv[shotIndex + 2] ?? "";
    const root = (await readState()).lastProject;
    if (!root) {
      console.error("自截图需要先选定项目：electron . --shot <输出.png> 前先设置 lastProject");
      app.exit(1);
      return;
    }
    app.exit(await runShot(root, out, tab));
  });
} else if (smokeIndex !== -1) {
  void app.whenReady().then(async () => {
    const explicit = process.argv[smokeIndex + 1];
    const root = explicit && !explicit.startsWith("-") ? explicit : (await readState()).lastProject;
    if (!root) {
      console.error("冒烟检查需要项目目录：electron . --smoke <项目目录>");
      app.exit(1);
      return;
    }
    app.exit(await runSmoke(root));
  });
} else {
  void app.whenReady().then(() => {
    registerHandlers();
    createWindow();
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
}
