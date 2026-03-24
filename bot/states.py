"""
bot/states.py

O'ZGARISHLAR:
  - UserMainMenuStates.main_menu OLIB TASHLANDI.
    Bu state amalda keraksiz edi — faqat reply keyboard handlerlarni
    cheklash uchun ishlatilardi, lekin bu F.text == "..." filter bilan
    ham ishlaydi va state siz ham to'g'ri ishlaydi.

    Foydalari yo'q edi, zararlari bor edi:
      * FSM storageда keraksiz yozuv
      * show_main_menu dan keyin state.set_state(main_menu) kerak edi —
        unutilsa handlerlar ishlamay qolishi mumkin edi
      * test_active holatda main_menu handlerlari ishlamasdi
        (lekin shu holatda ishlashi ham to'g'ri bo'lmasdi)

    Endi handlerlar:
      - state yo'q holda ishlaydi (ya'ni har qanday holat/yo'q holatda)
      - test_active holatini o'zi tekshirib, test jarayonida
        tugmalarni e'tiborsiz qoldiradi
"""
from aiogram.fsm.state import State, StatesGroup


class UserRegistrationStates(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_phone     = State()
    waiting_for_region    = State()
    waiting_for_district  = State()
    confirmation          = State()


class TestSessionStates(StatesGroup):
    test_confirmation     = State()
    test_active           = State()
    waiting_for_direction = State()
    searching_direction   = State()


class ProfileEditStates(StatesGroup):
    edit_full_name        = State()
    edit_direction        = State()
    searching_direction   = State()