# macOS 桌面窗口探针

该探针只验证 macOS 原生桌面窗口行为，不读取或修改 DeskToDo 用户数据，也不会启用开机启动。

## 运行环境

- Apple Silicon（arm64）Mac；
- macOS 26.3.1；
- Python 3.10 或更高版本，建议使用 Python 3.12。

先在终端确认：

```bash
uname -m
sw_vers -productVersion
python3 --version
```

其中 `uname -m` 应输出 `arm64`。如果没有合适的 Python，请先从 Python 官方安装包或 Homebrew 安装 Python 3.12。

## 获取代码

首次在 Mac 上操作：

```bash
mkdir -p ~/Developer
cd ~/Developer
git clone --branch codex/macos-port https://github.com/ShawnXu01/DeskToDo.git DeskToDo-macos-port
cd DeskToDo-macos-port
```

如果已经克隆过该分支：

```bash
cd ~/Developer/DeskToDo-macos-port
git pull --ff-only
```

## 安装探针依赖

```bash
cd ~/Developer/DeskToDo-macos-port
python3 -m venv .venv-macos
source .venv-macos/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-macos-probe.txt
```

## 启动

```bash
python scripts/macos_desktop_probe.py
```

程序启动后会同时显示一个半透明测试面板和一个菜单栏图标。如果面板消失，可以通过菜单栏图标选择“显示并重新应用窗口行为”。

## 测试顺序

先保持默认的“桌面图标下方一级（推荐）”，依次验证：

1. 打开 Finder 或浏览器，确认普通窗口位于探针上方；
2. 使用 macOS“显示桌面”，确认探针仍然保留；
3. 打开一个全屏应用，确认探针不出现在全屏空间；
4. 新建第二个桌面空间，确认勾选“在所有桌面空间显示”时两个空间都能看到；
5. 取消该选项，确认探针只保留在当前空间；
6. 未锁定时把探针拖到另一块显示器；
7. 勾选“锁定位置”，确认无法继续拖动，但按钮和选项仍可操作；
8. 点击“隐藏 5 秒”，确认 5 秒后恢复并保持原生层级。

如果默认层级出现以下问题，再切换到“桌面层上方一级（备用）”重复测试：

- 探针完全不可见；
- 显示桌面时消失；
- 探针被桌面壁纸遮挡；
- 探针无法接收鼠标操作。

“普通窗口下方一级（诊断）”只用于比较，不作为最终方案。

## 需要反馈的结果

点击“复制诊断信息”，把 JSON 和下表结果一起发回：

| 测试项 | 推荐层级 | 备用层级 | 备注 |
| --- | --- | --- | --- |
| 普通窗口覆盖探针 | 通过/失败 | 通过/失败 | |
| 显示桌面时保留 | 通过/失败 | 通过/失败 | |
| 全屏应用中隐藏 | 通过/失败 | 通过/失败 | |
| 所有 Spaces 开关 | 通过/失败 | 通过/失败 | |
| 菜单栏恢复窗口 | 通过/失败 | 通过/失败 | |
| 未锁定时跨屏拖动 | 通过/失败 | 通过/失败 | |
| 锁定后仍可操作按钮 | 通过/失败 | 通过/失败 | |

如果启动时终端出现 traceback，请复制完整错误输出，不要自行猜测或更换依赖版本。
