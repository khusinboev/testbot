"""
database/models.py

Barcha SQLAlchemy modellari — mantiqiy guruhlar bo'yicha tartiblanган:
  1. Geo (Region, District)
  2. Education (Direction, Subject, Question)
  3. User
  4. Test (TestSession, UserTestParticipation, UserAnswer)
  5. Results (Score, Leaderboard)
  6. Admin / Bot management (Admin, MandatoryChannel, BroadcastMessage)
  7. Referral (ReferralSettings, ReferralLink, ReferralInvite)
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float,
    ForeignKey, Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ══════════════════════════════════════════════════════════════════════════════
# 1. GEO
# ══════════════════════════════════════════════════════════════════════════════

class Region(Base):
    __tablename__ = "regions"

    id       = Column(Integer, primary_key=True)
    name_uz  = Column(String(255), nullable=False)
    name_oz  = Column(String(255), nullable=False)
    name_ru  = Column(String(255), nullable=False)

    districts = relationship("District", back_populates="region")
    users     = relationship("User",     back_populates="region")


class District(Base):
    __tablename__ = "districts"

    id        = Column(Integer, primary_key=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    name_uz   = Column(String(255), nullable=False)
    name_oz   = Column(String(255), nullable=False)
    name_ru   = Column(String(255), nullable=False)

    region = relationship("Region", back_populates="districts")
    users  = relationship("User",   back_populates="district")


# ══════════════════════════════════════════════════════════════════════════════
# 2. EDUCATION
# ══════════════════════════════════════════════════════════════════════════════

class Direction(Base):
    __tablename__ = "directions"

    id          = Column(String(10), primary_key=True)
    name_uz     = Column(String(255), nullable=False)
    name_oz     = Column(String(255), nullable=False)
    name_ru     = Column(String(255), nullable=False)
    subject1_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    subject2_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)

    subject1 = relationship("Subject", foreign_keys=[subject1_id])
    subject2 = relationship("Subject", foreign_keys=[subject2_id])
    users    = relationship("User",    back_populates="direction")


class Subject(Base):
    __tablename__ = "subjects"

    id                  = Column(Integer, primary_key=True)
    name_uz             = Column(String(255), nullable=False)
    name_oz             = Column(String(255), nullable=False)
    name_ru             = Column(String(255), nullable=False)
    question_count      = Column(Integer, default=0)
    points_per_question = Column(Float,   default=1.0)

    questions = relationship("Question", back_populates="subject")

    # overlaps — SQLAlchemy ogohlantirmaslik uchun
    directions_as_subject1 = relationship(
        "Direction", foreign_keys=[Direction.subject1_id], overlaps="subject1"
    )
    directions_as_subject2 = relationship(
        "Direction", foreign_keys=[Direction.subject2_id], overlaps="subject2"
    )


class Question(Base):
    __tablename__ = "questions"

    id             = Column(Integer, primary_key=True)
    subject_id     = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    text_uz        = Column(Text, nullable=False)
    text_oz        = Column(Text, nullable=False)
    text_ru        = Column(Text, nullable=False)
    option_a       = Column(Text, nullable=False)
    option_b       = Column(Text, nullable=False)
    option_c       = Column(Text, nullable=False)
    option_d       = Column(Text, nullable=False)
    correct_answer = Column(String(1), nullable=False)
    difficulty     = Column(String(20), default="medium")

    subject = relationship("Subject",    back_populates="questions")
    answers = relationship("UserAnswer", back_populates="question")


# ══════════════════════════════════════════════════════════════════════════════
# 3. USER
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id           = Column(Integer,    primary_key=True)
    telegram_id  = Column(BigInteger, unique=True, nullable=False)
    first_name   = Column(String(255), nullable=False)
    last_name    = Column(String(255), nullable=True)
    phone        = Column(String(20),  nullable=False)
    region_id    = Column(Integer,    ForeignKey("regions.id"),    nullable=False)
    district_id  = Column(Integer,    ForeignKey("districts.id"),  nullable=False)
    direction_id = Column(String(10), ForeignKey("directions.id"), nullable=True)
    language     = Column(String(10), default="uz")
    is_blocked   = Column(Boolean,    default=False)
    created_at   = Column(DateTime,   default=datetime.utcnow)

    region   = relationship("Region",    back_populates="users")
    district = relationship("District",  back_populates="users")
    direction = relationship("Direction", back_populates="users")

    test_participations = relationship("UserTestParticipation", back_populates="user")
    answers             = relationship("UserAnswer",            back_populates="user")
    leaderboard_entries = relationship("Leaderboard",           back_populates="user")
    scores              = relationship("Score",                 back_populates="user")
    referral_link       = relationship(
        "ReferralLink",
        back_populates="user",
        foreign_keys="ReferralLink.user_id",
        uselist=False,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4. TEST
# ══════════════════════════════════════════════════════════════════════════════

class TestSession(Base):
    __tablename__ = "test_sessions"

    id                 = Column(Integer,  primary_key=True)
    admin_id           = Column(Integer,  ForeignKey("admins.id"), nullable=False)
    exam_date          = Column(DateTime, nullable=False)
    start_time         = Column(DateTime, nullable=False)
    duration_minutes   = Column(Integer,  default=180)
    status             = Column(String(20), default="scheduled")
    allowed_directions = Column(JSON)
    created_at         = Column(DateTime, default=datetime.utcnow)

    admin          = relationship("Admin",                back_populates="test_sessions")
    participations = relationship("UserTestParticipation", back_populates="test_session")
    leaderboard    = relationship("Leaderboard",           back_populates="test_session")


class UserTestParticipation(Base):
    __tablename__ = "user_test_participation"

    id              = Column(Integer,    primary_key=True)
    user_id         = Column(Integer,    ForeignKey("users.id"),         nullable=False)
    test_session_id = Column(Integer,    ForeignKey("test_sessions.id"), nullable=False)
    direction_id    = Column(String(10), ForeignKey("directions.id"),    nullable=False)

    # Vaqt
    joined_at    = Column(DateTime, default=datetime.utcnow)
    started_at   = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    deadline_at  = Column(DateTime, nullable=True)

    status = Column(String(20), default="joined")

    # Snapshot (test davomidagi holat)
    snapshot_questions     = Column(JSON,    nullable=True)
    snapshot_current_index = Column(Integer, default=0)
    snapshot_answers       = Column(JSON,    nullable=True)

    user         = relationship("User",        back_populates="test_participations")
    test_session = relationship("TestSession", back_populates="participations")
    direction    = relationship("Direction")
    answers      = relationship("UserAnswer",  back_populates="participation")


class UserAnswer(Base):
    __tablename__ = "user_answers"
    __table_args__ = (
        UniqueConstraint("participation_id", "question_id", name="uq_participation_question"),
    )

    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, ForeignKey("users.id"),                   nullable=False)
    test_session_id  = Column(Integer, ForeignKey("test_sessions.id"),           nullable=False)
    participation_id = Column(Integer, ForeignKey("user_test_participation.id"), nullable=False)
    question_id      = Column(Integer, ForeignKey("questions.id"),               nullable=False)
    selected_answer  = Column(String(1), nullable=True)
    is_correct       = Column(Boolean,   nullable=True)
    submitted_at     = Column(DateTime,  default=datetime.utcnow)

    user          = relationship("User",                  back_populates="answers")
    test_session  = relationship("TestSession")
    participation = relationship("UserTestParticipation", back_populates="answers")
    question      = relationship("Question",              back_populates="answers")


# ══════════════════════════════════════════════════════════════════════════════
# 5. RESULTS
# ══════════════════════════════════════════════════════════════════════════════

class Score(Base):
    __tablename__ = "scores"

    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, ForeignKey("users.id"),                   nullable=False)
    participation_id = Column(Integer, ForeignKey("user_test_participation.id"), nullable=True)
    score            = Column(Float,   nullable=False)
    correct_count    = Column(Integer, nullable=False)
    attempted_count  = Column(Integer, default=0)
    total_questions  = Column(Integer, nullable=False)
    is_archived      = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="scores")


class Leaderboard(Base):
    __tablename__ = "leaderboard"

    id              = Column(Integer,    primary_key=True)
    test_session_id = Column(Integer,    ForeignKey("test_sessions.id"), nullable=False)
    user_id         = Column(Integer,    ForeignKey("users.id"),         nullable=False)
    direction_id    = Column(String(10), ForeignKey("directions.id"),    nullable=False)
    rank            = Column(Integer,    nullable=False)
    total_score     = Column(Float,      nullable=False)
    period          = Column(String(20), default="daily")
    timestamp       = Column(DateTime,   default=datetime.utcnow)

    test_session = relationship("TestSession", back_populates="leaderboard")
    user         = relationship("User",        back_populates="leaderboard_entries")
    direction    = relationship("Direction")


# ══════════════════════════════════════════════════════════════════════════════
# 6. ADMIN / BOT MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

class Admin(Base):
    __tablename__ = "admins"

    id               = Column(Integer,    primary_key=True)
    telegram_id      = Column(BigInteger, unique=True, nullable=False)
    role             = Column(String(20), default="admin")
    permissions_json = Column(JSON,       default=dict)
    created_at       = Column(DateTime,   default=datetime.utcnow)

    test_sessions = relationship("TestSession", back_populates="admin")


class MandatoryChannel(Base):
    __tablename__ = "mandatory_channels"

    id           = Column(Integer,     primary_key=True)
    channel_id   = Column(String(100), unique=True, nullable=False)
    channel_name = Column(String(255), nullable=False)
    invite_link  = Column(String(512), nullable=True)
    is_active    = Column(Boolean,     default=True)
    created_at   = Column(DateTime,    default=datetime.utcnow)


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id                 = Column(Integer,    primary_key=True)
    admin_id           = Column(Integer,    ForeignKey("admins.id"), nullable=True)
    message_type       = Column(String(20), default="text")
    content            = Column(Text,       nullable=True)
    forward_from_chat  = Column(String(100), nullable=True)
    forward_message_id = Column(BigInteger,  nullable=True)
    target             = Column(String(20),  default="all")
    sent_count         = Column(Integer,     default=0)
    fail_count         = Column(Integer,     default=0)
    status             = Column(String(20),  default="pending")
    created_at         = Column(DateTime,    default=datetime.utcnow)
    finished_at        = Column(DateTime,    nullable=True)


# ══════════════════════════════════════════════════════════════════════════════
# 7. REFERRAL
# ══════════════════════════════════════════════════════════════════════════════

class ReferralSettings(Base):
    """
    Global sozlamalar — faqat id=1 qator bo'ladi.
    Admin paneldan boshqariladi.
    """
    __tablename__ = "referral_settings"

    id             = Column(Integer,  primary_key=True)
    is_enabled     = Column(Boolean,  default=False)
    required_count = Column(Integer,  default=0)      # 0 = talab yo'q
    reward_message = Column(Text,     nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReferralLink(Base):
    """Har bir user uchun unikal referal kod va statistika."""
    __tablename__ = "referral_links"

    id            = Column(Integer,    primary_key=True)
    user_id       = Column(Integer,    ForeignKey("users.id"), unique=True, nullable=False)
    code          = Column(String(20), unique=True, nullable=False)   # ref_XXXXXXXX
    invited_count = Column(Integer,    default=0)
    created_at    = Column(DateTime,   default=datetime.utcnow)

    user    = relationship("User",          foreign_keys=[user_id], back_populates="referral_link")
    invites = relationship("ReferralInvite", back_populates="referrer_link")


class ReferralInvite(Base):
    """Kim kimni taklif qilgani — yangi user uchun bitta yozuv."""
    __tablename__ = "referral_invites"

    id               = Column(Integer, primary_key=True)
    referral_link_id = Column(Integer, ForeignKey("referral_links.id"), nullable=False)
    invited_user_id  = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    created_at       = Column(DateTime, default=datetime.utcnow)

    referrer_link = relationship("ReferralLink", back_populates="invites")
    invited_user  = relationship("User",         foreign_keys=[invited_user_id])