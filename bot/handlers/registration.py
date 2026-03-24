"""
bot/handlers/registration.py  — score display tuzatildi

O'zgarishlar:
  - _format_score_result(): yangi helper, hamma natija xabarlarini bir joyda
  - attempted_count / total (90) ko'rsatiladi
  - Foiz = correct / 90 * 100
  - Arxivlangan natijalar shaxsiy natijalar bo'limida belgilanadi
"""
from __future__ import annotations

from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ContentType, InlineKeyboardMarkup, InlineKeyboardButton,
)
from database.db import Session
from database.models import User, Region, District, Direction, Score, UserTestParticipation
from bot.states import (
    UserRegistrationStates, UserMainMenuStates,
    TestSessionStates, ProfileEditStates
)
from bot.keyboards import (
    get_regions_keyboard, get_districts_keyboard,
    get_directions_keyboard, get_direction_search_results,
    get_phone_keyboard, get_main_menu_keyboard,
    get_test_confirmation_keyboard, get_test_answer_keyboard,
    get_test_results_keyboard, get_profile_settings_keyboard,
)
from utils.test_service import TestService, TOTAL_TEST_QUESTIONS
from utils.locks import user_lock, is_processing, throttle_check
from utils.channel_service import (
    subscription_gate, check_user_subscriptions, build_subscribe_keyboard
)
from sqlalchemy.orm import joinedload
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)
router = Router()


def _err(e: Exception) -> str:
    logger.error("Handler xato:\n%s", traceback.format_exc())
    return f"❌ Xato: {str(e)[:150]}"


def _format_score_result(score_info: dict, prefix: str = "✅ <b>Imtihon tugallandi!</b>") -> str:
    """
    Natija xabarini formatlaydi.
    score_info: complete_test() dan kelgan dict
    - correct_count / 90 * 100 = foiz
    - attempted_count = javob berilgan savollar soni
    """
    score        = score_info.get('score', 0)
    correct      = score_info.get('correct_count', 0)
    attempted    = score_info.get('attempted_count', 0)
    total        = TOTAL_TEST_QUESTIONS  # Har doim 90
    pct          = round(correct / total * 100, 1)
    unanswered   = total - attempted

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


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_user_by_telegram_id(telegram_id: int):
    db = Session()
    user = db.query(User).options(
        joinedload(User.region),
        joinedload(User.district),
        joinedload(User.direction)
    ).filter(User.telegram_id == telegram_id).first()
    db.close()
    return user


def _split_full_name(full_name: str):
    parts = full_name.strip().split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _get_direction_subject_names(direction: Direction):
    db = Session()
    try:
        d = db.query(Direction).options(
            joinedload(Direction.subject1),
            joinedload(Direction.subject2)
        ).filter(Direction.id == direction.id).first()
        if d:
            return (
                d.subject1.name_uz if d.subject1 else "—",
                d.subject2.name_uz if d.subject2 else "—",
            )
        return "—", "—"
    finally:
        db.close()


async def show_main_menu(message: types.Message, state: FSMContext, user: User):
    keyboard       = await get_main_menu_keyboard()
    direction_name = user.direction.name_uz if user.direction else "❗ Belgilanmagan"
    await message.answer(
        f"🏛 <b>DTM Test Bot</b>\n\n"
        f"Assalomu alaykum, <b>{user.first_name} {user.last_name or ''}</b>!\n\n"
        f"• 📱 {user.phone}\n"
        f"• 📍 {user.region.name_uz} / {user.district.name_uz}\n"
        f"• 📚 {direction_name}\n\n"
        f"<b>Nima qilmoqchi ekaningizni tanlang:</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(UserMainMenuStates.main_menu)


# ─── Kanal obuna ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(
    callback_query: types.CallbackQuery, state: FSMContext, bot: Bot
):
    uid = callback_query.from_user.id
    not_sub = await check_user_subscriptions(bot, uid)
    if not not_sub:
        await callback_query.answer("✅ Rahmat! Barcha kanallarga obuna bo'ldingiz.", show_alert=True)
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        user = get_user_by_telegram_id(uid)
        if user:
            await show_main_menu(callback_query.message, state, user)
        else:
            await callback_query.message.answer("Ro'yxatdan o'tish uchun /start bosing.")
    else:
        keyboard = build_subscribe_keyboard(not_sub)
        await callback_query.answer("❌ Hali obuna bo'lmagan kanallar bor!", show_alert=True)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        except Exception:
            pass


# ─── /start ──────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    if not await subscription_gate(bot, message.from_user.id, message):
        return
    user = get_user_by_telegram_id(message.from_user.id)
    if user:
        await show_main_menu(message, state, user)
    else:
        await message.answer(
            "📝 <b>Ro'yxatdan o'tish</b>\n\n"
            "Assalomu alaykum! Ro'yxatdan o'tish uchun:\n\n"
            "👤 <b>To'liq ismingizni kiriting (F.I.SH):</b>",
            parse_mode="HTML"
        )
        await state.set_state(UserRegistrationStates.waiting_for_full_name)


# ─── Ro'yxatdan o'tish ───────────────────────────────────────────────────────

@router.message(UserRegistrationStates.waiting_for_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Kamida 2 ta harf kiriting!")
        return
    full_name = message.text.strip()
    first, last = _split_full_name(full_name)
    await state.update_data(first_name=first, last_name=last, full_name=full_name)
    keyboard = await get_phone_keyboard()
    await message.answer(
        f"✅ <b>{full_name}</b>\n\n📱 <b>Telefon raqamingizni ulang:</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_phone)


@router.message(UserRegistrationStates.waiting_for_phone, F.content_type == ContentType.CONTACT)
async def process_phone_contact(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    keyboard = await get_regions_keyboard()
    await message.answer("📍 <b>Viloyatingizni tanlang:</b>",
                         reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserRegistrationStates.waiting_for_region)


@router.message(UserRegistrationStates.waiting_for_phone)
async def process_phone_invalid(message: types.Message, state: FSMContext):
    keyboard = await get_phone_keyboard()
    await message.answer("📱 Iltimos tugmani bosing:", reply_markup=keyboard)


@router.callback_query(UserRegistrationStates.waiting_for_region, F.data.startswith("region_"))
async def process_region_selection(callback_query: types.CallbackQuery, state: FSMContext):
    region_id = int(callback_query.data.split("_")[1])
    db = Session()
    region = db.query(Region).filter(Region.id == region_id).first()
    db.close()
    if not region:
        await callback_query.answer("❌ Viloyat topilmadi!")
        return
    await state.update_data(region_id=region_id)
    keyboard = await get_districts_keyboard(region_id)
    await callback_query.message.edit_text(
        f"📍 <b>Tumanni tanlang ({region.name_uz}):</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_district)


@router.callback_query(UserRegistrationStates.waiting_for_district, F.data == "region_back")
async def reg_district_back(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = await get_regions_keyboard()
    await callback_query.message.edit_text(
        "📍 <b>Viloyatingizni tanlang:</b>", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_region)


@router.callback_query(UserRegistrationStates.waiting_for_district, F.data.startswith("district_"))
async def process_district_selection(callback_query: types.CallbackQuery, state: FSMContext):
    district_id = int(callback_query.data.split("_")[1])
    db = Session()
    district = db.query(District).filter(District.id == district_id).first()
    db.close()
    if not district:
        await callback_query.answer("❌ Tuman topilmadi!")
        return
    await state.update_data(district_id=district_id)

    data = await state.get_data()
    db2  = Session()
    region = db2.query(Region).filter(Region.id == data.get('region_id')).first()
    db2.close()

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha", callback_data="confirm_yes"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no")
    ]])
    await callback_query.message.edit_text(
        f"✅ <b>Tasdiqlash</b>\n\n"
        f"• F.I.SH: {data.get('full_name', '')}\n"
        f"• Telefon: {data['phone']}\n"
        f"• Viloyat: {region.name_uz if region else '—'}\n"
        f"• Tuman: {district.name_uz}\n\n"
        f"<b>Tasdiqlaysizmi?</b>",
        reply_markup=confirm_kb, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.confirmation)


@router.callback_query(UserRegistrationStates.confirmation)
async def process_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    if is_processing(callback_query.from_user.id):
        await callback_query.answer("⏳ Kuting...")
        return

    if callback_query.data == "confirm_no":
        await callback_query.message.edit_text("❌ Bekor qilindi.")
        await state.clear()
        await callback_query.message.answer("Qayta boshlash: /start")
        return

    async with user_lock(callback_query.from_user.id):
        existing = get_user_by_telegram_id(callback_query.from_user.id)
        if existing:
            await callback_query.answer("✅ Allaqachon ro'yxatdan o'tgansiz!", show_alert=True)
            await state.clear()
            await show_main_menu(callback_query.message, state, existing)
            return

        data = await state.get_data()
        db   = Session()
        try:
            new_user = User(
                telegram_id=callback_query.from_user.id,
                first_name=data['first_name'],
                last_name=data.get('last_name', ''),
                phone=data['phone'],
                region_id=data['region_id'],
                district_id=data['district_id'],
                direction_id=None
            )
            db.add(new_user)
            db.commit()
            user = db.query(User).options(
                joinedload(User.region), joinedload(User.district), joinedload(User.direction)
            ).filter(User.telegram_id == callback_query.from_user.id).first()
            await callback_query.answer("✅ Ro'yxatdan o'tildi!", show_alert=True)
            await state.clear()
            await show_main_menu(callback_query.message, state, user)
        except Exception as e:
            db.rollback()
            await callback_query.answer(_err(e), show_alert=True)
        finally:
            db.close()


# ─── Leaderboard ─────────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🏆 Reyting")
async def show_leaderboard(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Ro'yxatdan o'ting!")
        return

    if not user.direction_id:
        await message.answer(
            "❗ <b>Yo'nalish tanlang!</b>\n\nReytingni ko'rish uchun avval "
            "ta'lim yo'nalishingizni belgilang.",
            parse_mode="HTML"
        )
        return

    period_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Kunlik",      callback_data="leaderboard_daily")],
        [InlineKeyboardButton(text="📊 Haftalik",    callback_data="leaderboard_weekly")],
        [InlineKeyboardButton(text="🏆 Barcha vaqt", callback_data="leaderboard_all_time")],
    ])
    await message.answer(
        "🏆 <b>Reytingni tanlang</b>\n\n"
        f"Yo'nalish: <b>{user.direction.name_uz}</b>",
        reply_markup=period_kb, parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("leaderboard_"))
async def handle_leaderboard_period(callback_query: types.CallbackQuery, state: FSMContext):
    period_map = {
        "leaderboard_daily":    "daily",
        "leaderboard_weekly":   "weekly",
        "leaderboard_all_time": "all_time"
    }
    period = period_map.get(callback_query.data)
    if not period:
        return

    user = get_user_by_telegram_id(callback_query.from_user.id)
    if not user or not user.direction_id:
        await callback_query.answer("❌ Xato!", show_alert=True)
        return

    leaderboard = TestService.get_direction_leaderboard(user.direction_id, period, limit=10)

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
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(entry['rank'], f"{entry['rank']}.")
            name = f"{entry['first_name']} {entry['last_name'] or ''}".strip()
            me = " 👈 <b>Siz</b>" if entry['user_id'] == user.id else ""
            if entry['user_id'] == user.id:
                user_in_top = True
            text += f"{medal} {name} — <b>{entry['score']:.1f}</b> ball{me}\n"

        if not user_in_top:
            rank = TestService.get_user_direction_rank(user.id, user.direction_id)
            text += f"\n👤 Sizning o'rningiz: <b>#{rank}</b>"

    try:
        await callback_query.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()


# ─── Testni boshlash ─────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🧪 Testni boshlash")
async def start_test_button(message: types.Message, state: FSMContext, bot: Bot):
    if not await subscription_gate(bot, message.from_user.id, message):
        return

    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return

    active = TestService.get_active_participation(user.id)
    if active:
        snapshot = TestService.load_snapshot(active.id)
        if snapshot and snapshot.get('questions'):
            remaining = active.deadline_at - datetime.utcnow()
            mins = int(remaining.total_seconds() // 60)
            secs = int(remaining.total_seconds() % 60)
            answered = sum(1 for v in snapshot['answers'].values() if v is not None)

            resume_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="▶️ Davom ettirish", callback_data="test_resume"),
                InlineKeyboardButton(text="🆕 Yangi test",     callback_data="test_force_new"),
            ]])
            await message.answer(
                f"⚠️ <b>Tugallanmagan test bor!</b>\n\n"
                f"• 🕐 Qolgan: <b>{mins} daq {secs} sek</b>\n"
                f"• 📝 Savol: {snapshot['current_question_index'] + 1}/{TOTAL_TEST_QUESTIONS}\n"
                f"• ✅ Javob berilgan: {answered} ta",
                reply_markup=resume_kb, parse_mode="HTML"
            )
            return
        else:
            TestService.complete_test(active.id)

    if not user.direction_id:
        db = Session()
        total = db.query(Direction).count()
        db.close()
        keyboard = await get_directions_keyboard()
        await message.answer(
            f"📚 <b>Ta'lim yo'nalishingizni tanlang</b>\n\n<i>Jami {total} ta yo'nalish</i>",
            reply_markup=keyboard, parse_mode="HTML"
        )
        await state.set_state(TestSessionStates.waiting_for_direction)
        return

    await _show_test_confirmation(message, state, user)


@router.callback_query(F.data == "test_resume")
async def handle_test_resume(callback_query: types.CallbackQuery,
                               state: FSMContext, bot: Bot):
    user = get_user_by_telegram_id(callback_query.from_user.id)
    if not user:
        await callback_query.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    active = TestService.get_active_participation(user.id)
    if not active:
        await callback_query.answer("❌ Aktiv test topilmadi!", show_alert=True)
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        keyboard = await get_main_menu_keyboard()
        await callback_query.message.answer("🏠 Bosh menyu", reply_markup=keyboard)
        await state.set_state(UserMainMenuStates.main_menu)
        return

    snapshot = TestService.load_snapshot(active.id)
    if not snapshot or not snapshot.get('questions'):
        await callback_query.answer("❌ Test ma'lumotlari topilmadi!", show_alert=True)
        TestService.complete_test(active.id)
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        keyboard = await get_main_menu_keyboard()
        await callback_query.message.answer("🏠 Bosh menyu", reply_markup=keyboard)
        await state.set_state(UserMainMenuStates.main_menu)
        return

    if active.deadline_at and active.deadline_at <= datetime.utcnow():
        await callback_query.answer("❌ Test vaqti tugagan!", show_alert=True)
        score_info = TestService.complete_test(active.id)
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        keyboard = await get_main_menu_keyboard()
        result_text = "⏰ Test vaqti tugadi."
        if score_info:
            result_text = _format_score_result(score_info, "⏰ <b>Vaqt tugadi!</b>")
        await callback_query.message.answer(result_text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserMainMenuStates.main_menu)
        return

    current_idx = snapshot['current_question_index']
    questions   = snapshot['questions']
    remaining   = active.deadline_at - datetime.utcnow()
    mins        = int(remaining.total_seconds() // 60)

    await state.update_data(
        participation_id=active.id,
        test_session_id=active.test_session_id,
        questions=questions,
        current_question_index=current_idx,
        answers=snapshot['answers'],
        deadline_ts=active.deadline_at.timestamp(),
    )

    try:
        await callback_query.message.delete()
    except Exception:
        pass

    await callback_query.message.answer(
        f"▶️ <b>Test davom ettirildi!</b> (qolgan: {mins} daq)\n\n"
        + _format_question(questions[current_idx], current_idx, len(questions)),
        reply_markup=get_test_answer_keyboard(), parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.test_active)
    await callback_query.answer()


@router.callback_query(F.data == "test_force_new")
async def handle_force_new_test(callback_query: types.CallbackQuery, state: FSMContext):
    user = get_user_by_telegram_id(callback_query.from_user.id)
    if not user:
        await callback_query.answer("❌ Xato!", show_alert=True)
        return

    db = Session()
    active_ids = [
        p.id for p in db.query(UserTestParticipation).filter(
            UserTestParticipation.user_id == user.id,
            UserTestParticipation.status == 'active'
        ).all()
    ]
    db.close()

    for p_id in active_ids:
        TestService.complete_test(p_id)

    try:
        await callback_query.message.delete()
    except Exception:
        pass

    await callback_query.answer("✅ Eski test yakunlandi")
    await state.clear()
    await state.set_state(UserMainMenuStates.main_menu)

    if not user.direction_id:
        db2 = Session()
        total = db2.query(Direction).count()
        db2.close()
        keyboard = await get_directions_keyboard()
        await callback_query.message.answer(
            f"📚 <b>Ta'lim yo'nalishingizni tanlang</b>\n\n<i>Jami {total} ta</i>",
            reply_markup=keyboard, parse_mode="HTML"
        )
        await state.set_state(TestSessionStates.waiting_for_direction)
    else:
        await _show_test_confirmation(callback_query.message, state, user)


async def _show_test_confirmation(message: types.Message, state: FSMContext, user: User):
    from sqlalchemy import func as sqlfunc
    db = Session()
    today = datetime.utcnow().date()
    existing_today = db.query(UserTestParticipation).filter(
        UserTestParticipation.user_id == user.id,
        sqlfunc.date(UserTestParticipation.started_at) == today,
        UserTestParticipation.status.in_(['active', 'completed'])
    ).first()
    db.close()

    if existing_today:
        await message.answer(
            "⏰ <b>Bugun allaqachon test yechgansiz!</b>\n\n"
            "Har kuni faqat <b>1 marta</b> test yechish mumkin.\n"
            "Ertaga qayta urinib ko'ring! 🚀",
            parse_mode="HTML"
        )
        return

    if user.direction:
        s1, s2 = _get_direction_subject_names(user.direction)
        direction_line = (
            f"  • 📚 {user.direction.name_uz}\n"
            f"  • 📖 1-fan: <b>{s1}</b>\n"
            f"  • 📗 2-fan: <b>{s2}</b>"
        )
    else:
        direction_line = "  • ❗ Yo'nalish belgilanmagan"

    await message.answer(
        f"📝 <b>Imtihon boshlash</b>\n\n"
        f"⏱️ <b>180 daqiqa</b> | ❓ <b>{TOTAL_TEST_QUESTIONS} savol</b>\n\n"
        f"1️⃣ Matematika (10) · 2️⃣ Ona tili (10) · 3️⃣ Tarix (10)\n"
        f"4️⃣ 1-asosiy fan (30) · 5️⃣ 2-asosiy fan (30)\n\n"
        f"{direction_line}\n\n<b>Boshlaysizmi?</b>",
        reply_markup=get_test_confirmation_keyboard(), parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.test_confirmation)


# ─── Yo'nalish tanlash ────────────────────────────────────────────────────────

@router.callback_query(TestSessionStates.waiting_for_direction, F.data.startswith("direction_page_"))
async def test_direction_page(callback_query: types.CallbackQuery, state: FSMContext):
    page     = int(callback_query.data.split("_")[2])
    keyboard = await get_directions_keyboard(page)
    await callback_query.message.edit_text(
        "📚 <b>Yo'nalishni tanlang</b>", reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(TestSessionStates.waiting_for_direction, F.data == "direction_list_back")
async def test_direction_back(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await state.set_state(UserMainMenuStates.main_menu)
    keyboard = await get_main_menu_keyboard()
    await callback_query.message.answer("🏠 Bosh menyu", reply_markup=keyboard)


@router.callback_query(TestSessionStates.waiting_for_direction, F.data.startswith("direction_"))
async def test_direction_selected(callback_query: types.CallbackQuery, state: FSMContext):
    if "_page_" in callback_query.data:
        return
    direction_id = callback_query.data.split("_")[1]
    db = Session()
    direction = db.query(Direction).options(
        joinedload(Direction.subject1), joinedload(Direction.subject2)
    ).filter(Direction.id == direction_id).first()
    if not direction:
        await callback_query.answer("❌ Topilmadi!")
        db.close()
        return
    user_db = db.query(User).filter(User.telegram_id == callback_query.from_user.id).first()
    if user_db:
        user_db.direction_id = direction_id
        db.commit()
    db.close()
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    user = get_user_by_telegram_id(callback_query.from_user.id)
    await callback_query.answer(f"✅ {direction.name_uz[:30]}")
    await _show_test_confirmation(callback_query.message, state, user)


# ─── Test tasdiqlash ──────────────────────────────────────────────────────────

@router.message(TestSessionStates.test_confirmation)
async def block_messages_during_confirmation(message: types.Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_start_confirm")
async def confirm_test_start(callback_query: types.CallbackQuery,
                              state: FSMContext, bot: Bot):
    uid = callback_query.from_user.id
    if is_processing(uid):
        await callback_query.answer("⏳ Kuting...")
        return

    async with user_lock(uid):
        user = get_user_by_telegram_id(uid)
        if not user:
            await callback_query.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
            return

        db  = Session()
        now = datetime.utcnow()
        active = db.query(UserTestParticipation).filter(
            UserTestParticipation.user_id   == user.id,
            UserTestParticipation.status    == 'active',
            UserTestParticipation.deadline_at > now
        ).first()
        db.close()

        if active:
            await callback_query.answer(
                "⚠️ Avval davom etayotgan testni yakunlang!", show_alert=True
            )
            return

        # Vaqti o'tgan 'active' participationlarni tozalash
        db2 = Session()
        stale = [p.id for p in db2.query(UserTestParticipation).filter(
            UserTestParticipation.user_id == user.id,
            UserTestParticipation.status  == 'active'
        ).all()]
        db2.close()
        for stale_id in stale:
            TestService.complete_test(stale_id)

        try:
            participation = TestService.create_participation(user.id, user.direction_id)

            if not participation:
                await callback_query.answer(
                    "❌ Kunlik test limiti tugagan! Ertaga qayta urinib ko'ring.", show_alert=True
                )
                return

            questions = TestService.get_test_questions(user.direction_id)

            if not questions:
                await callback_query.answer("❌ Savollar topilmadi!", show_alert=True)
                return

            deadline_ts = participation.deadline_at.timestamp()

            await state.update_data(
                participation_id=participation.id,
                test_session_id=participation.test_session_id,
                questions=questions,
                current_question_index=0,
                answers={},
                deadline_ts=deadline_ts,
            )
            TestService.save_snapshot(participation.id, questions, 0, {})

            try:
                await callback_query.message.delete()
            except Exception:
                pass

            await callback_query.message.answer(
                _format_question(questions[0], 0, len(questions)),
                reply_markup=get_test_answer_keyboard(), parse_mode="HTML"
            )
            await state.set_state(TestSessionStates.test_active)
        except Exception as e:
            logger.error("confirm_test_start: %s", traceback.format_exc())
            await callback_query.answer(_err(e), show_alert=True)


def _format_question(q: dict, index: int, total: int) -> str:
    group_label = q.get('group_label', '')
    if 'Majburiy' in group_label:
        emoji, gtype = '📌', 'Majburiy'
    else:
        emoji, gtype = '🎯', 'Asosiy'
    fan = group_label.split('—')[-1].strip() if '—' in group_label else group_label
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


@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_cancel")
async def cancel_test(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await state.set_state(UserMainMenuStates.main_menu)
    user     = get_user_by_telegram_id(callback_query.from_user.id)
    keyboard = await get_main_menu_keyboard()
    await callback_query.message.answer(
        f"🏠 Bosh menyu. Assalomu alaykum, <b>{user.first_name if user else ''}!</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )


# ─── Test jarayoni ────────────────────────────────────────────────────────────

@router.callback_query(TestSessionStates.test_active, F.data.startswith("answer_"))
async def handle_test_answer(callback_query: types.CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    if not throttle_check(uid, min_interval=0.3):
        await callback_query.answer()
        return
    if is_processing(uid):
        await callback_query.answer("⏳")
        return

    async with user_lock(uid):
        answer           = callback_query.data.split("_")[1]
        data             = await state.get_data()
        current_index    = data.get('current_question_index', 0)
        questions        = data.get('questions', [])
        answers          = data.get('answers', {})
        participation_id = data.get('participation_id')
        test_session_id  = data.get('test_session_id')
        deadline_ts      = data.get('deadline_ts')

        if not questions or participation_id is None:
            await callback_query.answer("❌ Test topilmadi.", show_alert=True)
            await state.clear()
            await state.set_state(UserMainMenuStates.main_menu)
            keyboard = await get_main_menu_keyboard()
            await callback_query.message.answer("🏠 Bosh menyu", reply_markup=keyboard)
            return

        if current_index >= len(questions):
            await callback_query.answer()
            return

        # Deadline tekshiruvi — FSM state dan (DB ga bormaydi)
        if deadline_ts and datetime.utcnow().timestamp() > deadline_ts:
            score_info = TestService.complete_test(participation_id)
            try:
                await callback_query.message.delete()
            except Exception:
                pass
            await state.clear()
            await state.set_state(UserMainMenuStates.main_menu)
            result_text = "⏰ Test vaqti tugadi!"
            if score_info:
                result_text = _format_score_result(score_info, "⏰ <b>Vaqt tugadi!</b>")
            await callback_query.message.answer(
                result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML"
            )
            await callback_query.answer()
            return

        current_q = questions[current_index]

        if answer != "skip":
            answers[str(current_index)] = answer
            user = get_user_by_telegram_id(uid)
            if user:
                TestService.save_answer(
                    participation_id=participation_id,
                    user_id=user.id,
                    test_session_id=test_session_id,
                    question_id=current_q['id'],
                    selected_answer=answer
                )
        else:
            answers[str(current_index)] = None

        current_index += 1

        if current_index % 5 == 0 or current_index >= len(questions):
            TestService.save_snapshot(participation_id, questions, current_index, answers)

        if current_index >= len(questions):
            score_info = TestService.complete_test(participation_id)
            try:
                await callback_query.message.delete()
            except Exception:
                pass
            await state.clear()
            await state.set_state(UserMainMenuStates.main_menu)

            result_text = (
                _format_score_result(score_info) if score_info else "✅ Imtihon tugallandi!"
            )
            await callback_query.message.answer(
                result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML"
            )
        else:
            next_q = questions[current_index]
            await state.update_data(current_question_index=current_index, answers=answers)
            try:
                await callback_query.message.edit_text(
                    _format_question(next_q, current_index, len(questions)),
                    reply_markup=get_test_answer_keyboard(), parse_mode="HTML"
                )
            except Exception:
                pass

        await callback_query.answer()


@router.callback_query(TestSessionStates.test_active, F.data == "test_finish")
async def finish_test_early(callback_query: types.CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    if is_processing(uid):
        await callback_query.answer("⏳ Yakunlanmoqda...")
        return

    async with user_lock(uid):
        data             = await state.get_data()
        participation_id = data.get('participation_id')
        if not participation_id:
            await callback_query.answer("❌ Test topilmadi.", show_alert=True)
            await state.clear()
            await state.set_state(UserMainMenuStates.main_menu)
            keyboard = await get_main_menu_keyboard()
            await callback_query.message.answer("🏠 Bosh menyu", reply_markup=keyboard)
            return

        score_info = TestService.complete_test(participation_id)
        try:
            await callback_query.message.delete()
        except Exception:
            pass

        await state.clear()
        await state.set_state(UserMainMenuStates.main_menu)

        result_text = (
            _format_score_result(score_info) if score_info else "✅ Imtihon tugallandi!"
        )
        await callback_query.message.answer(
            result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML"
        )
        await callback_query.answer()


# ─── Natijalarim ─────────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "📊 Natijalarim")
async def show_my_results(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Ro'yxatdan o'tmagan edingiz!")
        return

    # include_archived=True — shaxsiy natijalar, hammasi ko'rinadi
    scores = TestService.get_user_scores(user.id, include_archived=True, limit=10)

    if not scores:
        await message.answer("📊 <b>Hali test topshirilmagan.</b>", parse_mode="HTML")
        return

    text = "📊 <b>Natijalaringiz:</b>\n\n"
    for i, s in enumerate(scores[:10], 1):
        archive_tag = " 🗃 <i>arxiv</i>" if s['is_archived'] else ""
        text += (
            f"{i}. {s['created_at'].strftime('%d.%m.%Y %H:%M')}{archive_tag}\n"
            f"   📈 {s['score']:.1f} ball | ✅ {s['correct_count']}/{TOTAL_TEST_QUESTIONS}"
            f" | 📝 yechdi: {s['attempted_count']} | 📊 {s['percentage']}%\n\n"
        )
    await message.answer(text, parse_mode="HTML")


# ─── Reyting (main menu tugmasi) ─────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🏆 Reyting")
async def show_leaderboard_menu(message: types.Message, state: FSMContext):
    # Bu handler yuqoridagi show_leaderboard bilan bir xil — ikkinchisi ustun turadi
    pass


@router.callback_query(F.data == "leaderboard_global")
async def show_global_leaderboard_cb(callback_query: types.CallbackQuery, state: FSMContext):
    db = Session()
    try:
        top_scores = (
            db.query(Score)
            .filter(Score.is_archived == False)
            .order_by(Score.score.desc())
            .limit(10)
            .all()
        )
        if not top_scores:
            await callback_query.message.answer(
                "🏆 <b>Reytingda hali hech kim yo'q.</b>", parse_mode="HTML"
            )
            await callback_query.answer()
            return
        text = "🏆 <b>Umumiy reyting (Top 10)</b>\n\n"
        for i, s in enumerate(top_scores, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            u = s.user
            pct = round(s.correct_count / TOTAL_TEST_QUESTIONS * 100, 1)
            text += (
                f"{medal} <b>{u.first_name} {u.last_name or ''}</b>\n"
                f"   📊 {s.score:.1f} | ✅ {s.correct_count}/{TOTAL_TEST_QUESTIONS} ({pct}%)\n\n"
            )
        await callback_query.message.answer(text, parse_mode="HTML")
    finally:
        db.close()
    await callback_query.answer()


# ─── Yordam ───────────────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "❓ Yordam")
async def show_help(message: types.Message, state: FSMContext):
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        f"180 daqiqa · {TOTAL_TEST_QUESTIONS} savol\n\n"
        "  1️⃣ Matematika (10) — 1.1 ball\n"
        "  2️⃣ Ona tili (10) — 1.1 ball\n"
        "  3️⃣ Tarix (10) — 1.1 ball\n"
        "  4️⃣ 1-asosiy fan (30) — 3.1 ball\n"
        "  5️⃣ 2-asosiy fan (30) — 2.1 ball\n\n"
        "<b>Foiz hisoblash:</b> to'g'ri / 90 × 100",
        parse_mode="HTML"
    )


# ─── Profil ───────────────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "👤 Profilim")
async def show_profile(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Ro'yxatdan o'tmagan edingiz!")
        return

    # Faqat non-archived scorlar — hozirgi holat uchun
    active_scores = TestService.get_user_scores(user.id, include_archived=False, limit=100)
    all_scores    = TestService.get_user_scores(user.id, include_archived=True, limit=100)

    best_score = max((s['score'] for s in active_scores), default=0)
    total_tests = len(all_scores)

    if user.direction:
        s1, s2 = _get_direction_subject_names(user.direction)
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
        reply_markup=get_profile_settings_keyboard(), parse_mode="HTML"
    )


@router.callback_query(F.data == "profile_back")
async def profile_back(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await state.set_state(UserMainMenuStates.main_menu)


# ─── F.I.SH tahrirlash ────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile_edit_name")
async def profile_edit_name_start(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "✏️ <b>F.I.SH tahrirlash</b>\n\nYangi to'liq ismingizni kiriting:", parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.edit_full_name)


@router.message(ProfileEditStates.edit_full_name)
async def profile_edit_name_save(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Kamida 2 ta harf!")
        return
    first, last = _split_full_name(message.text.strip())
    db = Session()
    try:
        u = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if u:
            u.first_name = first
            u.last_name  = last
            db.commit()
        await state.set_state(UserMainMenuStates.main_menu)
        await message.answer(f"✅ F.I.SH yangilandi: <b>{first} {last}</b>", parse_mode="HTML")
        await show_profile(message, state)
    except Exception:
        db.rollback()
        await message.answer("❌ Xato yuz berdi.")
    finally:
        db.close()


# ─── Yo'nalish tahrirlash (profil) ───────────────────────────────────────────

@router.callback_query(F.data == "profile_edit_direction")
async def profile_edit_direction_start(callback_query: types.CallbackQuery, state: FSMContext):
    db    = Session()
    total = db.query(Direction).count()
    db.close()
    keyboard = await get_directions_keyboard()
    await callback_query.message.edit_text(
        f"📚 <b>Yo'nalishni o'zgartirish</b>\n\n<i>{total} ta yo'nalish</i>",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.edit_direction)


@router.callback_query(ProfileEditStates.edit_direction, F.data.startswith("direction_page_"))
async def profile_direction_page(callback_query: types.CallbackQuery, state: FSMContext):
    page     = int(callback_query.data.split("_")[2])
    keyboard = await get_directions_keyboard(page)
    await callback_query.message.edit_text(
        "📚 <b>Yo'nalishni o'zgartirish</b>", reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(ProfileEditStates.edit_direction, F.data == "direction_list_back")
async def profile_direction_back(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserMainMenuStates.main_menu)
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await show_profile(callback_query.message, state)


@router.callback_query(ProfileEditStates.edit_direction, F.data.startswith("direction_"))
async def profile_direction_selected(callback_query: types.CallbackQuery, state: FSMContext):
    if "_page_" in callback_query.data or callback_query.data in (
        "direction_search", "direction_search_empty",
        "direction_search_back", "direction_list_back"
    ):
        return
    direction_id = callback_query.data.split("_")[1]
    db = Session()
    direction = db.query(Direction).filter(Direction.id == direction_id).first()
    if not direction:
        await callback_query.answer("❌ Topilmadi!")
        db.close()
        return
    user = db.query(User).filter(User.telegram_id == callback_query.from_user.id).first()
    if user:
        user.direction_id = direction_id
        db.commit()
    db.close()
    await callback_query.answer("✅ Saqlandi!")
    await state.set_state(UserMainMenuStates.main_menu)
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await show_profile(callback_query.message, state)


# ─── Inline qidiruv ───────────────────────────────────────────────────────────

@router.message(F.text == "direction_search_failed")
async def handle_search_failed(message: types.Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass


@router.message(F.text.startswith("direction_chosen:"))
async def handle_any_direction_chosen(message: types.Message, state: FSMContext):
    direction_id = message.text.split(":", 1)[1].strip()
    try:
        await message.delete()
    except Exception:
        pass
    db = Session()
    direction = db.query(Direction).options(
        joinedload(Direction.subject1), joinedload(Direction.subject2)
    ).filter(Direction.id == direction_id).first()
    if not direction:
        await message.answer("❌ Yo'nalish topilmadi!")
        db.close()
        return
    user_db = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if user_db:
        user_db.direction_id = direction_id
        db.commit()
    direction_name = direction.name_uz
    db.close()

    current_state = await state.get_state()
    user          = get_user_by_telegram_id(message.from_user.id)
    await message.answer(f"✅ Yo'nalish: <b>{direction_name}</b>", parse_mode="HTML")
    if current_state in (
        TestSessionStates.waiting_for_direction,
        TestSessionStates.searching_direction,
    ):
        await _show_test_confirmation(message, state, user)
    elif current_state in (
        ProfileEditStates.edit_direction,
        ProfileEditStates.searching_direction,
    ):
        await state.set_state(UserMainMenuStates.main_menu)
        await show_profile(message, state)
    else:
        await show_main_menu(message, state, user)


# ─── Qidiruv ─────────────────────────────────────────────────────────────────

@router.callback_query(TestSessionStates.waiting_for_direction, F.data == "direction_search")
async def test_direction_search_start(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "🔍 <b>Yo'nalish qidirish</b>\n\nNomini kiriting:", parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.searching_direction)


@router.message(TestSessionStates.searching_direction)
async def test_direction_search_query(message: types.Message, state: FSMContext):
    query = (message.text or '').strip()
    if not query:
        return
    keyboard = await get_direction_search_results(query)
    db = Session()
    count = db.query(Direction).filter(Direction.name_uz.ilike(f"%{query}%")).count()
    db.close()
    await message.answer(
        f"🔍 <b>«{query}»</b> — {count} ta", reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(TestSessionStates.searching_direction, F.data == "direction_search_back")
async def test_direction_search_back(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = await get_directions_keyboard()
    await callback_query.message.edit_text(
        "📚 <b>Yo'nalishni tanlang</b>", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.waiting_for_direction)


@router.callback_query(TestSessionStates.searching_direction, F.data.startswith("direction_"))
async def test_direction_search_selected(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data in (
        "direction_search", "direction_search_empty",
        "direction_search_back", "direction_list_back"
    ):
        return
    direction_id = callback_query.data.split("_")[1]
    db = Session()
    direction = db.query(Direction).filter(Direction.id == direction_id).first()
    if not direction:
        await callback_query.answer("❌ Topilmadi!")
        db.close()
        return
    user_db = db.query(User).filter(User.telegram_id == callback_query.from_user.id).first()
    if user_db:
        user_db.direction_id = direction_id
        db.commit()
    db.close()
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    user = get_user_by_telegram_id(callback_query.from_user.id)
    await callback_query.answer(f"✅ {direction.name_uz[:30]}")
    await _show_test_confirmation(callback_query.message, state, user)


@router.callback_query(ProfileEditStates.edit_direction, F.data == "direction_search")
async def profile_direction_search_start(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "🔍 <b>Yo'nalish qidirish</b>\n\nNomini kiriting:", parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.searching_direction)


@router.message(ProfileEditStates.searching_direction)
async def profile_direction_search_query(message: types.Message, state: FSMContext):
    query = (message.text or '').strip()
    if not query:
        return
    keyboard = await get_direction_search_results(query)
    db = Session()
    count = db.query(Direction).filter(Direction.name_uz.ilike(f"%{query}%")).count()
    db.close()
    await message.answer(
        f"🔍 <b>«{query}»</b> — {count} ta", reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(ProfileEditStates.searching_direction, F.data == "direction_search_back")
async def profile_direction_search_back(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = await get_directions_keyboard()
    await callback_query.message.edit_text(
        "📚 <b>Yo'nalishni o'zgartirish</b>", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.edit_direction)


@router.callback_query(ProfileEditStates.searching_direction, F.data.startswith("direction_"))
async def profile_direction_search_selected(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data in (
        "direction_search", "direction_search_empty",
        "direction_search_back", "direction_list_back"
    ):
        return
    direction_id = callback_query.data.split("_")[1]
    db = Session()
    direction = db.query(Direction).filter(Direction.id == direction_id).first()
    if not direction:
        await callback_query.answer("❌ Topilmadi!")
        db.close()
        return
    user_db = db.query(User).filter(User.telegram_id == callback_query.from_user.id).first()
    if user_db:
        user_db.direction_id = direction_id
        db.commit()
    db.close()
    await callback_query.answer("✅ Saqlandi!")
    await state.set_state(UserMainMenuStates.main_menu)
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await show_profile(callback_query.message, state)


# ─── Test natijasi tugmalari ──────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🧪 Yana test qol")
async def another_test(message: types.Message, state: FSMContext, bot: Bot):
    await start_test_button(message, state, bot)


@router.message(UserMainMenuStates.main_menu, F.text == "📊 Natijalarni ko'rish")
async def view_results_from_test(message: types.Message, state: FSMContext):
    await show_my_results(message, state)


@router.message(UserMainMenuStates.main_menu, F.text == "🏠 Bosh menyu")
async def return_to_main_menu(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Ro'yxatdan o'tmagan edingiz!")
        return
    keyboard = await get_main_menu_keyboard()
    await message.answer(
        f"🏛 <b>DTM Test Bot</b>\n\nAssalomu alaykum, <b>{user.first_name}</b>!\n\n"
        f"Nima qilmoqchi ekaningizni tanlang:",
        reply_markup=keyboard, parse_mode="HTML"
    )