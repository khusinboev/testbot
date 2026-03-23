from datetime import datetime
from database.db import Session
from database.models import (
    Question, Direction, UserTestParticipation,
    UserAnswer, Leaderboard, TestSession, Score, Admin
)
from sqlalchemy import func
import config


class TestService:

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

    @staticmethod
    def create_participation(user_id: int, direction_id: str) -> UserTestParticipation:
        db = Session()
        test_session = TestService.get_or_create_test_session()
        participation = UserTestParticipation(
            user_id=user_id,
            test_session_id=test_session.id,
            direction_id=direction_id,
            status='active',
            started_at=datetime.utcnow()
        )
        db.add(participation)
        db.commit()
        # scalar maydonlar yopilgandan keyin ham ishlaydi
        p_id = participation.id
        ts_id = participation.test_session_id
        db.close()

        # Qayta olamiz — handlerda .test_session_id kerak bo'ladi
        db2 = Session()
        result = db2.query(UserTestParticipation).filter(UserTestParticipation.id == p_id).first()
        db2.close()
        return result

    @staticmethod
    def get_test_questions(direction_id: str) -> list:
        db = Session()
        direction = db.query(Direction).filter(Direction.id == direction_id).first()
        if not direction:
            db.close()
            return []

        questions = []

        # Majburiy fanlar: Matematika (1), Tarix (5), Ona tili (6)
        for subject_id in [1, 5, 6]:
            qs = db.query(Question).filter(
                Question.subject_id == subject_id
            ).limit(config.MANDATORY_QUESTIONS_PER_SUBJECT).all()
            questions.extend(qs)

        # Ixtisoslashgan fanlar: yo'nalishning 2 ta fani, har biridan 30 ta
        for subject_id in [direction.subject1_id, direction.subject2_id]:
            qs = db.query(Question).filter(
                Question.subject_id == subject_id
            ).limit(config.SPECIALIZED_QUESTIONS_PER_SUBJECT).all()
            questions.extend(qs)

        db.close()

        import random
        random.shuffle(questions)
        return questions[:90]

    @staticmethod
    def save_answer(
        participation_id: int,
        user_id: int,
        test_session_id: int,
        question_id: int,
        selected_answer: str
    ) -> bool:
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
            UserAnswer.participation_id == participation_id
        ).all()

        total_score = 0.0
        for answer in answers:
            if not answer.is_correct:
                continue
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
    def complete_test(participation_id: int) -> dict:
        db = Session()
        try:
            participation = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if not participation:
                return None

            score = TestService.calculate_score(participation_id)

            participation.status = 'completed'
            participation.completed_at = datetime.utcnow()
            db.commit()

            # is_(True) — SQLAlchemy uchun to'g'ri usul
            correct_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.is_correct.is_(True)
            ).count()

            total_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id
            ).count()

            db.add(Score(
                user_id=participation.user_id,
                score=score,
                correct_count=correct_count,
                total_questions=total_count
            ))

            # Leaderboard ham yangilash
            db.add(Leaderboard(
                test_session_id=participation.test_session_id,
                user_id=participation.user_id,
                rank=0,          # Keyinroq qayta hisoblanadi
                total_score=score
            ))

            db.commit()
            return {
                'score': score,
                'correct_count': correct_count,
                'total_questions': total_count,
                'percentage': round(
                    (correct_count / total_count * 100) if total_count > 0 else 0, 1
                )
            }
        except Exception as e:
            db.rollback()
            print(f"complete_test xato: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def get_leaderboard(test_session_id: int, limit: int = 10) -> list:
        db = Session()
        # total_score — Leaderboard modelidagi to'g'ri maydon nomi
        leaders = db.query(Leaderboard).filter(
            Leaderboard.test_session_id == test_session_id
        ).order_by(Leaderboard.total_score.desc()).limit(limit).all()
        db.close()
        return leaders