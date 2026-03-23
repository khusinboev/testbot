"""
utils/channel_service.py
Majburiy kanal obuna tekshiruvi.
"""
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

logger = logging.getLogger(__name__)


async def get_active_channels() -> list:
    """DB dan aktiv kanallar ro'yxatini oladi."""
    from database.db import Session
    from database.models import MandatoryChannel
    db = Session()
    channels = db.query(MandatoryChannel).filter(
        MandatoryChannel.is_active.is_(True)
    ).all()
    db.close()
    return channels


async def check_user_subscriptions(bot: Bot, telegram_id: int) -> list:
    """
    Foydalanuvchi obuna bo'lmagan kanallar ro'yxatini qaytaradi.
    Bo'sh ro'yxat = barcha kanallarga obuna.
    """
    channels = await get_active_channels()
    not_subscribed = []

    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, telegram_id)
            if member.status in ('left', 'kicked', 'banned'):
                not_subscribed.append(ch)
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning("Kanal tekshiruv xato (%s): %s", ch.channel_id, e)
            # Bot kanalda admin emas yoki kanal topilmadi — o'tkazib yuboramiz
        except Exception as e:
            logger.error("check_user_subscriptions xato: %s", e)

    return not_subscribed


def build_subscribe_keyboard(not_subscribed: list) -> InlineKeyboardMarkup:
    """Obuna bo'lmagan kanallar uchun tugmalar."""
    buttons = []
    for ch in not_subscribed:
        url = ch.invite_link or f"https://t.me/{ch.channel_id.lstrip('@')}"
        buttons.append([
            InlineKeyboardButton(
                text=f"📢 {ch.channel_name}",
                url=url
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="✅ Tekshirish",
            callback_data="check_subscription"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def subscription_gate(bot: Bot, telegram_id: int, message_or_cb) -> bool:
    """
    True qaytarsa — barcha kanallarga obuna, davom etish mumkin.
    False qaytarsa — xabar yuborildi, davom etmaslik kerak.
    """
    not_subscribed = await check_user_subscriptions(bot, telegram_id)
    if not not_subscribed:
        return True

    keyboard = build_subscribe_keyboard(not_subscribed)
    channel_list = "\n".join(
        f"  • <b>{ch.channel_name}</b>" for ch in not_subscribed
    )
    text = (
        "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
        f"{channel_list}\n\n"
        "Obuna bo'lgandan keyin <b>«✅ Tekshirish»</b> tugmasini bosing."
    )

    try:
        if hasattr(message_or_cb, 'answer'):
            await message_or_cb.answer(text, reply_markup=keyboard, parse_mode="HTML")
        elif hasattr(message_or_cb, 'message'):
            await message_or_cb.message.answer(
                text, reply_markup=keyboard, parse_mode="HTML"
            )
    except Exception as e:
        logger.error("subscription_gate xabar xato: %s", e)

    return False
