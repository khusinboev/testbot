from aiogram.fsm.state import State, StatesGroup


class UserRegistrationStates(StatesGroup):
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_phone = State()
    waiting_for_region = State()
    waiting_for_district = State()
    waiting_for_direction = State()
    confirmation = State()


class UserMainMenuStates(StatesGroup):
    main_menu = State()


class TestSessionStates(StatesGroup):
    test_confirmation = State()
    test_active = State()