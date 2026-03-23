"""
bot/handlers/registration.py  (to'liq yangilangan)
Yangiliklar:
  - Kanal obuna tekshiruvi (subscription_gate)
  - Test davom ettirish (resume test)
  - Yo'nalish bo'yicha reyting
  - Yangi check_subscription callback
"""
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ContentType, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
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
from utils.test_service import TestService
from utils.locks import user_lock, is_processing, throttle_check
from utils.channel_service import subscription_gate, check_user_subscriptions, build_subscribe_keyboard
from sqlalchemy.orm import joinedload
import logging
import traceback

logger = logging.getLogger(__name__)
router = Router()


def _err(e: Exception) -> str:
    logger.error("Handler xato:\n%s", traceback.format_exc())
    return f"❌ Xato: {str(e)[:150]}"


# ─── Yordamchi funksiyalar ───────────────────────────────────────────────────

def get_user_by_telegram_id(telegram_id: int) -> User | None:
    db = Session()
    user = db.query(User).options(
        joinedload(User.region),
        joinedload(User.district),
        joinedload(User.direction)
    ).filter(User.telegram_id == telegram_id).first()
    db.close()
    return user


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _get_direction_subject_names(direction: Direction) -> tuple[str, str]:
    db = Session()
    try:
        d = db.query(Direction).options(
            joinedload(Direction.subject1),
            joinedload(Direction.subject2)
        ).filter(Direction.id == direction.id).first()
        if d:
            return (
                d.subject1.name_uz if d.subject1 else "—",
                d.subject2.name_uz if d.subject2 else "—"
            )
        return "—", "—"
    finally:
        db.close()


async def show_main_menu(message: types.Message, state: FSMContext, user: User):
    keyboard = await get_main_menu_keyboard()
    direction_name = user.direction.name_uz if user.direction else "❗ Belgilanmagan"
    text = (
        f"🏛 <b>DTM Test Bot</b>\n\n"
        f"Assalomu alaykum, <b>{user.first_name} {user.last_name or ''}</b>!\n\n"
        f"<b>Shaxsiy ma'lumotlar:</b>\n"
        f"• 📱 Telefon: {user.phone}\n"
        f"• 📍 Viloyat: {user.region.name_uz}\n"
        f"• 📍 Tuman: {user.district.name_uz}\n"
        f"• 📚 Yo'nalish: {direction_name}\n\n"
        f"<b>Nima qilmoqchi ekaningizni tanlang:</b>"
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserMainMenuStates.main_menu)


# ─── Obuna tekshiruv callback ────────────────────────────────────────────────

@router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(callback_query: types.CallbackQuery,
                                     state: FSMContext, bot: Bot):
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
            await callback_query.message.answer(
                "Ro'yxatdan o'tish uchun /start bosing."
            )
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

    # Kanal obuna tekshiruvi
    if not await subscription_gate(bot, message.from_user.id, message):
        return

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
        f"✅ Ism saqlandi: <b>{full_name}</b>\n\n📱 <b>Telefon raqamingizni ulang:</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_phone)


@router.message(UserRegistrationStates.waiting_for_phone, F.content_type == ContentType.CONTACT)
async def process_phone_contact(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    keyboard = await get_regions_keyboard()
    await message.answer(
        "📍 <b>Viloyatingizni tanlang:</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_region)


@router.message(UserRegistrationStates.waiting_for_phone)
async def process_phone_invalid(message: types.Message, state: FSMContext):
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
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_district)


@router.callback_query(UserRegistrationStates.waiting_for_district, F.data == "region_back")
async def reg_district_back(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = await get_regions_keyboard()
    await callback_query.message.edit_text(
        "📍 <b>Viloyatingizni tanlang:</b>",
        reply_markup=keyboard, parse_mode="HTML"
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

    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha", callback_data="confirm_yes"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no")
    ]])
    await callback_query.message.edit_text(
        f"✅ <b>Ro'yxatdan o'tish — tasdiqlash</b>\n\n"
        f"• 👤 F.I.SH: {data.get('full_name', data.get('first_name', ''))}\n"
        f"• 📱 Telefon: {data['phone']}\n"
        f"• 📍 Viloyat: {region.name_uz if region else '—'}\n"
        f"• 📍 Tuman: {district.name_uz}\n\n"
        f"<i>Yo'nalishni keyinroq Profil sozlamalarida belgilaysiz.</i>\n\n"
        f"<b>Tasdiqlaysizmi?</b>",
        reply_markup=confirm_keyboard, parse_mode="HTML"
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
            user = db.query(User).options(
                joinedload(User.region),
                joinedload(User.district),
                joinedload(User.direction)
            ).filter(User.telegram_id == callback_query.from_user.id).first()
            await callback_query.answer("✅ Ro'yxatdan o'tildi!", show_alert=True)
            await state.clear()
            await show_main_menu(callback_query.message, state, user)
        except Exception as e:
            db.rollback()
            await callback_query.answer(_err(e), show_alert=True)
        finally:
            db.close()


# ─── Asosiy menyu — Test boshlash ─────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🧪 Testni boshlash")
async def start_test_button(message: types.Message, state: FSMContext, bot: Bot):
    # Kanal tekshiruvi
    if not await subscription_gate(bot, message.from_user.id, message):
        return

    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return

    # Aktiv test bor-yo'qligini tekshirish
    active = TestService.get_active_participation(user.id)
    if active:
        snapshot = TestService.load_snapshot(active.id)
        if snapshot:
            # Vaqt hali tugamaganmi?
            if active.deadline_at and active.deadline_at > __import__('datetime').datetime.utcnow():
                remaining = active.deadline_at - __import__('datetime').datetime.utcnow()
                mins = int(remaining.total_seconds() // 60)
                secs = int(remaining.total_seconds() % 60)

                resume_kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="▶️ Davom ettirish",
                        callback_data="test_resume"
                    ),
                    InlineKeyboardButton(
                        text="🆕 Yangi test",
                        callback_data="test_force_new"
                    )
                ]])
                await message.answer(
                    f"⚠️ <b>Sizda tugallanmagan test bor!</b>\n\n"
                    f"• 🕐 Qolgan vaqt: <b>{mins} daq {secs} sek</b>\n"
                    f"• 📝 Savol: {snapshot['current_question_index'] + 1}/90\n\n"
                    f"Davom ettirasizmi yoki yangi test boshlaysizmi?",
                    reply_markup=resume_kb, parse_mode="HTML"
                )
                return

    if not user.direction_id:
        keyboard = await get_directions_keyboard()
        db = Session()
        total = db.query(Direction).count()
        db.close()
        await message.answer(
            f"📚 <b>Ta'lim yo'nalishingizni tanlang</b>\n\n"
            f"<i>Jami {total} ta yo'nalish mavjud</i>",
            reply_markup=keyboard, parse_mode="HTML"
        )
        await state.set_state(TestSessionStates.waiting_for_direction)
        return

    await _show_test_confirmation(message, state, user)


@router.callback_query(F.data == "test_resume")
async def handle_test_resume(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Tugallanmagan testni davom ettirish."""
    user = get_user_by_telegram_id(callback_query.from_user.id)
    if not user:
        await callback_query.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return

    active = TestService.get_active_participation(user.id)
    if not active:
        await callback_query.answer("❌ Aktiv test topilmadi!", show_alert=True)
        return

    snapshot = TestService.load_snapshot(active.id)
    if not snapshot or not snapshot['questions']:
        await callback_query.answer("❌ Test ma'lumotlari topilmadi!", show_alert=True)
        return

    import datetime
    if active.deadline_at and active.deadline_at <= datetime.datetime.utcnow():
        await callback_query.answer("❌ Test vaqti tugagan!", show_alert=True)
        TestService.complete_test(active.id)
        return

    # State ni tiklash
    await state.update_data(
        participation_id=active.id,
        test_session_id=active.test_session_id,
        questions=snapshot['questions'],
        current_question_index=snapshot['current_question_index'],
        answers=snapshot['answers'],
    )

    try:
        await callback_query.message.delete()
    except Exception:
        pass

    current_idx = snapshot['current_question_index']
    questions   = snapshot['questions']
    current_q   = questions[current_idx]

    remaining = active.deadline_at - datetime.datetime.utcnow()
    mins = int(remaining.total_seconds() // 60)

    await callback_query.message.answer(
        f"▶️ <b>Test davom ettirildi!</b> (qolgan vaqt: {mins} daq)\n\n"
        + _format_question(current_q, current_idx, len(questions)),
        reply_markup=get_test_answer_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.test_active)
    await callback_query.answer()


@router.callback_query(F.data == "test_force_new")
async def handle_force_new_test(callback_query: types.CallbackQuery, state: FSMContext):
    """Davom etayotgan testni yakunlab yangi test boshlash."""
    user = get_user_by_telegram_id(callback_query.from_user.id)
    if not user:
        await callback_query.answer("❌ Xato!", show_alert=True)
        return

    active = TestService.get_active_participation(user.id)
    if active:
        TestService.complete_test(active.id)

    try:
        await callback_query.message.delete()
    except Exception:
        pass

    await callback_query.answer("✅ Eski test yakunlandi")
    await _show_test_confirmation(callback_query.message, state, user)


async def _show_test_confirmation(message: types.Message, state: FSMContext, user: User):
    if user.direction:
        s1_name, s2_name = _get_direction_subject_names(user.direction)
        direction_line = (
            f"  • 📚 Yo'nalish: <b>{user.direction.name_uz}</b>\n"
            f"  • 📖 1-asosiy fan: <b>{s1_name}</b>\n"
            f"  • 📗 2-asosiy fan: <b>{s2_name}</b>"
        )
    else:
        direction_line = "  • ❗ Yo'nalish belgilanmagan"

    await message.answer(
        f"📝 <b>Imtihonni boshlash</b>\n\n"
        f"⏱️ Vaqt: <b>180 daqiqa</b> | ❓ Savollar: <b>90 ta</b>\n\n"
        f"<u>Savollar tartibi:</u>\n"
        f"  1️⃣ Majburiy — Matematika (10)\n"
        f"  2️⃣ Majburiy — Ona tili (10)\n"
        f"  3️⃣ Majburiy — Tarix (10)\n"
        f"  4️⃣ Asosiy 1-fan (30)\n"
        f"  5️⃣ Asosiy 2-fan (30)\n\n"
        f"<u>Sizning yo'nalishingiz:</u>\n{direction_line}\n\n"
        f"<b>Boshlaysizmi?</b>",
        reply_markup=get_test_confirmation_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.test_confirmation)


# ─── Yo'nalish tanlash (test uchun) ──────────────────────────────────────────

@router.callback_query(TestSessionStates.waiting_for_direction, F.data.startswith("direction_page_"))
async def test_direction_page(callback_query: types.CallbackQuery, state: FSMContext):
    page = int(callback_query.data.split("_")[2])
    keyboard = await get_directions_keyboard(page)
    await callback_query.message.edit_text(
        f"📚 <b>Yo'nalishni tanlang</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(TestSessionStates.waiting_for_direction, F.data == "direction_list_back")
async def test_direction_back(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer("Bekor qilindi")
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
        await callback_query.answer("❌ Yo'nalish topilmadi!")
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
        await callback_query.answer("⏳ Test boshlanmoqda, kuting...")
        return

    async with user_lock(uid):
        user = get_user_by_telegram_id(uid)
        if not user:
            await callback_query.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
            return

        # Aktiv test bor-yo'qligini qayta tekshirish
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
            questions     = TestService.get_test_questions(user.direction_id)

            if not questions:
                await callback_query.answer("❌ Savollar topilmadi!", show_alert=True)
                return

            await state.update_data(
                participation_id=participation.id,
                test_session_id=participation.test_session_id,
                questions=questions,
                current_question_index=0,
                answers={}
            )
            # Snapshotni darhol saqlash
            TestService.save_snapshot(participation.id, questions, 0, {})

            try:
                await callback_query.message.delete()
            except Exception:
                pass

            await callback_query.message.answer(
                _format_question(questions[0], 0, len(questions)),
                reply_markup=get_test_answer_keyboard(),
                parse_mode="HTML"
            )
            await state.set_state(TestSessionStates.test_active)
        except Exception as e:
            logger.error("confirm_test_start xato: %s", traceback.format_exc())
            await callback_query.answer(_err(e), show_alert=True)


def _format_question(q: dict, index: int, total: int) -> str:
    group_label = q.get('group_label', '')
    if 'Majburiy' in group_label:
        group_emoji = '📌'
        group_type  = 'Majburiy'
    else:
        group_emoji = '🎯'
        group_type  = 'Asosiy'
    fan_name = group_label.split('—')[-1].strip() if '—' in group_label else group_label
    return (
        f"{group_emoji} <b>{group_type} | {fan_name}</b>\n"
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
    user = get_user_by_telegram_id(callback_query.from_user.id)
    keyboard = await get_main_menu_keyboard()
    await callback_query.message.answer(
        f"🏠 Bosh menyu\n\nAssalomu alaykum, <b>{user.first_name}</b>!",
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
        answer          = callback_query.data.split("_")[1]
        data            = await state.get_data()
        current_index   = data.get('current_question_index', 0)
        questions       = data.get('questions', [])
        answers         = data.get('answers', {})
        participation_id = data.get('participation_id')
        test_session_id = data.get('test_session_id')

        if not questions or participation_id is None:
            await callback_query.answer("❌ Test ma'lumotlari topilmadi.", show_alert=True)
            await state.clear()
            return
        if current_index >= len(questions):
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

        # Snapshot yangilash
        TestService.save_snapshot(participation_id, questions, current_index, answers)

        if current_index >= len(questions):
            score_info = TestService.complete_test(participation_id)
            try:
                await callback_query.message.delete()
            except Exception:
                pass
            if score_info:
                pct = (score_info['correct_count'] / score_info['total_questions'] * 100
                       if score_info['total_questions'] > 0 else 0)
                result_text = (
                    f"✅ <b>Imtihon tugallandi!</b>\n\n"
                    f"• 📈 Ball: <b>{score_info['score']}</b>\n"
                    f"• ✅ To'g'ri: {score_info['correct_count']}/{score_info['total_questions']}\n"
                    f"• 📊 Foiz: {pct:.1f}%\n\n"
                    "🏆 Reytingda o'zingizni tekshiring!"
                )
            else:
                result_text = "✅ Imtihon tugallandi!"
            await callback_query.message.answer(
                result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML"
            )
            await state.set_state(UserMainMenuStates.main_menu)
        else:
            next_q = questions[current_index]
            await state.update_data(current_question_index=current_index, answers=answers)
            try:
                await callback_query.message.edit_text(
                    _format_question(next_q, current_index, len(questions)),
                    reply_markup=get_test_answer_keyboard(),
                    parse_mode="HTML"
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
            pct = (score_info['correct_count'] / score_info['total_questions'] * 100
                   if score_info['total_questions'] > 0 else 0)
            result_text = (
                f"✅ <b>Imtihon tugallandi!</b>\n\n"
                f"• 📈 Ball: <b>{score_info['score']}</b>\n"
                f"• ✅ To'g'ri: {score_info['correct_count']}/{score_info['total_questions']}\n"
                f"• 📊 Foiz: {pct:.1f}%"
            )
        else:
            result_text = "✅ Imtihon tugallandi!"

        await callback_query.message.answer(
            result_text, reply_markup=get_test_results_keyboard(), parse_mode="HTML"
        )
        await state.clear()
        await state.set_state(UserMainMenuStates.main_menu)
        await callback_query.answer()


# ─── Natijalarim ─────────────────────────────────────────────────────────────

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
                "🧪 Testni boshlash uchun tugmani bosing.",
                parse_mode="HTML"
            )
            return
        text = "📊 <b>Sizning natijalaringiz:</b>\n\n"
        for i, score in enumerate(scores[:5], 1):
            pct = (score.correct_count / score.total_questions * 100) if score.total_questions else 0
            text += (
                f"{i}. <b>Sana:</b> {score.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   📈 Ball: {score.score} | ✅ {score.correct_count}/{score.total_questions}"
                f" ({pct:.1f}%)\n\n"
            )
        await message.answer(text, parse_mode="HTML")
    finally:
        db.close()


# ─── Reyting — yo'nalish bo'yicha ────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "🏆 Reyting")
async def show_leaderboard(message: types.Message, state: FSMContext):
    user = get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return

    db = Session()
    try:
        # Agar user yo'nalishi belgilangan bo'lsa — yo'nalish reytingi
        if user.direction_id and user.direction:
            direction_name = user.direction.name_uz

            # Foydalanuvchining o'rni
            rank = TestService.get_user_direction_rank(user.id, user.direction_id)

            # User's best score
            user_best = db.query(Score).filter(
                Score.user_id == user.id
            ).order_by(Score.score.desc()).first()
            user_best_score = user_best.score if user_best else 0

            # Top 5 yo'nalish bo'yicha
            top_scores = TestService.get_direction_leaderboard(user.direction_id, limit=5)

            text = (
                f"🏆 <b>Yo'nalish reytingi</b>\n"
                f"📚 <i>{direction_name}</i>\n\n"
            )

            if top_scores:
                text += "<b>Top 5:</b>\n"
                for i, s in enumerate(top_scores, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
                    u = s.user
                    is_me = " 👈 <b>Siz</b>" if s.user_id == user.id else ""
                    text += (
                        f"{medal} <b>{u.first_name} {u.last_name or ''}</b> "
                        f"— {s.score} ball{is_me}\n"
                    )
            else:
                text += "<i>Hali natija yo'q</i>\n"

            text += (
                f"\n📍 <b>Sizning o'rningiz:</b> #{rank}\n"
                f"📊 <b>Eng yuqori ballingiz:</b> {user_best_score}"
            )

            # Umumiy reyting tugmasi
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🌐 Umumiy reyting (top 10)",
                    callback_data="leaderboard_global"
                )
            ]])
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
        else:
            # Yo'nalish belgilanmagan — umumiy reyting
            await _show_global_leaderboard(message, db)
    finally:
        db.close()


@router.callback_query(F.data == "leaderboard_global")
async def show_global_leaderboard_cb(callback_query: types.CallbackQuery, state: FSMContext):
    db = Session()
    try:
        await _show_global_leaderboard(callback_query.message, db)
    finally:
        db.close()
    await callback_query.answer()


async def _show_global_leaderboard(message: types.Message, db):
    top_scores = db.query(Score).order_by(Score.score.desc()).limit(10).all()
    if not top_scores:
        await message.answer("🏆 <b>Reytingda hali hech kim yo'q.</b>", parse_mode="HTML")
        return
    text = "🏆 <b>Umumiy reyting (Top 10)</b>\n\n"
    for i, score in enumerate(top_scores, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        u = score.user
        text += (
            f"{medal} <b>{u.first_name} {u.last_name or ''}</b>\n"
            f"   📊 Ball: {score.score} | ✅ {score.correct_count}/{score.total_questions}\n\n"
        )
    await message.answer(text, parse_mode="HTML")


# ─── Yordam ───────────────────────────────────────────────────────────────────

@router.message(UserMainMenuStates.main_menu, F.text == "❓ Yordam")
async def show_help(message: types.Message, state: FSMContext):
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        "<b>Imtihon:</b> 180 daqiqa, 90 ta savol\n\n"
        "<b>Savollar:</b>\n"
        "  1️⃣ Matematika (10) — 1.1 ball\n"
        "  2️⃣ Ona tili (10) — 1.1 ball\n"
        "  3️⃣ Tarix (10) — 1.1 ball\n"
        "  4️⃣ 1-asosiy fan (30) — 3.1 ball\n"
        "  5️⃣ 2-asosiy fan (30) — 2.1 ball\n\n"
        "<b>Profil</b> bo'limida yo'nalish va ismni o'zgartirish mumkin.",
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
        best_score     = max((s.score for s in scores), default=0)
        direction_name = user.direction.name_uz if user.direction else "❗ Belgilanmagan"
        full_name      = f"{user.first_name} {user.last_name or ''}".strip()

        if user.direction:
            s1, s2 = _get_direction_subject_names(user.direction)
            direction_block = (
                f"• 📚 Yo'nalish: {direction_name}\n"
                f"• 📖 1-asosiy fan: {s1}\n"
                f"• 📗 2-asosiy fan: {s2}"
            )
        else:
            direction_block = f"• 📚 Yo'nalish: {direction_name}"

        await message.answer(
            f"👤 <b>Profil</b>\n\n"
            f"• 📝 F.I.SH: {full_name}\n"
            f"• 📱 Telefon: {user.phone}\n"
            f"• 📍 Viloyat: {user.region.name_uz}\n"
            f"• 📍 Tuman: {user.district.name_uz}\n"
            f"{direction_block}\n\n"
            f"• 🧪 Imtihon soni: {len(scores)}\n"
            f"• 📊 Eng yuqori ball: {best_score}\n"
            f"• 📅 Ro'yxat: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            f"<b>Tahrirlash:</b>",
            reply_markup=get_profile_settings_keyboard(),
            parse_mode="HTML"
        )
    finally:
        db.close()


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
        "✏️ <b>F.I.SH ni tahrirlash</b>\n\nYangi to'liq ismingizni kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.edit_full_name)


@router.message(ProfileEditStates.edit_full_name)
async def profile_edit_name_save(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Kamida 2 ta harf kiriting!")
        return
    full_name  = message.text.strip()
    first, last = _split_full_name(full_name)
    db = Session()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user:
            user.first_name = first
            user.last_name  = last
            db.commit()
        await state.set_state(UserMainMenuStates.main_menu)
        await message.answer(f"✅ F.I.SH yangilandi: <b>{full_name}</b>", parse_mode="HTML")
        await show_profile(message, state)
    except Exception as e:
        db.rollback()
        await message.answer("❌ Ichki xato yuz berdi.")
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
        f"📚 <b>Yo'nalishni o'zgartirish</b>\n\n<i>Jami {total} ta yo'nalish</i>",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.edit_direction)


@router.callback_query(ProfileEditStates.edit_direction, F.data.startswith("direction_page_"))
async def profile_direction_page(callback_query: types.CallbackQuery, state: FSMContext):
    page = int(callback_query.data.split("_")[2])
    keyboard = await get_directions_keyboard(page)
    await callback_query.message.edit_text(
        "📚 <b>Yo'nalishni o'zgartirish</b>",
        reply_markup=keyboard, parse_mode="HTML"
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
        await callback_query.answer("❌ Yo'nalish topilmadi!")
        db.close()
        return
    user = db.query(User).filter(User.telegram_id == callback_query.from_user.id).first()
    if user:
        user.direction_id = direction_id
        db.commit()
    db.close()
    await callback_query.answer("✅ Yo'nalish saqlandi!")
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
    db.close()

    current_state = await state.get_state()
    user = get_user_by_telegram_id(message.from_user.id)
    await message.answer(
        f"✅ Yo'nalish tanlandi: <b>{direction.name_uz}</b>", parse_mode="HTML"
    )

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


# ─── Qidiruv handlerlari ──────────────────────────────────────────────────────

@router.callback_query(TestSessionStates.waiting_for_direction, F.data == "direction_search")
async def test_direction_search_start(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "🔍 <b>Yo'nalish qidirish</b>\n\nYo'nalish nomini kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.searching_direction)


@router.message(TestSessionStates.searching_direction)
async def test_direction_search_query(message: types.Message, state: FSMContext):
    query = message.text.strip() if message.text else ""
    if not query:
        return
    keyboard = await get_direction_search_results(query)
    db = Session()
    count = db.query(Direction).filter(Direction.name_uz.ilike(f"%{query}%")).count()
    db.close()
    await message.answer(
        f"🔍 <b>«{query}»</b> — {count} ta natija",
        reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(TestSessionStates.searching_direction, F.data == "direction_search_back")
async def test_direction_search_back(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = await get_directions_keyboard()
    await callback_query.message.edit_text(
        "📚 <b>Yo'nalishni tanlang</b>",
        reply_markup=keyboard, parse_mode="HTML"
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
        await callback_query.answer("❌ Yo'nalish topilmadi!")
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


# Profil qidiruv handlerlari (avvalgidek)
@router.callback_query(ProfileEditStates.edit_direction, F.data == "direction_search")
async def profile_direction_search_start(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "🔍 <b>Yo'nalish qidirish</b>\n\nYo'nalish nomini kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.searching_direction)


@router.message(ProfileEditStates.searching_direction)
async def profile_direction_search_query(message: types.Message, state: FSMContext):
    query = message.text.strip() if message.text else ""
    if not query:
        return
    keyboard = await get_direction_search_results(query)
    db = Session()
    count = db.query(Direction).filter(Direction.name_uz.ilike(f"%{query}%")).count()
    db.close()
    await message.answer(
        f"🔍 <b>«{query}»</b> — {count} ta natija",
        reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(ProfileEditStates.searching_direction, F.data == "direction_search_back")
async def profile_direction_search_back(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = await get_directions_keyboard()
    await callback_query.message.edit_text(
        "📚 <b>Yo'nalishni o'zgartirish</b>",
        reply_markup=keyboard, parse_mode="HTML"
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
        await callback_query.answer("❌ Yo'nalish topilmadi!")
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


# ─── Test natijasi menyusidan qayta boshlash ──────────────────────────────────

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
        await message.answer("❌ Siz ro'yxatdan o'tmagan edingiz!")
        return
    keyboard = await get_main_menu_keyboard()
    await message.answer(
        f"🏛 <b>DTM Test Bot</b>\n\nAssalomu alaykum, <b>{user.first_name}</b>!\n\n"
        f"<b>Nima qilmoqchi ekaningizni tanlang:</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )