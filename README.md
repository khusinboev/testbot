# DTM Preparation Telegram Bot

A comprehensive Telegram bot for high school students to prepare for Uzbekistan's DTM (entrance exam) with timed practice tests, ranking system, and admin management.

## Features

- **User Registration**: Name, phone, region/district selection
- **Timed Practice Tests**: 180-minute sessions with 90 questions (30 mandatory + 60 specialized)
- **Scoring System**: DTM-compliant scoring (mandatory 1.1pts, specialized 3.1/2.1pts)
- **Ranking**: Real-time leaderboard after test completion
- **Admin Panel**: Web dashboard for test management, user monitoring, analytics
- **Multi-language**: Uzbek (Cyrillic/Latin), Russian support

## Tech Stack

- **Backend**: Python 3.8+
- **Bot Framework**: Aiogram 3.x
- **Database**: PostgreSQL + SQLAlchemy
- **Web Admin**: Flask + Bootstrap
- **Scheduling**: APScheduler
- **Data Processing**: Pandas, OpenPyXL

## Setup

### 1. Clone and Install Dependencies

```bash
cd d:\own\projects\python\test-bot
pip install -r requirements.txt
```

### 2. Database Setup

Create PostgreSQL database and update `.env`:

```bash
cp .env.example .env
# Edit .env with your database credentials
```

Initialize database:

```bash
python init_db.py
```

### 3. Bot Configuration

1. Create Telegram bot via [@BotFather](https://t.me/botfather)
2. Add bot token to `.env`
3. Add admin Telegram IDs to `.env`

### 4. Run the Application

**Bot:**
```bash
python -m bot.main
```

**Admin Panel:**
```bash
python -m admin.app
```

Visit `http://localhost:5000` for admin dashboard.

## Project Structure

```
├── bot/                    # Telegram bot
│   ├── main.py            # Bot entry point
│   └── handlers/          # Bot command handlers
├── admin/                 # Web admin panel
│   ├── app.py            # Flask application
│   └── templates/        # HTML templates
├── database/             # Database models and setup
│   ├── models.py         # SQLAlchemy models
│   └── db.py            # Database connection & seeding
├── utils/                # Utility functions
│   ├── pdf_parser.py     # Parse directions from PDF
│   └── scoring.py       # Score calculation logic
├── tests/                # Unit tests
├── regions.json         # Region data
├── districts.json       # District data
├── Fanlar_majmuasi_2025-2026.pdf  # Directions PDF
└── requirements.txt     # Python dependencies
```

## Database Schema

### Core Tables
- `users` - Student registrations
- `regions`/`districts` - Geographic data
- `directions` - Test directions (subject combinations)
- `subjects` - Available subjects
- `questions` - Test questions
- `test_sessions` - Scheduled exams
- `user_answers` - Student responses
- `leaderboard` - Final rankings

## Development Phases

### Phase 1: Database & Setup ✓
- Database schema design
- Seed data (regions, districts, directions)
- Basic project structure

### Phase 2: User Registration & Bot Basics
- Registration flow (FSM)
- Main menu navigation
- Channel subscription checks

### Phase 3: Test Taking & Questions
- Test session management
- Question display & navigation
- Auto-submit functionality

### Phase 4: Scoring & Ranking
- Score calculation
- Leaderboard generation
- Results display

### Phase 5: Admin Web Dashboard
- User management
- Test creation
- Excel import functionality

### Phase 6: Polish & Features
- Admin Telegram commands
- Performance optimization
- Comprehensive testing

## API Endpoints

### Admin Web API
- `GET /` - Dashboard
- `GET /users` - User management
- `GET /tests` - Test management
- `POST /api/tests` - Create test session
- `POST /api/questions/import` - Import questions from Excel

## Testing

Run tests:
```bash
python -m pytest tests/
```

## Deployment

### Production Setup
1. Use production PostgreSQL instance
2. Set `FLASK_ENV=production` in `.env`
3. Use proper secret keys
4. Set up reverse proxy (nginx)
5. Configure SSL certificates
6. Set up monitoring/logging

### Docker (Optional)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "bot.main"]
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit pull request

## License

This project is licensed under the MIT License.