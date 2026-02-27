## 🎉 What's New / چه چیزی جدید شده / 更新内容

**Jump to:** [🇬🇧 English](#-english) · [🇮🇷 فارسی](#-فارسی) · [🇨🇳 中文](#-中文)

---

### 🇬🇧 English

#### 🚀 v1.4.1

**🤖 Android / Termux Compatibility**
- ✅ **Platform-aware imports** — `google-re2` and `pyperclip` are automatically skipped on Android/Termux; falls back to stdlib `re` and a no-op clipboard wrapper respectively
- ✅ **Zero crash on Termux** — App now launches cleanly on Termux without any manual package removal

**🐛 Bug Fix**
- 🔎 **Resolved IP column** — Previously always resolved `google.com` regardless of the configured scan domain; now correctly resolves the domain entered in the scan configuration

---

#### 🚀 v1.4.0

**🎨 Redesigned Start Menu**
- ✅ Completely redesigned configuration screen with cleaner layout and improved visual hierarchy
- ✅ Optional log panel — hidden by default; press `L` during scan to toggle on/off

**🗂️ Three Scan Modes**
All three modes use the same scanning logic. The differences are the maximum number of IPs read from the CIDR file and the **shuffle step**: if no working DNS is found within that many consecutive IPs, the remaining range reshuffles automatically so servers spread across a large subnet are not missed.
- 🚀 **Quick Scan** — up to **25,000 IPs**, shuffle step every **500** IPs
- 🔍 **Deep Scan** — up to **50,000 IPs**, shuffle step every **1,000** IPs
- 🔬 **Full Scan** — **unlimited IPs** (entire file), shuffle step every **3,000** IPs

**🔐 Security Testing**
- 🚨 **Hijack detection** — Detects if the server intercepts or redirects queries
- 🚫 **Filtered detection** — Identifies servers that silently block certain domains
- 🌍 **Open resolver check** — Flags servers that resolve arbitrary external queries
- 🔒 **DNSSEC validation** — Reports whether the server returns signed (DNSSEC) responses

**🌐 Network Analysis Columns**
- 🔎 **Resolved IP** — Each candidate DNS server resolves `google.com`; the resulting IP is shown in the results table
- 📡 **ISP detection** — AS number and organisation name per server via ip-api.com (rate-limited, async)
- 🌍 **IPv4 / IPv6 detection** — Shows which IP versions each server supports
- 📶 **EDNS0 detection** — Tests and displays EDNS0 extension support
- 🔀 **TCP / UDP column** — Tests and shows supported transports

**🔌 Slipstream Rust Plus — Improved Proxy Testing**
- ⬆️ **Upgraded to Slipstream Rust Plus client** — significantly faster binaries across all platforms
- ✅ **HTTPS CONNECT tunnel** — Proxy test now targets `https://www.google.com` via HTTP CONNECT; previous plain-HTTP probe always returned "Failed"
- ✅ **Independent SOCKS5 test** — SOCKS5 tested on its own, not just as a fallback
- ✅ **False-positive elimination** — Improved result validation removes incorrect pass/fail results
- 🧮 **Smart multi-key sort** — Results sorted: Proxy pass → DNSSEC → fastest ping

**🗃️ Results Table Overhaul**
- 📐 **New column layout** — Port column removed; order: Ping → [Proxy] → IPv4/IPv6 → Security → TCP/UDP → EDNS0 → Resolved IP → ISP
- 📊 **Live pass/fail counters** — Statistics bar updates correctly throughout the scan
- 💾 **CSV output** — Results saved as `TIMESTAMP.csv`; columns adapt to enabled tests (Proxy Test, Security, EDNS0 columns included only when enabled)

**🐛 Bug Fixes**
- 📁 **Custom CIDR selection** — Fixed bug where selecting a custom IP range file was not applied correctly in the scan menu
- 🔢 **/31 and /32 subnet fix** — IPs from these subnets were previously silently skipped
- 🔓 **ISP lock hang** — Rate-limit lock released before sleeping, eliminating pipeline stalls

**⚡ Performance & Module Improvements**
- 🚄 **`google-re2`** — Replaced Python stdlib `re` with Google's RE2 engine for faster, safer regex
- 🔁 **Per-test aiodns resolver** — Each DNS test creates its own resolver, preventing C-ares concurrency hangs
- 📐 **Range-based IP shuffle** — Integer arithmetic replaces `list(subnet.hosts())` for large CIDR ranges
- 🚦 **ISP rate limiter** — ip-api.com capped with async lock + automatic 429 retry with 60 s backoff
- ⚠️ **Windows socket advisory** — Warning logged when concurrency exceeds 64 (Windows selector event-loop cap)

---

### 🇮🇷 فارسی

#### 🚀 نسخه ۱.۴.۱

**🤖 سازگاری با Android / Termux**
- ✅ **وارد کردن وابسته به پلتفرم** — `google-re2` و `pyperclip` روی Android/Termux به‌طور خودکار رد می‌شوند؛ به ترتیب به `re` استاندارد و یک wrapper بی‌عمل جایگزین می‌شوند
- ✅ **بدون crash در Termux** — اپلیکیشن اکنون بدون نیاز به حذف دستی هیچ بسته‌ای در Termux اجرا می‌شود

**🐛 رفع باگ**
- 🔎 **ستون Resolved IP** — قبلاً بدون توجه به دامنه پیکربندی‌شده همیشه `google.com` را resolve می‌کرد؛ اکنون دامنه وارد‌شده در تنظیمات اسکن به‌درستی resolve می‌شود

---

#### 🚀 نسخه ۱.۴.۰

**🎨 منوی شروع طراحی‌شده از نو**
- ✅ صفحه پیکربندی کاملاً بازطراحی شده با چیدمان تمیزتر و سلسله‌مراتب بصری بهبودیافته
- ✅ پنل لاگ اختیاری — پیش‌فرض پنهان است؛ کلید `L` را حین اسکن بزنید تا آن را روشن یا خاموش کنید

**🗂️ سه حالت اسکن**
هر سه حالت از منطق اسکن یکسانی استفاده می‌کنند. تفاوت تنها در تعداد IP خوانده‌شده از فایل CIDR و **آستانه shuffle** است: اگر در این تعداد IP متوالی هیچ DNS فعالی یافت نشود، محدوده باقی‌مانده خودکار shuffle می‌شود.
- 🚀 **Quick Scan (اسکن سریع)** — حداکثر 25,000 IP، آستانه shuffle هر 500 IP
- 🔍 **Deep Scan (اسکن عمیق)** — حداکثر 50,000 IP، آستانه shuffle هر 1,000 IP
- 🔬 **Full Scan (اسکن کامل)** — تعداد IP نامحدود (کل فایل)، آستانه shuffle هر 3,000 IP

**🔐 تست امنیتی**
- 🚨 **تشخیص Hijack** — آیا سرور DNS درخواست‌ها را رهگیری یا تغییر مسیر می‌دهد
- 🚫 **تشخیص Filtered** — سرورهایی که دامنه‌های خاص را بی‌صدا بلاک می‌کنند
- 🌍 **بررسی Open Resolver** — سرورهایی که پرس‌وجوهای خارجی دلخواه را resolve می‌کنند
- 🔒 **اعتبارسنجی DNSSEC** — آیا سرور پاسخ‌های امضاشده برمی‌گرداند

**🌐 ستون‌های تحلیل شبکه**
- 🔎 **Resolved IP** — هر سرور DNS کاندیدا برای resolve کردن `google.com` استفاده می‌شود و IP نتیجه در جدول نمایش می‌یابد
- 📡 **تشخیص ISP** — شماره AS و نام سازمان از طریق ip-api.com (محدودشده، ناهمزمان)
- 🌍 **تشخیص IPv4/IPv6** — سرور روی IPv4، IPv6 یا هر دو پاسخ می‌دهد
- 📶 **تشخیص EDNS0** — پشتیبانی از افزونه EDNS0 تست و نمایش داده می‌شود
- 🔀 **ستون TCP/UDP** — انتقال‌های پشتیبانی‌شده تست و نمایش داده می‌شوند

**🔌 Slipstream Rust Plus — تست پروکسی بهبودیافته**
- ⬆️ **ارتقا به کلاینت Slipstream Rust Plus** — باینری‌های سریع‌تر در همه پلتفرم‌ها
- ✅ **تونل HTTPS CONNECT** — تست پروکسی از `https://www.google.com` با HTTP CONNECT استفاده می‌کند؛ پروب HTTP ساده قبلی همیشه «Failed» برمی‌گرداند
- ✅ **تست SOCKS5 مستقل** — SOCKS5 جداگانه تست می‌شود
- ✅ **حذف نتایج false-positive** — اعتبارسنجی بهبودیافته اشتباهات را برطرف می‌کند
- 🧮 **مرتب‌سازی هوشمند چند کلیدی** — موفقیت پروکسی → DNSSEC → سریع‌ترین پینگ

**🗃️ بازطراحی جدول نتایج**
- 📐 **چیدمان ستون جدید** — ستون پورت حذف شد؛ ترتیب: Ping → [Proxy] → IPv4/IPv6 → Security → TCP/UDP → EDNS0 → Resolved IP → ISP
- 📊 **شمارنده‌های زنده Pass/Fail** — نوار آمار در طول کل اسکن به‌درستی به‌روز می‌شود
- 💾 **خروجی CSV** — نتایج به صورت `TIMESTAMP.csv` ذخیره می‌شوند؛ ستون‌ها با تست‌های فعال تطبیق می‌یابند

**🐛 رفع باگ**
- 📁 **انتخاب CIDR سفارشی** — باگی که هنگام انتخاب فایل محدوده IP سفارشی اعمال نمی‌شد رفع شد
- 🔢 **رفع باگ زیرشبکه /31 و /32** — IP‌های این زیرشبکه‌ها قبلاً بی‌صدا رد می‌شدند
- 🔓 **رفع قفل ISP** — قفل rate-limit قبل از sleep آزاد می‌شود تا از توقف pipeline جلوگیری شود

**⚡ بهبودهای عملکرد و ماژول‌ها**
- 🚄 **`google-re2`** — کتابخانه `re` با موتور RE2 گوگل جایگزین شد برای regex سریع‌تر و ایمن‌تر
- 🔁 **Resolver اختصاصی برای هر تست** — از قفل شدن C-ares جلوگیری می‌کند
- 📐 **Shuffle بر پایه محدوده** — حساب عددی جایگزین `list(subnet.hosts())` برای CIDR‌های بزرگ
- 🚦 **محدودکننده نرخ ISP** — درخواست‌های ip-api.com محدود + retry خودکار برای خطای 429
- ⚠️ **هشدار سوکت ویندوز** — هنگام تجاوز همزمانی از ۶۴ سوکت هشدار داده می‌شود

---

### 🇨🇳 中文

#### 🚀 v1.4.1

**🤖 Android / Termux 兼容性**
- ✅ **平台感知导入** — 在 Android/Termux 上自动跳过 `google-re2` 和 `pyperclip`；分别回退至标准库 `re` 和空操作剪贴板包装器
- ✅ **Termux 零崩溃** — 无需手动删除任何包，应用现可在 Termux 上正常启动

**🐛 缺陷修复**
- 🔎 **已解析 IP 列** — 此前无论配置的扫描域名是什么，始终解析 `google.com`；现已正确解析扫描配置中输入的域名

---

#### 🚀 v1.4.0

**🎨 重新设计的启动菜单**
- ✅ 配置界面全面重新设计，布局更简洁，视觉层次更清晰
- ✅ 可选日志面板 — 默认隐藏；扫描期间按 `L` 键切换显示/隐藏

**🗂️ 三种扫描模式**
三种模式使用完全相同的扫描逻辑，区别仅在于从 CIDR 文件中读取的最大 IP 数量及**混洗步长**：若在连续该数量的 IP 中未发现可用 DNS，则剩余范围将自动重新混洗，避免遗漏分散在大子网中的服务器。
- 🚀 **Quick Scan（快速扫描）** — 最多 **25,000 个 IP**，每 **500** 个 IP 混洗一次
- 🔍 **Deep Scan（深度扫描）** — 最多 **50,000 个 IP**，每 **1,000** 个 IP 混洗一次
- 🔬 **Full Scan（完整扫描）** — **不限 IP 数量**（整个文件），每 **3,000** 个 IP 混洗一次

**🔐 安全测试**
- 🚨 **劫持检测** — 检测 DNS 服务器是否拦截或重定向查询
- 🚫 **过滤检测** — 识别静默屏蔽特定域名的服务器
- 🌍 **开放解析器检查** — 标记解析任意外部查询的服务器
- 🔒 **DNSSEC 验证** — 报告服务器是否返回已签名（DNSSEC）的响应

**🌐 网络分析列**
- 🔎 **已解析 IP** — 每个候选 DNS 服务器解析 `google.com`，结果 IP 显示在结果表中
- 📡 **ISP 检测** — 通过 ip-api.com 获取每台服务器的 AS 号和组织名称（限速、异步）
- 🌍 **IPv4 / IPv6 检测** — 显示每台服务器支持的 IP 版本
- 📶 **EDNS0 检测** — 测试并显示 EDNS0 扩展支持情况
- 🔀 **TCP / UDP 列** — 测试并显示支持的传输协议

**🔌 Slipstream Rust Plus — 改进的代理测试**
- ⬆️ **升级至 Slipstream Rust Plus 客户端** — 所有平台二进制文件速度显著提升
- ✅ **HTTPS CONNECT 隧道** — 代理测试现通过 HTTP CONNECT 访问 `https://www.google.com`；旧版纯 HTTP 探测始终返回"Failed"
- ✅ **独立 SOCKS5 测试** — SOCKS5 单独测试，而非仅作为回退方案
- ✅ **消除误报** — 改进的结果验证去除错误的通过/失败结果
- 🧮 **智能多键排序** — 排序顺序：代理通过 → DNSSEC → 最快 ping

**🗃️ 结果表格全面升级**
- 📐 **新列布局** — 移除端口列；顺序：Ping → [Proxy] → IPv4/IPv6 → Security → TCP/UDP → EDNS0 → Resolved IP → ISP
- 📊 **实时通过/失败计数器** — 统计栏在整个扫描过程中正确更新
- 💾 **CSV 输出** — 结果保存为 `TIMESTAMP.csv`；列根据已启用的测试自动调整（仅在启用对应测试时包含 Proxy Test、Security、EDNS0 列）

**🐛 缺陷修复**
- 📁 **自定义 CIDR 选择** — 修复了在扫描菜单中选择自定义 IP 范围文件未正确应用的问题
- 🔢 **/31 和 /32 子网修复** — 此前这些子网的 IP 被静默跳过
- 🔓 **ISP 锁挂起修复** — 速率限制锁在休眠前释放，消除流水线停滞

**⚡ 性能与模块改进**
- 🚄 **`google-re2`** — 将 Python 标准库 `re` 替换为 Google RE2 引擎，正则处理更快更安全
- 🔁 **每次测试独立 aiodns 解析器** — 为每个 DNS 测试创建独立解析器，防止 C-ares 并发挂起
- 📐 **基于范围的 IP 混洗** — 对大 CIDR 范围使用整数运算替代 `list(subnet.hosts())`
- 🚦 **ISP 速率限制器** — ip-api.com 请求受异步锁限制 + 429 错误自动重试（60 秒退避）
- ⚠️ **Windows 套接字提示** — 并发数超过 64 时记录警告（Windows 选择器事件循环上限）

---

📦 **Install / نصب / 安装:**
```bash
pip install pydns-scanner --upgrade
```