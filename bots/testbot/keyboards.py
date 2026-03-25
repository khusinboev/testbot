"""
bots/testbot/keyboards.py

Barcha klaviaturalar — faqat shu bot uchun.
Umumiy logika yo'q, boshqa bot yaratishda bu fayl butunlay boshqacha.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from database.db import Session
from database.models import Direction, District, Region


# ══════════════════════════════════════════════════════════════════════════════
# RO'YXATDAN O'TISH
# ══════════════════════════════════════════════════════════════════════════════

async def get_regions_keyboard() -> InlineKeyboardMarkup:
    db      = Session()
    regions = db.query(Region).all()
    db.close()

    buttons = [
        InlineKeyboardButton(text=r.name_uz, callback_data=f"region_{r.id}")
        for r in regions
    ]
    rows = []
    for i in range(0, len(buttons), 2):
        row = [buttons[i]]
        if i + 1 < len(buttons):
            row.append(buttons[i + 1])
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def get_districts_keyboard(region_id: int) -> InlineKeyboardMarkup:
    db        = Session()
    districts = db.query(District).filter(District.region_id == region_id).all()
    db.close()

    buttons = [
        InlineKeyboardButton(text=d.name_uz, callback_data=f"district_{d.id}")
        for d in districts
    ]
    rows = []
    for i in range(0, len(buttons), 2):
        row = [buttons[i]]
        if i + 1 < len(buttons):
            row.append(buttons[i + 1])
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀ Orqaga", callback_data="region_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def get_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni ulash", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# YO'NALISH
# ══════════════════════════════════════════════════════════════════════════════

async def get_directions_keyboard(page: int = 0, per_page: int = 20) -> InlineKeyboardMarkup:
    db         = Session()
    directions = db.query(Direction).all()
    db.close()

    start        = page * per_page
    page_items   = directions[start: start + per_page]
    total        = len(directions)
    keyboard     = []

    for d in page_items:
        name = d.name_uz if len(d.name_uz) <= 35 else d.name_uz[:33] + "…"
        keyboard.append([InlineKeyboardButton(text=name, callback_data=f"direction_{d.id}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"direction_page_{page - 1}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"direction_page_{page + 1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton(
        text="🔍 Qidirish", switch_inline_query_current_chat="yo'nalish: "
    )])
    keyboard.append([InlineKeyboardButton(text="◀ Orqaga", callback_data="direction_list_back")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def get_direction_search_results(query: str) -> InlineKeyboardMarkup:
    db         = Session()
    directions = db.query(Direction).filter(
        Direction.name_uz.ilike(f"%{query}%")
    ).limit(20).all()
    db.close()

    keyboard = [
        [InlineKeyboardButton(
            text=(d.name_uz if len(d.name_uz) <= 35 else d.name_uz[:33] + "…"),
            callback_data=f"direction_{d.id}",
        )]
        for d in directions
    ]
    if not keyboard:
        keyboard.append([InlineKeyboardButton(
            text="❌ Topilmadi", callback_data="direction_search_empty"
        )])
    keyboard.append([InlineKeyboardButton(
        text="◀ Ro'yxatga qaytish", callback_data="direction_search_back"
    )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ══════════════════════════════════════════════════════════════════════════════
# ASOSIY MENYU
# ══════════════════════════════════════════════════════════════════════════════

async def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Referal yoqilgan bo'lsa — "🔗 Referalim" tugmasi qo'shiladi.
    """
    try:
        from utils.referral_service import get_referral_settings
        referral_enabled = get_referral_settings().is_enabled
    except Exception:
        referral_enabled = False

    rows = [
        [KeyboardButton(text="🧪 Testni boshlash")],
        [KeyboardButton(text="📊 Natijalarim"), KeyboardButton(text="🏆 Reyting")],
    ]
    if referral_enabled:
        rows.append([KeyboardButton(text="🔗 Referalim"), KeyboardButton(text="👤 Profilim")])
        rows.append([KeyboardButton(text="❓ Yordam")])
    else:
        rows.append([KeyboardButton(text="👤 Profilim"), KeyboardButton(text="❓ Yordam")])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

def get_test_answer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🅰️ A", callback_data="answer_A"),
            InlineKeyboardButton(text="🅱️ B", callback_data="answer_B"),
        ],
        [
            InlineKeyboardButton(text="🅲️ C", callback_data="answer_C"),
            InlineKeyboardButton(text="🅳️ D", callback_data="answer_D"),
        ],
        [InlineKeyboardButton(text="⏭️ O'tkazish",     callback_data="answer_skip")],
        [InlineKeyboardButton(text="🏁 Testni yakunlash", callback_data="test_finish")],
    ])


def get_test_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Boshlash",   callback_data="test_start_confirm"),
        InlineKeyboardButton(text="❌ Bekor qil", callback_data="test_cancel"),
    ]])


def get_test_results_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Yana test qol")],
            [KeyboardButton(text="📊 Natijalarni ko'rish")],
            [KeyboardButton(text="🏠 Bosh menyu")],
        ],
        resize_keyboard=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PROFIL
# ══════════════════════════════════════════════════════════════════════════════

def get_profile_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ F.I.SH ni tahrirlash",      callback_data="profile_edit_name")],
        [InlineKeyboardButton(text="📚 Yo'nalishni o'zgartirish", callback_data="profile_edit_direction")],
        [InlineKeyboardButton(text="◀ Orqaga",                    callback_data="profile_back")],
    ])