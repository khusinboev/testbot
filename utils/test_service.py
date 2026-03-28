"""
utils/test_service.py

TestService bir klass — lekin ichki metodlar mantiqiy bloklarga ajratilgan:
  ┌─ Session management   get_or_create_test_session()
  ├─ Participation        create / get_active / save_snapshot / load_snapshot
  ├─ Questions            get_test_questions()
  ├─ Answers              save_answer()
  ├─ Scoring              calculate_score()  (private-ish)
  ├─ Completion           complete_test()    (asosiy)
  ├─ Scheduler support    get_expired_participations()
  ├─ Leaderboard build    _rebuild_leaderboard_for_direction()
  └─ Leaderboard read     get_direction_leaderboard() / get_user_direction_rank()
"""

from __future__ import annotations

import logging
import random
import threading
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import config
from database.db import Session
from database.models import (
    Admin, Direction, Leaderboard, Question,
    Score, TestSession, User, UserAnswer, UserTestParticipation,
)
from sqlalchemy import func
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

# Har doim 90 savol — o'zgarmaydi
TOTAL_TEST_QUESTIONS = 90


class TestService:

    # ──────────────────────────────────────────────────────────────────────────
    # SESSION
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_test_session() -> TestSession:
        """Bugungi aktiv TestSession ni oladi, yo'q bo'lsa yaratadi."""
        db = Session()
        try:
            today = datetime.utcnow().date()

            test_session = db.query(TestSession).filter(
                func.date(TestSession.exam_date) == today,
                TestSession.status == "active",
            ).first()

            if not test_session:
                admin = db.query(Admin).first()
                if not admin:
                    admin = Admin(telegram_id=0, role="super_admin")
                    db.add(admin)
                    db.flush()

                test_session = TestSession(
                    admin_id=admin.id,
                    exam_date=datetime.utcnow(),
                    start_time=datetime.utcnow(),
                    duration_minutes=config.TEST_DURATION_MINUTES,
                    status="active",
                )
                db.add(test_session)
                db.commit()

            db.refresh(test_session)
            db.expunge(test_session)
            return test_session
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────────────────
    # PARTICIPATION
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_participation(user_id: int, direction_id: str) -> Optional[UserTestParticipation]:
        """
        Yangi participation yaratadi.
        Kunlik cheklov: har user kuniga faqat 1 ta test yecha oladi.
        Limit oshsa — None qaytaradi.
        """
        db = Session()
        try:
            today = datetime.utcnow().date()
            already_today = db.query(UserTestParticipation).filter(
                UserTestParticipation.user_id == user_id,
                func.date(UserTestParticipation.started_at) == today,
                UserTestParticipation.status.in_(["active", "completed"]),
            ).first()

            if already_today:
                return None

            test_session = TestService.get_or_create_test_session()
            deadline = datetime.utcnow() + timedelta(minutes=config.TEST_DURATION_MINUTES)

            p = UserTestParticipation(
                user_id=user_id,
                test_session_id=test_session.id,
                direction_id=direction_id,
                status="active",
                started_at=datetime.utcnow(),
                deadline_at=deadline,
            )
            db.add(p)
            db.commit()
            db.refresh(p)
            db.expunge(p)
            return p
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get_active_participation(user_id: int) -> Optional[UserTestParticipation]:
        """Vaqti hali o'tmagan aktiv participation ni qaytaradi."""
        db = Session()
        try:
            now = datetime.utcnow()
            p = db.query(UserTestParticipation).filter(
                UserTestParticipation.user_id == user_id,
                UserTestParticipation.status == "active",
                UserTestParticipation.deadline_at > now,
            ).order_by(UserTestParticipation.started_at.desc()).first()

            if p is None:
                return None
            db.expunge(p)
            return p
        finally:
            db.close()

    @staticmethod
    def save_snapshot(participation_id: int, questions: list,
                      current_index: int, answers: dict) -> None:
        """Test jarayonida vaqti-vaqti bilan holat saqlanadi (crash-recovery)."""
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
        """Saqlangan snapshot ni qaytaradi. Yo'q bo'lsa — None."""
        db = Session()
        try:
            p = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if not p or not p.snapshot_questions:
                return None
            return {
                "participation_id":       p.id,
                "test_session_id":        p.test_session_id,
                "questions":              p.snapshot_questions,
                "current_question_index": p.snapshot_current_index or 0,
                "answers":                p.snapshot_answers or {},
                "deadline_at":            p.deadline_at,
            }
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────────────────
    # QUESTIONS
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_test_questions(direction_id: str) -> List[Dict[str, Any]]:
        """
        90 ta savol qaytaradi — guruhlar tartibi:
          Matematika (10) → Ona tili (10) → Tarix (10)
          → 1-asosiy fan (30) → 2-asosiy fan (30)

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

        groups = [
            {"label": "Majburiy — Matematika", "subject_id": 1,
             "count": config.MANDATORY_QUESTIONS_PER_SUBJECT},
            {"label": "Majburiy — Ona tili",   "subject_id": 6,
             "count": config.MANDATORY_QUESTIONS_PER_SUBJECT},
            {"label": "Majburiy — Tarix",       "subject_id": 5,
             "count": config.MANDATORY_QUESTIONS_PER_SUBJECT},
            {"label": f"Asosiy (1-fan) — {subj1_name}", "subject_id": subj1_id,
             "count": config.SPECIALIZED_QUESTIONS_PER_SUBJECT},
            {"label": f"Asosiy (2-fan) — {subj2_name}", "subject_id": subj2_id,
             "count": config.SPECIALIZED_QUESTIONS_PER_SUBJECT},
        ]

        result: List[Dict] = []
        for grp in groups:
            questions = TestService._fetch_shuffled(grp["subject_id"], grp["count"])
            for q in questions:
                q["group_label"] = grp["label"]
            result.extend(questions)

        return result[:TOTAL_TEST_QUESTIONS]

    @staticmethod
    def _fetch_shuffled(subject_id: int, count: int) -> List[Dict]:
        """
        Berilgan fandan `count` ta savol oladi, random aralashtirib,
        variantlar tartibini ham random qiladi (to'g'ri javob kuzatiladi).

        Samarali strategiya (50k+ foydalanuvchi):
          1. Faqat ID larni yukla (juda tez)
          2. Pythonda random sampling
          3. Tanlangan IDlar bo'yicha faqat kerakli savollarni yukla
        """
        # 1. Faqat IDlarni yukla
        db = Session()
        try:
            all_ids = [
                r[0] for r in
                db.query(Question.id).filter(Question.subject_id == subject_id).all()
            ]
        finally:
            db.close()

        if not all_ids:
            return []

        # 2. Random sampling — butun ro'yxatni aralashtirishga hojat yo'q
        sampled_ids = random.sample(all_ids, min(count, len(all_ids)))

        # 3. Faqat tanlangan savollarni yukla
        db = Session()
        try:
            rows = db.query(Question).filter(Question.id.in_(sampled_ids)).all()
        finally:
            db.close()

        # Tartibni ham random qil (IN clause tartibni kafolat qilmaydi)
        random.shuffle(rows)
        result = []

        for q in rows[:count]:
            correct_text = {
                "A": q.option_a, "B": q.option_b,
                "C": q.option_c, "D": q.option_d,
            }.get(q.correct_answer, q.option_a)

            options = [
                ("A", q.option_a), ("B", q.option_b),
                ("C", q.option_c), ("D", q.option_d),
            ]
            random.shuffle(options)

            new_correct = "A"
            for letter, (_, text) in zip("ABCD", options):
                if text == correct_text:
                    new_correct = letter
                    break

            result.append({
                "id":             q.id,
                "text_uz":        q.text_uz,
                "option_a":       options[0][1],
                "option_b":       options[1][1],
                "option_c":       options[2][1],
                "option_d":       options[3][1],
                "correct_answer": new_correct,
                "subject_id":     q.subject_id,
            })

        return result

    # ──────────────────────────────────────────────────────────────────────────
    # ANSWERS
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def save_answer(participation_id: int, user_id: int,
                    test_session_id: int, question_id: int,
                    selected_answer: str,
                    correct_answer: Optional[str] = None) -> bool:
        """
        Javobni saqlaydi. Bir xil savol uchun takroriy yozuv bo'lmaydi
        (UniqueConstraint himoyasi + oldindan tekshiruv).

        correct_answer — snapshot dagi ararishtirilgan to'g'ri javob harfi.
        Berilsa DB ga murojaat qilinmaydi (tez + to'g'ri).
        Berilmasa — DB dan original correct_answer olinadi (fallback).
        """
        db = Session()
        try:
            existing = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.question_id == question_id,
            ).first()
            if existing:
                return True

            if correct_answer is not None:
                is_correct = bool(selected_answer and selected_answer == correct_answer)
            else:
                question = db.query(Question).filter(Question.id == question_id).first()
                if not question:
                    return False
                is_correct = bool(selected_answer and selected_answer == question.correct_answer)

            db.add(UserAnswer(
                user_id=user_id,
                test_session_id=test_session_id,
                participation_id=participation_id,
                question_id=question_id,
                selected_answer=selected_answer,
                is_correct=is_correct,
            ))
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────────────────
    # SCORING  (ichki hisoblash)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_score(participation_id: int) -> float:
        """
        DTM ball tizimi:
          - Majburiy fanlar (Matematika/Tarix/Ona tili): MANDATORY_POINTS_PER_QUESTION
          - 1-asosiy fan: SPECIALIZED_HIGH_POINTS
          - 2-asosiy fan: SPECIALIZED_LOW_POINTS
        """
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

            correct_answers = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.is_correct.is_(True),
            ).all()

            if not correct_answers:
                return 0.0

            # Barcha savollarni BITTA so'rovda yukla (N+1 o'rniga 1 so'rov)
            q_ids = [ans.question_id for ans in correct_answers]
            questions_map = {
                q.id: q
                for q in db.query(Question).filter(Question.id.in_(q_ids)).all()
            }

            total = 0.0
            for ans in correct_answers:
                q = questions_map.get(ans.question_id)
                if not q:
                    continue
                if q.subject_id in config.MANDATORY_SUBJECT_IDS:
                    total += config.MANDATORY_POINTS_PER_QUESTION
                elif q.subject_id == direction.subject1_id:
                    total += config.SPECIALIZED_HIGH_POINTS
                elif q.subject_id == direction.subject2_id:
                    total += config.SPECIALIZED_LOW_POINTS

            return round(total, 2)
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────────────────
    # COMPLETION  (asosiy funksiya)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def complete_test(participation_id: int) -> Optional[Dict[str, Any]]:
        """
        Testni yakunlaydi. Qadamlar:
          1. participation → 'completed' + snapshot tozalanadi
          2. score / correct_count / attempted_count hisoblanadi
          3. Bir direction bo'yicha oldingi non-archived score arxivlanadi
          4. Yangi Score yaratiladi (is_archived=False)
          5. Leaderboard qayta quriladi (alohida session)

        Agar allaqachon 'completed' — mavjud natija qaytariladi.
        """
        db = Session()
        try:
            p = db.query(UserTestParticipation).filter(
                UserTestParticipation.id == participation_id
            ).first()
            if not p:
                return None

            # Takroriy chaqiruv himoyasi
            if p.status == "completed":
                existing = db.query(Score).filter(
                    Score.participation_id == participation_id
                ).first()
                if existing:
                    pct = round(existing.correct_count / TOTAL_TEST_QUESTIONS * 100, 1)
                    return {
                        "score":           existing.score,
                        "correct_count":   existing.correct_count,
                        "attempted_count": existing.attempted_count or 0,
                        "total_questions": TOTAL_TEST_QUESTIONS,
                        "percentage":      pct,
                    }
                return None

            # 1. Participation yakunlash + snapshot tozalash
            p.status                   = "completed"
            p.completed_at             = datetime.utcnow()
            p.snapshot_questions       = None
            p.snapshot_current_index   = 0
            p.snapshot_answers         = None
            db.commit()

            # 2. Natijalarni hisoblash
            score_val = TestService.calculate_score(participation_id)

            correct_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
                UserAnswer.is_correct.is_(True),
            ).count()

            attempted_count = db.query(UserAnswer).filter(
                UserAnswer.participation_id == participation_id,
            ).count()

            user_id      = p.user_id
            direction_id = p.direction_id
            ts_id        = p.test_session_id

            # 3. Bu direction bo'yicha oldingi non-archived scorlarni arxivlash
            old_scores = (
                db.query(Score)
                .join(UserTestParticipation,
                      Score.participation_id == UserTestParticipation.id)
                .filter(
                    Score.user_id == user_id,
                    UserTestParticipation.direction_id == direction_id,
                    Score.is_archived == False,
                    Score.participation_id != participation_id,
                )
                .all()
            )
            for old in old_scores:
                old.is_archived = True
            db.commit()

            # 4. Yangi score
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

        # 5. Leaderboard rebuild — fon threadida (asosiy javobni bloklamaydi)
        threading.Thread(
            target=TestService._rebuild_leaderboard_for_direction,
            args=(ts_id, direction_id),
            daemon=True,
            name=f"leaderboard-{direction_id}",
        ).start()

        pct = round(correct_count / TOTAL_TEST_QUESTIONS * 100, 1)
        return {
            "score":           score_val,
            "correct_count":   correct_count,
            "attempted_count": attempted_count,
            "total_questions": TOTAL_TEST_QUESTIONS,
            "percentage":      pct,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # SCHEDULER SUPPORT
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_expired_participations() -> List[Tuple[int, int]]:
        """Vaqti o'tgan, hali 'active' bo'lgan participationlar [(id, user_id)]."""
        db = Session()
        try:
            now = datetime.utcnow()
            expired = db.query(UserTestParticipation).filter(
                UserTestParticipation.status == "active",
                UserTestParticipation.deadline_at <= now,
            ).all()
            return [(p.id, p.user_id) for p in expired]
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────────────────
    # LEADERBOARD BUILD  (delete + recreate, duplikatlardan himoya)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _rebuild_leaderboard_for_direction(test_session_id: int, direction_id: str) -> None:
        """
        Berilgan direction uchun barcha periodlar (daily / weekly / all_time)
        bo'yicha leaderboard ni to'liq qayta quradi.

        Algoritm: DELETE → INSERT (duplikat bo'lishi mumkin emas).
        Faqat is_archived=False scorlar hisobga olinadi.
        Har user uchun ENG YUQORI ball tanlanadi.
        """
        db = Session()
        try:
            now        = datetime.utcnow()
            today      = now.date()
            week_start = datetime.combine(
                today - timedelta(days=today.weekday()), datetime.min.time()
            )

            for period in ("daily", "weekly", "all_time"):
                # ── 1. O'chirish ────────────────────────────────────────────
                del_q = db.query(Leaderboard).filter(
                    Leaderboard.direction_id == direction_id,
                    Leaderboard.period == period,
                )
                if period == "daily":
                    del_q = del_q.filter(func.date(Leaderboard.timestamp) == today)
                elif period == "weekly":
                    del_q = del_q.filter(Leaderboard.timestamp >= week_start)

                del_q.delete(synchronize_session=False)
                db.flush()

                # ── 2. Har user uchun eng yaxshi non-archived score ─────────
                best_q = (
                    db.query(Score.user_id, func.max(Score.score).label("best"))
                    .join(UserTestParticipation,
                          Score.participation_id == UserTestParticipation.id)
                    .join(User, Score.user_id == User.id)
                    .filter(
                        UserTestParticipation.direction_id == direction_id,
                        Score.is_archived == False,
                    )
                )
                if period == "daily":
                    best_q = best_q.filter(
                        func.date(UserTestParticipation.completed_at) == today
                    )
                elif period == "weekly":
                    best_q = best_q.filter(
                        UserTestParticipation.completed_at >= week_start
                    )

                user_bests = (
                    best_q
                    .group_by(Score.user_id)
                    .order_by(func.max(Score.score).desc())
                    .all()
                )

                # ── 3. Yangi yozuvlar ───────────────────────────────────────
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
            logger.debug("Leaderboard rebuilt: direction=%s", direction_id)

        except Exception as e:
            db.rollback()
            logger.error("_rebuild_leaderboard_for_direction xato: %s", e)
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────────────────
    # LEADERBOARD READ
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_direction_leaderboard(
        direction_id: str,
        period: str = "all_time",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Direction + period bo'yicha reyting. Faqat non-archived scorlar."""
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

            if period == "daily":
                query = query.filter(func.date(Leaderboard.timestamp) == today)
            elif period == "weekly":
                query = query.filter(Leaderboard.timestamp >= week_start)

            entries = query.order_by(Leaderboard.rank).limit(limit).all()

            return [
                {
                    "rank":       lb.rank,
                    "score":      lb.total_score,
                    "user_id":    lb.user_id,
                    "first_name": lb.user.first_name if lb.user else "—",
                    "last_name":  lb.user.last_name  if lb.user else "",
                }
                for lb in entries
            ]
        finally:
            db.close()

    @staticmethod
    def get_user_direction_rank(user_id: int, direction_id: str) -> int:
        """Foydalanuvchining yo'nalish ichidagi o'rni (1-dan). Non-archived scorlar."""
        db = Session()
        try:
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
    def get_user_scores(
        user_id: int,
        include_archived: bool = False,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Foydalanuvchining natijalar tarixi.
        include_archived=True: arxivlanganlar ham ko'rinadi (shaxsiy sahifa).
        include_archived=False: faqat joriy natija (reyting uchun).

        OUTER JOIN ishlatiladi — participation_id=NULL bo'lgan eski scorlar ham chiqadi.
        """
        db = Session()
        try:
            query = (
                db.query(Score)
                .outerjoin(
                    UserTestParticipation,
                    Score.participation_id == UserTestParticipation.id,
                )
                .filter(Score.user_id == user_id)
            )
            if not include_archived:
                query = query.filter(Score.is_archived == False)

            scores = query.order_by(Score.created_at.desc()).limit(limit).all()

            # participation larni batch load qilamiz (session yopilgandan keyin lazy load xato)
            p_ids = [s.participation_id for s in scores if s.participation_id is not None]
            participations: Dict[int, UserTestParticipation] = {}
            if p_ids:
                for p in db.query(UserTestParticipation).filter(
                    UserTestParticipation.id.in_(p_ids)
                ).all():
                    participations[p.id] = p

            return [
                {
                    "score":           s.score,
                    "correct_count":   s.correct_count,
                    "attempted_count": s.attempted_count or 0,
                    "total_questions": TOTAL_TEST_QUESTIONS,
                    "percentage":      round(s.correct_count / TOTAL_TEST_QUESTIONS * 100, 1),
                    "is_archived":     s.is_archived,
                    "created_at":      s.created_at,
                    "direction_id":    participations[s.participation_id].direction_id
                                       if s.participation_id else None,
                }
                for s in scores
            ]
        finally:
            db.close()

    @staticmethod
    def get_leaderboard(test_session_id: int, limit: int = 10) -> list:
        """Session bo'yicha leaderboard (admin panel uchun)."""
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