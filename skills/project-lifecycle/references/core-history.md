# 核心组件变更历史

项目需要为重要类或组件保留可读时间线时，用本模式。

## 事实源

Git 负责提交标识、作者、时间戳、提交信息、重命名和变更路径。生成的 Markdown 是这段历史的确定性投影。永远不要手改生成报告，也不要把它当作 `git log` 的替代品。

生成器无法可靠地从提交文本推断架构重要性，也无法推断与语言无关的类边界。因此要在一个小的项目配置里显式声明被跟踪的单元：

```json
{
  "units": [
    {
      "id": "user-service",
      "name": "UserService",
      "paths": ["src/services/user-service.ts"]
    }
  ]
}
```

用稳定的 `id`。`paths` 是仓库相对路径，可以包含多个文件。重命名后写当前路径，并在旧路径的历史应继续属于同一单元时保留旧路径。单元以文件为界：一个文件里有多个类且需要分别记录历史时，声明分开的路径，或在生成报告旁保留手工的符号笔记。不要声称 Git 路径历史给不了的符号级精度。

推荐位置：

```text
.agent/core-components.json
.agent/history/core-components.md
```

需要针对单个工作项的历史时，把同一对文件放在该变更的工件根目录下。

## 生成的条目

每个单元条目应展示：

- 配置的单元名称与跟踪路径；
- 提交日期与作者；
- 缩写提交哈希；
- 提交主题；
- Git 报告的变更路径。

这回答了"何时、由谁、在哪些路径上改动了该单元"。报告不会编造原因或影响说明。决策是跨功能且长期有效时，把原因写进提交正文、已批准的设计或一篇 Agent Note。

## 更新方式

常规命令：

```sh
$lifecycle history \
  --config .agent/core-components.json \
  --output .agent/history/core-components.md
```

`$lifecycle` 指向已安装 Skill 的命令适配器（Windows 的 `project-lifecycle.ps1`，macOS/Linux 的 `project-lifecycle.sh`）；不要要求用户直接调用 Python 文件。项目若配置了自动化 hook，hook 可以继续使用内部脚本，但必须由项目维护者显式配置。

用于 CI 或评审检查时加 `--check`；报告缺失或与当前 Git 历史不一致时返回非零。输出是确定性的，不含生成时间戳。

项目希望每次提交后都更新时，装一个显式的 `post-commit` hook 来运行该命令。按仓库实际情况调整路径；hook 属于项目策略，不是本 Skill 的隐藏副作用：

```sh
#!/bin/sh
python .agent/scripts/generate_core_history.py \
  --config .agent/core-components.json \
  --output .agent/history/core-components.md
```

hook 可以更新工作区里的受跟踪报告，但不得自动创建第二次提交。这样避免递归提交、不隐藏生成的差异，并让用户决定这个投影是否进入下一次提交。仓库级 hook 管理器可以单独管理这个 hook 的版本。

不要在 hook 里调用模型或外部服务来总结提交。那会让历史不确定，还可能暴露源码或凭据。需要人类可读的解释时，在生命周期流程中索取，并存进相关的提案、设计或笔记。

## 漂移与重命名

重新生成，不要追加。改写历史、压缩、amend 和 revert 都可能让追加式 Markdown 日志失效。脚本使用 Git 路径历史，在 Git 支持的范围内跟进重命名，并在单元跟踪多个路径时对提交去重。重命名之后、下一次生成之前更新 `paths`，好让重命名后的提交被纳入；类的身份发生改变时在 Agent Note 里记录该次重命名或拆分，不要悄悄合并无关的历史。
