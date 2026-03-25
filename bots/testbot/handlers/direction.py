"""
bots/testbot/handlers/direction.py

Yo'nalish tanlash handlerlar — test va profil holatlarida ishlaydi.

Asosiy funksiya: apply_direction_change()
  → yo'nalishni saqlaydi va qaysi state da ekaniga qarab keyingi qadamga o'tadi.
"""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import joinedload

from database.db import Session
from database.models import Direction, User

from .common import get_user_by_telegram_id, safe_delete, show_main_menu
from ..keyboards import get_direction_search_results, get_directions_keyboard
from ..states import ProfileEditStates, TestSessionStates

router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# UMUMIY: yo'nalish saqlash va yo'naltirish
# ══════════════════════════════════════════════════════════════════════════════

async def apply_direction_change(
    source: types.Message | types.CallbackQuery,
    state: FSMContext,
    direction_id: str,
) -> None:
    """
    Yo'nalishni DB ga saqlaydi va qaysi state da ekaniga qarab:
      - TestSessionStates → test tasdiqlash sahifasiga
      - ProfileEditStates → profil sahifasiga
      - Boshqa           → bosh menyuga
    """
    db        = Session()
    direction = db.query(Direction).options(
        joinedload(Direction.subject1),
        joinedload(Direction.subject2),
    ).filter(Direction.id == direction_id).first()

    if not direction:
        db.close()
        if isinstance(source, types.CallbackQuery):
            await source.answer("❌ Yo'nalish topilmadi!")
        else:
            await source.answer("❌ Yo'nalish topilmadi!")
        return

    tg_id   = source.from_user.id
    user_db = db.query(User).filter(User.telegram_id == tg_id).first()
    if user_db:
        user_db.direction_id = direction_id
        db.commit()
    db.close()

    msg            = source.message if isinstance(source, types.CallbackQuery) else source
    current_state  = await state.get_state()
    user           = get_user_by_telegram_id(tg_id)

    await msg.answer(
        f"✅ Yo'nalish: <b>{direction.name_uz}</b>", parse_mode="HTML"
    )

    if current_state in (TestSessionStates.waiting_for_direction,
                          TestSessionStates.searching_direction):
        # test.py dagi funksiyani import qilamiz (circular import'dan saqlanish uchun)
        from .test import show_test_confirmation
        await show_test_confirmation(msg, state, user)

    elif current_state in (ProfileEditStates.edit_direction,
                            ProfileEditStates.searching_direction):
        from .profile import show_profile
        await state.clear()
        await show_profile(msg, state)

    else:
        await show_main_menu(msg, state, user)


# ══════════════════════════════════════════════════════════════════════════════
# TEST: yo'nalish tanlash
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(TestSessionStates.waiting_for_direction,
                       F.data.startswith("direction_page_"))
async def test_dir_page(callback: types.CallbackQuery, state: FSMContext):
    page     = int(callback.data.split("_")[2])
    keyboard = await get_directions_keyboard(page)
    await callback.message.edit_text(
        "📚 <b>Yo'nalishni tanlang</b>", reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(TestSessionStates.waiting_for_direction, F.data == "direction_list_back")
async def test_dir_back(callback: types.CallbackQuery, state: FSMContext):
    from ..keyboards import get_main_menu_keyboard
    await callback.answer()
    await safe_delete(callback.message)
    await state.clear()
    keyboard = await get_main_menu_keyboard()
    await callback.message.answer("🏠 Bosh menyu", reply_markup=keyboard)


@router.callback_query(TestSessionStates.waiting_for_direction, F.data.startswith("direction_"))
async def test_dir_selected(callback: types.CallbackQuery, state: FSMContext):
    if "_page_" in callback.data:
        return
    direction_id = callback.data.split("_")[1]
    await safe_delete(callback.message)
    await apply_direction_change(callback, state, direction_id)


@router.callback_query(TestSessionStates.waiting_for_direction, F.data == "direction_search")
async def test_dir_search_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 <b>Yo'nalish qidirish</b>\n\nNomini kiriting:", parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.searching_direction)


@router.message(TestSessionStates.searching_direction)
async def test_dir_search_query(message: types.Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query:
        return
    db    = Session()
    count = db.query(Direction).filter(Direction.name_uz.ilike(f"%{query}%")).count()
    db.close()
    keyboard = await get_direction_search_results(query)
    await message.answer(
        f"🔍 <b>«{query}»</b> — {count} ta", reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(TestSessionStates.searching_direction, F.data == "direction_search_back")
async def test_dir_search_back(callback: types.CallbackQuery, state: FSMContext):
    keyboard = await get_directions_keyboard()
    await callback.message.edit_text(
        "📚 <b>Yo'nalishni tanlang</b>", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(TestSessionStates.waiting_for_direction)


@router.callback_query(TestSessionStates.searching_direction, F.data.startswith("direction_"))
async def test_dir_search_selected(callback: types.CallbackQuery, state: FSMContext):
    if callback.data in ("direction_search", "direction_search_empty",
                         "direction_search_back", "direction_list_back"):
        return
    direction_id = callback.data.split("_")[1]
    await safe_delete(callback.message)
    await apply_direction_change(callback, state, direction_id)


# ══════════════════════════════════════════════════════════════════════════════
# PROFIL: yo'nalish o'zgartirish
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(ProfileEditStates.edit_direction,
                       F.data.startswith("direction_page_"))
async def prof_dir_page(callback: types.CallbackQuery, state: FSMContext):
    page     = int(callback.data.split("_")[2])
    keyboard = await get_directions_keyboard(page)
    await callback.message.edit_text(
        "📚 <b>Yo'nalishni o'zgartirish</b>", reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(ProfileEditStates.edit_direction, F.data == "direction_list_back")
async def prof_dir_back(callback: types.CallbackQuery, state: FSMContext):
    from .profile import show_profile
    await state.clear()
    await safe_delete(callback.message)
    await show_profile(callback.message, state)


@router.callback_query(ProfileEditStates.edit_direction, F.data.startswith("direction_"))
async def prof_dir_selected(callback: types.CallbackQuery, state: FSMContext):
    if callback.data in ("direction_search", "direction_search_empty",
                         "direction_search_back", "direction_list_back") \
            or "_page_" in callback.data:
        return
    direction_id = callback.data.split("_")[1]
    await apply_direction_change(callback, state, direction_id)


@router.callback_query(ProfileEditStates.edit_direction, F.data == "direction_search")
async def prof_dir_search_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 <b>Yo'nalish qidirish</b>\n\nNomini kiriting:", parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.searching_direction)


@router.message(ProfileEditStates.searching_direction)
async def prof_dir_search_query(message: types.Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query:
        return
    db    = Session()
    count = db.query(Direction).filter(Direction.name_uz.ilike(f"%{query}%")).count()
    db.close()
    keyboard = await get_direction_search_results(query)
    await message.answer(
        f"🔍 <b>«{query}»</b> — {count} ta", reply_markup=keyboard, parse_mode="HTML"
    )


@router.callback_query(ProfileEditStates.searching_direction,
                       F.data == "direction_search_back")
async def prof_dir_search_back(callback: types.CallbackQuery, state: FSMContext):
    keyboard = await get_directions_keyboard()
    await callback.message.edit_text(
        "📚 <b>Yo'nalishni o'zgartirish</b>", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.edit_direction)


@router.callback_query(ProfileEditStates.searching_direction, F.data.startswith("direction_"))
async def prof_dir_search_selected(callback: types.CallbackQuery, state: FSMContext):
    if callback.data in ("direction_search", "direction_search_empty",
                         "direction_search_back", "direction_list_back"):
        return
    direction_id = callback.data.split("_")[1]
    await apply_direction_change(callback, state, direction_id)


# ══════════════════════════════════════════════════════════════════════════════
# INLINE tanlash (direction_chosen: prefiksi)
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "direction_search_failed")
async def handle_search_failed(message: types.Message, state: FSMContext):
    await safe_delete(message)


@router.message(F.text.startswith("direction_chosen:"))
async def handle_direction_chosen(message: types.Message, state: FSMContext):
    direction_id = message.text.split(":", 1)[1].strip()
    await safe_delete(message)
    await apply_direction_change(message, state, direction_id)
