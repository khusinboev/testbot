from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Handle /help command"""
    text = """
❓ <b>Yordam</b>

<b>Asosiy buyruqlar:</b>
/start - Botni ishga tushirish / Qayta boshlash
/help - Yordam
/profile - Profilingizni ko'rish

<b>Test jarayoni:</b>
1. /start buyrug'i bilan ro'yxatdan o'ting (avtomatik tarzda)
2. Shaxsiy ma'lumotlarni kiriting
3. Yo'nalishni tanlang
4. Testni boshlang
5. 180 daqiqa ichida 90 ta savolni javoblang

<b>Qabul qilinadigan ma'lumotlar:</b>
• Ism va familiya
• Telefon raqami (9+ raqam)
• Viloyat va tuman
• Ta'lim yo'nalishi (167 ta variant)

🎓 <b>DTM Test Bot</b> - Sizning muvaffaqiyatingiz uchun!
"""
    await message.reply(text, parse_mode="HTML")

# @router.message(Command("profile"))
# async def cmd_profile(message: types.Message):
#     """Handle /profile command"""
#     text = """
# 👤 <b>Profilingiz</b>
#
# Hozircha profilingiz mavjud emas yoki ro'yxatdan o'tmagan ekaningiz.
#
# <i>Ro'yxatdan o'tgandan keyin bu yerda:
# - Shaxsiy ma'lumotlaringiz
# - Test natijalaringiz
# - Reytingingiz ko'rinadi</i>
#
# <b>Ro'yxatdan o'tish uchun:</b> /start buyrug'ini yuboring
# """
#     keyboard = await get_main_menu_keyboard()
#     await message.reply(text, parse_mode="HTML", reply_markup=keyboard)

# @router.message(F.text)
# async def echo_message(message: types.Message):
#     """Echo text messages that are not commands with helpful prompt"""
#     text = f"""
# 👋 Salom <b>{message.from_user.first_name}</b>!
#
# Siz yuborgan xabar: <code>{message.text}</code>
#
# <i>Bu testbot asosiy buyruqlarni qabul qiladi:</i>
# • /start - Boshlash yoki qayta boshlash
# • /help - Yordam
# • /profile - Profilingiz
# """
#     await message.reply(text, parse_mode="HTML")
