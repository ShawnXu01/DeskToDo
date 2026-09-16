# DeskToDo 双平台发布检查清单

每次用户要求“打包”或发布新版本时，Windows 与 macOS 两条开发线必须一起推进，不能只更新其中一个分支。

## 发布前

- [ ] 明确新版本号，并检查代码、关于页、安装脚本、README 和产物名称中的旧版本号。
- [ ] 更新 README：当前版本、功能说明、下载文件名、构建产物和平台状态。
- [ ] 运行完整自动化测试，并检查 `git diff --check`、未跟踪文件和构建警告。
- [ ] 检查 Windows 与 `codex/macos-port` 的差异；除明确的平台适配外，两边应包含相同的产品功能。

## 构建与验证

- [ ] Windows：使用 `desktodo.spec` 构建 `dist/DeskToDo/`。
- [ ] Windows：使用 `installer.iss` 导出对应版本的安装包并核对版本元数据、文件大小和 SHA-256。
- [ ] macOS：同步同版本功能、数据模型、设置和文档。
- [ ] macOS：必须在 macOS 实机或 macOS CI 上构建并验证 `.app`/`.dmg`；不得在 Windows 上声称已完成 macOS 二进制验证。
- [ ] 对两个平台分别进行启动、数据兼容和关键功能检查。

## 发布

- [ ] 提交 Windows 主分支的版本更新与安装包相关配置。
- [ ] 将同版本产品改动同步到 `codex/macos-port`，保留并验证平台专属代码。
- [ ] 推送两个分支，并核对远程分支提交与本地提交一致。
- [ ] 最终报告两个平台的版本、测试结果、产物位置、尚未完成的实机验证和任何已知限制。

## v1.8 执行记录（2026-09-16）

- [x] 代码、关于页、安装脚本、README、用户指南和产物名称统一为 v1.8。
- [x] Windows `master` 与 `codex/macos-port` 均通过 108 项自动化测试和 `git diff --check`。
- [x] 使用 `desktodo.spec` 重新生成 `dist/DeskToDo/`，并成功启动打包后的程序。
- [x] 使用 `installer.iss` 生成 `installer_output/DeskToDo-Setup-1.8.exe`；版本元数据为 1.8，大小为 36,962,223 字节。
- [x] Windows 安装包 SHA-256：`8857EEF74B8CBDD62F84F25D595E9D8DE678DBB54D8AB01B47AE85145AF5E3FB`。
- [x] v1.8 日历模式、设置、数据配置、测试和文档已同步到 `codex/macos-port`，并保留 macOS 原生窗口探针。
- [ ] macOS `.app`/`.dmg` 构建及桌面层级实机验证：需要在 macOS 实机或 macOS CI 上完成，Windows 无法验证。
- [x] `master`、`codex/macos-port`、`v1.8` 标签和 Windows 安装包发布到 GitHub。
