"""
utils/referral_service.py

Referal tizimi logikasi:
  - Har user uchun unikal kod yaratish
  - /start?ref=CODE orqali kelgan userlarni qayd qilish
  - Referal talab tekshiruvi (required_count)
  - Admin sozlamalari CRUD
"""
from __future__ import annotations

import logging
import secrets
import string
from typing import Optional, Dict, Any, List

from database.db import Session
from database.models import (
    User, ReferralSettings, ReferralLink, ReferralInvite
)
from sqlalchemy import func

logger = logging.getLogger(__name__)


# ─── Sozlamalar ──────────────────────────────────────────────────────────────

class _ReferralSettingsDTO:
    """Session yopilgandan keyin xavfsiz ishlatish uchun oddiy DTO."""
    def __init__(self, is_enabled, required_count, reward_message):
        self.is_enabled     = is_enabled
        self.required_count = required_count
        self.reward_message = reward_message


def get_referral_settings() -> _ReferralSettingsDTO:
    """Sozlamalarni oladi, yo'q bo'lsa yaratadi. DTO qaytaradi (session mustaqil)."""
    db = Session()
    try:
        settings = db.query(ReferralSettings).filter(ReferralSettings.id == 1).first()
        if not settings:
            settings = ReferralSettings(
                id=1,
                is_enabled=False,
                required_count=0,
                reward_message="🎉 Tabriklaymiz! Referal talabi bajarildi!"
            )
            db.add(settings)
            db.commit()
        return _ReferralSettingsDTO(
            is_enabled=settings.is_enabled,
            required_count=settings.required_count,
            reward_message=settings.reward_message,
        )
    finally:
        db.close()

def update_referral_settings(
    is_enabled: Optional[bool] = None,
    required_count: Optional[int] = None,
    reward_message: Optional[str] = None,
) -> ReferralSettings:
    db = Session()
    try:
        settings = db.query(ReferralSettings).filter(ReferralSettings.id == 1).first()
        if not settings:
            settings = ReferralSettings(id=1)
            db.add(settings)
        if is_enabled is not None:
            settings.is_enabled = is_enabled
        if required_count is not None:
            settings.required_count = max(0, int(required_count))
        if reward_message is not None:
            settings.reward_message = reward_message
        db.commit()
        return settings
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─── Referal link ─────────────────────────────────────────────────────────────

def _generate_code() -> str:
    """8 ta harfdan iborat unikal kod."""
    alphabet = string.ascii_uppercase + string.digits
    return 'ref_' + ''.join(secrets.choice(alphabet) for _ in range(8))


def get_or_create_referral_link(user_id: int) -> Optional[object]:
    """User uchun referal linkni oladi yoki yaratadi. DTO qaytaradi."""
    db = Session()
    try:
        link = db.query(ReferralLink).filter(ReferralLink.user_id == user_id).first()
        if not link:
            for _ in range(10):
                code = _generate_code()
                if not db.query(ReferralLink).filter(ReferralLink.code == code).first():
                    break
            link = ReferralLink(user_id=user_id, code=code, invited_count=0)
            db.add(link)
            db.commit()
            db.refresh(link)

        # Session yopilishidan oldin kerakli ma'lumotlarni DTO ga ko'chiramiz
        class _LinkDTO:
            pass
        dto = _LinkDTO()
        dto.id            = link.id
        dto.code          = link.code
        dto.invited_count = link.invited_count or 0
        dto.user_id       = link.user_id
        return dto
    finally:
        db.close()


def get_referral_link_by_code(code: str) -> Optional[ReferralLink]:
    db = Session()
    try:
        return db.query(ReferralLink).filter(ReferralLink.code == code).first()
    finally:
        db.close()


# ─── Taklif qayd qilish ───────────────────────────────────────────────────────

def record_referral_invite(referral_code: str, invited_user_id: int) -> bool:
    """
    Yangi user referal orqali ro'yxatdan o'tganda chaqiriladi.
    True = muvaffaqiyatli qayd qilindi.
    False = allaqachon qayd qilingan yoki kod noto'g'ri.
    """
    db = Session()
    try:
        # Kod mavjudligini tekshirish
        link = db.query(ReferralLink).filter(ReferralLink.code == referral_code).first()
        if not link:
            return False

        # User o'zini taklif qilishi mumkin emas
        if link.user_id == invited_user_id:
            return False

        # Allaqachon qayd qilinganmi?
        existing = db.query(ReferralInvite).filter(
            ReferralInvite.invited_user_id == invited_user_id
        ).first()
        if existing:
            return False

        # Qayd qilish
        invite = ReferralInvite(
            referral_link_id=link.id,
            invited_user_id=invited_user_id,
        )
        db.add(invite)
        link.invited_count = (link.invited_count or 0) + 1
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error("record_referral_invite xato: %s", e)
        return False
    finally:
        db.close()


# ─── Referal talab tekshiruvi ─────────────────────────────────────────────────

def check_referral_gate(user_id: int) -> Dict[str, Any]:
    """
    Botga kirish tekshiruvi.

    Qaytariladi:
      {
        'allowed': bool,        # Botdan foydalanish mumkinmi?
        'enabled': bool,        # Referal tizimi yoqilganmi?
        'required': int,        # Nechta referal kerak (0 = talab yo'q)
        'invited': int,         # Hozir nechta taklif qilgan
        'remaining': int,       # Qancha qoldi
        'link_code': str,       # Referal kodi
        'link_url': str,        # To'liq havola (bot username kerak)
      }
    """
    settings = get_referral_settings()

    # Tizim o'chirilgan bo'lsa — hamma o'ta oladi
    if not settings.is_enabled or settings.required_count == 0:
        link = get_or_create_referral_link(user_id)
        return {
            'allowed':   True,
            'enabled':   settings.is_enabled,
            'required':  settings.required_count,
            'invited':   link.invited_count if link else 0,
            'remaining': 0,
            'link_code': link.code if link else '',
            'link_url':  '',
        }

    # Talab bor — tekshirish
    link = get_or_create_referral_link(user_id)
    invited = link.invited_count if link else 0
    remaining = max(0, settings.required_count - invited)

    return {
        'allowed':   remaining == 0,
        'enabled':   True,
        'required':  settings.required_count,
        'invited':   invited,
        'remaining': remaining,
        'link_code': link.code if link else '',
        'link_url':  '',
    }


# ─── Statistika ──────────────────────────────────────────────────────────────

def get_referral_stats() -> Dict[str, Any]:
    """Admin panel uchun umumiy statistika."""
    db = Session()
    try:
        total_links   = db.query(func.count(ReferralLink.id)).scalar() or 0
        total_invites = db.query(func.count(ReferralInvite.id)).scalar() or 0

        # Top 10 referal
        top_referrers = (
            db.query(ReferralLink, User)
            .join(User, ReferralLink.user_id == User.id)
            .order_by(ReferralLink.invited_count.desc())
            .limit(10)
            .all()
        )

        top_list = []
        for link, user in top_referrers:
            top_list.append({
                'user_id':      user.id,
                'first_name':   user.first_name,
                'last_name':    user.last_name or '',
                'phone':        user.phone,
                'code':         link.code,
                'invited_count': link.invited_count,
            })

        return {
            'total_links':   total_links,
            'total_invites': total_invites,
            'top_referrers': top_list,
        }
    finally:
        db.close()


def get_user_referral_detail(user_id: int) -> Dict[str, Any]:
    """Bitta user ning referal ma'lumoti."""
    db = Session()
    try:
        link = db.query(ReferralLink).filter(ReferralLink.user_id == user_id).first()
        if not link:
            return {'has_link': False, 'code': None, 'invited_count': 0, 'invites': []}

        invites = (
            db.query(ReferralInvite, User)
            .join(User, ReferralInvite.invited_user_id == User.id)
            .filter(ReferralInvite.referral_link_id == link.id)
            .order_by(ReferralInvite.created_at.desc())
            .limit(20)
            .all()
        )

        invite_list = []
        for invite, u in invites:
            invite_list.append({
                'user_id':    u.id,
                'first_name': u.first_name,
                'last_name':  u.last_name or '',
                'created_at': invite.created_at,
            })

        return {
            'has_link':     True,
            'code':         link.code,
            'invited_count': link.invited_count,
            'invites':      invite_list,
        }
    finally:
        db.close()
