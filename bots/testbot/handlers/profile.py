"""
bots/testbot/handlers/profile.py

Profil ko'rish va tahrirlash, hamda misc handlerlar:
  - Profilim
  - Natijalarim
  - Reyting
  - Referalim
  - Yordam
  - Bosh menyu
"""

from __future__ import annotations

import urllib.parse

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.db import Session
from database.models import Direction, Score, User
from utils.referral_service import get_or_create_referral_link, get_referral_settings
from utils.test_service import TOTAL_TEST_QUESTIONS, TestService

from .common import (
    get_bot_username, get_direction_subject_names,
    get_user_by_telegram_id, safe_delete, show_main_menu,
    split_full_name,
)
from ..keyboards import get_directions_keyboard, get_main_menu_keyboard, get_profile_settings_keyboard
from ..states import ProfileEditStates, TestSessionStates

from aiogram import Bot

router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# PROFIL
# ══════════════════════════════════════════════════════════════════════════════

async def show_profile(message: types.Message, state: FSMContext) -> None:
    user = get_user_by_telegram_id(message.chat.id)
    if not user:
        await message.answer("❌ Ro'yxatdan o'tmagan edingiz!")
        return

    active_scores = TestService.get_user_scores(user.id, include_archived=False, limit=100)
    all_scores    = TestService.get_user_scores(user.id, include_archived=True,  limit=100)
    best_score    = max((s["score"] for s in active_scores), default=0)
    total_tests   = len(all_scores)

    if user.direction:
        s1, s2 = get_direction_subject_names(user.direction)
        dir_block = (
            f"• 📚 {user.direction.name_uz}\n"
            f"• 📖 1-fan: {s1}\n• 📗 2-fan: {s2}"
        )
    else:
        dir_block = "• 📚 ❗ Yo'nalish belgilanmagan"

    await message.answer(
        f"👤 <b>Profil</b>\n\n"
        f"• 📝 {user.first_name} {user.last_name or ''}\n"
        f"• 📱 {user.phone}\n"
        f"• 📍 {user.region.name_uz} / {user.district.name_uz}\n"
        f"{dir_block}\n\n"
        f"• 🧪 Jami testlar: {total_tests} ta\n"
        f"• 📊 Eng yaxshi ball: {best_score:.1f}\n"
        f"• 📅 Ro'yxat: {user.created_at.strftime('%d.%m.%Y')}\n\n"
        f"<b>Tahrirlash:</b>",
        reply_markup=get_profile_settings_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "👤 Profilim")
async def cmd_profile(message: types.Message, state: FSMContext):
    if await state.get_state() == TestSessionStates.test_active:
        return
    await show_profile(message, state)


@router.callback_query(F.data == "profile_back")
async def profile_back(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await state.clear()


@router.callback_query(F.data == "profile_edit_name")
async def profile_edit_name_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ <b>F.I.SH tahrirlash</b>\n\nYangi to'liq ismingizni kiriting:",
        parse_mode="HTML",
    )
    await state.set_state(ProfileEditStates.edit_full_name)


@router.message(ProfileEditStates.edit_full_name)
async def profile_edit_name_save(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Kamida 2 ta harf!")
        return
    first, last = split_full_name(message.text.strip())
    db = Session()
    try:
        u = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if u:
            u.first_name = first
            u.last_name  = last
            db.commit()
        await state.clear()
        await message.answer(
            f"✅ F.I.SH yangilandi: <b>{first} {last}</b>", parse_mode="HTML"
        )
        await show_profile(message, state)
    except Exception:
        db.rollback()
        await message.answer("❌ Xato yuz berdi.")
    finally:
        db.close()


@router.callback_query(F.data == "profile_edit_direction")
async def profile_edit_direction_start(callback: types.CallbackQuery, state: FSMContext):
    db    = Session()
    total = db.query(Direction).count()
    db.close()
    keyboard = await get_directions_keyboard()
    await callback.message.edit_text(
        f"📚 <b>Yo'nalishni o'zgartirish</b>\n\n<i>{total} ta yo'nalish</i>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await state.set_state(ProfileEditStates.edit_direction)


# ══════════════════════════════════════════════════════════════════════════════
# NATIJALAR
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text.in_({"📊 Natijalarim", "📊 Natijalarni ko'rish"}))
async def show_my_results(message: types.Message, state: FSMContext):
    if await state.get_state() == TestSessionStates.test_active:
        return

    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("📊 <b>Hali test topshirilmagan.</b>", parse_mode="HTML")
        return

    scores = TestService.get_user_scores(user.id, include_archived=True, limit=10)
    if not scores:
        await message.answer("📊 <b>Hali test topshirilmagan.</b>", parse_mode="HTML")
        return

    text = "📊 <b>Natijalaringiz:</b>\n\n"
    for i, s in enumerate(scores[:10], 1):
        archive_tag = " 🗃 <i>arxiv</i>" if s["is_archived"] else ""
        text += (
            f"{i}. {s['created_at'].strftime('%d.%m.%Y %H:%M')}{archive_tag}\n"
            f"   📈 {s['score']:.1f} ball | ✅ {s['correct_count']}/{TOTAL_TEST_QUESTIONS}"
            f" | 📝 yechdi: {s['attempted_count']} | 📊 {s['percentage']}%\n\n"
        )
    await message.answer(text, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
# REYTING
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🏆 Reyting")
async def show_leaderboard(message: types.Message, state: FSMContext):
    if await state.get_state() == TestSessionStates.test_active:
        return

    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Ro'yxatdan o'ting!")
        return

    if not user.direction_id:
        await message.answer(
            "❗ <b>Yo'nalish tanlang!</b>\n\nReytingni ko'rish uchun avval "
            "ta'lim yo'nalishingizni belgilang.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"🏆 <b>Reytingni tanlang</b>\n\nYo'nalish: <b>{user.direction.name_uz}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Kunlik",      callback_data="leaderboard_daily")],
            [InlineKeyboardButton(text="📊 Haftalik",    callback_data="leaderboard_weekly")],
            [InlineKeyboardButton(text="🏆 Barcha vaqt", callback_data="leaderboard_all_time")],
        ]),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("leaderboard_"))
async def handle_leaderboard_period(callback: types.CallbackQuery, state: FSMContext):
    period_map = {
        "leaderboard_daily":    "daily",
        "leaderboard_weekly":   "weekly",
        "leaderboard_all_time": "all_time",
    }
    period = period_map.get(callback.data)
    if not period:
        return

    user = get_user_by_telegram_id(callback.from_user.id)
    if not user or not user.direction_id:
        await callback.answer("❌ Xato!", show_alert=True)
        return

    leaderboard  = TestService.get_direction_leaderboard(user.direction_id, period, limit=10)
    period_names = {"daily": "Kunlik", "weekly": "Haftalik", "all_time": "Barcha vaqt"}

    if not leaderboard:
        text = (
            f"📊 <b>{period_names[period]} reyting</b>\n"
            f"📚 {user.direction.name_uz}\n\n"
            "<i>Bu davrda test yechganlar yo'q.</i>"
        )
    else:
        text = f"🏆 <b>{period_names[period]} Reyting</b>\n📚 {user.direction.name_uz}\n\n"
        user_in_top = False
        for entry in leaderboard:
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(entry["rank"], f"{entry['rank']}.")
            name  = f"{entry['first_name']} {entry['last_name'] or ''}".strip()
            me    = " 👈 <b>Siz</b>" if entry["user_id"] == user.id else ""
            if entry["user_id"] == user.id:
                user_in_top = True
            text += f"{medal} {name} — <b>{entry['score']:.1f}</b> ball{me}\n"

        if not user_in_top:
            rank = TestService.get_user_direction_rank(user.id, user.direction_id)
            text += f"\n👤 Sizning o'rningiz: <b>#{rank}</b>"

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# REFERALIM
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🔗 Referalim")
async def show_my_referral(message: types.Message, state: FSMContext, bot: Bot):
    if await state.get_state() == TestSessionStates.test_active:
        return

    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Ro'yxatdan o'ting!")
        return

    settings = get_referral_settings()
    if not settings.is_enabled:
        await message.answer(
            "🔗 <b>Referal tizimi</b>\n\n<i>Hozircha referal tizimi faol emas.</i>",
            parse_mode="HTML",
        )
        return

    link = get_or_create_referral_link(message.from_user.id)
    if not link:
        await message.answer("❌ Xato yuz berdi. Iltimos qayta urinib ko'ring.")
        return

    bot_username = await get_bot_username(bot)
    link_url     = f"https://t.me/{bot_username}?start={link.code}"
    invited      = link.invited_count

    if settings.required_count > 0:
        filled   = min(invited, settings.required_count)
        bar      = "🟢" * filled + "⚪️" * (settings.required_count - filled)
        progress = f"\n\n📊 Talab: {invited}/{settings.required_count}\n{bar}"
        if invited >= settings.required_count:
            progress += "\n✅ Talab bajarilgan!"
    else:
        progress = f"\n\n👥 Jami taklif qilganlar: <b>{invited}</b> ta"

    share_url = (
        "https://t.me/share/url"
        f"?url={urllib.parse.quote(link_url, safe='')}"
        f"&text={urllib.parse.quote('👨‍🏫Sizni DTM testlar botiga taklif qilaman! 🎓', safe='')}"
    )

    await message.answer(
        f"🔗 <b>Mening referal havolam</b>\n\n"
        f"<code>{link_url}</code>\n"
        f"{progress}\n\n"
        f"Do'stlaringiz ushbu havola orqali kirganda hisobingizga qo'shiladi!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url)],
        ]),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════════════════════
# MISC
# ══════════════════════════════════════════════════════════════════════════════

@router.message(Command("help"))
@router.message(F.text == "❓ Yordam")
async def show_help(message: types.Message, state: FSMContext):
    if await state.get_state() == TestSessionStates.test_active:
        return
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        f"180 daqiqa · {TOTAL_TEST_QUESTIONS} savol\n\n"
        "  1️⃣ Matematika (10) — 1.1 ball\n"
        "  2️⃣ Ona tili (10) — 1.1 ball\n"
        "  3️⃣ Tarix (10) — 1.1 ball\n"
        "  4️⃣ 1-asosiy fan (30) — 3.1 ball\n"
        "  5️⃣ 2-asosiy fan (30) — 2.1 ball\n\n"
        "<b>Foiz hisoblash:</b> to'g'ri / 90 × 100",
        parse_mode="HTML",
    )


@router.message(F.text.in_({"🏠 Bosh menyu", "🧪 Yana test qol"}))
async def return_to_main_menu(message: types.Message, state: FSMContext, bot: Bot = None):
    if await state.get_state() == TestSessionStates.test_active:
        return
    if message.text == "🧪 Yana test qol":
        from .test import start_test_button
        await start_test_button(message, state, bot)
        return
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Ro'yxatdan o'tmagan edingiz!")
        return
    await state.clear()
    await message.answer(
        f"🏛 <b>DTM Test Bot</b>\n\nAssalomu alaykum, <b>{user.first_name}</b>!\n\n"
        "Nima qilmoqchi ekaningizni tanlang:",
        reply_markup=await get_main_menu_keyboard(),
        parse_mode="HTML",
    )
