"""
utils/scheduler.py
APScheduler bilan:
  - Har 60 sekunda: vaqti o'tgan testlarni avtomatik yakunlash
  - Bot instance shu scheduler orqali userga xabar yuboradi
"""
import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_bot_instance = None   # aiogram Bot ob'ekti


def init_scheduler(bot):
    """Bot ishga tushganda chaqiriladi."""
    global _scheduler, _bot_instance
    _bot_instance = bot
    _scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
    _scheduler.add_job(
        _auto_finish_expired_tests,
        trigger='interval',
        seconds=60,
        id='auto_finish_tests',
        replace_existing=True,
        misfire_grace_time=30,
    )
    _scheduler.start()
    logger.info("✅ Scheduler ishga tushdi (auto-finish har 60 sek)")


def stop_scheduler():
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler to'xtatildi")


async def _auto_finish_expired_tests():
    """Vaqti o'tgan active participationlarni yakunlaydi."""
    from utils.test_service import TestService
    try:
        expired = TestService.get_expired_participations()
        if not expired:
            return

        logger.info("⏰ Auto-finish: %d ta participation topildi", len(expired))

        for participation_id, user_id in expired:
            try:
                score_info = TestService.complete_test(participation_id)
                # Foydalanuvchiga xabar yuborish
                if _bot_instance and score_info:
                    pct = (
                        score_info['correct_count'] / score_info['total_questions'] * 100
                        if score_info['total_questions'] > 0 else 0
                    )
                    text = (
                        "⏰ <b>Imtihon vaqti tugadi!</b>\n\n"
                        f"• 📈 Ball: <b>{score_info['score']}</b>\n"
                        f"• ✅ To'g'ri: {score_info['correct_count']}"
                        f"/{score_info['total_questions']}\n"
                        f"• 📊 Foiz: {pct:.1f}%\n\n"
                        "🏆 Reytingda o'zingizni tekshiring!"
                    )
                    # User telegram_id ni olish
                    from database.db import Session
                    from database.models import User
                    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
                    db = Session()
                    user = db.query(User).filter(User.id == user_id).first()
                    db.close()
                    if user:
                        keyboard = ReplyKeyboardMarkup(
                            keyboard=[
                                [KeyboardButton(text="🧪 Yana test qol")],
                                [KeyboardButton(text="📊 Natijalarni ko'rish")],
                                [KeyboardButton(text="🏠 Bosh menyu")]
                            ],
                            resize_keyboard=True
                        )
                        await _bot_instance.send_message(
                            user.telegram_id,
                            text,
                            parse_mode="HTML",
                            reply_markup=keyboard
                        )
                logger.info(
                    "✅ Auto-finish: participation %d yakunlandi (user %d)",
                    participation_id, user_id
                )
            except Exception as e:
                logger.error(
                    "Auto-finish xato (participation %d): %s",
                    participation_id, e
                )
    except Exception as e:
        logger.error("_auto_finish_expired_tests umumiy xato: %s", e)
