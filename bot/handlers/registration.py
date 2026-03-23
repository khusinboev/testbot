from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ContentType, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from database.db import Session
from database.models import User, Region, District, Direction, Score, UserTestParticipation
from bot.states import (
    UserRegistrationStates, UserMainMenuStates,
    TestSessionStates, ProfileEditStates
)
from bot.keyboards import (
    get_regions_keyboard,
    get_districts_keyboard,
    get_directions_keyboard,
    get_phone_keyboard,
    get_main_menu_keyboard,
    get_test_confirmation_keyboard,
    get_test_answer_keyboard,
    get_test_results_keyboard,
    get_profile_settings_keyboard,
)
from utils.test_service import TestService
from utils.locks import user_lock, is_processing, throttle_check
from sqlalchemy.orm import joinedload
import re
import logging
import traceback

logger = logging.getLogger(__name__)
router = Router()


def _err(e: Exception) -> str:
    """callback_query.answer() uchun xato xabarini qisqartiradi (max 180 belgi).
    Asosiy xatoni konsolga to'liq chiqaradi."""
    msg = str(e)
    logger.error("Handler xato:\n%s", traceback.format_exc())
    short = msg[:150].replace('\n', ' ')
    return f"❌ Xato: {short}"


# ─── Yordamchi funksiyalar ───────────────────────────────────────────────────

def get_user_by_telegram_id(telegram_id: int) -> User:
    db = Session()
    user = db.query(User).options(
        joinedload(User.region),
        joinedload(User.district),
        joinedload(User.direction)
    ).filter(User.telegram_id == telegram_id).first()
    db.close()
    return user


def _split_full_name(full_name: str) -> tuple[str, str]:
    """'Ism Familiya' → ('Ism', 'Familiya'). Bitta so'z bo'lsa last_name=''."""
    parts = full_name.strip().split(None, 1)
    first = parts[0] if parts else full_name
    last = parts[1] if len(parts) > 1 else ""
    return first, last


async def show_main_menu(message: types.Message, state: FSMContext, user: User):
    keyboard = await get_main_menu_keyboard()
    direction_name = user.direction.name_uz if user.direction else "❗ Belgilanmagan"
    text = (
        f"🏛 <b>DTM Test Bot</b>\n\n"
        f"Assalomu alaykum, <b>{user.first_name} {user.last_name}</b>!\n\n"
        f"<b>Shaxsiy ma'lumotlar:</b>\n"
        f"• 📱 Telefon: {user.phone}\n"
        f"• 📍 Viloyat: {user.region.name_uz}\n"
        f"• 📍 Tuman: {user.district.name_uz}\n"
        f"• 📚 Yo'nalish: {direction_name}\n\n"
        f"<b>Nima qilmoqchi ekaningizni tanlang:</b>"
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserMainMenuStates.main_menu)


# ─── /start ──────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = get_user_by_telegram_id(message.from_user.id)
    if user:
        await show_main_menu(message, state, user)
    else:
        await message.answer(
            "📝 <b>Ro'yxatdan o'tish</b>\n\n"
            "Assalomu alaykum! Botdan foydalanish uchun ro'yxatdan o'ting.\n\n"
            "👤 <b>To'liq ismingizni kiriting (F.I.SH):</b>\n"
            "<i>Misol: Aliyev Jasur Bahodirovich</i>",
            parse_mode="HTML"
        )
        await state.set_state(UserRegistrationStates.waiting_for_full_name)


# ─── Ro'yxatdan o'tish ───────────────────────────────────────────────────────

@router.message(UserRegistrationStates.waiting_for_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Iltimos, to'liq ismingizni kiriting (kamida 2 ta harf)!")
        return
    full_name = message.text.strip()
    first, last = _split_full_name(full_name)
    await state.update_data(first_name=first, last_name=last, full_name=full_name)

    keyboard = await get_phone_keyboard()
    await message.answer(
        f"✅ Ism saqlandi: <b>{full_name}</b>\n\n"
        "📱 <b>Telefon raqamingizni ulang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_phone)


@router.message(UserRegistrationStates.waiting_for_phone, F.content_type == ContentType.CONTACT)
async def process_phone_contact(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    keyboard = await get_regions_keyboard()
    await message.answer(
        "📍 <b>Viloyatingizni tanlang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_region)


@router.message(UserRegistrationStates.waiting_for_phone)
async def process_phone_invalid(message: types.Message, state: FSMContext):
    # Tugma orqali yuborilmagan har qanday xabarni rad etish
    keyboard = await get_phone_keyboard()
    await message.answer(
        "📱 Iltimos, quyidagi tugmani bosib telefon raqamingizni ulang:",
        reply_markup=keyboard
    )


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
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_district)


@router.callback_query(UserRegistrationStates.waiting_for_district, F.data == "region_back")
async def reg_district_back(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = await get_regions_keyboard()
    await callback_query.message.edit_text(
        "📍 <b>Viloyatingizni tanlang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
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
    db2 = Session()
    region = db2.query(Region).filter(Region.id == data.get('region_id')).first()
    db2.close()

    confirmation_text = (
        f"✅ <b>Ro'yxatdan o'tish — tasdiqlash</b>\n\n"
        f"• 👤 F.I.SH: {data.get('full_name', data.get('first_name', ''))}\n"
        f"• 📱 Telefon: {data['phone']}\n"
        f"• 📍 Viloyat: {region.name_uz if region else '—'}\n"
        f"• 📍 Tuman: {district.name_uz}\n\n"
        f"<i>Yo'nalishni keyinroq Profil sozlamalarida belgilaysiz.</i>\n\n"
        f"<b>Tasdiqlaysizmi?</b>"
    )
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha", callback_data="confirm_yes"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no")
    ]])
    await callback_query.message.edit_text(
        confirmation_text, reply_markup=confirm_keyboard, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.confirmation)


@router.callback_query(UserRegistrationStates.confirmation)
async def process_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    if is_processing(callback_query.from_user.id):
        await callback_query.answer("⏳ Iltimos kuting...")
        return

    if callback_query.data == "confirm_no":
        await callback_query.message.edit_text("❌ Ro'yxatdan o'tish bekor qilindi.")
        await state.clear()
        await callback_query.message.answer("Qayta boshlash uchun /start bosing.")
        return

    async with user_lock(callback_query.from_user.id):
        existing = get_user_by_telegram_id(callback_query.from_user.id)
        if existing:
            await callback_query.answer("✅ Siz allaqachon ro'yxatdan o'tgansiz!", show_alert=True)
            await state.clear()
            await show_main_menu(callback_query.message, state, existing)
            return

        data = await state.get_data()
        db = Session()
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
            await callback_query.answer("✅ Ro'yxatdan o'tildi!", show_alert=True)
            user = db.query(User).options(
                joinedload(User.region),
                joinedload(User.district),
                joinedload(User.direction)
            ).filter(User.telegram_id == callback_query.from_user.id).first()
            await state.clear()
            await show_main_menu(callback_query.message, state, user)
        except Exception as e:
            db.rollback()
            await callback_query.answer(_err(e), show_alert=True)
        finally:
            db.close()


# ─── Asosiy menyu ─────────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🧪 Testni boshlash")
async def start_test_button(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return

    # Yo'nalish belgilanmagan — avval so'rash
    if not user.direction_id:
        keyboard = await get_directions_keyboard()
        db = Session()
        total = db.query(Direction).count()
        db.close()
        await message.answer(
            "📚 <b>Ta'lim yo'nalishingizni tanlang</b>\n\n"
            "Test boshlash uchun avval yo'nalishingizni belgilang:\n\n"
            f"<i>Jami {total} ta yo'nalish mavjud</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.set_state(TestSessionStates.waiting_for_direction)
        return

    await _show_test_confirmation(message, state, user)


async def _show_test_confirmation(message: types.Message, state: FSMContext, user: User):
    """Test tasdiqlash xabarini ko'rsatish"""
    confirmation_text = (
        f"📝 <b>Imtihonni boshlash</b>\n\n"
        f"<u>Imtihon haqida:</u>\n"
        f"⏱️ Vaqt: 180 daqiqa\n"
        f"❓ Savollar: 90 ta\n"
        f"  • 30 ta majburiy (Matematika, Tarix, Ona tili)\n"
        f"  • 60 ta ixtisoslashgan\n\n"
        f"<u>Yo'nalish:</u> {user.direction.name_uz}\n\n"
        f"<b>Boshlaysizmi?</b>"
    )
    await message.answer(
        confirmation_text,
        reply_markup=get_test_confirmation_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.test_confirmation)


# ─── Test oldida yo'nalish tanlash ────────────────────────────────────────────

@router.callback_query(TestSessionStates.waiting_for_direction, F.data.startswith("direction_page_"))
async def test_direction_page(callback_query: types.CallbackQuery, state: FSMContext):
    page = int(callback_query.data.split("_")[2])
    db = Session()
    total = db.query(Direction).count()
    db.close()
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    keyboard = await get_directions_keyboard(page)
    await callback_query.message.edit_text(
        f"📚 <b>Yo'nalishni tanlang</b>\n\n"
        f"<i>Sahifa {page + 1}/{total_pages}</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(TestSessionStates.waiting_for_direction, F.data == "direction_list_back")
async def test_direction_back(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer("Bekor qilindi")
    await callback_query.message.delete()
    await state.set_state(UserMainMenuStates.main_menu)
    user = get_user_by_telegram_id(callback_query.from_user.id)
    keyboard = await get_main_menu_keyboard()
    await callback_query.message.answer(
        f"🏠 Bosh menyu",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(TestSessionStates.waiting_for_direction, F.data.startswith("direction_"))
async def test_direction_selected(callback_query: types.CallbackQuery, state: FSMContext):
    if "_page_" in callback_query.data:
        return

    direction_id = callback_query.data.split("_")[1]
    db = Session()
    direction = db.query(Direction).filter(Direction.id == direction_id).first()

    if not direction:
        await callback_query.answer("❌ Yo'nalish topilmadi!")
        db.close()
        return

    # Foydalanuvchiga yo'nalishni saqlab qo'yish
    user_db = db.query(User).filter(
        User.telegram_id == callback_query.from_user.id
    ).first()
    if user_db:
        user_db.direction_id = direction_id
        db.commit()
    db.close()

    await callback_query.message.delete()
    user = get_user_by_telegram_id(callback_query.from_user.id)
    await callback_query.answer(f"✅ Yo'nalish tanlandi: {direction.name_uz[:30]}")
    await _show_test_confirmation(callback_query.message, state, user)


# ─── Test tasdiqlash — boshqa xabarlarni o'chirish ────────────────────────────

@router.message(TestSessionStates.test_confirmation)
async def block_messages_during_confirmation(message: types.Message, state: FSMContext):
    """
    Test tasdiqlash ekranida barcha xabarlarni o'chirib, faqat inline tugmalarni qabul qilish.
    """
    try:
        await message.delete()
    except Exception:
        pass
    # Yengil eslatma (o'chadi)
    try:
        reminder = await message.answer("⚠️ Iltimos, faqat «✅ Boshlash» yoki «❌ Bekor qil» tugmasini bosing.")
        import asyncio
        await asyncio.sleep(2)
        await reminder.delete()
    except Exception:
        pass


@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_start_confirm")
async def confirm_test_start(callback_query: types.CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id

    if is_processing(uid):
        await callback_query.answer("⏳ Test boshlanmoqda, kuting...")
        return

    async with user_lock(uid):
        user = get_user_by_telegram_id(uid)
        if not user:
            await callback_query.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
            return

        db = Session()
        active = db.query(UserTestParticipation).filter(
            UserTestParticipation.user_id == user.id,
            UserTestParticipation.status == 'active'
        ).first()
        db.close()

        if active:
            await callback_query.answer("⚠️ Siz allaqachon test boshlagan edingiz!", show_alert=True)
            return

        try:
            participation = TestService.create_participation(user.id, user.direction_id)
            questions = TestService.get_test_questions(user.direction_id)

            if not questions:
                await callback_query.answer("❌ Savollar topilmadi!", show_alert=True)
                return

            await state.update_data(
                participation_id=participation.id,
                test_session_id=participation.test_session_id,
                questions=[(q.id, q.text_uz, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_answer) for q in questions],
                current_question_index=0,
                answers={}
            )

            await callback_query.message.delete()
            question = questions[0]
            question_text = (
                f"<b>Savol #1/{len(questions)}</b>\n\n"
                f"{question.text_uz}\n\n"
                f"A) {question.option_a}\n"
                f"B) {question.option_b}\n"
                f"C) {question.option_c}\n"
                f"D) {question.option_d}"
            )
            await callback_query.message.answer(
                question_text, reply_markup=get_test_answer_keyboard(), parse_mode="HTML"
            )
            await state.set_state(TestSessionStates.test_active)
        except Exception as e:
            logger.error("confirm_test_start xato: %s", traceback.format_exc())
            await callback_query.answer(_err(e), show_alert=True)


@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_cancel")
async def cancel_test(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await state.set_state(UserMainMenuStates.main_menu)
    user = get_user_by_telegram_id(callback_query.from_user.id)
    keyboard = await get_main_menu_keyboard()
    await callback_query.message.answer(
        f"🏠 Bosh menyu\n\nAssalomu alaykum, <b>{user.first_name} {user.last_name}</b>!",
        reply_markup=keyboard,
        parse_mode="HTML"
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
        answer = callback_query.data.split("_")[1]
        data = await state.get_data()
        current_index = data.get('current_question_index', 0)
        questions = data.get('questions', [])
        answers = data.get('answers', {})
        participation_id = data.get('participation_id')
        test_session_id = data.get('test_session_id')

        if not questions or participation_id is None:
            await callback_query.answer("❌ Test ma'lumotlari topilmadi. /start bosing.", show_alert=True)
            await state.clear()
            return

        if current_index >= len(questions):
            await callback_query.answer()
            return

        if answer != "skip":
            question_id = questions[current_index][0]
            answers[str(current_index)] = answer
            user = get_user_by_telegram_id(uid)
            if user:
                TestService.save_answer(
                    participation_id=participation_id,
                    user_id=user.id,
                    test_session_id=test_session_id,
                    question_id=question_id,
                    selected_answer=answer
                )
        else:
            answers[str(current_index)] = None

        current_index += 1

        if current_index >= len(questions):
            score_info = TestService.complete_test(participation_id)
            try:
                await callback_query.message.delete()
            except Exception:
                pass
            if score_info:
                pct = (
                    score_info['correct_count'] / score_info['total_questions'] * 100
                    if score_info['total_questions'] > 0 else 0
                )
                result_text = (
                    f"✅ <b>Imtihon tugallandi!</b>\n\n"
                    f"• 📈 Ball: {score_info['score']}\n"
                    f"• ✅ To'g'ri: {score_info['correct_count']}/{score_info['total_questions']}\n"
                    f"• 📊 Foiz: {pct:.1f}%\n\n"
                    f"🏆 Reytingda o'zingizni tekshiring!"
                )
            else:
                result_text = "✅ Imtihon tugallandi!"
            await callback_query.message.answer(
                result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML"
            )
            await state.set_state(UserMainMenuStates.main_menu)
        else:
            question = questions[current_index]
            question_text = (
                f"<b>Savol #{current_index + 1}/{len(questions)}</b>\n\n"
                f"{question[1]}\n\n"
                f"A) {question[2]}\nB) {question[3]}\nC) {question[4]}\nD) {question[5]}"
            )
            await state.update_data(current_question_index=current_index, answers=answers)
            try:
                await callback_query.message.edit_text(
                    question_text, reply_markup=get_test_answer_keyboard(), parse_mode="HTML"
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
        data = await state.get_data()
        participation_id = data.get('participation_id')

        if not participation_id:
            await callback_query.answer("❌ Test ma'lumotlari yo'q.", show_alert=True)
            await state.clear()
            return

        score_info = TestService.complete_test(participation_id)
        try:
            await callback_query.message.delete()
        except Exception:
            pass

        if score_info:
            pct = (
                score_info['correct_count'] / score_info['total_questions'] * 100
                if score_info['total_questions'] > 0 else 0
            )
            result_text = (
                f"✅ <b>Imtihon tugallandi!</b>\n\n"
                f"• 📈 Ball: {score_info['score']}\n"
                f"• ✅ To'g'ri: {score_info['correct_count']}/{score_info['total_questions']}\n"
                f"• 📊 Foiz: {pct:.1f}%"
            )
        else:
            result_text = "✅ Imtihon tugallandi!"

        await callback_query.message.answer(
            result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML"
        )
        await state.set_state(UserMainMenuStates.main_menu)
        await callback_query.answer()


# ─── Asosiy menyu — boshqa tugmalar ──────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "📊 Natijalarim")
async def show_my_results(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    db = Session()
    try:
        scores = db.query(Score).filter(
            Score.user_id == user.id
        ).order_by(Score.created_at.desc()).all()
        if not scores:
            await message.answer(
                "📊 <b>Hali imtihon topshirmagan edingiz.</b>\n\n"
                "🧪 Testni boshlash uchun \"Testni boshlash\" tugmasini bosing.",
                parse_mode="HTML"
            )
            return
        result_text = "📊 <b>Sizning natijalaringiz:</b>\n\n"
        for i, score in enumerate(scores[:5], 1):
            pct = (score.correct_count / score.total_questions * 100) if score.total_questions > 0 else 0
            result_text += (
                f"{i}. <b>Sana:</b> {score.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   📈 Ball: {score.score} | ✅ {score.correct_count}/{score.total_questions} ({pct:.1f}%)\n\n"
            )
        await message.answer(result_text, parse_mode="HTML")
    except Exception as e:
        logger.error("Xato: %s", traceback.format_exc()); await message.answer(f"❌ Ichki xato yuz berdi. Logni tekshiring.")
    finally:
        db.close()


@router.message(UserMainMenuStates.main_menu, F.text == "🏆 Reyting")
async def show_leaderboard(message: types.Message, state: FSMContext):
    db = Session()
    try:
        top_scores = db.query(Score).order_by(Score.score.desc()).limit(10).all()
        if not top_scores:
            await message.answer("🏆 <b>Reytingda hali hech kim yo'q.</b>", parse_mode="HTML")
            return
        text = "🏆 <b>Reyting (Top 10)</b>\n\n"
        for i, score in enumerate(top_scores, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            u = score.user
            text += (
                f"{medal} <b>{u.first_name} {u.last_name}</b>\n"
                f"   📊 Ball: {score.score} | ✅ {score.correct_count}/{score.total_questions}\n\n"
            )
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error("Xato: %s", traceback.format_exc()); await message.answer(f"❌ Ichki xato yuz berdi. Logni tekshiring.")
    finally:
        db.close()


@router.message(UserMainMenuStates.main_menu, F.text == "❓ Yordam")
async def show_help(message: types.Message, state: FSMContext):
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        "<b>Imtihon haqida:</b>\n"
        "• 180 daqiqa davom etadi\n"
        "• Jami 90 ta savol\n"
        "• 30 ta majburiy + 60 ta ixtisoslashgan\n\n"
        "<b>Ball tizimi:</b>\n"
        "• Majburiy: 1.1 ball/savol\n"
        "• Ixtisoslashgan 1-fan: 3.1 ball/savol\n"
        "• Ixtisoslashgan 2-fan: 2.1 ball/savol\n\n"
        "<b>Profil:</b> Yo'nalish va F.I.SH ni «👤 Profilim» bo'limidan o'zgartirish mumkin.",
        parse_mode="HTML"
    )


# ─── Profil ───────────────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "👤 Profilim")
async def show_profile(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    db = Session()
    try:
        scores = db.query(Score).filter(Score.user_id == user.id).all()
        best_score = max((s.score for s in scores), default=0)
        direction_name = user.direction.name_uz if user.direction else "❗ Belgilanmagan"
        full_name = f"{user.first_name} {user.last_name}".strip()

        text = (
            f"👤 <b>Profil</b>\n\n"
            f"<b>Shaxsiy ma'lumotlar:</b>\n"
            f"• 📝 F.I.SH: {full_name}\n"
            f"• 📱 Telefon: {user.phone}\n"
            f"• 📍 Viloyat: {user.region.name_uz}\n"
            f"• 📍 Tuman: {user.district.name_uz}\n"
            f"• 📚 Yo'nalish: {direction_name}\n\n"
            f"<b>Statistika:</b>\n"
            f"• 🧪 Imtihon soni: {len(scores)}\n"
            f"• 📊 Eng yuqori ball: {best_score}\n"
            f"• 📅 Ro'yxatdan o'tish: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            f"<b>Tahrirlash:</b>"
        )
        await message.answer(text, reply_markup=get_profile_settings_keyboard(), parse_mode="HTML")
    except Exception as e:
        logger.error("Xato: %s", traceback.format_exc()); await message.answer(f"❌ Ichki xato yuz berdi. Logni tekshiring.")
    finally:
        db.close()


@router.callback_query(F.data == "profile_back")
async def profile_back(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    await state.set_state(UserMainMenuStates.main_menu)


# ─── F.I.SH tahrirlash ────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile_edit_name")
async def profile_edit_name_start(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "✏️ <b>F.I.SH ni tahrirlash</b>\n\n"
        "Yangi to'liq ismingizni kiriting:\n"
        "<i>Misol: Aliyev Jasur Bahodirovich</i>",
        parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.edit_full_name)


@router.message(ProfileEditStates.edit_full_name)
async def profile_edit_name_save(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Iltimos, to'liq ismingizni kiriting (kamida 2 ta harf)!")
        return

    full_name = message.text.strip()
    first, last = _split_full_name(full_name)

    db = Session()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user:
            user.first_name = first
            user.last_name = last
            db.commit()
        await state.set_state(UserMainMenuStates.main_menu)
        await message.answer(
            f"✅ F.I.SH yangilandi: <b>{full_name}</b>",
            parse_mode="HTML"
        )
        # Yangilangan profilni ko'rsatish
        user_fresh = get_user_by_telegram_id(message.from_user.id)
        await show_profile(message, state)
    except Exception as e:
        db.rollback()
        logger.error("Xato: %s", traceback.format_exc()); await message.answer(f"❌ Ichki xato yuz berdi. Logni tekshiring.")
    finally:
        db.close()


# ─── Yo'nalish tahrirlash (profil) ───────────────────────────────────────────

@router.callback_query(F.data == "profile_edit_direction")
async def profile_edit_direction_start(callback_query: types.CallbackQuery, state: FSMContext):
    db = Session()
    total = db.query(Direction).count()
    db.close()
    keyboard = await get_directions_keyboard()
    await callback_query.message.edit_text(
        f"📚 <b>Yo'nalishni o'zgartirish</b>\n\n"
        f"Yangi yo'nalishingizni tanlang:\n"
        f"<i>Jami {total} ta yo'nalish</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.edit_direction)


@router.callback_query(ProfileEditStates.edit_direction, F.data.startswith("direction_page_"))
async def profile_direction_page(callback_query: types.CallbackQuery, state: FSMContext):
    page = int(callback_query.data.split("_")[2])
    db = Session()
    total = db.query(Direction).count()
    db.close()
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    keyboard = await get_directions_keyboard(page)
    await callback_query.message.edit_text(
        f"📚 <b>Yo'nalishni o'zgartirish</b>\n\n"
        f"<i>Sahifa {page + 1}/{total_pages}</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(ProfileEditStates.edit_direction, F.data == "direction_list_back")
async def profile_direction_back(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserMainMenuStates.main_menu)
    user = get_user_by_telegram_id(callback_query.from_user.id)
    db = Session()
    scores = db.query(Score).filter(Score.user_id == user.id).all()
    best_score = max((s.score for s in scores), default=0)
    db.close()
    direction_name = user.direction.name_uz if user.direction else "❗ Belgilanmagan"
    full_name = f"{user.first_name} {user.last_name}".strip()
    text = (
        f"👤 <b>Profil</b>\n\n"
        f"• 📝 F.I.SH: {full_name}\n"
        f"• 📱 Telefon: {user.phone}\n"
        f"• 📍 Viloyat: {user.region.name_uz}\n"
        f"• 📍 Tuman: {user.district.name_uz}\n"
        f"• 📚 Yo'nalish: {direction_name}\n\n"
        f"• 🧪 Imtihon soni: {len(scores)}\n"
        f"• 📊 Eng yuqori ball: {best_score}\n\n"
        f"<b>Tahrirlash:</b>"
    )
    await callback_query.message.edit_text(
        text, reply_markup=get_profile_settings_keyboard(), parse_mode="HTML"
    )


@router.callback_query(ProfileEditStates.edit_direction, F.data.startswith("direction_"))
async def profile_direction_selected(callback_query: types.CallbackQuery, state: FSMContext):
    if "_page_" in callback_query.data:
        return

    direction_id = callback_query.data.split("_")[1]
    db = Session()
    direction = db.query(Direction).filter(Direction.id == direction_id).first()
    if not direction:
        await callback_query.answer("❌ Yo'nalish topilmadi!")
        db.close()
        return

    user = db.query(User).filter(User.telegram_id == callback_query.from_user.id).first()
    if user:
        user.direction_id = direction_id
        db.commit()
    db.close()

    await callback_query.answer(f"✅ Yo'nalish saqlandi!")
    await state.set_state(UserMainMenuStates.main_menu)

    user_fresh = get_user_by_telegram_id(callback_query.from_user.id)
    direction_name = user_fresh.direction.name_uz if user_fresh.direction else "—"
    full_name = f"{user_fresh.first_name} {user_fresh.last_name}".strip()

    db2 = Session()
    scores = db2.query(Score).filter(Score.user_id == user_fresh.id).all()
    best_score = max((s.score for s in scores), default=0)
    db2.close()

    text = (
        f"👤 <b>Profil</b>\n\n"
        f"• 📝 F.I.SH: {full_name}\n"
        f"• 📱 Telefon: {user_fresh.phone}\n"
        f"• 📍 Viloyat: {user_fresh.region.name_uz}\n"
        f"• 📍 Tuman: {user_fresh.district.name_uz}\n"
        f"• 📚 Yo'nalish: {direction_name}\n\n"
        f"• 🧪 Imtihon soni: {len(scores)}\n"
        f"• 📊 Eng yuqori ball: {best_score}\n\n"
        f"<b>Tahrirlash:</b>"
    )
    await callback_query.message.edit_text(
        text, reply_markup=get_profile_settings_keyboard(), parse_mode="HTML"
    )


# ─── Test natijasi menyusidan ─────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🧪 Yana test qol")
async def another_test(message: types.Message, state: FSMContext):
    await start_test_button(message, state)


@router.message(UserMainMenuStates.main_menu, F.text == "📊 Natijalarni ko'rish")
async def view_results_from_test(message: types.Message, state: FSMContext):
    await show_my_results(message, state)


@router.message(UserMainMenuStates.main_menu, F.text == "🏠 Bosh menyu")
async def return_to_main_menu(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    await state.set_state(UserMainMenuStates.main_menu)
    keyboard = await get_main_menu_keyboard()
    await message.answer(
        f"🏛 <b>DTM Test Bot</b>\n\nAssalomu alaykum, <b>{user.first_name} {user.last_name}</b>!\n\n"
        f"<b>Nima qilmoqchi ekaningizni tanlang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )