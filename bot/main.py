import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)


async def main():
    logger.info("DTM Bot ishga tushmoqda...")
    try:
        from bot.handlers.start import router as start_router
        from bot.handlers.registration import router as registration_router
        from bot.handlers.test import router as test_router
        from bot.handlers.inline import router as inline_router

        dp.include_router(start_router)
        dp.include_router(test_router)
        dp.include_router(registration_router)
        dp.include_router(inline_router)

        logger.info("Bot muvaffaqiyatli ishga tushdi!")
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
    except Exception as e:
        logger.error(f"Bot xatosi: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())