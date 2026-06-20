# 已知问题（已解决的记录）

## PyQt6 6.11 在当前开发机上无法导入 —— 已解决，根因是版本兼容性问题

- **现象**：`from PyQt6.QtWidgets import QApplication` 报 `ImportError: DLL load failed while importing QtCore/QtWidgets: 找不到指定的程序`（WinError 127）
- **排查过程中排除的原因**：虚拟环境隔离、Anaconda PATH 污染、Git Bash/MSYS 环境、文件损坏或被 Windows 标记拦截、Qt6Core.dll 静态依赖缺失导出（递归4层检查28个DLL均无缺失）、系统文件损坏（`sfc`/`DISM` 修复后问题依旧）
- **真正根因**：**PyQt6 6.11.0（配 Qt6 6.11.1）与这台机器的 Windows 版本不兼容**。验证依据：Pillow、numpy 等同样依赖复杂 DLL 的库都能正常加载（排除系统性 DLL 故障），换成 PySide6 报错完全相同（排除 PyQt6 包本身的问题），最终把 PyQt6 降级到 **6.6.1**（配 `PyQt6-Qt6==6.6.1`、`PyQt6-sip==13.6.0`）后导入成功
- **解决方案**：项目固定使用 `PyQt6==6.6.1`（不要用最新版），已在虚拟环境 `.venv` 里验证整个程序可以正常启动（引导向导/主界面/托盘/配置面板均正常弹出）
- **记录时间**：问题发现于 2026-06-18（Phase 2 开发期间），解决于 2026-06-18
