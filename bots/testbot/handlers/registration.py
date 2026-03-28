"""
bots/testbot/handlers/registration.py

/start va ro'yxatdan o'tish FSM (5 qadam):
  full_name → phone → region → district → confirmation → main_menu
"""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ContentType, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.orm import joinedload

from database.db import Session
from database.models import District, Region, User
from utils.locks import is_processing, user_lock
from utils.referral_service import record_referral_invite

from .common import (
    fmt_error, get_user_by_telegram_id, safe_delete,
    show_main_menu, split_full_name,
)
from ..keyboards import get_districts_keyboard, get_phone_keyboard, get_regions_keyboard
from ..states import UserRegistrationStates

router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════════════════════════

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    args     = message.text.split(maxsplit=1)
    ref_code = args[1].strip() if len(args) > 1 else None
    if ref_code and ref_code.startswith("ref_"):
        await state.update_data(pending_ref_code=ref_code)

    user = get_user_by_telegram_id(message.from_user.id)
    if user:
        await show_main_menu(message, state, user)
    else:
        await message.answer(
            "📝 <b>Ro'yxatdan o'tish</b>\n\n"
            "Assalomu alaykum! Ro'yxatdan o'tish uchun:\n\n"
            "👤 <b>To'liq ismingizni kiriting (F.I.SH):</b>",
            parse_mode="HTML",
        )
        await state.set_state(UserRegistrationStates.waiting_for_full_name)


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRATION FSM
# ══════════════════════════════════════════════════════════════════════════════

@router.message(UserRegistrationStates.waiting_for_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Kamida 2 ta harf kiriting!")
        return
    first, last = split_full_name(message.text.strip())
    await state.update_data(first_name=first, last_name=last,
                             full_name=message.text.strip())
    keyboard = await get_phone_keyboard()
    await message.answer(
        f"✅ <b>{message.text.strip()}</b>\n\n📱 <b>Telefon raqamingizni ulang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
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
async def process_region(callback: types.CallbackQuery, state: FSMContext):
    region_id = int(callback.data.split("_")[1])
    db     = Session()
    region = db.query(Region).filter(Region.id == region_id).first()
    db.close()
    if not region:
        await callback.answer("❌ Viloyat topilmadi!")
        return
    await state.update_data(region_id=region_id)
    keyboard = await get_districts_keyboard(region_id)
    await callback.message.edit_text(
        f"📍 <b>Tumanni tanlang ({region.name_uz}):</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await state.set_state(UserRegistrationStates.waiting_for_district)


@router.callback_query(UserRegistrationStates.waiting_for_district, F.data == "region_back")
async def reg_district_back(callback: types.CallbackQuery, state: FSMContext):
    keyboard = await get_regions_keyboard()
    await callback.message.edit_text(
        "📍 <b>Viloyatingizni tanlang:</b>", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(UserRegistrationStates.waiting_for_region)


@router.callback_query(UserRegistrationStates.waiting_for_district,
                       F.data.startswith("district_"))
async def process_district(callback: types.CallbackQuery, state: FSMContext):
    district_id = int(callback.data.split("_")[1])
    db       = Session()
    district = db.query(District).filter(District.id == district_id).first()
    db.close()
    if not district:
        await callback.answer("❌ Tuman topilmadi!")
        return
    await state.update_data(district_id=district_id)

    data   = await state.get_data()
    db2    = Session()
    region = db2.query(Region).filter(Region.id == data.get("region_id")).first()
    db2.close()

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha",   callback_data="confirm_yes"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_no"),
    ]])
    await callback.message.edit_text(
        f"✅ <b>Tasdiqlash</b>\n\n"
        f"• F.I.SH: {data.get('full_name', '')}\n"
        f"• Telefon: {data['phone']}\n"
        f"• Viloyat: {region.name_uz if region else '—'}\n"
        f"• Tuman: {district.name_uz}\n\n"
        f"<b>Tasdiqlaysizmi?</b>",
        reply_markup=confirm_kb,
        parse_mode="HTML",
    )
    await state.set_state(UserRegistrationStates.confirmation)


@router.callback_query(UserRegistrationStates.confirmation)
async def process_confirmation(callback: types.CallbackQuery, state: FSMContext):
    if is_processing(callback.from_user.id):
        await callback.answer("⏳ Kuting...")
        return

    if callback.data == "confirm_no":
        await safe_delete(callback.message)
        await state.clear()
        await callback.message.answer(
            "❌ Bekor qilindi. Qayta boshlash uchun /start bosing."
        )
        return

    async with user_lock(callback.from_user.id):
        existing = get_user_by_telegram_id(callback.from_user.id)
        if existing:
            await callback.answer("✅ Allaqachon ro'yxatdan o'tgansiz!", show_alert=True)
            await safe_delete(callback.message)
            await state.clear()
            await show_main_menu(callback.message, state, existing)
            return

        data = await state.get_data()
        db   = Session()
        try:
            new_user = User(
                telegram_id=callback.from_user.id,
                first_name=data["first_name"],
                last_name=data.get("last_name", ""),
                phone=data["phone"],
                region_id=data["region_id"],
                district_id=data["district_id"],
                direction_id=None,
            )
            db.add(new_user)
            db.commit()
            new_user_id = new_user.id

            user = db.query(User).options(
                joinedload(User.region),
                joinedload(User.district),
                joinedload(User.direction),
            ).filter(User.telegram_id == callback.from_user.id).first()

            # Referal qayd etish
            pending_ref = data.get("pending_ref_code")
            if pending_ref:
                ok = record_referral_invite(pending_ref, new_user_id)
                if ok:
                    import logging
                    logging.getLogger(__name__).info(
                        "Referal qayd qilindi: code=%s → user_id=%d", pending_ref, new_user_id
                    )

            await callback.answer("✅ Ro'yxatdan o'tildi!", show_alert=True)
            await safe_delete(callback.message)
            await state.clear()

            await show_main_menu(callback.message, state, user)

        except Exception as e:
            db.rollback()
            await callback.answer(fmt_error(e), show_alert=True)
        finally:
            db.close()
