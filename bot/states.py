from aiogram.fsm.state import State, StatesGroup

class UserRegistrationStates(StatesGroup):
    """States for user registration flow"""
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_phone = State()
    waiting_for_region = State()
    waiting_for_district = State()
    waiting_for_direction = State()
    confirmation = State()

class UserMainMenuStates(StatesGroup):
    """States for main menu"""
    main_menu = State()
    test_menu = State()

class TestSessionStates(StatesGroup):
    """States for test session"""
    test_starting = State()
    test_active = State()
    test_question = State()
    test_confirmation = State()
    test_completed = State()

class ChannelCheckStates(StatesGroup):
    """States for channel subscription check"""
    checking_channels = State()