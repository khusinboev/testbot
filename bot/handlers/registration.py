from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import Session
from database.models import User, Region, District, Direction, TestSession, Score
from bot.states import UserRegistrationStates, UserMainMenuStates, TestSessionStates
from bot.keyboards import (
    get_regions_keyboard, 
    get_districts_keyboard,
    get_directions_keyboard,
    get_phone_keyboard,
    get_main_menu_keyboard
)
from utils.test_service import TestService
import re

router = Router()

def get_user_by_telegram_id(telegram_id: int) -> User:
    """Get user from database by telegram ID with relationships loaded"""
    db = Session()
    user = db.query(User).options(
        db.joinedload(User.region),
        db.joinedload(User.district),
        db.joinedload(User.direction)
    ).filter(User.telegram_id == telegram_id).first()
    db.close()
    return user

async def start_registration(message: types.Message, state: FSMContext):
    """Start user registration flow"""
    await message.answer(
        "📝 <b>Ro'yxatdan o'tish</b>\n\n"
        "Assalomu alaykum! Iltimos, quyidagi ma'lumotlarni kiriting:\n\n"
        "👤 <b>Ism:</b>",
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_first_name)

async def show_main_menu(message: types.Message, state: FSMContext, user: User):
    """Show main menu for registered user"""
    keyboard = await get_main_menu_keyboard()
    text = f"""
🏛 <b>DTM Test Bot</b>

Assalomu alaykum, <b>{user.first_name} {user.last_name}</b>!

<b>Shaxsiy ma'lumotlar:</b>
• 📱 Telefon: {user.phone}
• 📍 Viloyat: {user.region.name_uz}
• 📍 Tuman: {user.district.name_uz}
• 📚 Yo'nalish: {user.direction.name_uz if user.direction else 'Tanlanmagan'}

<b>Nima qilmoqchi ekaningizni tanlang:</b>
"""
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserMainMenuStates.main_menu)

@router.message(Command("start"), StateFilter(None))
async def cmd_start(message: types.Message, state: FSMContext):
    """Handle /start command with registration check"""
    telegram_id = message.from_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if user:
        # User is registered, show main menu
        await show_main_menu(message, state, user)
    else:
        # User is not registered, start registration flow
        await start_registration(message, state)

@router.message(UserRegistrationStates.waiting_for_first_name)
async def process_first_name(message: types.Message, state: FSMContext):
    """Process first name input"""
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Ism kamida 2 ta harfdan iborat bo'lishi kerak!")
        return
    
    await state.update_data(first_name=message.text.strip())
    await message.answer("👤 <b>Familiya:</b>", parse_mode="HTML")
    await state.set_state(UserRegistrationStates.waiting_for_last_name)

@router.message(UserRegistrationStates.waiting_for_last_name)
async def process_last_name(message: types.Message, state: FSMContext):
    """Process last name input"""
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Familiya kamida 2 ta harfdan iborat bo'lishi kerak!")
        return
    
    await state.update_data(last_name=message.text.strip())
    keyboard = await get_phone_keyboard()
    await message.answer(
        "📱 <b>Telefon raqam:</b>\n\n"
        "Iltimos, telefon raqamini yuboring yoki quyidagi tugmani bosing:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_phone)

@router.message(UserRegistrationStates.waiting_for_phone, F.content_type == ContentType.CONTACT)
async def process_phone_contact(message: types.Message, state: FSMContext):
    """Process phone number from contact"""
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    # Ask for region
    keyboard = await get_regions_keyboard()
    await message.answer(
        "📍 <b>Viloyatni tanlang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_region)

@router.message(UserRegistrationStates.waiting_for_phone)
async def process_phone_text(message: types.Message, state: FSMContext):
    """Process phone number from text"""
    phone = message.text.strip()
    
    # Validate phone number
    if not re.match(r'^[\d\+\-\s\(\)]{10,}$', phone):
        await message.answer("❌ Telefon raqam noto'g'ri. Iltimos, to'g'ri raqamni kiriting!")
        return
    
    await state.update_data(phone=phone)
    
    # Ask for region
    keyboard = await get_regions_keyboard()
    await message.answer(
        "📍 <b>Viloyatni tanlang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_region)

@router.callback_query(UserRegistrationStates.waiting_for_region, F.data.startswith("region_"))
async def process_region_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Process region selection"""
    region_id = int(callback_query.data.split("_")[1])
    
    db = Session()
    region = db.query(Region).filter(Region.id == region_id).first()
    db.close()
    
    if not region:
        await callback_query.answer("❌ Viloyat topilmadi!")
        return
    
    await state.update_data(region_id=region_id)
    
    # Ask for district
    keyboard = await get_districts_keyboard(region_id)
    await callback_query.message.edit_text(
        f"📍 <b>Tumanni tanlang ({region.name_uz}):</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_district)

@router.callback_query(UserRegistrationStates.waiting_for_district, F.data.startswith("district_"))
async def process_district_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Process district selection"""
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
    
    # Ask for direction
    keyboard = await get_directions_keyboard()
    await callback_query.message.edit_text(
        f"📚 <b>Ta'lim yo'nalishini tanlang ({district.name_uz}):</b>\n\n"
        "<i>Sahifa 1/17 - 167 ta yo'nalishdan 10 tasini ko'rsatmoqda...</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_direction)

@router.callback_query(UserRegistrationStates.waiting_for_direction, F.data.startswith("direction_page_"))
async def process_direction_page(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle direction pagination"""
    page = int(callback_query.data.split("_")[2])
    
    data = await state.get_data()
    district_id = data.get('district_id')
    
    db = Session()
    district = db.query(District).filter(District.id == district_id).first()
    db.close()
    
    if not district:
        await callback_query.answer("❌ Tuman ma'lumotlari topilmadi!")
        return
    
    keyboard = await get_directions_keyboard(page)
    total_pages = 17  # Approximately 167 directions / 10 per page
    
    await callback_query.message.edit_text(
        f"📚 <b>Ta'lim yo'nalishini tanlang ({district.name_uz}):</b>\n\n"
        f"<i>Sahifa {page+1}/{total_pages} - 167 ta yo'nalishdan {page*10+1}-{min((page+1)*10, 167)} tasini ko'rsatmoqda...</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    """Process direction selection"""
    direction_id = callback_query.data.split("_")[1]
    
    db = Session()
    direction = db.query(Direction).filter(Direction.id == direction_id).first()
    db.close()
    
    if not direction:
        await callback_query.answer("❌ Yo'nalish topilmadi!")
        return
    
    await state.update_data(direction_id=direction_id)
    
    # Show confirmation
    data = await state.get_data()
    
    confirmation_text = f"""
✅ <b>Ro'yxatdan o'tish tasdiqlash</b>

<b>Sizning ma'lumotlar:</b>
• 👤 Ism: {data['first_name']} {data['last_name']}
• 📱 Telefon: {data['phone']}
• 📍 Viloyat: {data['region_id']} raqamli viloyat
• 📍 Tuman: {data['district_id']} raqamli tuman
• 📚 Yo'nalish: {direction.name_uz}

<b>Ro'yxatdan o'tishni tasdiqlaysizmi?</b>
"""
    
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no")
        ]
    ])
    
    await callback_query.message.edit_text(
        confirmation_text,
        reply_markup=confirm_keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.confirmation)

@router.callback_query(UserRegistrationStates.confirmation)
async def process_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    """Process registration confirmation"""
    if callback_query.data == "confirm_no":
        await callback_query.message.edit_text("❌ Ro'yxatdan o'tish bekor qilindi.")
        await state.clear()
        await callback_query.message.answer(
            "Qayta boshlash uchun /start buyrug'ini yuboring."
        )
        return
    
    data = await state.get_data()
    db = Session()
    
    try:
        # Create new user
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
        
        user = db.query(User).filter(User.telegram_id == callback_query.from_user.id).first()
        await state.clear()
        await show_main_menu(callback_query.message, state, user)
        
    except Exception as e:
        db.rollback()
        await callback_query.answer(f"❌ Xato: {str(e)}", show_alert=True)
    finally:
        db.close()

# Main Menu Button Handlers
@router.message(UserMainMenuStates.main_menu, F.text == "🧪 Testni boshlash")
async def start_test_button(message: types.Message, state: FSMContext):
    """Handle test start button"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    
    if not user.direction_id:
        await message.answer("❌ Iltimos, avval yo'nalishni tanlang!")
        return
    
    # Show test confirmation
    confirmation_text = f"""
📝 <b>Imtihondan o'tishni boshlash</b>

<u>Imtihon haqida ma'lumot:</u>
⏱️ Vaqt: 180 daqiqa
❓ Savollar soni: 90 ta
📊 Qo'llanmalar:
  • 30 ta majburiy savol (Matematika, Tarix, Ona tili)
  • 60 ta ixtisoslashgan savol

<u>Yo'nalish:</u> {user.direction.name_uz}

<b>Imtihondan o'tishni boshlaysizmi?</b>
"""
    
    from bot.keyboards import get_test_confirmation_keyboard
    keyboard = get_test_confirmation_keyboard()
    
    await message.answer(confirmation_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TestSessionStates.test_confirmation)

@router.message(UserMainMenuStates.main_menu, F.text == "📊 Natijalarim")
async def show_my_results(message: types.Message, state: FSMContext):
    """Show user's test results"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    
    db = Session()
    try:
        # Get user's scores
        scores = db.query(Score).filter(Score.user_id == user.id).order_by(Score.created_at.desc()).all()
        db.close()
        
        if not scores:
            await message.answer("📊 <b>Siz hali imtihondan o'tmagan edingiz.</b>\n\n🧪 Testni boshlash uchun \"Testni boshlash\" tugmasini bosing.", parse_mode="HTML")
            return
        
        result_text = f"📊 <b>Sizning natijalaringiz:</b>\n\n"
        
        for i, score in enumerate(scores[:5], 1):
            percentage = (score.correct_count / score.total_questions * 100) if score.total_questions > 0 else 0
            result_text += f"{i}. <b>Sana:</b> {score.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            result_text += f"   📈 <b>Ball:</b> {score.score}\n"
            result_text += f"   ✅ <b>To'g'ri:</b> {score.correct_count}/{score.total_questions}\n"
            result_text += f"   📊 <b>Foiz:</b> {percentage:.1f}%\n\n"
        
        await message.answer(result_text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)}")
    finally:
        if db:
            db.close()

@router.message(UserMainMenuStates.main_menu, F.text == "🏆 Reyting")
async def show_leaderboard(message: types.Message, state: FSMContext):
    """Show leaderboard"""
    db = Session()
    try:
        # Get top 10 scores with user info
        top_scores = db.query(Score).order_by(Score.score.desc()).limit(10).all()
        
        if not top_scores:
            await message.answer("🏆 <b>Reytingda hali hech kim yo'q.</b>", parse_mode="HTML")
            return
        
        leaderboard_text = "🏆 <b>Reyting (Top 10)</b>\n\n"
        
        for i, score in enumerate(top_scores, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            user = score.user
            leaderboard_text += f"{medal} <b>{user.first_name} {user.last_name}</b>\n"
            leaderboard_text += f"   📊 Ball: {score.score}\n"
            leaderboard_text += f"   ✅ To'g'ri: {score.correct_count}/{score.total_questions}\n\n"
        
        await message.answer(leaderboard_text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)}")
    finally:
        db.close()

@router.message(UserMainMenuStates.main_menu, F.text == "👤 Profilim")
async def show_profile(message: types.Message, state: FSMContext):
    """Show user profile"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    
    db = Session()
    try:
        # Get user's stats
        scores = db.query(Score).filter(Score.user_id == user.id).all()
        best_score = max([s.score for s in scores], default=0) if scores else 0
        tests_count = len(scores)
        
        profile_text = f"""
👤 <b>Sizning profil</b>

<b>Shaxsiy ma'lumotlar:</b>
• 📝 F.I.SH: {user.first_name} {user.last_name}
• 📱 Telefon: {user.phone}
• 📍 Viloyat: {user.region.name_uz}
• 📍 Tuman: {user.district.name_uz}
• 📚 Yo'nalish: {user.direction.name_uz if user.direction else 'Tanlanmagan'}

<b>Statistika:</b>
• 🧪 Imtihon soni: {tests_count}
• 📊 Eng yuqori ball: {best_score}
• 📅 Ro'yxatdan o'tish: {user.created_at.strftime('%d.%m.%Y')}
"""
        
        await message.answer(profile_text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)}")
    finally:
        db.close()

@router.message(UserMainMenuStates.main_menu, F.text == "⚙️ Sozlamalar")
async def show_settings(message: types.Message, state: FSMContext):
    """Show settings menu"""
    settings_text = """
⚙️ <b>Sozlamalar</b>

Hozircha sozlamalar mavjud emas.
"""
    await message.answer(settings_text, parse_mode="HTML")

@router.message(UserMainMenuStates.main_menu, F.text == "❓ Yordam")
async def show_help(message: types.Message, state: FSMContext):
    """Show help menu"""
    help_text = """
❓ <b>Yordam</b>

<b>Imtihon haqida:</b>
• Imtihon 180 daqiqa davom etadi
• Jami 90 ta savol bor
• 30 ta majburiy savol va 60 ta ixtisoslashgan savol

<b>Ballga oid:</b>
• Majburiy savollar: 1.1 ball
• Ixtisoslashgan savollar: 3.1 ball (mo'ynaq va boshqa) yoki 2.1 ball

<b>Muammolar:</b>
Agar muammo bo'lsa, admin bilan bog'laning.
"""
    await message.answer(help_text, parse_mode="HTML")

@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_start_confirm")
async def confirm_test_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Confirm and start test"""
    user = get_user_by_telegram_id(callback_query.from_user.id)
    
    if not user:
        await callback_query.answer("❌ Xato: Foydalanuvchi topilmadi!")
        return
    
    try:
        # Create test participation
        service = TestService()
        participation = service.create_participation(user.id, user.direction_id)
        
        # Get test questions
        questions = service.get_test_questions(user.direction_id)
        
        if not questions:
            await callback_query.answer("❌ Xato: Savollar topilmadi!", show_alert=True)
            return
        
        # Save to state
        await state.update_data(
            participation_id=participation.id,
            questions=[(q.id, q.text_uz, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_answer) for q in questions],
            current_question_index=0,
            answers={}
        )
        
        # Show first question
        await callback_query.message.delete()
        
        from bot.keyboards import get_test_answer_keyboard
        
        question = questions[0]
        question_text = f"""
<b>Savol #{1}/{len(questions)}</b>

{question.text_uz}

A) {question.option_a}
B) {question.option_b}
C) {question.option_c}
D) {question.option_d}
"""
        keyboard = get_test_answer_keyboard()
        await callback_query.message.answer(question_text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(TestSessionStates.test_active)
        
    except Exception as e:
        await callback_query.answer(f"❌ Xato: {str(e)}", show_alert=True)

@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_cancel")
async def cancel_test(callback_query: types.CallbackQuery, state: FSMContext):
    """Cancel test start"""
    user = get_user_by_telegram_id(callback_query.from_user.id)
    
    db = Session()
    try:
        db.close()
        await callback_query.message.delete()
        
        await state.set_state(UserMainMenuStates.main_menu)
        user = db.query(User).filter(User.telegram_id == callback_query.from_user.id).first()
        keyboard = await get_main_menu_keyboard()
        
        await callback_query.message.answer(
            f"Bosh menyu\n\nAssalomu alaykum, <b>{user.first_name} {user.last_name}</b>!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        await callback_query.answer(f"❌ Xato: {str(e)}", show_alert=True)
    finally:
        db.close()

@router.callback_query(TestSessionStates.test_active, F.data.startswith("answer_"))
async def handle_test_answer(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle test answer"""
    user = get_user_by_telegram_id(callback_query.from_user.id)
    answer = callback_query.data.split("_")[1]
    
    data = await state.get_data()
    current_index = data.get('current_question_index', 0)
    questions = data.get('questions', [])
    answers = data.get('answers', {})
    participation_id = data.get('participation_id')
    
    service = TestService()
    
    if answer == "skip":
        # Skip question
        answers[str(current_index)] = None
    else:
        # Save answer
        question_id = questions[current_index][0]
        is_correct = answer == questions[current_index][6]
        
        answers[str(current_index)] = answer
        service.save_answer(participation_id, question_id, answer, is_correct)
    
    # Move to next question or finish
    current_index += 1
    
    if current_index >= len(questions):
        # Test completed
        score_info = service.complete_test(participation_id)
        
        await callback_query.message.delete()
        
        result_text = f"""
✅ <b>Imtihon tugallandi!</b>

📊 <b>Sizning natijalaringiz:</b>
• 📈 Ball: {score_info['score']}
• ✅ To'g'ri javoblar: {score_info['correct_count']}/{score_info['total_questions']}
• 📊 Foiz: {(score_info['correct_count'] / score_info['total_questions'] * 100):.1f}%

🏆 Reytingda o'zingizning o'riningizni tekshiring!
"""
        
        from bot.keyboards import get_test_results_keyboard
        keyboard = get_test_results_keyboard()
        
        await callback_query.message.answer(result_text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserMainMenuStates.main_menu)
        
    else:
        # Show next question
        question = questions[current_index]
        question_text = f"""
<b>Savol #{current_index + 1}/{len(questions)}</b>

{question[1]}

A) {question[2]}
B) {question[3]}
C) {question[4]}
D) {question[5]}
"""
        
        await state.update_data(current_question_index=current_index, answers=answers)
        
        from bot.keyboards import get_test_answer_keyboard
        keyboard = get_test_answer_keyboard()
        
        await callback_query.message.edit_text(question_text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback_query.answer()

@router.callback_query(TestSessionStates.test_active, F.data == "test_finish")
async def finish_test_early(callback_query: types.CallbackQuery, state: FSMContext):
    """Finish test early"""
    data = await state.get_data()
    participation_id = data.get('participation_id')
    questions = data.get('questions', [])
    
    service = TestService()
    score_info = service.complete_test(participation_id)
    
    await callback_query.message.delete()
    
    result_text = f"""
✅ <b>Imtihon tugallandi!</b>

📊 <b>Sizning natijalaringiz:</b>
• 📈 Ball: {score_info['score']}
• ✅ To'g'ri javoblar: {score_info['correct_count']}/{score_info['total_questions']}
• 📊 Foiz: {(score_info['correct_count'] / score_info['total_questions'] * 100):.1f}%

🏆 Reytingda o'zingizning o'riningizni tekshiring!
"""
    
    from bot.keyboards import get_test_results_keyboard
    keyboard = get_test_results_keyboard()
    
    await callback_query.message.answer(result_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserMainMenuStates.main_menu)
    await callback_query.answer()

@router.message(UserMainMenuStates.main_menu, F.text == "🧪 Yana test qol")
async def another_test(message: types.Message, state: FSMContext):
    """Handle another test button"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    
    if not user.direction_id:
        await message.answer("❌ Iltimos, avval yo'nalishni tanlang!")
        return
    
    # Show test confirmation
    confirmation_text = f"""
📝 <b>Imtihondan o'tishni boshlash</b>

<u>Imtihon haqida ma'lumot:</u>
⏱️ Vaqt: 180 daqiqa
❓ Savollar soni: 90 ta
📊 Qo'llanmalar:
  • 30 ta majburiy savol (Matematika, Tarix, Ona tili)
  • 60 ta ixtisoslashgan savol

<u>Yo'nalish:</u> {user.direction.name_uz}

<b>Imtihondan o'tishni boshlaysizmi?</b>
"""
    
    from bot.keyboards import get_test_confirmation_keyboard
    keyboard = get_test_confirmation_keyboard()
    
    await message.answer(confirmation_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TestSessionStates.test_confirmation)

@router.message(UserMainMenuStates.main_menu, F.text == "📊 Natijalarni ko'rish")
async def view_results_from_test(message: types.Message, state: FSMContext):
    """Show results from test menu"""
    await show_my_results(message, state)

@router.message(UserMainMenuStates.main_menu, F.text == "🏠 Bosh menyu")
async def return_to_main_menu(message: types.Message, state: FSMContext):
    """Return to main menu"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    
    await state.set_state(UserMainMenuStates.main_menu)
    keyboard = await get_main_menu_keyboard()
    
    text = f"""
🏛 <b>DTM Test Bot</b>

Assalomu alaykum, <b>{user.first_name} {user.last_name}</b>!

<b>Nima qilmoqchi ekaningizni tanlang:</b>
"""
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")