from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Float, ForeignKey, JSON, BigInteger, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Region(Base):
    __tablename__ = 'regions'
    id       = Column(Integer, primary_key=True)
    name_uz  = Column(String(255), nullable=False)
    name_oz  = Column(String(255), nullable=False)
    name_ru  = Column(String(255), nullable=False)
    districts = relationship("District", back_populates="region")
    users     = relationship("User", back_populates="region")


class District(Base):
    __tablename__ = 'districts'
    id        = Column(Integer, primary_key=True)
    region_id = Column(Integer, ForeignKey('regions.id'), nullable=False)
    name_uz   = Column(String(255), nullable=False)
    name_oz   = Column(String(255), nullable=False)
    name_ru   = Column(String(255), nullable=False)
    region    = relationship("Region", back_populates="districts")
    users     = relationship("User", back_populates="district")


class Direction(Base):
    __tablename__ = 'directions'
    id         = Column(String(10), primary_key=True)
    name_uz    = Column(String(255), nullable=False)
    name_oz    = Column(String(255), nullable=False)
    name_ru    = Column(String(255), nullable=False)
    subject1_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    subject2_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    subject1   = relationship("Subject", foreign_keys=[subject1_id])
    subject2   = relationship("Subject", foreign_keys=[subject2_id])
    users      = relationship("User", back_populates="direction")


class Subject(Base):
    __tablename__ = 'subjects'
    id                    = Column(Integer, primary_key=True)
    name_uz               = Column(String(255), nullable=False)
    name_oz               = Column(String(255), nullable=False)
    name_ru               = Column(String(255), nullable=False)
    question_count        = Column(Integer, default=0)
    points_per_question   = Column(Float, default=1.0)
    questions             = relationship("Question", back_populates="subject")
    directions_as_subject1 = relationship(
        "Direction", foreign_keys=[Direction.subject1_id], overlaps="subject1"
    )
    directions_as_subject2 = relationship(
        "Direction", foreign_keys=[Direction.subject2_id], overlaps="subject2"
    )


class Question(Base):
    __tablename__ = 'questions'
    id             = Column(Integer, primary_key=True)
    subject_id     = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    text_uz        = Column(Text, nullable=False)
    text_oz        = Column(Text, nullable=False)
    text_ru        = Column(Text, nullable=False)
    option_a       = Column(Text, nullable=False)
    option_b       = Column(Text, nullable=False)
    option_c       = Column(Text, nullable=False)
    option_d       = Column(Text, nullable=False)
    correct_answer = Column(String(1), nullable=False)
    difficulty     = Column(String(20), default='medium')
    subject        = relationship("Subject", back_populates="questions")
    answers        = relationship("UserAnswer", back_populates="question")


class User(Base):
    __tablename__ = 'users'
    id           = Column(Integer, primary_key=True)
    telegram_id  = Column(BigInteger, unique=True, nullable=False)
    first_name   = Column(String(255), nullable=False)
    last_name    = Column(String(255), nullable=True)
    phone        = Column(String(20), nullable=False)
    region_id    = Column(Integer, ForeignKey('regions.id'), nullable=False)
    district_id  = Column(Integer, ForeignKey('districts.id'), nullable=False)
    direction_id = Column(String(10), ForeignKey('directions.id'), nullable=True)
    language     = Column(String(10), default='uz')
    is_blocked   = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    region              = relationship("Region", back_populates="users")
    district            = relationship("District", back_populates="users")
    direction           = relationship("Direction", back_populates="users")
    test_participations = relationship("UserTestParticipation", back_populates="user")
    answers             = relationship("UserAnswer", back_populates="user")
    leaderboard_entries = relationship("Leaderboard", back_populates="user")


class TestSession(Base):
    __tablename__ = 'test_sessions'
    id                  = Column(Integer, primary_key=True)
    admin_id            = Column(Integer, ForeignKey('admins.id'), nullable=False)
    exam_date           = Column(DateTime, nullable=False)
    start_time          = Column(DateTime, nullable=False)
    duration_minutes    = Column(Integer, default=180)
    status              = Column(String(20), default='scheduled')
    allowed_directions  = Column(JSON)
    created_at          = Column(DateTime, default=datetime.utcnow)
    admin               = relationship("Admin", back_populates="test_sessions")
    participations      = relationship("UserTestParticipation", back_populates="test_session")
    leaderboard         = relationship("Leaderboard", back_populates="test_session")


class UserTestParticipation(Base):
    __tablename__ = 'user_test_participation'
    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_session_id = Column(Integer, ForeignKey('test_sessions.id'), nullable=False)
    direction_id    = Column(String(10), ForeignKey('directions.id'), nullable=False)
    joined_at       = Column(DateTime, default=datetime.utcnow)
    started_at      = Column(DateTime, nullable=True)
    completed_at    = Column(DateTime, nullable=True)
    deadline_at     = Column(DateTime, nullable=True)   # vaqt chegarasi
    status          = Column(String(20), default='joined')
    # FSM state snapshot — botni restart qilishda davom ettirish uchun
    snapshot_questions     = Column(JSON, nullable=True)   # savollar ro'yxati
    snapshot_current_index = Column(Integer, default=0)
    snapshot_answers       = Column(JSON, nullable=True)   # {str(index): letter}

    user         = relationship("User", back_populates="test_participations")
    test_session = relationship("TestSession", back_populates="participations")
    direction    = relationship("Direction")
    answers      = relationship("UserAnswer", back_populates="participation")


class UserAnswer(Base):
    __tablename__ = 'user_answers'
    __table_args__ = (
        UniqueConstraint('participation_id', 'question_id', name='uq_participation_question'),
    )
    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_session_id = Column(Integer, ForeignKey('test_sessions.id'), nullable=False)
    participation_id = Column(Integer, ForeignKey('user_test_participation.id'), nullable=False)
    question_id     = Column(Integer, ForeignKey('questions.id'), nullable=False)
    selected_answer = Column(String(1), nullable=True)
    is_correct      = Column(Boolean, nullable=True)
    submitted_at    = Column(DateTime, default=datetime.utcnow)

    user         = relationship("User", back_populates="answers")
    test_session = relationship("TestSession")
    participation = relationship("UserTestParticipation", back_populates="answers")
    question     = relationship("Question", back_populates="answers")


class Leaderboard(Base):
    __tablename__ = 'leaderboard'
    id              = Column(Integer, primary_key=True)
    test_session_id = Column(Integer, ForeignKey('test_sessions.id'), nullable=False)
    user_id         = Column(Integer, ForeignKey('users.id'), nullable=False)
    rank            = Column(Integer, nullable=False)
    total_score     = Column(Float, nullable=False)
    timestamp       = Column(DateTime, default=datetime.utcnow)
    test_session    = relationship("TestSession", back_populates="leaderboard")
    user            = relationship("User", back_populates="leaderboard_entries")


class Score(Base):
    __tablename__ = 'scores'
    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey('users.id'), nullable=False)
    participation_id = Column(Integer, ForeignKey('user_test_participation.id'), nullable=True)
    score           = Column(Float, nullable=False)
    correct_count   = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    user            = relationship("User")


class Admin(Base):
    __tablename__ = 'admins'
    id               = Column(Integer, primary_key=True)
    telegram_id      = Column(BigInteger, unique=True, nullable=False)
    role             = Column(String(20), default='admin')
    permissions_json = Column(JSON, default=dict)
    created_at       = Column(DateTime, default=datetime.utcnow)
    test_sessions    = relationship("TestSession", back_populates="admin")


class MandatoryChannel(Base):
    """Majburiy obuna kanallari."""
    __tablename__ = 'mandatory_channels'
    id            = Column(Integer, primary_key=True)
    channel_id    = Column(String(100), unique=True, nullable=False)  # @username yoki -1001234
    channel_name  = Column(String(255), nullable=False)
    invite_link   = Column(String(512), nullable=True)   # inline tugma havolasi
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class BroadcastMessage(Base):
    """Broadcast yuborish tarixi."""
    __tablename__ = 'broadcast_messages'
    id            = Column(Integer, primary_key=True)
    admin_id      = Column(Integer, ForeignKey('admins.id'), nullable=True)
    message_type  = Column(String(20), default='text')   # 'text' | 'forward'
    content       = Column(Text, nullable=True)          # matn xabari
    forward_from_chat = Column(String(100), nullable=True)   # kanal username
    forward_message_id = Column(BigInteger, nullable=True)   # post ID
    target        = Column(String(20), default='all')    # 'all' | count
    sent_count    = Column(Integer, default=0)
    fail_count    = Column(Integer, default=0)
    status        = Column(String(20), default='pending')  # pending|sending|done|failed
    created_at    = Column(DateTime, default=datetime.utcnow)
    finished_at   = Column(DateTime, nullable=True)