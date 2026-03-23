import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv


load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher with FSM storage
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# Import handlers (will be created in next phases)
from handlers.start import router as start_router
from handlers.registration import router as registration_router
from handlers.test import router as test_router

async def main():
    """Main function to start the bot"""
    logger.info("Starting DTM Bot...")

    # Use polling mode (reliable for development)
    try:
        logger.info("Starting polling mode...")

        # Register handlers
        dp.include_router(start_router)
        dp.include_router(test_router)  # ← avval
        dp.include_router(registration_router)  # ← keyin

        # Start polling
        logger.info("Bot started successfully! Polling for updates...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

    except Exception as e:
        logger.error(f"Bot startup error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())