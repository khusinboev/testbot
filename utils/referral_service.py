"""
utils/referral_service.py

TUZATILDI:
  - ASOSIY XATO: get_or_create_referral_link() va check_referral_gate()
    telegram_id qabul qilib, users.id (DB primary key) ga FK bog'langan
    ReferralLink.user_id ga yozardi → ForeignKeyViolation

    Endi barcha public funksiyalar telegram_id qabul qiladi va
    ichida users jadvalidan db_user_id ni topadi.
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
    def __init__(self, is_enabled, required_count, reward_message):
        self.is_enabled     = is_enabled
        self.required_count = required_count
        self.reward_message = reward_message


def get_referral_settings() -> _ReferralSettingsDTO:
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


# ─── Yordamchi: telegram_id → db_user_id ──────────────────────────────────

def _get_db_user_id(telegram_id: int) -> Optional[int]:
    """telegram_id bo'yicha users.id ni topadi."""
    db = Session()
    try:
        user = db.query(User.id).filter(User.telegram_id == telegram_id).first()
        return user[0] if user else None
    finally:
        db.close()


# ─── Referal link ──────────────────────────────────────────────────────────

def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return 'ref_' + ''.join(secrets.choice(alphabet) for _ in range(8))


class _LinkDTO:
    """Session mustaqil DTO."""
    def __init__(self, id, code, invited_count, user_id):
        self.id            = id
        self.code          = code
        self.invited_count = invited_count or 0
        self.user_id       = user_id


def get_or_create_referral_link(telegram_id: int) -> Optional[_LinkDTO]:
    """
    telegram_id bo'yicha user uchun referal linkni oladi yoki yaratadi.

    TUZATILDI: avval telegram_id ni users.id ga (DB PK) aylantiradi,
    shundan keyin ReferralLink.user_id ga yozadi (FK to'g'ri ishlaydi).
    """
    db_user_id = _get_db_user_id(telegram_id)
    if db_user_id is None:
        logger.warning("get_or_create_referral_link: telegram_id=%d users jadvalida topilmadi",
                       telegram_id)
        return None

    db = Session()
    try:
        link = db.query(ReferralLink).filter(ReferralLink.user_id == db_user_id).first()
        if not link:
            for _ in range(10):
                code = _generate_code()
                if not db.query(ReferralLink).filter(ReferralLink.code == code).first():
                    break
            link = ReferralLink(user_id=db_user_id, code=code, invited_count=0)
            db.add(link)
            db.commit()
            db.refresh(link)
        return _LinkDTO(
            id=link.id,
            code=link.code,
            invited_count=link.invited_count,
            user_id=link.user_id,
        )
    finally:
        db.close()


def get_or_create_referral_link_by_db_id(db_user_id: int) -> Optional[_LinkDTO]:
    """
    users.id (DB PK) bo'yicha referal link oladi yoki yaratadi.
    Admin panel va ichki servislar uchun.
    """
    db = Session()
    try:
        link = db.query(ReferralLink).filter(ReferralLink.user_id == db_user_id).first()
        if not link:
            for _ in range(10):
                code = _generate_code()
                if not db.query(ReferralLink).filter(ReferralLink.code == code).first():
                    break
            link = ReferralLink(user_id=db_user_id, code=code, invited_count=0)
            db.add(link)
            db.commit()
            db.refresh(link)
        return _LinkDTO(
            id=link.id,
            code=link.code,
            invited_count=link.invited_count,
            user_id=link.user_id,
        )
    finally:
        db.close()


# ─── Taklif qayd qilish ──────────────────────────────────────────────────────

def record_referral_invite(referral_code: str, invited_db_user_id: int) -> bool:
    """
    invited_db_user_id = yangi ro'yxatdan o'tgan userning users.id (DB PK).
    Bu funksiya to'g'ri — u allaqachon DB id qabul qiladi.
    """
    db = Session()
    try:
        link = db.query(ReferralLink).filter(ReferralLink.code == referral_code).first()
        if not link:
            return False

        if link.user_id == invited_db_user_id:
            return False

        existing = db.query(ReferralInvite).filter(
            ReferralInvite.invited_user_id == invited_db_user_id
        ).first()
        if existing:
            return False

        invite = ReferralInvite(
            referral_link_id=link.id,
            invited_user_id=invited_db_user_id,
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


# ─── Referal gate ────────────────────────────────────────────────────────────

def check_referral_gate(telegram_id: int) -> Dict[str, Any]:
    """
    telegram_id qabul qiladi.
    TUZATILDI: get_or_create_referral_link(telegram_id) endi to'g'ri ishlaydi.
    """
    settings = get_referral_settings()

    if not settings.is_enabled or settings.required_count == 0:
        link = get_or_create_referral_link(telegram_id)
        return {
            'allowed':   True,
            'enabled':   settings.is_enabled,
            'required':  settings.required_count,
            'invited':   link.invited_count if link else 0,
            'remaining': 0,
            'link_code': link.code if link else '',
            'link_url':  '',
        }

    link = get_or_create_referral_link(telegram_id)
    if link is None:
        # User DB da topilmadi — ro'yxatdan o'tmagan, o'tkazamiz
        return {
            'allowed':   True,
            'enabled':   True,
            'required':  settings.required_count,
            'invited':   0,
            'remaining': settings.required_count,
            'link_code': '',
            'link_url':  '',
        }

    invited   = link.invited_count
    remaining = max(0, settings.required_count - invited)

    return {
        'allowed':   remaining == 0,
        'enabled':   True,
        'required':  settings.required_count,
        'invited':   invited,
        'remaining': remaining,
        'link_code': link.code,
        'link_url':  '',
    }


# ─── Statistika ──────────────────────────────────────────────────────────────

def get_referral_stats() -> Dict[str, Any]:
    db = Session()
    try:
        total_links   = db.query(func.count(ReferralLink.id)).scalar() or 0
        total_invites = db.query(func.count(ReferralInvite.id)).scalar() or 0

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
                'user_id':       user.id,
                'first_name':    user.first_name,
                'last_name':     user.last_name or '',
                'phone':         user.phone,
                'code':          link.code,
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
    """user_id = users.id (DB PK). Admin panel uchun."""
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
            'has_link':      True,
            'code':          link.code,
            'invited_count': link.invited_count,
            'invites':       invite_list,
        }
    finally:
        db.close()