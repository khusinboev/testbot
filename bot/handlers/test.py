from aiogram import Router, types, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from database.db import Session
from database.models import User, UserTestParticipation, Question
from bot.states import TestSessionStates, UserMainMenuStates
from bot.keyboards import (
    get_test_answer_keyboard,
    get_test_confirmation_keyboard,
    get_test_results_keyboard,
    get_main_menu_keyboard
)
from utils.test_service import TestService
import config

router = Router()

def get_user_by_telegram_id(telegram_id: int) -> User:
    """Get user from database"""
    db = Session()
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    db.close()
    return user

@router.message(F.text == "🧪 Testni boshlash")
async def start_test_menu(message: types.Message, state: FSMContext):
    """Handle test start button from main menu"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan ekaningiz!")
        return
    
    if not user.direction_id:
        await message.answer(
            "❌ Siz yo'nalish tanlamagan ekaningiz!\n"
            "Iltimos, /start buyrug'i orqali profilingizni to'ldiring."
        )
        return
    
    # Show test confirmation
    db = Session()
    direction = db.query(User).filter(User.id == user.id).first()
    db.close()
    
    confirmation_text = f"""
🧪 <b>Test Boshlash</b>

<b>Test haqida:</b>
• <b>Vaqt:</b> {config.TEST_DURATION_MINUTES} daqiqa (180 min)
• <b>Savollar:</b> 90 ta savol
• <b>Struktura:</b>
  - 30 ta majburiy savol (Matematika, Tarix, Ona tili)
  - 60 ta ixtisoslashtirilgan savol {direction.direction.name_uz}
• <b>Qiymatlash:</b> Avtomatik hisoblanadi

<b>Qadam:</b>
1. Har bir savolga A, B, C, D variantlaridan birini tanlang
2. O'tkazish tugmasini bosish orqali savolni o'tkazishingiz mumkin
3. Test pastdagi "Testni yakunlash" tugmasini bosib tugatiladi

⚠️ <b>E'tibor:</b> Test boshlangandan keyin to'xtatish mumkin emas!

<b>Testni boshlashga tayyormisiz?</b>
"""
    
    keyboard = get_test_confirmation_keyboard()
    await message.answer(confirmation_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TestSessionStates.test_confirmation)

@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_cancel")
async def cancel_test(callback_query: types.CallbackQuery, state: FSMContext):
    """Cancel test start"""
    user = get_user_by_telegram_id(callback_query.from_user.id)
    keyboard = await get_main_menu_keyboard()
    
    await callback_query.message.edit_text(
        "❌ Test bekor qilindi.\n\nBosh menyu:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(UserMainMenuStates.main_menu)

@router.callback_query(TestSessionStates.test_confirmation, F.data == "test_start_confirm")
async def confirm_test_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Confirm and start test"""
    user = get_user_by_telegram_id(callback_query.from_user.id)
    
    if not user or not user.direction_id:
        await callback_query.answer("❌ Xato: User ma'lumotlari topilmadi", show_alert=True)
        return
    
    try:
        # Create test participation
        participation = TestService.create_participation(user.id, user.direction_id)
        
        # Get test questions
        questions = TestService.get_test_questions(user.direction_id)
        
        if not questions or len(questions) < 90:
            await callback_query.answer(
                f"❌ Xato: Etarli savol topilmadi ({len(questions)}/90)",
                show_alert=True
            )
            return
        
        # Store test data in state
        await state.update_data(
            participation_id=participation.id,
            test_session_id=participation.test_session_id,
            questions=[q.id for q in questions],
            current_question_index=0,
            answers={},
            start_time=callback_query.message.date.timestamp()
        )
        
        # Show first question
        await show_question(callback_query.message, questions[0], 1, state)
        await state.set_state(TestSessionStates.test_active)
        
    except Exception as e:
        await callback_query.answer(f"❌ Xato: {str(e)}", show_alert=True)

async def show_question(message: types.Message, question: Question, question_num: int, state: FSMContext):
    """Show a test question"""
    db = Session()
    question_obj = db.query(Question).filter(Question.id == question.id).first()
    db.close()
    
    question_text = f"""
<b>Savol {question_num}/90</b>

{question_obj.text_uz}

<b>Variantlar:</b>
🅰️ <code>{question_obj.option_a}</code>
🅱️ <code>{question_obj.option_b}</code>
🅲️ <code>{question_obj.option_c}</code>
🅳️ <code>{question_obj.option_d}</code>
"""
    
    keyboard = get_test_answer_keyboard()
    await message.answer(question_text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(TestSessionStates.test_active, F.data.startswith("answer_"))
async def handle_answer(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle answer selection"""
    answer_data = callback_query.data
    
    if answer_data == "answer_skip":
        selected = None
    else:
        selected = answer_data.split("_")[1]  # A, B, C, or D
    
    data = await state.get_data()
    current_idx = data['current_question_index']
    question_id = data['questions'][current_idx]
    
    # Save answer
    TestService.save_answer(
        data['participation_id'],
        callback_query.from_user.id,
        data['test_session_id'],
        question_id,
        selected
    )
    
    # Move to next question
    next_idx = current_idx + 1
    
    if next_idx >= 90:
        # Test completed
        await complete_test(callback_query.message, state)
    else:
        # Show next question
        db = Session()
        next_question = db.query(Question).filter(
            Question.id == data['questions'][next_idx]
        ).first()
        db.close()
        
        await state.update_data(current_question_index=next_idx)
        await show_question(callback_query.message, next_question, next_idx + 1, state)

@router.callback_query(TestSessionStates.test_active, F.data == "test_finish")
async def finish_test_early(callback_query: types.CallbackQuery, state: FSMContext):
    """Finish test early"""
    await callback_query.answer("Testni yakunlash...", show_alert=True)
    await complete_test(callback_query.message, state)

async def complete_test(message: types.Message, state: FSMContext):
    """Complete test and show results"""
    data = await state.get_data()
    
    # Calculate results
    results = TestService.complete_test(
        data['participation_id'],
        message.from_user.id,
        data['test_session_id']
    )
    
    if not results:
        await message.answer("❌ Xato: Natijalarni hisoblashda xato")
        return
    
    results_text = f"""
✅ <b>Test Yakunlandi!</b>

<b>Natijalaringiz:</b>
• <b>Umumiy ball:</b> {results['score']:.1f}
• <b>To'g'ri javoblar:</b> {results['correct']}/{results['total']}
• <b>Foiz:</b> {results['percentage']}%

<b>Baholanish:</b>
"""
    
    percentage = results['percentage']
    if percentage >= 80:
        results_text += "🌟 <b>A'lo</b> - Juda yaxshi!"
    elif percentage >= 70:
        results_text += "⭐ <b>Yaxshi</b> - Chiroyli!"
    elif percentage >= 60:
        results_text += "👍 <b>Qoniqarli</b>"
    else:
        results_text += "💪 <b>Yana harakat qiling</b>"
    
    keyboard = get_test_results_keyboard()
    await message.answer(results_text, reply_markup=keyboard, parse_mode="HTML")
    
    await state.clear()
    await state.set_state(UserMainMenuStates.main_menu)