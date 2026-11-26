# gitdash

一个零依赖的终端 Git 仓库状态面板。所有操作均在本地执行，不访问网络，也不会修改仓库内容。

A zero-dependency terminal dashboard for Git repository status. It runs local Git commands only and never modifies your repository.

## 功能

- 显示当前分支、上游分支以及 ahead / behind 数量
- 统计已暂存、已修改、未跟踪和冲突文件
- 显示 stash 数量与最近提交
- 支持 detached HEAD、空仓库、仓库子目录和 bare 仓库错误提示
- 支持定时刷新、JSON 输出与 `NO_COLOR`
- 支持 Python 3.9+，安装后无需第三方运行时依赖

## 安装

需要先安装 [Git](https://git-scm.com/) 并确保 `git` 在 `PATH` 中。

从源码安装：

```bash
python -m pip install .
gitdash
```

也可以直接运行模块：

```bash
PYTHONPATH=src python -m gitdash
```

## 使用

```bash
gitdash
gitdash /path/to/repository
gitdash --watch 2
gitdash --limit 10 --no-color
gitdash --json . > status.json
```

输出示例：

```text
gitdash | /home/user/project
Branch: main -> origin/main (ahead 0, behind 0)
State: DIRTY | 1 staged, 2 modified, 3 untracked, 0 conflicted
Stashes: 1
Recent commits:
  a1b2c3d4  2 hours ago  Improve status rendering
  5e6f7a8b  1 day ago  Initial commit
```

`--watch` 默认间隔为 0.5 秒起，可按秒传入小数；在终端中会清屏刷新，按 `Ctrl+C` 退出。颜色在非 TTY 输出时自动关闭，也可使用 `--no-color` 或设置 `NO_COLOR`。

## JSON

JSON 模式输出路径、仓库根目录、分支、上游、ahead / behind、四类文件计数、stash 数量和最近提交列表。空分支的 `branch` 为分支名但提交列表为空；detached HEAD 的 `branch` 为 `null`，`detached` 为 `true`。

## 退出码

- `0`：成功渲染状态
- `2`：参数、路径或 Git 命令错误
- `130`：监视模式被 `Ctrl+C` 中断

仓库存在未提交改动不会导致非零退出码，便于交互式使用和脚本采集。

## 开发

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build twine
python -m build
python -m twine check dist/*
```

测试使用临时 Git 仓库，覆盖干净仓库、暂存/修改/未跟踪文件、合并冲突、detached HEAD、stash、空仓库、子目录、bare 仓库与 CLI 错误路径，不需要网络。

## 许可证

[MIT](LICENSE)
