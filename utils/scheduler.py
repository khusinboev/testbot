"""
utils/scheduler.py

TUZATILDI:
  - X | Y type hint → Optional[] (Python 3.8 mos)
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
_bot_instance = None


def init_scheduler(bot) -> None:
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


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler to'xtatildi")


async def _auto_finish_expired_tests() -> None:
    from utils.test_service import TestService
    try:
        expired = TestService.get_expired_participations()
        if not expired:
            return

        logger.info("⏰ Auto-finish: %d ta participation", len(expired))

        for participation_id, user_id in expired:
            try:
                score_info = TestService.complete_test(participation_id)
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
                    from database.db import Session
                    from database.models import User
                    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
                    db = Session()
                    try:
                        user = db.query(User).filter(User.id == user_id).first()
                        tg_id = user.telegram_id if user else None
                    finally:
                        db.close()

                    if tg_id:
                        keyboard = ReplyKeyboardMarkup(
                            keyboard=[
                                [KeyboardButton(text="🧪 Yana test qol")],
                                [KeyboardButton(text="📊 Natijalarni ko'rish")],
                                [KeyboardButton(text="🏠 Bosh menyu")]
                            ],
                            resize_keyboard=True
                        )
                        try:
                            await _bot_instance.send_message(
                                tg_id, text,
                                parse_mode="HTML", reply_markup=keyboard
                            )
                        except Exception as send_err:
                            logger.warning("Xabar yuborib bo'lmadi %d: %s", tg_id, send_err)

                logger.info("✅ Auto-finish: participation %d (user_id %d)",
                            participation_id, user_id)
            except Exception as e:
                logger.error("Auto-finish xato participation %d: %s", participation_id, e)
    except Exception as e:
        logger.error("_auto_finish_expired_tests: %s", e)