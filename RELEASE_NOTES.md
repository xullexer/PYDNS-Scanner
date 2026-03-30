## 🎉 What's New / چه چیزی جدید شده / 更新内容

**Jump to:** [🇬🇧 English](#-english) · [🇮🇷 فارسی](#-فارسی) · [🇨🇳 中文](#-中文)

---

### 🇬🇧 English

#### 🔥 v2.0.5 Hotfix

- 🐛 Fixed **Minimum DNS Type Score setting not being applied** — a hardcoded threshold of 4 in the extra-tests safety net was overriding the user-configured value, causing DNS servers with scores 2–3 to be skipped even when the user set a lower minimum
- 🐛 Fixed **"too many file descriptors in select()" crash** — manually entered concurrency values now enforce the same hard cap (440) on Windows that auto-detection uses, preventing the `SelectorEventLoop` 512-fd `select()` limit from being exceeded

---

### 🇮🇷 فارسی

#### 🔥 نسخه ۲.۰.۵ هات‌فیکس

- 🐛 رفع مشکل **عدم اعمال تنظیم حداقل امتیاز DNS Type** — مقدار ثابت ۴ در بررسی ایمنی extra-tests مقدار تنظیم‌شده توسط کاربر را نادیده می‌گرفت و باعث رد شدن سرورهای DNS با امتیاز ۲ تا ۳ می‌شد حتی اگر کاربر حداقل کمتری تعیین کرده بود
- 🐛 رفع **کرش "too many file descriptors in select()"** — مقدار همزمانی وارد‌شده دستی اکنون همان محدودیت سقف (۴۴۰) روی ویندوز را اعمال می‌کند تا از رسیدن به محدودیت ۵۱۲ file descriptor در `SelectorEventLoop` جلوگیری شود

---

### 🇨🇳 中文

#### 🔥 v2.0.5 热修复

- 🐛 修复 **最低 DNS 类型评分设置未生效** 的问题 — extra-tests 安全检查中硬编码的阈值 4 覆盖了用户配置的值，导致评分为 2–3 的 DNS 服务器即使用户设置了更低的最低值仍被跳过
- 🐛 修复 **"too many file descriptors in select()" 崩溃** — 手动输入的并发值现在在 Windows 上强制执行与自动检测相同的上限（440），防止 `SelectorEventLoop` 的 512 文件描述符 `select()` 限制被超过

---

📦 **Install / نصب / 安装:**
```bash
pip install pydns-scanner --upgrade
```