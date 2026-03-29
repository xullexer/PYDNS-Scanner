# PYDNS 扫描器

<br>
<div align="center">
  <img
    src="https://github.com/user-attachments/assets/4ed004bc-b64f-4407-abb0-b14bd010354e"
    width="720"
    style="border-radius:12px;"
  />
</div>
<br>
<br>
<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Android-orange?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Termux-兼容-cyan?style=for-the-badge" alt="Termux">
</div>

<br>

<div align="center">
  🇺🇸 <a href="https://github.com/xullexer/PYDNS-Scanner/blob/main/README.md"><b>English</b></a>
  &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  🇮🇷 <a href="https://github.com/xullexer/PYDNS-Scanner/blob/main/README-FA.md"><b>فارسی</b></a>
  &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  🇨🇳 <a href="https://github.com/xullexer/PYDNS-Scanner/blob/main/README-ZH.md"><b>中文</b></a>
</div>

<br>

<div align="center">
  <strong>一款现代、高性能的 DNS 扫描器，拥有基于 Textual 构建的精美终端用户界面（TUI）。</strong><br>
  该工具可扫描数百万个 IP 地址以发现可用的 DNS 服务器，支持可选的 Slipstream / SlipNet（DNSTT、NoiseDNS）代理测试、自动 DNS 类型评分和多平台客户端下载。<br>
  <br>
  <strong>🆕 v2.0.0：SlipNet 支持、DNS Scan 模式、双向多范围扫描、高级设置和重大性能提升！</strong>
</div>

## 🎉 v2.0.0 更新内容

### 🌐 三种扫描模式
- **Slipstream** — 经典代理测试，支持 SOCKS5
- **SlipNet** — 完整 SlipNet 配置支持：DNSTT 和 NoiseDNS 隧道，支持 SOCKS5 / SSH 认证及自动检测认证方式
- **DNS Scan** — 全新轻量级模式：只需输入域名、设置并发数即可开始扫描 — 无需代理测试、无需认证。自动测试安全性、DNS 类型、延迟、解析 IP、EDNS0 等

### 🔀 全新扫描策略 — 双向多范围扫描
扫描器现从每个 IP 范围的**首尾两端**同时扫描，跨多个范围进行，结合随机混洗 — 与线性扫描相比，性能更快，发现可用 DNS 服务器的概率更高。

### 🧪 自动 DNS 类型检测 + 评分
所有 DNS 类型（A、AAAA、MX、TXT、NS）自动测试并为每台服务器评分 — 与 SlipNet 扫描器相同的评分系统。

### ⚙️ 全新高级设置区
完全可定制的扫描参数：
- 代理测试最低 ping 阈值
- DNS 连接超时
- 代理端到端测试超时
- 并行代理测试数量
- 自定义混洗步长
- 代理测试 URL + 预期响应状态码
- 设置 MTU（实验性操作系统级 MTU 覆盖）
- SlipNet 查询大小（DNSTT / NoiseDNS）

### 🎨 用户体验改进
- **增强的扫描统计** — 重新设计的统计显示，布局更清晰
- **更好的结果表格** — 改进的结果表格书写与格式
- **全新代理测试状态界面** — 实时代理测试反馈
- **更好的过滤 IP 检测** — 更准确地识别被过滤的 IP
- **日志区域始终可见** — 日志面板不再可切换；扫描期间始终显示

### 🔧 实验性功能：设置操作系统 MTU
使用指定的 MTU 值进行扫描，用于高级网络调优。

### ⚡ 性能
- 扫描性能大幅提升
- 自动检测 SlipNet 认证方式（DNSTT / NoiseDNS）

### ⚙️ Bug 修复
- 修复扫描大型 DNS 范围后 UI 冻结的问题
- 修复扫描超过 50 万个 IP 后速度下降的问题
- 修复长时间运行扫描时的内存泄漏
- 更新依赖以解决 Dependabot 低危漏洞警报

## ✨ 功能特性

- � **三种扫描模式** — Slipstream（代理测试）、SlipNet（DNSTT / NoiseDNS 隧道）、DNS Scan（轻量级，无需代理/认证）
- 🔀 **双向多范围扫描** — 从每个 IP 范围的首尾两端同时扫描，结合随机混洗，更快发现目标
- 🧪 **自动 DNS 类型评分** — 所有 DNS 类型（A、AAAA、MX、TXT、NS）自动测试并为每台服务器评分
- ⚙️ **高级设置** — 自定义代理 ping 阈值、DNS 超时、代理 E2E 超时、并行代理数量、混洗步长、测试 URL、MTU 和查询大小
- 🔐 **安全测试** — 劫持、过滤、开放解析器及 DNSSEC 检测
- 🌐 **Resolved IP 列** — 每台 DNS 服务器通过解析 `google.com` 进行验证
- 📡 **ISP 检测** — AS 号和组织名称
- 🌍 **IPv4 / IPv6 检测** — 支持的 IP 版本
- 📶 **EDNS0 检测** — EDNS0 扩展支持情况
- 🔌 **Slipstream Rust Plus** — 更快的代理测试，修复误报，独立 SOCKS5 测试
- 🔗 **SlipNet 支持** — DNSTT / NoiseDNS 隧道测试，支持 SOCKS5 / SSH 认证及自动检测
- 🧮 **智能排序** — 代理通过 → DNSSEC → Ping
- ⚡ **高性能** — 可配置并发的异步扫描
- ⏸️ **暂停 / 继续 / 混洗** — 完整的扫描控制
- 📊 **实时统计** — 扫描过程中的通过/失败/发现计数器
- 🔍 **智能 DNS 检测** — 即使返回 NXDOMAIN/NODATA 也能识别可用 DNS 服务器
- 🎲 **随机子域名** — 绕过缓存的 DNS 响应
- 🌐 **多种 DNS 类型** — A、AAAA、MX、TXT、NS
- 📝 **常驻日志面板** — 日志区域在扫描期间始终可见
- 🌍 **自动多平台下载** — 自动下载适合您平台的 Slipstream 客户端
- 📥 **断点续传** — 网络中断时智能续传
- 💾 **自动保存结果** — 包含每台服务器详情的 CSV 导出
- 📁 **CIDR 管理** — 内置伊朗 IP 列表 + 自定义文件选择器
- 🚀 **内存高效** — 流式 IP 生成，无需将所有 IP 加载至内存
- 🔔 **音频提示** — 代理测试成功时可选的提示音
- 🔧 **实验性 MTU** — 设置操作系统级 MTU 用于高级网络扫描

## 📋 前提条件

### Python 版本
- Python 3.11 或更高版本

### 依赖项

```bash
# 核心依赖（始终安装 — 在所有平台包括 Android/Termux 上均可工作）
textual>=0.47.0       # TUI 框架
aiodns>=3.1.0         # 异步 DNS 解析器
httpx[socks]>=0.25.0  # 支持 SOCKS5 的 HTTP 客户端（用于代理测试）
loguru>=0.7.0         # 高级日志记录

# 可选 "full" 额外包 (pip install pydns-scanner[full]) — 仅桌面端
google-re2>=1.0       # 快速 RE2 正则引擎（回退至标准库 re）
orjson>=3.9.0         # 快速 JSON 序列化（回退至标准库 json）
pyperclip>=1.8.0      # 剪贴板支持（缺少时自动禁用）
```

### 可选
- **Slipstream 客户端** — 用于代理测试功能（5 个并发测试）
  - **自动下载**：程序会自动检测您的平台并下载合适的客户端
  - **智能检测**：检测已有安装（包括旧版名称）
  - **断点续传**：未完成的下载保存为 `.partial` 文件，重新运行时自动续传
  - 支持的平台：
    - Linux (x86_64)：`slipstream-client-linux-amd64`
    - Linux (ARM64)：`slipstream-client-linux-arm64`
    - Windows (x86_64)：`slipstream-client-windows-amd64.exe`
    - macOS (ARM64)：`slipstream-client-darwin-arm64`
    - macOS (Intel)：`slipstream-client-darwin-amd64`
    - Android (ARM64)：`slipstream-client-linux-arm64`
  - 手动下载：[slipstream-rust-plus-deploy releases](https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest)

### 📦 随附的 Slipstream 客户端

来自 [Fox-Fig/slipstream-rust-plus-deploy](https://github.com/Fox-Fig/slipstream-rust-plus-deploy) 的预编译二进制文件已包含在 `slipstream-client/` 目录中：

| 平台 | 路径 | 说明 |
|------|------|------|
| **Linux x86_64** | `slipstream-client/linux/slipstream-client-linux-amd64` | Linux x86_64 二进制文件 |
| **Linux ARM64** | `slipstream-client/linux/slipstream-client-linux-arm64` | Linux ARM64 二进制文件（树莓派、ARM 服务器） |
| **Android/Termux** | `slipstream-client/android/slipstream-client-linux-arm64` | Android ARM64（Termux 兼容） |
| **Windows** | `slipstream-client/windows/slipstream-client-windows-amd64.exe` | Windows x86_64 可执行文件 |
| **macOS ARM** | `slipstream-client/mac/slipstream-client-darwin-arm64` | Apple Silicon Mac（M1/M2/M3/M4） |
| **macOS Intel** | `slipstream-client/mac/slipstream-client-darwin-amd64` | Intel x86_64 Mac |

> **⚠️ Windows 注意：** Windows 客户端需要 OpenSSL DLL 文件（`libcrypto-3-x64.dll` 和 `libssl-3-x64.dll`），已放置在 `slipstream-client/windows/` 目录中。使用自动下载时，这些文件会与 Windows 可执行文件一起自动下载。

### 可选
- **SlipNet 客户端** — 用于 SlipNet（DNSTT / NoiseDNS）隧道测试
  - **自动下载**：程序会自动检测您的平台并下载合适的 SlipNet 客户端
  - **智能检测**：检测已有安装
  - **断点续传**：未完成的下载保存为 `.partial` 文件，重新运行时自动续传
  - 支持的平台：
    - Linux (x86_64)：`slipnet-linux-amd64`
    - Linux (ARM64)：`slipnet-linux-arm64`
    - Windows (x86_64)：`slipnet-windows-amd64.exe`
    - macOS (ARM64)：`slipnet-darwin-arm64`
    - macOS (Intel)：`slipnet-darwin-amd64`
  - 手动下载：[anonvector](https://github.com/anonvector/SlipNet/releases)

### 📦 随附的 SlipNet 客户端

由 [anonvector](https://github.com/anonvector/SlipNet/releases) 开发的预编译 SlipNet 客户端二进制文件已包含在 `slipnet-client/` 目录中：

| 平台 | 路径 | 说明 |
|------|------|------|
| **Linux x86_64** | `slipnet-client/linux/slipnet-linux-amd64` | Linux x86_64 二进制文件 |
| **Linux ARM64** | `slipnet-client/linux/slipnet-linux-arm64` | Linux ARM64 二进制文件（树莓派、ARM 服务器） |
| **Windows** | `slipnet-client/windows/slipnet-windows-amd64.exe` | Windows x86_64 可执行文件 |
| **macOS ARM** | `slipnet-client/mac/slipnet-darwin-arm64` | Apple Silicon Mac（M1/M2/M3/M4） |
| **macOS Intel** | `slipnet-client/mac/slipnet-darwin-amd64` | Intel x86_64 Mac |

## 🚀 安装

### 方式一：从 PyPI 安装（推荐）

最简便的安装方式：

#### 使用 pip
```bash
pip install pydns-scanner
```

#### 桌面端 — 完整额外包（更快正则、剪贴板、快速 JSON）
```bash
pip install pydns-scanner[full]
```

#### 使用 uv（更快）
```bash
uv pip install pydns-scanner        # 核心
uv pip install pydns-scanner[full]   # 桌面端额外包
```

#### Android / Termux
```bash
pkg update && pkg install python
pip install pydns-scanner            # 仅核心 — 在 Termux 上始终可用
pydns-scanner
```

> **注意：** 在 Android/Termux 上，可选的 C 扩展包（`google-re2`、`orjson`、`pyperclip`）会自动跳过
> — 扫描器无需任何手动干预即可回退至标准库等价物。

#### 使用镜像源（适用于 PyPI 访问受限的用户）
```bash
# 阿里云镜像
pip install pydns-scanner -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 清华 TUNA 镜像
pip install pydns-scanner -i https://pypi.tuna.tsinghua.edu.cn/simple

# Runflare 镜像
pip install pydns-scanner -i https://mirror-pypi.runflare.com/simple/ --trusted-host mirror-pypi.runflare.com
```

#### 安装后运行
```bash
pydns-scanner
```

---

### 方式二：从源码运行（手动）

如需直接从仓库运行代码：

#### 第一步：克隆仓库
```bash
git clone https://github.com/xullexer/PYDNS-Scanner.git
cd PYDNS-Scanner
```

#### 第二步：安装依赖

**使用 uv（推荐 — 速度快！）**
```bash
uv pip install -r requirements.txt
```

**使用 pip**
```bash
pip install -r requirements.txt
```

**使用镜像源（适用于 PyPI 访问受限的用户）**
```bash
# 阿里云镜像
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 清华 TUNA 镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Runflare 镜像
pip install -r requirements.txt -i https://mirror-pypi.runflare.com/simple/ --trusted-host mirror-pypi.runflare.com
```

#### 第三步：运行程序
```bash
python -m python
```

---

## 🎮 使用方法

### 基本用法

**从 PyPI：**
```bash
pydns-scanner
```

**从源码：**
```bash
python -m python
```

启动后将打开交互式 TUI 界面，您可以配置：
- **CIDR 文件**：包含 IP 范围的文件路径（CIDR 表示法）
- **域名**：要查询的域名（例如 google.com）
- **DNS 类型**：记录类型（A、AAAA、MX、TXT、NS）
- **并发数**：并行工作线程数量（默认：100）
- **随机子域名**：添加随机前缀以绕过缓存的 DNS 响应
- **扫描模式**：选择 Slipstream（代理测试）、SlipNet（DNSTT/NoiseDNS）或 DNS Scan（轻量级）

### CIDR 文件格式

创建一个文本文件，每行一个 CIDR 范围：

```
# 以 # 开头的行为注释
1.1.1.0/24
8.8.8.0/24
178.22.122.0/24
185.51.200.0/22
```

### 使用示例

1. **启动程序**：
   ```bash
   python dnsscanner_tui.py
   ```

2. **配置扫描参数**：
   - 点击"📂 Browse"选择您的 CIDR 文件
   - 输入域名（例如 `google.com`）
   - 调整并发数（建议：100–500）
   - 根据需要启用相应选项

3. **开始扫描**：
   - 点击"🚀 Start Scan"
   - 实时查看进度和结果
   - 使用"⏸ Pause"随时暂停
   - 使用"▶ Resume"从暂停处继续

4. **查看结果**：
   - 按响应时间排序（最快优先）
   - 绿色 = 快速（<100ms）
   - 黄色 = 中等（100–300ms）
   - 红色 = 缓慢（>300ms）

5. **保存结果**：
   - 结果自动保存至 `results/TIMESTAMP.csv`
   - 按 `c` 键或点击"💾 Save Results"手动保存

## ⌨️ 键盘快捷键

| 按键 | 时机 | 功能 |
|------|------|------|
| `s` | 配置界面 | 开始扫描 |
| `q` | 任意时刻 | 退出程序 |
| `c` | 扫描中 | 保存结果 |
| `p` | 扫描中 | 暂停扫描 |
| `r` | 已暂停 | 继续扫描 |
| `x` | 已暂停 | 混洗剩余 IP |

## 🎮 控制按钮

扫描进行中时：
- **⏸ Pause** — 暂停扫描，不丢失进度
- **▶ Resume** — 从暂停处继续扫描
- **💾 Save Results** — 手动保存当前结果
- **🛑 Quit** — 退出程序

## 🎛️ 配置

### 并发设置

根据您的系统和网络进行调整：

- **低（50–100）**：保守模式，适合较慢的系统
- **中（100–300）**：均衡性能
- **高（300–500）**：快速扫描，需要较好的硬件
- **极高（500+）**：最大速度，可能触及资源限制

### Slipstream 测试设置

扫描器支持并行 Slipstream 代理测试，并自动下载：

```python
# 在 __init__ 方法中
self.slipstream_max_concurrent = 5  # 最大并行代理测试数
self.slipstream_base_port = 10800   # 基础端口（使用 10800、10801、10802）
```

## 📊 输出格式

结果以 **CSV 格式**保存（`results/TIMESTAMP.csv`）。列根据已启用的测试自动调整：

```csv
DNS,Ping (ms),IPv4/IPv6,TCP/UDP,Security,EDNS0,Resolved IP,ISP
8.8.8.8,12,IPv4/IPv6,TCP+UDP,DNSSEC,Yes,142.250.185.46,AS15169 Google LLC
1.1.1.1,15,IPv4/IPv6,TCP+UDP,DNSSEC,Yes,142.250.185.46,AS13335 Cloudflare Inc
```

可选列（**Proxy Test**、**Security**、**EDNS0**）仅在设置中启用对应测试时才会包含。

## 🔍 工作原理

### DNS 检测逻辑

扫描器将以下情况的服务器视为"可用 DNS"：

1. **成功响应**：在 2 秒内返回有效的 DNS 答案
2. **DNS 错误响应**：在 2 秒内返回 NXDOMAIN、NODATA 或 NXRRSET
   - 这些错误表明 DNS 服务器正在运行，只是记录不存在

这种方式比仅接受成功响应的工具能发现更多可用的 DNS 服务器。

### 性能优化

- **流式 IP 生成**：IP 从 CIDR 范围按需即时生成
- **分块处理**：以 500 个为一批处理 IP
- **异步 I/O**：使用 aiodns 进行非阻塞 DNS 查询
- **信号量控制**：限制并发操作以防止资源耗尽
- **内存映射**：尽可能使用 mmap 快速读取 CIDR 文件

## 📂 项目结构

```
PYDNS-Scanner/
├── README.md                          # 英文文档
├── README-FA.md                       # 波斯语文档
├── README-ZH.md                       # 中文文档
├── RELEASE_NOTES.md                   # 发行说明（EN / FA / ZH）
├── pyproject.toml                     # Python 包配置
├── requirements.txt                   # Python 依赖
├── pydns-scanner.spec                 # PyInstaller 构建规格
├── python/
│   ├── __init__.py                    # 包初始化
│   ├── __main__.py                    # 入口点（pydns-scanner CLI）
│   ├── dnsscanner_tui.py             # 主 TUI 程序
│   ├── iran-ipv4.cidrs               # 示例伊朗 CIDR 文件
│   ├── requirements.txt               # Python 依赖（源码）
│   ├── scanner/                       # 模块化扫描器包
│   │   ├── __init__.py
│   │   ├── config_mixin.py           # TUI 配置 Mixin
│   │   ├── constants.py              # 共享常量
│   │   ├── extra_tests.py            # 安全 & EDNS0 测试
│   │   ├── ip_streaming.py           # 从 CIDR 流式生成 IP
│   │   ├── isp_cache.py              # ISP 检测与缓存
│   │   ├── proxy_testing.py          # Slipstream 代理测试
│   │   ├── results.py                # 结果格式化及 CSV 导出
│   │   ├── slipnet.py                # SlipNet（DNSTT/NoiseDNS）测试
│   │   ├── slipstream.py            # Slipstream 客户端管理
│   │   ├── utils.py                  # 工具函数
│   │   ├── widgets.py                # 自定义 TUI 组件
│   │   └── worker_pool.py           # 异步工作池
│   ├── slipstream-client/            # 随附的 Slipstream 二进制文件
│   │   ├── linux/
│   │   ├── windows/
│   │   ├── mac/
│   │   └── android/
│   └── slipnet-client/               # 随附的 SlipNet 二进制文件
│       ├── linux/
│       ├── windows/
│       └── mac/
├── results/                           # 扫描结果（自动生成）
├── logs/                              # 应用日志（启用时）
└── static/                            # 静态资源
```

## 🌍 获取 CIDR 列表

### 国家 IP 范围

**IPv4**：
- https://www.ipdeny.com/ipblocks/data/aggregated/

**IPv6**：
- https://www.ipdeny.com/ipv6/ipaddresses/aggregated/

### 使用示例
```bash
# 下载中国 IPv4 范围
wget https://www.ipdeny.com/ipblocks/data/aggregated/cn-aggregated.zone -O china-ipv4.cidrs

# 在扫描器中使用
python dnsscanner_tui.py
# 然后在文件浏览器中选择 china-ipv4.cidrs
```

## 🐛 故障排除

### "No module named 'textual'"
```bash
pip install textual
```

### "File not found" 错误
- 确认 CIDR 文件路径正确
- 使用绝对路径或相对于脚本位置的相对路径
- 使用内置文件浏览器（📂 Browse 按钮）

### 扫描速度慢
- 降低并发数
- 检查网络带宽
- 确认 DNS 超时设置

### Slipstream 下载失败
- **网络问题**：程序会以指数退避自动重试最多 5 次
- **续传**：未完成的下载保存为 `.partial` 文件 — 重新运行即可
- **手动下载**：从 [slipstream-rust-plus-deploy releases](https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest) 下载
- **查看日志**：启用日志（参见配置部分）获取详细错误信息
- **防火墙**：确保允许访问 GitHub

### Slipstream 测试失败
- 确认可执行文件具有正确权限（Linux/macOS：`chmod +x`）
- 检查端口 10800–10802 是否可用
- 查看 `logs/` 目录中的日志（如已启用）
- 手动测试与 DNS 服务器的连接

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request 或开启 Issue。

### 开发环境设置
```bash
git clone https://github.com/xullexer/PYDNS-Scanner.git
cd PYDNS-Scanner/python
pip install -r requirements.txt
python dnsscanner_tui.py
```

## 📄 许可证

本项目基于 MIT 许可证发布。

## 👨‍💻 作者

- GitHub: [@xullexer](https://github.com/xullexer)

## 🙏 致谢

- 基于 [Textual](https://github.com/Textualize/textual)（由 Textualize 出品）构建
- DNS 解析通过 [aiodns](https://github.com/saghul/aiodns) 实现
- 灵感来源于对高效 DNS 服务器发现工具的需求
- 感谢 [**anonvector**](https://github.com/anonvector) 开发 **SlipNet CLI** — 本项目中包含的 SlipNet 客户端二进制文件来自他们的工作
- Python 代码现已实现**模块化**，更易于开发与维护

## 📈 性能说明

在不同系统上的测试性能：

- **小型扫描**（1,000 个 IP）：约 10–30 秒
- **中型扫描**（50,000 个 IP）：约 5–10 分钟
- **大型扫描**（100 万+ IP）：约 1–3 小时

*实际结果因网络速度、并发设置和系统资源而异。*

## 🔐 安全说明

- 使用加密安全随机数生成器（`secrets.SystemRandom`）
- 不记录任何凭据或敏感数据
- DNS 查询使用标准 UDP/TCP 53 端口
- Slipstream 代理测试为可选项，默认禁用

## 💝 支持项目

如果您觉得本项目有用，欢迎支持项目开发：

### 加密货币捐赠

- **比特币（BTC）**  
  `bc1qpya0kc2uh0mc08c7nuzrqkpsqjr36mrwscgpxr`

- **Solana（SOL）**  
  `J1XzZfizQ6mgYiyxpLGWU52kHBF1hm2Tb9AZ5FaRj8tH`

- **以太坊（ETH）**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **币安智能链（BNB/BSC）**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **波场（TRX）**  
  `TYBZFr8WUsjgfrXrqmrdF5EXPXo7QdimA8`

- **以太坊 Base（Ethereum Base）**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **Telegram Open Network（TON）**  
  `UQBcI_ZZGQq3fcNzTkL-zszgFR5HpRDLFHYRZffizriiScxJ`
