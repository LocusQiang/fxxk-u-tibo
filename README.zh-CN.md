# fxxk u tibo

**Windows 版 Codex 自动续接工具，附带随机抛厨具动画。**

> fxxk u tibo，no more Selected model is at capacity. Please try a different model.

[查看 60 种语言版本的文案](docs/slogan-translations.md) · 原名 **Codex Auto Retry Kitchen**。

[English](README.md) · [兼容性](docs/compatibility.md) · [更新记录](CHANGELOG.md) · [安全说明](SECURITY.md)

[![Windows tests](https://github.com/LocusQiang/fxxk-u-tibo/actions/workflows/test.yml/badge.svg)](https://github.com/LocusQiang/fxxk-u-tibo/actions/workflows/test.yml)

**[下载 v0.1.1 — Windows 预览版](https://github.com/LocusQiang/fxxk-u-tibo/releases/tag/v0.1.1)** · 源码 ZIP，需另行安装 Python 和 Node.js。

面向 **Windows 版 Codex 桌面应用**的非官方自动续接工具。对话因已核实的服务不可用、HTTP 503、服务器过载或模型容量不足而中断时，它会向同一对话发送固定中文 **`继续`**。屏幕上会抛过一个可爱的 AI 生成厨具，并显示位置固定、持续一秒的提醒。没有语音播报。

本项目独立于 OpenAI，不是官方产品或受官方支持的集成。它依赖未公开的桌面接口，接口可能随时变化。

![28 个 AI 生成厨具素材总览](docs/kitchen-contact-sheet.png)

## 开始前请先了解

**启动监控后，工具会自动续接符合条件的对话。第一次点击 Start 前，请确认以下默认行为符合你的意图：**

- 检测所配置 Codex 主目录下的本地用户对话，**排除已归档对话和 subagent（子代理）对话**。范围不限于当前打开的聊天。v0.1.x 暂无包含归档对话的开关。
- **首次正式 Start 会建立持久基线，跳过当时已存在的失败。** 之后只自动恢复新出现且符合条件的失败。安装和预览不会启动监控。如需恢复已有失败任务，请打开对应对话，手动发送一次 `继续`。
- 自动续接可能消耗 Codex 用量或额度，并继续原任务中的工具调用或其他动作。它沿用原对话的权限和设置，**不绕过审批，也不授予额外权限**。
- 实际发送始终是中文 **`继续`**。即使选择英文界面，也不会改成英文 `Continue`；v0.1.x 不支持自定义发送文本。
- 已处理的中断不会重复补发；发送结果未知时禁止自动补发。运行态未知或历史结构不兼容时，阻止该次提交。同一对话两次发送至少间隔 **30 秒**。同一对话随后出现新的、符合条件的中断时，仍可再次续接。
- 锁屏时，只要桌面应用与本地会话仍可用，后台发送继续；视觉提醒直接丢弃，解锁后不补播。电脑睡眠或关机期间无法运行。

安装本身不会启动监控，也不会启用开机自启。确认这些默认行为适合你 Codex 主目录里的任务后，再执行 Start。

**公开版与个人早期原型不同：**首次正式启动跳过已有失败，排除归档对话，并且不再通过旧版会话文件扫描触发自动发送。请以公开版文档为准，不要沿用早期原型的操作预期。

## 环境要求与兼容性

| 组件 | 要求 | 证据范围 |
| --- | --- | --- |
| Windows | Windows 10 或 11，x64 | 目标平台；当前报告的本机环境只有 Windows 11。 |
| Codex | 已安装并登录的 Windows 桌面应用 | 本机基线版本 **26.1016.6573.0**；其他版本需要重新检测能力。 |
| Python | **3.11–3.14**，包含 `tkinter` | 本机桌面检查使用 **3.14.3**；托管 CI 的 3.11、3.12、3.13、3.14 均通过。CI 不代表另一台电脑上的真实 Codex 兼容性。 |
| Node.js | 单独安装的 **22+** | 本机基线 **22.20**；最低版本要求不代表后续版本均已测试。 |
| Pillow | **12.2.0** | 安装时放入项目的 Python 虚拟环境。 |

不支持 Codex CLI、VS Code 扩展、macOS 或 Linux。不捆绑 Python、Node.js；请从 [Python Windows 下载页](https://www.python.org/downloads/windows/)和 [Node.js 下载页](https://nodejs.org/en/download)安装，并在 Python 安装时保留 Tcl/Tk 支持。

当前依赖桌面进程间通信（IPC）的 **snapshot v11**、**start-turn v2**，以及结构兼容的本地数据库 **`state_5.sqlite`** 和 **`thread_history_1.sqlite`**。两份数据库都必须存在；缺少历史数据库时 Doctor 会报错。这些属于内部实现，不是稳定的公开接口。Codex 升级后不保证检测或发送仍能工作，详见[兼容矩阵与升级步骤](docs/compatibility.md)。

## 安装

在 Windows 下载 ZIP 后，请先右键 ZIP，选择 **属性 > 解除锁定（Unblock）**并应用，**再解压**到可写目录（如果属性中显示该选项）。启动入口和自启脚本使用 `RemoteSigned`；下面的 `Bypass` 仅用于本次安装器调用，不要修改全局 PowerShell 执行策略。也可以使用源码检出目录。

在项目目录打开 PowerShell，运行：

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
~~~

安装会创建本地 Python 环境和运行配置，**不会启动自动重试，也不会注册开机自启**。

可选安装参数：

| 参数 | 取值 | 用途 |
| --- | --- | --- |
| `-CodexHome` | Codex 主目录路径 | 指定需要监控的本地数据目录。 |
| `-Language` | `auto`、`en` 或 `zh` | 选择界面语言；实际发送文字仍为 `继续`。 |
| `-Python` | Python 可执行文件 | 指定包含 `tkinter` 的 Python 3.11–3.14。 |

下例使用的是**占位路径，运行前必须替换**：

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -CodexHome "X:\path\to\codex-home" -Language zh -Python "X:\path\to\python.exe"
~~~

## 检测、预览、启动与停止

1. **先检测能力，不发送消息。** 在项目目录运行：

   ~~~powershell
   .\.venv\Scripts\python.exe .\doctor.py
   ~~~

   打开 Codex 后，也可以附加只读的桌面连接探测：

   ~~~powershell
   .\.venv\Scripts\python.exe .\doctor.py --connect
   ~~~

   Doctor 只检查本地能力；连接探测成功也不等于真实续接已验证。分享诊断结果前，先在本机检查内容。

2. **预览动画。** 双击 `Preview.vbs`，或运行：

   ~~~powershell
   powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\launch.ps1 -Demo
   ~~~

   预览只模拟视觉效果，不会向 Codex 发送续接消息。

3. **启动自动重试。** 保持 Codex 可用，确认已了解首次启动行为，再双击 `Start.vbs`，或运行：

   ~~~powershell
   powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\launch.ps1
   ~~~

4. **停止自动重试。** 双击 `Stop.vbs`。已经开始的一次发送可能会完成；Stop 不会取消已经恢复执行的 Codex 任务，如需取消请在 Codex 中操作。

## 可选的开机自启与故障恢复

开机自启需要**主动安装**：

~~~powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\install-autostart.ps1
~~~

自启机制在开机后的用户登录时启动，并每分钟检查、恢复守护进程。注册后，当前登录会话中的下一次恢复检查就可能启动监控，不必等到重启。守护进程会在工作进程意外退出后，按 **3–60 秒**的退避间隔重新启动它。这些是恢复间隔，不保证服务可用或消息发送成功。

手动 Stop 会持续生效，直到显式 Start 或下一次重启。安装了自启时，下一次重启并登录可以恢复监控。移除后续自启：

~~~powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\install-autostart.ps1 -Remove
~~~

移除自启不会停止已经运行的监控。如需立即停止，请同时使用 `Stop.vbs`。

## 何时会发送续接

工具从必需的数据库中读取本地会话元数据和结构化故障信息。发送前会用桌面实时状态核对准确的对话及其最新失败轮次。正在运行、运行态未知、已经恢复或发生变化的轮次，以及不符合服务不可用、503、过载、容量不足识别规则的故障，都不会触发发送。历史数据库缺失或结构不兼容时阻止发送，不使用旧版 rollout 会话文件回退触发自动发送。它不负责处理所有报错、登录问题、审批请求或网络断开。

每次提交前都会先写入本地记录。已确认发送、提交中、结果未知的记录，以及首次启动基线，都会跨重启保留。结果未知时，请自行检查对应对话，禁止自动补发。不要删除或重置运行状态来强制重试：基线与发送记录都是防止意外续接和重复发送的依据。

只有桌面返回的新轮次标识是有效的非空字符串，才能确认发送。确认数据缺失或格式异常属于结果未知，不能据此补发。“发送已确认”也不代表原任务已经完成。

## 本地数据与隐私

- 工具以只读方式打开 Codex 数据库。公开版要求状态与历史数据库结构兼容，不使用旧版会话文件作为自动发送的回退来源，不读取 `auth.json`。
- 运行配置、日志、首次启动基线、发送记录、计数和进程状态默认存放在**项目目录内的 `.runtime/`**。该目录可能包含对话标识、标题、本地路径和运行细节，应作为私有数据保留。
- 工具不上传聊天，不收集分析数据。发送 `继续` 会让 Codex 通过自身正常服务恢复对话，Codex 自身的联网和数据处理仍然适用。安装依赖时会下载软件包。
- Git 忽略运行数据；发行包必须按明确的文件允许清单打包，排除运行数据、本地环境和私有诊断材料。不要直接压缩整个工作目录作为发行包。打包检查结果单独记录在[兼容性文档](docs/compatibility.md#release-validation-record)。

公开 Issue 或 Pull Request 请使用合成示例。不要上传原始运行文件、会话数据库、认证数据、真实对话 ID、个人路径或私人聊天截图。私密漏洞报告方式见[安全说明](SECURITY.md)。

## 常见问题

| 情况 | 下一步 |
| --- | --- |
| 安装找不到 Python、`tkinter` 或 Node.js | 安装所需组件；用 `-Python` 选择正确的 Python，然后重新安装。 |
| Doctor 报告数据库结构或桌面连接异常 | 停止监控，核对 Codex 版本与主目录，并按[兼容性文档](docs/compatibility.md)处理。 |
| 旧对话或归档对话没有恢复 | 首次基线会跳过已有失败，归档对话被排除。如需恢复旧任务，请打开对话手动发送一次 `继续`。 |
| 新的符合条件的对话没有恢复 | 打开对话检查状态；用 Doctor 核对历史数据库是否缺失或不兼容，并确认桌面运行态能被识别。 |
| 发送结果未知 | 先检查对话；工具不会自动补发该次中断。 |
| 锁屏期间没有动画 | 属于预期行为；后台可以继续发送，锁屏视觉提醒永久丢弃。 |
| 重启后监控又启动了 | 如需以后登录也保持关闭，请移除已主动安装的自启注册。 |

## 验证状态

维护者提供的**单机本地桌面基线**为 Windows 11 x64、Codex 26.1016.6573.0、Python 3.14.3、Node.js 22.20。尚未在另一台电脑验证桌面兼容性。

维护者报告，v0.1.0 候选版的 **48 项 Python 测试、16 项 Node 测试、26 项 Windows PowerShell 5.1 检查在本地通过**。安装在公开版工作目录，以及从允许清单 ZIP 解压得到的中文、含空格嵌套路径中均已通过；发布包 Demo 启动也已通过。英中视觉 smoke 检查通过；Doctor 只读连接与真实空闲快照解析通过，**真实续接消息发送数为零**。

**[GitHub Actions 运行 39750132929](https://github.com/LocusQiang/fxxk-u-tibo/actions/runs/39750132929) 在修订 `6a9037d` 上通过**：四个 `windows-latest` 任务分别使用 Python 3.11、3.12、3.13、3.14，均搭配 Node.js 22。每个任务均通过 48 项 Python 测试、16 项 Node 测试、PowerShell 语法解析和打包。该运行早于新增的 PowerShell 生命周期测试脚本；上面的 26 项结果属于本地证据。上方徽章链接当前工作流运行。

公开版尚**未验证**真实发送、真实锁屏/解锁、计划任务注册和重启恢复。托管环境的模拟测试不代表另一台电脑上的真实 Codex 行为。实测数值与证据范围见[验证记录](docs/compatibility.md#release-validation-record)。

## 贡献与许可

项目地址：[LocusQiang/fxxk-u-tibo](https://github.com/LocusQiang/fxxk-u-tibo)。提交问题、诊断信息或改动前，请阅读[贡献指南](CONTRIBUTING.md)。

软件采用 [MIT 许可证](LICENSE)，copyright **2026 LocusQiang**。随附 AI 生成厨具图片在贡献者可许可的权利范围内按 MIT 提供，不声称 AI 生成内容具有独占版权。依赖保留各自的许可，详见[第三方声明](THIRD_PARTY_NOTICES.md)。
