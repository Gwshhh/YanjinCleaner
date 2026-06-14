# 严谨清理 (YanjinCleaner)

[![版本](https://img.shields.io/badge/版本-1.0.2-blue.svg)](https://github.com/Gwshhh/YanjinCleaner/releases)
[![许可证](https://img.shields.io/badge/许可证-专有软件-red.svg)](LICENSE_EULA.md)
[![平台](https://img.shields.io/badge/平台-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

一款专为 Windows 系统设计的智能系统清理工具，旨在帮助用户安全地清理系统垃圾文件、浏览器缓存、已卸载软件残留，并检查可疑的系统组件。

**⚠️ 重要声明**：本软件**仅供个人学习研究使用**，不得用于任何商业用途。使用者应遵守当地法律法规，开发者不对使用本软件产生的任何后果承担责任。

---

## 📋 目录

- [核心功能](#核心功能)
- [系统要求](#系统要求)
- [安装与使用](#安装与使用)
- [功能详解](#功能详解)
- [安全机制](#安全机制)
- [常见问题](#常见问题)
- [开发与贡献](#开发与贡献)
- [法律文件](#法律文件)
- [技术架构](#技术架构)
- [许可证信息](#许可证信息)

---

## 🎯 核心功能

### 1. 系统垃圾清理
- **临时文件扫描**：检测并清理 Windows 临时目录（`%TEMP%`、`C:\Windows\Temp`）中的过期文件
- **系统日志清理**：扫描系统崩溃转储文件（`*.dmp`）、Windows 更新日志等
- **用户缓存清理**：清理用户配置文件中的临时数据和缓存

### 2. 浏览器数据清理
支持清理以下浏览器的缓存、Cookies 和临时文件：
- **Microsoft Edge**（Chromium 版本）
- **Google Chrome**
- **Mozilla Firefox**
- **360 安全浏览器** / **360 极速浏览器**
- **QQ 浏览器**
- **搜狗浏览器**
- **2345 浏览器**

### 3. 已卸载软件残留检测
智能检测以下已卸载软件的残留文件和注册表项：
- **安全软件**：360 安全卫士、360 杀毒、腾讯电脑管家、金山毒霸、百度杀毒
- **浏览器软件**：2345 浏览器、360 浏览器、搜狗浏览器
- **工具软件**：WinRAR、7-Zip、迅雷、快压、好压
- **弹窗软件**：2345 看图王、2345 好压、今日头条、快手、抖音等资讯类弹窗
- **游戏平台**：腾讯游戏平台（WeGame）、Steam、Epic Games 等

### 4. 系统组件检查（仅展示，不自动清理）
- **进程监控**：检测当前运行的可疑进程
- **服务检查**：列出可能与已卸载软件相关的系统服务
- **启动项检查**：扫描注册表和启动文件夹中的自启动项
- **计划任务检查**：检测 Windows 计划任务中的可疑项
- **注册表残留**：识别注册表中的软件卸载残留项

> **⚠️ 安全提示**：高风险项目（如服务、注册表、计划任务）仅供用户参考，系统**不会**自动清理这些项目，以防止系统损坏。

---

## 💻 系统要求

- **操作系统**：Windows 10 / Windows 11（64位）
- **运行权限**：需要管理员权限（用于检查系统服务、计划任务和受保护目录）
- **磁盘空间**：至少 200 MB 可用空间（用于存储日志、隔离区和备份文件）
- **.NET Framework**：Windows 10/11 自带，无需额外安装

---

## 📦 安装与使用

### 方式一：直接运行（推荐）

1. 从 [Releases](https://github.com/Gwshhh/YanjinCleaner/releases) 页面下载最新版本的 `YanjinCleaner.exe`
2. 右键点击 `YanjinCleaner.exe`，选择"以管理员身份运行"
3. 首次运行时，Windows 可能会弹出 SmartScreen 警告，请点击"更多信息" → "仍要运行"

> **注意**：由于本软件未进行商业代码签名认证，Windows Defender SmartScreen 可能会显示"未识别的应用"警告。这是正常现象，不代表软件包含病毒。

### 方式二：从源码运行（开发者）

```powershell
# 1. 克隆仓库
git clone https://github.com/Gwshhh/YanjinCleaner.git
cd YanjinCleaner

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行软件
python main.py
```

---

## 🔍 功能详解

### 扫描流程

1. **启动软件**：软件会请求管理员权限，用于检查系统服务和受保护目录
2. **选择扫描类型**：
   - **快速扫描**（推荐）：仅扫描临时文件、浏览器缓存和常见软件残留
   - **完整扫描**：包含系统日志、崩溃转储、所有已卸载软件残留和系统组件检查
3. **查看扫描结果**：扫描完成后，软件会按风险等级分类显示所有检测到的项目
4. **选择清理项目**：
   - **低风险**（绿色）：可以安全清理，如临时文件、浏览器缓存
   - **中风险**（黄色）：建议用户确认后清理，如某些软件残留
   - **高风险**（红色）：需要谨慎处理，可能影响系统稳定性
   - **禁止清理**（灰色）：系统关键组件，禁止自动清理

### 清理策略

本软件采用**三级安全清理策略**：

1. **首选方式**：移动到 Windows 回收站（可恢复）
2. **备选方式**：移动到应用隔离区 `%LOCALAPPDATA%\严谨清理\quarantine\`（可手动恢复）
3. **禁止方式**：**不执行永久删除**，高风险项目仅展示不清理

### 更新机制

软件内置自动更新功能：
- 启动时自动检查 GitHub Releases 是否有新版本
- 检测到新版本后，会弹出更新通知（可在设置中关闭）
- 用户确认后，自动下载并安装更新（旧版本会备份到 `%LOCALAPPDATA%\严谨清理\backups\`）

---

## 🛡️ 安全机制

### 1. 白名单保护
以下目录和文件**永久受保护**，不会被扫描或清理：
- **系统关键目录**：`C:\Windows\System32`、`C:\Windows\SysWOW64`
- **用户个人文件**：桌面、文档、下载、图片、视频、音乐
- **程序安装目录**：`C:\Program Files`、`C:\Program Files (x86)`（仅扫描卸载残留，不清理正在使用的软件）
- **驱动程序**：`.sys`、`.dll`、`.exe`（系统目录下的文件）

### 2. 权限控制
- 需要管理员权限才能检查系统服务和计划任务
- 不修改系统注册表（仅读取和展示）
- 不终止正在运行的进程（仅列出可疑进程供用户参考）

### 3. 数据备份
- 清理前自动备份到隔离区或回收站
- 支持从隔离区恢复误删文件
- 软件更新前自动备份旧版本

### 4. 日志记录
所有清理操作都会记录到本地日志文件：
- **日志位置**：`%LOCALAPPDATA%\严谨清理\logs\`
- **日志内容**：清理时间、清理项目、文件路径、清理结果

---

## ❓ 常见问题

### Q1: 为什么软件需要管理员权限？
**A**: 软件需要读取以下受保护的系统信息：
- Windows 系统服务列表
- 计划任务列表
- 注册表中的软件卸载信息
- 某些系统目录下的残留文件

如果不授予管理员权限，软件将无法扫描这些项目。

### Q2: Windows Defender / SmartScreen 提示"不受信任的应用"怎么办？
**A**: 这是因为本软件未购买商业代码签名证书（费用较高）。您可以：
1. 点击"更多信息" → "仍要运行"
2. 或者从源代码自行编译运行（见上文"从源码运行"）

### Q3: 清理后系统出现问题怎么办？
**A**: 
1. 首先尝试从 Windows 回收站恢复被清理的文件
2. 如果回收站已清空，可以从软件的隔离区恢复：
   - 打开软件，点击"设置" → "管理隔离区"
   - 选择需要恢复的文件，点击"恢复"
3. 如果仍无法解决，请使用 Windows 系统还原功能

### Q4: 软件会不会泄露我的隐私？
**A**: **不会**。本软件：
- **不联网上传任何数据**（仅检查更新时访问 GitHub API）
- **不包含任何广告或追踪代码**
- **所有数据均存储在本地**
- 详情请参阅 [隐私政策](PRIVACY_POLICY.md)

### Q5: 为什么扫描结果中有些项目显示"禁止清理"？
**A**: 这些项目属于**高风险系统组件**，删除后可能导致：
- 系统无法启动
- 某些软件无法运行
- 系统功能异常

软件仅将这些项目列出供用户参考，**不会**自动清理。

### Q6: 可以清理其他用户的垃圾文件吗？
**A**: 可以，但需要以管理员身份运行软件。软件会扫描 `C:\Users\` 下所有用户的临时文件和缓存。

---

## 🔧 开发与贡献

### 技术栈
- **GUI 框架**：PySide6 (Qt for Python)
- **系统信息**：psutil
- **文件操作**：send2trash（回收站操作）
- **打包工具**：PyInstaller

### 目录结构
```
垃圾清理/
├── main.py                  # 程序入口
├── cleaner_app/             # 核心功能模块
│   ├── ui.py                # 主界面
│   ├── scanner.py           # 扫描引擎
│   ├── executor.py          # 清理执行器
│   ├── rules.py             # 清理规则定义
│   ├── safety.py            # 安全检查器
│   ├── models.py            # 数据模型
│   ├── settings.py          # 配置管理
│   ├── update_checker.py    # 更新检查器
│   ├── update_downloader.py # 更新下载器
│   ├── update_ui.py         # 更新界面
│   ├── version.py           # 版本信息
│   └── windows_utils.py     # Windows 工具函数
├── tests/                   # 单元测试
├── icon.ico                 # 应用图标
├── requirements.txt         # Python 依赖
├── YanjinCleaner.spec       # PyInstaller 配置
├── README.md                # 本文件
├── LICENSE_EULA.md          # 最终用户许可协议
└── PRIVACY_POLICY.md        # 隐私政策
```

### 运行测试
```powershell
# 运行所有单元测试
python -m unittest discover -v

# 运行特定测试
python -m unittest tests.test_scanner

# 语法检查
python -m py_compile main.py cleaner_app\*.py tests\*.py
```

### 打包为 EXE
```powershell
# 安装打包依赖
pip install PyInstaller Send2Trash

# 打包（生成单个文件夹）
pyinstaller --noconfirm --clean YanjinCleaner.spec

# 打包结果位于 dist\YanjinCleaner\YanjinCleaner.exe
```

### 代码贡献
欢迎提交 Issue 和 Pull Request，但请注意：
1. 遵守现有代码风格（使用 `black` 和 `isort` 格式化）
2. 添加适当的单元测试
3. 更新相关文档

---

## 📄 法律文件

- [最终用户许可协议 (EULA)](LICENSE_EULA.md)
- [隐私政策](PRIVACY_POLICY.md)

**使用本软件即表示您同意上述协议的全部条款。**

---

## 🏗️ 技术架构

### 扫描引擎架构
```
用户触发扫描
    ↓
CleanupScanner (扫描器)
    ├── 加载清理规则 (rules.py)
    ├── 遍历目标路径
    ├── 应用安全检查 (SafetyGuard)
    └── 生成 CleanupItem 列表
    ↓
CleanupReport (扫描报告)
    └── 按风险等级分类
```

### 清理执行器架构
```
用户确认清理
    ↓
CleanupExecutor (执行器)
    ├── 风险等级验证
    ├── 文件备份（隔离区 / 回收站）
    ├── 执行清理操作
    └── 记录日志
    ↓
显示清理结果
```

### 更新系统架构
```
软件启动
    ↓
UpdateChecker (更新检查器)
    ├── 访问 GitHub API
    ├── 比较版本号
    └── 返回更新信息
    ↓
UpdateDialog (更新对话框)
    ├── 显示更新日志
    └── 用户确认更新
    ↓
UpdateDownloader (更新下载器)
    ├── 下载新版本
    ├── 验证 SHA256
    ├── 备份当前版本
    └── 启动更新程序 (updater_stub.exe)
```

---

## 📜 许可证信息

### 本软件许可
本软件为**专有软件**，受 [最终用户许可协议](LICENSE_EULA.md) 约束。**仅供个人学习研究使用，严禁商业用途。**

### 第三方组件许可证

本软件使用以下开源组件：

| 组件 | 版本 | 许可证 | 官网 |
|------|------|--------|------|
| PySide6 | 6.x | LGPLv3 | https://www.qt.io/qt-for-python |
| psutil | 5.x | BSD-3-Clause | https://github.com/giampaolo/psutil |
| send2trash | 1.x | BSD-3-Clause | https://github.com/arsenetar/send2trash |

#### PySide6 (LGPLv3) 合规说明
本软件使用 PyInstaller 打包时，以**动态链接方式**引用 Qt 库（DLL 文件位于发布目录中），符合 LGPLv3 许可证要求。用户有权替换发布目录中的 PySide6 DLL 文件为其他版本。

#### BSD 组件合规说明
本软件保留了 psutil 和 send2trash 的版权声明和许可证文本，符合 BSD-3-Clause 许可证要求。

---

## ⚖️ 免责声明

1. 本软件**按"现状"提供**，不提供任何明示或暗示的保证
2. 本软件**不是杀毒软件**，不承诺检测或清除计算机病毒
3. 开发者不对使用本软件导致的任何直接、间接、附带、特殊或后果性损害承担责任
4. 用户应**自行备份重要数据**，谨慎执行清理操作
5. 本软件**仅供学习研究**，使用者应遵守当地法律法规

---

## 📞 联系与反馈

- **问题反馈**：[GitHub Issues](https://github.com/Gwshhh/YanjinCleaner/issues)
- **功能建议**：[GitHub Discussions](https://github.com/Gwshhh/YanjinCleaner/discussions)
- **邮件联系**：请通过 GitHub 个人主页查看

---

## 🎓 学习资源

本项目适合以下学习场景：
- Python GUI 编程（PySide6）
- Windows 系统编程（注册表、服务、计划任务）
- 软件打包与分发（PyInstaller）
- 自动更新系统设计
- 软件安全设计（权限控制、数据备份）

---

**最后更新**：2026 年 6 月 14 日  
**当前版本**：v1.0.2  
**开发者**：[Gwshhh](https://github.com/Gwshhh)

---

**⚠️ 再次声明**：本软件仅供个人学习研究使用，不得用于任何商业用途。使用本软件即表示您已阅读、理解并同意 [最终用户许可协议](LICENSE_EULA.md) 和 [隐私政策](PRIVACY_POLICY.md)。
