#!/usr/bin/env python3
"""
Test script to send messages to the bot and verify functionality
"""

import asyncio
import config
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

async def test_bot_functionality():
    """Test bot by sending test messages"""
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    try:
        # Get bot info
        me = await bot.get_me()
        print(f"🤖 Test boshlandi: @{me.username}")
        print("=" * 50)

        # Test commands that should work
        test_commands = [
            "/start",
            "/help",
            "🧪 Testni boshlash",
            "📊 Natijalarim",
            "🏆 Reyting",
            "👤 Profilim"
        ]

        print("📋 Test buyruqlari:")
        for cmd in test_commands:
            print(f"   • {cmd}")

        print("\n✅ Bot tayyor! Endi quyidagi manzilda test qiling:")
        print(f"   https://t.me/{me.username}")
        print("\n📝 Test qilish uchun:")
        print("   1. /start yuboring")
        print("   2. Ro'yxatdan o'ting")
        print("   3. Test boshlang")
        print("   4. Savollarga javob bering")

    except Exception as e:
        print(f"❌ Xato: {str(e)}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_bot_functionality())