from aiogram import Router, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from database.db import Session
from database.models import Direction, User
import hashlib

router = Router()


@router.inline_query()
async def direction_inline_search(inline_query: types.InlineQuery):
    """
    Inline qidiruv: @bot yo'nalish nomi
    Foydalanuvchi tanlagan yo'nalish direction_id sifatida qaytariladi.
    """
    query = inline_query.query.strip()

    # "yo'nalish: " prefixini olib tashlash
    if query.lower().startswith("yo'nalish:"):
        query = query[len("yo'nalish:"):].strip()
    elif query.lower().startswith("yo'nalish:"):
        query = query[10:].strip()

    db = Session()
    try:
        if query:
            directions = db.query(Direction).filter(
                Direction.name_uz.ilike(f"%{query}%")
            ).limit(50).all()
        else:
            # Bo'sh query — birinchi 50 ta
            directions = db.query(Direction).limit(50).all()

        results = []
        for d in directions:
            # Har bir yo'nalish uchun unique ID
            result_id = hashlib.md5(d.id.encode()).hexdigest()[:8]
            results.append(
                InlineQueryResultArticle(
                    id=result_id,
                    title=d.name_uz,
                    description=f"Kod: {d.id}",
                    input_message_content=InputTextMessageContent(
                        message_text=f"direction_chosen:{d.id}"
                    )
                )
            )

        await inline_query.answer(
            results,
            cache_time=10,
            is_personal=True
        )
    finally:
        db.close()