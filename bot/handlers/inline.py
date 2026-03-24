"""
bot/handlers/inline.py

YANGILANDI:
  - Inline handler faqat yo'nalish qidirish kontekstida ishlaydi.
    Agar query "yo'nalish:" prefiksi bilan boshlanmasa — bo'sh javob qaytariladi.
    Bu boshqa kontekstlarda (masalan, referalni ulashishda) inline mode ni
    tasodifan ishga tushirib yuborishning oldini oladi.

  - Referal ulashish tugmasi switch_inline_query o'rniga t.me/share/url ishlatadi,
    shuning uchun bot username matn boshiga qo'shilmaydi.
"""
from aiogram import Router, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from database.db import Session
from database.models import Direction
import hashlib

router = Router()

# Faqat shu prefiks bilan kelgan so'rovlar yo'nalish qidiruviga yo'naltiriladi
DIRECTION_PREFIXES = ("yo'nalish: ", "yo'nalish:", "yo'nalish ", "yonalish: ", "yonalish:")


def _is_direction_query(query: str) -> bool:
    """Inline query yo'nalish qidiruvi kontekstida ekanligini tekshiradi."""
    q_low = query.lower().strip()
    for prefix in DIRECTION_PREFIXES:
        if q_low.startswith(prefix):
            return True
    return False


def _strip_prefix(query: str) -> str:
    """Prefiksni olib tashlaydi."""
    q_low = query.lower().strip()
    for prefix in DIRECTION_PREFIXES:
        if q_low.startswith(prefix):
            return query[len(prefix):].strip()
    return query.strip()


@router.inline_query()
async def direction_inline_search(inline_query: types.InlineQuery):
    """
    Inline qidiruv: faqat "yo'nalish: <qidiruv>" formatida ishlaydi.

    Boshqa holatlarda (masalan, foydalanuvchi boshqa maqsadda inline
    rejimni ochgan bo'lsa) — bo'sh natija bilan darhol javob qaytariladi.
    Bu share tugmasi va boshqa inline trigger larning aralashib ketishini
    oldini oladi.
    """
    query = inline_query.query or ""

    # Prefiks yo'q — yo'nalish qidiruvi emas, bo'sh javob
    if not _is_direction_query(query):
        await inline_query.answer(
            results=[],
            cache_time=1,
            is_personal=True,
            switch_pm_text="Botni ochish uchun bosing",
            switch_pm_parameter="start",
        )
        return

    # Prefiksni olib tashlab, asosiy qidiruv so'zini olamiz
    search_term = _strip_prefix(query)

    db = Session()
    try:
        if search_term:
            directions = db.query(Direction).filter(
                Direction.name_uz.ilike(f"%{search_term}%")
            ).limit(50).all()
        else:
            directions = db.query(Direction).limit(50).all()

        results = []
        for d in directions:
            result_id = hashlib.md5(d.id.encode()).hexdigest()[:8]
            results.append(
                InlineQueryResultArticle(
                    id=result_id,
                    title=d.name_uz,
                    description=f"📚 Kod: {d.id}",
                    # Bot darhol bu xabarni o'chiradi — user ko'rmaydi
                    input_message_content=InputTextMessageContent(
                        message_text=f"direction_chosen:{d.id}"
                    ),
                )
            )

        if not results:
            results.append(
                InlineQueryResultArticle(
                    id="not_found",
                    title="❌ Hech narsa topilmadi",
                    description=f"'{search_term}' bo'yicha yo'nalish yo'q",
                    input_message_content=InputTextMessageContent(
                        message_text="direction_search_failed"
                    )
                )
            )

        await inline_query.answer(results, cache_time=10, is_personal=True)
    finally:
        db.close()