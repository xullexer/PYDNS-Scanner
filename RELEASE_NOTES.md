## 🎉 What's New / چه چیزی جدید شده / 更新内容

**Jump to:** [🇬🇧 English](#-english) · [🇮🇷 فارسی](#-فارسی) · [🇨🇳 中文](#-中文)

---

### 🇬🇧 English

#### � v2.0.4

- 🐛 Fixed **crash on long-running scans** caused by file descriptor leak — subprocess pipe handles are now explicitly closed after each proxy test, preventing the Windows `select()` handle limit from being exceeded
- ✨ Added **Clear button** next to the SlipNet URL input for quick one-click reset
- ✨ Added **Minimum DNS Type Score** setting in the Advanced section — configure the minimum score (1–6) a DNS server must achieve before it qualifies for proxy testing (default: 4)
- ✨ Added **Proxy Test Try Number** setting in the Advanced section — set how many times (1–5) to retry the full proxy test (tunnel + HTTP) before marking a server as failed
- 🔧 **Improved proxy testing retry logic** — each retry now restarts the entire tunnel process from scratch rather than only retrying the HTTP request, giving timed-out servers a genuine second chance
- 🔧 Fixed default expected HTTP status code staying at **200** instead of being auto-overridden to 204 when using a `gen_204` test URL

#### �🔥 v2.0.3 Hotfix

- 🔧 Fixed **SlipNet config paste** in packaged TUI builds by adding reliable clipboard paste handling for input fields
- 🔧 Fixed **double-click copy** on result rows so it copies the actual **IP address** instead of the proxy-status column
- 🔧 Updated package / app version metadata for the `v2.0.3` release

#### 🚀 v2.0.0

**🌐 Three Scan Modes: Slipstream · SlipNet · DNS Scan**
- ✅ **Slipstream** — Classic proxy testing with SOCKS5 support
- ✅ **SlipNet** — Full SlipNet configs support for DNSTT and NoiseDNS tunnels with SOCKS5 / SSH authentication and auto-detected auth method
- ✅ **DNS Scan** — New lightweight scan mode: insert a domain, set concurrency, and scan — no proxy testing, no authentication. Tests security, DNS types, ping, resolved IP, EDNS0, and more

**🔀 New Scan Strategy — Bidirectional Multi-Range**
- ✅ Scanner now scans from the **start and end** of each IP range simultaneously across multiple ranges, combined with random shuffle — faster performance and higher chance of finding working DNS servers compared to linear scanning

**🧪 Auto DNS Type Check + Scoring**
- ✅ All DNS types (A, AAAA, MX, TXT, NS) are automatically tested and scored per server — same scoring system as the SlipNet scanner

**⚙️ New Advanced Section**
Fully customizable scanning parameters:
- 🔧 Minimum proxy ping threshold for proxy test
- 🔧 DNS connection timeout
- 🔧 Proxy end-to-end test timeout
- 🔧 Parallel proxy test count
- 🔧 Custom shuffle steps
- 🔧 Proxy test URL + expected response status code
- 🔧 Set MTU (experimental OS-level MTU override)
- 🔧 Query size for SlipNet (DNSTT / NoiseDNS)

**🎨 UX Improvements**
- ✅ Enhanced scan statistics display
- ✅ Improved result table writing and formatting
- ✅ New proxy test status UI with real-time feedback
- ✅ Better Filtered IP detection
- ✅ Log section is always visible (no longer toggleable)

**🔧 Experimental: Set OS MTU**
- ✅ Scan with a specified MTU value — experimental feature for advanced network tuning

**⚡ Performance**
- ✅ Significantly higher scan performance
- ✅ Auto detect auth method for SlipNet (DNSTT / NoiseDNS)

**⚙️ Bug Fixes**
- 🔧 Fixed UI freeze after scanning large DNS ranges
- 🔧 Fixed speed drop after 500K+ scanned IPs
- 🔧 Fixed memory leak during long-running scans
- 🔧 Updated dependencies to resolve Dependabot low-severity vulnerability alerts

**🙏 Acknowledgment**
- 👏 SlipNet client binaries bundled in this release are developed by [**anonvector**](https://github.com/anonvector) — thanks for building the **SlipNet CLI**

---

### 🇮🇷 فارسی

#### � نسخه ۲.۰.۴

- 🐛 رفع **کرش در اسکن‌های طولانی** ناشی از نشت file descriptor — هندل‌های pipe پس از هر تست پروکسی اکنون به صورت صریح بسته می‌شوند تا از رسیدن به محدودیت handle ویندوز جلوگیری شود
- ✨ افزودن **دکمه Clear** کنار فیلد URL SlipNet برای پاک‌سازی سریع با یک کلیک
- ✨ افزودن تنظیم **حداقل امتیاز DNS Type** در بخش Advanced — حداقل امتیاز لازم (۱ تا ۶) برای قرار گرفتن سرور DNS در صف تست پروکسی (پیش‌فرض: ۴)
- ✨ افزودن تنظیم **تعداد تلاش تست پروکسی** در بخش Advanced — تعداد دفعات تکرار (۱ تا ۵) کل تست پروکسی (تونل + HTTP) قبل از علامت‌گذاری به عنوان ناموفق
- 🔧 **بهبود منطق retry تست پروکسی** — هر بار تلاش مجدد، کل فرآیند تونل را از ابتدا شروع می‌کند نه اینکه فقط درخواست HTTP تکرار شود
- 🔧 رفع مشکل کد وضعیت HTTP پیش‌فرض که به اشتباه برای URL نوع `gen_204` به ۲۰۴ تغییر می‌کرد؛ اکنون مقدار **200** حفظ می‌شود

#### �🔥 نسخه ۲.۰.۳ هات‌فیکس

- 🔧 مشکل **پیست کردن تنظیمات SlipNet** در نسخه‌های بسته‌بندی‌شده TUI رفع شد و پشتیبانی مطمئن‌تری برای paste در فیلدهای ورودی اضافه شد
- 🔧 مشکل **کپی با دابل‌کلیک** در جدول نتایج رفع شد تا به‌جای ستون وضعیت پروکسی، خود **IP** کپی شود
- 🔧 نسخه برنامه و پکیج برای انتشار `v2.0.3` به‌روزرسانی شد

#### 🚀 نسخه ۲.۰.۰

**🌐 سه حالت اسکن: Slipstream · SlipNet · DNS Scan**
- ✅ **Slipstream** — تست پروکسی کلاسیک با پشتیبانی SOCKS5
- ✅ **SlipNet** — پشتیبانی کامل از تنظیمات SlipNet برای تونل‌های DNSTT و NoiseDNS با احراز هویت SOCKS5 / SSH و تشخیص خودکار روش احراز هویت
- ✅ **DNS Scan** — حالت اسکن سبک جدید: فقط دامنه را وارد کنید، همزمانی را تنظیم کنید و اسکن کنید — بدون تست پروکسی، بدون احراز هویت. امنیت، انواع DNS، پینگ، IP حل‌شده، EDNS0 و موارد بیشتر را تست می‌کند

**🔀 استراتژی اسکن جدید — دوطرفه چند محدوده‌ای**
- ✅ اسکنر اکنون همزمان از **ابتدا و انتهای** هر محدوده IP در چندین محدوده اسکن می‌کند، همراه با shuffle تصادفی — عملکرد سریع‌تر و شانس بیشتر برای یافتن سرورهای DNS فعال در مقایسه با اسکن خطی

**🧪 بررسی خودکار انواع DNS + امتیازدهی**
- ✅ تمام انواع DNS (A، AAAA، MX، TXT، NS) به صورت خودکار برای هر سرور تست و امتیازدهی می‌شوند — همان سیستم امتیازدهی اسکنر SlipNet

**⚙️ بخش پیشرفته جدید**
پارامترهای اسکن کاملاً قابل تنظیم:
- 🔧 حداقل آستانه پینگ پروکسی برای تست پروکسی
- 🔧 زمان انتظار اتصال DNS
- 🔧 زمان انتظار تست سرتاسری پروکسی
- 🔧 تعداد تست‌های پروکسی موازی
- 🔧 مراحل shuffle سفارشی
- 🔧 آدرس تست پروکسی + کد وضعیت پاسخ مورد انتظار
- 🔧 تنظیم MTU (تغییر آزمایشی MTU در سطح سیستم‌عامل)
- 🔧 اندازه پرس‌وجو برای SlipNet (DNSTT / NoiseDNS)

**🎨 بهبودهای UX**
- ✅ نمایش بهبودیافته آمار اسکن
- ✅ نوشتن و قالب‌بندی بهتر جدول نتایج
- ✅ رابط کاربری جدید وضعیت تست پروکسی با بازخورد زنده
- ✅ تشخیص بهتر IP فیلترشده
- ✅ بخش لاگ همیشه نمایان (دیگر قابل تغییر نیست)

**🔧 آزمایشی: تنظیم MTU سیستم‌عامل**
- ✅ اسکن با مقدار MTU مشخص — ویژگی آزمایشی برای تنظیم پیشرفته شبکه

**⚡ عملکرد**
- ✅ عملکرد اسکن به‌طور قابل توجهی بالاتر
- ✅ تشخیص خودکار روش احراز هویت برای SlipNet (DNSTT / NoiseDNS)

**⚙️ رفع باگ**
- 🔧 رفع فریز شدن رابط کاربری پس از اسکن محدوده‌های بزرگ DNS
- 🔧 رفع افت سرعت پس از اسکن بیش از ۵۰۰ هزار IP
- 🔧 رفع نشت حافظه در اسکن‌های طولانی
- 🔧 به‌روزرسانی وابستگی‌ها برای رفع هشدارهای آسیب‌پذیری کم‌شدت Dependabot

**🙏 قدردانی**
- 👏 باینری‌های کلاینت SlipNet موجود در این نسخه توسط [**anonvector**](https://github.com/anonvector) توسعه داده شده است — با تشکر برای ساخت **SlipNet CLI**

---

### 🇨🇳 中文

#### � v2.0.4

- 🐛 修复 **长时间扫描崩溃** 问题：子进程管道句柄现在在每次代理测试后被显式关闭，防止 Windows `select()` 句柄数量超限
- ✨ 在 SlipNet URL 输入框旁新增 **Clear（清除）按钮**，一键快速清空
- ✨ 在高级设置中新增 **最低 DNS 类型评分** 选项 — 设置 DNS 服务器参与代理测试所需的最低评分（1–6，默认值：4）
- ✨ 在高级设置中新增 **代理测试重试次数** 选项 — 设置将服务器标记为失败前的完整代理测试（隧道 + HTTP）重试次数（1–5）
- 🔧 **改进代理测试重试逻辑** — 每次重试都会从头重启完整隧道进程，而非仅重试 HTTP 请求，让超时的服务器获得真正的第二次机会
- 🔧 修复默认期望 HTTP 状态码在使用 `gen_204` 测试 URL 时被自动改为 204 的问题，现在默认保持 **200**

#### �🔥 v2.0.3 热修复

- 🔧 修复打包版 TUI 中 **SlipNet 配置无法粘贴** 的问题，为输入框增加更可靠的剪贴板粘贴处理
- 🔧 修复结果表中 **双击复制** 的问题，现会复制真实的 **IP 地址**，不再错误复制代理状态列
- 🔧 已同步更新 `v2.0.3` 的程序与包版本元数据

#### 🚀 v2.0.0

**🌐 三种扫描模式：Slipstream · SlipNet · DNS Scan**
- ✅ **Slipstream** — 经典代理测试，支持 SOCKS5
- ✅ **SlipNet** — 完整 SlipNet 配置支持：DNSTT 和 NoiseDNS 隧道，支持 SOCKS5 / SSH 认证及自动检测认证方式
- ✅ **DNS Scan** — 全新轻量级扫描模式：只需输入域名、设置并发数即可开始扫描 — 无需代理测试、无需认证。自动测试安全性、DNS 类型、延迟、解析 IP、EDNS0 等

**🔀 全新扫描策略 — 双向多范围扫描**
- ✅ 扫描器现从每个 IP 范围的**首尾两端**同时扫描，跨多个范围进行，结合随机混洗 — 与线性扫描相比，性能更快，发现可用 DNS 服务器的概率更高

**🧪 自动 DNS 类型检测 + 评分**
- ✅ 所有 DNS 类型（A、AAAA、MX、TXT、NS）自动测试并为每台服务器评分 — 与 SlipNet 扫描器相同的评分系统

**⚙️ 全新高级设置区**
完全可定制的扫描参数：
- 🔧 代理测试最低 ping 阈值
- 🔧 DNS 连接超时
- 🔧 代理端到端测试超时
- 🔧 并行代理测试数量
- 🔧 自定义混洗步长
- 🔧 代理测试 URL + 预期响应状态码
- 🔧 设置 MTU（实验性操作系统级 MTU 覆盖）
- 🔧 SlipNet 查询大小（DNSTT / NoiseDNS）

**🎨 用户体验改进**
- ✅ 增强的扫描统计显示
- ✅ 改进的结果表格书写与格式
- ✅ 全新代理测试状态界面，提供实时反馈
- ✅ 更好的过滤 IP 检测
- ✅ 日志区域始终可见（不再可切换）

**🔧 实验性功能：设置操作系统 MTU**
- ✅ 使用指定的 MTU 值进行扫描 — 用于高级网络调优的实验性功能

**⚡ 性能**
- ✅ 扫描性能大幅提升
- ✅ 自动检测 SlipNet 认证方式（DNSTT / NoiseDNS）

**⚙️ Bug 修复**
- 🔧 修复扫描大型 DNS 范围后 UI 冻结的问题
- 🔧 修复扫描超过 50 万个 IP 后速度下降的问题
- 🔧 修复长时间运行扫描时的内存泄漏
- 🔧 更新依赖以解决 Dependabot 低危漏洞警报

**🙏 致谢**
- 👏 本版本中包含的 SlipNet 客户端二进制文件由 [**anonvector**](https://github.com/anonvector) 开发 — 感谢其构建 **SlipNet CLI**

---

📦 **Install / نصب / 安装:**
```bash
pip install pydns-scanner --upgrade
```