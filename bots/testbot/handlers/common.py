"""
bots/testbot/handlers/common.py

Bu fayl barcha handler modullari import qiladigan
umumiy yordamchi funksiyalar va konstantalarni o'z ichiga oladi.

Tashqi modullardan: database, utils
Bot-specific: states, keyboards — shu papkadan
"""

from __future__ import annotations

import logging
import traceback
from typing import Optional

from aiogram import Bot, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import joinedload

from database.db import Session
from database.models import Direction, User
from utils.test_service import TOTAL_TEST_QUESTIONS

logger = logging.getLogger(__name__)

# Bot username keshi (bir marta olinadi, qayta-qayta API chaqirilmaydi)
_BOT_USERNAME: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# BOT UTILS
# ══════════════════════════════════════════════════════════════════════════════

async def get_bot_username(bot: Bot) -> str:
    global _BOT_USERNAME
    if not _BOT_USERNAME:
        try:
            me = await bot.get_me()
            _BOT_USERNAME = me.username
        except Exception:
            _BOT_USERNAME = "dtm_bot"
    return _BOT_USERNAME


def fmt_error(e: Exception) -> str:
    logger.error("Handler xato:\n%s", traceback.format_exc())
    return f"❌ Xato: {str(e)[:150]}"


async def safe_delete(message: types.Message) -> None:
    """Xabarni o'chiradi; xato chiqsa e'tibor berilmaydi."""
    try:
        await message.delete()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# DB SHORTCUTS
# ══════════════════════════════════════════════════════════════════════════════

def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    db   = Session()
    user = db.query(User).options(
        joinedload(User.region),
        joinedload(User.district),
        joinedload(User.direction),
    ).filter(User.telegram_id == telegram_id).first()
    db.close()
    return user


def get_direction_subject_names(direction: Direction) -> tuple[str, str]:
    db = Session()
    try:
        d = db.query(Direction).options(
            joinedload(Direction.subject1),
            joinedload(Direction.subject2),
        ).filter(Direction.id == direction.id).first()
        if d:
            return (
                d.subject1.name_uz if d.subject1 else "—",
                d.subject2.name_uz if d.subject2 else "—",
            )
        return "—", "—"
    finally:
        db.close()


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTERS
# ══════════════════════════════════════════════════════════════════════════════

def format_score_result(
    score_info: dict,
    prefix: str = "✅ <b>Imtihon tugallandi!</b>",
) -> str:
    total      = TOTAL_TEST_QUESTIONS
    score      = score_info.get("score", 0)
    correct    = score_info.get("correct_count", 0)
    attempted  = score_info.get("attempted_count", 0)
    pct        = round(correct / total * 100, 1)
    unanswered = total - attempted

    lines = [
        prefix, "",
        f"📈 Ball: <b>{score}</b>",
        f"✅ To'g'ri: <b>{correct}</b> ta",
        f"📝 Yechildi: <b>{attempted}/{total}</b>",
        f"📊 Foiz: <b>{pct}%</b>",
    ]
    if unanswered > 0:
        lines.append(f"⏭ Yechilmadi: {unanswered} ta")
    lines.append("\n🏆 Reytingda o'zingizni tekshiring!")
    return "\n".join(lines)


def format_question(q: dict, index: int, total: int) -> str:
    group_label = q.get("group_label", "")
    if "Majburiy" in group_label:
        emoji, gtype = "📌", "Majburiy"
    else:
        emoji, gtype = "🎯", "Asosiy"
    fan = group_label.split("—")[-1].strip() if "—" in group_label else group_label

    return (
        f"{emoji} <b>{gtype} | {fan}</b>\n"
        f"<b>Savol {index + 1} / {total}</b>\n"
        f"{'─' * 28}\n\n"
        f"{q['text_uz']}\n\n"
        f"<b>A)</b> {q['option_a']}\n"
        f"<b>B)</b> {q['option_b']}\n"
        f"<b>C)</b> {q['option_c']}\n"
        f"<b>D)</b> {q['option_d']}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU SHOW
# ══════════════════════════════════════════════════════════════════════════════

async def show_main_menu(message: types.Message, state: FSMContext, user: User) -> None:
    from bots.testbot.keyboards import get_main_menu_keyboard

    keyboard       = await get_main_menu_keyboard()
    direction_name = user.direction.name_uz if user.direction else "❗ Belgilanmagan"

    await message.answer(
        f"🏛 <b>DTM Test Bot</b>\n\n"
        f"Assalomu alaykum, <b>{user.first_name} {user.last_name or ''}</b>!\n\n"
        f"• 📱 {user.phone}\n"
        f"• 📍 {user.region.name_uz} / {user.district.name_uz}\n"
        f"• 📚 {direction_name}\n\n"
        f"<b>Nima qilmoqchi ekaningizni tanlang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await state.clear()
