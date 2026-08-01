import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- مدل‌های دیتابیس ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(36), unique=True, nullable=False)
    messages = db.relationship('Message', backref='recipient', lazy=True, cascade="all, delete-orphan")


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- روت‌ها (Route) ---

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('این نام کاربری قبلاً استفاده شده است.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(
            username=username,
            password_hash=hashed_pw,
            slug=str(uuid.uuid4())[:8]  # یک شناسه ۸ کاراکتری یکتا
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash('حساب کاربری شما با موفقیت ساخته شد!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('نام کاربری یا رمز عبور نادرست است.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('از حساب کاربری خارج شدید.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    # لینک اختصاصی کاربر برای اشتراک‌گذاری
    share_url = request.host_url.rstrip('/') + url_for('send_message', slug=current_user.slug)
    messages = Message.query.filter_by(user_id=current_user.id).order_by(Message.created_at.desc()).all()
    return render_template('dashboard.html', share_url=share_url, messages=messages)


@app.route('/u/<slug>', methods=['GET', 'POST'])
def send_message(slug):
    user = User.query.filter_by(slug=slug).first_or_404()

    if request.method == 'POST':
        content = request.form.get('content').strip()
        if content:
            new_msg = Message(content=content, user_id=user.id)
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('message_sent'))
        flash('متن پیام نمی‌تواند خالی باشد.', 'danger')

    return render_template('send_message.html', recipient_name=user.username)


@app.route('/sent')
def message_sent():
    return render_template('success.html')


@app.route('/delete-message/<int:msg_id>', methods=['POST'])
@login_required
def delete_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.user_id == current_user.id:
        db.session.delete(msg)
        db.session.commit()
        flash('پیام حذف شد.', 'success')
    return redirect(url_for('dashboard'))


# ایجاد جدول‌های دیتابیس در صورت عدم وجود
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
