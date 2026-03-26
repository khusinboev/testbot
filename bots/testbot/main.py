"""
bots/testbot/main.py

Bot ishga tushirish nuqtasi.
Barcha routerlar shu yerda ulanadi — tartib muhim!
"""
import asyncio
import logging
import os
import sys

# Loyiha ildizini sys.path ga qo'shish
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Avval bot-specific .env, keyin global .env
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
load_dotenv(os.path.join(ROOT, '.env'))

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
REDIS_URL  = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_storage():
    try:
        from aiogram.fsm.storage.redis import RedisStorage
        storage = RedisStorage.from_url(REDIS_URL)
        logger.info("✅ RedisStorage ulandi: %s", REDIS_URL)
        return storage
    except Exception as e:
        logger.warning("⚠️  Redis ulanmadi (%s) — MemoryStorage ishlatiladi", e)
        from aiogram.fsm.storage.memory import MemoryStorage
        return MemoryStorage()


if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN topilmadi! .env faylini tekshiring.")
    sys.exit(1)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = get_storage()
dp      = Dispatcher(storage=storage)


async def main():
    logger.info("DTM Test Bot ishga tushmoqda...")
    try:
        # ── Routerlarni import qilish ──────────────────────────────────────
        from bots.testbot.handlers.registration import router as registration_router
        from bots.testbot.handlers.gates        import router as gates_router
        from bots.testbot.handlers.test         import router as test_router
        from bots.testbot.handlers.direction    import router as direction_router
        from bots.testbot.handlers.profile      import router as profile_router
        from bots.testbot.handlers.inline       import router as inline_router
        from bots.testbot.handlers.start        import router as start_router

        # ── Router ulanish TARTIBI muhim! ──────────────────────────────────
        # 1. Registration — /start va FSM ro'yxatdan o'tish (eng birinchi)
        dp.include_router(registration_router)

        # 2. Gates — kanal obuna va referal tekshiruvi callback lari
        dp.include_router(gates_router)

        # 3. Test oqimi — test boshlash, javob berish, yakunlash
        dp.include_router(test_router)

        # 4. Yo'nalish tanlash — test va profil ichida ishlaydi
        dp.include_router(direction_router)

        # 5. Profil, natijalar, reyting, referal, yordam
        dp.include_router(profile_router)

        # 6. Inline qidiruv — yo'nalish qidirish
        dp.include_router(inline_router)

        # 7. /help — oxirida (umumiy handler)
        dp.include_router(start_router)

        # ── Scheduler ishga tushirish ──────────────────────────────────────
        from utils.scheduler import init_scheduler
        init_scheduler(bot)

        logger.info("✅ Barcha %d ta router ulandi", 7)
        logger.info("✅ Bot muvaffaqiyatli ishga tushdi!")

        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
    except Exception as e:
        logger.error("Bot xatosi: %s", e)
        raise
    finally:
        from utils.scheduler import stop_scheduler
        stop_scheduler()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())