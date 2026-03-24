"""
utils/test_service.py

TUZATILDI (to'liq qayta yozildi):
  1. Score arxiv tizimi:
       - Foydalanuvchi bir yo'nalishda qayta test yechganda oldingi score arxivlanadi
       - is_archived=True natijalar reyting/leaderboard da ko'rinmaydi
       - Shaxsiy natijalar sahifasida hammasi (arxivlangan ham) ko'rinadi

  2. Leaderboard duplikatlardan himoya:
       - _rebuild_leaderboard_for_direction(): delete-then-recreate pattern
       - Har user uchun faqat bitta (eng yaxshi) natija
       - Uchala period (daily, weekly, all_time) alohida tozalanadi va qayta yaratiladi

  3. attempted_count tracking:
       - Test chala tashlab ketilsa ham qayd qilinadi
       - attempted_count = javob berilgan savollar soni (skip/unanswered hisoblanmaydi)
       - total_questions = har doim 90
       - Foiz = correct_count / 90 * 100

  4. complete_test() yaxshilandi:
       - Takroriy chaqiruvdan himoya
       - Snapshot tozalanadi
       - Arxivlash oldin, keyin yangi Score

  5. get_user_scores() TUZATILDI:
       - INNER JOIN → OUTER JOIN (participation_id=NULL bo'lgan eski scorlar ham ko'rinadi)
       - s.participation lazy load → session yopilgandan keyin xato bermaslik uchun
         participation lar alohida batch so'rovda olinadi
       - debug `print(s.direction_id)` olib tashlandi
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
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

logger = logging.getLogger(__name__)

# Har doim 90 savol — o'zgarmaydi
TOTAL_TEST_QUESTIONS = 90


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
        try:
            return db2.query(TestSession).filter(TestSession.id == session_id).first()
        finally:
            db2.close()

    # ─────────────────────────────────────────────────────────────
    # Participation
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def create_participation(user_id: int, direction_id: str) -> Optional[UserTestParticipation]:
        """Kunlik cheklov: har user kuniga faqat 1 ta test."""
        db = Session()
        try:
            today = datetime.utcnow().date()
            existing_today = db.query(UserTestParticipation).filter(
                UserTestParticipation.user_id == user_id,
                func.date(UserTestParticipation.started_at) == today,
                UserTestParticipation.status.in_(['active', 'completed'])
            ).first()
            if existing_today:
                return None

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
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        db2 = Session()
        try:
            return db2.query(UserTestParticipation).filter(
                UserTestParticipation.id == p_id
            ).first()
        finally:
            db2.close()

    @staticmethod
    def get_active_participation(user_id: int) -> Optional[UserTestParticipation]:
        """Faqat vaqti o'tmagan aktiv participation."""
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
        except Exception:
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
                'participation_id':      p.id,
                'test_session_id':       p.test_session_id,
                'questions':             p.snapshot_questions,
                'current_question_index': p.snapshot_current_index or 0,
                'answers':               p.snapshot_answers or {},
                'deadline_at':           p.deadline_at,
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
        return ordered[:TOTAL_TEST_QUESTIONS]

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
    # Score hisoblash
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def calculate_score(participation_id: int) -> float:
        """DTM ball tizimi bo'yicha hisoblash."""
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
                question = db.query(Question).filter(
                    Question.id == answer.question_id
                ).first()
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

    # ─────────────────────────────────────────────────────────────
    # Test yakunlash — ASOSIY FUNKSIYA
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def complete_test(participation_id: int) -> Optional[Dict[str, Any]]:
        """
        Testni yakunlaydi. Quyidagi tartibda ishlaydi:
          1. Participation 'completed' ga o'tkaziladi
          2. score, correct_count, attempted_count hisoblanadi
             - total_questions = har doim 90
             - attempted_count = javob berilgan savollar (skip/unanswered hisoblanmaydi)
             - Foiz = correct_count / 90 * 100
          3. Bu user+direction uchun oldingi NON-ARCHIVED scorlar arxivlanadi
          4. Yangi Score yaratiladi (is_archived=False)
          5. Leaderboard qayta quriladi (faqat non-archived, per user best score)
          6. Snapshot tozalanadi

        Agar allaqachon 'completed' bo'lsa — mavjud natija qaytariladi.
        """
        db = Session()
        try:
            participation = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if not participation:
                return None

            # Allaqachon tugallangan — mavjud score qaytariladi
            if participation.status == 'completed':
                score_obj = db.query(Score).filter(
                    Score.participation_id == participation_id
                ).first()
                if score_obj:
                    pct = round(score_obj.correct_count / TOTAL_TEST_QUESTIONS * 100, 1)
                    return {
                        'score':           score_obj.score,
                        'correct_count':   score_obj.correct_count,
                        'attempted_count': score_obj.attempted_count or 0,
                        'total_questions': TOTAL_TEST_QUESTIONS,
                        'percentage':      pct,
                    }
                return None

            # Participation ni yakunlaymiz
            participation.status       = 'completed'
            participation.completed_at = datetime.utcnow()
            # Snapshot tozalash
            participation.snapshot_questions     = None
            participation.snapshot_current_index = 0
            participation.snapshot_answers       = None
            db.commit()

            # Ball hisoblash
            score_val = TestService.calculate_score(participation_id)

            # To'g'ri javoblar
            correct_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.is_correct.is_(True)
            ).count()

            # Javob berilgan savollar (skip va unanswered hisoblanmaydi)
            # save_answer faqat A/B/C/D da chaqiriladi, skip da emas
            attempted_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id
            ).count()

            user_id      = participation.user_id
            direction_id = participation.direction_id
            ts_id        = participation.test_session_id

            # Bu user+direction uchun oldingi non-archived scorlarni arxivlaymiz
            # (yangi score yaratilishidan OLDIN)
            old_scores = (
                db.query(Score)
                .join(UserTestParticipation,
                      Score.participation_id == UserTestParticipation.id)
                .filter(
                    Score.user_id == user_id,
                    UserTestParticipation.direction_id == direction_id,
                    Score.is_archived == False,
                    Score.participation_id != participation_id
                )
                .all()
            )
            for old_s in old_scores:
                old_s.is_archived = True
            db.commit()

            # Yangi Score yaratish
            new_score = Score(
                user_id=user_id,
                participation_id=participation_id,
                score=score_val,
                correct_count=correct_count,
                attempted_count=attempted_count,
                total_questions=TOTAL_TEST_QUESTIONS,
                is_archived=False,
            )
            db.add(new_score)
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error("complete_test xato (participation_id=%d): %s", participation_id, e)
            return None
        finally:
            db.close()

        # Leaderboard qayta quriladi (alohida session)
        try:
            TestService._rebuild_leaderboard_for_direction(ts_id, direction_id)
        except Exception as e:
            logger.error("Leaderboard rebuild xato: %s", e)

        pct = round(correct_count / TOTAL_TEST_QUESTIONS * 100, 1)
        return {
            'score':           score_val,
            'correct_count':   correct_count,
            'attempted_count': attempted_count,
            'total_questions': TOTAL_TEST_QUESTIONS,
            'percentage':      pct,
        }

    # ─────────────────────────────────────────────────────────────
    # Auto-finish (scheduler)
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
    # Leaderboard — DELETE + RECREATE (duplikatlardan himoya)
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _rebuild_leaderboard_for_direction(test_session_id: int, direction_id: str) -> None:
        """
        Berilgan direction uchun barcha periodlar bo'yicha leaderboard ni
        to'liq qayta quradi.

        Algoritm:
          1. O'sha direction+period+vaqt oynasidagi barcha Leaderboard yozuvlarini o'chir
          2. Faqat non-archived scorlardan, har user uchun ENG YUQORI ball ni ol
          3. Rank bo'yicha tartiblab qayta yoz

        Bu DELETE+INSERT yondashuvi duplikatlarni mutlaqo yo'q qiladi.
        """
        db = Session()
        try:
            now        = datetime.utcnow()
            today      = now.date()
            week_start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())

            for period in ('daily', 'weekly', 'all_time'):
                # ── Mavjud yozuvlarni o'chirish ──────────────────────────────
                del_q = db.query(Leaderboard).filter(
                    Leaderboard.direction_id == direction_id,
                    Leaderboard.period == period
                )
                if period == 'daily':
                    del_q = del_q.filter(func.date(Leaderboard.timestamp) == today)
                elif period == 'weekly':
                    del_q = del_q.filter(Leaderboard.timestamp >= week_start)
                # all_time — hamma yozuvlar o'chiriladi

                del_q.delete(synchronize_session=False)
                db.flush()

                # ── Har user uchun eng yaxshi non-archived score ─────────────
                best_q = (
                    db.query(Score.user_id, func.max(Score.score).label('best'))
                    .join(UserTestParticipation,
                          Score.participation_id == UserTestParticipation.id)
                    .join(User, Score.user_id == User.id)
                    .filter(
                        UserTestParticipation.direction_id == direction_id,
                        Score.is_archived == False,
                    )
                )
                if period == 'daily':
                    best_q = best_q.filter(
                        func.date(UserTestParticipation.completed_at) == today
                    )
                elif period == 'weekly':
                    best_q = best_q.filter(
                        UserTestParticipation.completed_at >= week_start
                    )

                user_bests = (
                    best_q
                    .group_by(Score.user_id)
                    .order_by(func.max(Score.score).desc())
                    .all()
                )

                # ── Yangi Leaderboard yozuvlari ──────────────────────────────
                for rank, (uid, best_score) in enumerate(user_bests, 1):
                    db.add(Leaderboard(
                        test_session_id=test_session_id,
                        user_id=uid,
                        direction_id=direction_id,
                        rank=rank,
                        total_score=best_score,
                        period=period,
                        timestamp=now,
                    ))

            db.commit()
            logger.debug(
                "Leaderboard rebuilt: direction=%s, periods=3", direction_id
            )
        except Exception as e:
            db.rollback()
            logger.error("_rebuild_leaderboard_for_direction xato: %s", e)
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────
    # Leaderboard so'rovlari
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def get_direction_leaderboard(
        direction_id: str,
        period: str = 'all_time',
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Direction + period bo'yicha reyting.
        Faqat non-archived scorlar (arxivlanganlar ko'rinmaydi).
        """
        db = Session()
        try:
            today      = datetime.utcnow().date()
            week_start = datetime.combine(
                today - timedelta(days=today.weekday()), datetime.min.time()
            )

            query = (
                db.query(Leaderboard)
                .join(User, Leaderboard.user_id == User.id)
                .filter(
                    Leaderboard.direction_id == direction_id,
                    Leaderboard.period == period,
                )
                .options(joinedload(Leaderboard.user))
            )

            if period == 'daily':
                query = query.filter(func.date(Leaderboard.timestamp) == today)
            elif period == 'weekly':
                query = query.filter(Leaderboard.timestamp >= week_start)

            entries = query.order_by(Leaderboard.rank).limit(limit).all()

            result = []
            for lb in entries:
                u = lb.user
                result.append({
                    'rank':       lb.rank,
                    'score':      lb.total_score,
                    'user_id':    lb.user_id,
                    'first_name': u.first_name if u else '—',
                    'last_name':  u.last_name  if u else '',
                })
            return result
        finally:
            db.close()

    @staticmethod
    def get_user_direction_rank(user_id: int, direction_id: str) -> int:
        """
        Foydalanuvchining yo'nalish ichidagi o'rni.
        Faqat non-archived scorlar hisobga olinadi.
        """
        db = Session()
        try:
            # Foydalanuvchining eng yuqori non-archived bali
            user_best = (
                db.query(func.max(Score.score))
                .join(UserTestParticipation,
                      Score.participation_id == UserTestParticipation.id)
                .filter(
                    Score.user_id == user_id,
                    UserTestParticipation.direction_id == direction_id,
                    Score.is_archived == False,
                )
                .scalar()
            ) or 0.0

            # Undan yuqori ball olgan boshqa userlar soni
            better_count = (
                db.query(func.count(Score.user_id.distinct()))
                .join(UserTestParticipation,
                      Score.participation_id == UserTestParticipation.id)
                .join(User, Score.user_id == User.id)
                .filter(
                    User.direction_id == direction_id,
                    UserTestParticipation.direction_id == direction_id,
                    Score.is_archived == False,
                    Score.score > user_best,
                    Score.user_id != user_id,
                )
                .scalar()
            ) or 0

            return better_count + 1
        finally:
            db.close()

    @staticmethod
    def get_leaderboard(test_session_id: int, limit: int = 10) -> list:
        db = Session()
        try:
            return (
                db.query(Leaderboard)
                .filter(Leaderboard.test_session_id == test_session_id)
                .order_by(Leaderboard.total_score.desc())
                .limit(limit)
                .all()
            )
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────
    # Shaxsiy natijalar — TUZATILDI
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def get_user_scores(
        user_id: int,
        include_archived: bool = False,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Foydalanuvchining natijalarini qaytaradi.

        TUZATILDI:
          - INNER JOIN → OUTER JOIN: participation_id=NULL bo'lgan
            eski scorlar ham ko'rinadi, yo'qolmaydi.
          - s.participation lazy load olib tashlandi: session yopilgandan
            keyin attribute xatosi bermaslik uchun participation lar
            alohida IN so'rovda olinadi.
          - debug print(s.direction_id) olib tashlandi.
          - attempted_count uchun `or 0` qo'shildi (NULL bo'lishi mumkin).

        include_archived=True: arxivlangan natijalar ham ko'rinadi (shaxsiy sahifa)
        include_archived=False: faqat hozirgi (reyting uchun)
        """
        db = Session()
        try:
            query = (
                db.query(Score)
                .outerjoin(
                    UserTestParticipation,
                    Score.participation_id == UserTestParticipation.id
                )
                .filter(Score.user_id == user_id)
            )
            if not include_archived:
                query = query.filter(Score.is_archived == False)

            scores = (
                query
                .order_by(Score.created_at.desc())
                .limit(limit)
                .all()
            )

            # participation larni session ichida batch olamiz
            # (session yopilgandan keyin lazy load qilish xato beradi)
            p_ids = [s.participation_id for s in scores if s.participation_id is not None]
            participations: Dict[int, UserTestParticipation] = {}
            if p_ids:
                for p in db.query(UserTestParticipation).filter(
                    UserTestParticipation.id.in_(p_ids)
                ).all():
                    participations[p.id] = p

            result = []
            for s in scores:
                pct = round(s.correct_count / TOTAL_TEST_QUESTIONS * 100, 1)
                p = participations.get(s.participation_id) if s.participation_id else None
                result.append({
                    'score':           s.score,
                    'correct_count':   s.correct_count,
                    'attempted_count': s.attempted_count or 0,
                    'total_questions': TOTAL_TEST_QUESTIONS,
                    'percentage':      pct,
                    'is_archived':     s.is_archived,
                    'created_at':      s.created_at,
                    'direction_id':    p.direction_id if p else None,
                })
            return result
        finally:
            db.close()