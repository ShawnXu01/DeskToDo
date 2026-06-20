# 实现计划（按模块分阶段）

> 每个阶段完成后都应该是可运行/可验证的状态，不是写到一半才能测。

## Phase 0：项目基础设施（已完成）

- 目录骨架、`.gitignore`、`README.md`、`docs/v2-mobile-sync-plan.md`、和风天气密钥

## Phase 1：核心数据层

**文件**：`deskcal/core/models.py`、`deskcal/core/storage.py`

**功能**：
- 任务数据模型：`dated`（日历任务，含 4 种周期规则）/ `floating`（无日期任务）两类
- 每个任务 UUID + 修改时间戳
- 周期任务按日期记录完成状态（`completed_dates` 集合），不是全局布尔值
- 软删除墓碑（标记删除时间，而非物理移除）
- 本地 JSON 读写，原子写入（写临时文件再 rename），避免异常退出导致文件损坏

## Phase 2：日历主体 + 任务弹窗（单机可跑）

**文件**：
- `deskcal/main.py`（入口，先只启动这一个窗口）
- `deskcal/ui/desktop_overlay/overlay_window.py`、`calendar_grid.py`、`sidebar_todo.py`
- `deskcal/ui/dialogs/task_dialog.py`、`mini_calendar_picker.py`
- `deskcal/services/lunar_holiday.py`

**功能**：
- 7×6 月历网格渲染，非本月灰化，今天日期数字标红+小角标
- 任务条按优先级排序，已完成沉底+打勾+轻微变淡
- 格子内任务溢出时悬停滚轮局部滚动，日期数字不动
- 右键空白建任务 / 右键或双击任务编辑，4 级优先级颜色
- 周期类型选择（单次/范围每天/每周几/指定多日），"指定多日"联动迷你日历多选弹窗，与其余类型互斥
- 待办收纳侧栏：待办/完成筛选 tab，勾选即时筛选切换，不删除
- 接入 Phase 1 的本地存储，此阶段**无网络同步**，纯单机可用

## Phase 3：窗口行为 + 系统托盘

**文件**：
- `deskcal/tray/tray_icon.py`
- 修改 `overlay_window.py`（拖动/缩放/锁定状态/临时隐藏）
- `deskcal/services/autostart.py`

**功能**：
- 贴底层（`HWND_BOTTOM`）、无边框、半透明黑底白字
- 解锁状态：仅能拖动（仅组件区/待办区空白处触发）+ 拖拽边缘缩放，整窗灰度模糊+文案提示"调整模式"；日历区右键/滚轮等功能此状态下不响应
- 锁定状态：恢复全部交互功能，禁止拖动/缩放，窗口最小宽高有下限（按"日历格子最少能显示日期+一条任务"反推）
- 托盘菜单：打开设置面板 / ☐ 锁定桌面位置 / 临时隐藏15秒 / 退出
- 写入注册表实现开机自启

## Phase 4：Widget Registry + 桌面组件 + 配置面板

**文件**：
- `deskcal/ui/desktop_overlay/widgets/registry.py`、`clock_widget.py`、`countdown_widget.py`、`weather_widget.py`、`progress_widget.py`
- `deskcal/ui/config_panel/config_window.py`
- `deskcal/services/weather_service.py`

**功能**：
- 组件注册表：单例型组件（时钟/天气，固定高度）与多实例型组件（倒计时/进度条，按条目数累加高度）
- 组件区内容超出窗口高度时滚轮滚动，不强行压缩
- 配置面板（同程序第二窗口，有边框）：桌面组件 tab（增删/拖拽排序/单个组件设置）、数据同步 tab（占位，Phase 6 填）、关于 tab
- 天气服务：内置 JWT 凭证签名调用和风天气，用户只需选城市，30分钟刷新一次

## Phase 5：首次引导向导 + 凭证存储

**文件**：
- `deskcal/ui/onboarding/wizard.py`
- `deskcal/utils/crypto.py`

**功能**：
- 检测无本地配置时弹出有边框引导向导，收集用户自己的 GitHub Gist Token + 天气城市
- Token 本地加密存储（Windows DPAPI），不留明文
- 配置完成销毁向导，进入静默模式

## Phase 6：Gist 云同步

**文件**：
- `deskcal/core/sync/__init__.py`（`SyncProvider` 抽象接口，为 V2 飞书预留）
- `deskcal/core/sync/gist_provider.py`
- 修改 `storage.py`（dirty 标记）、`config_window.py`（数据同步 tab 真正逻辑）、`main.py`（挂载 QThread 轮询）

**功能**：
- 后台 QThread 定时轮询 Gist 拉取/推送变更，断网/超时静默重试+写本地日志，不弹错误框
- "立即同步"按钮，带进行中标志位防止并发重复同步
- 时间戳覆盖冲突策略，墓碑超过90天自动清理
- 节假日数据更新按钮（用户主动触发，可以有失败提示，与后台静默同步原则不冲突）

## Phase 7：打包与发布

**文件**：
- PyInstaller 配置（`.spec`，不入库）
- `.github/workflows/build-release.yml`
- 完善 `README.md`

**功能**：
- `--noconsole` 单文件打包
- GitHub Actions：打 tag 后自动构建并把 `.exe` 挂到 Release，用户直接在 Releases 页面下载，不需要看源码
