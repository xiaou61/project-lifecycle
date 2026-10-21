# 工件查看器（Electron + TypeScript）

读取目标项目 `.agent/` 里的工件，把工作项阶段、任务进度、审批签署和文件日期可视化；选中文件后渲染 Markdown 正文。它是 `.agent` 的**只读视图**，不替代 `project-lifecycle.ps1 status`，也不写任何工件。

## 三个视图

- **关系图谱视图**（顶栏「关系图谱」）：全宽 3D 力图，把所有工作项之间的依赖、关联和模块归属一次画出来。拖动空白处绕轴旋转，滚轮缩放，双击空白复位，点节点跳进该项目视图；悬停点亮邻域并把关系写成文字。右侧是状态分布、阶段分布和选中节点的详情。图例：圆的大小是任务量，颜色是状态（绿完成 / 蓝进行中 / 红需处理 / 灰草稿），菱形是 `.agent/INDEX.md` 模块索引里的模块。默认只开「硬依赖」——成熟项目的 `related_to` 能比依赖多一个量级（Paideia 22 依赖 vs 174 关联），三层全开仍可看但会很密。
- **工作区视图**（顶栏「工作区」）：项目数、工作项数、需要处理数、待补签工件数、缺证据验收数，加每个项目一张卡片（状态分桶、待补签、Git、最后活动），点卡片进入该项目。清单来源优先取工作区的 `.agent/PROJECT-INDEX.md`「项目清单」表的源码目录列，没有该文件时用本应用记住的清单（卡片上可移出清单）。直接打开工作区导航目录（有 `PROJECT-INDEX.md`、没有 `changes/`）时会自动进这个视图。工作区级是**汇总不是图谱**——项目之间没有可推导的边，理由见 [wiki/D-009](../wiki/D-009-工作区汇总面板.md)。
- **项目视图**：下面的五个页签。

## 五个页签

| 页签 | 内容 |
| --- | --- |
| **总览**（默认） | **阶段门槛条**：按流程顺序列出每道门，圆点颜色是状态（绿=已过、蓝=当前、红=卡住、灰虚=未到达），每道批准门显示签署人和时间，卡住的门直接把原因写在卡片里。**需求追踪图**：REQ / AC / TASK 三条带，连线只来自工件里真实写下的引用（任务的 `对应` 与 `依赖`、来源覆盖表的 REQ↔AC 配对），平时几乎不可见，悬停亮出该节点的关系、点击把关系写成文字；未映射到需求的任务、无结构化证据的验收、引用了未定义需求的 id 会标黄报警。**关联图谱**：力导向布局，三类节点与三类边——实线箭头 = 硬依赖（`depends_on`，未完成会阻塞实现和验收），虚线弧 = 关联（`related_to`，不阻塞），浅色虚线小卡 = `.agent/INDEX.md`「模块索引」登记的模块（连到它登记的工作项）。节点可拖动、画布可滚轮缩放与拖动平移、双击节点复位；悬停点亮邻域并在下方写出关系文字，点击跳到该工作项。四个图层开关（硬依赖 / 关联 / 模块 / 只看待处理）默认只开硬依赖——`related_to` 在成熟项目里能比依赖多一个量级（Paideia：22 条依赖 vs 174 条关联），全开就是面条。 |
| 阅读 | 工件卡片（状态、签署人、Git 日期）+ Markdown 正文 + frontmatter 表 |
| 校验 | `project_validate.py` 的错误和警告，按严重程度着色 |
| 历史 | `.agent/history/updates.md` 的最近记录 |
| 数据 | `project_status.py --json` 的原始输出，上色；点 `"WORK-00X"` 跳到该工作项，点 `*.md` 路径打开文件正文 |

界面显示的一切都来自那一次 `project_status.py --json` 调用，前端不做任何状态推导——状态只能有一个实现，否则就是两份会漂移的事实。追踪关系也一样，解析在 Python 的 `traceability` 块里做（见 [wiki/D-008](../wiki/D-008-需求追踪图谱.md)）。

**门槛条的两条规则**：门槛数量随风险模式变化（`managed` 不显示方案和设计两道门，把它们画成"缺失"是误导）；圆点颜色由位置决定（上游没满足却已经走到后面就是卡住），且验证报告为 `partial`/`failed`/`stale` 时点红——它们是失败态，不是"还没做"。

**追踪图的两条规则**：`id 只在工作项内唯一`（每个工作项都有自己的 `REQ-001`），所以跨工作项引用必须带 `work_id`；只画显式写下的引用，不按编号顺序推测 REQ 与 AC 的对应——猜出来的边比不画更糟。

## 前置条件

- **Python 3.9 或更高版本**。查看器不自己解析工件，而是调用 Skill 的 `project_status.py`、`project_validate.py` 和 `update_history.py` 取数据。exe 里不含 Python 运行时，目标机器需要自行安装。

## 开发运行

```powershell
cd desktop
npm install
npm start          # 编译 TS 并启动
```

## 自检

```powershell
# 数据桥 + 界面交互断言，失败返回非零；加 --no-ui 只查数据桥
npm run smoke -- "F:\我的项目"

# 启动界面并保存渲染结果
# 参数：<页签>[@滚动位置][+图层开关][!WORK编号]，页签为 overview|read|validate|history|data
npx electron . --shot ".\shot.png" overview
npx electron . --shot ".\shot.png" "overview!WORK-004"          # 先选中 WORK-004
npx electron . --shot ".\shot.png" "data@600"                    # 数据页签并下滚 600px
npx electron . --shot ".\shot.png" "overview@1150+related+modules"  # 打开关联与模块图层后截图
npx electron . --shot ".\shot.png" "relations"                   # 3D 关系图谱
npx electron . --shot ".\shot.png" "relations@0+modules+related" # 3D 图谱打开模块与关联图层
npx electron . --shot ".\shot.png" workspace                     # 工作区视图
```

界面自检用真实事件派发（`dispatchEvent`）而不是 `element.click()`：SVG 元素没有 `HTMLElement.click()`，用 `click()` 会静默什么都不做，让联动看起来"实现了"却从未被验证。首屏与工作区都用**轮询**等数据就绪，不用固定延时——固定 6 秒在慢机上会抢跑成空列表，报出假红。

自检覆盖 30 项：项目已加载、工作项列表、五个页签、门槛条、追踪图渲染节点 / 悬停亮线 / 点击详情、关系图点节点联动、图谱节点不重叠、图谱缩放按钮生效、图谱关联与模块图层开关、数据面板 JSON 与点路径联动、项目资料视图与文件渲染、工作区视图、项目卡片与进入项目、3D 关系图谱的打开 / 连线 / 分布条形图 / 悬停压暗邻域 / 拖拽旋转视角 / 点节点进入工作项。没有工作项的工作区导航目录会明确报「跳过」而不是假通过。

## 打包成 exe

```powershell
npm run pack
# 产物：release/project-lifecycle-viewer-win32-x64/project-lifecycle-viewer.exe
```

`--extra-resource=../skills` 会把 `skills/project-lifecycle/` 一并打进 `resources/skills/`，所以 exe 自带一份脚本副本、开箱可用。代价是**这份副本会随 Skill 更新而过期**：改过 `skills/` 后要重新 `npm run pack`。想在开发时用实时版本，设置环境变量指向 checkout：

```powershell
$env:PROJECT_LIFECYCLE_SCRIPTS = "F:\项目开发管理器\skills\project-lifecycle\scripts"
```

解压后目录约 326 MB（Electron 自带 Chromium/Node 的固定开销），压缩分发约 100 MB。这是选 Electron 的代价，不是本应用代码的体积。

## 结构

| 文件 | 职责 |
| --- | --- |
| `src/main.ts` | 唯一 IO 层：定位脚本目录、调用 Python、读文件、取 Git 日期、解析 `.agent/INDEX.md` 模块索引、渲染 Markdown；另有 `--smoke` 与 `--shot` 两个自检入口 |
| `src/preload.ts` | 用 `contextBridge` 暴露固定几个方法，不暴露 `ipcRenderer` 或文件系统 |
| `src/renderer.ts` | 展示与联动：门槛条、SVG 力导向关联图谱（布局/拖拽/缩放/图层开关）、JSON 上色与锚点；无 import/export，编译成浏览器可直接加载的普通脚本 |
| `src/types.d.ts` | 主进程与渲染进程共用的数据形状 |
| `index.html`、`styles.css` | 界面；CSP 关掉脚本和内联样式 |

渲染进程开着 `contextIsolation`、关着 `nodeIntegration`、`sandbox: true`，并且 CSP 是 `default-src 'none'; script-src 'self'`。工件正文按 Markdown 渲染后直接 `innerHTML`，所以这道 CSP 是必需的：它让工件里混入的 `<script>` 或事件属性无法执行。链接只允许 `http(s)` 交给系统浏览器，其余 `href` 一律移除。

## 唯一会写的文件

`%APPDATA%\project-lifecycle-desktop\state.json`，只存上次打开的项目路径。目标项目目录全程只读。
