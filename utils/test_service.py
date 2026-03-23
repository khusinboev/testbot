"""
utils/test_service.py

TUZATILDI:
  1. get_direction_leaderboard() — db.close() dan keyin score.user ishlatilardi
     → DetachedInstanceError. Endi score_data dict list qaytaradi.
  2. get_user_direction_rank() — murakkab join mantiq to'g'rilandi.
  3. X | Y type hint → Optional[] (Python 3.8 mos)
  4. complete_test() — har safar yangi Session, takroriy chaqiruvdan himoya
  5. get_active_participation() — deadline_at > now filtri qo'shildi
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from database.db import Session
from database.models import (
    Question, Direction, UserTestParticipation,
    UserAnswer, Leaderboard, TestSession, Score, Admin, User
)
from sqlalchemy import func
from sqlalchemy.orm import joinedload
import config
import random


class TestService:

    # ─────────────────────────────────────────────────────────────
    # TestSession
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def get_or_create_test_session() -> TestSession:
        db = Session()
        today = datetime.utcnow().date()
        test_session = db.query(TestSession).filter(
            func.date(TestSession.exam_date) == today,
            TestSession.status == 'active'
        ).first()

        if not test_session:
            admin = db.query(Admin).first()
            if not admin:
                admin = Admin(telegram_id=0, role='super_admin')
                db.add(admin)
                db.flush()
            test_session = TestSession(
                admin_id=admin.id,
                exam_date=datetime.utcnow(),
                start_time=datetime.utcnow(),
                duration_minutes=config.TEST_DURATION_MINUTES,
                status='active'
            )
            db.add(test_session)
            db.commit()

        session_id = test_session.id
        db.close()

        db2 = Session()
        result = db2.query(TestSession).filter(TestSession.id == session_id).first()
        db2.close()
        return result

    # ─────────────────────────────────────────────────────────────
    # Participation
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def create_participation(user_id: int, direction_id: str) -> UserTestParticipation:
        db = Session()
        test_session = TestService.get_or_create_test_session()
        deadline = datetime.utcnow() + timedelta(minutes=config.TEST_DURATION_MINUTES)
        participation = UserTestParticipation(
            user_id=user_id,
            test_session_id=test_session.id,
            direction_id=direction_id,
            status='active',
            started_at=datetime.utcnow(),
            deadline_at=deadline,
        )
        db.add(participation)
        db.commit()
        p_id = participation.id
        db.close()

        db2 = Session()
        result = db2.query(UserTestParticipation).filter(
            UserTestParticipation.id == p_id
        ).first()
        db2.close()
        return result

    @staticmethod
    def get_active_participation(user_id: int) -> Optional[UserTestParticipation]:
        """
        Faqat haqiqiy aktiv (vaqti o'tmagan) participation ni qaytaradi.
        TUZATILDI: deadline_at > now filtri — vaqti o'tgan 'active' lar ko'rinmaydi.
        """
        db = Session()
        try:
            now = datetime.utcnow()
            p = db.query(UserTestParticipation).filter(
                UserTestParticipation.user_id == user_id,
                UserTestParticipation.status == 'active',
                UserTestParticipation.deadline_at > now
            ).order_by(UserTestParticipation.started_at.desc()).first()

            if p is None:
                return None
            p_id = p.id
        finally:
            db.close()

        # Yangi session bilan qaytadan olish — detached instance xatosidan saqlanish
        db2 = Session()
        try:
            return db2.query(UserTestParticipation).filter(
                UserTestParticipation.id == p_id
            ).first()
        finally:
            db2.close()

    @staticmethod
    def save_snapshot(participation_id: int, questions: list,
                      current_index: int, answers: dict) -> None:
        db = Session()
        try:
            p = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if p:
                p.snapshot_questions     = questions
                p.snapshot_current_index = current_index
                p.snapshot_answers       = answers
                db.commit()
        except Exception as e:
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def load_snapshot(participation_id: int) -> Optional[Dict[str, Any]]:
        db = Session()
        try:
            p = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if not p or not p.snapshot_questions:
                return None
            return {
                'participation_id': p.id,
                'test_session_id':  p.test_session_id,
                'questions':        p.snapshot_questions,
                'current_question_index': p.snapshot_current_index or 0,
                'answers':          p.snapshot_answers or {},
                'deadline_at':      p.deadline_at,
            }
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────
    # Questions
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def get_test_questions(direction_id: str) -> List[Dict[str, Any]]:
        """
        Guruhlar tartibi: Matematika → Ona tili → Tarix → 1-fan → 2-fan
        Har guruh ichida savollar va variantlar random aralashtiriladi.
        """
        db = Session()
        direction = db.query(Direction).filter(Direction.id == direction_id).first()
        if not direction:
            db.close()
            return []
        subj1_id   = direction.subject1_id
        subj2_id   = direction.subject2_id
        subj1_name = direction.subject1.name_uz if direction.subject1 else f"Fan-{subj1_id}"
        subj2_name = direction.subject2.name_uz if direction.subject2 else f"Fan-{subj2_id}"
        db.close()

        def _fetch_shuffled(subject_id: int, count: int) -> List[Dict]:
            db2 = Session()
            try:
                rows = db2.query(Question).filter(
                    Question.subject_id == subject_id
                ).all()
            finally:
                db2.close()

            random.shuffle(rows)
            selected = rows[:count]
            result = []
            for q in selected:
                correct_text = {
                    'A': q.option_a, 'B': q.option_b,
                    'C': q.option_c, 'D': q.option_d,
                }.get(q.correct_answer, q.option_a)
                options = [
                    ('A', q.option_a), ('B', q.option_b),
                    ('C', q.option_c), ('D', q.option_d),
                ]
                random.shuffle(options)
                new_correct = 'A'
                for ltr, (_, txt) in zip('ABCD', options):
                    if txt == correct_text:
                        new_correct = ltr
                        break
                result.append({
                    'id':             q.id,
                    'text_uz':        q.text_uz,
                    'option_a':       options[0][1],
                    'option_b':       options[1][1],
                    'option_c':       options[2][1],
                    'option_d':       options[3][1],
                    'correct_answer': new_correct,
                    'subject_id':     q.subject_id,
                })
            return result

        groups = [
            {'label': 'Majburiy — Matematika',
             'subject_id': 1, 'count': config.MANDATORY_QUESTIONS_PER_SUBJECT},
            {'label': 'Majburiy — Ona tili',
             'subject_id': 6, 'count': config.MANDATORY_QUESTIONS_PER_SUBJECT},
            {'label': 'Majburiy — Tarix',
             'subject_id': 5, 'count': config.MANDATORY_QUESTIONS_PER_SUBJECT},
            {'label': f'Asosiy (1-fan) — {subj1_name}',
             'subject_id': subj1_id, 'count': config.SPECIALIZED_QUESTIONS_PER_SUBJECT},
            {'label': f'Asosiy (2-fan) — {subj2_name}',
             'subject_id': subj2_id, 'count': config.SPECIALIZED_QUESTIONS_PER_SUBJECT},
        ]

        ordered: List[Dict] = []
        for grp in groups:
            qs = _fetch_shuffled(grp['subject_id'], grp['count'])
            for q in qs:
                q['group_label'] = grp['label']
            ordered.extend(qs)
        return ordered[:90]

    # ─────────────────────────────────────────────────────────────
    # Answers
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def save_answer(participation_id: int, user_id: int,
                    test_session_id: int, question_id: int,
                    selected_answer: str) -> bool:
        db = Session()
        try:
            existing = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.question_id == question_id
            ).first()
            if existing:
                return True
            question = db.query(Question).filter(Question.id == question_id).first()
            if not question:
                return False
            is_correct = (selected_answer == question.correct_answer) if selected_answer else False
            db.add(UserAnswer(
                user_id=user_id,
                test_session_id=test_session_id,
                participation_id=participation_id,
                question_id=question_id,
                selected_answer=selected_answer,
                is_correct=is_correct
            ))
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────
    # Score
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def calculate_score(participation_id: int) -> float:
        db = Session()
        try:
            participation = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if not participation:
                return 0.0
            direction = db.query(Direction).filter(
                Direction.id == participation.direction_id
            ).first()
            if not direction:
                return 0.0

            answers = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.is_correct.is_(True)
            ).all()

            total_score = 0.0
            for answer in answers:
                question = db.query(Question).filter(Question.id == answer.question_id).first()
                if not question:
                    continue
                if question.subject_id in config.MANDATORY_SUBJECT_IDS:
                    total_score += config.MANDATORY_POINTS_PER_QUESTION
                elif question.subject_id == direction.subject1_id:
                    total_score += config.SPECIALIZED_HIGH_POINTS
                elif question.subject_id == direction.subject2_id:
                    total_score += config.SPECIALIZED_LOW_POINTS
            return round(total_score, 2)
        finally:
            db.close()

    @staticmethod
    def complete_test(participation_id: int) -> Optional[Dict[str, Any]]:
        """
        TUZATILDI:
        - Har safar yangi Session ochadi
        - status='completed' bo'lsa avvalgi natijani qaytaradi (takroriy chaqiruvdan himoya)
        - Snapshot tozalanadi
        """
        db = Session()
        try:
            participation = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if not participation:
                return None

            # Allaqachon tugallangan — mavjud score ni qaytaramiz
            if participation.status == 'completed':
                score_obj = db.query(Score).filter(
                    Score.participation_id == participation_id
                ).first()
                if score_obj:
                    return {
                        'score':           score_obj.score,
                        'correct_count':   score_obj.correct_count,
                        'total_questions': score_obj.total_questions,
                        'percentage':      round(
                            score_obj.correct_count / score_obj.total_questions * 100
                            if score_obj.total_questions else 0, 1
                        ),
                    }
                return None

            score_val = TestService.calculate_score(participation_id)

            participation.status           = 'completed'
            participation.completed_at     = datetime.utcnow()
            participation.snapshot_questions     = None
            participation.snapshot_current_index = 0
            participation.snapshot_answers       = None
            db.commit()

            correct_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.is_correct.is_(True)
            ).count()

            total_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id
            ).count()
            if total_count == 0:
                total_count = 90

            db.add(Score(
                user_id=participation.user_id,
                participation_id=participation_id,
                score=score_val,
                correct_count=correct_count,
                total_questions=total_count
            ))
            db.add(Leaderboard(
                test_session_id=participation.test_session_id,
                user_id=participation.user_id,
                rank=0,
                total_score=score_val
            ))
            db.commit()

            return {
                'score':           score_val,
                'correct_count':   correct_count,
                'total_questions': total_count,
                'percentage':      round(
                    (correct_count / total_count * 100) if total_count > 0 else 0, 1
                ),
            }
        except Exception as e:
            db.rollback()
            return None
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────
    # Auto-finish (scheduler tomonidan chaqiriladi)
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def get_expired_participations() -> List[Tuple[int, int]]:
        """Vaqti o'tgan, hali active bo'lgan participationlar."""
        db = Session()
        try:
            now = datetime.utcnow()
            expired = db.query(UserTestParticipation).filter(
                UserTestParticipation.status == 'active',
                UserTestParticipation.deadline_at <= now
            ).all()
            return [(p.id, p.user_id) for p in expired]
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────
    # Leaderboard
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def get_leaderboard(test_session_id: int, limit: int = 10) -> list:
        db = Session()
        try:
            return db.query(Leaderboard).filter(
                Leaderboard.test_session_id == test_session_id
            ).order_by(Leaderboard.total_score.desc()).limit(limit).all()
        finally:
            db.close()

    @staticmethod
    def get_direction_leaderboard(direction_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        TUZATILDI: db.close() dan keyin score.user ishlatilardi → DetachedInstanceError.
        Endi dict list qaytaradi — ORM ob'ektlari emas.
        """
        db = Session()
        try:
            scores = (
                db.query(Score)
                .join(User, Score.user_id == User.id)
                .filter(User.direction_id == direction_id)
                .options(joinedload(Score.user))
                .order_by(Score.score.desc())
                .limit(limit)
                .all()
            )
            # Session yopilishidan oldin dict ga o'tkazamiz
            result = []
            for s in scores:
                u = s.user
                result.append({
                    'score':      s.score,
                    'correct':    s.correct_count,
                    'total':      s.total_questions,
                    'user_id':    s.user_id,
                    'first_name': u.first_name if u else '—',
                    'last_name':  u.last_name  if u else '',
                })
            return result
        finally:
            db.close()

    @staticmethod
    def get_user_direction_rank(user_id: int, direction_id: str) -> int:
        """
        TUZATILDI: murakkab join → oddiy subquery bilan.
        Foydalanuvchining yo'nalish ichidagi o'rni.
        """
        db = Session()
        try:
            # Foydalanuvchining eng yuqori balli
            user_best = (
                db.query(func.max(Score.score))
                .filter(Score.user_id == user_id)
                .scalar()
            ) or 0

            # Shu yo'nalishda undan yuqori ball olganlar soni
            better_count = (
                db.query(func.count(Score.user_id.distinct()))
                .join(User, Score.user_id == User.id)
                .filter(
                    User.direction_id == direction_id,
                    Score.score > user_best,
                    Score.user_id != user_id
                )
                .scalar()
            ) or 0

            return better_count + 1
        finally:
            db.close()