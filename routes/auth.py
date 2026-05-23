from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin
from models import db, User, Employee

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'worker':
            return redirect(url_for('worker.dashboard'))
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=True)
            next_page = request.args.get('next', '')
            # Validate next_page to prevent open redirect attacks
            if next_page:
                ref = urlparse(request.host_url)
                target = urlparse(urljoin(request.host_url, next_page))
                if not (target.scheme in ('http', 'https') and ref.netloc == target.netloc):
                    next_page = ''
            if next_page:
                return redirect(next_page)
            if user.role == 'worker':
                return redirect(url_for('worker.dashboard'))
            return redirect(url_for('dashboard.index'))
        flash('Λάθος όνομα χρήστη ή κωδικός.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/users')
@login_required
def users():
    if current_user.role != 'admin':
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    all_users = User.query.order_by(User.full_name).all()
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    return render_template('auth/users.html', users=all_users, employees=employees)


@auth_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    if current_user.role != 'admin':
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    if request.method == 'POST':
        username = request.form['username'].strip()
        if User.query.filter_by(username=username).first():
            flash('Το username υπάρχει ήδη.', 'danger')
            return render_template('auth/new_user.html', employees=employees)
        employee_id = request.form.get('employee_id') or None
        user = User(
            username=username,
            email=request.form.get('email', '').strip() or f'{username}@artrestoration.gr',
            full_name=request.form.get('full_name', '').strip(),
            role=request.form.get('role', 'user'),
            employee_id=employee_id,
        )
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        flash('Ο χρήστης δημιουργήθηκε.', 'success')
        return redirect(url_for('auth.users'))
    return render_template('auth/new_user.html', employees=employees)


@auth_bp.route('/users/<int:id>/edit', methods=['POST'])
@login_required
def edit_user(id):
    if current_user.role != 'admin':
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    user = User.query.get_or_404(id)
    user.full_name = request.form.get('full_name', '').strip()
    user.email = request.form.get('email', '').strip()
    user.role = request.form.get('role', user.role)
    user.employee_id = request.form.get('employee_id') or None
    user.is_active = request.form.get('is_active') == '1'
    new_pw = request.form.get('new_password', '').strip()
    if new_pw:
        user.set_password(new_pw)
    db.session.commit()
    flash(f'Χρήστης "{user.username}" ενημερώθηκε.', 'success')
    return redirect(url_for('auth.users'))


@auth_bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.role != 'admin':
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Δεν μπορείτε να διαγράψετε τον εαυτό σας.', 'danger')
        return redirect(url_for('auth.users'))
    db.session.delete(user)
    db.session.commit()
    flash('Ο χρήστης διαγράφηκε.', 'success')
    return redirect(url_for('auth.users'))
