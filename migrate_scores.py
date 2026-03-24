#!/usr/bin/env python3
"""
migrate_scores.py

Mavjud bazaga yangi ustunlar qo'shish:
  - scores.is_archived    (BOOLEAN DEFAULT FALSE)
  - scores.attempted_count (INTEGER DEFAULT 0)

Yangi baza uchun (drop_tables + init_db) shart emas — bu faqat
mavjud ma'lumotlarni saqlab qolmoqchi bo'lganlarga.

Ishlatish:
    python migrate_scores.py
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import Session
from sqlalchemy import text


def run_migration():
    db = Session()
    try:
        print("🔄 Migration boshlandi...")

        # 1. is_archived ustuni
        try:
            db.execute(text(
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS "
                "is_archived BOOLEAN DEFAULT FALSE"
            ))
            db.commit()
            print("✅ scores.is_archived qo'shildi (yoki allaqachon bor)")
        except Exception as e:
            db.rollback()
            print(f"⚠️  is_archived: {e}")

        # 2. attempted_count ustuni
        try:
            db.execute(text(
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS "
                "attempted_count INTEGER DEFAULT 0"
            ))
            db.commit()
            print("✅ scores.attempted_count qo'shildi (yoki allaqachon bor)")
        except Exception as e:
            db.rollback()
            print(f"⚠️  attempted_count: {e}")

        # 3. Mavjud scorelarda total_questions ni 90 ga to'g'rilash
        try:
            db.execute(text("UPDATE scores SET total_questions = 90 WHERE total_questions != 90"))
            db.commit()
            print("✅ Mavjud scorelarda total_questions = 90 qilib to'g'rilandi")
        except Exception as e:
            db.rollback()
            print(f"⚠️  total_questions update: {e}")

        # 4. Leaderboard duplikatlarini tozalash
        # Har direction+period+user kombinatsiyasida faqat eng oxirgisi qoladi
        try:
            db.execute(text("""
                DELETE FROM leaderboard
                WHERE id NOT IN (
                    SELECT MAX(id)
                    FROM leaderboard
                    GROUP BY user_id, direction_id, period
                )
            """))
            deleted = db.execute(text("SELECT ROW_COUNT()")).scalar() or 0
            db.commit()
            print(f"✅ Leaderboard duplikatlari tozalandi")
        except Exception as e:
            db.rollback()
            print(f"⚠️  Leaderboard cleanup: {e}")

        print("\n🎉 Migration tugadi!")
        print("\nEslatma: bot/admin ni qayta ishga tushiring.")

    except Exception as e:
        db.rollback()
        print(f"❌ Migration xato: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
