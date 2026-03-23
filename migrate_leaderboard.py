#!/usr/bin/env python3
"""
Migration script for Leaderboard table updates
Run this after updating the Leaderboard model
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import Session
from database.models import Leaderboard, Direction
from sqlalchemy import text

def migrate_leaderboard():
    db = Session()
    try:
        # Check if columns exist
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'leaderboard' AND column_name IN ('direction_id', 'period')
        """))
        existing_columns = [row[0] for row in result]

        if 'direction_id' not in existing_columns:
            print("Adding direction_id column...")
            db.execute(text("ALTER TABLE leaderboard ADD COLUMN direction_id VARCHAR(10)"))
            db.execute(text("ALTER TABLE leaderboard ADD CONSTRAINT fk_leaderboard_direction FOREIGN KEY (direction_id) REFERENCES directions(id)"))

        if 'period' not in existing_columns:
            print("Adding period column...")
            db.execute(text("ALTER TABLE leaderboard ADD COLUMN period VARCHAR(20) DEFAULT 'all_time'"))

        # Populate direction_id for existing records
        print("Populating direction_id for existing records...")
        participations = db.execute(text("""
            SELECT l.id, p.direction_id
            FROM leaderboard l
            JOIN user_test_participation p ON l.test_session_id = p.test_session_id
            WHERE l.user_id = p.user_id AND l.direction_id IS NULL
        """)).fetchall()

        for lb_id, dir_id in participations:
            db.execute(text("UPDATE leaderboard SET direction_id = :dir_id WHERE id = :lb_id"),
                      {'dir_id': dir_id, 'lb_id': lb_id})

        # Set default period for existing records
        db.execute(text("UPDATE leaderboard SET period = 'all_time' WHERE period IS NULL"))

        db.commit()
        print("✅ Migration completed successfully")

    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting leaderboard migration...")
    migrate_leaderboard()
    print("Migration complete!")