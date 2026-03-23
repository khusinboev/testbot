from datetime import datetime, timedelta
from database.db import Session
from database.models import (
    Question, Direction, Subject, UserTestParticipation,
    UserAnswer, Leaderboard, TestSession, User, Score, Admin
)
from sqlalchemy import func, and_
import config

class TestService:
    """Service for managing test sessions and scoring"""

    @staticmethod
    def get_or_create_test_session() -> TestSession:
        db = Session()
        today = datetime.utcnow().date()

        test_session = db.query(TestSession).filter(
            func.date(TestSession.exam_date) == today,
            TestSession.status == 'active'
        ).first()

        if not test_session:
            # Admin topish yoki yaratish
            admin = db.query(Admin).first()
            if not admin:
                admin = Admin(telegram_id=0, role='super_admin')
                db.add(admin)
                db.flush()  # id olish uchun

            test_session = TestSession(
                admin_id=admin.id,  # ← 1 emas, real ID
                exam_date=datetime.utcnow(),
                start_time=datetime.utcnow(),
                duration_minutes=config.TEST_DURATION_MINUTES,
                status='active'
            )
            db.add(test_session)
            db.commit()

        session_id = test_session.id
        db.close()

        # Yopilgan sessiondan qayta olish
        db2 = Session()
        result = db2.query(TestSession).filter(TestSession.id == session_id).first()
        db2.close()
        return result
    
    @staticmethod
    def create_participation(user_id: int, direction_id: str) -> UserTestParticipation:
        """Create user test participation record"""
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
        
        db.close()
        return participation
    
    @staticmethod
    def get_test_questions(direction_id: str) -> list:
        """Get questions for a test based on direction and mandatory subjects"""
        db = Session()
        
        # Get direction and its subjects
        direction = db.query(Direction).filter(Direction.id == direction_id).first()
        
        if not direction:
            db.close()
            return []
        
        questions = []
        
        # Mandatory subjects: Math (1), History (5), Native Language (6)
        mandatory_subject_ids = [1, 5, 6]
        
        # Get mandatory questions (30 total: 10 per subject)
        for subject_id in mandatory_subject_ids:
            mandatory_qs = db.query(Question).filter(
                Question.subject_id == subject_id
            ).limit(config.MANDATORY_QUESTIONS_PER_SUBJECT).all()
            questions.extend(mandatory_qs)
        
        # Get specialized questions from direction subjects
        # 30 questions from subject1, 30 from subject2
        for subject_id in [direction.subject1_id, direction.subject2_id]:
            specialized_qs = db.query(Question).filter(
                Question.subject_id == subject_id
            ).limit(config.SPECIALIZED_QUESTIONS_PER_SUBJECT).all()
            questions.extend(specialized_qs)
        
        db.close()
        
        # Shuffle questions for randomness
        import random
        random.shuffle(questions)
        
        return questions[:90]  # Return exactly 90 questions
    
    @staticmethod
    def save_answer(participation_id: int, user_id: int, test_session_id: int, question_id: int, selected_answer: str) -> bool:
        """Save user's answer to a question"""
        db = Session()
        
        try:
            # Check if answer already exists
            existing_answer = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.question_id == question_id
            ).first()
            
            if existing_answer:
                db.close()
                return True  # Already answered
            
            # Get question to check correct answer
            question = db.query(Question).filter(Question.id == question_id).first()
            if not question:
                db.close()
                return False
            
            is_correct = (selected_answer == question.correct_answer) if selected_answer else False
            
            answer = UserAnswer(
                user_id=user_id,
                test_session_id=test_session_id,
                participation_id=participation_id,
                question_id=question_id,
                selected_answer=selected_answer,
                is_correct=is_correct
            )
            db.add(answer)
            db.commit()
            db.close()
            
            return True
        except Exception as e:
            db.rollback()
            db.close()
            print(f"Error saving answer: {e}")
            return False
    
    @staticmethod
    def calculate_score(participation_id: int) -> float:
        """Calculate total score for a test participation using DTM scoring rules"""
        db = Session()
        
        # Get participation and direction
        participation = db.query(UserTestParticipation).filter(
            UserTestParticipation.id == participation_id
        ).first()
        
        if not participation:
            db.close()
            return 0.0
        
        direction = db.query(Direction).filter(Direction.id == participation.direction_id).first()
        if not direction:
            db.close()
            return 0.0
        
        # Get all answers for this participation
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
            
            # Determine points based on subject type
            if question.subject_id in config.MANDATORY_SUBJECT_IDS:
                # Mandatory subjects: Math (1), History (5), Native Language (6)
                total_score += config.MANDATORY_POINTS_PER_QUESTION
            elif question.subject_id == direction.subject1_id:
                # Main specialized subject
                total_score += config.SPECIALIZED_HIGH_POINTS
            elif question.subject_id == direction.subject2_id:
                # Secondary specialized subject
                total_score += config.SPECIALIZED_LOW_POINTS
        
        db.close()
        return round(total_score, 2)
    
    @staticmethod
    def complete_test(participation_id: int) -> dict:
        """Complete test and update leaderboard and save score"""
        db = Session()
        
        try:
            # Get participation
            participation = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            
            if not participation:
                db.close()
                return None
            
            # Calculate score
            score = TestService.calculate_score(participation_id)
            
            # Update participation status
            participation.status = 'completed'
            participation.completed_at = datetime.utcnow()
            db.commit()
            
            # Count correct answers
            correct_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.is_correct == True
            ).count()
            
            total_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id
            ).count()
            
            # Save score record
            score_record = Score(
                user_id=participation.user_id,
                score=score,
                correct_count=correct_count,
                total_questions=total_count
            )
            db.add(score_record)
            db.commit()
            
            db.close()
            
            return {
                'score': score,
                'correct_count': correct_count,
                'total_questions': total_count,
                'percentage': round((correct_count / total_count * 100) if total_count > 0 else 0, 1)
            }
        except Exception as e:
            db.rollback()
            db.close()
            print(f"Error completing test: {e}")
            return None
    
    @staticmethod
    def get_leaderboard(test_session_id: int, limit: int = 10) -> list:
        """Get top scores from leaderboard"""
        db = Session()
        
        leaders = db.query(Leaderboard).filter(
            Leaderboard.test_session_id == test_session_id
        ).order_by(Leaderboard.score.desc()).limit(limit).all()
        
        db.close()
        return leaders