# DeskToDo

贴在桌面最底层的悬浮日历 + 待办事项小工具（Windows / PyQt6）。日历常驻桌面背景之上、其他窗口之下，点开任务一目了然，配合天气、倒计时、进度条等小组件。

## 功能特性

- **桌面悬浮日历**：贴在桌面壁纸上方、普通窗口下方，背板黑色透明度可调，不挡壁纸也不抢焦点
- **任务管理**：单次、范围每天、范围内每周几、指定多日四种周期类型；今日任务高亮、农历/节假日信息显示在日期旁
- **节假日**：内置当年法定节假日数据，母亲节/父亲节等公式类节日自动计算，以后年份可自行导入新数据
- **小组件**：时钟、天气（4 天预报 + 折线图，城市名自动识别）、倒计时、进度条，均可在设置面板里启用/排序/配置
- **多显示器位置记忆**：按当前显示器组合自动记住悬浮窗位置、大小，换接口/换地方自动切换
- **多设备同步（可选）**：通过 GitHub Gist 同步任务数据，支持多台电脑共享同一份待办
- **开机自启动**：可在设置面板里一键开关
- **外观可调**：悬浮窗 / 设置界面背板透明度独立可调，设置界面背景图可自行替换

## 安装与运行

### 方式一：直接用安装包（推荐给普通使用者）

1. 下载 `DeskToDo-Setup-x.x.exe`，双击运行
2. 选择安装目录，勾选是否需要桌面快捷方式、开机自启动
3. 安装完成后自动启动，首次启动会弹出引导向导

### 方式二：从源码运行（开发/调试用）

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. 启动
python -m deskcal.main
```

> ⚠️ `requirements.txt` 里 PyQt6 锁定在 6.6.1：更新版本在部分 Windows 环境会导致 `Qt6Core.dll` 加载失败（`WinError 127`），详见 `docs/known-issues.md`。

## 配置说明

首次启动会弹出引导向导，可以填，也可以先跳过、之后在**右键托盘图标 → 设置**里随时补填：

| 配置项 | 在哪里填 | 怎么获取 |
| --- | --- | --- |
| GitHub Gist Token | 设置面板 → 数据同步 | GitHub → Settings → Developer settings → Personal access tokens，勾选 `gist` 权限。**改动后需要重启程序才会生效** |
| 天气城市定位 | 设置面板 → 桌面组件 → 天气 → 设置 | 填 `经度,纬度`（如 `120.68,30.51`），或和风天气 LocationID（在 qweather.com 搜索城市后，网址末尾的数字）。城市名称会自动识别显示，不需要手填 |
| 节假日数据 | 设置面板 → 节假日信息 | 当年数据已内置；以后年份需要自己去国务院发布的节假日安排里整理成 JSON 后导入，页面里有格式说明 |
| 开机自启动 | 设置面板 → UI 调整 | 勾选/取消即可，立即生效 |
| 设置界面背景图 | 设置面板 → UI 调整 | "上传背景图..." 按钮，选一张图片即可替换 |

数据存放位置：`%APPDATA%\DeskCal\`（任务数据、窗口位置记忆、Token 等，每台电脑独立，互不影响）。

## 打包成 exe（给开发者）

项目用 [PyInstaller](https://pyinstaller.org/) 打包、[Inno Setup](https://jrsoftware.org/isinfo.php) 做安装包，脚本都在仓库根目录：

```bash
# 1. 装打包工具（只在打包机器上需要，不算运行依赖）
pip install pyinstaller

# 2. 用 PyInstaller 打成单目录应用，产出 dist/DeskToDo/
python -m PyInstaller desktodo.spec --noconfirm

# 3. 用 Inno Setup 编译成一个安装包 exe，产出 installer_output/DeskToDo-Setup-x.x.exe
"C:\Users\<你>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

几点说明：

- `desktodo.spec` 里把 `deskcal/assets/`（图标、字体、节假日默认数据）和 `secrets/qweather/`（和风天气私钥）一起打进了包。私钥被打进 exe 意味着任何拿到这个 exe 的人理论上都能反编译出私钥、冒用你的和风天气项目额度——这个项目目前只打算给身边几个人用，所以接受这个风险；**如果以后要公开分发给不认识的人，私钥不能再这样直接打包，需要改成服务端代理转发天气请求**
- `installer.iss` 用的是非管理员权限安装（装到当前用户目录下），不需要 UAC 弹窗，对朋友更友好；安装时可选"创建桌面快捷方式"和"开机自动启动"
- 打包产物 `build/`、`dist/`、`installer_output/` 不需要提交到 git
- 改完代码记得先跑一遍测试再打包：`pytest coding_file_test`

## 开发

```bash
# 跑测试
python -m pytest coding_file_test -v
```

代码结构（`deskcal/` 下）：

- `core/`：数据模型、本地存储、Gist 同步逻辑
- `services/`：节假日、天气、开机自启动等后台服务
- `ui/desktop_overlay/`：悬浮日历主窗口、日历格子、小组件
- `ui/config_panel/`：设置面板各个 Tab
- `ui/dialogs/`：新建任务、日期选择等弹窗
- `ui/onboarding/`：首次启动引导向导
- `tray/`：系统托盘图标
- `utils/`：图标、显示器签名、凭证加密等工具函数

## 路线图

- V1：本地日历 + Gist 多 PC 同步（已完成）
- V2：飞书跨端协同（详见 `docs/v2-mobile-sync-plan.md`）
