import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
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


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = get_storage()
dp      = Dispatcher(storage=storage)


async def main():
    logger.info("DTM Bot ishga tushmoqda...")
    try:
        from bots.testbot.handlers.start import router as start_router
        from bots.testbot.handlers.registration import router as registration_router
        from bots.testbot.handlers.inline import router as inline_router

        # Tartibi muhim: registration avval (u ko'proq handler tutadi)
        dp.include_router(registration_router)
        dp.include_router(start_router)
        dp.include_router(inline_router)

        # Scheduler ishga tushirish
        from utils.scheduler import init_scheduler
        init_scheduler(bot)

        logger.info("Bot muvaffaqiyatli ishga tushdi!")
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


if __name__ == "__main__":
    asyncio.run(main())