from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from database.db import Session
from database.models import User
from bot.states import TestSessionStates, UserMainMenuStates
from bot.keyboards import get_test_results_keyboard, get_main_menu_keyboard
from utils.test_service import TestService

router = Router()

# Bu faylda barcha test handlerlari registration.py ga ko'chirildi.
# Faqat router ob'ekti eksport qilinadi — main.py ga include qilish uchun.
#
# Nima uchun bu fayl saqlanmoqda:
#   - main.py router importini o'zgartirmaslik uchun
#   - Kelajakda qo'shimcha test handlerlari qo'shish uchun