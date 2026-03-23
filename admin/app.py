from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['DEBUG'] = config.FLASK_DEBUG

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class AdminUser(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    # This will be replaced with database lookup
    return AdminUser(user_id, "admin", "admin")

@app.route('/')
@login_required
def dashboard():
    """Admin dashboard"""
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login"""
    if request.method == 'POST':
        # Simple login for now - replace with proper authentication
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'admin' and password == 'admin':  # Change this!
            user = AdminUser(1, username, 'admin')
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/users')
@login_required
def users():
    """User management"""
    return render_template('users.html')

@app.route('/tests')
@login_required
def tests():
    """Test management"""
    return render_template('tests.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)