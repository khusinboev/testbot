# ═══════════════════════════════════════════════════════════════════
# INTEGRATSIYA QO'LLANMASI — barcha o'zgartirishlarni qo'llash
# ═══════════════════════════════════════════════════════════════════

## 1. FAYLLARNI NUSXALASH

Yangilangan fayllar:
  outputs/
  ├── database/
  │   ├── models.py           → database/models.py
  │   └── db.py               → database/db.py
  ├── utils/
  │   ├── test_service.py     → utils/test_service.py
  │   ├── scheduler.py        → utils/scheduler.py (YANGI)
  │   └── channel_service.py  → utils/channel_service.py (YANGI)
  ├── bot/
  │   ├── main.py             → bot/main.py
  │   └── handlers/
  │       └── registration.py → bot/handlers/registration.py
  └── admin/
      ├── routes_extra.py     → admin/routes_extra.py (YANGI)
      └── templates/
          ├── questions.html  → admin/templates/questions.html
          ├── channels.html   → admin/templates/channels.html (YANGI)
          └── broadcast.html  → admin/templates/broadcast.html (YANGI)


## 2. ADMIN/APP.PY GA QO'SHISH

admin/app.py ning oxiriga, `if __name__ == '__main__':` dan oldin:

```python
# Qo'shimcha routelarni ro'yxatga olish
from admin.routes_extra import register_extra_routes
register_extra_routes(app)
```


## 3. ADMIN/TEMPLATES/BASE.HTML SIDEBAR YANGILASH

base.html da mavjud Export nav-section ni quyidagi bilan almashtiring
(base_sidebar_new.html dan nusxa oling):

```html
  <nav class="nav-section mt-2">
    <div class="nav-label">Boshqaruv</div>
    <a href="{{ url_for('channels') }}"
       class="nav-item {% if request.endpoint == 'channels' %}active{% endif %}">
      <span class="icon">📢</span> Kanallar
    </a>
    <a href="{{ url_for('broadcast') }}"
       class="nav-item {% if request.endpoint == 'broadcast' %}active{% endif %}">
      <span class="icon">📣</span> Xabar yuborish
    </a>
  </nav>

  <nav class="nav-section mt-2">
    <div class="nav-label">Export</div>
    <a href="{{ url_for('export_users') }}" class="nav-item">
      <span class="icon">📥</span> Users Excel
    </a>
    <a href="{{ url_for('export_scores') }}" class="nav-item">
      <span class="icon">📥</span> Natijalar Excel
    </a>
    <a href="{{ url_for('export_questions') }}" class="nav-item">
      <span class="icon">📥</span> Savollar Excel
    </a>
  </nav>
```


## 4. DATABASE MIGRATION (yangi ustunlar va jadvallar)

Yangi jadvallar va ustunlar uchun Alembic migration yoki to'g'ridan qo'lda:

```sql
-- user_test_participation jadvaliga yangi ustunlar
ALTER TABLE user_test_participation
  ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS snapshot_questions JSON,
  ADD COLUMN IF NOT EXISTS snapshot_current_index INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS snapshot_answers JSON;

-- scores jadvaliga participation_id
ALTER TABLE scores
  ADD COLUMN IF NOT EXISTS participation_id INTEGER
    REFERENCES user_test_participation(id);

-- users jadvaliga is_blocked va language
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'uz';

-- Yangi jadvallar (agar mavjud bo'lmasa)
-- mandatory_channels, broadcast_messages jadvallari
-- models.py dan Base.metadata.create_all() orqali yaratiladi
```

Yoki `init_db.py` ni qayta ishga tushiring (faqat yangi jadvallar yaratiladi,
mavjudlari o'zgartirilmaydi):
```bash
python init_db.py
```

Mavjud ustunlarga o'zgartirish uchun esa to'g'ridan SQL ishlaytiring.


## 5. REQUIREMENTS.TXT GA QO'SHISH

```
apscheduler==3.10.4   # allaqachon bor
```
apscheduler requirements.txt da mavjud — qo'shimcha o'rnatish shart emas.


## 6. TEKSHIRISH RO'YXATI

✅ Admin panel:
  - /questions sahifasida Export modal ishlaydi
  - /channels da kanal qo'shish/o'chirish ishlaydi
  - /broadcast da xabar yuborish ishlaydi

✅ Bot:
  - /start da kanal obuna tekshiriladi
  - Tugallanmagan test bo'lsa resume/yangi test taklif qilinadi
  - Vaqt tugaganda avtomatik yakunlanadi (scheduler har 60 sek)
  - 🏆 Reyting yo'nalish bo'yicha ko'rsatiladi


## 7. ASOSIY XATOLAR VA TUZATILGANLARI

❌ database/db.py: StaticPool PostgreSQL bilan mos emasdi
✅ Tuzatildi: PostgreSQL uchun to'g'ri pool konfiguratsiyasi

❌ bot/main.py: router tartib noto'g'ri (test_router registration_router dan oldin)
✅ Tuzatildi: registration_router birinchi

❌ UserAnswer: participation_id + question_id bo'yicha unique constraint yo'q
✅ Tuzatildi: UniqueConstraint qo'shildi

❌ Score modelida participation_id yo'q
✅ Tuzatildi: participation_id maydoni qo'shildi

❌ complete_test: tugallanmagan bo'lsa ikki marta chaqirilsa ikki Score yaratilar edi
✅ Tuzatildi: status 'completed' bo'lsa qayta Score yaratilmaydi

❌ Test vaqt boshqaruvi yo'q
✅ Tuzatildi: deadline_at + scheduler + snapshot

❌ Admin export dropdown z-index muammosi
✅ Tuzatildi: to'liq modal bilan almashtirildi

❌ Kanal obuna tekshiruvi yo'q
✅ Tuzatildi: channel_service.py + subscription_gate

❌ Broadcast yo'q
✅ Tuzatildi: admin broadcast + background worker
