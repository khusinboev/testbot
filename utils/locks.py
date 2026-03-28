"""
Oddiy in-memory user lock va throttle.
Redis kerak emas — MemoryStorage bilan ishlaydi.

Foydalanish:
    from utils.locks import user_lock, is_processing

    async def handler(cb, state):
        if is_processing(cb.from_user.id):
            await cb.answer("⏳ Iltimos kuting...")
            return
        async with user_lock(cb.from_user.id):
            # handler logikasi

50k foydalanuvchi uchun yaxshilashlar:
  - WeakValueDictionary: foydalanilmagan locklar avtomatik GC qilinadi
  - _last_action: 100k dan oshsa eski yozuvlar tozalanadi
"""

import asyncio
import time
from weakref import WeakValueDictionary
from typing import Dict

# WeakValueDictionary: lock ishlatilmayotganda GC avtomatik o'chiradi
_user_locks: WeakValueDictionary = WeakValueDictionary()
# Hozir bajarilayotgan userlar
_processing: set = set()


def _get_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


def is_processing(user_id: int) -> bool:
    """User hozir biror operatsiyada ekanligini tekshiradi."""
    return user_id in _processing


class UserLockContext:
    """Async context manager — user ni lock qiladi va tugagach bo'shatadi."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.lock = _get_lock(user_id)

    async def __aenter__(self):
        await self.lock.acquire()
        _processing.add(self.user_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _processing.discard(self.user_id)
        self.lock.release()


def user_lock(user_id: int) -> UserLockContext:
    return UserLockContext(user_id)


# ─── Throttle (bitta amal uchun minimal vaqt oralig'i) ──────────────────────

_last_action: Dict[int, float] = {}
_MAX_THROTTLE_SIZE = 100_000  # 50k user + zaxira


def _cleanup_throttle(now: float) -> None:
    """1 soatdan eski yozuvlarni o'chiradi."""
    cutoff = now - 3600.0
    stale = [k for k, v in _last_action.items() if v < cutoff]
    for k in stale:
        del _last_action[k]


def throttle_check(user_id: int, min_interval: float = 0.5) -> bool:
    """
    True qaytarsa — OK, davom etish mumkin.
    False qaytarsa — juda tez bosdi, e'tibor bermaslik kerak.
    """
    now = time.monotonic()
    last = _last_action.get(user_id, 0.0)
    if now - last < min_interval:
        return False
    _last_action[user_id] = now
    if len(_last_action) > _MAX_THROTTLE_SIZE:
        _cleanup_throttle(now)
    return True
