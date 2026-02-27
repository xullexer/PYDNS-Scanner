# PYDNS Scanner

<br>
<div align="center">
  <img
    src="https://github.com/user-attachments/assets/3082a260-5d40-4134-9c95-622c12f770cc"
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
  <img src="https://img.shields.io/badge/Termux-Compatible-cyan?style=for-the-badge" alt="Termux">
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
  <strong>A modern, high-performance DNS scanner with a beautiful Terminal User Interface (TUI) built with Textual.</strong><br>
  This tool can scan millions of IP addresses to find working DNS servers with optional Slipstream proxy testing and automatic multi-platform client download.<br>
  <br>
  <strong>🆕 v1.4.0: Resolved IP column, smart multi-key sorting, proxy HTTPS-CONNECT fix, performance improvements!</strong>
</div>

## 🎉 What's New in v1.4.0

### 🎨 Redesigned Start Menu
- **Better UI** - Completely redesigned configuration screen with cleaner layout and improved visual hierarchy
- **Optional log panel** - Log output is hidden by default; press `L` at any time during a scan to toggle it on or off

### 🗂️ Three Scan Modes
All three modes use identical scan logic. They differ only in how many IPs are read from the CIDR file and the **shuffle step** — if no working DNS is found within that many consecutive IPs, the remaining range is automatically reshuffled to avoid missing servers hidden deep in a subnet.
- **Quick Scan** — up to 25,000 IPs, shuffle step every 500 IPs
- **Deep Scan** — up to 50,000 IPs, shuffle step every 1,000 IPs
- **Full Scan** — unlimited IPs (entire file), shuffle step every 3,000 IPs

### 🔐 Security Testing
- **Hijack detection** - Detects if the DNS server is intercepting or redirecting queries
- **Filtered detection** - Identifies servers that silently block certain domains
- **Open resolver check** - Flags servers that resolve arbitrary external queries
- **DNSSEC validation** - Reports whether the server returns signed (DNSSEC) responses

### 🌐 Network Analysis Columns
- **Resolved IP** - Each candidate DNS server is used to resolve `google.com`; the resulting IP is shown in the results table
- **ISP detection** - Displays AS number and organisation name for each DNS server via ip-api.com (rate-limited, async)
- **IPv4 / IPv6 detection** - Shows whether the server responds on IPv4, IPv6, or both
- **EDNS0 detection** - Tests and displays EDNS0 extension support
- **TCP / UDP column** - Tests and shows which transports the server supports

### 🔌 Slipstream Rust Plus — Improved Proxy Testing
- **Upgraded to Slipstream Rust Plus client** ([Fox-Fig/slipstream-rust-plus-deploy](https://github.com/Fox-Fig/slipstream-rust-plus-deploy)) — significantly faster binaries across all platforms
- **HTTPS CONNECT tunnel** - Proxy test now targets `https://www.google.com` via HTTP CONNECT; the previous plain-HTTP probe always returned "Failed"
- **Independent SOCKS5 test** - SOCKS5 is tested on its own, not just as a fallback
- **False-positive elimination** - Improved result validation removes incorrect pass/fail determinations
- **Smart multi-key sort** - Results ordered by: Proxy pass → DNSSEC → fastest ping

### 🗃️ Results Table Overhaul
- **New column layout** - Port column removed; column order: Ping → [Proxy] → IPv4/IPv6 → Security → TCP/UDP → EDNS0 → Resolved IP → ISP
- **Live pass/fail counters** - Statistics bar updates correctly throughout the scan

### 🐛 Bug Fixes
- **Custom CIDR selection** - Fixed a bug where selecting a custom IP range file in the scan menu was not applied correctly
- **/31 and /32 subnet fix** - IPs from these subnets were previously skipped silently
- **ISP lock hang** - Rate-limit lock is now released before sleeping, eliminating pipeline stalls

### ⚡ Performance & Module Improvements
- **`google-re2`** - Replaced Python's stdlib `re` with Google's RE2 engine for faster, safer regex
- **Per-test aiodns resolver** - Each DNS test creates its own resolver, preventing C-ares concurrency hangs
- **Range-based IP shuffle** - Integer arithmetic replaces `list(subnet.hosts())` for large CIDR ranges
- **ISP rate limiter** - ip-api.com capped with async lock + automatic 429 retry with 60 s backoff
- **Windows socket advisory** - Warning logged when concurrency exceeds 64 (Windows selector event-loop cap)

## ✨ Features

- 🎨 **Redesigned Start Menu** - Clean, modern configuration screen with improved layout
- 🗂️ **Three Scan Modes** - Quick (25K IPs, step 500), Deep (50K IPs, step 1K), Full (unlimited, step 3K) — same logic, different scale
- 🔄 **Auto-Shuffle** - Reshuffles remaining IPs automatically when no working DNS is found within the step range
- 🔐 **Security Testing** - Detects hijacked, filtered, open resolver, and DNSSEC per server
- 🌐 **Resolved IP Column** - Tests each DNS server by resolving `google.com`, result shown in table
- 📡 **ISP Detection** - AS number and organisation name via ip-api.com
- 🌍 **IPv4 / IPv6 Detection** - Reports which IP versions each server supports
- 📶 **EDNS0 Detection** - Tests and displays EDNS0 extension support
- 🔌 **Slipstream Rust Plus** - Faster proxy testing with false-positive fixes and independent SOCKS5 test
- 🧮 **Smart Multi-key Sort** - Auto-sorts by proxy pass → DNSSEC → ping for best servers first
- ⚡ **High Performance** - Asynchronous scanning with configurable concurrency
- ⏸️ **Pause / Resume / Shuffle** - Full live scan control
- 📊 **Real-time Statistics** - Live pass/fail/found counters updated throughout the scan
- 🔍 **Smart DNS Detection** - Detects working DNS servers even with NXDOMAIN / NODATA responses
- 🎲 **Random Subdomain Support** - Avoid cached responses with random subdomains
- 🌐 **Multiple DNS Types** - Supports A, AAAA, MX, TXT, NS records
- 📝 **Optional Log Panel** - Hidden by default; press `L` during scan to toggle
- 🌍 **Multi-Platform Auto-Download** - Automatically downloads the correct Slipstream client for your platform
- 📥 **Resume Downloads** - Smart download resume on network interruptions with retry logic
- 💾 **Auto-save Results** - Automatic CSV export with per-server detail
- 📁 **CIDR Management** - Built-in Iran IPs + custom file picker (bug-fixed)
- ⚙️ **Configurable** - Adjustable concurrency, timeouts, and filters
- 🚀 **Memory Efficient** - Streaming IP generation without loading all IPs into memory
- 🚄 **google-re2** - Google's RE2 engine for faster, safer regex matching
- 🔔 **Audio Alerts** - Optional sparkle sound on successful proxy test

## 📋 Requirements

### Python Version
- Python 3.11 or higher

### Dependencies

```bash
# Core dependencies
textual>=0.47.0       # TUI framework
aiodns>=3.1.0         # Async DNS resolver
httpx[socks]>=0.25.0  # HTTP client with SOCKS5 support for proxy testing
orjson>=3.9.0         # Fast JSON serialization
loguru>=0.7.0         # Advanced logging
pyperclip>=1.8.0      # Clipboard support
google-re2>=1.0       # Fast RE2 regex engine (replaces stdlib re)
```

### Optional
- **Slipstream Client** - For proxy testing functionality (5 concurrent tests)
  - **Automatic Download**: The application automatically detects your platform and downloads the correct client
  - **Smart Detection**: Detects existing installations (including legacy filenames)
  - **Resume Support**: Partial downloads are saved and can be resumed on retry
  - Supported platforms:
    - Linux (x86_64): `slipstream-client-linux-amd64`
    - Linux (ARM64): `slipstream-client-linux-arm64`
    - Windows (x86_64): `slipstream-client-windows-amd64.exe`
    - macOS (ARM64): `slipstream-client-darwin-arm64`
    - macOS (Intel): `slipstream-client-darwin-amd64`
    - Android (ARM64): `slipstream-client-linux-arm64`
  - Manual download available from: [slipstream-rust-plus-deploy releases](https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest)

### 📦 Bundled Slipstream Clients

Pre-compiled Slipstream client binaries (from the faster [Fox-Fig/slipstream-rust-plus-deploy](https://github.com/Fox-Fig/slipstream-rust-plus-deploy)) are included in the `slipstream-client/` folder for all platforms:

| Platform | Path | Description |
|----------|------|-------------|
| **Linux x86_64** | `slipstream-client/linux/slipstream-client-linux-amd64` | Linux x86_64 binary |
| **Linux ARM64** | `slipstream-client/linux/slipstream-client-linux-arm64` | Linux ARM64 binary (Raspberry Pi, ARM servers) |
| **Android/Termux** | `slipstream-client/android/slipstream-client-linux-arm64` | Android ARM64 (Termux compatible) |
| **Windows** | `slipstream-client/windows/slipstream-client-windows-amd64.exe` | Windows x86_64 executable |
| **macOS ARM** | `slipstream-client/mac/slipstream-client-darwin-arm64` | macOS Apple Silicon (M1/M2/M3/M4) |
| **macOS Intel** | `slipstream-client/mac/slipstream-client-darwin-amd64` | macOS Intel x86_64 |

> **⚠️ Windows Note:** The Windows client requires OpenSSL DLLs (`libcrypto-3-x64.dll` and `libssl-3-x64.dll`) which are included in the `slipstream-client/windows/` folder. When using automatic download, these DLLs are downloaded automatically alongside the Windows executable.

#### 📥 All-in-One Archives

For convenience, compressed archives containing all platform binaries are available:

- **`slipstream-client/slipstream-client-all-platforms.tar.gz`** - Best compression (recommended)
- **`slipstream-client/slipstream-client-all-platforms.zip`** - Windows-friendly format

These archives include Linux, Windows, and macOS clients in a single download.

## 🚀 Installation

### Method 1: Install from PyPI (Recommended)

The easiest way to install PYDNS Scanner:

#### Using pip
```bash
pip install pydns-scanner
```

#### Using uv (Faster)
```bash
uv pip install pydns-scanner
```

#### Using Mirror (For Users with Limited Access to PyPI)
```bash
# Runflare Mirror
pip install pydns-scanner -i https://mirror-pypi.runflare.com/simple/ --trusted-host mirror-pypi.runflare.com

# Or Alibaba Cloud Mirror
pip install pydns-scanner -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# Or TUNA Mirror
pip install pydns-scanner -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### Run after installation
```bash
pydns-scanner
```

---

### Method 2: Run from Source (Manual)

If you want to run the code directly from the repository:

#### Step 1: Clone the Repository
```bash
git clone https://github.com/xullexer/PYDNS-Scanner.git
cd PYDNS-Scanner
```

#### Step 2: Install Dependencies

**Using uv (Recommended - Fast!)**
```bash
uv pip install -r requirements.txt
```

**Using pip**
```bash
pip install -r requirements.txt
```

**Using Mirror (For Users with Limited Access to PyPI)**
```bash
# Runflare Mirror
pip install -r requirements.txt -i https://mirror-pypi.runflare.com/simple/ --trusted-host mirror-pypi.runflare.com

# Or Alibaba Cloud Mirror
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# Or TUNA Mirror
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### Step 3: Run the Application
```bash
python -m python
```

---

## 🎮 Usage

### Basic Usage

**From PyPI:**
```bash
pydns-scanner
```

**From source:**
```bash
python -m python
```

This will launch the interactive TUI where you can configure:
- **CIDR File**: Path to file containing IP ranges (CIDR notation)
- **Domain**: Domain to query (e.g., google.com)
- **DNS Type**: Record type (A, AAAA, MX, TXT, NS)
- **Concurrency**: Number of parallel workers (default: 100)
- **Random Subdomain**: Add random prefix to avoid cached responses
- **Slipstream Test**: Enable proxy testing for found DNS servers

### CIDR File Format

Create a text file with one CIDR range per line:

```
# Comments start with #
1.1.1.0/24
8.8.8.0/24
178.22.122.0/24
185.51.200.0/22
```

### Example Workflow

1. **Launch the application**:
   ```bash
   python dnsscanner_tui.py
   ```

2. **Configure scan parameters**:
   - Click "📂 Browse" to select your CIDR file
   - Enter domain (e.g., `google.com`)
   - Set concurrency (recommended: 100-500)
   - Enable options as needed

3. **Start scanning**:
   - Click "🚀 Start Scan"
   - Watch real-time progress and results
   - Use "⏸ Pause" to pause the scan at any time
   - Use "▶ Resume" to continue from where you paused

4. **View results**:
   - Sorted by response time (fastest first)
   - Green = fast (<100ms)
   - Yellow = medium (100-300ms)
   - Red = slow (>300ms)

5. **Save results**:
   - Results are auto-saved to `results/TIMESTAMP.csv`
   - Press `c` or click "💾 Save Results" to save manually

## ⌨️ Keyboard Shortcuts

| Key | When | Action |
|-----|------|--------|
| `s` | Config screen | Start scan |
| `q` | Anytime | Quit application |
| `c` | While scanning | Save results |
| `p` | While scanning | Pause scan |
| `l` | While scanning | Toggle log panel |
| `r` | When paused | Resume scan |
| `x` | When paused | Shuffle remaining IPs |

## 🎮 Control Buttons

During an active scan:
- **⏸ Pause** - Pause the scan without losing progress
- **▶ Resume** - Continue scanning from where you paused
- **💾 Save Results** - Manually save current results
- **🛑 Quit** - Exit the application

## 🎛️ Configuration

### Logging

Logging is **disabled by default** to keep the interface clean and avoid unnecessary disk writes.

**To enable logging**, edit `dnsscanner_tui.py`:

```python
# Configure logging (disabled by default)
logger.remove()  # Remove default handler to disable logging
# Uncomment the line below to enable file logging
logger.add(
    "logs/dnsscanner_{time}.log",
    rotation="50 MB",
    compression="zip",
    level="DEBUG",
)
```

When enabled:
- Logs are saved to `logs/dnsscanner_TIMESTAMP.log`
- Auto-rotate at 50 MB
- Compressed automatically (zip)
- Includes DEBUG level details

### Concurrency Settings

Adjust based on your system and network:

- **Low (50-100)**: Conservative, suitable for slower systems
- **Medium (100-300)**: Balanced performance
- **High (300-500)**: Fast scanning, requires good hardware
- **Very High (500+)**: Maximum speed, may hit resource limits

### Slipstream Testing

The scanner supports parallel Slipstream proxy testing with automatic download:

```python
# In __init__ method
self.slipstream_max_concurrent = 5  # Max parallel proxy tests
self.slipstream_base_port = 10800   # Base port (uses 10800, 10801, 10802)
```

**Auto-Download Features:**
- Platform detection (Windows/Linux/macOS + architecture)
- Progress bar with download speed
- Resume on interruption (keeps `.partial` files)
- Retry with exponential backoff (up to 5 attempts)
- Legacy filename detection (`slipstream-client.exe`)

### DNS Timeout

DNS queries timeout after 2 seconds:

```python
# In _test_dns method
resolver = aiodns.DNSResolver(nameservers=[ip], timeout=2.0, tries=1)
```

## 📊 Output Format

Results are saved in **CSV format** (`results/TIMESTAMP.csv`). Columns adapt to which tests are enabled:

```csv
DNS,Ping (ms),IPv4/IPv6,TCP/UDP,Security,EDNS0,Resolved IP,ISP
8.8.8.8,12,IPv4/IPv6,TCP+UDP,DNSSEC,Yes,142.250.185.46,AS15169 Google LLC
1.1.1.1,15,IPv4/IPv6,TCP+UDP,DNSSEC,Yes,142.250.185.46,AS13335 Cloudflare Inc
```

Optional columns (**Proxy Test**, **Security**, **EDNS0**) are included only when the corresponding test is enabled in settings.

## 🔍 How It Works

### DNS Detection Logic

The scanner considers a server as "working DNS" if:

1. **Successful Response**: Returns valid DNS answer in <2s
2. **DNS Error Responses**: Returns NXDOMAIN, NODATA, or NXRRSET in <2s
   - These errors mean the DNS server IS working, just the record doesn't exist

This approach catches more working DNS servers than tools that only accept successful responses.

### Performance Optimizations

- **Streaming IP Generation**: IPs are generated on-the-fly from CIDR ranges
- **Chunked Processing**: Processes IPs in batches of 500
- **Async I/O**: Non-blocking DNS queries using aiodns
- **Semaphore Control**: Limits concurrent operations to prevent resource exhaustion
- **Memory Mapping**: Fast CIDR file reading using mmap when possible

### Random Subdomain Feature

When enabled, queries use random prefixes:
```
original: google.com
random:   a1b2c3d4.google.com
```

**Use case**: Bypass cached DNS responses
**Requirement**: Target domain should have wildcard DNS (`*.example.com`)

## 📂 Directory Structure

```
PYDNS-Scanner/
├── README.md                   # This file
├── python/
│   ├── dnsscanner_tui.py      # Main application
│   ├── requirements.txt        # Python dependencies
│   └── iran-ipv4.cidrs        # Sample CIDR file
├── logs/                       # Application logs (when enabled, gitignored)
├── results/                    # Scan results (gitignored)
└── slipstream-client/          # Slipstream binaries (auto-downloaded, gitignored)
    ├── windows/
    ├── linux/
    └── macos/
```

## 🐛 Troubleshooting

### "No module named 'textual'"
```bash
pip install textual
```

### "File not found" error
- Ensure CIDR file path is correct
- Use absolute path or relative path from script location
- Use the built-in file browser (📂 Browse button)

### Slow scanning
- Reduce concurrency value
- Check network bandwidth
- Verify DNS timeout settings

### High memory usage
- The scanner uses streaming to minimize memory
- If issues persist, reduce chunk size in `_stream_ips_from_file`

### Slipstream download fails
- **Network issues**: The app automatically retries up to 5 times with exponential backoff
- **Resume**: Partial downloads are saved as `.partial` files - just run again to resume
- **Manual download**: Download from [slipstream-rust-plus-deploy releases](https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest)
- **Check logs**: Enable logging (see Configuration section) for detailed error info
- **Firewall**: Ensure GitHub access is allowed

### Slipstream not detected
- Check platform-specific directory exists (`slipstream-client/windows/`, etc.)
- Verify filename matches (supports both new and legacy names)
- For legacy installs: Use `slipstream-client.exe` (auto-detected)
- Enable logging to see detection process

### Slipstream tests fail
- Verify executable has correct permissions (Linux/macOS: `chmod +x`)
- Check that ports 10800-10802 are available
- Review logs (if enabled) in `logs/` directory
- Test connectivity to DNS servers manually

## 📝 Logging

**Default: Disabled** - No logs are created to keep your system clean.

**To Enable Logging:**

1. Edit `python/dnsscanner_tui.py`
2. Uncomment the `logger.add()` section
3. Logs saved to `logs/dnsscanner_TIMESTAMP.log`

**Log Levels:**
- **DEBUG**: Detailed DNS query results, download progress
- **INFO**: Scan progress and statistics
- **WARNING**: Non-critical issues, retry attempts
- **ERROR**: Critical failures, download errors

## 🌍 Finding CIDR Lists

### Country IP Ranges

**IPv4**:
- https://www.ipdeny.com/ipblocks/data/aggregated/

**IPv6**:
- https://www.ipdeny.com/ipv6/ipaddresses/aggregated/

### Usage Example
```bash
# Download Iran IPv4 ranges
wget https://www.ipdeny.com/ipblocks/data/aggregated/ir-aggregated.zone -O iran-ipv4.cidrs

# Use in scanner
python dnsscanner_tui.py
# Then select iran-ipv4.cidrs in the file browser
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

### Development Setup
```bash
git clone https://github.com/xullexer/PYDNS-Scanner.git
cd PYDNS-Scanner/python
pip install -r requirements.txt
python dnsscanner_tui.py
```

## 📄 License

This project is licensed under the MIT License.

## 👨‍💻 Author

- GitHub: [@xullexer](https://github.com/xullexer)

## 🙏 Acknowledgments

- Built with [Textual](https://github.com/Textualize/textual) by Textualize
- DNS resolution via [aiodns](https://github.com/saghul/aiodns)
- Inspired by the need for efficient DNS server discovery

## 📈 Performance Notes

Tested performance on various systems:

- **Small scan** (1,000 IPs): ~10-30 seconds
- **Medium scan** (50,000 IPs): ~5-10 minutes
- **Large scan** (1M+ IPs): ~1-3 hours

*Results vary based on network speed, concurrency settings, and system resources.*

## 🔐 Security Considerations

- Uses cryptographically secure random number generator (`secrets.SystemRandom`)
- No credentials or sensitive data are logged
- DNS queries are standard UDP/TCP port 53
- Slipstream proxy testing is optional and disabled by default

## 💝 Support the Project

If you find this project useful, consider supporting its development:

### Cryptocurrency Donations

- **Bitcoin (BTC)**  
  `bc1qpya0kc2uh0mc08c7nuzrqkpsqjr36mrwscgpxr`

- **Solana (SOL)**  
  `J1XzZfizQ6mgYiyxpLGWU52kHBF1hm2Tb9AZ5FaRj8tH`

- **Ethereum (ETH)**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **Binance Smart Chain (BNB/BSC)**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **Tron (TRX)**  
  `TYBZFr8WUsjgfrXrqmrdF5EXPXo7QdimA8`

- **Ethereum Base**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **TON (Telegram Open Network)**  
  `UQBcI_ZZGQq3fcNzTkL-zszgFR5HpRDLFHYRZffizriiScxJ`

---

**Happy Scanning! 🚀**
