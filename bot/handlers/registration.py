from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import Session
from database.models import User, Region, District, Direction, Score
from bot.states import UserRegistrationStates, UserMainMenuStates, TestSessionStates
from bot.keyboards import (
    get_regions_keyboard,
    get_districts_keyboard,
    get_directions_keyboard,
    get_phone_keyboard,
    get_main_menu_keyboard
)
from utils.test_service import TestService
from sqlalchemy.orm import joinedload
import re

router = Router()


def get_user_by_telegram_id(telegram_id: int) -> User:
    db = Session()
    user = db.query(User).options(
        joinedload(User.region),
        joinedload(User.district),
        joinedload(User.direction)
    ).filter(User.telegram_id == telegram_id).first()
    db.close()
    return user


async def start_registration(message: types.Message, state: FSMContext):
    await message.answer(
        "📝 <b>Ro'yxatdan o'tish</b>\n\n"
        "Assalomu alaykum! Iltimos, quyidagi ma'lumotlarni kiriting:\n\n"
        "👤 <b>Ism:</b>",
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_first_name)


async def show_main_menu(message: types.Message, state: FSMContext, user: User):
    keyboard = await get_main_menu_keyboard()
    text = (
        f"🏛 <b>DTM Test Bot</b>\n\n"
        f"Assalomu alaykum, <b>{user.first_name} {user.last_name}</b>!\n\n"
        f"<b>Shaxsiy ma'lumotlar:</b>\n"
        f"• 📱 Telefon: {user.phone}\n"
        f"• 📍 Viloyat: {user.region.name_uz}\n"
        f"• 📍 Tuman: {user.district.name_uz}\n"
        f"• 📚 Yo'nalish: {user.direction.name_uz if user.direction else 'Tanlanmagan'}\n\n"
        f"<b>Nima qilmoqchi ekaningizni tanlang:</b>"
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserMainMenuStates.main_menu)


# ─── /start ──────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """StateFilter yo'q — har qanday holatda /start ishlaydi"""
    await state.clear()
    user = get_user_by_telegram_id(message.from_user.id)
    if user:
        await show_main_menu(message, state, user)
    else:
        await start_registration(message, state)


# ─── Ro'yxatdan o'tish ───────────────────────────────────────────────────────

@router.message(UserRegistrationStates.waiting_for_first_name)
async def process_first_name(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Ism kamida 2 ta harfdan iborat bo'lishi kerak!")
        return
    await state.update_data(first_name=message.text.strip())
    await message.answer("👤 <b>Familiya:</b>", parse_mode="HTML")
    await state.set_state(UserRegistrationStates.waiting_for_last_name)


@router.message(UserRegistrationStates.waiting_for_last_name)
async def process_last_name(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Familiya kamida 2 ta harfdan iborat bo'lishi kerak!")
        return
    await state.update_data(last_name=message.text.strip())
    keyboard = await get_phone_keyboard()
    await message.answer(
        "📱 <b>Telefon raqam:</b>\n\nIltimos, telefon raqamini yuboring yoki tugmani bosing:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_phone)


@router.message(UserRegistrationStates.waiting_for_phone, F.content_type == ContentType.CONTACT)
async def process_phone_contact(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    keyboard = await get_regions_keyboard()
    await message.answer("📍 <b>Viloyatni tanlang:</b>", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserRegistrationStates.waiting_for_region)


@router.message(UserRegistrationStates.waiting_for_phone)
async def process_phone_text(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not re.match(r'^[\d\+\-\s\(\)]{10,}$', phone):
        await message.answer("❌ Telefon raqam noto'g'ri. Iltimos, to'g'ri raqamni kiriting!")
        return
    await state.update_data(phone=phone)
    keyboard = await get_regions_keyboard()
    await message.answer("📍 <b>Viloyatni tanlang:</b>", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserRegistrationStates.waiting_for_region)


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


@router.callback_query(UserRegistrationStates.waiting_for_district, F.data.startswith("district_"))
async def process_district_selection(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "region_back":
        keyboard = await get_regions_keyboard()
        await callback_query.message.edit_text(
            "📍 <b>Viloyatni tanlang:</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.set_state(UserRegistrationStates.waiting_for_region)
        return
    district_id = int(callback_query.data.split("_")[1])
    db = Session()
    district = db.query(District).filter(District.id == district_id).first()
    db.close()
    if not district:
        await callback_query.answer("❌ Tuman topilmadi!")
        return
    await state.update_data(district_id=district_id)
    keyboard = await get_directions_keyboard()
    await callback_query.message.edit_text(
        f"📚 <b>Ta'lim yo'nalishini tanlang ({district.name_uz}):</b>\n\n"
        "<i>Sahifa 1 — 10 ta ko'rsatilmoqda...</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_direction)


@router.callback_query(UserRegistrationStates.waiting_for_direction, F.data.startswith("direction_page_"))
async def process_direction_page(callback_query: types.CallbackQuery, state: FSMContext):
    """Sahifalar o'rtasida o'tish — FAQAT shu, boshqa kod yo'q"""
    page = int(callback_query.data.split("_")[2])
    data = await state.get_data()
    district_id = data.get('district_id')

    db = Session()
    district = db.query(District).filter(District.id == district_id).first()
    total = db.query(Direction).count()
    db.close()

    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start = page * per_page + 1
    end = min((page + 1) * per_page, total)

    keyboard = await get_directions_keyboard(page)
    await callback_query.message.edit_text(
        f"📚 <b>Ta'lim yo'nalishini tanlang ({district.name_uz if district else ''}):</b>\n\n"
        f"<i>Sahifa {page + 1}/{total_pages} — {start}-{end} ta ko'rsatilmoqda</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(UserRegistrationStates.waiting_for_direction, F.data.startswith("direction_"))
async def process_direction_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Yo'nalish tanlash — direction_page_ va direction_back ni o'tkazib yuborish"""
    if "_page_" in callback_query.data or callback_query.data == "direction_back":
        return

    direction_id = callback_query.data.split("_")[1]
    db = Session()
    direction = db.query(Direction).filter(Direction.id == direction_id).first()
    db.close()

    if not direction:
        await callback_query.answer("❌ Yo'nalish topilmadi!")
        return

    await state.update_data(direction_id=direction_id)
    data = await state.get_data()

    db2 = Session()
    region = db2.query(Region).filter(Region.id == data.get('region_id')).first()
    district = db2.query(District).filter(District.id == data.get('district_id')).first()
    db2.close()

    confirmation_text = (
        f"✅ <b>Ro'yxatdan o'tish tasdiqlash</b>\n\n"
        f"<b>Sizning ma'lumotlar:</b>\n"
        f"• 👤 Ism: {data['first_name']} {data['last_name']}\n"
        f"• 📱 Telefon: {data['phone']}\n"
        f"• 📍 Viloyat: {region.name_uz if region else '—'}\n"
        f"• 📍 Tuman: {district.name_uz if district else '—'}\n"
        f"• 📚 Yo'nalish: {direction.name_uz}\n\n"
        f"<b>Ro'yxatdan o'tishni tasdiqlaysizmi?</b>"
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
    if callback_query.data == "confirm_no":
        await callback_query.message.edit_text("❌ Ro'yxatdan o'tish bekor qilindi.")
        await state.clear()
        await callback_query.message.answer("Qayta boshlash uchun /start buyrug'ini yuboring.")
        return

    data = await state.get_data()
    db = Session()
    try:
        new_user = User(
            telegram_id=callback_query.from_user.id,
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone=data['phone'],
            region_id=data['region_id'],
            district_id=data['district_id'],
            direction_id=data['direction_id']
        )
        db.add(new_user)
        db.commit()
        await callback_query.answer("✅ Ro'yxatdan o'tish tugallandi!", show_alert=True)
        user = db.query(User).options(
            joinedload(User.region),
            joinedload(User.district),
            joinedload(User.direction)
        ).filter(User.telegram_id == callback_query.from_user.id).first()
        await state.clear()
        await show_main_menu(callback_query.message, state, user)
    except Exception as e:
        db.rollback()
        await callback_query.answer(f"❌ Xato: {str(e)}", show_alert=True)
    finally:
        db.close()


# ─── Asosiy menyu ─────────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🧪 Testni boshlash")
async def start_test_button(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    if not user.direction_id:
        await message.answer("❌ Iltimos, avval yo'nalishni tanlang!")
        return
    confirmation_text = (
        f"📝 <b>Imtihondan o'tishni boshlash</b>\n\n"
        f"<u>Imtihon haqida ma'lumot:</u>\n"
        f"⏱️ Vaqt: 180 daqiqa\n"
        f"❓ Savollar soni: 90 ta\n"
        f"📊 Tarkib:\n"
        f"  • 30 ta majburiy savol (Matematika, Tarix, Ona tili)\n"
        f"  • 60 ta ixtisoslashgan savol\n\n"
        f"<u>Yo'nalish:</u> {user.direction.name_uz}\n\n"
        f"<b>Imtihondan o'tishni boshlaysizmi?</b>"
    )
    from bot.keyboards import get_test_confirmation_keyboard
    await message.answer(confirmation_text, reply_markup=get_test_confirmation_keyboard(), parse_mode="HTML")
    await state.set_state(TestSessionStates.test_confirmation)


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
                "📊 <b>Siz hali imtihondan o'tmagan edingiz.</b>\n\n"
                "🧪 Testni boshlash uchun \"Testni boshlash\" tugmasini bosing.",
                parse_mode="HTML"
            )
            return
        result_text = "📊 <b>Sizning natijalaringiz:</b>\n\n"
        for i, score in enumerate(scores[:5], 1):
            pct = (score.correct_count / score.total_questions * 100) if score.total_questions > 0 else 0
            result_text += (
                f"{i}. <b>Sana:</b> {score.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   📈 Ball: {score.score}\n"
                f"   ✅ To'g'ri: {score.correct_count}/{score.total_questions} ({pct:.1f}%)\n\n"
            )
        await message.answer(result_text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)}")
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
        await message.answer(f"❌ Xato: {str(e)}")
    finally:
        db.close()


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
        text = (
            f"👤 <b>Sizning profil</b>\n\n"
            f"<b>Shaxsiy ma'lumotlar:</b>\n"
            f"• 📝 F.I.SH: {user.first_name} {user.last_name}\n"
            f"• 📱 Telefon: {user.phone}\n"
            f"• 📍 Viloyat: {user.region.name_uz}\n"
            f"• 📍 Tuman: {user.district.name_uz}\n"
            f"• 📚 Yo'nalish: {user.direction.name_uz if user.direction else 'Tanlanmagan'}\n\n"
            f"<b>Statistika:</b>\n"
            f"• 🧪 Imtihon soni: {len(scores)}\n"
            f"• 📊 Eng yuqori ball: {best_score}\n"
            f"• 📅 Ro'yxatdan o'tish: {user.created_at.strftime('%d.%m.%Y')}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)}")
    finally:
        db.close()


@router.message(UserMainMenuStates.main_menu, F.text == "⚙️ Sozlamalar")
async def show_settings(message: types.Message, state: FSMContext):
    await message.answer("⚙️ <b>Sozlamalar</b>\n\nHozircha sozlamalar mavjud emas.", parse_mode="HTML")


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
        "• Ixtisoslashgan 2-fan: 2.1 ball/savol",
        parse_mode="HTML"
    )


# ─── Test jarayoni ────────────────────────────────────────────────────────────

@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_start_confirm")
async def confirm_test_start(callback_query: types.CallbackQuery, state: FSMContext):
    user = get_user_by_telegram_id(callback_query.from_user.id)
    if not user:
        await callback_query.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return
    try:
        participation = TestService.create_participation(user.id, user.direction_id)
        questions = TestService.get_test_questions(user.direction_id)

        if not questions:
            await callback_query.answer("❌ Savollar topilmadi!", show_alert=True)
            return

        # state ga participation.test_session_id ham saqlaymiz
        await state.update_data(
            participation_id=participation.id,
            test_session_id=participation.test_session_id,  # ← to'g'rilandi
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
        from bot.keyboards import get_test_answer_keyboard
        await callback_query.message.answer(question_text, reply_markup=get_test_answer_keyboard(), parse_mode="HTML")
        await state.set_state(TestSessionStates.test_active)
    except Exception as e:
        await callback_query.answer(f"❌ Xato: {str(e)}", show_alert=True)


@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_cancel")
async def cancel_test(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await callback_query.message.delete()
        await state.set_state(UserMainMenuStates.main_menu)
        user = get_user_by_telegram_id(callback_query.from_user.id)
        keyboard = await get_main_menu_keyboard()
        await callback_query.message.answer(
            f"🏠 Bosh menyu\n\nAssalomu alaykum, <b>{user.first_name} {user.last_name}</b>!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        await callback_query.answer(f"❌ Xato: {str(e)}", show_alert=True)


@router.callback_query(TestSessionStates.test_active, F.data.startswith("answer_"))
async def handle_test_answer(callback_query: types.CallbackQuery, state: FSMContext):
    answer = callback_query.data.split("_")[1]
    data = await state.get_data()
    current_index = data.get('current_question_index', 0)
    questions = data.get('questions', [])
    answers = data.get('answers', {})
    participation_id = data.get('participation_id')
    test_session_id = data.get('test_session_id')

    if answer != "skip":
        question_id = questions[current_index][0]
        answers[str(current_index)] = answer
        # to'g'ri signature bilan chaqirish
        TestService.save_answer(
            participation_id=participation_id,
            user_id=callback_query.from_user.id,
            test_session_id=test_session_id,
            question_id=question_id,
            selected_answer=answer
        )
    else:
        answers[str(current_index)] = None

    current_index += 1

    if current_index >= len(questions):
        score_info = TestService.complete_test(participation_id)
        await callback_query.message.delete()
        if score_info:
            pct = (score_info['correct_count'] / score_info['total_questions'] * 100) if score_info['total_questions'] > 0 else 0
            result_text = (
                f"✅ <b>Imtihon tugallandi!</b>\n\n"
                f"📊 <b>Natijalaringiz:</b>\n"
                f"• 📈 Ball: {score_info['score']}\n"
                f"• ✅ To'g'ri: {score_info['correct_count']}/{score_info['total_questions']}\n"
                f"• 📊 Foiz: {pct:.1f}%\n\n"
                f"🏆 Reytingda o'zingizning o'riningizni tekshiring!"
            )
        else:
            result_text = "✅ Imtihon tugallandi! Natijalarni ko'rish uchun \"Natijalarim\" tugmasini bosing."
        from bot.keyboards import get_test_results_keyboard
        await callback_query.message.answer(result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML")
        await state.set_state(UserMainMenuStates.main_menu)
    else:
        question = questions[current_index]
        question_text = (
            f"<b>Savol #{current_index + 1}/{len(questions)}</b>\n\n"
            f"{question[1]}\n\n"
            f"A) {question[2]}\nB) {question[3]}\nC) {question[4]}\nD) {question[5]}"
        )
        await state.update_data(current_question_index=current_index, answers=answers)
        from bot.keyboards import get_test_answer_keyboard
        await callback_query.message.edit_text(question_text, reply_markup=get_test_answer_keyboard(), parse_mode="HTML")

    await callback_query.answer()


@router.callback_query(TestSessionStates.test_active, F.data == "test_finish")
async def finish_test_early(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    participation_id = data.get('participation_id')
    score_info = TestService.complete_test(participation_id)
    await callback_query.message.delete()
    if score_info:
        pct = (score_info['correct_count'] / score_info['total_questions'] * 100) if score_info['total_questions'] > 0 else 0
        result_text = (
            f"✅ <b>Imtihon tugallandi!</b>\n\n"
            f"• 📈 Ball: {score_info['score']}\n"
            f"• ✅ To'g'ri: {score_info['correct_count']}/{score_info['total_questions']}\n"
            f"• 📊 Foiz: {pct:.1f}%"
        )
    else:
        result_text = "✅ Imtihon tugallandi!"
    from bot.keyboards import get_test_results_keyboard
    await callback_query.message.answer(result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML")
    await state.set_state(UserMainMenuStates.main_menu)
    await callback_query.answer()


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