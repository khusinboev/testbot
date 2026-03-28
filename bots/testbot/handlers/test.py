"""
bots/testbot/handlers/test.py

Test oqimi (flow):
  "Testni boshlash" → [resume / force_new / yo'nalish tanlash] → tasdiqlash
  → test_active → [answer / skip / finish / timeout]
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func as sqlfunc

from database.db import Session
from database.models import Direction, User, UserTestParticipation
from utils.channel_service import subscription_gate
from utils.locks import is_processing, throttle_check, user_lock
from utils.test_service import TOTAL_TEST_QUESTIONS, TestService

from .common import (
    fmt_error, format_question, format_score_result,
    get_direction_subject_names, get_user_by_telegram_id,
    safe_delete, show_main_menu,
)
from .gates import referral_gate
from ..keyboards import (
    get_directions_keyboard,
    get_main_menu_keyboard,
    get_test_answer_keyboard,
    get_test_confirmation_keyboard,
    get_test_results_keyboard,
)
from ..states import TestSessionStates

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# TEST BOSHLASH
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🧪 Testni boshlash")
async def start_test_button(message: types.Message, state: FSMContext, bot: Bot):
    if await state.get_state() == TestSessionStates.test_active:
        return

    if not await subscription_gate(bot, message.from_user.id, message):
        return
    if not await referral_gate(bot, message.from_user.id, message):
        return

    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return

    # Tugallanmagan aktiv test bormi?
    active = TestService.get_active_participation(user.id)
    if active:
        snapshot = TestService.load_snapshot(active.id)
        if snapshot and snapshot.get("questions"):
            remaining = active.deadline_at - datetime.utcnow()
            mins      = int(remaining.total_seconds() // 60)
            secs      = int(remaining.total_seconds() % 60)
            answered  = sum(1 for v in snapshot["answers"].values() if v is not None)

            await message.answer(
                f"⚠️ <b>Tugallanmagan test bor!</b>\n\n"
                f"• 🕐 Qolgan: <b>{mins} daq {secs} sek</b>\n"
                f"• 📝 Savol: {snapshot['current_question_index'] + 1}/{TOTAL_TEST_QUESTIONS}\n"
                f"• ✅ Javob berilgan: {answered} ta",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="▶️ Davom ettirish", callback_data="test_resume"),
                    InlineKeyboardButton(text="🆕 Yangi test",     callback_data="test_force_new"),
                ]]),
                parse_mode="HTML",
            )
            return
        else:
            TestService.complete_test(active.id)

    # Yo'nalish tanlanmagan bo'lsa avval tanlash
    if not user.direction_id:
        db    = Session()
        total = db.query(Direction).count()
        db.close()
        await message.answer(
            f"📚 <b>Ta'lim yo'nalishingizni tanlang</b>\n\n<i>Jami {total} ta yo'nalish</i>",
            reply_markup=await get_directions_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(TestSessionStates.waiting_for_direction)
        return

    await show_test_confirmation(message, state, user)


@router.callback_query(F.data == "test_resume")
async def handle_test_resume(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user = get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    active = TestService.get_active_participation(user.id)
    if not active:
        await callback.answer("❌ Aktiv test topilmadi!", show_alert=True)
        await safe_delete(callback.message)
        await callback.message.answer("🏠 Bosh menyu",
                                      reply_markup=await get_main_menu_keyboard())
        await state.clear()
        return

    snapshot = TestService.load_snapshot(active.id)
    if not snapshot or not snapshot.get("questions"):
        await callback.answer("❌ Test ma'lumotlari topilmadi!", show_alert=True)
        TestService.complete_test(active.id)
        await safe_delete(callback.message)
        await callback.message.answer("🏠 Bosh menyu",
                                      reply_markup=await get_main_menu_keyboard())
        await state.clear()
        return

    if active.deadline_at and active.deadline_at <= datetime.utcnow():
        score_info = TestService.complete_test(active.id)
        await safe_delete(callback.message)
        text = (
            format_score_result(score_info, "⏰ <b>Vaqt tugadi!</b>")
            if score_info else "⏰ Test vaqti tugadi."
        )
        await callback.message.answer(text,
                                      reply_markup=await get_main_menu_keyboard(),
                                      parse_mode="HTML")
        await state.clear()
        await callback.answer("❌ Test vaqti tugagan!", show_alert=True)
        return

    current_idx = snapshot["current_question_index"]
    questions   = snapshot["questions"]
    remaining   = active.deadline_at - datetime.utcnow()
    mins        = int(remaining.total_seconds() // 60)

    await state.update_data(
        participation_id=active.id,
        test_session_id=active.test_session_id,
        questions=questions,
        current_question_index=current_idx,
        answers=snapshot["answers"],
        deadline_ts=active.deadline_at.timestamp(),
    )
    await safe_delete(callback.message)
    await callback.message.answer(
        f"▶️ <b>Test davom ettirildi!</b> (qolgan: {mins} daq)\n\n"
        + format_question(questions[current_idx], current_idx, len(questions)),
        reply_markup=get_test_answer_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(TestSessionStates.test_active)
    await callback.answer()


@router.callback_query(F.data == "test_force_new")
async def handle_force_new_test(callback: types.CallbackQuery, state: FSMContext):
    user = get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Xato!", show_alert=True)
        return

    db = Session()
    stale_ids = [
        p.id for p in db.query(UserTestParticipation).filter(
            UserTestParticipation.user_id == user.id,
            UserTestParticipation.status  == "active",
        ).all()
    ]
    db.close()
    for p_id in stale_ids:
        TestService.complete_test(p_id)

    await safe_delete(callback.message)
    await callback.answer("✅ Eski test yakunlandi")
    await state.clear()

    if not user.direction_id:
        db2   = Session()
        total = db2.query(Direction).count()
        db2.close()
        await callback.message.answer(
            f"📚 <b>Ta'lim yo'nalishingizni tanlang</b>\n\n<i>Jami {total} ta</i>",
            reply_markup=await get_directions_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(TestSessionStates.waiting_for_direction)
    else:
        await show_test_confirmation(callback.message, state, user)


async def show_test_confirmation(
    message: types.Message, state: FSMContext, user: User
) -> None:
    db = Session()
    today = datetime.utcnow().date()
    existing_today = db.query(UserTestParticipation).filter(
        UserTestParticipation.user_id == user.id,
        sqlfunc.date(UserTestParticipation.started_at) == today,
        UserTestParticipation.status.in_(["active", "completed"]),
    ).first()
    db.close()

    if existing_today:
        await message.answer(
            "⏰ <b>Bugun allaqachon test yechgansiz!</b>\n\n"
            "Har kuni faqat <b>1 marta</b> test yechish mumkin.\n"
            "Ertaga qayta urinib ko'ring! 🚀",
            parse_mode="HTML",
        )
        return

    if user.direction:
        s1, s2 = get_direction_subject_names(user.direction)
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
        reply_markup=get_test_confirmation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(TestSessionStates.test_confirmation)


# ══════════════════════════════════════════════════════════════════════════════
# TEST TASDIQLASH
# ══════════════════════════════════════════════════════════════════════════════

@router.message(TestSessionStates.test_confirmation)
async def block_during_confirmation(message: types.Message, state: FSMContext):
    await safe_delete(message)


@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_cancel")
async def cancel_test(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await state.clear()
    user = get_user_by_telegram_id(callback.from_user.id)
    await callback.message.answer(
        f"🏠 Bosh menyu. Assalomu alaykum, <b>{user.first_name if user else ''}!</b>",
        reply_markup=await get_main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_start_confirm")
async def confirm_test_start(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    uid = callback.from_user.id
    if is_processing(uid):
        await callback.answer("⏳ Kuting...")
        return

    async with user_lock(uid):
        user = await asyncio.to_thread(get_user_by_telegram_id, uid)
        if not user:
            await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
            return

        def _check_active_and_stale(u_id):
            db = Session()
            try:
                now = datetime.utcnow()
                active = db.query(UserTestParticipation).filter(
                    UserTestParticipation.user_id    == u_id,
                    UserTestParticipation.status     == "active",
                    UserTestParticipation.deadline_at > now,
                ).first()
                stale = [
                    p.id for p in db.query(UserTestParticipation).filter(
                        UserTestParticipation.user_id == u_id,
                        UserTestParticipation.status  == "active",
                    ).all()
                ]
                return bool(active), stale
            finally:
                db.close()

        still_active, stale_ids = await asyncio.to_thread(_check_active_and_stale, user.id)

        if still_active:
            await callback.answer(
                "⚠️ Avval davom etayotgan testni yakunlang!", show_alert=True
            )
            return

        for stale_id in stale_ids:
            await asyncio.to_thread(TestService.complete_test, stale_id)

        try:
            participation = await asyncio.to_thread(
                TestService.create_participation, user.id, user.direction_id
            )
            if not participation:
                await callback.answer(
                    "❌ Kunlik test limiti tugagan! Ertaga qayta urinib ko'ring.",
                    show_alert=True,
                )
                return

            questions = await asyncio.to_thread(
                TestService.get_test_questions, user.direction_id
            )
            if not questions:
                await callback.answer("❌ Savollar topilmadi!", show_alert=True)
                return

            await state.update_data(
                participation_id=participation.id,
                test_session_id=participation.test_session_id,
                questions=questions,
                current_question_index=0,
                answers={},
                deadline_ts=participation.deadline_at.timestamp(),
            )
            await asyncio.to_thread(
                TestService.save_snapshot, participation.id, questions, 0, {}
            )

            await safe_delete(callback.message)
            await callback.message.answer(
                format_question(questions[0], 0, len(questions)),
                reply_markup=get_test_answer_keyboard(),
                parse_mode="HTML",
            )
            await state.set_state(TestSessionStates.test_active)

        except Exception as e:
            logger.error("confirm_test_start: %s", traceback.format_exc())
            await callback.answer(fmt_error(e), show_alert=True)


# ══════════════════════════════════════════════════════════════════════════════
# TEST JARAYONI
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(TestSessionStates.test_active, F.data.startswith("answer_"))
async def handle_test_answer(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not throttle_check(uid, min_interval=0.3):
        await callback.answer()
        return
    if is_processing(uid):
        await callback.answer("⏳")
        return

    async with user_lock(uid):
        answer        = callback.data.split("_")[1]
        data          = await state.get_data()
        current_index = data.get("current_question_index", 0)
        questions     = data.get("questions", [])
        answers       = data.get("answers", {})
        p_id          = data.get("participation_id")
        ts_id         = data.get("test_session_id")
        deadline_ts   = data.get("deadline_ts")

        if not questions or p_id is None:
            await callback.answer("❌ Test topilmadi.", show_alert=True)
            await state.clear()
            await callback.message.answer("🏠 Bosh menyu",
                                          reply_markup=await get_main_menu_keyboard())
            return

        if current_index >= len(questions):
            await callback.answer()
            return

        # Vaqt tugadimi?
        if deadline_ts and datetime.utcnow().timestamp() > deadline_ts:
            score_info = await asyncio.to_thread(TestService.complete_test, p_id)
            await safe_delete(callback.message)
            await state.clear()
            text = (
                format_score_result(score_info, "⏰ <b>Vaqt tugadi!</b>")
                if score_info else "⏰ Test vaqti tugadi!"
            )
            await callback.message.answer(text,
                                          reply_markup=get_test_results_keyboard(),
                                          parse_mode="HTML")
            await callback.answer()
            return

        current_q = questions[current_index]

        if answer != "skip":
            answers[str(current_index)] = answer
            user = await asyncio.to_thread(get_user_by_telegram_id, uid)
            if user:
                await asyncio.to_thread(
                    TestService.save_answer,
                    p_id, user.id, ts_id,
                    current_q["id"], answer,
                    current_q.get("correct_answer"),
                )
        else:
            answers[str(current_index)] = None

        current_index += 1

        if current_index % 5 == 0 or current_index >= len(questions):
            await asyncio.to_thread(
                TestService.save_snapshot, p_id, questions, current_index, answers
            )

        if current_index >= len(questions):
            score_info = await asyncio.to_thread(TestService.complete_test, p_id)
            await safe_delete(callback.message)
            await state.clear()
            text = (
                format_score_result(score_info) if score_info else "✅ Imtihon tugallandi!"
            )
            await callback.message.answer(text,
                                          reply_markup=get_test_results_keyboard(),
                                          parse_mode="HTML")
        else:
            next_q = questions[current_index]
            await state.update_data(current_question_index=current_index, answers=answers)
            try:
                await callback.message.edit_text(
                    format_question(next_q, current_index, len(questions)),
                    reply_markup=get_test_answer_keyboard(),
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await callback.answer()


@router.callback_query(TestSessionStates.test_active, F.data == "test_finish")
async def finish_test_early(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if is_processing(uid):
        await callback.answer("⏳ Yakunlanmoqda...")
        return

    async with user_lock(uid):
        data = await state.get_data()
        p_id = data.get("participation_id")
        if not p_id:
            await callback.answer("❌ Test topilmadi.", show_alert=True)
            await state.clear()
            await callback.message.answer("🏠 Bosh menyu",
                                          reply_markup=await get_main_menu_keyboard())
            return

        score_info = await asyncio.to_thread(TestService.complete_test, p_id)
        await safe_delete(callback.message)
        await state.clear()
        text = (
            format_score_result(score_info) if score_info else "✅ Imtihon tugallandi!"
        )
        await callback.message.answer(text,
                                      reply_markup=get_test_results_keyboard(),
                                      parse_mode="HTML")
        await callback.answer()
