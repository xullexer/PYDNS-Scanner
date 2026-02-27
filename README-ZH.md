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
  该工具可扫描数百万个 IP 地址以发现可用的 DNS 服务器，支持可选的 Slipstream 代理测试和自动多平台客户端下载。<br>
  <br>
  <strong>🆕 v1.4.0：新增 Resolved IP 列、智能多键排序、代理 HTTPS-CONNECT 修复及性能改进！</strong>
</div>

## 🎉 v1.4.0 更新内容

### 🎨 重新设计的启动菜单
- **更好的用户界面** — 配置界面全面重新设计，布局更简洁，视觉层次更清晰
- **可选日志面板** — 日志输出默认隐藏；扫描期间随时按 `L` 键切换显示/隐藏

### 🗂️ 三种扫描模式
三种模式使用完全相同的扫描逻辑，区别仅在于从 CIDR 文件中读取的最大 IP 数量及**混洗步长**：若在连续该数量的 IP 中未发现可用 DNS，则剩余范围将自动重新混洗，避免遗漏分散在大子网中的服务器。
- **Quick Scan（快速扫描）** — 最多 **25,000 个 IP**，每 **500** 个 IP 混洗一次
- **Deep Scan（深度扫描）** — 最多 **50,000 个 IP**，每 **1,000** 个 IP 混洗一次
- **Full Scan（完整扫描）** — **不限 IP 数量**（整个文件），每 **3,000** 个 IP 混洗一次

### 🔐 安全测试
- **劫持检测** — 检测 DNS 服务器是否拦截或重定向查询
- **过滤检测** — 识别静默屏蔽特定域名的服务器
- **开放解析器检查** — 标记解析任意外部查询的服务器
- **DNSSEC 验证** — 报告服务器是否返回已签名（DNSSEC）的响应

### 🌐 网络分析列
- **Resolved IP** — 每个候选 DNS 服务器解析 `google.com`，结果 IP 显示在结果表中
- **ISP 检测** — 通过 ip-api.com 获取每台服务器的 AS 号和组织名称（限速、异步）
- **IPv4 / IPv6 检测** — 显示每台服务器支持的 IP 版本
- **EDNS0 检测** — 测试并显示 EDNS0 扩展支持情况
- **TCP / UDP 列** — 测试并显示支持的传输协议

### 🔌 Slipstream Rust Plus — 改进的代理测试
- **升级至 Slipstream Rust Plus 客户端** — 所有平台二进制文件速度显著提升
- **HTTPS CONNECT 隧道** — 代理测试现通过 HTTP CONNECT 访问 `https://www.google.com`；旧版纯 HTTP 探测始终返回"Failed"
- **独立 SOCKS5 测试** — SOCKS5 单独测试，而非仅作为回退方案
- **消除误报** — 改进的结果验证去除错误的通过/失败结果
- **智能多键排序** — 排序顺序：代理通过 → DNSSEC → 最快 ping

### 🗃️ 结果表格全面升级
- **新列布局** — 移除端口列；顺序：Ping → [Proxy] → IPv4/IPv6 → Security → TCP/UDP → EDNS0 → Resolved IP → ISP
- **实时通过/失败计数器** — 统计栏在整个扫描过程中正确更新

### 🐛 缺陷修复
- **自定义 CIDR 选择** — 修复了在扫描菜单中选择自定义 IP 范围文件未正确应用的问题
- **/31 和 /32 子网修复** — 此前这些子网的 IP 被静默跳过
- **ISP 锁挂起修复** — 速率限制锁在休眠前释放，消除流水线停滞

### ⚡ 性能与模块改进
- **`google-re2`** — 将 Python 标准库 `re` 替换为 Google RE2 引擎，正则处理更快更安全
- **每次测试独立解析器** — 为每个 DNS 测试创建独立 aiodns 解析器，防止 C-ares 并发挂起
- **基于范围的 IP 混洗** — 对大 CIDR 范围使用整数运算替代 `list(subnet.hosts())`
- **ISP 速率限制器** — ip-api.com 请求受异步锁限制，429 错误自动重试（60 秒退避）
- **Windows 套接字提示** — 并发数超过 64 时记录警告（Windows 选择器事件循环上限）

## ✨ 功能特性

- 🎨 **重新设计的启动菜单** — 现代简洁的配置界面
- 🗂️ **三种扫描模式** — Quick（最多 25K，步长 500）、Deep（最多 50K，步长 1K）、Full（不限，步长 3K）— 相同逻辑，不同规模
- 🔄 **智能自动混洗** — 在步长范围内未找到可用 DNS 时，自动混洗剩余范围
- 🔐 **安全测试** — 劫持、过滤、开放解析器及 DNSSEC 检测
- 🌐 **Resolved IP 列** — 每台 DNS 服务器通过解析 `google.com` 进行验证
- 📡 **ISP 检测** — AS 号和组织名称
- 🌍 **IPv4 / IPv6 检测** — 支持的 IP 版本
- 📶 **EDNS0 检测** — EDNS0 扩展支持情况
- 🔌 **Slipstream Rust Plus** — 更快的代理测试，修复误报，独立 SOCKS5 测试
- 🧮 **智能排序** — 代理通过 → DNSSEC → Ping
- ⚡ **高性能** — 可配置并发的异步扫描
- ⏸️ **暂停 / 继续 / 混洗** — 完整的扫描控制
- 📊 **实时统计** — 扫描过程中的通过/失败/发现计数器
- 🔍 **智能 DNS 检测** — 即使返回 NXDOMAIN/NODATA 也能识别可用 DNS 服务器
- 🎲 **随机子域名** — 绕过缓存的 DNS 响应
- 🌐 **多种 DNS 类型** — A、AAAA、MX、TXT、NS
- 📝 **可选日志面板** — 默认隐藏；按 `L` 键切换显示/隐藏
- 🌍 **自动多平台下载** — 自动下载适合您平台的 Slipstream 客户端
- 📥 **断点续传** — 网络中断时智能续传
- 💾 **自动保存结果** — 包含每台服务器详情的 CSV 导出
- 📁 **CIDR 管理** — 内置伊朗 IP 列表 + 自定义文件选择器（已修复缺陷）
- ⚙️ **可配置** — 可调节并发数、超时及过滤器
- 🚀 **内存高效** — 流式 IP 生成，无需将所有 IP 加载至内存
- 🚄 **google-re2** — Google RE2 引擎实现更快的正则匹配
- 🔔 **音频提示** — 代理测试成功时可选的提示音

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
- **Slipstream 测试**：为已找到的 DNS 服务器启用代理测试

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
| `l` | 扫描中 | 切换日志面板显示/隐藏 |
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
