from aiogram.fsm.state import State, StatesGroup


class UserRegistrationStates(StatesGroup):
    waiting_for_full_name = State()  # F.I.SH — bitta maydonda
    waiting_for_phone = State()
    waiting_for_region = State()
    waiting_for_district = State()
    confirmation = State()


class UserMainMenuStates(StatesGroup):
    main_menu = State()


class TestSessionStates(StatesGroup):
    test_confirmation = State()
    test_active = State()
    waiting_for_direction = State()  # Test oldida yo'nalish so'rash


class ProfileEditStates(StatesGroup):
    edit_full_name = State()
    edit_direction = State()