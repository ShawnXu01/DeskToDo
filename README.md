# DeskToDo

面向 Windows 的桌面日历、待办与课表工具。

DeskToDo 常驻在桌面壁纸上方、普通窗口下方，把月历、日期任务、无日期待办、课程表和常用信息组件集中在一个可调整的桌面面板中。程序通过系统托盘运行，默认不抢占普通窗口；布局、外观和数据均保存在当前 Windows 用户目录下。

当前版本：**v1.4**

[下载最新版](https://github.com/ShawnXu01/DeskToDo/releases/latest) · [完整用户指南](USER_GUIDE.md) · [已知问题](docs/known-issues.md)

> DeskToDo 当前专为 Windows 开发和测试。项目使用 Windows DPAPI（Data Protection API，数据保护 API）保存 GitHub Token，并通过 Windows 注册表管理开机自启动。

## 功能概览

### 日历与待办

- 月视图日历，一周从星期一开始，支持切换月份和点击相邻月份日期跳转。
- 日期任务支持四种重复规则：单次、日期范围内每天、日期范围内指定星期、指定多个日期。
- 重复任务按日期分别记录完成状态，不会因完成某一次而影响其他日期。
- 独立的无日期待办，适合记录暂时没有截止日期的事项。
- 任务支持优先级、编辑、完成/恢复和删除。

### 课程表

- 按学期管理课程，支持新增、编辑、复制、归档和删除学期。
- 课程可记录课程编号、名称、星期、时间、地点、教师、颜色和备注。
- 支持无固定时间课程，以及工作日/全周、12/24 小时制切换。
- 紧凑课表嵌入桌面面板，也可打开完整周课表查看详情。
- 可配置课前 Windows 通知，提前时间范围为 1–180 分钟。
- 支持通过“课表截图 + 外部图像识别 AI”生成 CSV，预览后追加导入课程。

> “AI 图片导入”不会在 DeskToDo 内调用 AI 服务。程序只负责复制结构化提示词，并读取外部 AI 生成的 UTF-8 CSV 文件。

### 桌面组件

| 组件 | 功能 |
| --- | --- |
| 时钟 | 显示当前时间与日期 |
| 天气 | 和风天气实时天气、今天及未来 3 天预报、最高/最低温趋势 |
| 无日期待办 | 在桌面直接管理未排期事项 |
| 课表 | 显示当前学期的紧凑周课表 |
| 倒计时 | 同时展示多个目标日期的剩余时间 |
| 进度条 | 按起止日期展示多个事项的时间进度 |

所有组件均可在设置面板中启用或关闭；普通组件还可以调整顺序。

### 桌面体验与数据

- 悬浮面板背景透明度、设置面板透明度和设置背景图均可调整。
- 解锁后可移动、缩放窗口，并调整左侧宽度及课表区域高度。
- 按当前显示器组合分别记忆窗口位置和布局，适合笔记本与外接显示器切换。
- 内置 2026 年节假日数据，并显示常见公历节日、农历节日和按规则计算的节日；支持导入自定义年度 JSON。
- 可选 GitHub Gist 同步，在多台电脑间合并日期任务和无日期待办。
- 支持开机自启动、首次启动向导、主界面引导和托盘临时隐藏 15 秒。

## 安装

### 使用安装包

1. 前往 [Releases](https://github.com/ShawnXu01/DeskToDo/releases/latest) 下载 `DeskToDo-Setup-1.4.exe`。
2. 运行安装程序，选择安装目录，并按需创建桌面快捷方式或启用开机自启动。
3. 安装完成后启动 DeskToDo，按首次启动向导配置天气和可选的 Gist 同步。

安装程序以当前用户权限安装，无需管理员权限。覆盖安装新版本时，程序文件会被替换，但 `%APPDATA%\DeskCal\` 中的用户数据不会被安装程序覆盖。

> 重要数据建议在升级前手动备份。详见[本地数据与备份](#本地数据与备份)。

### 首次使用

DeskToDo 启动后会显示桌面面板，并在 Windows 通知区域保留托盘图标。右键托盘图标可以：

- 打开设置面板；
- 重新查看使用引导；
- 解锁或锁定桌面位置；
- 临时隐藏面板 15 秒；
- 完全退出程序。

调整布局时，先取消“锁定桌面位置”，拖动窗口、边缘或分隔线；完成后重新锁定，当前显示器组合下的布局会被保存。

更详细的任务、课表、天气、同步和备份操作见 [DeskToDo 用户指南](USER_GUIDE.md)。

## 可选配置

| 配置项 | 入口 | 说明 |
| --- | --- | --- |
| 天气位置 | 设置 → 桌面组件 → 天气 → 设置 | 填写 `经度,纬度`（英文逗号）或和风天气 LocationID；城市名会自动识别 |
| GitHub Gist Token | 设置 → 数据同步 | 用于同步任务；保存后需要完全退出并重启 DeskToDo |
| Gist ID | 设置 → 数据同步 | 高级选项；自动查找失败或需要指定某个 Gist 时再填写 |
| 课前提醒 | 设置 → 桌面组件 → 课表 → 设置 | 启用 Windows 通知并设置提前分钟数 |
| 节假日 JSON | 设置 → 节假日信息 | 导入会替换当前导入的数据，不是追加合并 |
| 开机自启动 | 设置 → UI 调整 | 切换后立即更新当前用户的启动项 |
| 设置背景图 | 设置 → UI 调整 | 选择本地图片作为设置面板背景 |

## GitHub Gist 同步

Gist 同步是可选功能。配置有效 Token 后，DeskToDo 默认每 5 分钟在后台同步一次，也可以在设置面板中手动触发。首次同步会查找当前账号下已有的 DeskToDo Gist；未找到时自动创建私密 Gist。

合并以每条任务的 `updated_at` 时间为准，较新的记录覆盖较旧记录；删除状态也会参与同步。

### 会同步

- 日期任务；
- 无日期待办。

### 不会同步

- 学期与课程表；
- 天气、倒计时、进度条和组件排列配置；
- 窗口位置、区域大小与界面外观；
- 自定义节假日数据；
- 其他本地设置。

Token 使用 Windows DPAPI 加密，且与当前 Windows 用户绑定。换电脑或换 Windows 用户后，需要重新输入 Token。Token 相当于 Gist 的访问凭证，请勿分享、截图或提交到仓库。

## 本地数据与备份

所有用户数据默认保存在：

```text
%APPDATA%\DeskCal\
```

常见文件如下：

| 文件 | 内容 |
| --- | --- |
| `tasks.json` | 日期任务、无日期待办及同步删除记录 |
| `schedule.json` | 学期和课程 |
| `widgets.json` | 组件状态、顺序及各组件配置 |
| `window_state.json` | 不同显示器组合下的窗口位置和布局 |
| `appearance.json` | 透明度、设置背景图、开机自启动和引导状态 |
| `holidays.json` | 导入或内置的年度节假日数据 |
| `credentials.json` | 首次启动状态、加密后的 Gist Token 和 Gist ID |
| `schedule_reminder_state.json` | 当天已经发送过的课程提醒记录 |

完整备份时，请先从托盘退出 DeskToDo，再复制整个 `%APPDATA%\DeskCal\` 文件夹。由于 DPAPI 与 Windows 用户绑定，复制到另一台电脑后仍应重新填写 GitHub Token。

## 从源码运行

### 环境要求

- Windows；
- Python 3；
- 项目依赖见 [`requirements.txt`](requirements.txt)。

PyQt6 固定为 `6.6.1`。项目曾在部分 Windows 环境中遇到新版 Qt 的 `Qt6Core.dll` 加载失败（`WinError 127`），原因与处理记录见 [`docs/known-issues.md`](docs/known-issues.md)。

### 安装与启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m deskcal.main
```

仓库不会提交 `secrets/`。因此，从源码运行时，除天气外的功能可以正常使用；如需天气功能，需要准备自己的和风天气项目凭证：

1. 运行 `python scripts/gen_qweather_keypair.py` 生成 Ed25519 密钥对；
2. 将公钥上传到和风天气控制台；
3. 在 `deskcal/services/weather_service.py` 中填写自己的 `PROJECT_ID` 和 `KID`；
4. 将私钥保留在 `secrets/qweather/ed25519-private.pem`，不要提交到 Git。

## 测试

```powershell
python -m pytest tests -q
```

当前测试覆盖任务模型与存储、同步合并、凭证加密、节假日、组件配置、课表模型与导入、课程提醒、主界面引导等核心逻辑。

## 打包发布

项目使用 [PyInstaller](https://pyinstaller.org/) 生成单目录应用，再使用 [Inno Setup](https://jrsoftware.org/isinfo.php) 生成 Windows 安装包。

```powershell
python -m pip install pyinstaller
python -m PyInstaller desktodo.spec --noconfirm
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

构建产物：

- `dist/DeskToDo/`：PyInstaller 单目录应用；
- `installer_output/DeskToDo-Setup-1.4.exe`：Inno Setup 安装包。

> `desktodo.spec` 会把 `secrets/qweather/` 一并打包。私钥进入客户端后，理论上可以被提取并滥用天气服务额度。当前项目接受这一分发模型；若面向不受信任的公众大规模发布，应改为服务端代理，不能继续把私钥放入客户端。

## 项目结构

```text
DeskToDo/
├─ deskcal/
│  ├─ core/                 # 任务、课表、存储、导入与同步合并逻辑
│  ├─ services/             # 天气、节假日、同步、课表提醒与自启动
│  ├─ tray/                 # Windows 系统托盘
│  ├─ ui/
│  │  ├─ config_panel/      # 设置面板
│  │  ├─ desktop_overlay/   # 桌面悬浮面板、日历、待办与组件
│  │  ├─ dialogs/           # 任务与日期弹窗
│  │  ├─ onboarding/        # 首次启动向导与主界面引导
│  │  └─ schedule/          # 课表组件、完整课表、设置与 CSV 导入
│  ├─ utils/                # 图标、显示器识别与 Windows DPAPI
│  └─ main.py               # 程序入口
├─ tests/                   # 自动化测试
├─ test_data/               # 课表导入测试数据
├─ docs/                    # 设计记录、已知问题与后续规划
├─ scripts/                 # 辅助脚本
├─ desktodo.spec            # PyInstaller 配置
└─ installer.iss            # Inno Setup 配置
```

## 当前边界与路线图

- v1.4 仅面向 Windows 桌面端。
- Gist 当前只同步任务，不同步课表或界面配置。
- 默认只内置 2026 年需要按年份维护的节假日数据；其他年份可导入 JSON。
- V2 的跨端协同仍处于方案规划阶段，尚未实现，详见 [`docs/v2-mobile-sync-plan.md`](docs/v2-mobile-sync-plan.md)。

## 许可证

本项目采用 [MIT License](LICENSE)。
