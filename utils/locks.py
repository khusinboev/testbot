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
"""

import asyncio
from typing import Dict

# Har bir user uchun alohida lock
_user_locks: Dict[int, asyncio.Lock] = {}
# Hozir bajarilayotgan userlar
_processing: set = set()


def _get_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


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

import time

_last_action: Dict[int, float] = {}


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
    return True