# DTM Test Bot

DTM (O'zbekiston davlat test imtihoni) tayyorgarlik uchun Telegram boti.

## Loyiha tuzilmasi

```
test-bot/
├── bot/                    # Telegram bot
│   ├── handlers/
│   │   ├── registration.py # Asosiy handlerlar (ro'yxat, test, reyting)
│   │   ├── inline.py       # Inline qidiruv
│   │   ├── start.py        # /help va boshqa buyruqlar
│   │   └── test.py         # (stub fayl)
│   ├── keyboards.py
│   ├── main.py
│   └── states.py
│
├── admin/                  # Web admin panel (Flask)
│   ├── app.py
│   ├── routes_extra.py     # Kanallar va broadcast
│   └── templates/
│
├── database/               # Baza modellari va ulanish
│   ├── models.py
│   ├── db.py
│   ├── regions.json        # Viloyatlar ma'lumotlari
│   └── districts.json      # Tumanlar ma'lumotlari
│
├── utils/                  # Yordamchi modullar
│   ├── channel_service.py  # Kanal obuna tekshiruvi
│   ├── excel_parser.py     # Excel yo'nalishlar parser
│   ├── locks.py            # User lock/throttle
│   ├── scheduler.py        # APScheduler (avtomatik yakunlash)
│   └── test_service.py     # Test logikasi (asosiy)
│
├── scripts/
│   └── manage.py           # BARCHA baza amallari bitta joyda
│
├── data/
│   └── Fanlar_majmuasi_2025-2026.xlsx  ← Excel faylni shu yerga qo'ying
│
├── config.py
├── .env
└── requirements.txt
```

## O'rnatish

### 1. Muhit sozlash

```bash
pip install -r requirements.txt
cp .env.example .env
# .env faylida BOT_TOKEN va DATABASE_URL ni to'ldiring
```

### 2. Baza yaratish

```bash
# Yangi baza (barcha jadvallar + asosiy ma'lumotlar)
python scripts/manage.py init

# Savollarni qo'shish (init dan keyin)
python scripts/manage.py seed

# Holat tekshirish
python scripts/manage.py status
```

### 3. Excel yo'nalishlar fayli

`data/` papkasiga quyidagi faylni qo'ying:
```
data/Fanlar_majmuasi_2025-2026.xlsx
```

Fayl bo'lmasa 5 ta namuna yo'nalish bilan ishlaydi.

### 4. Ishga tushirish

**Bot:**
```bash
python -m bot.main
```

**Admin panel:**
```bash
python -m admin.app
# http://localhost:5000
```

## Mavjud baza migration

Eski bazani saqlab yangi ustunlar qo'shish uchun:
```bash
python scripts/manage.py migrate
```

## manage.py buyruqlari

| Buyruq    | Ta'rif                                        |
|-----------|-----------------------------------------------|
| `init`    | Jadvallar yaratish + asosiy ma'lumotlar       |
| `reset`   | Bazani o'chirib qayta yaratish (EHTIYOT!)     |
| `seed`    | Savollarni qo'shish (`--force` bilan qayta)  |
| `migrate` | Mavjud bazaga yangi ustunlar qo'shish         |
| `status`  | Baza holatini ko'rish                         |

## Texnologiyalar

- Python 3.8+, Aiogram 3.x, SQLAlchemy, PostgreSQL
- Flask + Flask-Login (admin panel)
- APScheduler (vaqt tugagan testlarni avtomatik yakunlash)
- Redis (ixtiyoriy, FSM storage uchun)