"""
utils/referral_service.py

Barcha public funksiyalar telegram_id qabul qiladi.
Ichkarida telegram_id → users.id (DB PK) konversiyasi amalga oshiriladi.

Tarkib:
  ── Settings     get_referral_settings() / update_referral_settings()
  ── Link         get_or_create_referral_link()          ← telegram_id
                  get_or_create_referral_link_by_db_id() ← users.id (admin)
  ── Invite       record_referral_invite()
  ── Gate         check_referral_gate()                  ← telegram_id
  ── Stats        get_referral_stats() / get_user_referral_detail()
"""

from __future__ import annotations

import logging
import secrets
import string
from typing import Any, Dict, List, Optional

from database.db import Session
from database.models import ReferralInvite, ReferralLink, ReferralSettings, User
from sqlalchemy import func
from sqlalchemy import update as _sql_update

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DTO
# ══════════════════════════════════════════════════════════════════════════════

class ReferralSettingsDTO:
    __slots__ = ("is_enabled", "required_count", "reward_message")

    def __init__(self, is_enabled: bool, required_count: int, reward_message: Optional[str]):
        self.is_enabled     = is_enabled
        self.required_count = required_count
        self.reward_message = reward_message


class ReferralLinkDTO:
    __slots__ = ("id", "code", "invited_count", "user_id")

    def __init__(self, id: int, code: str, invited_count: int, user_id: int):
        self.id            = id
        self.code          = code
        self.invited_count = invited_count or 0
        self.user_id       = user_id


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

def get_referral_settings() -> ReferralSettingsDTO:
    """Global referal sozlamalarini qaytaradi. Yo'q bo'lsa — default yaratadi."""
    db = Session()
    try:
        s = db.query(ReferralSettings).filter(ReferralSettings.id == 1).first()
        if not s:
            s = ReferralSettings(
                id=1,
                is_enabled=False,
                required_count=0,
                reward_message="🎉 Tabriklaymiz! Referal talabi bajarildi!",
            )
            db.add(s)
            db.commit()
        return ReferralSettingsDTO(
            is_enabled=s.is_enabled,
            required_count=s.required_count,
            reward_message=s.reward_message,
        )
    finally:
        db.close()


def update_referral_settings(
    is_enabled:     Optional[bool] = None,
    required_count: Optional[int]  = None,
    reward_message: Optional[str]  = None,
) -> ReferralSettings:
    """Bir yoki bir nechta sozlamani yangilaydi. None qiymatlar o'zgarmaydi."""
    db = Session()
    try:
        s = db.query(ReferralSettings).filter(ReferralSettings.id == 1).first()
        if not s:
            s = ReferralSettings(id=1)
            db.add(s)

        if is_enabled     is not None: s.is_enabled     = is_enabled
        if required_count is not None: s.required_count = max(0, int(required_count))
        if reward_message is not None: s.reward_message = reward_message

        db.commit()
        return s
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_db_user_id(telegram_id: int) -> Optional[int]:
    """telegram_id → users.id (DB PK). Topilmasa — None."""
    db = Session()
    try:
        row = db.query(User.id).filter(User.telegram_id == telegram_id).first()
        return row[0] if row else None
    finally:
        db.close()


def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "ref_" + "".join(secrets.choice(alphabet) for _ in range(8))


def _create_link(db_user_id: int, db) -> ReferralLinkDTO:
    """DB sessiyasi ichida yangi link yaratadi va saqlaydi."""
    for _ in range(10):
        code = _generate_code()
        if not db.query(ReferralLink).filter(ReferralLink.code == code).first():
            break
    link = ReferralLink(user_id=db_user_id, code=code, invited_count=0)
    db.add(link)
    db.commit()
    db.refresh(link)
    return ReferralLinkDTO(
        id=link.id, code=link.code,
        invited_count=link.invited_count, user_id=link.user_id,
    )


# ══════════════════════════════════════════════════════════════════════════════
# LINK
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_referral_link(telegram_id: int) -> Optional[ReferralLinkDTO]:
    """
    Telegram user uchun referal link oladi yoki yaratadi.
    telegram_id → users.id konversiyasi ichkarida.
    """
    db_user_id = _get_db_user_id(telegram_id)
    if db_user_id is None:
        logger.warning(
            "get_or_create_referral_link: telegram_id=%d topilmadi", telegram_id
        )
        return None
    return get_or_create_referral_link_by_db_id(db_user_id)


def get_or_create_referral_link_by_db_id(db_user_id: int) -> Optional[ReferralLinkDTO]:
    """
    users.id (DB PK) bo'yicha link oladi yoki yaratadi.
    Admin panel va ichki servislar tomonidan ishlatiladi.
    """
    db = Session()
    try:
        link = db.query(ReferralLink).filter(ReferralLink.user_id == db_user_id).first()
        if link:
            return ReferralLinkDTO(
                id=link.id, code=link.code,
                invited_count=link.invited_count, user_id=link.user_id,
            )
        return _create_link(db_user_id, db)
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# INVITE
# ══════════════════════════════════════════════════════════════════════════════

def record_referral_invite(referral_code: str, invited_db_user_id: int) -> bool:
    """
    Yangi user referal orqali ro'yxatdan o'tganda chaqiriladi.
    invited_db_user_id = users.id (DB PK).

    Himoya:
      - O'zini-o'zi taklif qila olmaydi
      - Bir user faqat bir marta qayd qilinadi
    """
    db = Session()
    try:
        link = db.query(ReferralLink).filter(ReferralLink.code == referral_code).first()
        if not link:
            return False

        if link.user_id == invited_db_user_id:
            return False   # O'z havolasidan kirdi

        already = db.query(ReferralInvite).filter(
            ReferralInvite.invited_user_id == invited_db_user_id
        ).first()
        if already:
            return False   # Allaqachon boshqa orqali kirishgan

        db.add(ReferralInvite(
            referral_link_id=link.id,
            invited_user_id=invited_db_user_id,
        ))
        # Atomic increment — race condition dan himoya
        db.execute(
            _sql_update(ReferralLink)
            .where(ReferralLink.id == link.id)
            .values(invited_count=func.coalesce(ReferralLink.invited_count, 0) + 1)
        )
        db.commit()
        return True

    except Exception as e:
        db.rollback()
        logger.error("record_referral_invite xato: %s", e)
        return False
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# GATE
# ══════════════════════════════════════════════════════════════════════════════

def check_referral_gate(telegram_id: int) -> Dict[str, Any]:
    """
    Foydalanuvchi botga kirish huquqiga ega ekanligini tekshiradi.

    Qaytarish:
      allowed   — True: kirish ruxsat, False: bloklangan
      enabled   — referal tizimi yoqilganmi
      required  — talab qilingan referal soni
      invited   — hozircha taklif qilinganlar
      remaining — qolgan soni
      link_code — foydalanuvchi referal kodi
    """
    settings = get_referral_settings()

    # Tizim o'chiq yoki talab 0 — hamma kira oladi
    if not settings.is_enabled or settings.required_count == 0:
        link = get_or_create_referral_link(telegram_id)
        return {
            "allowed":   True,
            "enabled":   settings.is_enabled,
            "required":  settings.required_count,
            "invited":   link.invited_count if link else 0,
            "remaining": 0,
            "link_code": link.code if link else "",
        }

    link = get_or_create_referral_link(telegram_id)

    # User DB da topilmadi (ro'yxatdan o'tmagan) — bloklash mantiqsiz
    if link is None:
        return {
            "allowed":   True,
            "enabled":   True,
            "required":  settings.required_count,
            "invited":   0,
            "remaining": settings.required_count,
            "link_code": "",
        }

    remaining = max(0, settings.required_count - link.invited_count)
    return {
        "allowed":   remaining == 0,
        "enabled":   True,
        "required":  settings.required_count,
        "invited":   link.invited_count,
        "remaining": remaining,
        "link_code": link.code,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════════════

def get_referral_stats() -> Dict[str, Any]:
    """Admin panel uchun umumiy statistika."""
    db = Session()
    try:
        total_links   = db.query(func.count(ReferralLink.id)).scalar() or 0
        total_invites = db.query(func.count(ReferralInvite.id)).scalar() or 0

        top_referrers_raw = (
            db.query(ReferralLink, User)
            .join(User, ReferralLink.user_id == User.id)
            .order_by(ReferralLink.invited_count.desc())
            .limit(10)
            .all()
        )

        top_referrers = [
            {
                "user_id":       user.id,
                "first_name":    user.first_name,
                "last_name":     user.last_name or "",
                "phone":         user.phone,
                "code":          link.code,
                "invited_count": link.invited_count,
            }
            for link, user in top_referrers_raw
        ]

        return {
            "total_links":   total_links,
            "total_invites": total_invites,
            "top_referrers": top_referrers,
        }
    finally:
        db.close()


def get_user_referral_detail(user_id: int) -> Dict[str, Any]:
    """Bitta user ning referal tafsilotlari. user_id = users.id (DB PK)."""
    db = Session()
    try:
        link = db.query(ReferralLink).filter(ReferralLink.user_id == user_id).first()
        if not link:
            return {"has_link": False, "code": None, "invited_count": 0, "invites": []}

        invites_raw = (
            db.query(ReferralInvite, User)
            .join(User, ReferralInvite.invited_user_id == User.id)
            .filter(ReferralInvite.referral_link_id == link.id)
            .order_by(ReferralInvite.created_at.desc())
            .limit(20)
            .all()
        )

        return {
            "has_link":      True,
            "code":          link.code,
            "invited_count": link.invited_count,
            "invites": [
                {
                    "user_id":    u.id,
                    "first_name": u.first_name,
                    "last_name":  u.last_name or "",
                    "created_at": inv.created_at,
                }
                for inv, u in invites_raw
            ],
        }
    finally:
        db.close()