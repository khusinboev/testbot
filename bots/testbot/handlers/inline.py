"""
bots/testbot/handlers/inline.py

Inline yo'nalish qidirish — faqat "yo'nalish:" prefiksi bilan ishlaydi.
"""

import hashlib

from aiogram import Router, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from database.db import Session
from database.models import Direction

router = Router()

_DIRECTION_PREFIXES = ("yo'nalish: ", "yo'nalish:", "yo'nalish ", "yonalish: ", "yonalish:")


def _is_direction_query(query: str) -> bool:
    q_low = query.lower().strip()
    return any(q_low.startswith(p) for p in _DIRECTION_PREFIXES)


def _strip_prefix(query: str) -> str:
    q_low = query.lower().strip()
    for prefix in _DIRECTION_PREFIXES:
        if q_low.startswith(prefix):
            return query[len(prefix):].strip()
    return query.strip()


@router.inline_query()
async def direction_inline_search(inline_query: types.InlineQuery):
    query = inline_query.query or ""

    if not _is_direction_query(query):
        await inline_query.answer(
            results=[],
            cache_time=1,
            is_personal=True,
            switch_pm_text="Botni ochish uchun bosing",
            switch_pm_parameter="start",
        )
        return

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
            results.append(InlineQueryResultArticle(
                id=result_id,
                title=d.name_uz,
                description=f"📚 Kod: {d.id}",
                input_message_content=InputTextMessageContent(
                    message_text=f"direction_chosen:{d.id}"
                ),
            ))

        if not results:
            results.append(InlineQueryResultArticle(
                id="not_found",
                title="❌ Hech narsa topilmadi",
                description=f"'{search_term}' bo'yicha yo'nalish yo'q",
                input_message_content=InputTextMessageContent(
                    message_text="direction_search_failed"
                ),
            ))

        await inline_query.answer(results, cache_time=10, is_personal=True)
    finally:
        db.close()
