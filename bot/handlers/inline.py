from aiogram import Router, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from database.db import Session
from database.models import Direction
import hashlib

router = Router()


@router.inline_query()
async def direction_inline_search(inline_query: types.InlineQuery):
    """
    Inline qidiruv: @bot yo'nalish nomi
    Natija tanlanganda: "direction_chosen:ID" xabari yuboriladi (bot darhol o'chiradi).
    """
    query = inline_query.query.strip()

    # "yo'nalish: " prefixini olib tashlash
    for prefix in ("yo'nalish: ", "yo'nalish:", "yo'nalish "):
        if query.lower().startswith(prefix):
            query = query[len(prefix):].strip()
            break

    db = Session()
    try:
        if query:
            directions = db.query(Direction).filter(
                Direction.name_uz.ilike(f"%{query}%")
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
                    # Chiroyli thumbnail — harfdan iborat
                    thumb_url=None,
                )
            )

        if not results:
            results.append(
                InlineQueryResultArticle(
                    id="not_found",
                    title="❌ Hech narsa topilmadi",
                    description=f"'{query}' bo'yicha yo'nalish yo'q",
                    input_message_content=InputTextMessageContent(
                        message_text="direction_search_failed"
                    )
                )
            )

        await inline_query.answer(results, cache_time=10, is_personal=True)
    finally:
        db.close()