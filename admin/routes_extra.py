"""
admin/routes_extra.py

YANGILANDI:
  1. Kanallar boshqaruvi (mavjud)
  2. Broadcast (mavjud)
  3. Yo'nalishlar sahifasi (YANGI) — statistika bilan
  4. Referal tizimi boshqaruvi (YANGI)
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from flask import request, jsonify, render_template
from flask_login import login_required

logger = logging.getLogger(__name__)


def register_extra_routes(app):

    # ══════════════════════════════════════════════════════════════
    # YO'NALISHLAR
    # ══════════════════════════════════════════════════════════════

    @app.route('/directions')
    @login_required
    def directions():
        from database.db import Session
        from database.models import Direction, User, Subject, Score, UserTestParticipation
        from sqlalchemy import func, desc

        db = Session()
        try:
            page     = request.args.get('page', 1, type=int)
            search   = request.args.get('search', '').strip()
            sort_by  = request.args.get('sort', 'users')  # users | name | scores
            per_page = 25

            query = db.query(Direction)
            if search:
                query = query.filter(
                    (Direction.name_uz.ilike(f'%{search}%')) |
                    (Direction.id.ilike(f'%{search}%'))
                )

            total      = query.count()
            all_dirs   = query.all()

            # Har yo'nalish uchun statistika
            dir_stats = {}
            for d in all_dirs:
                user_count = db.query(func.count(User.id)).filter(
                    User.direction_id == d.id
                ).scalar() or 0

                score_count = db.query(func.count(Score.id)).filter(
                    Score.user_id.in_(
                        db.query(User.id).filter(User.direction_id == d.id)
                    ),
                    Score.is_archived == False
                ).scalar() or 0

                avg_score = db.query(func.avg(Score.score)).filter(
                    Score.user_id.in_(
                        db.query(User.id).filter(User.direction_id == d.id)
                    ),
                    Score.is_archived == False
                ).scalar()

                best_score = db.query(func.max(Score.score)).filter(
                    Score.user_id.in_(
                        db.query(User.id).filter(User.direction_id == d.id)
                    ),
                    Score.is_archived == False
                ).scalar()

                dir_stats[d.id] = {
                    'user_count':  user_count,
                    'score_count': score_count,
                    'avg_score':   round(float(avg_score), 1) if avg_score else 0,
                    'best_score':  round(float(best_score), 1) if best_score else 0,
                }

            # Saralash
            if sort_by == 'users':
                all_dirs.sort(key=lambda d: dir_stats[d.id]['user_count'], reverse=True)
            elif sort_by == 'scores':
                all_dirs.sort(key=lambda d: dir_stats[d.id]['avg_score'], reverse=True)
            else:
                all_dirs.sort(key=lambda d: d.name_uz)

            # Sahifalash
            total_pages  = (total + per_page - 1) // per_page
            paged        = all_dirs[(page - 1) * per_page: page * per_page]

            # Umumiy statistika
            total_users_with_dir = db.query(func.count(User.id)).filter(
                User.direction_id.isnot(None)
            ).scalar() or 0
            total_users_without  = db.query(func.count(User.id)).filter(
                User.direction_id.is_(None)
            ).scalar() or 0

            subjects = db.query(Subject).all()
            subj_map = {s.id: s.name_uz for s in subjects}

            return render_template('directions.html',
                directions=paged,
                dir_stats=dir_stats,
                total=total,
                page=page,
                total_pages=total_pages,
                search=search,
                sort_by=sort_by,
                subj_map=subj_map,
                total_users_with_dir=total_users_with_dir,
                total_users_without=total_users_without,
            )
        finally:
            db.close()

    @app.route('/api/directions/<direction_id>/users')
    @login_required
    def api_direction_users(direction_id):
        """Yo'nalish foydalanuvchilari (AJAX)."""
        from database.db import Session
        from database.models import User, Score, Direction
        from sqlalchemy import func, desc

        db = Session()
        try:
            direction = db.query(Direction).filter(Direction.id == direction_id).first()
            if not direction:
                return jsonify({'success': False, 'error': 'Topilmadi'})

            users = db.query(User).filter(User.direction_id == direction_id).all()
            result = []
            for u in users:
                best = db.query(func.max(Score.score)).filter(
                    Score.user_id == u.id,
                    Score.is_archived == False
                ).scalar()
                result.append({
                    'id':         u.id,
                    'first_name': u.first_name,
                    'last_name':  u.last_name or '',
                    'phone':      u.phone,
                    'best_score': round(float(best), 1) if best else 0,
                })
            result.sort(key=lambda x: x['best_score'], reverse=True)
            return jsonify({'success': True, 'users': result, 'direction_name': direction.name_uz})
        finally:
            db.close()

    # ══════════════════════════════════════════════════════════════
    # REFERAL TIZIMI
    # ══════════════════════════════════════════════════════════════

    @app.route('/referral')
    @login_required
    def referral():
        from utils.referral_service import get_referral_settings, get_referral_stats
        settings = get_referral_settings()
        stats    = get_referral_stats()
        return render_template('referral.html', settings=settings, stats=stats)

    @app.route('/api/referral/settings', methods=['POST'])
    @login_required
    def api_referral_settings():
        from utils.referral_service import update_referral_settings
        data = request.get_json() or {}
        try:
            is_enabled     = data.get('is_enabled')
            required_count = data.get('required_count')
            reward_message = data.get('reward_message')

            if is_enabled is not None:
                is_enabled = bool(is_enabled)
            if required_count is not None:
                required_count = int(required_count)

            update_referral_settings(
                is_enabled=is_enabled,
                required_count=required_count,
                reward_message=reward_message,
            )
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/referral/user/<int:user_id>')
    @login_required
    def api_referral_user(user_id):
        from utils.referral_service import get_user_referral_detail
        detail = get_user_referral_detail(user_id)
        # datetime ni string ga o'tkazish
        for inv in detail.get('invites', []):
            if inv.get('created_at'):
                inv['created_at'] = inv['created_at'].strftime('%d.%m.%Y %H:%M')
        return jsonify({'success': True, 'data': detail})

    @app.route('/api/referral/reset/<int:user_id>', methods=['POST'])
    @login_required
    def api_referral_reset(user_id):
        """User ning referal kodini qayta generatsiya qilish."""
        import secrets, string
        from database.db import Session
        from database.models import ReferralLink
        db = Session()
        try:
            link = db.query(ReferralLink).filter(ReferralLink.user_id == user_id).first()
            if not link:
                return jsonify({'success': False, 'error': 'Topilmadi'})
            alphabet = string.ascii_uppercase + string.digits
            new_code = 'ref_' + ''.join(secrets.choice(alphabet) for _ in range(8))
            link.code = new_code
            db.commit()
            return jsonify({'success': True, 'new_code': new_code})
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            db.close()

    # ══════════════════════════════════════════════════════════════
    # KANALLAR (mavjud)
    # ══════════════════════════════════════════════════════════════

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
        data         = request.get_json() or {}
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
        db   = Session()
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

    # ══════════════════════════════════════════════════════════════
    # BROADCAST (mavjud)
    # ══════════════════════════════════════════════════════════════

    @app.route('/broadcast')
    @login_required
    def broadcast():
        from database.db import Session
        from database.models import User, BroadcastMessage
        from sqlalchemy import func, desc
        db = Session()
        try:
            total_users  = db.query(func.count(User.id)).scalar() or 0
            month_ago    = datetime.utcnow() - timedelta(days=30)
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


# ─── Broadcast helpers ────────────────────────────────────────────────────────

def _get_target_user_ids(db, target: str, top_n) -> List[int]:
    from database.models import User, Score
    from sqlalchemy import func, desc

    base_filter = ~User.is_blocked

    if target == 'all':
        rows = db.query(User.telegram_id).filter(base_filter).all()
    elif target == 'active':
        month_ago = datetime.utcnow() - timedelta(days=30)
        rows = db.query(User.telegram_id).filter(
            base_filter, User.created_at >= month_ago
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


def _run_broadcast(broadcast_id, message_type, content,
                   forward_chat, forward_msg_id, telegram_ids):
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


async def _async_broadcast(broadcast_id, message_type, content,
                            forward_chat, forward_msg_id, telegram_ids):
    import os
    from database.db import Session
    from database.models import BroadcastMessage
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    bot = Bot(token=os.getenv('BOT_TOKEN'),
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    db = Session()
    try:
        b = db.query(BroadcastMessage).filter(BroadcastMessage.id == broadcast_id).first()
        if b:
            b.status = 'sending'
            db.commit()
    finally:
        db.close()

    sent = fail = 0
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


def _set_broadcast_status(broadcast_id, status):
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