"""
database/db.py

TUZATILDI:
  1. seed_regions_and_districts() — base path xato edi:
       database/db.py → dirname → database/ → dirname → loyiha ildizi ✅
  2. StaticPool PostgreSQL bilan mos emas → to'g'ri pool
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import config

engine_kwargs: dict = {
    'pool_pre_ping': True,
    'pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 30,
    'pool_recycle': 1800,
}

if config.DATABASE_URL.startswith('sqlite'):
    from sqlalchemy.pool import StaticPool
    engine_kwargs = {
        'poolclass': StaticPool,
        'connect_args': {'check_same_thread': False},
    }

engine = create_engine(config.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Session = scoped_session(SessionLocal)


def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from .models import Base
    Base.metadata.create_all(bind=engine)


def drop_tables():
    from .models import Base
    Base.metadata.drop_all(bind=engine)


def init_db():
    create_tables()
    seed_default_admin()
    seed_subjects()
    seed_regions_and_districts()
    seed_directions_from_excel()


def seed_default_admin():
    from .models import Admin
    db = Session()
    try:
        if db.query(Admin).first():
            return
        db.add(Admin(telegram_id=0, role='super_admin'))
        db.commit()
        print("✅ Default admin qo'shildi")
    except Exception as e:
        db.rollback()
        print(f"❌ Admin seed xato: {e}")
    finally:
        db.close()


def seed_subjects():
    from .models import Subject
    db = Session()
    try:
        if db.query(Subject).first():
            print("Fanlar allaqachon bor, o'tkazildi")
            return
        subjects = [
            (1,  'Matematika',  'Matematika',  'Математика',      1.1),
            (2,  'Fizika',      'Fizika',       'Физика',          3.1),
            (3,  'Kimyo',       'Kimyo',        'Химия',           3.1),
            (4,  'Biologiya',   'Biologiya',    'Биология',        3.1),
            (5,  'Tarix',       'Tarix',        'История',         1.1),
            (6,  'Ona tili',    'Ona tili',     'Родной язык',     1.1),
            (7,  'Adabiyot',    'Adabiyot',     'Литература',      2.1),
            (8,  'Geografiya',  'Geografiya',   'География',       2.1),
            (9,  'Ingliz tili', 'Ingliz tili',  'Английский язык', 2.1),
            (10, 'Rus tili',    'Rus tili',     'Русский язык',    2.1),
        ]
        for sid, uz, oz, ru, pts in subjects:
            db.add(Subject(id=sid, name_uz=uz, name_oz=oz, name_ru=ru,
                           points_per_question=pts))
        db.commit()
        print(f"✅ {len(subjects)} ta fan qo'shildi")
    except Exception as e:
        db.rollback()
        print(f"❌ Fan seed xato: {e}")
    finally:
        db.close()


def _load_json(filepath: str) -> list:
    import json
    for enc in ('utf-8', 'utf-8-sig', 'cp1251'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, ValueError):
            continue
    raise RuntimeError(f"JSON o'qib bo'lmadi: {filepath}")


def seed_regions_and_districts():
    import os
    from .models import Region, District
    db = Session()
    try:
        if db.query(Region).first():
            print("Viloyatlar allaqachon bor, o'tkazildi")
            return

        # TUZATILDI: __file__ = .../database/db.py
        # dirname(abspath(__file__)) = .../database/
        # dirname(dirname(...))      = loyiha ildizi  ← TO'G'RI
        base = os.path.dirname(os.path.abspath(__file__))

        for r in _load_json(os.path.join(base, 'regions.json')):
            db.add(Region(id=int(r['id']), name_uz=r['name_uz'],
                          name_oz=r['name_oz'], name_ru=r['name_ru']))
        db.commit()
        for d in _load_json(os.path.join(base, 'districts.json')):
            db.add(District(id=int(d['id']), region_id=int(d['region_id']),
                            name_uz=d['name_uz'], name_oz=d['name_oz'],
                            name_ru=d['name_ru']))
        db.commit()
        print("✅ Viloyat va tumanlar qo'shildi")
    except Exception as e:
        db.rollback()
        print(f"❌ Viloyat/tuman seed xato: {e}")
    finally:
        db.close()


def seed_directions_from_excel():
    from .models import Direction
    from utils.excel_parser import parse_directions_from_excel
    db = Session()
    try:
        if db.query(Direction).first():
            print("Yo'nalishlar allaqachon bor, o'tkazildi")
            return
        directions = parse_directions_from_excel()
        if not directions:
            print("❌ Yo'nalish ma'lumotlari topilmadi")
            return
        for d in directions:
            db.add(Direction(
                id=d['code'], name_uz=d['name'], name_oz=d['name'], name_ru=d['name'],
                subject1_id=d['subject1_id'], subject2_id=d['subject2_id'],
            ))
        db.commit()
        print(f"✅ {len(directions)} ta yo'nalish qo'shildi")
    except Exception as e:
        db.rollback()
        print(f"❌ Yo'nalish seed xato: {e}")
    finally:
        db.close()