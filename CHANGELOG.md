# 更新历史

本文件记录 `project-lifecycle` Skill 仓库本身的维护变更；目标项目的逐轮记录以 Git 提交为准，不再维护 `.agent/history/updates.md`。Git 提交是可回滚事实源。

## 2026-11-19（P1）· 静态检查门禁（ruff + mypy）、status JSON 契约测试、文档死链检查、核心引擎类型收口

- 类型：feature + refactor（不兼容：无，行为不变；新增测试与 CI 门禁）
- 变更：①**新增 ruff 静态检查**（根 `ruff.toml`，`select = E4/E7/E9/F/W`），修掉 8 处测试告警（未用 `json` 导入、3 处未用局部变量），测试目录 `E402` 因 `sys.path.insert` 引导写法按文件豁免；`python -m ruff check skills/project-lifecycle/scripts tests` 全绿。②**新增 mypy 门禁**（根 `mypy.ini`，`ignore_missing_imports`），先对核心引擎 `scripts/project_status.py` 做类型收口：把 55 处 `dict[str, object]` 收窄为 `dict[str, Any]`，并修掉类型检查暴露的 3 类真实问题——`phase_result` 的 `tasks: dict[str, int]` 注解与实参（含 `warnings` 列表）不符；`git_status` 里 `except OSError as error:` 之后又给 `error` 赋值（Py3 会删除 except 变量）；`source_coverage_status` / `testing_evidence_status` 用 `None in {...}` / `any(v is None ...)` 判空后仍直接用 `int | None` 下标，改为逐项 `is None` 提前返回以实现类型收窄。③**status JSON 契约测试**（`tests/test_status_contract.py`）：固化 `schema_version="2"` 的顶层字段集合与 work-item 字段集合，新增/改名/删字段会立刻变红，防止桌面查看器（D-007 直接消费该 JSON）静默读到缺失字段；配套 `docs/reference/status-schema.md` 记录每个字段含义与变更流程。④**文档死链检查**（`tests/test_docs_links.py`）：扫描 README 与 `docs/**/*.md` 的站内链接，按 VitePress clean URL 规则（原路径 / +`.md` / +`/index.md` / +`.html`）解析，外链与纯锚点跳过。⑤**CI** 新增独立 `lint` job（Py 3.11，装 ruff+mypy，跑 ruff 全量 + mypy 核心引擎），与既有的三版本 `test` 矩阵、`docs`、`desktop` job 并列。
- 决策：**只把 mypy 门禁压到 `project_status.py`**——它是被桌面与下游直接消费的公共契约，风险最高、最值得先守；`artifacts.py`/`project_validate.py` 仍是 `dict[str, object]` 风格（分别约 160/190 条），整体收口是一次独立、test-guarded 的 typing 任务，不塞进本轮以免把「加个检查」做成大重构。**93KB 物理拆分暂缓**：把 2251 行拆成包会冲击 `import project_status` + `python project_status.py` 的既有契约（desktop 子进程按文件名调用），需单独一轮并全程用 81 条测试守护，本轮先用 `dict[str, Any]` + 类型检查把可维护性提升到位。**类型检查暴露的是真问题不是噪音**：`except as error` 的删除语义与 `dict[str, int]` 错注解都是潜在运行时/理解坑，借 mypy 修正比单纯加门禁更有价值。
- 依据：`ruff.toml`、`mypy.ini`、`.github/workflows/ci.yml`、`skills/project-lifecycle/scripts/project_status.py`、`tests/{test_status_contract,test_docs_links,test_project_status}.py`、`docs/reference/{status-schema.md,index.md}`。
- 验证：`python -m ruff check skills/project-lifecycle/scripts tests` 全绿；`python -m mypy skills/project-lifecycle/scripts/project_status.py` → `Success: no issues found`；`python -X utf8 -m unittest discover -s tests -p "test_*.py"` 共 **81 条全部通过**（新增 `test_status_contract` 1 条、`test_docs_links` 1 条）；`python -m compileall -q skills/project-lifecycle/scripts` 通过；`git diff --check` 无空白错误。
- 本地提交：见本轮提交。
- 远端推送：见本轮推送。

## 2026-11-19 · 收尾：清除 update_history 残留、修复红色测试、补文档命令一致性测试

- 类型：fix + refactor（不兼容：测试与文档，不涉及目标项目结构）
- 变更：完成 2026-10-28（`9fa5e3a`）删除按轮更新历史（`update_history.py` / `.agent/history/updates.md`）的收尾。此前删除只做了脚本与文档主干，`tests/`、`desktop/`、README、VitePress 文档、示例仍引用已删模块——`python -m unittest discover -s tests` 只能收集 14 条、2 个模块 import 失败（一次「Ran 0/14 tests 通过」的假通过）。本次：①测试改用 `artifacts.py`（`load_artifacts_module`，移除 `load_update_module`/`UPDATE_SCRIPT`），删掉 3 条针对已删命令的用例，新增 `test_init_does_not_create_history`，断言 init 不再创建 `.agent/history`；②`desktop/src/main.ts` 的「历史」页签改读 `git log`（`load-history` IPC），删除 history 工件分类与 `updates.md` 回退，`index.html`/`renderer.ts`/`types.d.ts` 文案「历史」→「提交」，`desktop/README.md` 同步；③README、`docs/reference/commands.md`、`docs/guide/qa.md`、`docs/guide/full-workflow.md`、`docs/guide/getting-started.md`、`docs/guide/resume.md`、`docs/reference/index.md`、`docs/architecture.md`、`examples/managed-walkthrough.md` 去掉 `updates`/`record`/`checkpoint`/`push-check` 命令与 `update-history.md` 引用，改用 `git commit` / `git status --porcelain`；④`tests/test_skill_packaging.py` 新增 `DocumentedCommandsTest`：扫描 README、docs、skill 参考与示例里所有 `$lifecycle <cmd>` 调用，断言命令都存在于 `COMMANDS`（CHANGELOG/wiki 有意保留旧命令名以如实记录当时的决策，故不扫描）。
- 决策：**文档命令漂移必须由测试兜住**——旧命令能留在十来份文档里，是因为「命令映射→脚本存在」有测试、「文档里的调用名」没有；加一条正则扫描，把这类残留固化成红色，顺带抓出并修掉了 `docs/guide/resume.md` 里遗留的 `$lifecycle checkpoint` 示例。**历史不改写**——`wiki/D-006/D-007/D-009` 与 `CHANGELOG.md` 旧条目如实记录当时围绕 `updates.md` 的决策，保留原文，仅在本条说明其已被取代。**`desktop/release/` 打包产物不动**（git 未跟踪，重新打包即可）。
- 依据：`skills/project-lifecycle/scripts/{project-lifecycle,project_status,artifacts}.py`、`tests/{test_project_status,test_lifecycle_actions,test_skill_packaging}.py`、`desktop/src/{main,renderer}.ts`、`desktop/src/types.d.ts`、`README.md`、`docs/**`、`skills/project-lifecycle/examples/managed-walkthrough.md`。
- 验证：`python -X utf8 -m unittest discover -s tests -p "test_*.py"` 共 **79 条全部通过**（此前只有 14 条可收集、2 个模块 import 失败）；`tests/test_skill_packaging.py` 6 条通过（含新增 `test_documented_commands_are_known`）；`python -m compileall` 通过。
- 本地提交：见本轮提交。
- 远端推送：见本轮推送。

## 2026-10-28 · 精简 Skill：删长期记忆、HTML 材料与核心历史，合并 5 个参考文件

- 类型：refactor（不兼容：目标项目结构）
- 变更：**参考文件 15 → 7**，Skill 正文 91.1 KB → 72.6 KB（-20%），包内文件 26 → 16。删除 `references/memory.md`、`html.md`、`core-history.md`、`requirements-interview.md`、`relationships.md`、`rules.md`、`notes.md`、`specs.md`，以及 `scripts/generate_core_history.py`、`history` 命令、`agents/openai.yaml`、`scripts/__pycache__`。**删的是工件类型，不只是文档**：初始化器不再创建 `.agent/memory.md` 和 `.agent/html/`，INDEX/README 模板不再登记；查看器去掉「长期记忆」「理解材料」两个分组和 core-components 提示。**合并保留能力**：需求深挖并入 `requirements.md`；工作项标识/frontmatter/依赖关系、规则优先级、稳定规格、决策说明并入 `workflow.md`（含归档后旧路径引用与 `approver` 默认签署人规则）；`SKILL.md` 删除与 workflow 重复的「每轮顺序」，命令清单去掉 `history`（12 → 11 个）。README、VitePress 教程、架构组件、QA（33 → 31 题）同步去掉已删功能，并修正 `workspace.md` 归因机制停用后仍留在文档里的旧描述。
- 决策：**没有校验的记忆就不是约束**——`project_status.py`/`project_validate.py` 从不解析 `MEM-*`，它只带来手工编号和 `stale`/`superseded` 的簿记成本；跨任务事实由 `rules/always.md`、`specs/` 和 `notes/` 承担。**核心历史就是 `git log --follow` 的投影**——为它维护 units JSON、post-commit hook、`--check` 和重命名规则不划算。**HTML 理解材料需要逐次授权**——政策四段里只有“先征得同意”是硬约束，不再单列工件目录。**合并而不是删规则**：优先级链、frontmatter 字段、`approver` 默认值、规格更新与归档引用检查都是脚本或流程依赖的事实，逐条搬进 `workflow.md` 后才删除原文件。**不做兼容迁移**：老项目残留的 `memory.md`/`html/` 不被任何校验或状态读取，保留为孤儿文件无害，不自动删除用户资料。
- 依据：`skills/project-lifecycle/SKILL.md`、`references/{workflow,requirements}.md`、`scripts/{init_project,project-lifecycle,project_status}.py`、`tests/test_project_status.py`、`desktop/src/main.ts`、`README.md`、`docs/`。
- 验证：`python -m unittest discover -s tests -p "test_*.py"` 共 80 条通过；`compileall` 通过；`npm run build`（desktop tsc）与 `npm run docs:build` 通过；临时目录 `init` 实测只创建 `rules/specs/changes/notes/references/history/scripts` 与 `INDEX.md`、`README.md`、`history/updates.md`，不再有 `memory.md`/`html/`。
- 本地提交：见本轮提交。
- 远端推送：见本轮推送。

## 2026-10-21（第二轮）· 反借口表、体积减法、签署人默认值与 worktree 三态、全量中文化

- 类型：feature + refactor
- 变更：**四个阶段参考文件新增统一小节「常见借口与反驳」**（`requirements.md` 5 条、`tasks.md` 5 条、`testing.md` 5 条、`workflow.md` 6 条），把该阶段最常见的省事路径连同反驳和应采取的动作写在同一张表里；`SKILL.md` 的「参考入口」加一行指向它们。每行第三列都对应同文件已有的规则，不引入新标准；`testing.md` 刻意不重复「完成前的硬门」已驳回的说法。**`SKILL.md` 减重 22%**（5126 → 3977 字符）：删掉三条脚本实现细节、「用户入口」整段对 `workflow.md` 表格的复述、与 `tasks.md` 重复的三条抓手、风险路由里的 yaml 示例。**`approve --by` 可省略**：新增 `resolve_signer()`，显式传入优先，其次取 `.agent/rules/always.md` frontmatter 的 `approver:`，都没有时报错而不猜；argparse 的必填校验相应改为函数内判断。**`worktree.decision` 增加 `proceed`**：工作区干净时不再打断用户，只有 `ask_user`（有未提交改动）才问一次；`active` 表示已在 worktree 内。**允许批准后连续执行**：`SKILL.md` 与 `workflow.md` 阶段门槛都写明可执行到每个任务自己的验证为止，范围变化、验证失败或新决策点才停。**新增探针任务**：`tasks.md` 允许交付物是决策记录的任务（结论写入 `.agent/notes/` 并被后续任务引用），避免为"验证某个 API 能不能用"编造行为断言去撞验证硬门。**全量中文化**：`design.md`、`proposal.md`、`specs.md`、`memory.md`、`core-history.md` 五个全英文文件与 `requirements.md`、`tasks.md`、`testing.md` 三个混血文件里的英文段落全部译为简体中文；`SKILL.md` 恢复一行语言规则——原始提交里有 "Output Language" 段，在 2026-08-31 的 `d5b8bce` 精简中被删除，但语言分布仍留在各文件里。
- 决策：**反借口表只放 4 个文件，不铺 11 个**——查阅型参考（`html.md`、`relationships.md`、`update-history.md`）不存在"agent 图省事"的阶段动作，加进去只是噪音。**副作用要抵掉**：加表之后检查并删掉了复述同文件紧邻规则的行，因为同一文件里说两遍比不写更伤遵守度。**默认签署人只补身份，不补批准**——是否批准仍取决于用户当轮是否明确确认，模型不能因为 `always.md` 里有 `approver` 就自己调 `approve`；这条边界写在 `resolve_signer` 的 docstring、`rules.md` 和 `workflow.md` 三处。**worktree 询问的触发条件改为事实驱动**：原来不管工作区多干净都要打断一次，而 `git status` 一直知道答案；`proceed` 的值由已有的 `git["status"] == "clean"` 推导，不新增探测。**统一中文而不是双语**——产出、文档、命令输出、历史记录全是中文，保留英文只会让一半文件继续悬空；当初偏英文的理由是"指令遵循更稳"，但本 Skill 最重的几条规则靠脚本机械校验，不靠模型读英文的自觉。
- 依据：`skills/project-lifecycle/SKILL.md`、`references/{requirements,tasks,testing,workflow,rules,design,proposal,specs,memory,core-history}.md`、`scripts/update_history.py` 的 `resolve_signer`、`scripts/project_status.py` 的 `resume_context`、`docs/guide/resume.md`、`docs/reference/commands.md`、`tests/test_lifecycle_actions.py`、`tests/test_project_status.py`。
- 验证：`python -m unittest discover -s tests -p "test_*.py"` 共 80 条全部通过（新增 `test_by_falls_back_to_project_approver`、`test_by_missing_everywhere_refuses_to_guess` 两条；原 `test_worktree_question_only_fires_outside_a_linked_worktree` 因行为约定变更改名为 `test_worktree_question_only_when_workspace_is_dirty`，改为断言三态）。两处冒烟实测：`.agent/rules/always.md` 无 `approver` 且未传 `--by` 时命令报错并给出配置指引；写入 `approver: 王五` 后省略 `--by`，落章为 `approved_by: 王五`。全量中文化后扫描全部 reference，除标识符、路径、命令外无成段英文；SKILL.md 与 references 之间的相对链接全部可解析；两处安装（`~/.agents/skills`、`~/.codex/skills`）均为指向仓库的符号链接，无需另行同步。
- 本地提交：见本轮提交。
- 远端推送：未执行。

## 2026-10-21 · 跨平台入口、触发描述、文档自检、实施前 worktree 询问与初始化精简

- 类型：fix + feature
- 变更：**初始化不再把 Skill 脚本复制进目标项目**——`init_project.py` 原会把 `generate_core_history.py` 拷到 `.agent/scripts/`，而 `.agent/README.md` 模板与 `SKILL.md` 都写着"状态、恢复和严格校验脚本属于已安装 Skill 的内部实现，不在目标项目 `.agent/scripts/` 中查找"。每个项目因此多一份会随 Skill 升级而过期的副本；现在只创建空目录供项目自己放辅助脚本，`history` 命令本来跑的就是 Skill 目录里的版本。`copy_if_missing` 与 `shutil` 导入随之删除。**实施前询问 worktree**——`SKILL.md` 第 5 步与「触发与不触发」表要求：即将改源码、测试、配置或工件时，先问一次要不要为这个 `WORK-*` 开独立 worktree，用户同意才 `git worktree add`。`references/workflow.md` 写明触发点、前置核对（Git 仓库、分支/目录未占用、**该工作项的 `.agent/changes/` 已提交**——worktree 只检出已提交内容）和决定落库方式。`project_status.py` 的 `git` 概览新增 `worktree.linked`（由 `git rev-parse --git-dir` 与 `--git-common-dir` 是否相同判定，不依赖目录名），`resume --json` 在实施阶段带出 `worktree.decision`：`active`（已隔离，不重复问）或 `ask_user`（主工作树，改代码前问一次）。**修复一条假通过的自检命令**——`SKILL.md` 原让在 `scripts/` 下跑 `unittest discover`，实测 `Ran 0 tests ... OK`（测试实际在仓库根 `tests/`），与 Skill 自己的"无证据不算通过"底线冲突；现改为 `-s tests` 并写明 `Ran 0 tests` 不算通过。**新增跨平台入口**：命令映射抽到 `scripts/project-lifecycle.py`，`project-lifecycle.ps1` 与新增的 `project-lifecycle.sh` 只做转发，命令表只维护一份；SKILL.md 顶部补 `$lifecycle` 的宿主解析规则，不再让 Agent 照字面执行裸 `project-lifecycle.ps1`。**`$lifecycle` 定义只留一处**：`workflow.md` 里三处重复的路径定义删掉，改为指向 `SKILL.md` 顶部。**描述扩到真实触发词**（写需求、把需求问透、拆任务、验收、继续上次的活、归档）并写明不适用场景（一次性问答、纯代码审查、单文件小修复）。**SKILL.md 新增「触发与不触发」对照表**，把六种常见说法直接映射到动作。**去掉重复的风险表**：`workflow.md` 不再抄一份 `lite/managed/strict` 表格，只指向 `SKILL.md`。新增 `examples/managed-walkthrough.md`（一个 `WORK` 从需求到归档的最小完整示例）；补 `LICENSE`（MIT）与 frontmatter `metadata.version`。`tests/test_skill_packaging.py` 把这次的漂移变成断言：SKILL.md 引用的路径必须存在、相对链接不得死链、命令映射必须指向存在的脚本。
- 决策：**初始化器不再分发脚本副本**——副本让"Skill 升级后行为一致"这个前提失效，而目标项目里没有任何东西引用它（`F:\Paideia` 实测）。**worktree 只问一次，且用工件信号判断而不是靠记忆**——`resume` 输出的 `decision` 由 Git 的 git-dir/git-common-dir 差异推导，agent 不必自己判断"是不是已经在 worktree 里"，避免每轮重复追问。**只问不代开**：创建 worktree 会改变用户的工作目录布局，属于用户决定；Agent 只负责核对前置条件并在同意后执行。**把"工件已提交"写成硬前置**：`.agent/` 虽入库，但未提交的需求/任务文件不会被新 worktree 检出，直接开会得到"空工作项"，这是这个功能最容易踩的坑。**入口映射放进 Python 而不是让 `.sh`/`.ps1` 各写一份**——两份 switch 必然漂移，而 `.ps1` 原来的 45 行里 30 行是重复的映射与参数补全。`$lifecycle` 统一为占位符，是因为原文档把 Windows 路径写进了所有示例，macOS/Linux 用户无从下手。补 `examples/` 而不是继续加规则段落：执行者缺的是"长什么样"，不是"还有哪条规矩"。
- 依据：`skills/project-lifecycle/SKILL.md`、`references/workflow.md`、`scripts/project-lifecycle.py`、`scripts/project_status.py` 的 `git_status`/`resume_context`、`scripts/init_project.py`、`tests/test_skill_packaging.py`、`tests/test_project_status.py` 的 `test_worktree_question_only_fires_outside_a_linked_worktree`。
- 验证：`python -m unittest discover -s tests -p "test_*.py"` 共 78 条全部通过（新增 6 条）；`python -m compileall` 通过；`project-lifecycle.py --help`/未知命令返回码正确；`pwsh` 经 `.ps1` 在真实项目 `F:\Paideia` 上跑 `brief --json` 返回 `WORK-027` 等活动项。worktree 判定在临时仓库上双向实测：主目录 `linked=false`、`worktree add` 出来的目录 `linked=true`，`F:\Paideia` 上 `resume WORK-027` 返回 `decision: ask_user`，`validate` 0 error。临时项目上 `init` 两次均成功且第二次全部"保留"，`.agent/scripts/` 为空目录，`history --help` 仍可用。`.sh` 与 macOS/Linux 原生路径**未实测**。
- 本地提交：待用户授权。
- 远端推送：未执行。

## 2026-10-18 · 状态可信度修复、brief 入口、批量签署与归档

- 类型：fix + feature
- 变更：**任务解析不再静默失效**——`task_counts` 现在认四种真实写法（`### TASK-001 | done | 名称`、带“状态”列的表格、`## T-01 名称` 加复选框小节、散落复选框），并在任务编号存在却一个都解析不出时返回错误级提示，不再把未完成工作项显示成“没有任务”。**验证锚点改为按路径判定**：未提交改动里 `.agent/` 之外的源码才影响结论，`code_sync` 新增 `drift` 状态（报告覆盖到它绑定的提交，之后的提交属于后续工作），只有锚点之后**已提交**源码或完全取不到路径清单时才报 `stale`。**提示分三层**：`warnings`（真阻塞，阻止自动恢复）、`hygiene`（文档体积、任务状态格式）、`advice`（计划质量建议）。**新增 `brief` 入口**：只输出活动工作项、阻塞与下一步，16 个工作项的项目上从 225 KB 降到约 2 KB。**`resume --json` 只返回恢复上下文**（原来把整份 status 原样吐出，文档承诺的 `auto_resume`/`blockers` 被淹没）。**新增 `approve --artifact all`**：一次签完已存在的阶段工件，只追加一条 decision 记录（此前每签一次写一条，历史里约 28% 是签名噪音）。**新增 `archive` 入口**：把“完成沉淀 + 已完成”的工作项移进 `changes/archive/YYYY-MM-DD-<名称>/`，只移动目录不改内容。**文档吸收 Superpowers 的三条**：`tasks.md` 增加接口块、步骤粒度判据、`## 评审焦点`（规格暗示但无任务测试覆盖的失败模式，每条指到任务与测试名）与四条质量门；`testing.md` 增加“结论 → 必须跑的命令 → 判据”对照表；`SKILL.md` 从目录页改为可照做的六步入口加三条底线。`tests/` 新增 `test_task_parsing.py`（7 条）与 `test_lifecycle_actions.py`（9 条）。
- 决策：**任务台账读不出状态时不以乐观推断代替证据**——但也不推翻已 `passed` 的验证报告：报告是完成证据，台账只是计划记录，`passed` 之后的状态缺口只进 `hygiene`（`test_document_budget_warns_without_blocking_work` 固定了这条边界）。**`drift` 不撒谎**：它不推翻当时的验证结论，也不声称“现在仍然成立”，两者在 `settlement_status` 与 `note` 里分开写。**不搬 Superpowers 的“每任务派子代理 + 独立评审”执行模型**：它的价值前提是执行者完全没有上下文，而本 Skill 的前提正相反（`resume` 就是为了从工件恢复上下文）；单人单 agent 场景下，那是同一个模型换个身份重读一遍文件。**`hygiene` 不并进 `resume.warnings`**：文档体积超阈值不等于恢复被阻塞；`advice` 更只对“已批准、尚未 `passed`”的 `strict` 工作项提示，回头给历史项补计划不会改变已发生的事。**归档只移动目录**：改写被归档工件里的路径会伪造历史，旧路径引用交给 `validate` 报告，`updates.md` 作为追加式时间线豁免。
- 依据：`references/tasks.md`、`references/testing.md`、`references/workflow.md`、`SKILL.md`、`project_status.py` 的 `parse_task_states`/`verification_anchor`/`state_evidence`/`plan_hygiene`、`update_history.py` 的 `approve`/`archive_completed`。
- 验证：`python -m unittest discover -s tests` 在 Python 3.9.13 上 **72 条全部通过**（`test_project_status.py` 56 + `test_task_parsing.py` 7 + `test_lifecycle_actions.py` 9）；`python -m compileall skills/project-lifecycle/scripts` 通过；`npm run docs:build` 完成（12.01s）；`desktop` 的 `tsc` 通过。真实项目 `F:\Paideia`（17 个工作项）上核对：`brief` 2.2 KB、`status --json` 247 KB、`resume --json` 13.7 KB、`validate` 0 error；任务解析从“16 项中 8 项报 0 个任务”变为 17/17 全部读出真实任务数；永久 `needs_attention` 从 10 项降到 1 项（WORK-010，确无验证报告）。修复了三个由本轮改动引入、又被仓库既有测试抓出的回归：`resume` 误把 `hygiene` 当阻塞、`verification_anchor` 在拿不到路径清单时给出过度乐观的 `verified`、`tasks` 字典新增字段后破坏等值断言。另有三条陈旧断言随“工作区归因机制停用”更新为断言停用后的行为。
- 本地提交：见本轮提交。
- 远端推送：已推送至 `origin/main`。

## 2026-09-20 · 审批签署、需求追踪图谱与工件查看器

- 类型：feature
- 变更：新增第 10 个用户命令 `approve`，把用户确认盖章成带审批人和脚本时间戳的签署记录——它同时把工件 `status` 置为 `approved`、写入 `approved_by`/`approved_at`/`approver_role`（`--artifact test-report` 时写 `accepted_by`/`accepted_at`）并向 `updates.md` 追加一条 decision 记录；签署范围限定为已有阶段门槛的 `requirements`/`proposal`/`design`/`tasks` 加验证报告的业务验收，`lite` 短路径、`testing/plan.md` 和 `.agent/specs/` 不签。`project_status.py` 新增 `approval` 投影（已签署/待补签/格式无效/业务验收）、`state_label` 字段和 `traceability` 追踪投影（REQ/AC 定义、任务的 `对应` 与 `依赖`、来源覆盖表的 REQ↔AC 直连边、未映射任务、无结构化证据的验收、未定义引用），`status` 文本输出与 `resume` 的 `work_item` 都会显示签署人、角色和时间；`project_validate.py` 把"已批准但缺签署"按兼容性警告报告（`--strict` 视为失败）、把签署时间戳格式错误按错误报告。`update_history.py` 把三处重复的记录拼接收敛成一个 `append_history_entry`（时间戳只在一个地方盖）。新增 `desktop/`：Electron + TypeScript 的只读工件查看器，两个视图——**工作区**（项目数/工作项数/需要处理数/待补签工件数/缺证据验收数，加每个项目一张卡片，点卡片进入该项目；清单来源优先取工作区 `.agent/PROJECT-INDEX.md`「项目清单」表的源码目录列，没有该文件时用应用记住的清单，直接打开工作区导航目录时自动进这个视图）与**项目**（五个页签——**总览**（七道阶段门槛条，每道门显示状态、签署人和卡住原因；**需求追踪图**，REQ/AC/TASK 三条带、连线悬停才亮、点击把关系写成文字、缺口标黄；工作项依赖/关联关系图，点节点联动）、**阅读**（工件卡片 + Markdown 正文，含每个工件的状态、签署人、Git 日期）、**校验**、**历史**、**数据**（`project_status.py --json` 的原始输出，上色并把 `"WORK-00X"` 和 `*.md` 路径做成可点跳转的锚））；去掉了 Electron 默认菜单栏，可打包成 Windows exe，`--smoke` 自检含 17 项界面交互断言，`--shot` 自截图可指定页签、滚动位置和预选工作项。README、`docs/reference/commands.md`、`docs/reference/index.md`、`docs/architecture.md`、`SKILL.md` 与 `references/` 下的 `workflow.md`、`update-history.md`、`requirements.md`、`proposal.md`、`design.md`、`tasks.md`、`testing.md` 同步了签署协议与命令清单；CI 新增 `desktop` job 做类型检查和编译（`npm ci --ignore-scripts`，不下载 Electron 二进制）；新增 `wiki/D-006`、`wiki/D-007`、`wiki/D-008`、`wiki/D-009`。
- 决策：签署字段只能由命令入口写，因为让模型自己填 `approved_by` 等于让模型替用户签字——字段存在但不可信，比没有字段更糟；时间戳由脚本盖，姓名由 `--by` 必填传入，并同时落进追加式的 `updates.md`。缺签署**不**并进 `item["warnings"]`，否则 `resume_context` 会把它当阻塞项，一次升级让全部历史工作项变成不可自动恢复；兼容期只由 `validate` 报告、`--strict` 拦截，旧工件按需补签。不引入项目身份名单：`--by` 是自由文本，名单只防拼写和编造，单人项目不值得再加一个文件和一套表格解析，多人协作真需要身份校验时再加。签署字段的语义在文档里明确写成流程证据而不是密码学证据。查看器侧的决定是状态推导和追踪解析都留在 Python（`spawn` 调 `project_status.py --json`），不在 TS 里重新解析工件，否则就是 D-003 禁止的第二份状态；Markdown 渲染放在主进程，渲染进程因此不需要打包器；工件正文 `innerHTML` 的安全由 CSP 覆盖（`default-src 'none'; script-src 'self'`），不引入清洗库。门槛条的两条规则是踩出来的：**门槛数量随模式变化**（`managed` 不显示方案和设计两道门，把它们画成"缺失"是误导）；**位置决定红点**（上游没满足却已经走到后面就是卡住），且报告为 `partial`/`failed`/`stale` 时必须点红——它们不是"还没做"而是失败态。追踪图谱的决定见 D-008：只画工件里显式写下的引用，不按编号顺序推测 REQ↔AC 的对应（AutoTest 的 `AC-001` 同时挂在 5 个 REQ 下，编号根本不一一对应，猜出来的边比不画更糟）；id 只在工作项内唯一，节点 key 必须带 `work_id`；70+ 条边全量连线是面条，所以默认几乎不可见、悬停才亮；工作区级不画图（项目之间没有可推导的边），应该是汇总，见 D-009：清单来源按「当前目录的 PROJECT-INDEX.md → 父目录的 → 应用自己记住的清单」顺序尝试，界面明确写出清单来自哪里；汇总只对 `project_status.py --json` 已有的字段相加，不产生新语义；「最后活动」优先 Git 提交时间、其次 updates.md 最后一条记录，两者都没有就如实说没有（不用目录 mtime 兜底，目录 mtime 在文件被修改时不会变）；`scope: workspace` 的导航目录没有工作项是正常的，打开它直接进工作区视图而不是显示错误。解析要认下真实存在的四种定义写法、区间语法 `AC-006~AC-009`、`旧版` 前缀和同行 `对应/依赖`——旧工件不会因为工具升级被重写。界面自检用真实事件派发而不是 `element.click()`：SVG 元素没有 `HTMLElement.click()`，用 `click()` 会静默什么都不做，让联动看起来"实现了"却从未被验证。exe 用 `--extra-resource=../skills` 内置脚本副本换取开箱可用，代价是 Skill 更新后要重新打包，`PROJECT_LIFECYCLE_SCRIPTS` 可指向实时 checkout。本次是向后兼容的新增（新命令、新字段、新警告、新目录），按 MINOR 建议记为 `v0.1.0`；实际打 tag 和发布需用户明确授权，本轮未执行。
- 依据：`wiki/D-006-审批人与签署.md`、`wiki/D-007-查看器不重新实现状态推导.md`、`wiki/D-008-需求追踪图谱.md`、`references/workflow.md` 的“签署”与阶段门槛表、`references/testing.md` 关于 `passed` 不等于业务验收的既有规定、`project_status.py` 的 `STATE_LABELS` 与 `state_evidence` 实现。
- 验证：57 个单元测试在 Python 3.9.13 与 3.14.0 上全部通过（新增 7 个签署用例和 5 个追踪用例：区间展开与截断、四种定义写法、同行 `对应/依赖`、未映射与未定义引用、来源覆盖表才产出 REQ↔AC 直连）；`python -m compileall` 通过。端到端在临时项目上验证：`project-lifecycle.ps1 approve` 写入 frontmatter 与 `updates.md`（两处时间戳一致），`status` 文本输出显示三处签署和一处验收，`resume` 的 `work_item.approval` 正确且不因缺签署阻塞。追踪解析在三个真实项目上核对：AI测试平台 4 个工作项（REQ 8/5/4/0、AC 9/5/4/0、TASK 12/3/3/3、依赖边 14、未映射任务 1、无证据验收 9/9）、AutoTest WORK-001（REQ 10、AC 9、TASK 15、依赖边 20、来源覆盖表直连边 16）、Code-Nest 两个工作项（含无粗体的 `- REQ-001：` 写法与同行 `对应/依赖`）。桌面端：`tsc` 类型检查与编译通过；`--smoke` 在开发态和打包后各跑一遍，17 项界面自检在四个目录上全部通过：`F:\AIAM开发`（工作区导航目录，13 项，4 项工作项相关断言明确报跳过）、`F:\AIAM开发genticiam-pdp`（走 PROJECT-INDEX.md 清单，4 张卡片）、`F:\AI测试平台`（走应用清单）、`F:\AutoTest`（单工作项，联动断言报跳过）；覆盖项目已加载、工作项列表、5 个页签、门槛条 7 道门、追踪图节点与悬停亮线（主动找有连线的工作项再验）、点击详情、关系图点节点联动、数据面板 JSON 与点路径联动、工作区视图与项目卡片；`--shot` 对总览（`strict` 7 道门与 `managed` 5 道门各一张）、追踪图（AI测试平台与 AutoTest 各一张）、阅读、校验、历史、数据逐张核对。真实项目 `F:\AI测试平台`（4 个工作项，全部是"已批准但未签署"的历史工件）上确认：`status` 的状态判定未因签署改动而变、`resume` 未被阻塞，`validate` 每个工作项只多出 1 条签署警告。自检和实测还抓出四个只有跑真实数据才会暴露的问题：冒烟模式漏注册 IPC handler 导致界面根本没加载（页签断言因此假通过，已补"项目已加载"前置检查）；Chromium 对被遮挡窗口跳过重绘、`capturePage()` 返回旧帧（已用 `disable-backgrounding-occluded-windows` 加截图前 `invalidate()` 修掉，这也是先前"页签点击没生效"假象的真因）；追踪解析用 `if/elif` 导致同行写法下 `依赖` 永远解析不到（已改为两个独立判断）；`expand_trace_ids` 先扫区间再扫单个 id 丢掉了原文顺序（已改为单次扫描）；自检在 pdp 上假失败，因为 pdp 的第一个工作项没有 tasks.md、确实没有连线，断言不该依赖「碰巧选中的那个有边」（已改为主动遍历工作项找有连线的那个再验悬停）；工作区卡片用 `path.resolve` 得到的反斜杠路径与配置里的正斜杠比较导致「当前项目」标记错位（已归一化）。`npm run pack` 产出 `release/project-lifecycle-viewer-win32-x64/project-lifecycle-viewer.exe`（解压 326 MB），打包版自检与界面截图均与开发态一致。
- 本地提交：待用户授权。
- 远端推送：未执行。
- 部署：未执行；`docs/` 有内容改动（命令清单新增 `approve`），教程站需单独授权后重新构建部署。

## 2026-09-15 · Python 3.9 兼容、版本守卫、CI 门与决策说明规范

- 类型：maintenance
- 变更：修复命令适配器在 Python 3.9 下完全不可用的问题——`init_project.py` 补显式编码声明（3.9 的 tokenizer 在无声明且单行超过 512 字节含非 ASCII 时误判编码），并把 4 处 `Path.write_text(..., newline="\n")`（Python 3.10+ 才有 `newline`）改为语义等价的 `write_bytes((...).encode("utf-8"))`；`project-lifecycle.ps1` 增加最低版本守卫，低于 3.9 时报出解析到的版本，而不是让源码编码的 SyntaxError 冒出来；新增 `.github/workflows/ci.yml`，在 Python 3.9/3.11/3.13 上执行编译与单元测试，并单独构建 VitePress 站点，CI 使用 `checkout@v7`、`setup-python@v7`、`setup-node@v7` 并把 Node 固定为 24；新增 `references/notes.md` 定义 `.agent/notes/` 的取舍范围、写作结构、命名和失效规则，并接入 `SKILL.md`、`README.md` 与 `rules.md`；`project_validate.py` 新增归档死链检查，把仍指向归档前路径的引用作为警告报告；`proposal.md` 要求先写备选方案最强的一面并记录所选方案的代价；把 `README.md` 和 5 个 docs 页面里 18 处硬编码的 `$env:USERPROFILE\.codex\skills\...` 入口路径统一为按宿主解析的 `$lifecycle` 占位符（其中一处还写死了本机用户名）。
- 决策：选择支持 Python 3.9，而不是把下限提高到 3.10——阻碍只有 5 处等价改写，而适配器在本机回退到的正是 3.9，提高下限会让 `init` 在只装 3.9 的机器上继续失败；`write_bytes(text.encode("utf-8"))` 与 `write_text(..., newline="\n")` 输出逐字节相同，不引入行为变化。版本守卫不用 `$LASTEXITCODE` 判定，避免空值被当成失败。归档死链检查只做子串匹配并按警告报告，因为它分不清仍然有效的链接和叙述历史位置的行文；`.agent/history/updates.md` 是追加式时间线，明确豁免不回改。CI 不加 `git diff --check`：`actions/checkout` 默认浅克隆，`HEAD~1` 和 merge-base 都不可用，配 `|| true` 等于不检查。CI 的 action 直接对齐当前主版本而不是沿用旧版：`v4`/`v5` 已触发 Node 20 弃用告警，升级前确认了 `python-version`、`node-version`、`cache` 三个输入在 v7 中仍然存在；Node 固定为 24，因为本机构建正是在该版本上验证通过的。本次是向后兼容的新增（新警告、新守卫、兼容性修复），按 `PATCH` 记为 `v0.0.3`。
- 依据：`tests/test_project_status.py` 的多版本实测结果、`docs/reference/index.md` 的维护者检查清单、`wiki/D-005-python-版本下限.md`、`wiki/README.md` 的决策记录门槛、`references/workflow.md` 的入口约定。
- 验证：45 个单元测试在 Python 3.9.13、3.11.5、3.14.0 上全部通过（修复前 3.9 为 3 failures + 2 errors）；`python -m compileall` 通过；`skill-creator/quick_validate.py` 报告 Skill is valid；VitePress 构建通过；`git diff --check` 无错误；Skill 内 Markdown 相对链接全部可解析；`project-lifecycle.ps1` 在临时项目上完成 init/status/validate 端到端验证，版本守卫对 3.8 拒绝、3.9 及以上通过。推送后 GitHub Actions 运行 `34952181907` 的 4 个 job（`test` 3.9/3.11/3.13 与 `docs`）全部成功，本仓库此前没有任何 CI，这是第一次由机器而不是由 Agent 自述来确认测试结果。
- 本地提交：发布提交 `6bba6c8`。
- 远端推送：已推送 `main` 和 `v0.0.3`，用 `git ls-remote` 核对 `refs/heads/main` 与 `refs/tags/v0.0.3^{}` 均指向 `6bba6c8`，`v0.0.1` 和 `v0.0.2` 保持不移动。
- GitHub Release：[v0.0.3](https://github.com/xiaou61/project-lifecycle/releases/tag/v0.0.3)。
- 部署：未执行。本次改动了 `docs/` 下 5 个页面，教程站仍停留在 `v0.0.2` 内容；部署需要单独授权，上一版 release 目录和 `current` 指向保持不变。

## 2026-09-10 · 建立设计 wiki

- 类型：docs
- 变更：新增 `wiki/` 目录和入口导航，收录 4 篇设计决策记录：`D-001` 保留单一 Skill 而非拆分、`D-002` 风险三档路由、`D-003` 状态从工件推导而非状态文件、`D-004` 不提供文件锁而用 Worktree 隔离；在 `docs/reference/index.md` 的维护地图增加一行入口。
- 决策：本仓库此前没有承载“当初为什么这么设计”的位置 —— 目标项目有 `.agent/notes/`，设计理由在本仓库只散落在本文件“决策”字段和 commit message 里；wiki 只收录从代码和现有文档推不出来的内容（被否掉的备选、取舍代价、改动影响），不复制 `docs/` 已讲清的内容；每篇写明“什么情况下该重审”作为失效条件；这是文档增量且不改脚本行为，不单独发行新版本。
- 依据：`docs/architecture.md` 对单一 Skill 的说明、`skills/project-lifecycle/references/workflow.md`、`skills/project-lifecycle/references/update-history.md` 对 `.agent/notes/` 的定位、`project_status.py` 的 `state_evidence` 实现。
- 验证：wiki 内相对链接目标存在；Markdown 表格列数一致；44 个单元测试通过；Python 编译通过；Skill 校验通过；VitePress 构建通过；`git diff --check` 通过。
- 本地提交：本轮文档提交。
- 远端推送：随本轮提交推送 `origin/main`。

## 2026-09-10 · 忽略 playwright 工作目录

- 类型：maintenance
- 变更：在 `.gitignore` 增加 `/.playwright-cli/`，与既有 `/output/playwright/` 规则同类；此前该目录里 59 个 Playwright 会话日志和快照一直以未跟踪状态出现在 `git status` 中。
- 决策：只加忽略规则，不删除本地文件、不改目录内容，也不把会话产物纳入版本管理；这是仓库级元数据维护，不影响 Skill 运行时行为、`.agent/` 结构和初始化行为，因此不单独发行新版本，随 `main` 提交即可。
- 依据：`.gitignore`、`git check-ignore -v .playwright-cli` 输出。
- 验证：`git check-ignore -v` 命中 `.gitignore:4`；`git status --short` 不再列出该目录；本地 59 个文件保持原样。
- 本地提交：本轮维护提交。
- 远端推送：随本轮提交推送 `origin/main`。

## v0.0.2 · 2026-09-09 · 用户入口文档同步与结构性修复

- 类型：release
- 变更：修正 `skills/project-lifecycle/SKILL.md`、`docs/reference/index.md`、`docs/architecture.md`、`docs/reference/commands.md` 中过时的用户命令清单，补全 `updates`、`record`、`checkpoint`、`push-check`；在 `references/workflow.md` 的“用户如何触发”表补上更新历史、记录更新、本地检查点和推送核验四类动作；QA 计数按实际标题改正为 33（`18.1`、`18.2`、`24.1` 为追问），并统一 `18.2` 的小节标题格式；把版本基线元数据从 `v0.0.1` 更新到 `v0.0.2`；按真实 Git 提交回填本文件早前仍写“待用户授权/未执行”的本地提交与远端推送字段。
- 决策：本轮只同步文档与元数据、不改脚本行为，因此按 `PATCH` 发布为 `v0.0.2`；`quick_validate.py` 保持为 Codex `skill-creator` 的外部工具并显式标注来源，不复制进仓库；`v0.0.1` 既已发布即不移动、不覆盖；本文件把未提交的维护记录并入发布条目，不保留指向尚未存在提交的悬空记录。
- 依据：`skills/project-lifecycle/scripts/project-lifecycle.ps1` 的 `ValidateSet`、`skills/project-lifecycle/references/workflow.md`、`docs/guide/qa.md`、`docs/reference/commands.md`、`README.md` 的版本与发布流程。
- 验证：44 个单元测试通过；Python 脚本编译通过；Skill 校验（`skill-creator/scripts/quick_validate.py`）通过；VitePress 构建通过；`git diff --check` 通过。tag 创建后以 `git ls-remote` 核对本次提交与 `v0.0.2` 均已到达 GitHub。
- 本地提交：发布提交 `2701c27`。
- 远端推送：已推送 `main` 和 `v0.0.2`，用 `git ls-remote` 核对 `refs/heads/main`、`refs/tags/v0.0.2` 和 `v0.0.2^{}` 均指向 `2701c27`。
- GitHub Release：[v0.0.2](https://github.com/xiaou61/project-lifecycle/releases/tag/v0.0.2)，`v0.0.1` 未移动。
- 部署：`remote-45`，新 release `/opt/project-lifecycle-docs/releases/20260910103002/dist`，`current` 已切换，`project-lifecycle-docs.service` 重启后为 active；`/`、`/guide/qa`、`/reference/commands`、`/reference/`、`/architecture` 均返回 200，5 个关键页面 SHA-256 与本地构建一致；上一个 release `20260909163928` 保留可回滚。

## 2026-09-09 · 文档预算、验证锚点与推送核验

- 类型：maintenance
- 变更：为状态恢复增加核心 Markdown 体积软警告；为验证报告增加 `verified_commit` 锚点状态；新增 `push-check` 与 `--record-push`，检测远端已推送但 `updates.md` 未记录的情况。
- 决策：文档超限只提示，不自动压缩或删除；远端查询只在显式 `push-check` 时执行；`updates.md` 仍是人工时间线，Git 远端仍是推送事实源。
- 依据：`skills/project-lifecycle/scripts/project_status.py`、`skills/project-lifecycle/scripts/update_history.py`、`skills/project-lifecycle/references/update-history.md`。
- 验证：44 个单元测试通过；Python 编译、Skill 校验、VitePress 构建和 `git diff --check` 通过；GitHub `origin/main` 已核对。
- 本地提交：实现提交 `2e2896b501f32b6c0818ad5f3eb98f49172f56ff`，发布记录提交 `a55ed6a872fab5bd049966378209ceb235fd09af`。
- 远端推送：实现、发布记录和元数据修订均已推送到 `origin/main` 并完成核对。
- 部署：`remote-45`，最新 release `/opt/project-lifecycle-docs/releases/20260909163928/dist`，服务 `project-lifecycle-docs.service` 已验证为 active。

## 2026-09-09 · 压缩后任务目标恢复包

- 类型：maintenance
- 变更：`resume --json` 从 `requirements.md` 提取 `goal`、`acceptance_criteria`、`constraints` 和 `goal_status`，文本恢复输出与接力提示同步带出；缺失目标或验收标准时返回明确警告。
- 决策：对话历史可以被压缩，当前任务状态继续以项目工件为唯一事实源；恢复包新增 `state_evidence`，明确工件状态、已记录测试、Git 快照和未知的源码同步，避免把过时 Markdown 当成实时代码状态；不新增数据库、向量存储或后台服务，长期 `.agent/memory.md` 不承担当前任务目标。
- 依据：`skills/project-lifecycle/scripts/project_status.py`、`skills/project-lifecycle/references/workflow.md`、`docs/guide/resume.md`。
- 验证：未单独留档；本轮实现随 `2e2896b` 一并回归。
- 本地提交：实现提交 `2e2896b`（与“文档预算、验证锚点与推送核验”同批）。
- 远端推送：随 `2e2896b` 推送到 `origin/main`。

## 2026-09-09 14:10:00 +0800 · 发布三档模式与秒级更新历史

- 类型：maintenance
- 变更：提交 `976cf4b` 已推送到 GitHub `main`；VitePress 构建产物已部署到 `remote-45`。
- 决策：服务器使用独立 release 目录 `/opt/project-lifecycle-docs/releases/20260909135408/dist`，`current` 指向该目录并保留旧 release 供回滚。
- 依据：GitHub `origin/main`、远端 `project-lifecycle-docs.service` 和本地构建产物。
- 验证：远端服务 `active`；首页和 `/guide/qa` 返回 200；远端与本地 `index.html`、`guide/qa.html` SHA-256 一致。
- 本地提交：`976cf4b`。
- 远端推送：已推送 `origin/main`。
- 部署：已部署到 `remote-45`，监听 `4175`，入口为 `http://45.207.197.87:4175/`。

## 2026-09-09 13:47:43 +0800 · 更新历史时间精度

- 类型：maintenance
- 变更：`updates --record` 生成的更新标题精确到秒并带本地时区；列表解析继续兼容旧的纯日期标题。
- 决策：采用人类可读的 `YYYY-MM-DD HH:mm:ss ±HHMM`，不改写已有历史，也不引入独立时间服务。
- 依据：`skills/project-lifecycle/scripts/update_history.py`、`skills/project-lifecycle/references/update-history.md`。
- 验证：38 个单元测试通过；Python 脚本编译通过；Skill 校验通过；VitePress 构建通过；`git diff --check` 通过。
- 本地提交：随后续实现提交 `976cf4b` 落地。
- 远端推送：随 `976cf4b` 推送到 `origin/main`。

## 2026-09-09 · 三档风险模式

- 类型：maintenance
- 变更：增加 `lite`、`managed`、`strict` 三档风险路由；旧 `workflow: compact/full` 工件继续兼容推导；普通 `validate` 不再自动升级为严格校验。
- 决策：模式在开始时判断，风险上升只允许升级；严格模式增加必要工件和批准门槛，但不机械增加测试；冒烟测试仍仅按用户、项目规则或已批准计划执行。
- 依据：`skills/project-lifecycle/SKILL.md`、`skills/project-lifecycle/references/workflow.md`、`skills/project-lifecycle/references/testing.md`。
- 验证：37 个单元测试通过；Python 脚本编译通过；Skill 校验通过；VitePress 构建通过；`git diff --check` 通过。
- 本地提交：实现提交 `976cf4b`。
- 远端推送：已推送到 `origin/main`。

## 2026-09-08 · 生命周期入口与更新记录

- 类型：maintenance
- 变更：修正状态/校验脚本的相对路径误用，统一通过 `project-lifecycle.ps1` 调用；初始化目标项目时增加 `.agent/history/updates.md`；补充每轮变更、决策、依据、验证和本地提交边界的规则与教程。
- 决策：`.agent/history/updates.md` 采用追加式人工可读时间线；Git 继续负责提交事实，`core-components.md` 继续负责确定性组件历史；本地 commit 是检查点，远端 push 必须用户明确授权。
- 依据：`skills/project-lifecycle/SKILL.md`、`skills/project-lifecycle/references/workflow.md`、`skills/project-lifecycle/references/update-history.md`。
- 验证：30 个单元测试通过；Skill 校验通过；Python 脚本编译通过；VitePress 构建通过。
- 本地提交：待用户授权。
- 远端推送：未执行。

## 2026-09-08 · 更新历史命令入口

- 类型：maintenance
- 变更：新增 `updates`、`record`、`checkpoint` 命令，分别用于查看更新历史、追加结构化记录和检查本地 Git 工作区；补充命令参考、README、总索引和回归测试。
- 决策：命令复用现有 `project-lifecycle.ps1`，只读检查和文本追加不自动提交；本地 commit 与远端 push 继续分离。
- 依据：`skills/project-lifecycle/references/update-history.md`、`skills/project-lifecycle/scripts/update_history.py`、`tests/test_project_status.py`。
- 验证：31 个单元测试通过；Skill 校验通过；Python 脚本编译通过；VitePress 构建通过。
- 本地提交：实现提交 `54ccabc`。
- 远端推送：已推送到 `origin/main`。

## 2026-09-09 · 并发边界与使用 QA

- 类型：maintenance
- 变更：补充多对话并发与 Git Worktree 隔离规则；在 VitePress 增加 30 问 QA 页面，并接入导航和总索引；同步 README 与恢复教程的并发说明。
- 决策：明确 Skill 负责跨会话事实恢复、多个工作项选择和 Git 改动归因，但不承诺同一工作树的文件锁或自动合并；并行写入采用“一项工作、一个分支、一个 Worktree、一个写入对话”。
- 依据：`skills/project-lifecycle/references/workflow.md`、`docs/guide/resume.md`、`docs/guide/qa.md`。
- 验证：`npm run docs:build` 通过；31 个单元测试通过；Python 脚本编译通过；Skill 校验通过；`git diff --check` 通过。
- 本地提交：待用户授权。
- 远端推送：未执行。
- 部署：已发布到 `remote-45` 的 `project-lifecycle-docs.service`；当前目录为 `/opt/project-lifecycle-docs/releases/20260909104500/dist`，公网 `/guide/qa` 返回 200，页面哈希已核对。

## 2026-09-09 · 冒烟测试默认边界

- 类型：maintenance
- 变更：在测试规范、README、QA 和总索引中明确普通用户任务不默认执行冒烟测试，并将维护命令的“冒烟检查”改为入口/行为检查。
- 决策：只执行验收矩阵中最窄可信验证；冒烟测试仅在用户、项目常驻规则或已批准测试计划明确要求时执行；部署健康检查仍属于部署验证。
- 依据：`skills/project-lifecycle/references/testing.md`、`docs/guide/qa.md`。
- 验证：`npm run docs:build` 通过；31 个单元测试通过；Python 脚本编译通过；Skill 校验通过；`git diff --check` 通过；公网 `/guide/qa` 返回 200 且包含默认不执行冒烟测试的说明。
- 本地提交：待用户授权。
- 远端推送：未执行。
- 部署：已发布到 `remote-45` 的 `project-lifecycle-docs.service`；当前目录为 `/opt/project-lifecycle-docs/releases/20260909105439/dist`，页面哈希已与本地构建核对。

## v0.0.1 · 2026-09-09 · 首个可发布版本

- 类型：release
- 变更：将当前生命周期 Skill、VitePress 用户教程、30 问 QA、更新历史命令、并发边界和可选冒烟测试规则作为首个可发布基线。
- 决策：版本以不可移动的 Git tag `v0.0.1` 标识；后续按兼容性使用 `v0.MINOR.PATCH`，通过 GitHub 的分支、提交、tag 和 Release 流程发布。
- 依据：`README.md` 的版本与发布流程、`docs/guide/qa.md`、`skills/project-lifecycle/SKILL.md`。
- 验证：随发布提交执行完整回归、Skill 校验、Python 编译、VitePress 构建和 GitHub 远端 ref 校验。
- 本地提交：本次发布提交。
- 远端推送：随本次发布推送 `main` 和 `v0.0.1`。
