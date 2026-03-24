#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               DTM Test Bot — Loyiha boshqaruv skripti                      ║
║               scripts/manage.py  (v2.0 — to'liq qayta yozildi)            ║
╚══════════════════════════════════════════════════════════════════════════════╝

ISHLATISH:
    python scripts/manage.py <buyruq> [opsiyalar]

BUYRUQLAR:
    check           — Konfiguratsiya va DB ulanishni tekshirish (BIRINCHI QADAM)
    init            — Yangi baza: jadvallar + barcha boshlang'ich ma'lumotlar
    migrate         — Mavjud bazaga yangi ustunlar/jadvallar qo'shish
    seed            — Savollarni qo'shish (--force bilan qayta)
    status          — Baza holati
    reset           — XAVFLI: bazani o'chirib qayta yaratish
    createsuperuser — Admin login/parolini .env ga yozish

YANGI SERVERGA KO'CHIRISH TARTIBI:
    1.  git clone / fayllarni nusxalash
    2.  pip install -r requirements.txt
    3.  .env faylini to'ldirish (env.example dan nusxa)
    4.  python scripts/manage.py check        # hamma narsa to'g'rimi?
    5.  python scripts/manage.py init         # jadvallar + seed
    6.  python scripts/manage.py seed         # savollar
    7.  python scripts/manage.py status       # natijani tekshirish
    8.  python -m bot.main                    # botni ishga tushirish
    9.  python -m admin.app                   # admin panelni ishga tushirish

MAVJUD BAZAGA YANGI KOD DEPLOY QILISH:
    1.  git pull
    2.  pip install -r requirements.txt
    3.  python scripts/manage.py migrate      # yangi jadvallar/ustunlar
    4.  bot va admin ni qayta ishga tushirish

MISOLLAR:
    python scripts/manage.py check
    python scripts/manage.py init
    python scripts/manage.py seed --force
    python scripts/manage.py status
    python scripts/manage.py createsuperuser
"""

import os
import sys
import random

# ─── Project root ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# CHECK
# ══════════════════════════════════════════════════════════════════════════════

def cmd_check():
    """Konfiguratsiya va ulanishlarni tekshirish."""
    print("\n🔍 Konfiguratsiya tekshiruvi...\n")
    ok = True

    # BOT_TOKEN
    tok = os.getenv("BOT_TOKEN", "")
    if tok and tok != "your_telegram_bot_token_here":
        print("  ✅ BOT_TOKEN")
    else:
        print("  ❌ BOT_TOKEN — .env da to'ldiring!")
        ok = False

    # DATABASE_URL
    dbu = os.getenv("DATABASE_URL", "")
    if dbu and "username" not in dbu and dbu != "":
        print(f"  ✅ DATABASE_URL — {dbu[:50]}...")
    else:
        print("  ❌ DATABASE_URL — .env da to'ldiring!")
        ok = False

    # SECRET_KEY
    sk = os.getenv("SECRET_KEY", "")
    bad_keys = ("your-secret-key-here", "change_this_to_random_secret_key_min32chars", "")
    if sk and sk not in bad_keys:
        print("  ✅ SECRET_KEY")
    else:
        import secrets as _s
        nk = _s.token_hex(32)
        print(f"  ⚠️  SECRET_KEY yo'q! .env ga qo'shing:")
        print(f"      SECRET_KEY={nk}")

    # Redis
    ru = os.getenv("REDIS_URL", "")
    if ru:
        try:
            import redis as _r
            _r.from_url(ru).ping()
            print(f"  ✅ Redis — ulanish muvaffaqiyatli")
        except Exception as e:
            print(f"  ⚠️  Redis ulanmadi: {e}")
            print("      MemoryStorage ishlatiladi (bot restart bo'lsa FSM o'chadi)")
    else:
        print("  ⚠️  REDIS_URL yo'q — MemoryStorage ishlatiladi")

    # DB ulanishi
    if dbu and "username" not in dbu:
        try:
            import config
            from database.db import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("  ✅ PostgreSQL ulanishi — muvaffaqiyatli")
        except Exception as e:
            print(f"  ❌ PostgreSQL ulanishi xato: {e}")
            ok = False

    # Excel
    ep = os.path.join(ROOT, "utils", "Fanlar_majmuasi_2025-2026.xlsx")
    if os.path.exists(ep):
        print(f"  ✅ Excel fayl — {os.path.getsize(ep)//1024} KB")
    else:
        print(f"  ⚠️  Excel fayl yo'q: data/Fanlar_majmuasi_2025-2026.xlsx")
        print("      5 ta fallback yo'nalish ishlatiladi")

    print()
    if ok:
        print("🎉 Konfiguratsiya to'g'ri! Keyingi qadam: python scripts/manage.py init\n")
    else:
        print("❌ Yuqoridagi muammolarni hal qiling.\n")
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# INIT
# ══════════════════════════════════════════════════════════════════════════════

def cmd_init():
    """Yangi baza: jadvallar + barcha boshlang'ich ma'lumotlar."""
    from database.db import init_db
    init_db()


# ══════════════════════════════════════════════════════════════════════════════
# RESET
# ══════════════════════════════════════════════════════════════════════════════

def cmd_reset():
    """XAVFLI: barcha ma'lumotlar o'chadi."""
    c = input("\n⚠️  BARCHA MA'LUMOTLAR O'CHADI! Davom etish uchun 'yes' yozing: ").strip()
    if c != "yes":
        print("Bekor qilindi.")
        return
    from database.db import drop_tables, init_db
    print("🗑  O'chirilmoqda...")
    drop_tables()
    print("🔧 Qayta yaratilmoqda...")
    init_db()


# ══════════════════════════════════════════════════════════════════════════════
# MIGRATE
# ══════════════════════════════════════════════════════════════════════════════

def cmd_migrate():
    """
    Mavjud bazaga yangi ustunlar va jadvallar.
    Ma'lumotlar saqlanib qoladi.
    """
    from sqlalchemy import text
    from database.db import Session, create_tables

    print("\n🔄 Migration boshlandi...\n")

    # 1. Yangi jadvallarni ORM orqali yaratish
    print("📋 Yangi jadvallar (agar yo'q bo'lsa yaratiladi)...")
    create_tables()

    db = Session()

    # 2. ALTER TABLE
    alters = [
        # scores
        ("scores.is_archived",
         "ALTER TABLE scores ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE"),
        ("scores.attempted_count",
         "ALTER TABLE scores ADD COLUMN IF NOT EXISTS attempted_count INTEGER DEFAULT 0"),
        ("scores.participation_id",
         "ALTER TABLE scores ADD COLUMN IF NOT EXISTS participation_id INTEGER"
         " REFERENCES user_test_participation(id) ON DELETE SET NULL"),
        # user_test_participation
        ("participation.started_at",
         "ALTER TABLE user_test_participation ADD COLUMN IF NOT EXISTS started_at TIMESTAMP"),
        ("participation.deadline_at",
         "ALTER TABLE user_test_participation ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMP"),
        ("participation.snapshot_questions",
         "ALTER TABLE user_test_participation ADD COLUMN IF NOT EXISTS snapshot_questions JSON"),
        ("participation.snapshot_current_index",
         "ALTER TABLE user_test_participation ADD COLUMN IF NOT EXISTS"
         " snapshot_current_index INTEGER DEFAULT 0"),
        ("participation.snapshot_answers",
         "ALTER TABLE user_test_participation ADD COLUMN IF NOT EXISTS snapshot_answers JSON"),
        # users
        ("users.is_blocked",
         "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"),
        ("users.language",
         "ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'uz'"),
        # leaderboard duplikatlarni tozalash
        ("leaderboard duplikatlar",
         """DELETE FROM leaderboard WHERE id NOT IN (
                SELECT MAX(id) FROM leaderboard GROUP BY user_id, direction_id, period
            )"""),
    ]

    print("\n🔧 ALTER TABLE buyruqlari:")
    for name, sql in alters:
        try:
            db.execute(text(sql))
            db.commit()
            print(f"  ✅ {name}")
        except Exception as e:
            db.rollback()
            msg = str(e).split("\n")[0]
            if "already exists" in msg.lower() or "duplicate" in msg.lower():
                print(f"  ⏭  {name} — allaqachon bor")
            else:
                print(f"  ⚠️  {name}: {msg}")

    # 3. Indekslar
    indexes = [
        ("idx_referral_links_user_id",
         "CREATE INDEX IF NOT EXISTS idx_referral_links_user_id ON referral_links(user_id)"),
        ("idx_referral_links_code",
         "CREATE INDEX IF NOT EXISTS idx_referral_links_code ON referral_links(code)"),
        ("idx_referral_invites_link_id",
         "CREATE INDEX IF NOT EXISTS idx_referral_invites_link_id ON referral_invites(referral_link_id)"),
        ("idx_referral_invites_invited",
         "CREATE INDEX IF NOT EXISTS idx_referral_invites_invited ON referral_invites(invited_user_id)"),
        ("idx_scores_user_id",
         "CREATE INDEX IF NOT EXISTS idx_scores_user_id ON scores(user_id)"),
        ("idx_scores_archived",
         "CREATE INDEX IF NOT EXISTS idx_scores_archived ON scores(is_archived)"),
        ("idx_utp_user_status",
         "CREATE INDEX IF NOT EXISTS idx_utp_user_status ON user_test_participation(user_id, status)"),
        ("idx_utp_deadline",
         "CREATE INDEX IF NOT EXISTS idx_utp_deadline ON user_test_participation(deadline_at)"),
        ("idx_users_telegram",
         "CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id)"),
        ("idx_lb_dir_period",
         "CREATE INDEX IF NOT EXISTS idx_lb_dir_period ON leaderboard(direction_id, period)"),
    ]

    print("\n📑 Indekslar:")
    for name, sql in indexes:
        try:
            db.execute(text(sql))
            db.commit()
            print(f"  ✅ {name}")
        except Exception as e:
            db.rollback()
            msg = str(e).split("\n")[0]
            if "already exists" in msg.lower():
                print(f"  ⏭  {name}")
            else:
                print(f"  ⚠️  {name}: {msg}")

    db.close()

    # 4. Seed (yo'q bo'lsa qo'shish)
    print("\n🌱 Boshlang'ich ma'lumotlar:")
    from database.db import (
        seed_admin, seed_subjects, seed_regions_and_districts,
        seed_directions, seed_referral_settings,
    )
    seed_admin()
    seed_subjects()
    seed_regions_and_districts()
    seed_directions()
    seed_referral_settings()

    print("\n🎉 Migration tugadi! Bot va admin panelni qayta ishga tushiring.\n")


# ══════════════════════════════════════════════════════════════════════════════
# SEED
# ══════════════════════════════════════════════════════════════════════════════

QUESTIONS_DATA = {
    1: [  # Matematika
        {"text_uz": "2 + 2 nechaga teng?", "option_a": "3", "option_b": "4", "option_c": "5", "option_d": "6", "correct_answer": "B"},
        {"text_uz": "Kvadratning perimetri P=16 sm. Tomoni a=?", "option_a": "2 sm", "option_b": "4 sm", "option_c": "8 sm", "option_d": "16 sm", "correct_answer": "B"},
        {"text_uz": "x² - 4x + 4 = 0 tenglamaning ildizi?", "option_a": "x=1", "option_b": "x=-2", "option_c": "x=2", "option_d": "x=4", "correct_answer": "C"},
        {"text_uz": "3² + 4² = ?", "option_a": "25", "option_b": "49", "option_c": "14", "option_d": "7", "correct_answer": "A"},
        {"text_uz": "log₁₀(100) = ?", "option_a": "1", "option_b": "2", "option_c": "10", "option_d": "20", "correct_answer": "B"},
        {"text_uz": "sin(90°) = ?", "option_a": "0", "option_b": "0.5", "option_c": "1", "option_d": "-1", "correct_answer": "C"},
        {"text_uz": "cos(0°) = ?", "option_a": "0", "option_b": "1", "option_c": "-1", "option_d": "0.5", "correct_answer": "B"},
        {"text_uz": "√144 = ?", "option_a": "11", "option_b": "12", "option_c": "13", "option_d": "14", "correct_answer": "B"},
        {"text_uz": "2^10 = ?", "option_a": "512", "option_b": "1000", "option_c": "1024", "option_d": "2048", "correct_answer": "C"},
        {"text_uz": "5! = ?", "option_a": "60", "option_b": "100", "option_c": "120", "option_d": "125", "correct_answer": "C"},
        {"text_uz": "tan(45°) = ?", "option_a": "0", "option_b": "0.5", "option_c": "1", "option_d": "√2", "correct_answer": "C"},
        {"text_uz": "(-3)² = ?", "option_a": "-9", "option_b": "-6", "option_c": "6", "option_d": "9", "correct_answer": "D"},
        {"text_uz": "EKUB(12,18)=?", "option_a": "2", "option_b": "3", "option_c": "6", "option_d": "36", "correct_answer": "C"},
        {"text_uz": "EKUK(4,6)=?", "option_a": "2", "option_b": "12", "option_c": "24", "option_d": "6", "correct_answer": "B"},
        {"text_uz": "Agar x+y=10, x-y=4 bo'lsa, x=?", "option_a": "3", "option_b": "5", "option_c": "7", "option_d": "9", "correct_answer": "C"},
        {"text_uz": "1/2 + 1/3 = ?", "option_a": "2/5", "option_b": "1/6", "option_c": "5/6", "option_d": "2/6", "correct_answer": "C"},
        {"text_uz": "C(5,2)=?", "option_a": "5", "option_b": "10", "option_c": "15", "option_d": "20", "correct_answer": "B"},
        {"text_uz": "lg(1000)=?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "10", "correct_answer": "B"},
        {"text_uz": "Agar f(x)=2x+1 bo'lsa, f(3)=?", "option_a": "5", "option_b": "6", "option_c": "7", "option_d": "8", "correct_answer": "C"},
        {"text_uz": "sin²x + cos²x = ?", "option_a": "0", "option_b": "1", "option_c": "2", "option_d": "sin(2x)", "correct_answer": "B"},
        {"text_uz": "Doira yuzi S=? (r=5)", "option_a": "10π", "option_b": "25π", "option_c": "5π", "option_d": "50π", "correct_answer": "B"},
        {"text_uz": "Arifmetik progressiyada a₁=2, d=3 bo'lsa, a₅=?", "option_a": "10", "option_b": "12", "option_c": "14", "option_d": "17", "correct_answer": "C"},
        {"text_uz": "Uchburchak tomonlari 3,4,5 — bu qanday uchburchak?", "option_a": "O'tkir", "option_b": "To'g'ri", "option_c": "O'tmas", "option_d": "Teng yonli", "correct_answer": "B"},
        {"text_uz": "Geometrik progressiya: 2,6,18... 4-had=?", "option_a": "36", "option_b": "54", "option_c": "72", "option_d": "108", "correct_answer": "B"},
        {"text_uz": "Silindr hajmi V=? (r=3, h=5)", "option_a": "15π", "option_b": "30π", "option_c": "45π", "option_d": "90π", "correct_answer": "C"},
        {"text_uz": "Parallelogramm yuzi S=? (a=6, h=4)", "option_a": "10", "option_b": "20", "option_c": "24", "option_d": "48", "correct_answer": "C"},
        {"text_uz": "Diskriminant D=b²-4ac. a=1,b=2,c=1 bo'lsa D=?", "option_a": "-4", "option_b": "0", "option_c": "4", "option_d": "8", "correct_answer": "B"},
        {"text_uz": "15!/14!=?", "option_a": "1", "option_b": "14", "option_c": "15", "option_d": "16", "correct_answer": "C"},
        {"text_uz": "Agar a=3,b=4 bo'lsa, a²+b²=?", "option_a": "7", "option_b": "14", "option_c": "25", "option_d": "49", "correct_answer": "C"},
        {"text_uz": "0.1 + 0.2 = ?", "option_a": "0.12", "option_b": "0.3", "option_c": "0.21", "option_d": "0.02", "correct_answer": "B"},
    ],
    2: [{"text_uz": "Erkin tushish tezlanishi g=?", "option_a": "8.9 m/s²", "option_b": "9.8 m/s²", "option_c": "10.8 m/s²", "option_d": "11 m/s²", "correct_answer": "B"},
        {"text_uz": "Kuch birligi SI da?", "option_a": "Joule", "option_b": "Vatt", "option_c": "Newton", "option_d": "Pascal", "correct_answer": "C"},
        {"text_uz": "Ish formulasi W=?", "option_a": "m·a", "option_b": "F·v", "option_c": "F·s·cosα", "option_d": "m·v²", "correct_answer": "C"},
        {"text_uz": "Yorug'lik tezligi vakuumda?", "option_a": "3·10⁶ m/s", "option_b": "3·10⁸ m/s", "option_c": "3·10¹⁰ m/s", "option_d": "3·10⁴ m/s", "correct_answer": "B"},
        {"text_uz": "Kinetik energiya formulasi?", "option_a": "mgh", "option_b": "mv", "option_c": "mv²/2", "option_d": "ma", "correct_answer": "C"},
        {"text_uz": "Potensial energiya E=?", "option_a": "mv²/2", "option_b": "mgh", "option_c": "Fs", "option_d": "ma²", "correct_answer": "B"},
        {"text_uz": "Ohm qonuni: I=?", "option_a": "U·R", "option_b": "U/R", "option_c": "R/U", "option_d": "U+R", "correct_answer": "B"},
        {"text_uz": "Issiqlik miqdori Q=?", "option_a": "mc·ΔT", "option_b": "mv·ΔT", "option_c": "mg·h", "option_d": "F·s", "correct_answer": "A"},
        {"text_uz": "Tovush tezligi havoda taxminan?", "option_a": "34 m/s", "option_b": "340 m/s", "option_c": "3400 m/s", "option_d": "34000 m/s", "correct_answer": "B"},
        {"text_uz": "Nyuton 2-qonuni: F=?", "option_a": "m/a", "option_b": "m+a", "option_c": "m·a", "option_d": "m·v", "correct_answer": "C"},
        {"text_uz": "Bosim P=?", "option_a": "F·S", "option_b": "F/S", "option_c": "S/F", "option_d": "F+S", "correct_answer": "B"},
        {"text_uz": "Absolyut nol temperatura?", "option_a": "-100°C", "option_b": "-200°C", "option_c": "-273°C", "option_d": "-373°C", "correct_answer": "C"},
        {"text_uz": "Impuls p=?", "option_a": "m/v", "option_b": "m·v", "option_c": "m·a", "option_d": "F·t", "correct_answer": "B"},
        {"text_uz": "Mayatnik davri T=?", "option_a": "2π√(l/g)", "option_b": "2π√(g/l)", "option_c": "π√(l/g)", "option_d": "2l/g", "correct_answer": "A"},
        {"text_uz": "Foton energiyasi E=?", "option_a": "hν", "option_b": "mc²", "option_c": "mv²/2", "option_d": "hλ", "correct_answer": "A"},
        {"text_uz": "Gaz bosimi (T=const): P₁V₁=?", "option_a": "P₂+V₂", "option_b": "P₂V₂", "option_c": "P₂/V₂", "option_d": "P₂·T₂", "correct_answer": "B"},
        {"text_uz": "Elektr sig'im birligi?", "option_a": "Genri", "option_b": "Veber", "option_c": "Farad", "option_d": "Tesla", "correct_answer": "C"},
        {"text_uz": "Mexanik to'lqin tarqalishi uchun?", "option_a": "Vakuum", "option_b": "Modda", "option_c": "Magnit maydon", "option_d": "Yorug'lik", "correct_answer": "B"},
        {"text_uz": "Nyuton 3-qonuni nimani ta'riflaydi?", "option_a": "Inersiya", "option_b": "Tezlanish", "option_c": "Ta'sir va aks ta'sir", "option_d": "Tortishish", "correct_answer": "C"},
        {"text_uz": "Massa birligi SI da?", "option_a": "Gramm", "option_b": "Kilogramm", "option_c": "Tonna", "option_d": "Milligramm", "correct_answer": "B"},
        {"text_uz": "Arximed kuchi?", "option_a": "Suyuqlik og'irligiga", "option_b": "Siqib chiqarilgan suyuqlik og'irligiga", "option_c": "Jism og'irligiga", "option_d": "Jism massasiga", "correct_answer": "B"},
        {"text_uz": "Elektr zaryad birligi?", "option_a": "Volt", "option_b": "Amper", "option_c": "Kulon", "option_d": "Farad", "correct_answer": "C"},
        {"text_uz": "Diffraktsiya nima?", "option_a": "To'lqin sinishi", "option_b": "To'lqin egilishi", "option_c": "To'lqin qaytishi", "option_d": "To'lqin kuchayishi", "correct_answer": "B"},
        {"text_uz": "Termodinamika 1-qonuni?", "option_a": "Entropiya ortishi", "option_b": "Energiya saqlanishi", "option_c": "Absolyut nol", "option_d": "Issiqlik o'tkazuvchanlik", "correct_answer": "B"},
        {"text_uz": "Yer tortishishi qanday kuch?", "option_a": "Mexanik", "option_b": "Elektromagnit", "option_c": "Gravitatsiya", "option_d": "Yadro", "correct_answer": "C"},
        {"text_uz": "Elektr quvvati birligi?", "option_a": "Amper", "option_b": "Volt", "option_c": "Vatt", "option_d": "Om", "correct_answer": "C"},
        {"text_uz": "Faradey qonuni?", "option_a": "Tok kuchini", "option_b": "EMK ni", "option_c": "Zaryad miqdorini", "option_d": "Quvvatni", "correct_answer": "B"},
        {"text_uz": "Radioaktivlik misoli?", "option_a": "Yorug'lik sinishi", "option_b": "Elektroliz", "option_c": "Yadro reaksiyasi", "option_d": "Magnit induksiyasi", "correct_answer": "C"},
        {"text_uz": "Elektromagnit to'lqin nima tarqatadi?", "option_a": "Faqat elektr maydon", "option_b": "Faqat magnit maydon", "option_c": "Elektr va magnit maydon", "option_d": "Zarrachalar", "correct_answer": "C"},
        {"text_uz": "Nurlanish xarakteristikasi?", "option_a": "Faqat gaz", "option_b": "Faqat qattiq jism", "option_c": "Barcha isitilgan jismlar", "option_d": "Faqat suyuqlik", "correct_answer": "C"},
    ],
    3: [{"text_uz": "Suvning kimyoviy formulasi?", "option_a": "H2", "option_b": "O2", "option_c": "H2O", "option_d": "CO2", "correct_answer": "C"},
        {"text_uz": "pH=7 bo'lgan eritma?", "option_a": "Kislotali", "option_b": "Asosli", "option_c": "Neytral", "option_d": "Tuzli", "correct_answer": "C"},
        {"text_uz": "Natriy belgisi?", "option_a": "K", "option_b": "Na", "option_c": "N", "option_d": "Ni", "correct_answer": "B"},
        {"text_uz": "NaCl nima?", "option_a": "Osh tuzi", "option_b": "Soda", "option_c": "Ohak", "option_d": "Mis sulfat", "correct_answer": "A"},
        {"text_uz": "Davriy sistemani kim yaratgan?", "option_a": "Lavuazye", "option_b": "Darvin", "option_c": "Mendeleyev", "option_d": "Nyuton", "correct_answer": "C"},
        {"text_uz": "H₂SO₄ qanday kislota?", "option_a": "Xlorid", "option_b": "Sulfat", "option_c": "Azot", "option_d": "Karbonat", "correct_answer": "B"},
        {"text_uz": "NaOH dissotsilanishida?", "option_a": "H⁺ ionlar", "option_b": "Na⁺ va OH⁻", "option_c": "O²⁻", "option_d": "Na va O", "correct_answer": "B"},
        {"text_uz": "Organik kimyo asosi?", "option_a": "Azot", "option_b": "Kislorod", "option_c": "Uglerod", "option_d": "Vodorod", "correct_answer": "C"},
        {"text_uz": "Metan formulasi?", "option_a": "C₂H₆", "option_b": "CH₄", "option_c": "C₃H₈", "option_d": "C₂H₄", "correct_answer": "B"},
        {"text_uz": "Oksidlanishda elektron?", "option_a": "Qo'shiladi", "option_b": "Yo'qoladi", "option_c": "O'zgarmaydi", "option_d": "Ko'payadi", "correct_answer": "B"},
        {"text_uz": "Ca(OH)₂ nima?", "option_a": "Ohak suvi", "option_b": "Soda", "option_c": "Mis vitriol", "option_d": "KMnO4", "correct_answer": "A"},
        {"text_uz": "Vodorod atomi protoni?", "option_a": "0", "option_b": "1", "option_c": "2", "option_d": "3", "correct_answer": "B"},
        {"text_uz": "Mis belgisi?", "option_a": "Co", "option_b": "Cr", "option_c": "Cu", "option_d": "Ca", "correct_answer": "C"},
        {"text_uz": "CO₂ qanday oksid?", "option_a": "Asosli", "option_b": "Kislotali", "option_c": "Amfoter", "option_d": "Neytral", "correct_answer": "B"},
        {"text_uz": "Etanol formulasi?", "option_a": "CH₃OH", "option_b": "C₂H₅OH", "option_c": "C₃H₇OH", "option_d": "C₄H₉OH", "correct_answer": "B"},
        {"text_uz": "Benzol formulasi?", "option_a": "C₅H₁₀", "option_b": "C₆H₁₂", "option_c": "C₆H₆", "option_d": "C₄H₈", "correct_answer": "C"},
        {"text_uz": "Mol nima?", "option_a": "Massa birligi", "option_b": "6.02·10²³ ta zarracha", "option_c": "Hajm birligi", "option_d": "Zichlik birligi", "correct_answer": "B"},
        {"text_uz": "Kumush belgisi?", "option_a": "Si", "option_b": "Sb", "option_c": "Ag", "option_d": "Au", "correct_answer": "C"},
        {"text_uz": "Alkanlar formulasi?", "option_a": "CₙH₂ₙ", "option_b": "CₙH₂ₙ₊₂", "option_c": "CₙH₂ₙ₋₂", "option_d": "CₙHₙ", "correct_answer": "B"},
        {"text_uz": "Alkenlar formulasi?", "option_a": "CₙH₂ₙ₊₂", "option_b": "CₙH₂ₙ", "option_c": "CₙH₂ₙ₋₂", "option_d": "CₙHₙ", "correct_answer": "B"},
        {"text_uz": "Kislota+asos = ?", "option_a": "Oksidlanish", "option_b": "Neytrallash", "option_c": "Parchalanish", "option_d": "Birikish", "correct_answer": "B"},
        {"text_uz": "Temir belgisi?", "option_a": "Te", "option_b": "Ti", "option_c": "Fe", "option_d": "Fo", "correct_answer": "C"},
        {"text_uz": "Ammoniyak formulasi?", "option_a": "NO₂", "option_b": "N₂O", "option_c": "NH₃", "option_d": "N₂H₄", "correct_answer": "C"},
        {"text_uz": "Elektroliz nima?", "option_a": "Issiqlik ta'sirida", "option_b": "Elektr toki ta'sirida", "option_c": "Yorug'lik ta'sirida", "option_d": "Bosim ostida", "correct_answer": "B"},
        {"text_uz": "O₂ qanday modda?", "option_a": "Birikma", "option_b": "Aralashma", "option_c": "Oddiy modda", "option_d": "Tuz", "correct_answer": "C"},
        {"text_uz": "Egzotermik reaksiyada?", "option_a": "Issiqlik yutiladi", "option_b": "Issiqlik ajraladi", "option_c": "Massa o'zgaradi", "option_d": "Rang o'zgaradi", "correct_answer": "B"},
        {"text_uz": "Kremniy belgisi?", "option_a": "Cr", "option_b": "Si", "option_c": "Sn", "option_d": "Sr", "correct_answer": "B"},
        {"text_uz": "Uglerod valentligi?", "option_a": "Faqat 2", "option_b": "Faqat 4", "option_c": "2 yoki 4", "option_d": "1,2,3,4", "correct_answer": "C"},
        {"text_uz": "Kislota+asos mahsuloti?", "option_a": "Tuz va suv", "option_b": "Oksid va suv", "option_c": "Kislota va asos", "option_d": "Faqat tuz", "correct_answer": "A"},
        {"text_uz": "Qaytarilishda elektron?", "option_a": "Yo'qoladi", "option_b": "Qo'shiladi", "option_c": "O'zgarmaydi", "option_d": "Kamayadi", "correct_answer": "B"},
    ],
    4: [{"text_uz": "Fotosintez qaysi organoidda?", "option_a": "Yadro", "option_b": "Mitoxondriya", "option_c": "Xloroplast", "option_d": "Lizosoma", "correct_answer": "C"},
        {"text_uz": "DNK nimani kodlaydi?", "option_a": "Yog'larni", "option_b": "Uglevodlarni", "option_c": "Oqsillarni", "option_d": "Vitaminlarni", "correct_answer": "C"},
        {"text_uz": "Odam qon guruhlari?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_answer": "C"},
        {"text_uz": "ATP nima?", "option_a": "Oqsil", "option_b": "Yog'", "option_c": "Energiya tashuvchi molekula", "option_d": "Ferment", "correct_answer": "C"},
        {"text_uz": "Mitoz necha bosqich?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_answer": "C"},
        {"text_uz": "Hujayraning energiya stantsiyasi?", "option_a": "Ribosoma", "option_b": "Lizosoma", "option_c": "Mitoxondriya", "option_d": "Vakuola", "correct_answer": "C"},
        {"text_uz": "Odamda juft xromosomalar?", "option_a": "21", "option_b": "22", "option_c": "23", "option_d": "24", "correct_answer": "C"},
        {"text_uz": "Fotosintezda nima hosil?", "option_a": "CO₂ va H₂O", "option_b": "O₂ va glyukoza", "option_c": "N₂ va ATP", "option_d": "H₂ va O₂", "correct_answer": "B"},
        {"text_uz": "Irsiyat qonunlari?", "option_a": "Darvin", "option_b": "Mendel", "option_c": "Lamark", "option_d": "Kox", "correct_answer": "B"},
        {"text_uz": "RNK vazifasi?", "option_a": "Irsiy ma'lumot saqlash", "option_b": "Oqsil sintezi", "option_c": "Energiya olish", "option_d": "Yog' sintezi", "correct_answer": "B"},
        {"text_uz": "Inson yuragida kameralar?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_answer": "C"},
        {"text_uz": "Kraxmal ferment?", "option_a": "Pepsin", "option_b": "Lipaza", "option_c": "Amilaza", "option_d": "Tripsin", "correct_answer": "C"},
        {"text_uz": "Neyron nima?", "option_a": "Qon hujayra", "option_b": "Asab hujayra", "option_c": "Muskul hujayra", "option_d": "Suyak hujayra", "correct_answer": "B"},
        {"text_uz": "Siydik hosil bo'lish?", "option_a": "Jigar", "option_b": "Taloq", "option_c": "Buyrak", "option_d": "O't pufagi", "correct_answer": "C"},
        {"text_uz": "D vitamini?", "option_a": "Temir so'rilishi", "option_b": "Kalsiy so'rilishi", "option_c": "Yod so'rilishi", "option_d": "Magniy so'rilishi", "correct_answer": "B"},
        {"text_uz": "Meyoz natijasi?", "option_a": "2", "option_b": "4", "option_c": "8", "option_d": "16", "correct_answer": "B"},
        {"text_uz": "Immunitet nima?", "option_a": "Kasallik", "option_b": "Himoya tizimi", "option_c": "Gormon", "option_d": "Ferment", "correct_answer": "B"},
        {"text_uz": "O'simlik hujayrasida yo'q?", "option_a": "Mitoxondriya", "option_b": "Ribosoma", "option_c": "Xloroplast", "option_d": "Yadro", "correct_answer": "C"},
        {"text_uz": "Evolyutsiya nazariyasi?", "option_a": "Mendel", "option_b": "Darvin", "option_c": "Pastyur", "option_d": "Linney", "correct_answer": "B"},
        {"text_uz": "Nafas olishda iste'mol?", "option_a": "CO₂", "option_b": "N₂", "option_c": "O₂", "option_d": "H₂", "correct_answer": "C"},
        {"text_uz": "Hazm boshlanishi?", "option_a": "Oshqozon", "option_b": "O'n ikki barmoq ichak", "option_c": "Og'iz bo'shlig'i", "option_d": "Qizil o'ngach", "correct_answer": "C"},
        {"text_uz": "Prokariot organizmlar?", "option_a": "O'simliklar", "option_b": "Hayvonlar", "option_c": "Bakteriyalar", "option_d": "Zamburug'lar", "correct_answer": "C"},
        {"text_uz": "Insulin?", "option_a": "Jigar", "option_b": "Buyrak", "option_c": "Oshqozon osti bezi", "option_d": "Taloq", "correct_answer": "C"},
        {"text_uz": "Ko'z to'r pardasi?", "option_a": "Tayoqcha va kolba", "option_b": "Neyron va glia", "option_c": "Epiteliy va muskul", "option_d": "Pigment va shaffof", "correct_answer": "A"},
        {"text_uz": "Juft qovurg'alar?", "option_a": "10", "option_b": "12", "option_c": "14", "option_d": "16", "correct_answer": "B"},
        {"text_uz": "Virus tarkibi?", "option_a": "Hujayra va DNK", "option_b": "Faqat oqsil", "option_c": "Nuklein kislota va oqsil", "option_d": "Hujayra membranasi", "correct_answer": "C"},
        {"text_uz": "Qon plazmasining asosiy komponenti?", "option_a": "Eritrositlar", "option_b": "Oqsil", "option_c": "Suv", "option_d": "Tuz", "correct_answer": "C"},
        {"text_uz": "Qon tarkibiga kirmaydigan?", "option_a": "Eritrositlar", "option_b": "Leykositlar", "option_c": "Trombositlar", "option_d": "Neyronlar", "correct_answer": "D"},
        {"text_uz": "Sut emizuvchilarda miya?", "option_a": "Ha, eng rivojlangan", "option_b": "Yo'q", "option_c": "Baliqlarda", "option_d": "Hasharotlarda", "correct_answer": "A"},
        {"text_uz": "O'simlik suv-tuz qabul qilish?", "option_a": "Barg", "option_b": "Poya", "option_c": "Ildiz", "option_d": "Gul", "correct_answer": "C"},
    ],
    5: [{"text_uz": "O'zbekiston mustaqilligi?", "option_a": "1990", "option_b": "1991", "option_c": "1992", "option_d": "1993", "correct_answer": "B"},
        {"text_uz": "Amir Temur vafoti?", "option_a": "1404", "option_b": "1405", "option_c": "1406", "option_d": "1407", "correct_answer": "B"},
        {"text_uz": "1-Jahon urushi?", "option_a": "1912", "option_b": "1913", "option_c": "1914", "option_d": "1915", "correct_answer": "C"},
        {"text_uz": "2-Jahon urushi tugashi?", "option_a": "1944", "option_b": "1945", "option_c": "1946", "option_d": "1947", "correct_answer": "B"},
        {"text_uz": "O'zbekiston birinchi Prezidenti?", "option_a": "Sh.Mirziyoyev", "option_b": "I.Karimov", "option_c": "A.Mutalov", "option_d": "R.Nishonov", "correct_answer": "B"},
        {"text_uz": "Buyuk Ipak yo'li?", "option_a": "M.av. I asr", "option_b": "M.av. II asr", "option_c": "Milodiy I asr", "option_d": "Milodiy II asr", "correct_answer": "B"},
        {"text_uz": "Al-Xorazmiy kim?", "option_a": "Shoir", "option_b": "Matematik va astronom", "option_c": "Sarkarda", "option_d": "Arxitektor", "correct_answer": "B"},
        {"text_uz": "Ibn Sino asari?", "option_a": "Kitob al-Qonun", "option_b": "Avesto", "option_c": "Temurnoma", "option_d": "Boburnoma", "correct_answer": "A"},
        {"text_uz": "Fransiya inqilobi?", "option_a": "1776", "option_b": "1789", "option_c": "1812", "option_d": "1848", "correct_answer": "B"},
        {"text_uz": "Amerika mustaqillik?", "option_a": "1775", "option_b": "1776", "option_c": "1777", "option_d": "1778", "correct_answer": "B"},
        {"text_uz": "Rus inqilobi?", "option_a": "1915", "option_b": "1916", "option_c": "1917", "option_d": "1918", "correct_answer": "C"},
        {"text_uz": "Berlin devori qurilishi?", "option_a": "1959", "option_b": "1961", "option_c": "1963", "option_d": "1965", "correct_answer": "B"},
        {"text_uz": "Berlin devori qulatilishi?", "option_a": "1987", "option_b": "1988", "option_c": "1989", "option_d": "1990", "correct_answer": "C"},
        {"text_uz": "Ulug'bek rasadxonasi?", "option_a": "1420s", "option_b": "1450s", "option_c": "1400s", "option_d": "1380s", "correct_answer": "A"},
        {"text_uz": "G'arbiy Rim qulab tushishi?", "option_a": "375", "option_b": "410", "option_c": "476", "option_d": "527", "correct_answer": "C"},
        {"text_uz": "Temuriylar barham topishi?", "option_a": "1500", "option_b": "1507", "option_c": "1510", "option_d": "1526", "correct_answer": "B"},
        {"text_uz": "Bobur Hindistonida?", "option_a": "Temuriylar", "option_b": "Safaviylar", "option_c": "Boburiylar", "option_d": "Shayboniylar", "correct_answer": "C"},
        {"text_uz": "O'zbekiston SSR?", "option_a": "1922", "option_b": "1924", "option_c": "1925", "option_d": "1936", "correct_answer": "B"},
        {"text_uz": "2-Jahon urushi boshlanishi?", "option_a": "1937", "option_b": "1938", "option_c": "1939", "option_d": "1940", "correct_answer": "C"},
        {"text_uz": "BMT tashkil topishi?", "option_a": "1944", "option_b": "1945", "option_c": "1946", "option_d": "1947", "correct_answer": "B"},
        {"text_uz": "Sovuq urush?", "option_a": "1944", "option_b": "1945", "option_c": "1947", "option_d": "1950", "correct_answer": "C"},
        {"text_uz": "MDH tashkil?", "option_a": "1990", "option_b": "1991", "option_c": "1992", "option_d": "1993", "correct_answer": "B"},
        {"text_uz": "Avesto kitobi?", "option_a": "Arablar", "option_b": "Turklar", "option_c": "Forslar va zardushtiylar", "option_d": "Hindlar", "correct_answer": "C"},
        {"text_uz": "Ulug'bekni o'ldirgan?", "option_a": "Ko'chmanchilar", "option_b": "O'g'li Abdullatif", "option_c": "Dushman", "option_d": "Saroy", "correct_answer": "B"},
        {"text_uz": "Samarqand Temur poytaxti?", "option_a": "1370", "option_b": "1380", "option_c": "1390", "option_d": "1400", "correct_answer": "A"},
        {"text_uz": "Xiva xonligi?", "option_a": "XVI asr boshi", "option_b": "XV asr oxiri", "option_c": "XVII asr boshi", "option_d": "XVIII asr", "correct_answer": "A"},
        {"text_uz": "Qo'qon xonligi?", "option_a": "XVII asr", "option_b": "XVIII asr boshi", "option_c": "XVIII asr o'rtasi", "option_d": "XIX asr boshi", "correct_answer": "B"},
        {"text_uz": "Rossiya O'rta Osiyoni bosib olishi?", "option_a": "1868", "option_b": "1876", "option_c": "1885", "option_d": "1895", "correct_answer": "C"},
        {"text_uz": "Jadidchilik paydo bo'lishi?", "option_a": "XIX asr boshi", "option_b": "XIX asr o'rtasi", "option_c": "XIX asr oxiri", "option_d": "XX asr boshi", "correct_answer": "C"},
        {"text_uz": "O'rta asr Yevropa?", "option_a": "V-XV asrlar", "option_b": "I-V asrlar", "option_c": "XV-XVIII asrlar", "option_d": "III-VIII asrlar", "correct_answer": "A"},
    ],
    6: [{"text_uz": "'Kitob' qaysi so'z turkumi?", "option_a": "Fe'l", "option_b": "Ot", "option_c": "Sifat", "option_d": "Ravish", "correct_answer": "B"},
        {"text_uz": "'Yozmoq' qaysi so'z turkumi?", "option_a": "Ot", "option_b": "Sifat", "option_c": "Fe'l", "option_d": "Ravish", "correct_answer": "C"},
        {"text_uz": "Ega — gapning qaysi bo'lagi?", "option_a": "Ikkinchi darajali", "option_b": "Bosh bo'lak", "option_c": "To'ldiruvchi", "option_d": "Aniqlovchi", "correct_answer": "B"},
        {"text_uz": "Kesim — gapning qaysi bo'lagi?", "option_a": "Ikkinchi darajali", "option_b": "Aniqlovchi", "option_c": "Bosh bo'lak", "option_d": "To'ldiruvchi", "correct_answer": "C"},
        {"text_uz": "O'zbek lotin alifbosi?", "option_a": "26", "option_b": "28", "option_c": "29", "option_d": "32", "correct_answer": "C"},
        {"text_uz": "'Qizil' qaysi so'z turkumi?", "option_a": "Ot", "option_b": "Sifat", "option_c": "Fe'l", "option_d": "Ravish", "correct_answer": "B"},
        {"text_uz": "Son nima bildiradi?", "option_a": "Harakat", "option_b": "Belgi", "option_c": "Miqdor yoki tartib", "option_d": "Predmet", "correct_answer": "C"},
        {"text_uz": "Olmosh nima?", "option_a": "Harakatni bildiradi", "option_b": "Boshqa so'zlarni almashtiradi", "option_c": "Belgini bildiradi", "option_d": "Miqdorni bildiradi", "correct_answer": "B"},
        {"text_uz": "Ko'makchi so'z turkumi?", "option_a": "Mustaqil", "option_b": "Yordamchi", "option_c": "Undov", "option_d": "Modal", "correct_answer": "B"},
        {"text_uz": "Bog'lovchi so'z turkumi?", "option_a": "Mustaqil", "option_b": "Undov", "option_c": "Yordamchi", "option_d": "Taqlid", "correct_answer": "C"},
        {"text_uz": "Antonim so'zlar?", "option_a": "Ma'nodosh", "option_b": "Qarama-qarshi ma'noli", "option_c": "Ko'p ma'noli", "option_d": "Shakldosh", "correct_answer": "B"},
        {"text_uz": "Sinonim so'zlar?", "option_a": "Qarama-qarshi", "option_b": "Ma'nodosh", "option_c": "Shakldosh", "option_d": "Ko'p ma'noli", "correct_answer": "B"},
        {"text_uz": "Omonim so'zlar?", "option_a": "Ma'nodosh", "option_b": "Qarama-qarshi", "option_c": "Bir xil yoziladigan, turli ma'noli", "option_d": "Ko'p ma'noli", "correct_answer": "C"},
        {"text_uz": "To'ldiruvchi savollar?", "option_a": "Qanday?", "option_b": "Kimning?", "option_c": "Kimga? Kimni?", "option_d": "Qayer?", "correct_answer": "C"},
        {"text_uz": "Aniqlovchi savollar?", "option_a": "Kimga?", "option_b": "Qanday? Qaysi?", "option_c": "Qaerga?", "option_d": "Kim?", "correct_answer": "B"},
        {"text_uz": "Nutq uslublari soni?", "option_a": "3", "option_b": "4", "option_c": "5", "option_d": "6", "correct_answer": "C"},
        {"text_uz": "Badiiy uslub xususiyati?", "option_a": "Rasmiylik", "option_b": "Ilmiylik", "option_c": "Ta'sirchanlik va obrazlilik", "option_d": "Soddalik", "correct_answer": "C"},
        {"text_uz": "Frazeologizm nima?", "option_a": "Bitta so'z", "option_b": "Barqaror so'z birikmasi", "option_c": "Gap turi", "option_d": "Qo'shimcha", "correct_answer": "B"},
        {"text_uz": "Metafora nima?", "option_a": "Tashbeh", "option_b": "Ko'chma ma'noli ta'bir", "option_c": "Takror", "option_d": "Mubolag'a", "correct_answer": "B"},
        {"text_uz": "Epitet nima?", "option_a": "Harakat so'z", "option_b": "Badiiy sifatlash", "option_c": "Qarama-qarshilik", "option_d": "So'z o'yini", "correct_answer": "B"},
        {"text_uz": "O'zbek tilida unli tovushlar?", "option_a": "5", "option_b": "6", "option_c": "7", "option_d": "8", "correct_answer": "B"},
        {"text_uz": "Undov so'z?", "option_a": "Lekin", "option_b": "Va", "option_c": "Oh!", "option_d": "Ham", "correct_answer": "C"},
        {"text_uz": "Affix nima?", "option_a": "So'z o'zagi", "option_b": "So'z yasovchi qo'shimcha", "option_c": "So'z boshi", "option_d": "Gap bo'lagi", "correct_answer": "B"},
        {"text_uz": "Qo'shma gap?", "option_a": "Bir ega kesimli", "option_b": "Ikki yoki ko'p sodda gapdan", "option_c": "So'roq gap", "option_d": "Buyruq gapi", "correct_answer": "B"},
        {"text_uz": "Undov gap?", "option_a": "So'roq", "option_b": "His-hayajon", "option_c": "Buyruq", "option_d": "Xabar", "correct_answer": "B"},
        {"text_uz": "'Kitoblar' da nechta morfema?", "option_a": "1", "option_b": "2", "option_c": "3", "option_d": "4", "correct_answer": "B"},
        {"text_uz": "Hol savollar?", "option_a": "Kim? Nima?", "option_b": "Qanday?", "option_c": "Qayer? Qachon?", "option_d": "Kimning?", "correct_answer": "C"},
        {"text_uz": "Ravish nima bildiradi?", "option_a": "Predmet", "option_b": "Belgi", "option_c": "Miqdor", "option_d": "Harakat belgisi", "correct_answer": "D"},
        {"text_uz": "Ilmiy uslub qayerda?", "option_a": "Adabiy asarlarda", "option_b": "Ilmiy maqolalarda", "option_c": "Kundalik muloqotda", "option_d": "Rasmiy hujjatlarda", "correct_answer": "B"},
        {"text_uz": "Mubolag'a nima?", "option_a": "O'xshatish", "option_b": "Bo'rttirib ko'rsatish", "option_c": "Kamaytirib ko'rsatish", "option_d": "Sifatlash", "correct_answer": "B"},
    ],
    7: [{"text_uz": "Navoiy qaysi asr shoiri?", "option_a": "14-asr", "option_b": "15-asr", "option_c": "16-asr", "option_d": "17-asr", "correct_answer": "B"},
        {"text_uz": "'Layli va Majnun' muallifi?", "option_a": "Navoiy", "option_b": "Qodiriy", "option_c": "Cho'lpon", "option_d": "Hamza", "correct_answer": "A"},
        {"text_uz": "Navoiy taxallusi?", "option_a": "Nizomiy", "option_b": "Husayn Boyqaro", "option_c": "Foniy", "option_d": "Bedil", "correct_answer": "C"},
        {"text_uz": "'O'tkan kunlar' muallifi?", "option_a": "Cho'lpon", "option_b": "Hamza", "option_c": "Abdulla Qodiriy", "option_d": "Fitrat", "correct_answer": "C"},
        {"text_uz": "'Shum bola' muallifi?", "option_a": "Hamza", "option_b": "G'afur G'ulom", "option_c": "Qodiriy", "option_d": "Cho'lpon", "correct_answer": "B"},
        {"text_uz": "Cho'lponning asl ismi?", "option_a": "Abdulhamid Sulaymon", "option_b": "Abdulla Hamid", "option_c": "Hamid Sulaymon", "option_d": "Abdulhamid Hamid", "correct_answer": "A"},
        {"text_uz": "Navoiy Xamsa nechta doston?", "option_a": "3", "option_b": "4", "option_c": "5", "option_d": "6", "correct_answer": "C"},
        {"text_uz": "'Farhod va Shirin' muallifi?", "option_a": "Nizomiy", "option_b": "Navoiy", "option_c": "Fuzuliy", "option_d": "Bedil", "correct_answer": "B"},
        {"text_uz": "G'azal janri?", "option_a": "Epik", "option_b": "Dramatik", "option_c": "Lirik", "option_d": "Lirik-epik", "correct_answer": "C"},
        {"text_uz": "Ruboiy misralari?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "6", "correct_answer": "C"},
        {"text_uz": "Doston janri?", "option_a": "Lirik", "option_b": "Dramatik", "option_c": "Epik yoki lirik-epik", "option_d": "Satirik", "correct_answer": "C"},
        {"text_uz": "Navoiy ona tili?", "option_a": "Fors", "option_b": "Arab", "option_c": "Chig'atoy o'zbek", "option_d": "Mo'g'ul", "correct_answer": "C"},
        {"text_uz": "'Alpomish' eposi?", "option_a": "Qozoq", "option_b": "Qirg'iz", "option_c": "O'zbek", "option_d": "Turkman", "correct_answer": "C"},
        {"text_uz": "Badiiy adabiyot asosiy funksiyasi?", "option_a": "Ma'lumot berish", "option_b": "Estetik ta'sir va tarbiya", "option_c": "Ilmiy bilim", "option_d": "Hujjat tuzish", "correct_answer": "B"},
        {"text_uz": "Pьesa janri?", "option_a": "Epik", "option_b": "Lirik", "option_c": "Dramatik", "option_d": "Lirik-epik", "correct_answer": "C"},
        {"text_uz": "Roman janri?", "option_a": "Lirik", "option_b": "Dramatik", "option_c": "Katta epik", "option_d": "Kichik epik", "correct_answer": "C"},
        {"text_uz": "Hikoya janri?", "option_a": "Katta epik", "option_b": "Lirik", "option_c": "Kichik proza", "option_d": "Dramatik", "correct_answer": "C"},
        {"text_uz": "Navoiy tug'ilgan yil?", "option_a": "1441", "option_b": "1451", "option_c": "1461", "option_d": "1471", "correct_answer": "A"},
        {"text_uz": "Babur kim edi?", "option_a": "Shoir va sarkarda", "option_b": "Faqat sarkarda", "option_c": "Faqat shoir", "option_d": "Olim", "correct_answer": "A"},
        {"text_uz": "'Devoni Hikmat' muallifi?", "option_a": "Navoiy", "option_b": "Ahmad Yassaviy", "option_c": "Bedil", "option_d": "Fuzuliy", "correct_answer": "B"},
        {"text_uz": "Tashbeh nima?", "option_a": "Ko'chma ma'no", "option_b": "O'xshatish", "option_c": "Qarama-qarshilik", "option_d": "Takror", "correct_answer": "B"},
        {"text_uz": "Kinoya nima?", "option_a": "To'g'ri maqtov", "option_b": "Istehzoli tanbeh", "option_c": "Mubolag'a", "option_d": "Tashbeh", "correct_answer": "B"},
        {"text_uz": "Shahnoma eposi?", "option_a": "O'zbek", "option_b": "Arab", "option_c": "Fors-tojik", "option_d": "Turk", "correct_answer": "C"},
        {"text_uz": "Abdulla Oripov to'plami?", "option_a": "Qo'shiqlar", "option_b": "Munojot", "option_c": "O'zbegim", "option_d": "Bahor", "correct_answer": "C"},
        {"text_uz": "Erkin Vohidov janri?", "option_a": "Proza", "option_b": "Drama", "option_c": "She'riyat", "option_d": "Publitsistika", "correct_answer": "C"},
        {"text_uz": "Hajviy asar nima?", "option_a": "Qayg'uli", "option_b": "Tanqidiy yoki kulgili", "option_c": "Qahramonlik", "option_d": "Romantik", "correct_answer": "B"},
        {"text_uz": "'Muqaddimatul adab' muallifi?", "option_a": "Navoiy", "option_b": "Zamaxshariy", "option_c": "Beruniy", "option_d": "Ulug'bek", "correct_answer": "B"},
        {"text_uz": "Hamza Hakimzodaning ismi?", "option_a": "Hamza Hakimzoda Niyoziy", "option_b": "Hamza Sultonov", "option_c": "Hamza Karimov", "option_d": "Hamza Yusupov", "correct_answer": "A"},
        {"text_uz": "Dostonlarda sevgi janri?", "option_a": "Epik", "option_b": "Lirik", "option_c": "Lirik-epik", "option_d": "Dramatik", "correct_answer": "C"},
        {"text_uz": "Mubolag'a nima?", "option_a": "O'xshatish", "option_b": "Bo'rttirib ko'rsatish", "option_c": "Kamaytirish", "option_d": "Sifatlash", "correct_answer": "B"},
    ],
    8: [{"text_uz": "O'zbekiston poytaxti?", "option_a": "Samarqand", "option_b": "Buxoro", "option_c": "Toshkent", "option_d": "Andijon", "correct_answer": "C"},
        {"text_uz": "Orolga quyiladigan daryolar?", "option_a": "Sirdaryo va Amudaryo", "option_b": "Zarafshon va Qashqadaryo", "option_c": "Volga va Don", "option_d": "Nil va Kongo", "correct_answer": "A"},
        {"text_uz": "Eng katta kontinent?", "option_a": "Afrika", "option_b": "Amerika", "option_c": "Yevropa", "option_d": "Osiyo", "correct_answer": "D"},
        {"text_uz": "Eng uzun daryo?", "option_a": "Amazonka", "option_b": "Nil", "option_c": "Yantszi", "option_d": "Mississippi", "correct_answer": "B"},
        {"text_uz": "Eng baland nuqta?", "option_a": "K2", "option_b": "Kanchenjunga", "option_c": "Everest", "option_d": "Lxotze", "correct_answer": "C"},
        {"text_uz": "Dunyo okeanlar soni?", "option_a": "3", "option_b": "4", "option_c": "5", "option_d": "6", "correct_answer": "C"},
        {"text_uz": "Eng katta okean?", "option_a": "Atlantika", "option_b": "Hind", "option_c": "Shimoliy Muz", "option_d": "Tinch", "correct_answer": "D"},
        {"text_uz": "O'zbekistonda nechta viloyat?", "option_a": "11", "option_b": "12", "option_c": "13", "option_d": "14", "correct_answer": "C"},
        {"text_uz": "Sahara qaysi qit'ada?", "option_a": "Osiyo", "option_b": "Afrika", "option_c": "Avstraliya", "option_d": "Amerika", "correct_answer": "B"},
        {"text_uz": "Eng ko'p aholli davlat?", "option_a": "Hindiston", "option_b": "Xitoy", "option_c": "AQSH", "option_d": "Rossiya", "correct_answer": "A"},
        {"text_uz": "Yer o'qi atrofida aylanish?", "option_a": "12 soat", "option_b": "24 soat", "option_c": "365 kun", "option_d": "30 kun", "correct_answer": "B"},
        {"text_uz": "Yer Quyosh atrofida?", "option_a": "24 soat", "option_b": "30 kun", "option_c": "365 kun 6 soat", "option_d": "100 yil", "correct_answer": "C"},
        {"text_uz": "Eng katta maydoni davlat?", "option_a": "Xitoy", "option_b": "AQSH", "option_c": "Kanada", "option_d": "Rossiya", "correct_answer": "D"},
        {"text_uz": "Kaspiy dengizi aslida?", "option_a": "Dengiz", "option_b": "Ko'l", "option_c": "Bo'g'oz", "option_d": "Daryo", "correct_answer": "B"},
        {"text_uz": "Eng chuqur ko'l?", "option_a": "Kaspiy", "option_b": "Viktoriya", "option_c": "Baykal", "option_d": "Orol", "correct_answer": "C"},
        {"text_uz": "O'zbekiston iqlimi?", "option_a": "Mo''tadil", "option_b": "Subtropik", "option_c": "Kontinental quruq", "option_d": "Arktik", "correct_answer": "C"},
        {"text_uz": "Sirdaryo qayerga?", "option_a": "Kaspiy", "option_b": "Orol", "option_c": "Qora dengiz", "option_d": "Hind okeani", "correct_answer": "B"},
        {"text_uz": "O'zbekiston eng uzun chegarasi?", "option_a": "Tojikiston", "option_b": "Qozog'iston", "option_c": "Afg'oniston", "option_d": "Turkmaniston", "correct_answer": "B"},
        {"text_uz": "Geografik kenglik?", "option_a": "Ekvatordan janub-shimol", "option_b": "Grinvichdan sharq-g'arb", "option_c": "Dengizdan balandlik", "option_d": "Ikki nuqta masofa", "correct_answer": "A"},
        {"text_uz": "Geografik uzunlik?", "option_a": "Ekvatordan masofa", "option_b": "Grinvich meridianidan", "option_c": "Balandlik", "option_d": "Chuqurlik", "correct_answer": "B"},
        {"text_uz": "Farg'ona vodiysi tog'lari?", "option_a": "Tyanshan va Pomir", "option_b": "Qoraqum va Qizilqum", "option_c": "Oltoy va Ural", "option_d": "Kavkaz va Himoloy", "correct_answer": "A"},
        {"text_uz": "O'zbekistonda eng baland cho'qqi?", "option_a": "Chimyon", "option_b": "Xazratisulton", "option_c": "Muztog'ota", "option_d": "Beshtor", "correct_answer": "B"},
        {"text_uz": "Qizilqum cho'li?", "option_a": "Faqat Turkmaniston", "option_b": "O'zbekiston va Qozog'iston", "option_c": "Faqat O'zbekiston", "option_d": "Tojikiston va O'zbekiston", "correct_answer": "B"},
        {"text_uz": "Zarafshon qayerdan?", "option_a": "Toshkent viloyati", "option_b": "Qirg'iziston", "option_c": "Tojikiston", "option_d": "Afg'oniston", "correct_answer": "C"},
        {"text_uz": "Ekvator qayerda?", "option_a": "Shimoliy qutbda", "option_b": "Janubiy qutbda", "option_c": "Yerning o'rta qismi", "option_d": "Tropiklar", "correct_answer": "C"},
        {"text_uz": "Amazon daryo havzasi?", "option_a": "Afrika", "option_b": "Osiyo", "option_c": "Janubiy Amerika", "option_d": "Shimoliy Amerika", "correct_answer": "C"},
        {"text_uz": "O'rta dengiz qit'alar?", "option_a": "Osiyo va Amerika", "option_b": "Yevropa, Afrika va Osiyo", "option_c": "Afrika va Avstraliya", "option_d": "Yevropa va Amerika", "correct_answer": "B"},
        {"text_uz": "Toshkent balandligi?", "option_a": "200-300 m", "option_b": "400-500 m", "option_c": "600-700 m", "option_d": "800-1000 m", "correct_answer": "B"},
        {"text_uz": "Eng uzun tog' tizmasi?", "option_a": "Himoloy", "option_b": "And tog'lari", "option_c": "Alp", "option_d": "Kavkaz", "correct_answer": "B"},
        {"text_uz": "O'zbekistondan o'tuvchi daryo?", "option_a": "Volga", "option_b": "Amudaryo", "option_c": "Don", "option_d": "Kama", "correct_answer": "B"},
    ],
    9: [{"text_uz": "'Kitob' inglizcha?", "option_a": "Book", "option_b": "Pen", "option_c": "Table", "option_d": "Chair", "correct_answer": "A"},
        {"text_uz": "To be (I) = ?", "option_a": "is", "option_b": "are", "option_c": "am", "option_d": "was", "correct_answer": "C"},
        {"text_uz": "She ___ a student.", "option_a": "am", "option_b": "are", "option_c": "is", "option_d": "be", "correct_answer": "C"},
        {"text_uz": "They ___ happy.", "option_a": "am", "option_b": "is", "option_c": "are", "option_d": "was", "correct_answer": "C"},
        {"text_uz": "Past of 'go'?", "option_a": "goed", "option_b": "gone", "option_c": "went", "option_d": "going", "correct_answer": "C"},
        {"text_uz": "Past of 'eat'?", "option_a": "eated", "option_b": "eaten", "option_c": "ate", "option_d": "eating", "correct_answer": "C"},
        {"text_uz": "Opposite of 'hot'?", "option_a": "Warm", "option_b": "Cool", "option_c": "Cold", "option_d": "Chilly", "correct_answer": "C"},
        {"text_uz": "How ___ apples?", "option_a": "much", "option_b": "many", "option_c": "some", "option_d": "any", "correct_answer": "B"},
        {"text_uz": "How ___ water?", "option_a": "many", "option_b": "much", "option_c": "some", "option_d": "few", "correct_answer": "B"},
        {"text_uz": "She ___ now. (study)", "option_a": "study", "option_b": "studies", "option_c": "is studying", "option_d": "studied", "correct_answer": "C"},
        {"text_uz": "I ___ go tomorrow.", "option_a": "shall", "option_b": "will", "option_c": "would", "option_d": "should", "correct_answer": "B"},
        {"text_uz": "Article 'an' qachon?", "option_a": "Undosh oldida", "option_b": "Unli oldida", "option_c": "Ko'plik oldida", "option_d": "Hech qachon", "correct_answer": "B"},
        {"text_uz": "She ___ the book. (read — Present Perfect)", "option_a": "read", "option_b": "has read", "option_c": "have read", "option_d": "reads", "correct_answer": "B"},
        {"text_uz": "Comparative of 'good'?", "option_a": "gooder", "option_b": "more good", "option_c": "better", "option_d": "best", "correct_answer": "C"},
        {"text_uz": "Superlative of 'bad'?", "option_a": "baddest", "option_b": "most bad", "option_c": "worst", "option_d": "worse", "correct_answer": "C"},
        {"text_uz": "The book ___ by students. (Passive)", "option_a": "reads", "option_b": "is read", "option_c": "reading", "option_d": "read", "correct_answer": "B"},
        {"text_uz": "interested ___ music.", "option_a": "at", "option_b": "on", "option_c": "in", "option_d": "of", "correct_answer": "C"},
        {"text_uz": "You ___ wear seatbelt.", "option_a": "can", "option_b": "must", "option_c": "may", "option_d": "might", "correct_answer": "B"},
        {"text_uz": "If it rains, I ___ stay.", "option_a": "will", "option_b": "would", "option_c": "should", "option_d": "shall", "correct_answer": "A"},
        {"text_uz": "He said he ___ tired.", "option_a": "is", "option_b": "was", "option_c": "are", "option_d": "were", "correct_answer": "B"},
        {"text_uz": "I enjoy ___. (swim — Gerund)", "option_a": "swim", "option_b": "to swim", "option_c": "swimming", "option_d": "swam", "correct_answer": "C"},
        {"text_uz": "I want ___ English. (learn)", "option_a": "learn", "option_b": "learning", "option_c": "to learn", "option_d": "learned", "correct_answer": "C"},
        {"text_uz": "'However' bog'lovchi?", "option_a": "Sabab", "option_b": "Natija", "option_c": "Qarama-qarshilik", "option_d": "Qo'shimcha", "correct_answer": "C"},
        {"text_uz": "I ___ breakfast every morning.", "option_a": "has", "option_b": "had", "option_c": "have", "option_d": "having", "correct_answer": "C"},
        {"text_uz": "'Beautiful' antonimi?", "option_a": "Pretty", "option_b": "Ugly", "option_c": "Nice", "option_d": "Gorgeous", "correct_answer": "B"},
        {"text_uz": "'Fast' sinonimi?", "option_a": "Slow", "option_b": "Quick", "option_c": "Careful", "option_d": "Heavy", "correct_answer": "B"},
        {"text_uz": "He doesn't ___ tennis.", "option_a": "plays", "option_b": "played", "option_c": "play", "option_d": "playing", "correct_answer": "C"},
        {"text_uz": "What is your name? — ...", "option_a": "I am fine", "option_b": "My name is...", "option_c": "I am 20", "option_d": "I live here", "correct_answer": "B"},
        {"text_uz": "'Very big' sinonimi?", "option_a": "Small", "option_b": "Huge", "option_c": "Medium", "option_d": "Tiny", "correct_answer": "B"},
        {"text_uz": "'I agree' = ?", "option_a": "Men rad etaman", "option_b": "Men rozi emasman", "option_c": "Men roziman", "option_d": "Tushunmadim", "correct_answer": "C"},
    ],
    10: [{"text_uz": "'Kitob' ruscha?", "option_a": "Книга", "option_b": "Ручка", "option_c": "Стол", "option_d": "Стул", "correct_answer": "A"},
         {"text_uz": "Rus tilida grammatik jinslar?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_answer": "B"},
         {"text_uz": "Мужской род misol?", "option_a": "Книга", "option_b": "Окно", "option_c": "Стол", "option_d": "Дверь", "correct_answer": "C"},
         {"text_uz": "Женский род misol?", "option_a": "Стол", "option_b": "Окно", "option_c": "Стул", "option_d": "Книга", "correct_answer": "D"},
         {"text_uz": "Средний род misol?", "option_a": "Стол", "option_b": "Книга", "option_c": "Окно", "option_d": "Стул", "correct_answer": "C"},
         {"text_uz": "Rus tilida kelishiklar?", "option_a": "4", "option_b": "5", "option_c": "6", "option_d": "7", "correct_answer": "C"},
         {"text_uz": "Я иду ___ школу.", "option_a": "в", "option_b": "на", "option_c": "к", "option_d": "от", "correct_answer": "A"},
         {"text_uz": "'Хорошо' antonimi?", "option_a": "Отлично", "option_b": "Плохо", "option_c": "Нормально", "option_d": "Средне", "correct_answer": "B"},
         {"text_uz": "Я ___ (читать).", "option_a": "читает", "option_b": "читаешь", "option_c": "читаю", "option_d": "читают", "correct_answer": "C"},
         {"text_uz": "Он ___ (читать).", "option_a": "читаю", "option_b": "читает", "option_c": "читаешь", "option_d": "читаем", "correct_answer": "B"},
         {"text_uz": "'Большой' antonimi?", "option_a": "Огромный", "option_b": "Средний", "option_c": "Маленький", "option_d": "Широкий", "correct_answer": "C"},
         {"text_uz": "Он шёл — qaysi zamon?", "option_a": "Hozirgi", "option_b": "O'tgan", "option_c": "Kelasi", "option_d": "Buyruq", "correct_answer": "B"},
         {"text_uz": "Я буду читать — qaysi zamon?", "option_a": "Hozirgi", "option_b": "O'tgan", "option_c": "Kelasi", "option_d": "Buyruq", "correct_answer": "C"},
         {"text_uz": "'красивый' so'z turkumi?", "option_a": "Ot", "option_b": "Fe'l", "option_c": "Sifat", "option_d": "Ravish", "correct_answer": "C"},
         {"text_uz": "'быстро' so'z turkumi?", "option_a": "Sifat", "option_b": "Fe'l", "option_c": "Ravish", "option_d": "Ot", "correct_answer": "C"},
         {"text_uz": "'Писать' buyruq shakli (sen)?", "option_a": "Пишу", "option_b": "Пишет", "option_c": "Пиши", "option_d": "Пишите", "correct_answer": "C"},
         {"text_uz": "Bir so'zda urg'u soni?", "option_a": "Faqat 1", "option_b": "2", "option_c": "3", "option_d": "Har qanday", "correct_answer": "A"},
         {"text_uz": "Совершенный вид?", "option_a": "Tugallanmagan", "option_b": "Tugallangan", "option_c": "Doimiy", "option_d": "Takroriy", "correct_answer": "B"},
         {"text_uz": "Несовершенный вид?", "option_a": "Tugallangan", "option_b": "Tugallanmagan", "option_c": "Bir marta", "option_d": "O'tgan", "correct_answer": "B"},
         {"text_uz": "Мягкий знак (ь) roli?", "option_a": "Unli tovush", "option_b": "Yumshatadi", "option_c": "Urg'u belgisi", "option_d": "Ajratish", "correct_answer": "B"},
         {"text_uz": "Твёрдый знак (ъ) qachon?", "option_a": "So'z oxirida", "option_b": "Prefiks va ildiz orasida", "option_c": "Undoshdan keyin", "option_d": "Unlidan oldin", "correct_answer": "B"},
         {"text_uz": "'Красиво' so'z turkumi?", "option_a": "Sifat", "option_b": "Ot", "option_c": "Ravish", "option_d": "Fe'l", "correct_answer": "C"},
         {"text_uz": "Деепричастие nima?", "option_a": "Sifatdosh", "option_b": "Ravishdosh", "option_c": "Fe'l", "option_d": "Ot", "correct_answer": "B"},
         {"text_uz": "Причастие nima?", "option_a": "Sifatdosh", "option_b": "Ravishdosh", "option_c": "Ravish", "option_d": "Olmosh", "correct_answer": "A"},
         {"text_uz": "Я иду ___ магазина.", "option_a": "в", "option_b": "к", "option_c": "из", "option_d": "на", "correct_answer": "C"},
         {"text_uz": "Rus tilida undosh harflar?", "option_a": "20", "option_b": "21", "option_c": "22", "option_d": "23", "correct_answer": "B"},
         {"text_uz": "Как вас зовут? — ...", "option_a": "Мне хорошо", "option_b": "Меня зовут...", "option_c": "Мне 20 лет", "option_d": "Я живу здесь", "correct_answer": "B"},
         {"text_uz": "Числительное so'z turkumi?", "option_a": "Fe'l", "option_b": "Ot", "option_c": "Son", "option_d": "Ravish", "correct_answer": "C"},
         {"text_uz": "Мне нравится музыка — kelishik?", "option_a": "Именительный", "option_b": "Родительный", "option_c": "Дательный", "option_d": "Винительный", "correct_answer": "A"},
         {"text_uz": "'Хотеть' spryajenie?", "option_a": "I", "option_b": "II", "option_c": "Разноспрягаемое", "option_d": "Irregular", "correct_answer": "C"},
    ],
}


def cmd_seed():
    """Savollarni qo'shadi. --force bilan mavjudlarni o'chirib qayta yozadi."""
    from database.db import Session
    from database.models import Question, Subject

    force = "--force" in sys.argv
    db = Session()
    try:
        existing = db.query(Question).count()
        if existing >= 300 and not force:
            print(f"\n⚠️  Savollar allaqachon bor: {existing} ta.")
            print("   Qayta yozish uchun: python scripts/manage.py seed --force\n")
            return

        if force and existing > 0:
            print(f"🗑  {existing} ta savol o'chirilmoqda...")
            db.query(Question).delete()
            db.commit()

        total = 0
        for subject_id, questions in QUESTIONS_DATA.items():
            subj = db.query(Subject).filter(Subject.id == subject_id).first()
            if not subj:
                print(f"  ⚠️  Fan {subject_id} topilmadi")
                continue
            for q in questions:
                db.add(Question(
                    subject_id=subject_id,
                    text_uz=q["text_uz"], text_oz=q["text_uz"], text_ru=q["text_uz"],
                    option_a=q["option_a"], option_b=q["option_b"],
                    option_c=q["option_c"], option_d=q["option_d"],
                    correct_answer=q["correct_answer"],
                    difficulty=random.choice(["easy", "medium", "hard"]),
                ))
                total += 1
        db.commit()

        for subj in db.query(Subject).all():
            cnt = db.query(Question).filter(Question.subject_id == subj.id).count()
            subj.question_count = cnt
        db.commit()

        print(f"\n✅ {total} ta savol qo'shildi!\n")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Savol seed xatosi: {e}\n")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════════════════════════════════════

def cmd_status():
    from database.db import Session
    from database.models import (
        User, Question, Direction, Region, Score, Leaderboard,
        UserTestParticipation, MandatoryChannel, ReferralSettings, ReferralLink,
    )
    db = Session()
    try:
        print("\n📊 Baza holati:")
        print(f"  👤 Foydalanuvchilar:     {db.query(User).count()}")

        from database.models import Subject
        q_total = db.query(Question).count()
        print(f"  ❓ Savollar (jami):      {q_total}")
        for s in db.query(Subject).all():
            cnt = db.query(Question).filter(Question.subject_id == s.id).count()
            print(f"     ├ {s.name_uz:<15}: {cnt}")

        print(f"  📚 Yo'nalishlar:         {db.query(Direction).count()}")
        print(f"  🗺  Viloyatlar:           {db.query(Region).count()}")

        st = db.query(Score).count()
        sa = db.query(Score).filter(Score.is_archived == False).count()
        sx = db.query(Score).filter(Score.is_archived == True).count()
        print(f"  📈 Natijalar (jami):     {st}  (joriy: {sa}, arxiv: {sx})")

        at = db.query(UserTestParticipation).filter(
            UserTestParticipation.status == "active"
        ).count()
        print(f"  ⚡ Aktiv testlar:        {at}")
        print(f"  🏆 Leaderboard:          {db.query(Leaderboard).count()}")

        chs = db.query(MandatoryChannel).count()
        ach = db.query(MandatoryChannel).filter(MandatoryChannel.is_active == True).count()
        print(f"  📢 Kanallar:             {chs}  (aktiv: {ach})")

        ref = db.query(ReferralSettings).filter(ReferralSettings.id == 1).first()
        rlinks = db.query(ReferralLink).count()
        if ref:
            state = "yoqilgan" if ref.is_enabled else "o'chirilgan"
            req = f", talab: {ref.required_count}" if ref.required_count else ""
            print(f"  🔗 Referal:              {state}{req}  ({rlinks} ta link)")
        else:
            print(f"  🔗 Referal:              sozlanmagan")
        print()
    except Exception as e:
        print(f"\n❌ Baza ulanmadi: {e}\n")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# CREATESUPERUSER
# ══════════════════════════════════════════════════════════════════════════════

def cmd_createsuperuser():
    """Admin login/parolini .env ga yozadi."""
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()

    if not username:
        username = input("Admin login (default: admin): ").strip() or "admin"
    if not password:
        import getpass
        password = getpass.getpass("Admin parol: ").strip()
        if not password:
            print("❌ Parol bo'sh bo'lmasligi kerak!")
            return

    env_path = os.path.join(ROOT, ".env")
    lines = []
    found_u = found_p = False

    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
        new = []
        for line in lines:
            if line.startswith("ADMIN_USERNAME="):
                new.append(f"ADMIN_USERNAME={username}\n"); found_u = True
            elif line.startswith("ADMIN_PASSWORD="):
                new.append(f"ADMIN_PASSWORD={password}\n"); found_p = True
            else:
                new.append(line)
        lines = new

    if not found_u: lines.append(f"ADMIN_USERNAME={username}\n")
    if not found_p: lines.append(f"ADMIN_PASSWORD={password}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)

    print(f"\n✅ Admin sozlamalari saqlandi:")
    print(f"   Login: {username}")
    print(f"   Parol: {'*' * len(password)}")
    print(f"\n   Admin panelni qayta ishga tushiring.\n")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

COMMANDS = {
    "check":           (cmd_check,           "Konfiguratsiya va DB ulanishni tekshirish"),
    "init":            (cmd_init,            "Yangi baza: jadvallar + boshlang'ich ma'lumotlar"),
    "migrate":         (cmd_migrate,         "Mavjud bazaga yangi ustunlar/jadvallar"),
    "seed":            (cmd_seed,            "Savollarni qo'shish (--force bilan qayta)"),
    "status":          (cmd_status,          "Baza holati"),
    "reset":           (cmd_reset,           "XAVFLI: bazani o'chirib qayta yaratish"),
    "createsuperuser": (cmd_createsuperuser, "Admin login/parolini o'rnatish"),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("Mavjud buyruqlar:")
        for name, (_, desc) in COMMANDS.items():
            print(f"  {name:<20} — {desc}")
        print()
        sys.exit(0)
    COMMANDS[sys.argv[1]][0]()