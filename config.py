import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(i.strip()) for i in os.getenv('ADMIN_IDS', '').split(',') if i.strip()]

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/dtm_bot')

# Flask Admin
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

# Test sozlamalari
TEST_DURATION_MINUTES = 180
MANDATORY_QUESTIONS_PER_SUBJECT = 10   # Matematika, Tarix, Ona tili — har biridan
SPECIALIZED_QUESTIONS_PER_SUBJECT = 30 # Yo'nalish fanlari — har biridan

# Ball tizimi (DTM formati)
MANDATORY_SUBJECT_IDS = [1, 5, 6]      # Matematika, Tarix, Ona tili
MANDATORY_POINTS_PER_QUESTION = 1.1    # Majburiy fanlar uchun
SPECIALIZED_HIGH_POINTS = 3.1          # 1-ixtisoslashgan fan
SPECIALIZED_LOW_POINTS = 2.1           # 2-ixtisoslashgan fan

# Vaqt zonasi
TIMEZONE = 'Asia/Tashkent'