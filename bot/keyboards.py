from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import Session
from database.models import Region, District, Direction

async def get_regions_keyboard() -> InlineKeyboardMarkup:
    """Get inline keyboard with all regions"""
    db = Session()
    regions = db.query(Region).all()
    db.close()
    
    buttons = []
    for region in regions:
        buttons.append(
            InlineKeyboardButton(
                text=region.name_uz,
                callback_data=f"region_{region.id}"
            )
        )
    
    # Create grid layout (2 columns)
    keyboard = []
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.append([buttons[i], buttons[i + 1]])
        else:
            keyboard.append([buttons[i]])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def get_districts_keyboard(region_id: int) -> InlineKeyboardMarkup:
    """Get inline keyboard with districts for selected region"""
    db = Session()
    districts = db.query(District).filter(District.region_id == region_id).all()
    db.close()
    
    buttons = []
    for district in districts:
        buttons.append(
            InlineKeyboardButton(
                text=district.name_uz,
                callback_data=f"district_{district.id}"
            )
        )
    
    # Create grid layout (2 columns)
    keyboard = []
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.append([buttons[i], buttons[i + 1]])
        else:
            keyboard.append([buttons[i]])
    
    # Add back button
    keyboard.append([InlineKeyboardButton(text="◀ Orqaga", callback_data="region_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def get_directions_keyboard(page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Get inline keyboard with directions with pagination"""
    db = Session()
    directions = db.query(Direction).all()
    db.close()
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_directions = directions[start_idx:end_idx]
    
    buttons = []
    for direction in page_directions:
        buttons.append(
            InlineKeyboardButton(
                text=f"{direction.id} - {direction.name_uz[:25]}...",
                callback_data=f"direction_{direction.id}"
            )
        )
    
    # Create grid layout (1 column for better readability)
    keyboard = []
    for button in buttons:
        keyboard.append([button])
    
    # Add navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"direction_page_{page-1}"))
    
    total_pages = (len(directions) + per_page - 1) // per_page
    if end_idx < len(directions):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"direction_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add back button
    keyboard.append([InlineKeyboardButton(text="◀ Orqaga", callback_data="region_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def get_phone_keyboard() -> ReplyKeyboardMarkup:
    """Get keyboard for phone number sharing"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yubor", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qil")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

async def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard for registered users"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Testni boshlash")],
            [KeyboardButton(text="📊 Natijalarim"), KeyboardButton(text="🏆 Reyting")],
            [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="⚙️ Sozlamalar")],
            [KeyboardButton(text="❓ Yordam")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_test_answer_keyboard() -> InlineKeyboardMarkup:
    """Get inline keyboard for test question answers"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
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
    return keyboard

def get_test_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Get confirmation keyboard for test start"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Boshlash", callback_data="test_start_confirm"),
            InlineKeyboardButton(text="❌ Bekor qil", callback_data="test_cancel")
        ]
    ])
    return keyboard

def get_test_results_keyboard() -> ReplyKeyboardMarkup:
    """Get keyboard for test results menu"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Yana test qol")],
            [KeyboardButton(text="📊 Natijalarni ko'rish")],
            [KeyboardButton(text="🏠 Bosh menyu")]
        ],
        resize_keyboard=True
    )
    return keyboard