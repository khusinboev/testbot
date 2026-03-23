from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import Session
from database.models import Region, District, Direction


async def get_regions_keyboard() -> InlineKeyboardMarkup:
    db = Session()
    regions = db.query(Region).all()
    db.close()
    buttons = [
        InlineKeyboardButton(text=r.name_uz, callback_data=f"region_{r.id}")
        for r in regions
    ]
    keyboard = []
    for i in range(0, len(buttons), 2):
        row = [buttons[i]]
        if i + 1 < len(buttons):
            row.append(buttons[i + 1])
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def get_districts_keyboard(region_id: int) -> InlineKeyboardMarkup:
    db = Session()
    districts = db.query(District).filter(District.region_id == region_id).all()
    db.close()
    buttons = [
        InlineKeyboardButton(text=d.name_uz, callback_data=f"district_{d.id}")
        for d in districts
    ]
    keyboard = []
    for i in range(0, len(buttons), 2):
        row = [buttons[i]]
        if i + 1 < len(buttons):
            row.append(buttons[i + 1])
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="◀ Orqaga", callback_data="region_back")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def get_directions_keyboard(page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    db = Session()
    directions = db.query(Direction).all()
    db.close()

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_directions = directions[start_idx:end_idx]

    keyboard = []
    for d in page_directions:
        # Nom 30 belgidan uzun bo'lsagina qisqartirish
        name = d.name_uz if len(d.name_uz) <= 30 else d.name_uz[:28] + "…"
        keyboard.append([
            InlineKeyboardButton(text=name, callback_data=f"direction_{d.id}")
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"direction_page_{page - 1}"))
    if end_idx < len(directions):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"direction_page_{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(text="◀ Orqaga", callback_data="region_back")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def get_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yubor", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qil")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


async def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Testni boshlash")],
            [KeyboardButton(text="📊 Natijalarim"), KeyboardButton(text="🏆 Reyting")],
            [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="⚙️ Sozlamalar")],
            [KeyboardButton(text="❓ Yordam")]
        ],
        resize_keyboard=True
    )


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
        [InlineKeyboardButton(text="⏭️ O'tkazish", callback_data="answer_skip")],
        [InlineKeyboardButton(text="🏁 Testni yakunlash", callback_data="test_finish")]
    ])


def get_test_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Boshlash", callback_data="test_start_confirm"),
        InlineKeyboardButton(text="❌ Bekor qil", callback_data="test_cancel")
    ]])


def get_test_results_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Yana test qol")],
            [KeyboardButton(text="📊 Natijalarni ko'rish")],
            [KeyboardButton(text="🏠 Bosh menyu")]
        ],
        resize_keyboard=True
    )