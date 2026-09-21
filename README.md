# BSB/CHSB Test Tekshiruvchi Bot + Web Admin Panel

O‘qituvchilar uchun BSB/CHSB testlarini avtomatik tekshiruvchi Telegram bot va boshqaruv paneli.

**Muhim qoida:** Gemini faqat fayldagi javoblarni o‘qiydi. Testni o‘zi yechmaydi. Solishtirish va hisob-kitob Python tomonidan bajariladi.

---

## Texnologiyalar

- Python 3.12+
- aiogram 3.x (Telegram bot)
- FastAPI (Admin API + panel)
- SQLAlchemy + PostgreSQL
- Google Gemini API (Files API)
- PyMuPDF, openpyxl

---

## Windows 11 da 0 dan o‘rnatish

### 1. Python o‘rnatish

1. https://www.python.org/downloads/ dan Python 3.12 yoki undan yuqori versiyani yuklab oling.
2. O‘rnatishda **"Add python.exe to PATH"** ni belgilang.
3. Tekshirish:

```cmd
python --version
```

### 2. PostgreSQL o‘rnatish

1. https://www.postgresql.org/download/windows/ dan PostgreSQL 16 yuklab oling.
2. O‘rnatishda `postgres` foydalanuvchisi uchun parol belgilang (eslab qoling).
3. pgAdmin yoki psql orqali database yarating:

```sql
CREATE DATABASE bsb_checker;
```

Yoki cmd da:

```cmd
psql -U postgres
CREATE DATABASE bsb_checker;
\q
```

### 3. Loyihani yuklab olish / papkaga o‘tish

```cmd
cd C:\path\to\bsb_checker
```

### 4. Virtual environment yaratish

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 5. Kutubxonalarni o‘rnatish

```cmd
pip install -r requirements.txt
```

### 6. .env fayl yaratish

`.env.example` ni nusxa qiling:

```cmd
copy .env.example .env
```

`.env` ni Notepad da ochib to‘ldiring:

```env
BOT_TOKEN=123456:ABC-DEF...
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-1.5-flash
DATABASE_URL=postgresql+asyncpg://postgres:SIZNING_PAROL@localhost:5432/bsb_checker
ADMIN_USERNAME=admin
ADMIN_PASSWORD=kuchli_parol_yozing
JWT_SECRET=kamida_32_belgidan_iborat_maxfiy_kalit
```

### 7. Telegram bot token olish

1. Telegramda [@BotFather](https://t.me/BotFather) ga `/newbot` yuboring.
2. Bot nomi va username bering.
3. Berilgan tokenni `.env` dagi `BOT_TOKEN` ga yozing.

### 8. Gemini API key olish

1. https://aistudio.google.com/apikey ga kiring.
2. API key yarating.
3. `.env` dagi `GEMINI_API_KEY` ga yozing.

### 9. Botni ishga tushirish

Yangi terminal (venv aktiv):

```cmd
cd C:\path\to\bsb_checker
.venv\Scripts\activate
python -m bot.bot
```

### 10. Admin panelni ishga tushirish

Yana bir terminal:

```cmd
cd C:\path\to\bsb_checker
.venv\Scripts\activate
python -m backend.main
```

Brauzerda: http://localhost:8000/admin

Login: `.env` dagi `ADMIN_USERNAME` / `ADMIN_PASSWORD`

---

## Loyiha strukturasi

```
bsb_checker/
├── bot/                 # Telegram bot
│   ├── bot.py
│   ├── handlers/
│   ├── keyboards/
│   └── middlewares/
├── backend/             # FastAPI
│   ├── main.py
│   ├── api/
│   └── admin/
├── database/            # SQLAlchemy models
├── services/            # Gemini, PDF, Checker, Excel, Payment
├── admin_panel/         # HTML/CSS/JS
├── uploads/
├── temp/
├── .env
├── requirements.txt
└── README.md
```

---

## Asosiy ish jarayoni

1. O‘qituvchi `/start` → **➕ Yangi test** (fan, sinf, nomi, savollar, BSB/CHSB)
2. **📋 Javoblar kaliti** — TXT/PDF/rasm yuboradi → Gemini o‘qiydi → JSON saqlanadi
3. **📄 O‘quvchilar javoblari** — PDF/rasm → sahifalar bo‘linadi → Gemini faqat belgilarni o‘qiydi
4. Python answer key bilan solishtiradi → to‘g‘ri/noto‘g‘ri/noaniq
5. **📊 Natijalar** + **📥 Excel**

---

## Premium

| Tarif   | Kunlik PDF |
|---------|------------|
| Oddiy   | 3          |
| Premium | 6 (30 kun, 35 000 so‘m) |

To‘lov providerini `.env` da sozlash mumkin. Hozircha provider yo‘q bo‘lsa, admin panel orqali Premium qo‘lda beriladi.

---

## Xavfsizlik

- Barcha maxfiy kalitlar `.env` da
- Admin paroli bcrypt hash
- JWT autentifikatsiya
- Foydalanuvchilar faqat o‘z testlarini ko‘radi
- Vaqtinchalik fayllar ishlatilgandan keyin o‘chiriladi

---

## Muammolar

**Database ulanmayapti:** `DATABASE_URL` va PostgreSQL ishlayotganini tekshiring.

**Gemini xato:** API key va internetni tekshiring. Rate limit bo‘lsa biroz kuting.

**Bot javob bermayapti:** Token to‘g‘riligini va `python -m bot.bot` ishlayotganini tekshiring.

---

## Vercel ga deploy qilish

> **Muhim cheklov:** Vercel serverless funksiyasi **qisqa timeout** ga ega (Hobby ~10s, Pro ~60s).  
> Katta PDF (60–90 sahifa) tekshiruvi timeoutga tushishi mumkin.  
> Admin panel + kichik testlar uchun mos. Katta PDF uchun **Railway / Render / VPS** tavsiya etiladi.

### 1. Kerakli narsalar

- [Vercel](https://vercel.com) akkaunt
- [Neon](https://neon.tech) yoki boshqa **cloud PostgreSQL** (Vercel ichida DB yo‘q)
- Bot token, Gemini API key

### 2. PostgreSQL (Neon)

1. neon.tech da project yarating  
2. Connection string oling (async uchun):  
   `postgresql+asyncpg://user:pass@host/db?ssl=require`

### 3. Vercel Environment Variables

Vercel Dashboard → Project → Settings → Environment Variables:

```
BOT_TOKEN=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash
DATABASE_URL=postgresql+asyncpg://...
ADMIN_USERNAME=admin
ADMIN_PASSWORD=...
JWT_SECRET=uzun_random_kalit
WEBHOOK_URL=https://SIZNING-LOYIHA.vercel.app
WEBHOOK_SECRET=ixtiyoriy_maxfiy_soz
```

### 4. Deploy

```cmd
cd bsb_checker
npm i -g vercel
vercel login
vercel
```

Yoki GitHub ga push qilib Vercel da Import qiling.

### 5. Webhook

Deploy dan keyin `WEBHOOK_URL` to‘g‘ri bo‘lsa, ilova ishga tushganda bot webhook ni o‘zi o‘rnatadi:

`https://SIZNING-LOYIHA.vercel.app/api/telegram/webhook`

Tekshirish: https://SIZNING-LOYIHA.vercel.app/api/health

### 6. Lokal polling (Vercel siz)

Katta PDF va barqaror ish uchun lokal yoki VPS:

```cmd
python -m bot.bot
python -m backend.main
```

Polling rejimida webhook kerak emas.
