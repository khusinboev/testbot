"""
admin/routes_extra.py
Kanallar va broadcast uchun qo'shimcha routelar.
Bu faylni admin/app.py ga import qiling:
    from admin.routes_extra import register_extra_routes
    register_extra_routes(app)
"""
import asyncio
import logging
from datetime import datetime, timedelta
from flask import request, jsonify, render_template
from flask_login import login_required

logger = logging.getLogger(__name__)


def register_extra_routes(app):
    """app.py ga import qilib chaqiriladi."""

    # ── Kanallar sahifasi ──────────────────────────────────────────────────

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
        channel_id   = (data.get('channel_id') or '').strip()
        channel_name = (data.get('channel_name') or '').strip()
        invite_link  = (data.get('invite_link') or '').strip() or None

        if not channel_id or not channel_name:
            return jsonify({'success': False, 'error': 'Kanal ID va nomi majburiy'})

        db = Session()
        try:
            existing = db.query(MandatoryChannel).filter(
                MandatoryChannel.channel_id == channel_id
            ).first()
            if existing:
                return jsonify({'success': False, 'error': 'Bu kanal allaqachon qo\'shilgan'})

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
            ch.is_active = data.get('is_active', True)
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

    # ── Broadcast sahifasi ──────────────────────────────────────────────────

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
        from database.models import BroadcastMessage, User
        from sqlalchemy import func
        import threading

        data = request.get_json() or {}
        message_type         = data.get('message_type', 'text')
        content              = data.get('content', '').strip() or None
        forward_from_chat    = data.get('forward_from_chat', '').strip() or None
        forward_message_id   = data.get('forward_message_id')
        target               = data.get('target', 'all')

        if message_type == 'text' and not content:
            return jsonify({'success': False, 'error': 'Xabar matni bo\'sh'})
        if message_type == 'forward' and not (forward_from_chat and forward_message_id):
            return jsonify({'success': False, 'error': 'Post ma\'lumotlari to\'liq emas'})

        db = Session()
        try:
            # User count
            q = db.query(User)
            if target == 'active':
                month_ago = datetime.utcnow() - timedelta(days=30)
                q = q.filter(User.created_at >= month_ago)
            total = q.count()

            broadcast = BroadcastMessage(
                message_type=message_type,
                content=content,
                forward_from_chat=forward_from_chat,
                forward_message_id=forward_message_id,
                target=target,
                status='pending',
            )
            db.add(broadcast)
            db.commit()
            broadcast_id = broadcast.id
            db.close()

            # Background thread da yuborish
            thread = threading.Thread(
                target=_run_broadcast,
                args=(broadcast_id, message_type, content,
                      forward_from_chat, forward_message_id, target),
                daemon=True
            )
            thread.start()

            return jsonify({'success': True, 'broadcast_id': broadcast_id, 'total': total})
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'error': str(e)})

    def _run_broadcast(broadcast_id, message_type, content,
                       forward_chat, forward_msg_id, target):
        """Background da broadcast yuborish."""
        import time
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                _async_broadcast(broadcast_id, message_type, content,
                                 forward_chat, forward_msg_id, target)
            )
        except Exception as e:
            logger.error("Broadcast thread xato: %s", e)
            _set_broadcast_status(broadcast_id, 'failed')

    async def _async_broadcast(broadcast_id, message_type, content,
                                forward_chat, forward_msg_id, target):
        import os
        from database.db import Session
        from database.models import User, BroadcastMessage
        from datetime import timedelta
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        BOT_TOKEN = os.getenv('BOT_TOKEN')
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

        db = Session()
        q = db.query(User)
        if target == 'active':
            month_ago = datetime.utcnow() - timedelta(days=30)
            q = q.filter(User.created_at >= month_ago)
        users = q.all()

        # Status: sending
        bcast = db.query(BroadcastMessage).filter(
            BroadcastMessage.id == broadcast_id
        ).first()
        if bcast:
            bcast.status = 'sending'
            db.commit()
        db.close()

        sent = 0
        fail = 0

        for user in users:
            try:
                if message_type == 'text':
                    await bot.send_message(user.telegram_id, content, parse_mode='HTML')
                else:
                    # Forward
                    await bot.forward_message(
                        chat_id=user.telegram_id,
                        from_chat_id=forward_chat,
                        message_id=int(forward_msg_id)
                    )
                sent += 1
            except Exception as e:
                fail += 1
                logger.debug("Broadcast user %d xato: %s", user.telegram_id, e)

            # Flood limit: Telegram 30 msg/sec ruxsat beradi
            if (sent + fail) % 25 == 0:
                await asyncio.sleep(1)

        # Yakunlash
        db2 = Session()
        try:
            b = db2.query(BroadcastMessage).filter(
                BroadcastMessage.id == broadcast_id
            ).first()
            if b:
                b.sent_count  = sent
                b.fail_count  = fail
                b.status      = 'done'
                b.finished_at = datetime.utcnow()
                db2.commit()
        finally:
            db2.close()

        await bot.session.close()
        logger.info(
            "Broadcast #%d yakunlandi: %d yuborildi, %d xato",
            broadcast_id, sent, fail
        )

    def _set_broadcast_status(broadcast_id, status):
        from database.db import Session
        from database.models import BroadcastMessage
        db = Session()
        try:
            b = db.query(BroadcastMessage).filter(
                BroadcastMessage.id == broadcast_id
            ).first()
            if b:
                b.status = status
                db.commit()
        finally:
            db.close()
