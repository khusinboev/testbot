"""
bots/testbot/config.py

Bu bot uchun xos sozlamalar.
Umumiy sozlamalar uchun loyiha ildizidagi config.py ga qarang.

Yangi bot yaratishda faqat shu faylni va handlers/ ni o'zgartirish yetarli.
"""

import os

# Bot tokeni (.env dan olinadi)
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Redis (FSM uchun)
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Bot nomi (log va xabarlarda ko'rinadi)
BOT_NAME: str = "DTM Test Bot"
BOT_VERSION: str = "2.0"
