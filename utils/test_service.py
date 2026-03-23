"""
utils/test_service.py
- Snapshot: test davomida savollar va javoblarni DB ga saqlaydi
- Deadline: participation yaratilganda deadline_at belgilanadi
- Auto-finish: scheduler bu servisni chaqiradi
"""
from datetime import datetime, timedelta
from database.db import Session
from database.models import (
    Question, Direction, UserTestParticipation,
    UserAnswer, Leaderboard, TestSession, Score, Admin
)
from sqlalchemy import func
import config
import random


class TestService:

    # ──────────────────────────────────────────────────────────────
    # Session
    # ──────────────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────────
    # Participation — snapshot bilan
    # ──────────────────────────────────────────────────────────────
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
    def get_active_participation(user_id: int) -> UserTestParticipation | None:
        """Foydalanuvchining aktiv participation ni qaytaradi."""
        db = Session()
        p = db.query(UserTestParticipation).filter(
            UserTestParticipation.user_id == user_id,
            UserTestParticipation.status == 'active'
        ).order_by(UserTestParticipation.started_at.desc()).first()
        db.close()
        return p

    @staticmethod
    def save_snapshot(participation_id: int, questions: list,
                      current_index: int, answers: dict):
        """Joriy test holatini DB ga saqlaydi."""
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
            print(f"save_snapshot xato: {e}")
        finally:
            db.close()

    @staticmethod
    def load_snapshot(participation_id: int) -> dict | None:
        """DB dagi snapshot ni qaytaradi."""
        db = Session()
        p = db.query(UserTestParticipation).filter(
            UserTestParticipation.id == participation_id
        ).first()
        db.close()
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

    # ──────────────────────────────────────────────────────────────
    # Questions
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def get_test_questions(direction_id: str) -> list:
        """
        Savollarni qat'iy tartibda qaytaradi:
          Guruh 1 — Majburiy: Matematika   (10 ta)
          Guruh 2 — Majburiy: Ona tili     (10 ta)
          Guruh 3 — Majburiy: Tarix        (10 ta)
          Guruh 4 — Asosiy 1-fan           (30 ta)
          Guruh 5 — Asosiy 2-fan           (30 ta)
        Har guruh ichida savollar va variantlar RANDOM aralashtiriladi.
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

        def _fetch_shuffled(subject_id: int, count: int) -> list:
            db2 = Session()
            rows = db2.query(Question).filter(
                Question.subject_id == subject_id
            ).all()
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
                new_correct = next(
                    (ltr for ltr, txt in zip('ABCD', [o[1] for o in options])
                     if txt == correct_text),
                    q.correct_answer
                )
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
            {'label': "Majburiy — Ona tili",
             'subject_id': 6, 'count': config.MANDATORY_QUESTIONS_PER_SUBJECT},
            {'label': 'Majburiy — Tarix',
             'subject_id': 5, 'count': config.MANDATORY_QUESTIONS_PER_SUBJECT},
            {'label': f'Asosiy (1-fan) — {subj1_name}',
             'subject_id': subj1_id, 'count': config.SPECIALIZED_QUESTIONS_PER_SUBJECT},
            {'label': f'Asosiy (2-fan) — {subj2_name}',
             'subject_id': subj2_id, 'count': config.SPECIALIZED_QUESTIONS_PER_SUBJECT},
        ]

        ordered = []
        for grp in groups:
            qs = _fetch_shuffled(grp['subject_id'], grp['count'])
            for q in qs:
                q['group_label'] = grp['label']
            ordered.extend(qs)
        return ordered[:90]

    # ──────────────────────────────────────────────────────────────
    # Answers
    # ──────────────────────────────────────────────────────────────
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
        except Exception as e:
            db.rollback()
            print(f"save_answer xato: {e}")
            return False
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────
    # Score
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def calculate_score(participation_id: int) -> float:
        db = Session()
        participation = db.query(UserTestParticipation).filter(
            UserTestParticipation.id == participation_id
        ).first()
        if not participation:
            db.close()
            return 0.0

        direction = db.query(Direction).filter(
            Direction.id == participation.direction_id
        ).first()
        if not direction:
            db.close()
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

        db.close()
        return round(total_score, 2)

    @staticmethod
    def complete_test(participation_id: int) -> dict | None:
        db = Session()
        try:
            participation = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if not participation:
                return None
            if participation.status == 'completed':
                # Avval tugallangan — Score dan qaytarish
                score_obj = db.query(Score).filter(
                    Score.participation_id == participation_id
                ).first()
                if score_obj:
                    return {
                        'score': score_obj.score,
                        'correct_count': score_obj.correct_count,
                        'total_questions': score_obj.total_questions,
                    }
                return None

            score_val = TestService.calculate_score(participation_id)

            participation.status       = 'completed'
            participation.completed_at = datetime.utcnow()
            # Snapshotni tozalash
            participation.snapshot_questions     = None
            participation.snapshot_current_index = 0
            participation.snapshot_answers       = None
            db.commit()

            correct_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.is_correct.is_(True)
            ).count()

            # Total savollar soni — snapshot yoki config dan
            total_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id
            ).count()
            if total_count == 0:
                total_count = 90  # standart

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
                )
            }
        except Exception as e:
            db.rollback()
            print(f"complete_test xato: {e}")
            return None
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────
    # Auto-finish (scheduler chaqiradi)
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def get_expired_participations() -> list:
        """Vaqti o'tgan, hali tugallanmagan participationlar."""
        db = Session()
        now = datetime.utcnow()
        expired = db.query(UserTestParticipation).filter(
            UserTestParticipation.status == 'active',
            UserTestParticipation.deadline_at <= now
        ).all()
        ids = [(p.id, p.user_id) for p in expired]
        db.close()
        return ids

    # ──────────────────────────────────────────────────────────────
    # Leaderboard
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def get_leaderboard(test_session_id: int, limit: int = 10) -> list:
        db = Session()
        leaders = db.query(Leaderboard).filter(
            Leaderboard.test_session_id == test_session_id
        ).order_by(Leaderboard.total_score.desc()).limit(limit).all()
        db.close()
        return leaders

    @staticmethod
    def get_direction_leaderboard(direction_id: str, limit: int = 5) -> list:
        """Yo'nalish bo'yicha top scorlar."""
        from database.models import User
        db = Session()
        scores = (
            db.query(Score)
            .join(User, Score.user_id == User.id)
            .filter(User.direction_id == direction_id)
            .order_by(Score.score.desc())
            .limit(limit)
            .all()
        )
        db.close()
        return scores

    @staticmethod
    def get_user_direction_rank(user_id: int, direction_id: str) -> int:
        """Foydalanuvchining yo'nalish bo'yicha reytingdagi o'rni."""
        from database.models import User
        db = Session()
        # User's best score
        user_best = db.query(func.max(Score.score)).join(
            User, Score.user_id == User.id
        ).filter(
            Score.user_id == user_id,
            User.direction_id == direction_id
        ).scalar() or 0

        # Count users with better score in same direction
        better_count = (
            db.query(func.count(Score.user_id.distinct()))
            .join(User, Score.user_id == User.id)
            .filter(
                User.direction_id == direction_id,
                Score.score > user_best
            )
            .scalar() or 0
        )
        db.close()
        return better_count + 1