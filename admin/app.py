"""
DTM Bot — Admin Panel (Flask)
Real DB integratsiya, auth, users, tests, questions, stats
"""

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, send_file
)
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import sys, os, io
from datetime import datetime, timedelta
from sqlalchemy import func, desc

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['DEBUG'] = config.FLASK_DEBUG
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload limit

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Iltimos, tizimga kiring."


# ─── Admin foydalanuvchi (Flask-Login uchun) ──────────────────────────────────

ADMIN_CREDENTIALS = {
    os.getenv('ADMIN_USERNAME', 'admin'): generate_password_hash(
        os.getenv('ADMIN_PASSWORD', 'dtm_admin_2025')
    )
}


class AdminUser(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    if user_id in ADMIN_CREDENTIALS:
        return AdminUser(user_id)
    return None


# ─── DB session helper ────────────────────────────────────────────────────────

def get_db():
    from database.db import Session
    return Session()


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if username in ADMIN_CREDENTIALS and \
                check_password_hash(ADMIN_CREDENTIALS[username], password):
            login_user(AdminUser(username), remember=True)
            return redirect(url_for('dashboard'))
        error = "Login yoki parol noto'g'ri!"

    return render_template('login.html', error=error)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    db = get_db()
    try:
        from database.models import User, Score, Question, UserTestParticipation, TestSession

        total_users = db.query(func.count(User.id)).scalar() or 0
        total_tests_done = db.query(func.count(Score.id)).scalar() or 0
        active_tests = db.query(func.count(UserTestParticipation.id)).filter(
            UserTestParticipation.status == 'active'
        ).scalar() or 0
        total_questions = db.query(func.count(Question.id)).scalar() or 0

        # So'nggi 7 kun registratsiyalar
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_users_week = db.query(func.count(User.id)).filter(
            User.created_at >= week_ago
        ).scalar() or 0

        # Bugungi testlar
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        tests_today = db.query(func.count(Score.id)).filter(
            Score.created_at >= today_start
        ).scalar() or 0

        # O'rtacha ball
        avg_score = db.query(func.avg(Score.score)).scalar()
        avg_score = round(float(avg_score), 1) if avg_score else 0

        # So'nggi 5 ta ro'yxatdan o'tgan
        recent_users = db.query(User).order_by(desc(User.created_at)).limit(5).all()

        # Top 5 natija
        top_scores = db.query(Score).order_by(desc(Score.score)).limit(5).all()

        # Kunlik ro'yxatdan o'tish (7 kun)
        daily_reg = []
        for i in range(6, -1, -1):
            day = datetime.utcnow() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0)
            day_end = day.replace(hour=23, minute=59, second=59)
            count = db.query(func.count(User.id)).filter(
                User.created_at.between(day_start, day_end)
            ).scalar() or 0
            daily_reg.append({'date': day.strftime('%d.%m'), 'count': count})

        return render_template('dashboard.html',
            total_users=total_users,
            total_tests_done=total_tests_done,
            active_tests=active_tests,
            total_questions=total_questions,
            new_users_week=new_users_week,
            tests_today=tests_today,
            avg_score=avg_score,
            recent_users=recent_users,
            top_scores=top_scores,
            daily_reg=daily_reg,
        )
    finally:
        db.close()


# ─── Users ────────────────────────────────────────────────────────────────────

@app.route('/users')
@login_required
def users():
    db = get_db()
    try:
        from database.models import User, Score

        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()
        region_filter = request.args.get('region', '', type=str)
        per_page = 20

        query = db.query(User)
        if search:
            query = query.filter(
                (User.first_name.ilike(f'%{search}%')) |
                (User.last_name.ilike(f'%{search}%')) |
                (User.phone.ilike(f'%{search}%'))
            )
        if region_filter:
            query = query.filter(User.region_id == region_filter)

        total = query.count()
        user_list = query.order_by(desc(User.created_at)) \
                         .offset((page - 1) * per_page) \
                         .limit(per_page).all()

        # Har user uchun test soni
        user_stats = {}
        for u in user_list:
            score_count = db.query(func.count(Score.id)).filter(
                Score.user_id == u.id
            ).scalar() or 0
            best = db.query(func.max(Score.score)).filter(
                Score.user_id == u.id
            ).scalar()
            user_stats[u.id] = {
                'test_count': score_count,
                'best_score': round(float(best), 1) if best else 0
            }

        from database.models import Region
        regions = db.query(Region).all()

        total_pages = (total + per_page - 1) // per_page
        return render_template('users.html',
            users=user_list,
            user_stats=user_stats,
            total=total,
            page=page,
            total_pages=total_pages,
            search=search,
            region_filter=region_filter,
            regions=regions,
        )
    finally:
        db.close()


@app.route('/users/<int:user_id>')
@login_required
def user_detail(user_id):
    db = get_db()
    try:
        from database.models import User, Score, UserTestParticipation
        from sqlalchemy.orm import joinedload

        user = db.query(User).options(
            joinedload(User.region),
            joinedload(User.district),
            joinedload(User.direction)
        ).filter(User.id == user_id).first()

        if not user:
            flash('Foydalanuvchi topilmadi', 'error')
            return redirect(url_for('users'))

        scores = db.query(Score).filter(
            Score.user_id == user_id
        ).order_by(desc(Score.created_at)).limit(10).all()

        participations = db.query(UserTestParticipation).filter(
            UserTestParticipation.user_id == user_id
        ).order_by(desc(UserTestParticipation.joined_at)).limit(10).all()

        return render_template('user_detail.html',
            user=user, scores=scores, participations=participations
        )
    finally:
        db.close()


@app.route('/api/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    db = get_db()
    try:
        from database.models import User, Score, UserAnswer, UserTestParticipation, Leaderboard

        # Bog'liq ma'lumotlarni tozalash
        participations = db.query(UserTestParticipation).filter(
            UserTestParticipation.user_id == user_id
        ).all()
        for p in participations:
            db.query(UserAnswer).filter(UserAnswer.participation_id == p.id).delete()
        db.query(UserTestParticipation).filter(
            UserTestParticipation.user_id == user_id
        ).delete()
        db.query(Score).filter(Score.user_id == user_id).delete()
        db.query(Leaderboard).filter(Leaderboard.user_id == user_id).delete()
        db.query(UserAnswer).filter(UserAnswer.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        db.close()


# ─── Questions ────────────────────────────────────────────────────────────────

@app.route('/questions')
@login_required
def questions():
    db = get_db()
    try:
        from database.models import Question, Subject

        page = request.args.get('page', 1, type=int)
        subject_filter = request.args.get('subject', 0, type=int)
        search = request.args.get('search', '').strip()
        per_page = 25

        query = db.query(Question)
        if subject_filter:
            query = query.filter(Question.subject_id == subject_filter)
        if search:
            query = query.filter(Question.text_uz.ilike(f'%{search}%'))

        total = query.count()
        question_list = query.order_by(Question.subject_id, Question.id) \
                             .offset((page - 1) * per_page) \
                             .limit(per_page).all()

        subjects = db.query(Subject).all()
        subject_counts = {}
        for s in subjects:
            subject_counts[s.id] = db.query(func.count(Question.id)).filter(
                Question.subject_id == s.id
            ).scalar() or 0

        total_pages = (total + per_page - 1) // per_page
        return render_template('questions.html',
            questions=question_list,
            subjects=subjects,
            subject_counts=subject_counts,
            subject_filter=subject_filter,
            search=search,
            total=total,
            page=page,
            total_pages=total_pages,
        )
    finally:
        db.close()


@app.route('/api/questions/import', methods=['POST'])
@login_required
def import_questions():
    """Excel fayldan savollarni import qilish."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Fayl yuklanmadi'})

    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'error': 'Faqat Excel fayl (.xlsx, .xls)'})

    subject_id = request.form.get('subject_id', type=int)
    if not subject_id:
        return jsonify({'success': False, 'error': 'Fan tanlanmadi'})

    try:
        import openpyxl
        from database.models import Question

        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
        ws = wb.active

        db = get_db()
        added = 0
        errors = []

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or not row[0]:
                continue
            try:
                text = str(row[0]).strip() if row[0] else ''
                opt_a = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                opt_b = str(row[2]).strip() if len(row) > 2 and row[2] else ''
                opt_c = str(row[3]).strip() if len(row) > 3 and row[3] else ''
                opt_d = str(row[4]).strip() if len(row) > 4 and row[4] else ''
                correct = str(row[5]).strip().upper() if len(row) > 5 and row[5] else ''

                if not all([text, opt_a, opt_b, opt_c, opt_d]) or correct not in ('A', 'B', 'C', 'D'):
                    errors.append(f"Qator {row_idx}: to'liq emas yoki javob noto'g'ri")
                    continue

                db.add(Question(
                    subject_id=subject_id,
                    text_uz=text, text_oz=text, text_ru=text,
                    option_a=opt_a, option_b=opt_b,
                    option_c=opt_c, option_d=opt_d,
                    correct_answer=correct,
                ))
                added += 1
            except Exception as e:
                errors.append(f"Qator {row_idx}: {e}")

        db.commit()

        # Savol sonini yangilash
        from database.models import Subject
        subj = db.query(Subject).filter(Subject.id == subject_id).first()
        if subj:
            subj.question_count = db.query(func.count(Question.id)).filter(
                Question.subject_id == subject_id
            ).scalar()
            db.commit()
        db.close()

        return jsonify({
            'success': True,
            'added': added,
            'errors': errors[:10],
            'message': f"{added} ta savol qo'shildi"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/questions/<int:q_id>/delete', methods=['POST'])
@login_required
def delete_question(q_id):
    db = get_db()
    try:
        from database.models import Question, UserAnswer
        db.query(UserAnswer).filter(UserAnswer.question_id == q_id).delete()
        db.query(Question).filter(Question.id == q_id).delete()
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        db.close()


# ─── Tests (Sessions) ─────────────────────────────────────────────────────────

@app.route('/tests')
@login_required
def tests():
    db = get_db()
    try:
        from database.models import TestSession, UserTestParticipation, Score

        test_sessions = db.query(TestSession).order_by(
            desc(TestSession.created_at)
        ).limit(20).all()

        session_stats = {}
        for ts in test_sessions:
            participants = db.query(func.count(UserTestParticipation.id)).filter(
                UserTestParticipation.test_session_id == ts.id
            ).scalar() or 0
            completed = db.query(func.count(UserTestParticipation.id)).filter(
                UserTestParticipation.test_session_id == ts.id,
                UserTestParticipation.status == 'completed'
            ).scalar() or 0
            avg = db.query(func.avg(Score.score)).join(
                UserTestParticipation,
                UserTestParticipation.user_id == Score.user_id
            ).filter(
                UserTestParticipation.test_session_id == ts.id
            ).scalar()
            session_stats[ts.id] = {
                'participants': participants,
                'completed': completed,
                'avg_score': round(float(avg), 1) if avg else 0
            }

        return render_template('tests.html',
            test_sessions=test_sessions,
            session_stats=session_stats,
        )
    finally:
        db.close()


@app.route('/tests/<int:session_id>')
@login_required
def test_detail(session_id):
    db = get_db()
    try:
        from database.models import TestSession, UserTestParticipation, Score
        from sqlalchemy.orm import joinedload

        session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()
        if not session:
            flash('Session topilmadi', 'error')
            return redirect(url_for('tests'))

        participations = db.query(UserTestParticipation).options(
            joinedload(UserTestParticipation.user)
        ).filter(
            UserTestParticipation.test_session_id == session_id
        ).order_by(UserTestParticipation.joined_at).all()

        # Har participant uchun score
        scores_map = {}
        for p in participations:
            score = db.query(Score).filter(
                Score.user_id == p.user_id
            ).order_by(desc(Score.created_at)).first()
            scores_map[p.user_id] = score

        return render_template('test_detail.html',
            session=session,
            participations=participations,
            scores_map=scores_map,
        )
    finally:
        db.close()


# ─── Leaderboard ─────────────────────────────────────────────────────────────

@app.route('/leaderboard')
@login_required
def leaderboard():
    db = get_db()
    try:
        from database.models import Score, User, Direction
        from sqlalchemy.orm import joinedload

        page = request.args.get('page', 1, type=int)
        direction_filter = request.args.get('direction', '').strip()
        per_page = 25

        query = db.query(Score).options(joinedload(Score.user))

        if direction_filter:
            query = query.join(User).filter(User.direction_id == direction_filter)

        total = query.count()
        scores = query.order_by(desc(Score.score)) \
                      .offset((page - 1) * per_page) \
                      .limit(per_page).all()

        from database.models import Direction
        directions = db.query(Direction).order_by(Direction.name_uz).all()
        total_pages = (total + per_page - 1) // per_page

        return render_template('leaderboard.html',
            scores=scores,
            directions=directions,
            direction_filter=direction_filter,
            total=total,
            page=page,
            total_pages=total_pages,
        )
    finally:
        db.close()


# ─── Stats API ────────────────────────────────────────────────────────────────

@app.route('/api/stats/daily')
@login_required
def stats_daily():
    db = get_db()
    try:
        from database.models import User, Score
        days = request.args.get('days', 7, type=int)
        result = {'registrations': [], 'tests': []}

        for i in range(days - 1, -1, -1):
            day = datetime.utcnow() - timedelta(days=i)
            ds = day.replace(hour=0, minute=0, second=0)
            de = day.replace(hour=23, minute=59, second=59)
            label = day.strftime('%d.%m')

            reg = db.query(func.count(User.id)).filter(
                User.created_at.between(ds, de)
            ).scalar() or 0
            tests = db.query(func.count(Score.id)).filter(
                Score.created_at.between(ds, de)
            ).scalar() or 0

            result['registrations'].append({'date': label, 'count': reg})
            result['tests'].append({'date': label, 'count': tests})

        return jsonify(result)
    finally:
        db.close()


@app.route('/api/stats/subjects')
@login_required
def stats_subjects():
    db = get_db()
    try:
        from database.models import Subject, Question
        subjects = db.query(Subject).all()
        result = []
        for s in subjects:
            count = db.query(func.count(Question.id)).filter(
                Question.subject_id == s.id
            ).scalar() or 0
            result.append({'name': s.name_uz, 'count': count})
        return jsonify(result)
    finally:
        db.close()


# ─── Export ───────────────────────────────────────────────────────────────────

@app.route('/export/users')
@login_required
def export_users():
    """Foydalanuvchilarni Excel ga export qilish."""
    try:
        import openpyxl
        from database.models import User, Score

        db = get_db()
        users_all = db.query(User).order_by(User.id).all()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Foydalanuvchilar"

        headers = ['ID', 'Ism', 'Familiya', 'Telefon', 'Viloyat', 'Tuman',
                   "Yo'nalish", "Test soni", "Eng yaxshi ball", "Ro'yxat sanasi"]
        ws.append(headers)

        for u in users_all:
            scores = db.query(Score).filter(Score.user_id == u.id).all()
            best = max((s.score for s in scores), default=0)
            ws.append([
                u.id,
                u.first_name,
                u.last_name or '',
                u.phone,
                u.region.name_uz if u.region else '',
                u.district.name_uz if u.district else '',
                u.direction.name_uz if u.direction else '',
                len(scores),
                best,
                u.created_at.strftime('%d.%m.%Y %H:%M'),
            ])

        db.close()

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"users_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(buf, as_attachment=True,
                         download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Export xatosi: {e}', 'error')
        return redirect(url_for('users'))


@app.route('/export/scores')
@login_required
def export_scores():
    """Natijalarni Excel ga export."""
    try:
        import openpyxl
        from database.models import Score, User

        db = get_db()
        scores = db.query(Score).order_by(desc(Score.score)).all()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Natijalar"
        ws.append(['#', 'Ism', 'Familiya', 'Telefon', "Yo'nalish",
                   'Ball', "To'g'ri", 'Jami', 'Foiz', 'Sana'])

        for i, s in enumerate(scores, 1):
            u = s.user
            pct = round(s.correct_count / s.total_questions * 100, 1) if s.total_questions else 0
            ws.append([
                i,
                u.first_name if u else '',
                u.last_name if u else '',
                u.phone if u else '',
                u.direction.name_uz if u and u.direction else '',
                s.score,
                s.correct_count,
                s.total_questions,
                pct,
                s.created_at.strftime('%d.%m.%Y %H:%M'),
            ])

        db.close()

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"scores_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(buf, as_attachment=True,
                         download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Export xatosi: {e}', 'error')
        return redirect(url_for('leaderboard'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=config.FLASK_DEBUG)