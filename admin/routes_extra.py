"""
admin/routes_extra.py

TUZATILDI:
  1. is_blocked filter: is_(False) → NULL ni tutmaydi → ~User.is_blocked ishlatildi
  2. Score import ortiqcha edi — olib tashlandi broadcast() da
  3. datetime import modul darajasida (top-level) — to'g'ri
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from flask import request, jsonify, render_template
from flask_login import login_required

logger = logging.getLogger(__name__)


def register_extra_routes(app):

    # ── Kanallar ──────────────────────────────────────────────────

    @app.route('/channels')
    @login_required
    def channels():
        from database.db import Session
        from database.models import MandatoryChannel
        db = Session()
        try:
            chs = db.query(MandatoryChannel).order_by(
                MandatoryChannel.created_at.desc()
            ).all()
            return render_template('channels.html', channels=chs)
        finally:
            db.close()

    @app.route('/api/channels/add', methods=['POST'])
    @login_required
    def api_channel_add():
        from database.db import Session
        from database.models import MandatoryChannel
        data = request.get_json() or {}
        channel_id   = (data.get('channel_id')   or '').strip()
        channel_name = (data.get('channel_name') or '').strip()
        invite_link  = (data.get('invite_link')  or '').strip() or None

        if not channel_id or not channel_name:
            return jsonify({'success': False, 'error': 'Kanal ID va nomi majburiy'})

        db = Session()
        try:
            existing = db.query(MandatoryChannel).filter(
                MandatoryChannel.channel_id == channel_id
            ).first()
            if existing:
                return jsonify({'success': False, 'error': "Bu kanal allaqachon qo'shilgan"})
            db.add(MandatoryChannel(
                channel_id=channel_id,
                channel_name=channel_name,
                invite_link=invite_link,
                is_active=True
            ))
            db.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            db.close()

    @app.route('/api/channels/<int:ch_id>/toggle', methods=['POST'])
    @login_required
    def api_channel_toggle(ch_id):
        from database.db import Session
        from database.models import MandatoryChannel
        data = request.get_json() or {}
        db = Session()
        try:
            ch = db.query(MandatoryChannel).filter(MandatoryChannel.id == ch_id).first()
            if not ch:
                return jsonify({'success': False, 'error': 'Topilmadi'})
            ch.is_active = bool(data.get('is_active', True))
            db.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            db.close()

    @app.route('/api/channels/<int:ch_id>/delete', methods=['POST'])
    @login_required
    def api_channel_delete(ch_id):
        from database.db import Session
        from database.models import MandatoryChannel
        db = Session()
        try:
            db.query(MandatoryChannel).filter(MandatoryChannel.id == ch_id).delete()
            db.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            db.close()

    # ── Broadcast ─────────────────────────────────────────────────

    @app.route('/broadcast')
    @login_required
    def broadcast():
        from database.db import Session
        from database.models import User, BroadcastMessage
        from sqlalchemy import func, desc
        db = Session()
        try:
            total_users = db.query(func.count(User.id)).scalar() or 0
            month_ago   = datetime.utcnow() - timedelta(days=30)
            active_users = db.query(func.count(User.id)).filter(
                User.created_at >= month_ago
            ).scalar() or 0
            broadcasts = db.query(BroadcastMessage).order_by(
                desc(BroadcastMessage.created_at)
            ).limit(10).all()
            return render_template(
                'broadcast.html',
                total_users=total_users,
                active_users=active_users,
                broadcasts=broadcasts,
            )
        finally:
            db.close()

    @app.route('/api/broadcast/send', methods=['POST'])
    @login_required
    def api_broadcast_send():
        from database.db import Session
        from database.models import BroadcastMessage
        import threading

        data               = request.get_json() or {}
        message_type       = data.get('message_type', 'text')
        content            = (data.get('content') or '').strip() or None
        forward_from_chat  = (data.get('forward_from_chat') or '').strip() or None
        forward_message_id = data.get('forward_message_id')
        target             = data.get('target', 'all')
        top_n              = data.get('top_n')

        if message_type == 'text' and not content:
            return jsonify({'success': False, 'error': "Xabar matni bo'sh"})
        if message_type == 'forward' and not (forward_from_chat and forward_message_id):
            return jsonify({'success': False, 'error': "Post ma'lumotlari to'liq emas"})

        db = Session()
        try:
            telegram_ids = _get_target_user_ids(db, target, top_n)
            total = len(telegram_ids)

            bcast = BroadcastMessage(
                message_type=message_type,
                content=content,
                forward_from_chat=forward_from_chat,
                forward_message_id=forward_message_id,
                target=target,
                status='pending',
            )
            db.add(bcast)
            db.commit()
            broadcast_id = bcast.id
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            db.close()

        thread = threading.Thread(
            target=_run_broadcast,
            args=(broadcast_id, message_type, content,
                  forward_from_chat, forward_message_id, telegram_ids),
            daemon=True
        )
        thread.start()

        return jsonify({'success': True, 'broadcast_id': broadcast_id, 'total': total})


def _get_target_user_ids(db, target: str, top_n) -> List[int]:
    """
    TUZATILDI:
      - is_blocked filter: ~User.is_blocked (NULL va False ikkalasini ham tutadi)
    """
    from database.models import User, Score
    from sqlalchemy import func, desc

    # TUZATILDI: is_(False) NULL ni tutmaydi → ~User.is_blocked ishlatildi
    base_filter = ~User.is_blocked

    if target == 'all':
        rows = db.query(User.telegram_id).filter(base_filter).all()

    elif target == 'active':
        month_ago = datetime.utcnow() - timedelta(days=30)
        rows = db.query(User.telegram_id).filter(
            base_filter,
            User.created_at >= month_ago
        ).all()

    elif target == 'top_n':
        try:
            n = int(top_n) if top_n else 100
            n = max(1, min(n, 100_000))
        except (TypeError, ValueError):
            n = 100

        subq = (
            db.query(Score.user_id, func.count(Score.id).label('cnt'))
            .group_by(Score.user_id)
            .order_by(desc('cnt'))
            .limit(n)
            .subquery()
        )
        rows = (
            db.query(User.telegram_id)
            .join(subq, User.id == subq.c.user_id)
            .filter(base_filter)
            .all()
        )
    else:
        rows = db.query(User.telegram_id).filter(base_filter).all()

    return [r[0] for r in rows]


def _run_broadcast(broadcast_id: int, message_type: str, content,
                   forward_chat, forward_msg_id, telegram_ids: List[int]) -> None:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _async_broadcast(broadcast_id, message_type, content,
                             forward_chat, forward_msg_id, telegram_ids)
        )
    except Exception as e:
        logger.error("Broadcast thread xato: %s", e)
        _set_broadcast_status(broadcast_id, 'failed')
    finally:
        try:
            loop.close()
        except Exception:
            pass


async def _async_broadcast(broadcast_id: int, message_type: str, content,
                            forward_chat, forward_msg_id,
                            telegram_ids: List[int]) -> None:
    import os
    from database.db import Session
    from database.models import BroadcastMessage
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    BOT_TOKEN = os.getenv('BOT_TOKEN')
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    db = Session()
    try:
        b = db.query(BroadcastMessage).filter(BroadcastMessage.id == broadcast_id).first()
        if b:
            b.status = 'sending'
            db.commit()
    finally:
        db.close()

    sent = 0
    fail = 0

    for tg_id in telegram_ids:
        try:
            if message_type == 'text':
                await bot.send_message(tg_id, content, parse_mode='HTML')
            else:
                await bot.forward_message(
                    chat_id=tg_id,
                    from_chat_id=forward_chat,
                    message_id=int(forward_msg_id)
                )
            sent += 1
        except Exception as e:
            fail += 1
            logger.debug("Broadcast %d xato: %s", tg_id, e)

        # Telegram flood limit: 30 msg/sec
        if (sent + fail) % 25 == 0:
            await asyncio.sleep(1)

    db2 = Session()
    try:
        b = db2.query(BroadcastMessage).filter(BroadcastMessage.id == broadcast_id).first()
        if b:
            b.sent_count  = sent
            b.fail_count  = fail
            b.status      = 'done'
            b.finished_at = datetime.utcnow()
            db2.commit()
    finally:
        db2.close()

    await bot.session.close()
    logger.info("Broadcast #%d: %d yuborildi, %d xato", broadcast_id, sent, fail)


def _set_broadcast_status(broadcast_id: int, status: str) -> None:
    from database.db import Session
    from database.models import BroadcastMessage
    db = Session()
    try:
        b = db.query(BroadcastMessage).filter(BroadcastMessage.id == broadcast_id).first()
        if b:
            b.status = status
            db.commit()
    finally:
        db.close()