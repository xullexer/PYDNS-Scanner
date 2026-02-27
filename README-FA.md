<div dir="rtl">

# اسکنر PYDNS

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
  <img src="https://img.shields.io/badge/Termux-%D8%B3%D8%A7%D8%B2%DA%AF%D8%A7%D8%B1-cyan?style=for-the-badge" alt="Termux">
</div>


<br>

<div align="center">
  🇺🇸 <a href="README.md"><b>English</b></a>
  &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  🇮🇷 <a href="README-FA.md"><b>فارسی</b></a>
  &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  🇨🇳 <a href="README-ZH.md"><b>中文</b></a>
</div>

<br>

<div align="center">
  <strong>یک اسکنر DNS مدرن و با کارایی بالا با رابط کاربری ترمینال (TUI) زیبا که با Textual ساخته شده است.</strong><br>
  این ابزار می‌تواند میلیون‌ها آدرس IP را اسکن کند تا سرورهای DNS فعال را پیدا کند، با قابلیت تست پروکسی Slipstream و دانلود خودکار چندپلتفرمی.<br>
  <br>
  <strong>🆕 نسخه ۱.۴.۰: ستون Resolved IP، مرتب‌سازی هوشمند چند کلیدی، رفع تست پروکسی و بهبودهای کارایی!</strong>
</div>

## 🎉 تازه‌های نسخه ۱.۴.۰

### 🎨 منوی شروع طراحی‌شده از نو
- **رابط کاربری بهتر** — صفحه پیکربندی کاملاً بازطراحی شده با چیدمان تمیزتر و سلسله‌مراتب بصری بهبودیافته
- **پنل لاگ اختیاری** — خروجی لاگ به‌صورت پیش‌فرض مخفی است؛ در هر زمان حین اسکن کلید `L` را بزنید تا آن را فعال یا غیرفعال کنید

### 🗂️ سه حالت اسکن
هر سه حالت از منطق اسکن یکسانی استفاده می‌کنند. تفاوت تنها در تعداد IP خوانده‌شده از فایل CIDR و آستانه shuffle است: اگر در این تعداد IP متوالی هیچ DNS فعالی یافت نشود، محدوده باقی‌مانده خودکار shuffle می‌شود تا سرورهای پنهان در زیرشبکه‌های بزرگ از دست نروند.
- **Quick Scan (اسکن سریع)** — حداکثر **۲۵‌۰۰۰ IP**، آستانه shuffle هر **۵۰۰ IP**
- **Deep Scan (اسکن عمیق)** — حداکثر **۵۰‌۰۰۰ IP**، آستانه shuffle هر **۱‌۰۰۰ IP**
- **Full Scan (اسکن کامل)** — تعداد IP **نامحدود** (کل فایل)، آستانه shuffle هر **۳‌۰۰۰ IP**

### 🔐 تست امنیتی
- **تشخیص Hijack** — تشخیص می‌دهد آیا سرور DNS درخواست‌ها را رهگیری یا تغییر مسیر می‌دهد
- **تشخیص Filtered** — سرورهایی که دامنه‌های خاص را بی‌صدا بلاک می‌کنند شناسایی می‌شوند
- **بررسی Open Resolver** — سرورهایی که پرس‌وجوهای خارجی دلخواه را resolve می‌کنند علامت‌گذاری می‌شوند
- **اعتبارسنجی DNSSEC** — گزارش می‌دهد آیا سرور پاسخ‌های امضاشده (DNSSEC) برمی‌گرداند

### 🌐 ستون‌های تحلیل شبکه
- **Resolved IP** — هر سرور DNS کاندیدا برای resolve کردن `google.com` استفاده می‌شود و IP نتیجه در جدول نمایش داده می‌شود
- **تشخیص ISP** — شماره AS و نام سازمان از طریق ip-api.com (محدودشده، ناهمزمان)
- **تشخیص IPv4/IPv6** — نشان می‌دهد سرور روی IPv4، IPv6 یا هر دو پاسخ می‌دهد
- **تشخیص EDNS0** — پشتیبانی از افزونه EDNS0 را تست و نمایش می‌دهد
- **ستون TCP/UDP** — انتقال‌های پشتیبانی‌شده را تست و نمایش می‌دهد

### 🔌 Slipstream Rust Plus — تست پروکسی بهبودیافته
- **ارتقا به کلاینت Slipstream Rust Plus** — باینری‌های سریع‌تر در همه پلتفرم‌ها
- **تونل HTTPS CONNECT** — تست پروکسی اکنون از `https://www.google.com` با HTTP CONNECT استفاده می‌کند؛ پروب HTTP ساده قبلی همیشه «Failed» برمی‌گرداند
- **تست SOCKS5 مستقل** — SOCKS5 جداگانه تست می‌شود، نه فقط به‌عنوان پشتیبان
- **حذف نتایج false-positive** — اعتبارسنجی بهبودیافته اشتباهات را حذف می‌کند
- **مرتب‌سازی هوشمند چند کلیدی** — موفقیت پروکسی → DNSSEC → سریع‌ترین پینگ

### 🗃️ بازطراحی جدول نتایج
- **چیدمان ستون جدید** — ستون پورت حذف شد؛ ترتیب: Ping → [Proxy] → IPv4/IPv6 → Security → TCP/UDP → EDNS0 → Resolved IP → ISP
- **شمارنده‌های زنده Pass/Fail** — نوار آمار در طول کل اسکن به‌درستی به‌روز می‌شود

### 🐛 رفع باگ
- **انتخاب CIDR سفارشی** — باگی که هنگام انتخاب فایل محدوده IP سفارشی در منوی اسکن اعمال نمی‌شد رفع شد
- **رفع باگ زیرشبکه /31 و /32** — IP‌های این زیرشبکه‌ها قبلاً بی‌صدا رد می‌شدند
- **رفع قفل ISP** — قفل rate-limit قبل از sleep آزاد می‌شود تا از توقف pipeline جلوگیری شود

### ⚡ بهبودهای عملکرد و ماژول‌ها
- **`google-re2`** — کتابخانه `re` با موتور RE2 گوگل جایگزین شد برای regex سریع‌تر و ایمن‌تر
- **Resolver اختصاصی برای هر تست** — از قفل شدن C-ares جلوگیری می‌کند
- **Shuffle بر پایه محدوده** — حساب عددی جایگزین `list(subnet.hosts())` برای CIDR‌های بزرگ
- **محدودکننده نرخ ISP** — درخواست‌های ip-api.com محدود + retry خودکار برای خطای 429
- **هشدار سوکت ویندوز** — هنگام تجاوز همزمانی از ۶۴ سوکت هشدار داده می‌شود

## ✨ ویژگی‌ها

- 🎨 **منوی شروع بازطراحی‌شده** — صفحه پیکربندی مدرن و تمیز
- 🗂️ **سه حالت اسکن** — Quick (حداکثر ۲۵ک، آستانه ۵۰۰)، Deep (حداکثر ۵۰ک، آستانه ۱ک)، Full (نامحدود، آستانه ۳ک) — منطق یکسان، مقیاس متفاوت
- 🔄 **Auto-Shuffle هوشمند** — اگر در آستانه تعریف‌شده هیچ DNS فعالی یافت نشود، محدوده باقی‌مانده خودکار shuffle می‌شود
- 🔐 **تست امنیتی** — Hijack، Filtered، Open Resolver و DNSSEC
- 🌐 **ستون Resolved IP** — هر سرور DNS با resolve `google.com` تست می‌شود
- 📡 **تشخیص ISP** — شماره AS و نام سازمان
- 🌍 **تشخیص IPv4/IPv6** — نسخه‌های IP پشتیبانی‌شده
- 📶 **تشخیص EDNS0** — پشتیبانی از افزونه EDNS0
- 🔌 **Slipstream Rust Plus** — تست پروکسی سریع‌تر با رفع false-positive و تست مستقل SOCKS5
- 🧮 **مرتب‌سازی هوشمند** — موفقیت پروکسی → DNSSEC → پینگ
- ⚡ **کارایی بالا** — اسکن غیرهمزمان با قابلیت تنظیم همزمانی
- ⏸️ **توقف/ادامه/تصادفی‌سازی** — کنترل کامل اسکن
- 📊 **آمار زنده** — شمارنده‌های Pass/Fail/Found در طول اسکن
- 🔍 **تشخیص هوشمند DNS** — سرورهای DNS فعال حتی با NXDOMAIN/NODATA
- 🎲 **زیردامنه تصادفی** — جلوگیری از پاسخ‌های کش‌شده
- 🌐 **انواع DNS متعدد** — A، AAAA، MX، TXT، NS
- 📝 **پنل لاگ اختیاری** — پیش‌فرض مخفی؛ کلید `L` برای نمایش/پنهان
- 🌍 **دانلود خودکار چندپلتفرمی** — کلاینت Slipstream مناسب برای پلتفرم شما
- 📥 **ادامه دانلود** — ادامه هوشمند در صورت قطع شبکه
- 💾 **ذخیره خودکار نتایج** — خروجی CSV با جزئیات هر سرور
- 📁 **مدیریت CIDR** — IP‌های ایران داخلی + انتخابگر فایل سفارشی (باگ برطرف شده)
- ⚙️ **قابل تنظیم** — همزمانی، زمان انتظار و فیلترها
- 🚀 **کم‌مصرف** — تولید IP جریانی بدون بارگذاری در حافظه
- 🚄 **google-re2** — موتور RE2 گوگل برای regex سریع‌تر
- 🔔 **هشدارهای صوتی** — صدای اختیاری هنگام تست موفق پروکسی

## 📋 پیش‌نیازها

### نسخه پایتون
- پایتون ۳.۱۱ یا بالاتر

### وابستگی‌ها

```bash
# وابستگی‌های اصلی (همیشه نصب می‌شوند — روی همه پلتفرم‌ها از جمله Android/Termux کار می‌کنند)
textual>=0.47.0       # فریمورک TUI
aiodns>=3.1.0         # حل‌کننده DNS غیرهمزمان
httpx[socks]>=0.25.0  # کلاینت HTTP با پشتیبانی SOCKS5 برای تست پروکسی
loguru>=0.7.0         # لاگ پیشرفته

# اکستراهای اختیاری "full" (pip install pydns-scanner[full]) — فقط دسکتاپ
google-re2>=1.0       # موتور regex سریع RE2 (به re استاندارد جایگزین می‌شود)
orjson>=3.9.0         # سریالایز سریع JSON (به json استاندارد جایگزین می‌شود)
pyperclip>=1.8.0      # پشتیبانی کلیپ‌بورد (در صورت نبود غیرفعال می‌شود)
```

### اختیاری
- **کلاینت Slipstream** - برای قابلیت تست پروکسی (۵ تست همزمان)
  - **دانلود خودکار**: برنامه به صورت خودکار پلتفرم شما را تشخیص داده و کلاینت مناسب را دانلود می‌کند
  - **تشخیص هوشمند**: تشخیص نصب‌های موجود (شامل نام‌های قدیمی)
  - **پشتیبانی از ادامه**: دانلودهای ناقص ذخیره شده و در تلاش مجدد ادامه می‌یابند
  - پلتفرم‌های پشتیبانی شده:
    - Linux (x86_64): `slipstream-client-linux-amd64`
    - Linux (ARM64): `slipstream-client-linux-arm64`
    - Windows (x86_64): `slipstream-client-windows-amd64.exe`
    - macOS (ARM64): `slipstream-client-darwin-arm64`
    - macOS (Intel): `slipstream-client-darwin-amd64`
    - Android (ARM64): `slipstream-client-linux-arm64`
  - دانلود دستی از: [انتشارات slipstream-rust-plus-deploy](https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest)

### 📦 کلاینت‌های Slipstream همراه

باینری‌های کامپایل‌شده کلاینت Slipstream (از مخزن سریع‌تر [Fox-Fig/slipstream-rust-plus-deploy](https://github.com/Fox-Fig/slipstream-rust-plus-deploy)) برای همه پلتفرم‌ها در پوشه `slipstream-client/` موجود است:

| پلتفرم | مسیر | توضیحات |
|--------|------|----------|
| **Linux x86_64** | `slipstream-client/linux/slipstream-client-linux-amd64` | باینری لینوکس x86_64 |
| **Linux ARM64** | `slipstream-client/linux/slipstream-client-linux-arm64` | باینری لینوکس ARM64 (رزبری پای، سرورهای ARM) |
| **Android/Termux** | `slipstream-client/android/slipstream-client-linux-arm64` | اندروید ARM64 (سازگار با Termux) |
| **Windows** | `slipstream-client/windows/slipstream-client-windows-amd64.exe` | فایل اجرایی ویندوز x86_64 |
| **macOS ARM** | `slipstream-client/mac/slipstream-client-darwin-arm64` | مک با تراشه اپل سیلیکون (M1/M2/M3/M4) |
| **macOS Intel** | `slipstream-client/mac/slipstream-client-darwin-amd64` | مک با پردازنده اینتل x86_64 |

> **⚠️ نکته ویندوز:** کلاینت ویندوز به فایل‌های DLL اپن‌اس‌اس‌ال (`libcrypto-3-x64.dll` و `libssl-3-x64.dll`) نیاز دارد که در پوشه `slipstream-client/windows/` قرار داده شده‌اند. در صورت استفاده از دانلود خودکار، این فایل‌ها به صورت خودکار همراه با فایل اجرایی ویندوز دانلود می‌شوند.

#### 📥 آرشیوهای همه‌در‌یک

برای راحتی، آرشیوهای فشرده شامل باینری همه پلتفرم‌ها موجود است:

- **`slipstream-client/slipstream-client-all-platforms.tar.gz`** - بهترین فشرده‌سازی (توصیه شده)
- **`slipstream-client/slipstream-client-all-platforms.zip`** - فرمت سازگار با ویندوز

این آرشیوها شامل کلاینت‌های لینوکس، ویندوز و مک در یک دانلود هستند.

## 🚀 نصب

### روش ۱: نصب از PyPI (توصیه شده)

ساده‌ترین روش نصب PYDNS Scanner:

#### استفاده از pip
```bash
pip install pydns-scanner
```

#### دسکتاپ — اکستراهای کامل (regex سریع‌تر، کلیپ‌بورد، JSON سریع)
```bash
pip install pydns-scanner[full]
```

#### استفاده از uv (سریع‌تر)
```bash
uv pip install pydns-scanner        # هسته اصلی
uv pip install pydns-scanner[full]   # اکستراهای دسکتاپ
```

#### Android / Termux
```bash
pkg update && pkg install python
pip install pydns-scanner            # فقط هسته اصلی — همیشه روی Termux کار می‌کند
pydns-scanner
```

> **نکته:** روی Android/Termux بسته‌های اختیاری C-extension (`google-re2`، `orjson`، `pyperclip`) به‌طور خودکار رد می‌شوند
> — اسکنر بدون هیچ دخالت دستی به معادل‌های استاندارد جایگزین می‌شود.

#### استفاده از میرور (برای کاربران با دسترسی محدود به PyPI)
```bash
# میرور Runflare
pip install pydns-scanner -i https://mirror-pypi.runflare.com/simple/ --trusted-host mirror-pypi.runflare.com

# یا میرور Alibaba Cloud
pip install pydns-scanner -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# یا میرور TUNA
pip install pydns-scanner -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### اجرا پس از نصب
```bash
pydns-scanner
```

---

### روش ۲: اجرا از سورس کد (دستی)

اگر می‌خواهید کد را مستقیماً از مخزن اجرا کنید:

#### مرحله ۱: کلون کردن مخزن
```bash
git clone https://github.com/xullexer/PYDNS-Scanner.git
cd PYDNS-Scanner
```

#### مرحله ۲: نصب وابستگی‌ها

**استفاده از uv (توصیه شده - سریع!)**
```bash
uv pip install -r requirements.txt
```

**استفاده از pip**
```bash
pip install -r requirements.txt
```

**استفاده از میرور (برای کاربران با دسترسی محدود به PyPI)**
```bash
# میرور Runflare
pip install -r requirements.txt -i https://mirror-pypi.runflare.com/simple/ --trusted-host mirror-pypi.runflare.com

# یا میرور Alibaba Cloud
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# یا میرور TUNA
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### مرحله ۳: اجرای برنامه
```bash
python -m python
```

---

## 🎮 استفاده

### استفاده پایه

**از PyPI:**
```bash
pydns-scanner
```

**از سورس کد:**
```bash
python -m python
```

این دستور رابط کاربری TUI تعاملی را راه‌اندازی می‌کند که می‌توانید تنظیم کنید:
- **فایل CIDR**: مسیر فایل حاوی محدوده IP‌ها (نشانه‌گذاری CIDR)
- **دامنه**: دامنه برای پرس‌وجو (مثلاً google.com)
- **نوع DNS**: نوع رکورد (A، AAAA، MX، TXT، NS)
- **همزمانی**: تعداد کارگران موازی (پیش‌فرض: ۱۰۰)
- **زیردامنه تصادفی**: اضافه کردن پیشوند تصادفی برای جلوگیری از پاسخ‌های کش شده
- **تست Slipstream**: فعال‌سازی تست پروکسی برای سرورهای DNS یافت شده

### فرمت فایل CIDR

یک فایل متنی با یک محدوده CIDR در هر خط ایجاد کنید:

```
# نظرات با # شروع می‌شوند
1.1.1.0/24
8.8.8.0/24
178.22.122.0/24
185.51.200.0/22
```

### گردش کار نمونه

۱. **راه‌اندازی برنامه**:
   ```bash
   python dnsscanner_tui.py
   ```

۲. **تنظیم پارامترهای اسکن**:
   - روی "📂 Browse" کلیک کنید تا فایل CIDR خود را انتخاب کنید
   - دامنه را وارد کنید (مثلاً `google.com`)
   - همزمانی را تنظیم کنید (توصیه: ۱۰۰-۵۰۰)
   - گزینه‌های مورد نیاز را فعال کنید

۳. **شروع اسکن**:
   - روی "🚀 Start Scan" کلیک کنید
   - پیشرفت و نتایج را به صورت زنده مشاهده کنید
   - از "⏸ Pause" برای توقف اسکن در هر زمان استفاده کنید
   - از "▶ Resume" برای ادامه از جایی که متوقف شدید استفاده کنید

۴. **مشاهده نتایج**:
   - مرتب شده بر اساس زمان پاسخ (سریع‌ترین اول)
   - سبز = سریع (<100ms)
   - زرد = متوسط (100-300ms)
   - قرمز = کند (>300ms)

۵. **ذخیره نتایج**:
   - نتایج به صورت خودکار در `results/TIMESTAMP.csv` ذخیره می‌شوند
   - `c` را فشار دهید یا روی "💾 Save Results" کلیک کنید برای ذخیره دستی

## ⌨️ میانبرهای صفحه‌کلید

| کلید | کِی | عملکرد |
|------|-----|--------|
| `s` | صفحه تنظیمات | شروع اسکن |
| `q` | همیشه | خروج از برنامه |
| `c` | هنگام اسکن | ذخیره نتایج |
| `p` | هنگام اسکن | توقف اسکن |
| `l` | هنگام اسکن | نمایش/پنهان پنل لاگ |
| `r` | وقتی متوقف شده | ادامه اسکن |
| `x` | وقتی متوقف شده | تصادفی‌سازی |

## 🎮 دکمه‌های کنترل

در حین اسکن فعال:
- **⏸ Pause** - توقف اسکن بدون از دست دادن پیشرفت
- **▶ Resume** - ادامه اسکن از جایی که متوقف شدید
- **💾 Save Results** - ذخیره دستی نتایج فعلی
- **🛑 Quit** - خروج از برنامه

## 🎛️ پیکربندی

### تنظیمات همزمانی

بر اساس سیستم و شبکه خود تنظیم کنید:

- **کم (50-100)**: محافظه‌کارانه، مناسب برای سیستم‌های کندتر
- **متوسط (100-300)**: عملکرد متعادل
- **بالا (300-500)**: اسکن سریع، نیاز به سخت‌افزار خوب
- **خیلی بالا (500+)**: حداکثر سرعت، ممکن است به محدودیت منابع برسد

### تنظیمات تست Slipstream

اسکنر از تست پروکسی Slipstream موازی با دانلود خودکار پشتیبانی می‌کند:

```python
# در متد __init__
self.slipstream_max_concurrent = 5  # حداکثر تست‌های پروکسی موازی
self.slipstream_base_port = 10800   # پورت پایه (استفاده از 10800، 10801، 10802)
```

## 📊 فرمت خروجی

نتایج در **فرمت CSV** ذخیره می‌شوند (`results/TIMESTAMP.csv`). ستون‌ها بر اساس تست‌های فعال تغییر می‌کنند:

```csv
DNS,Ping (ms),IPv4/IPv6,TCP/UDP,Security,EDNS0,Resolved IP,ISP
8.8.8.8,12,IPv4/IPv6,TCP+UDP,DNSSEC,Yes,142.250.185.46,AS15169 Google LLC
1.1.1.1,15,IPv4/IPv6,TCP+UDP,DNSSEC,Yes,142.250.185.46,AS13335 Cloudflare Inc
```

ستون‌های اختیاری (**Proxy Test**، **Security**، **EDNS0**) فقط در صورت فعال بودن تست مربوطه در تنظیمات درج می‌شوند.

## 🔍 نحوه کار

### منطق تشخیص DNS

اسکنر یک سرور را به عنوان "DNS فعال" در نظر می‌گیرد اگر:

۱. **پاسخ موفق**: پاسخ DNS معتبر در کمتر از ۲ ثانیه برگرداند
۲. **پاسخ‌های خطای DNS**: NXDOMAIN، NODATA یا NXRRSET در کمتر از ۲ ثانیه برگرداند
   - این خطاها به معنای این است که سرور DNS کار می‌کند، فقط رکورد وجود ندارد

این رویکرد سرورهای DNS فعال بیشتری را نسبت به ابزارهایی که فقط پاسخ‌های موفق را قبول می‌کنند، تشخیص می‌دهد.

### بهینه‌سازی‌های عملکرد

- **تولید IP جریانی**: IP‌ها به صورت آنی از محدوده‌های CIDR تولید می‌شوند
- **پردازش دسته‌ای**: IP‌ها در دسته‌های ۵۰۰ تایی پردازش می‌شوند
- **I/O غیرهمزمان**: پرس‌وجوهای DNS غیرمسدودکننده با استفاده از aiodns
- **کنترل سمافور**: محدود کردن عملیات همزمان برای جلوگیری از اتمام منابع
- **نگاشت حافظه**: خواندن سریع فایل CIDR با استفاده از mmap در صورت امکان

## 🌍 یافتن لیست‌های CIDR

### محدوده IP کشورها

**IPv4**:
- https://www.ipdeny.com/ipblocks/data/aggregated/

**IPv6**:
- https://www.ipdeny.com/ipv6/ipaddresses/aggregated/

### مثال استفاده
```bash
# دانلود محدوده IPv4 ایران
wget https://www.ipdeny.com/ipblocks/data/aggregated/ir-aggregated.zone -O iran-ipv4.cidrs

# استفاده در اسکنر
python dnsscanner_tui.py
# سپس iran-ipv4.cidrs را در مرورگر فایل انتخاب کنید
```

## 🐛 رفع اشکال

### "No module named 'textual'"
```bash
pip install textual
```

### خطای "File not found"
- مطمئن شوید مسیر فایل CIDR صحیح است
- از مسیر مطلق یا مسیر نسبی از محل اسکریپت استفاده کنید
- از مرورگر فایل داخلی استفاده کنید (دکمه 📂 Browse)

### اسکن کند
- مقدار همزمانی را کاهش دهید
- پهنای باند شبکه را بررسی کنید
- تنظیمات زمان انتظار DNS را تأیید کنید

### دانلود Slipstream ناموفق
- **مشکلات شبکه**: برنامه به صورت خودکار تا ۵ بار با تأخیر نمایی تلاش مجدد می‌کند
- **ادامه**: دانلودهای ناقص به صورت فایل‌های `.partial` ذخیره می‌شوند - فقط دوباره اجرا کنید
- **دانلود دستی**: از [انتشارات slipstream-rust-plus-deploy](https://github.com/Fox-Fig/slipstream-rust-plus-deploy/releases/latest) دانلود کنید
- **بررسی لاگ‌ها**: لاگ را فعال کنید (بخش پیکربندی را ببینید) برای اطلاعات خطای دقیق
- **فایروال**: مطمئن شوید دسترسی به GitHub مجاز است

### تست‌های Slipstream ناموفق
- تأیید کنید که فایل اجرایی مجوزهای صحیح دارد (Linux/macOS: `chmod +x`)
- بررسی کنید که پورت‌های 10800-10802 در دسترس هستند
- لاگ‌ها را (اگر فعال است) در پوشه `logs/` بررسی کنید
- اتصال به سرورهای DNS را به صورت دستی تست کنید

## 🤝 مشارکت

مشارکت‌ها خوش‌آمد هستند! لطفاً در ارسال pull request یا باز کردن issue تردید نکنید.

### راه‌اندازی توسعه
```bash
git clone https://github.com/xullexer/PYDNS-Scanner.git
cd PYDNS-Scanner/python
pip install -r requirements.txt
python dnsscanner_tui.py
```

## 📄 مجوز

این پروژه تحت مجوز MIT منتشر شده است.

## 👨‍💻 نویسنده

- GitHub: [@xullexer](https://github.com/xullexer)

## 🙏 قدردانی

- ساخته شده با [Textual](https://github.com/Textualize/textual) توسط Textualize
- حل DNS از طریق [aiodns](https://github.com/saghul/aiodns)
- الهام گرفته از نیاز به کشف کارآمد سرور DNS

## 📈 یادداشت‌های عملکرد

عملکرد تست شده در سیستم‌های مختلف:

- **اسکن کوچک** (1,000 IP): ~۱۰-۳۰ ثانیه
- **اسکن متوسط** (50,000 IP): ~۵-۱۰ دقیقه
- **اسکن بزرگ** (1M+ IP): ~۱-۳ ساعت

*نتایج بر اساس سرعت شبکه، تنظیمات همزمانی و منابع سیستم متفاوت است.*

## 🔐 ملاحظات امنیتی

- استفاده از مولد اعداد تصادفی امن رمزنگاری (`secrets.SystemRandom`)
- هیچ اطلاعات اعتباری یا داده حساسی لاگ نمی‌شود
- پرس‌وجوهای DNS از پورت استاندارد UDP/TCP 53 هستند
- تست پروکسی Slipstream اختیاری است و به صورت پیش‌فرض غیرفعال است

## 💝 حمایت از پروژه

اگر این پروژه برای شما مفید است، از توسعه آن حمایت کنید:

### کمک مالی با ارزهای دیجیتال

- **بیت‌کوین (BTC)**  
  `bc1qpya0kc2uh0mc08c7nuzrqkpsqjr36mrwscgpxr`

- **سولانا (SOL)**  
  `J1XzZfizQ6mgYiyxpLGWU52kHBF1hm2Tb9AZ5FaRj8tH`

- **اتریوم (ETH)**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **بایننس اسمارت چین (BNB/BSC)**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **ترون (TRX)**  
  `TYBZFr8WUsjgfrXrqmrdF5EXPXo7QdimA8`

- **اتریوم بیس (Ethereum Base)**  
  `0x26D9924B88e71b5908d957EA4c74C66989c253cb`

- **تلگرام اوپن نتورک (TON)**  
  `UQBcI_ZZGQq3fcNzTkL-zszgFR5HpRDLFHYRZffizriiScxJ`

---

</div>
