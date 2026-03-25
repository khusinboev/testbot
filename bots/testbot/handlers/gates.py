"""
bots/testbot/handlers/gates.py

Foydalanuvchi botga kirish huquqini tekshiradigan "eshiklar":
  - subscription_gate  → majburiy kanallar obunasi
  - referral_gate      → referal talab

Har ikki funksiya True/False qaytaradi:
  True  → o'tish mumkin
  False → xabar yuborildi, davom etish kerak emas
"""

from __future__ import annotations

import urllib.parse

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.channel_service import build_subscribe_keyboard, check_user_subscriptions, subscription_gate
from utils.referral_service import check_referral_gate

from .common import get_bot_username, get_user_by_telegram_id, safe_delete, show_main_menu

router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# REFERRAL GATE
# ══════════════════════════════════════════════════════════════════════════════

async def referral_gate(bot: Bot, telegram_id: int, message: types.Message) -> bool:
    result = check_referral_gate(telegram_id)
    if result["allowed"]:
        return True

    bot_username = await get_bot_username(bot)
    link_url     = f"https://t.me/{bot_username}?start={result['link_code']}"

    invited   = result["invited"]
    required  = result["required"]
    remaining = result["remaining"]
    bar       = "🟢" * min(invited, required) + "⚪️" * (required - min(invited, required))

    share_url = (
        "https://t.me/share/url"
        f"?url={urllib.parse.quote(link_url, safe='')}"
        f"&text={urllib.parse.quote('👨‍🏫Sizni DTM testlar botiga taklif qilaman! 🎓', safe='')}"
    )

    await message.answer(
        f"🔗 <b>Referal talab</b>\n\n"
        f"Botdan foydalanish uchun <b>{required}</b> ta do'stingizni taklif qiling.\n\n"
        f"📊 Holat: <b>{invited}/{required}</b>\n{bar}\n\n"
        f"🔗 Sizning havolangiz:\n<code>{link_url}</code>\n\n"
        f"⏳ <i>Qoldi: {remaining} ta</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url)],
        ]),
        parse_mode="HTML",
    )
    return False


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "check_referral")
async def handle_check_referral(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    uid    = callback.from_user.id
    result = check_referral_gate(uid)

    if result["allowed"]:
        await callback.answer("✅ Tabriklaymiz! Talab bajarildi!", show_alert=True)
        await safe_delete(callback.message)
        user = get_user_by_telegram_id(uid)
        if user:
            await show_main_menu(callback.message, state, user)
        else:
            await callback.message.answer("Boshlash uchun /start bosing.")
        return

    invited   = result["invited"]
    required  = result["required"]
    remaining = result["remaining"]
    bar       = "🟢" * min(invited, required) + "⚪️" * (required - min(invited, required))

    await callback.answer(f"❌ Hali {remaining} ta referal kerak!", show_alert=True)
    try:
        bot_username = await get_bot_username(bot)
        link_url = f"https://t.me/{bot_username}?start={result['link_code']}"
        await callback.message.edit_text(
            f"🔗 <b>Referal talab</b>\n\n"
            f"📊 Holat: <b>{invited}/{required}</b>\n{bar}\n\n"
            f"🔗 Havolangiz:\n<code>{link_url}</code>\n\n"
            f"⏳ <i>Qoldi: {remaining} ta</i>",
            reply_markup=callback.message.reply_markup,
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(
    callback: types.CallbackQuery, state: FSMContext, bot: Bot
):
    uid     = callback.from_user.id
    not_sub = await check_user_subscriptions(bot, uid)

    if not not_sub:
        await callback.answer("✅ Rahmat! Barcha kanallarga obuna bo'ldingiz.", show_alert=True)
        await safe_delete(callback.message)
        user = get_user_by_telegram_id(uid)
        if user:
            if not await referral_gate(bot, uid, callback.message):
                return
            await show_main_menu(callback.message, state, user)
        else:
            await callback.message.answer("Ro'yxatdan o'tish uchun /start bosing.")
    else:
        await callback.answer("❌ Hali obuna bo'lmagan kanallar bor!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(
                reply_markup=build_subscribe_keyboard(not_sub)
            )
        except Exception:
            pass
