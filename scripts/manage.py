#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               DTM Test Bot — Loyiha boshqaruv skripti                      ║
║               scripts/manage.py  (v2.1)                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

ISHLATISH:
    python scripts/manage.py <buyruq> [opsiyalar]

BUYRUQLAR:
    check           — Konfiguratsiya va DB ulanishni tekshirish
    init            — Yangi baza: jadvallar + barcha boshlang'ich ma'lumotlar
    migrate         — Mavjud bazaga yangi ustunlar/jadvallar qo'shish
    seed            — Savollarni qo'shish (--force bilan qayta)
    status          — Baza statistikasini ko'rish
    reset           — XAVFLI: bazani o'chirib qayta yaratish
    createsuperuser — Admin login/parolini .env ga yozish

YANGI SERVERGA KO'CHIRISH TARTIBI:
    1.  git clone / fayllarni nusxalash
    2.  pip install -r requirements.txt
    3.  .env faylini to'ldirish (.env.example dan nusxa)
    4.  python scripts/manage.py check        # hamma narsa to'g'rimi?
    5.  python scripts/manage.py init         # jadvallar + seed
    6.  python scripts/manage.py seed         # savollar
    7.  python scripts/manage.py status       # natijani tekshirish
    8.  python -m bots.testbot.main           # botni ishga tushirish  ✅
    9.  python -m admin.app                   # admin panelni ishga tushirish

MAVJUD BAZAGA YANGI KOD DEPLOY QILISH:
    1.  git pull
    2.  pip install -r requirements.txt
    3.  python scripts/manage.py migrate
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
    print("\n🔍 Konfiguratsiya tekshiruvi...\n")
    ok = True

    tok = os.getenv("BOT_TOKEN", "")
    if tok and tok != "your_telegram_bot_token_here":
        print("  ✅ BOT_TOKEN")
    else:
        print("  ❌ BOT_TOKEN — .env da to'ldiring!")
        ok = False

    dbu = os.getenv("DATABASE_URL", "")
    if dbu and "username" not in dbu:
        print(f"  ✅ DATABASE_URL — {dbu[:50]}...")
    else:
        print("  ❌ DATABASE_URL — .env da to'ldiring!")
        ok = False

    sk = os.getenv("SECRET_KEY", "")
    bad_keys = ("your-secret-key-here", "change_this_to_random_secret_key_min32chars", "")
    if sk and sk not in bad_keys:
        print("  ✅ SECRET_KEY")
    else:
        import secrets as _s
        nk = _s.token_hex(32)
        print(f"  ⚠️  SECRET_KEY yo'q! .env ga qo'shing: SECRET_KEY={nk}")

    ru = os.getenv("REDIS_URL", "")
    if ru:
        try:
            import redis as _r
            _r.from_url(ru).ping()
            print(f"  ✅ Redis — ulanish muvaffaqiyatli")
        except Exception as e:
            print(f"  ⚠️  Redis ulanmadi: {e}")
            print("      MemoryStorage ishlatiladi")
    else:
        print("  ⚠️  REDIS_URL yo'q — MemoryStorage ishlatiladi")

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

    # Excel — data/ papkasida ham tekshirish
    excel_paths = [
        os.path.join(ROOT, "data", "Fanlar_majmuasi_2025-2026.xlsx"),
        os.path.join(ROOT, "Fanlar_majmuasi_2025-2026.xlsx"),
    ]
    excel_found = any(os.path.exists(p) for p in excel_paths)
    if excel_found:
        for p in excel_paths:
            if os.path.exists(p):
                print(f"  ✅ Excel fayl — {os.path.relpath(p, ROOT)} ({os.path.getsize(p)//1024} KB)")
    else:
        print(f"  ⚠️  Excel fayl yo'q — data/Fanlar_majmuasi_2025-2026.xlsx ga qo'ying")
        print("      Fallback: 5 ta namuna yo'nalish ishlatiladi")

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
    from database.db import init_db
    # data/ papkasini yaratish (Excel uchun)
    data_dir = os.path.join(ROOT, "data")
    os.makedirs(data_dir, exist_ok=True)
    init_db()


# ══════════════════════════════════════════════════════════════════════════════
# RESET
# ══════════════════════════════════════════════════════════════════════════════

def cmd_reset():
    c = input("\n⚠️  BARCHA MA'LUMOTLAR O'CHADI! Davom etish uchun 'yes' yozing: ").strip()
    if c != "yes":
        print("Bekor qilindi.")
        return
    from database.db import drop_tables, init_db
    print("🗑  O'chirilmoqda...")
    drop_tables()
    print("🔧 Qayta yaratilmoqda...")
    cmd_init()


# ══════════════════════════════════════════════════════════════════════════════
# MIGRATE
# ══════════════════════════════════════════════════════════════════════════════

def cmd_migrate():
    from sqlalchemy import text
    from database.db import Session, create_tables

    print("\n🔄 Migration boshlandi...\n")
    print("📋 Yangi jadvallar (agar yo'q bo'lsa yaratiladi)...")
    create_tables()

    db = Session()

    alters = [
        ("scores.is_archived",
         "ALTER TABLE scores ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE"),
        ("scores.attempted_count",
         "ALTER TABLE scores ADD COLUMN IF NOT EXISTS attempted_count INTEGER DEFAULT 0"),
        ("scores.participation_id",
         "ALTER TABLE scores ADD COLUMN IF NOT EXISTS participation_id INTEGER"
         " REFERENCES user_test_participation(id) ON DELETE SET NULL"),
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
        ("users.is_blocked",
         "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"),
        ("users.language",
         "ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'uz'"),
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
# SEED (savollar — o'zgarmaydi)
# ══════════════════════════════════════════════════════════════════════════════

QUESTIONS_DATA = {
    1: [
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
    5: [
        {"text_uz": "O'zbekiston mustaqilligi?", "option_a": "1990", "option_b": "1991", "option_c": "1992", "option_d": "1993", "correct_answer": "B"},
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
    6: [
        {"text_uz": "'Kitob' qaysi so'z turkumi?", "option_a": "Fe'l", "option_b": "Ot", "option_c": "Sifat", "option_d": "Ravish", "correct_answer": "B"},
        {"text_uz": "'Yozmoq' qaysi so'z turkumi?", "option_a": "Ot", "option_b": "Sifat", "option_c": "Fe'l", "option_d": "Ravish", "correct_answer": "C"},
        {"text_uz": "Ega — gapning qaysi bo'lagi?", "option_a": "Ikkinchi darajali", "option_b": "Bosh bo'lak", "option_c": "To'ldiruvchi", "option_d": "Aniqlovchi", "correct_answer": "B"},
        {"text_uz": "Kesim — gapning qaysi bo'lagi?", "option_a": "Ikkinchi darajali", "option_b": "Aniqlovchi", "option_c": "Bosh bo'lak", "option_d": "To'ldiruvchi", "correct_answer": "C"},
        {"text_uz": "O'zbek lotin alifbosi nechta harf?", "option_a": "26", "option_b": "28", "option_c": "29", "option_d": "32", "correct_answer": "C"},
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
}

# Qolgan fanlar uchun minimal ma'lumotlar (test ishlashi uchun)
for sid in [2, 3, 4, 7, 8, 9, 10]:
    QUESTIONS_DATA[sid] = [
        {"text_uz": f"Fan {sid} — Savol {i+1}",
         "option_a": "A variant", "option_b": "B variant",
         "option_c": "C variant", "option_d": "D variant",
         "correct_answer": ["A","B","C","D"][i % 4]}
        for i in range(30)
    ]


def cmd_seed():
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
            status = "✅" if cnt >= 30 else ("⚠️ " if cnt >= 10 else "❌")
            print(f"     {status} {s.name_uz:<15}: {cnt}")

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
    print(f"   Parol: {'*' * len(password)}\n")


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