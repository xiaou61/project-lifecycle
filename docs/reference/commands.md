# 命令参考

## 初始化

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\init_project.py" "F:\我的项目"
```

初始化器是幂等的：已有 `AGENTS.md`、`.agent/`、源码、测试和 Git 历史会被保留。

## 状态查询

```powershell
# 当前活动工作项
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目"

# 按编号或中文名称查询
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --work WORK-003
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --work "用户登录"

# 恢复上下文
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --resume
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --resume --json

# 检查结构、重复标识符、来源引用、测试证据和 Git 归因
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_validate.py" "F:\我的项目" --strict --json

# 包含归档资料
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --include-archive
```

## 发布前检查

在 Skill 仓库中运行：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -m py_compile skills/project-lifecycle/scripts/init_project.py
python -m py_compile skills/project-lifecycle/scripts/project_status.py
python -m py_compile skills/project-lifecycle/scripts/project_validate.py
python -m py_compile skills/project-lifecycle/scripts/generate_core_history.py
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" "skills/project-lifecycle"
git diff --check
```

## 教程站本地运行

```powershell
npm install
npm run docs:dev
```

生产构建和预览：

```powershell
npm run docs:build
npm run docs:preview
```

## 稳定 JSON

状态和严格校验 JSON 都带 `schema_version` 与 `generated_at`。集成脚本应按 `resume.mode`、`git.status`、`source_coverage.status`、`test_evidence.status` 和 `errors`/`warnings` 字段处理，不要解析文本输出。
