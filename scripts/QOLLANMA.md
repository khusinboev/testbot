# DTM Test Bot — To'liq qo'llanma
## scripts/QOLLANMA.md

---

## 📁 Loyiha tuzilmasi

```
test-bot/
├── bot/                        # Telegram bot
│   ├── handlers/
│   │   ├── registration.py     # Asosiy: /start, test, reyting, profil, referal
│   │   ├── inline.py           # Inline yo'nalish qidiruvi
│   │   ├── start.py            # /help buyrug'i
│   │   └── test.py             # Stub (barcha test handleri registration.py da)
│   ├── keyboards.py            # Barcha klaviaturalar
│   ├── main.py                 # Bot ishga tushirish nuqtasi
│   └── states.py               # FSM holatlari
│
├── admin/                      # Web admin panel (Flask)
│   ├── app.py                  # Flask ilovasi + asosiy routelar
│   ├── routes_extra.py         # Qo'shimcha: yo'nalishlar, referal, kanallar, broadcast
│   └── templates/              # HTML shablonlar
│
├── database/
│   ├── models.py               # Barcha SQLAlchemy modellari
│   ├── db.py                   # Engine, Session, seed funksiyalar
│   ├── regions.json            # Viloyatlar ma'lumotlari
│   └── districts.json          # Tumanlar ma'lumotlari
│
├── utils/
│   ├── channel_service.py      # Kanal obuna tekshiruvi
│   ├── excel_parser.py         # Excel yo'nalishlar parser  [TUZATILDI]
│   ├── locks.py                # User lock/throttle
│   ├── referral_service.py     # Referal tizimi logikasi
│   ├── scheduler.py            # APScheduler (vaqt tugagan testlar)
│   └── test_service.py         # Test logikasi (asosiy)
│
├── scripts/
│   ├── manage.py               # ← SHU FAYL: barcha baza amallari  [TUZATILDI]
│   └── QOLLANMA.md             # ← SHU QOLLANMA
│
├── data/
│   └── Fanlar_majmuasi_2025-2026.xlsx   ← Excel faylni shu yerga qo'ying
│
├── config.py
├── .env                        # .env.example dan nusxa oling
├── env.example                 # Namuna muhit o'zgaruvchilari
└── requirements.txt
```

---

## bazalarni o'chirib qaytadan tiklash to'ldirish uchun

```bash
# 1. Bazani to'liq o'chirib qayta yaratish
python scripts/manage.py reset
# "yes" deb tasdiqlang

# 2. Savollarni qo'shish (300 ta namuna)
python scripts/manage.py seed

# 3. Holat tekshirish
python scripts/manage.py status
```

---

## 🚀 Yangi loyiha — boshlash (birinchi marta)

### 1. Repozitoriyni klonlash / ko'chirish

```bash
cd /path/to/your/projects
git clone <repo_url> test-testbot
cd test-testbot
```

### 2. Virtual muhit (ixtiyoriy, tavsiya etiladi)

```bash
python -m venv venv
source venv/bin/activate          # Linux/Mac
# yoki
venv\Scripts\activate             # Windows
```

### 3. Paketlarni o'rnatish

```bash
pip install -r requirements.txt
```

### 4. Muhit o'zgaruvchilarini sozlash

```bash
cp .env.example .env
nano .env    # yoki istalgan text muharrir
```

`.env` faylini to'ldiring:

```env
# Telegram Bot tokeni — @BotFather dan oling
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Admin Telegram ID lari (vergul bilan)
ADMIN_IDS=123456789,987654321

# PostgreSQL ulanish
# Format: postgresql://foydalanuvchi:parol@host:port/baza_nomi
DATABASE_URL=postgresql://dtm_user:strong_password@localhost:5432/dtm_bot

# Redis (ixtiyoriy, bot ko'p userli bo'lsa tavsiya)
REDIS_URL=redis://localhost:6379/0

# Flask admin panel
SECRET_KEY=bu_yerga_kamida_32_ta_belgi_kiriting_random
FLASK_ENV=production
FLASK_DEBUG=False

# Admin panel login (O'ZGARTIRING!)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=kuchli_parol_kiriting
```

### 5. PostgreSQL baza yaratish

```bash
# PostgreSQL ga kirish
psql -U postgres

-- Baza va foydalanuvchi yaratish
CREATE USER dtm_user WITH PASSWORD 'strong_password';
CREATE DATABASE dtm_bot OWNER dtm_user;
GRANT ALL PRIVILEGES ON DATABASE dtm_bot TO dtm_user;
\q
```

### 6. Excel fayl (ixtiyoriy lekin tavsiya)

```bash
mkdir -p data
# Fanlar_majmuasi_2025-2026.xlsx faylini data/ ga ko'chiring
cp /path/to/Fanlar_majmuasi_2025-2026.xlsx data/
```

Fayl bo'lmasa ham ishlaydi — 5 ta namuna yo'nalish bilan.

### 7. Bazani ishga tushirish

```bash
# Muhitni tekshirish (ixtiyoriy)
python scripts/manage.py check

# Bazani yaratish va asosiy ma'lumotlarni qo'shish
python scripts/manage.py init

# Savollarni qo'shish (300 ta namuna savol)
python scripts/manage.py seed

# Holat tekshirish
python scripts/manage.py status
```

### 8. Ishga tushirish

**Terminal 1 — Bot:**
```bash
python -m testbot.main
```

**Terminal 2 — Admin panel:**
```bash
python -m admin.app
# Brauzerda: http://localhost:5000
# Login: admin / dtm_admin_2025 (yoki .env dagi qiymat)
```

---

## 🔄 Mavjud bazani yangilash (migrate)

Eski loyihadan yangi versiyaga o'tganda:

```bash
# Yangi ustunlar va jadvallar qo'shish (ma'lumotlar saqlanadi)
python scripts/manage.py migrate
```

Nima qo'shiladi:
- `scores`: `is_archived`, `attempted_count`, `participation_id`
- `user_test_participation`: `deadline_at`, `snapshot_*` ustunlar
- `users`: `is_blocked`, `language`
- Yangi jadvallar: `mandatory_channels`, `broadcast_messages`,
  `referral_settings`, `referral_links`, `referral_invites`
- Leaderboard duplikatlarini tozalash

---

## 📋 manage.py buyruqlari

| Buyruq    | Tavsif                                              | Flag      |
|-----------|-----------------------------------------------------|-----------|
| `check`   | Muhit, paketlar, DB ulanishini tekshirish           |           |
| `init`    | Jadvallar + admin + fanlar + viloyatlar + yo'nalishlar + referal seed | `--force` |
| `seed`    | 300 ta namuna savol qo'shish                        | `--force` |
| `migrate` | Mavjud bazaga yangi ustun/jadvallar (ma'lumot saqlanadi) |      |
| `status`  | Baza statistikasini ko'rish                         |           |
| `reset`   | BARCHA ma'lumotni o'chirib qayta boshlash ⚠️        |           |

**`--force` flagi:** mavjud ma'lumotlarni o'chirib qayta yozadi.

```bash
python scripts/manage.py init --force    # hamma seedni qayta yoz
python scripts/manage.py seed --force   # savollarni qayta yoz
```

---

## 🗃️ Baza modellari (jadvallar)

```
regions              — Viloyatlar
districts            — Tumanlar
directions           — Ta'lim yo'nalishlari
subjects             — Fanlar (10 ta)
questions            — Savollar bazasi
users                — Foydalanuvchilar
admins               — Adminlar
test_sessions        — Test sessiyalar (kunlik)
user_test_participation — Testga qatnashish
user_answers         — Javoblar
scores               — Natijalar (is_archived tizimi bilan)
leaderboard          — Reyting (daily/weekly/all_time)
mandatory_channels   — Majburiy obuna kanallar
broadcast_messages   — Broadcast tarixi
referral_settings    — Referal sozlamalari (id=1, bitta qator)
referral_links       — Har user uchun referal kod
referral_invites     — Kim kimni taklif qilgani
```

---

## ⚙️ Asosiy konfiguratsiya (config.py)

```python
TEST_DURATION_MINUTES = 180          # Test muddati (daqiqa)
MANDATORY_QUESTIONS_PER_SUBJECT = 10 # Majburiy fanlardan savol soni
SPECIALIZED_QUESTIONS_PER_SUBJECT = 30 # Ixtisoslashgan fanlardan

MANDATORY_SUBJECT_IDS = [1, 5, 6]   # Matematika, Tarix, Ona tili
MANDATORY_POINTS_PER_QUESTION = 1.1  # Majburiy fan ballar
SPECIALIZED_HIGH_POINTS = 3.1        # 1-ixtisoslashgan fan
SPECIALIZED_LOW_POINTS = 2.1         # 2-ixtisoslashgan fan
```

Test tuzilmasi (jami 90 savol):
```
Matematika    10 × 1.1 = 11.0 max ball
Ona tili      10 × 1.1 = 11.0 max ball
Tarix         10 × 1.1 = 11.0 max ball
1-asosiy fan  30 × 3.1 = 93.0 max ball
2-asosiy fan  30 × 2.1 = 63.0 max ball
─────────────────────────────────────
JAMI          90 savol  189.0 max ball
```

---

## 🔧 Xato va yechimlar

### PostgreSQL ulanmayapti
```bash
# Ubuntu/Debian
sudo systemctl start postgresql
sudo systemctl enable postgresql

# ulanishni tekshirish
psql -U dtm_user -d dtm_bot -h localhost
```

### Redis ulanmayapti
Bot Redis siz ham ishlaydi (MemoryStorage), lekin server restart qilganda
FSM holatlari o'chadi. Ko'p userli botda Redis tavsiya etiladi:
```bash
sudo apt install redis-server
sudo systemctl start redis
```

### "alembic revision" xatosi
Bu loyihada Alembic ishlatilmaydi.
Barcha migrationlar `manage.py migrate` orqali amalga oshiriladi.

### "Table already exists"
```bash
# Xavfsiz — mavjud jadvallar o'zgarmaydi, faqat yo'qlari yaratiladi
python scripts/manage.py init
```

### Savollar yetarli emas (test tugamaydi)
Har bir fandan kamida 30 ta savol bo'lishi kerak (1-2-asosiy fanlar uchun).
Majburiy fanlar (Matematika=1, Tarix=5, Ona tili=6) uchun kamida 10 ta.

```bash
# Excel dan import qilish — admin panel → /questions → Import
# Yoki namuna savollarni qayta yozish:
python scripts/manage.py seed --force
```

### Admin panelga kira olmayapti
```bash
# .env ni tekshiring
cat .env | grep ADMIN

# Default (agar .env da yo'q):
# ADMIN_USERNAME=admin
# ADMIN_PASSWORD=dtm_admin_2025
```

---

## 📤 Savollarni Excel orqali import qilish

Admin panel → **Savollar** → **Import** tugmasi.

Excel fayl formati (ustunlar tartibi):
```
A: Savol matni
B: Variant A
C: Variant B
D: Variant C
E: Variant D
F: To'g'ri javob (A, B, C yoki D)
```
- 1-qator sarlavha (e'tiborsiz qoldiriladi)
- 2-qatordan savollar boshlanadi

---

## 🌐 Deployment (serverga joylashtirish)

### Systemd xizmati (Linux)

**Bot uchun** `/etc/systemd/system/dtm-bot.service`:
```ini
[Unit]
Description=DTM Telegram Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/test-bot
ExecStart=/var/www/test-bot/venv/bin/python -m bot.main
Restart=always
RestartSec=5
EnvironmentFile=/var/www/test-bot/.env

[Install]
WantedBy=multi-user.target
```

**Admin panel uchun** `/etc/systemd/system/dtm-admin.service`:
```ini
[Unit]
Description=DTM Admin Panel
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/test-bot
ExecStart=/var/www/test-bot/venv/bin/gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --timeout 60 \
    "admin.app:app"
Restart=always
RestartSec=5
EnvironmentFile=/var/www/test-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable dtm-testbot dtm-admin
sudo systemctl start dtm-testbot dtm-admin

# Holat tekshirish
sudo systemctl status dtm-testbot
sudo journalctl -u dtm-testbot -f
```

### Docker (ixtiyoriy)

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "bot.main"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  bot:
    build: .
    env_file: .env
    depends_on: [postgres, redis]
    restart: unless-stopped

  admin:
    build: .
    command: python -m admin.app
    ports: ["5000:5000"]
    env_file: .env
    depends_on: [postgres]
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: dtm_bot
      POSTGRES_USER: dtm_user
      POSTGRES_PASSWORD: strong_password
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    restart: unless-stopped

volumes:
  postgres_data:
```

```bash
docker-compose up -d
docker-compose exec testbot python scripts/manage.py init
docker-compose exec testbot python scripts/manage.py seed
```

---

## 📌 Muhim eslatmalar

1. **Kunlik cheklov**: Har bir foydalanuvchi kuniga faqat 1 marta test yecha oladi.

2. **Arxiv tizimi**: Foydalanuvchi bir yo'nalishda qayta test yechganda
   eski natijasi `is_archived=True` ga o'tadi. Reyting faqat joriy
   (arxivlanmagan) natijalarni ko'rsatadi.

3. **Vaqt tugashi**: APScheduler har 60 soniyada vaqti o'tgan testlarni
   avtomatik yakunlaydi va foydalanuvchiga natijani yuboradi.

4. **Referal tizimi**: Admin paneldan yoqiladi/o'chiriladi.
   `required_count=0` bo'lsa — talab yo'q, faqat statistika.

5. **Kanal obunasi**: Majburiy kanallarni admin panel → Kanallar sahifasida
   boshqarish mumkin. Bot o'sha kanalda **admin** bo'lishi shart.

6. **Excel yo'nalishlar**: `data/Fanlar_majmuasi_2025-2026.xlsx` — bu fayl
   bo'lmasa 5 ta namuna yo'nalish bilan ishlaydi. Real loyihada bu faylni
   qo'yish tavsiya etiladi.
