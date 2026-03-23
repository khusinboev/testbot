import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/dtm_bot')

# Flask Admin
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

# Test Settings
TEST_DURATION_MINUTES = 180  # 3 hours
MANDATORY_QUESTIONS_PER_SUBJECT = 10  # Math, Native Lang, History
SPECIALIZED_QUESTIONS_PER_SUBJECT = 30  # Per direction subject

# Scoring (DTM format)
MANDATORY_POINTS_PER_QUESTION = 1.1  # Math, History, Native Language
SPECIALIZED_HIGH_POINTS = 3.1  # Main specialized subject
SPECIALIZED_LOW_POINTS = 2.1   # Secondary specialized subject

# Mandatory subject IDs
MANDATORY_SUBJECT_IDS = [1, 5, 6]  # Math, History, Native Language
SPECIALIZED_QUESTIONS_PER_SUBJECT = 30  # Subject 1 and 2

# Scoring
MANDATORY_POINTS_PER_QUESTION = 1.1
SPECIALIZED_SUBJECT1_POINTS = 3.1
SPECIALIZED_SUBJECT2_POINTS = 2.1

# Timezone (Uzbekistan)
TIMEZONE = 'Asia/Tashkent'