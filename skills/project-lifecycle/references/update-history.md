# 项目更新历史与本地检查点

## 目的

`.agent/history/updates.md` 是面向人阅读的项目时间线，记录每轮实际变化和关键决定。它不是 Git 的替代品，也不复制完整任务状态：

- Git 负责提交身份、时间、作者、文件和可回滚事实；
- `.agent/changes/WORK-*/` 负责一次变更的需求、任务和验证证据；
- `.agent/notes/` 负责跨工作项仍有效的决策理由；
- `updates.md` 负责把本轮变更、决定、验证和提交边界串成可读历史。

## 何时追加

每次实际修改源码、测试、配置、Skill 规则、文档或项目工件后追加一条记录。只讨论、没有持久化变化的聊天不追加。一次工作项可以有多条记录，按时间顺序追加，不覆盖旧记录；发现记录错误时追加更正并引用原记录。

每条记录至少包含。新记录标题使用执行机器的本地时间，精确到秒并带 numeric 时区；历史中的旧日期格式继续兼容：

```markdown
## 2026-09-08 14:32:07 +0800 · WORK-003 · 修复登录超时

- 类型：implementation | decision | verification | maintenance
- 变更：具体增加、修改或删除了什么。
- 决策：采用了什么方案，放弃了什么方案，为什么。
- 依据：`requirements.md`、`design.md`、项目规则或外部资料的路径。
- 验证：实际运行的命令、结果和未验证项。
- 本地提交：`abc1234`，或“待用户授权/未提交：原因”。
- 远端推送：未执行；只有用户明确要求时才填写远端和结果。
```

低风险短路径没有 `WORK-*` 时，工作项填写 `maintenance`，仍然记录变更、决策和验证。

## 本地提交与远端边界

对应命令入口：

```powershell
& $lifecycle updates "F:\我的项目" --tail 10
& $lifecycle record "F:\我的项目" --work WORK-003 --title "修复登录超时" --type implementation `
  --change "调整会话超时处理" --decision "保留现有接口" --basis ".agent/changes/WORK-003-登录/design.md" `
  --verification "pytest tests/test_login.py -q：通过"
& $lifecycle checkpoint "F:\我的项目" --json
```

`updates` 和 `checkpoint` 默认只读；`record` 只追加文本，不创建 Git 提交或远端变更。`checkpoint` 返回非零表示工作区仍有未提交改动，便于脚本在切换工作项前阻断。

本地提交是可恢复的检查点，不等于发布：

1. 在切换到下一个独立工作项，或把当前工作项标记为完成沉淀前，先写完更新历史并确认当前 Git 改动已归因。
2. 用户明确要求“本地提交/保存这一轮”后，只暂存当前工作项归属的文件并创建本地 commit；提交信息应能定位 `WORK-*` 或维护事项。
3. 没有本地提交授权时，保留改动并在历史中写明“待用户授权”，不要假装已经保存为检查点。
4. `git push`、创建远端分支、打 tag 或发布都必须得到用户明确授权；“保存”“提交”“继续”不等于远端推送授权。

本地提交前后都不得覆盖或清理用户已有、未知归属或未授权的改动。凭据、密钥和令牌不得写入更新历史。

## 推送后核验

推送完成后，`updates.md` 可能没有被同一轮修改。不要把本地 `git log` 或旧的远端跟踪值当成远端事实，显式运行：

```powershell
& $lifecycle push-check "F:\我的项目" --json
```

该命令用 `git ls-remote` 查询当前分支的远端提交，并检查 `updates.md` 是否有对应的“远端推送”记录。远端已包含当前 HEAD 但历史缺记录时返回不一致且非零；确认结果后可追加一条本地核验记录：

```powershell
& $lifecycle push-check "F:\我的项目" --record-push --work WORK-003
```

`--record-push` 只追加本地文本，不会再次提交或推送。追加后 `updates.md` 会产生未提交改动，下一次要发布这条历史时仍需用户单独授权 commit/push。
