# 严谨清理

中文 Windows 桌面垃圾清理与已卸载软件残留检查工具。当前版本按商业软件架构实现，但仍坚持保守安全策略：先扫描和解释，再由用户确认；默认进入回收站，缺少 `send2trash` 时进入应用隔离区，不做静默永久删除。

## 主要功能

- 一键扫描用户临时文件、崩溃转储、浏览器缓存和常见软件缓存。
- 覆盖 360、2345、腾讯电脑管家、金山、百度、搜狗、压缩软件、资讯弹窗、游戏盒子等软件卸载后留下的残留文件规则。
- 检查疑似相关进程、服务、计划任务、启动项和注册表线索，但高风险项默认只展示不删除。
- 中文说明哪些可以清理、哪些需要谨慎、哪些禁止自动清理。
- 清理日志和隔离区位于 `%LOCALAPPDATA%\严谨清理`。

## 运行

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
python main.py
```

Windows 下启动会请求管理员权限，用于检查服务、计划任务和受限残留目录。

## 测试

```powershell
python -m unittest discover -v
python -m py_compile main.py cleaner_app\*.py tests\*.py
```

测试只使用仓库内模拟目录，不清理真实系统文件。

## 打包 exe

```powershell
python -m pip install PyInstaller Send2Trash
python -m PyInstaller --noconfirm --clean --windowed --uac-admin --name YanjinCleaner main.py
```

打包结果位于 `dist\YanjinCleaner\YanjinCleaner.exe`。该 exe 使用 `--uac-admin`，启动时会请求管理员权限。

## 安全边界

本工具不是杀毒软件，不承诺查杀病毒。它用于清理缓存、日志、临时文件和卸载残留，并辅助识别可能不再需要的软件组件。系统目录、用户文档、桌面、下载、图片、视频、服务、驱动、注册表和计划任务默认受到保护。

## 代码签名

发布到用户的 exe 文件建议使用 Windows Authenticode 代码签名证书签名。未签名的 exe 会被 Windows SmartScreen 拦截或提示"未知发布者"。

签名步骤（需先购买证书）：

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f cert.pfx /p PASSWORD dist\YanjinCleaner\YanjinCleaner.exe
```

国内常见的代码签名证书提供商有 CFCA、WoTrus（沃通）等。

## 开源许可证

本项目使用的第三方组件及其许可证：

| 组件 | 许可证 | 合规要点 |
|------|--------|----------|
| PySide6 | LGPLv3 | 必须以动态链接方式使用，或向用户提供替换 PySide6 的能力 |
| psutil | BSD-3-Clause | 保留版权声明即可 |
| send2trash | BSD-3-Clause | 保留版权声明即可 |

PySide6 基于 LGPLv3 许可证，PyInstaller 打包时默认以动态链接方式引用 Qt 库（DLL 位于发布目录中），符合 LGPL 要求。如果用户要求，应提供方法让其替换发布目录中的 PySide6 DLL 文件。

## 法律文件

- [用户协议](LICENSE_EULA.md)
- [隐私政策](PRIVACY_POLICY.md)
