# Yangi bot yaratish

## Arxitektura

```
loyiha/
├── database/        ← O'zgarmaydi
├── utils/           ← O'zgarmaydi
├── admin/           ← O'zgarmaydi
├── config.py        ← O'zgarmaydi
│
└── bots/
    ├── testbot/     ← Hozirgi bot (to'liq ishlaydi)
    └── mybot/       ← Yangi bot (shu papkani yarating)
```

## Qadamlar

### 1. Papka yarating

```bash
cp -r bots/testbot bots/mybot
```

### 2. Faqat shu fayllarni o'zgartiring

| Fayl | Nima o'zgaradi |
|------|----------------|
| `bots/mybot/config.py` | `BOT_TOKEN`, `BOT_NAME` |
| `bots/mybot/states.py` | Yangi bot uchun FSM holatlari |
| `bots/mybot/keyboards.py` | Yangi bot tugmalari |
| `bots/mybot/handlers/*.py` | Yangi bot handlerlari |
| `bots/mybot/main.py` | Router ulash tartibi |

### 3. Ishga tushiring

```bash
# testbot (avvalgisi o'zgarmaydi):
python -m bots.testbot.main

# yangi testbot:
python -m bots.mybot.main
```

### 4. .env da token sozlang

```env
# testbot uchun:
BOT_TOKEN=111:token_here

# Ko'p bot ishlatayotgan bo'lsangiz alohida env fayllar:
# bots/testbot/.env
# bots/mybot/.env
```

## Qaysi utils ishlatish mumkin

Yangi bot handlers ichida quyidagilarni import qilish mumkin:

```python
# Database
from database.db import Session
from database.models import User, Score, Direction  # va boshqalar

# Servislar
from utils.referral_service import check_referral_gate
from utils.channel_service  import subscription_gate
from utils.test_service     import TestService       # test logikasi
from utils.locks            import user_lock, throttle_check
```

Admin panel (`admin/`) ham ishlaydi — u database dan o'qiydi,
shuning uchun har ikkala bot ma'lumotlari ko'rinadi.

## Minimal bot namunasi

`bots/translatorbot/` yaratish uchun minimal tuzilma:

```
bots/translatorbot/
├── __init__.py
├── config.py      ← BOT_TOKEN, BOT_NAME = "Tarjimon Bot"
├── states.py      ← class TranslationStates(StatesGroup): ...
├── keyboards.py   ← get_language_keyboard() va boshqalar
├── handlers/
│   ├── __init__.py
│   ├── common.py  ← bot-specific yordamchilar
│   ├── start.py   ← /start, ro'yxatdan o'tish
│   └── translate.py ← asosiy funksiya
└── main.py        ← routerlarni ulash
```
