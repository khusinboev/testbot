"""
bots/testbot/states.py

FSM holatlari — faqat shu bot uchun.
Boshqa bot yaratishda bu fayl butunlay boshqacha bo'lishi mumkin.
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
    edit_full_name      = State()
    edit_direction      = State()
    searching_direction = State()