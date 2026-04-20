from flask import Flask, request, render_template_string, session, redirect, url_for, flash
import sqlite3
import hashlib
from datetime import datetime, timedelta
import secrets
from functools import wraps


app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(days=7)

DATABASE = 'expenses.db'


EXPENSE_CATEGORIES = {
    'food': {'name': '🍔 Еда', 'icon': '🍔', 'color': '#FF6384', 'priority': 1},
    'transport': {'name': '🚗 Транспорт', 'icon': '🚗', 'color': '#36A2EB', 'priority': 2},
    'entertainment': {'name': '🎬 Развлечения', 'icon': '🎬', 'color': '#FFCE56', 'priority': 3},
    'health': {'name': '💊 Здоровье', 'icon': '💊', 'color': '#4BC0C0', 'priority': 1},
    'housing': {'name': '🏠 Жилье', 'icon': '🏠', 'color': '#9966FF', 'priority': 1},
    'shopping': {'name': '🛍️ Покупки', 'icon': '🛍️', 'color': '#FF9F40', 'priority': 3},
    'education': {'name': '📚 Образование', 'icon': '📚', 'color': '#FF6384', 'priority': 2},
    'bills': {'name': '💡 Счета', 'icon': '💡', 'color': '#36A2EB', 'priority': 1},
    'gifts': {'name': '🎁 Подарки', 'icon': '🎁', 'color': '#FFCE56', 'priority': 4},
    'other': {'name': '📦 Другое', 'icon': '📦', 'color': '#4BC0C0', 'priority': 5}
}

# Источники доходов
INCOME_SOURCES = {
    'salary': {'name': '💰 Зарплата', 'icon': '💰'},
    'freelance': {'name': '💻 Фриланс', 'icon': '💻'},
    'business': {'name': '🏢 Бизнес', 'icon': '🏢'},
    'investment': {'name': '📈 Инвестиции', 'icon': '📈'},
    'gift': {'name': '🎁 Подарок', 'icon': '🎁'},
    'other': {'name': '📦 Другое', 'icon': '📦'}
}


def get_db():
    """Подключение к базе данных"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    """Хэширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    """Декоратор для проверки авторизации"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# ============= ФУНКЦИИ ДЛЯ РАБОТЫ С РАСХОДАМИ =============

def get_user_expenses(user_id, category=None, limit=None, offset=0, start_date=None, end_date=None):
    """Получение расходов пользователя с фильтрацией"""
    conn = get_db()
    cursor = conn.cursor()

    query = 'SELECT * FROM expenses WHERE user_id = ?'
    params = [user_id]

    if category and category != 'all':
        query += ' AND category = ?'
        params.append(category)

    if start_date:
        query += ' AND date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND date <= ?'
        params.append(end_date)

    query += ' ORDER BY date DESC, created_at DESC'

    if limit:
        query += ' LIMIT ? OFFSET ?'
        params.extend([limit, offset])

    cursor.execute(query, params)
    expenses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return expenses


def get_expense_stats(user_id, period='all'):
    """Получение статистики расходов за период"""
    conn = get_db()
    cursor = conn.cursor()

    date_filter = ""
    if period == 'week':
        date_filter = "AND date >= date('now', '-7 days')"
    elif period == 'month':
        date_filter = "AND date >= date('now', 'start of month')"
    elif period == 'year':
        date_filter = "AND date >= date('now', 'start of year')"

    cursor.execute(f'''
        SELECT 
            COUNT(*) as total_count,
            SUM(amount) as total_amount,
            AVG(amount) as average_amount,
            MIN(amount) as min_amount,
            MAX(amount) as max_amount
        FROM expenses 
        WHERE user_id = ? {date_filter}
    ''', (user_id,))
    stats = dict(cursor.fetchone())

    cursor.execute(f'''
        SELECT 
            category,
            COUNT(*) as count,
            SUM(amount) as total,
            AVG(amount) as average
        FROM expenses 
        WHERE user_id = ? {date_filter}
        GROUP BY category
        ORDER BY total DESC
    ''', (user_id,))
    category_stats = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return stats, category_stats


def add_expense(user_id, name, amount, category, description, date):
    """Добавление нового расхода"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO expenses (user_id, name, amount, category, description, date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, name, amount, category, description, date))
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def delete_expense(expense_id, user_id):
    """Удаление расхода"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (expense_id, user_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


# ============= ФУНКЦИИ ДЛЯ РАБОТЫ С ДОХОДАМИ =============

def get_user_incomes(user_id, limit=None, start_date=None, end_date=None):
    """Получение доходов пользователя"""
    conn = get_db()
    cursor = conn.cursor()

    query = 'SELECT * FROM incomes WHERE user_id = ?'
    params = [user_id]

    if start_date:
        query += ' AND date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND date <= ?'
        params.append(end_date)

    query += ' ORDER BY date DESC, created_at DESC'

    if limit:
        query += ' LIMIT ?'
        params.append(limit)

    cursor.execute(query, params)
    incomes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return incomes


def get_income_stats(user_id, period='all'):
    """Получение статистики доходов"""
    conn = get_db()
    cursor = conn.cursor()

    date_filter = ""
    if period == 'week':
        date_filter = "AND date >= date('now', '-7 days')"
    elif period == 'month':
        date_filter = "AND date >= date('now', 'start of month')"
    elif period == 'year':
        date_filter = "AND date >= date('now', 'start of year')"

    cursor.execute(f'''
        SELECT 
            COUNT(*) as total_count,
            SUM(amount) as total_amount,
            AVG(amount) as average_amount,
            MIN(amount) as min_amount,
            MAX(amount) as max_amount
        FROM incomes 
        WHERE user_id = ? {date_filter}
    ''', (user_id,))
    stats = dict(cursor.fetchone())

    cursor.execute(f'''
        SELECT 
            source,
            COUNT(*) as count,
            SUM(amount) as total
        FROM incomes 
        WHERE user_id = ? {date_filter}
        GROUP BY source
        ORDER BY total DESC
    ''', (user_id,))
    source_stats = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return stats, source_stats


def add_income(user_id, name, amount, source, date):
    """Добавление дохода"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO incomes (user_id, name, amount, source, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, name, amount, source, date))
    conn.commit()
    income_id = cursor.lastrowid
    conn.close()
    return income_id


def delete_income(income_id, user_id):
    """Удаление дохода"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM incomes WHERE id = ? AND user_id = ?', (income_id, user_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


# ============= ФУНКЦИИ ДЛЯ РАСЧЕТОВ =============

def get_balance(user_id):
    """Получение текущего баланса (доходы - расходы)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(amount) as total FROM incomes WHERE user_id = ?', (user_id,))
    total_income = cursor.fetchone()['total'] or 0
    cursor.execute('SELECT SUM(amount) as total FROM expenses WHERE user_id = ?', (user_id,))
    total_expense = cursor.fetchone()['total'] or 0
    conn.close()
    return total_income - total_expense


def get_monthly_summary(user_id, year, month):
    """Получение сводки за месяц"""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SUM(amount) as total, COUNT(*) as count
        FROM expenses
        WHERE user_id = ? AND date >= ? AND date < ?
    ''', (user_id, start_date, end_date))
    expenses_data = cursor.fetchone()

    cursor.execute('''
        SELECT SUM(amount) as total, COUNT(*) as count
        FROM incomes
        WHERE user_id = ? AND date >= ? AND date < ?
    ''', (user_id, start_date, end_date))
    incomes_data = cursor.fetchone()

    conn.close()

    return {
        'expenses_total': expenses_data['total'] or 0,
        'expenses_count': expenses_data['count'] or 0,
        'incomes_total': incomes_data['total'] or 0,
        'incomes_count': incomes_data['count'] or 0,
        'savings': (incomes_data['total'] or 0) - (expenses_data['total'] or 0)
    }


# ============= МАРШРУТЫ FLASK =============

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users WHERE username = ? AND password = ?',
                       (username, hash_password(password)))
        user = cursor.fetchone()

        if user:
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['username']

            flash(f'Добро пожаловать, {user["username"]}!', 'success')
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            conn.close()

    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход - Трекер расходов</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }
        .card {
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            border: none;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            border: none;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-5">
                <div class="card">
                    <div class="card-body p-5">
                        <h3 class="text-center mb-4">💰 Трекер Финансов</h3>
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endwith %}
                        <form method="POST">
                            <div class="mb-3">
                                <input type="text" class="form-control" name="username" placeholder="Имя пользователя" required>
                            </div>
                            <div class="mb-3">
                                <input type="password" class="form-control" name="password" placeholder="Пароль" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Войти</button>
                        </form>
                        <div class="text-center mt-3">
                            <a href="/register">Нет аккаунта? Зарегистрироваться</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
''')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or len(username) < 3:
            flash('Имя пользователя должно содержать минимум 3 символа', 'danger')
            return render_template_string(get_register_template())

        if not password or len(password) < 4:
            flash('Пароль должен содержать минимум 4 символа', 'danger')
            return render_template_string(get_register_template())

        if password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return render_template_string(get_register_template())

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                           (username, hash_password(password)))
            conn.commit()
            flash('Регистрация успешна! Теперь вы можете войти', 'success')
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Пользователь с таким именем уже существует', 'danger')
            conn.close()

    return render_template_string(get_register_template())


def get_register_template():
    return '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Регистрация - Трекер Финансов</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }
        .card {
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            border: none;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            border: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-5">
                <div class="card">
                    <div class="card-body p-5">
                        <h3 class="text-center mb-4">📝 Регистрация</h3>
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endwith %}
                        <form method="POST">
                            <div class="mb-3">
                                <input type="text" class="form-control" name="username" placeholder="Имя пользователя *" required>
                            </div>
                            <div class="mb-3">
                                <input type="password" class="form-control" name="password" placeholder="Пароль *" required>
                            </div>
                            <div class="mb-3">
                                <input type="password" class="form-control" name="confirm_password" placeholder="Подтвердите пароль *" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Зарегистрироваться</button>
                        </form>
                        <div class="text-center mt-3">
                            <a href="/login">Уже есть аккаунт? Войти</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']

    recent_expenses = get_user_expenses(user_id, limit=5)
    recent_incomes = get_user_incomes(user_id, limit=5)
    stats, category_stats = get_expense_stats(user_id, 'month')
    income_stats, source_stats = get_income_stats(user_id, 'month')
    balance = get_balance(user_id)

    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Главная - Трекер Финансов</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: #f5f5f5; }
        .navbar { background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-card { border: none; border-radius: 15px; }
        .balance { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
        .income { background: linear-gradient(135deg, #28a745, #20c997); color: white; }
        .expense { background: linear-gradient(135deg, #dc3545, #c82333); color: white; }
        .card { border: none; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); border: none; }
        .btn-success { background: linear-gradient(135deg, #28a745, #20c997); border: none; }
        .btn-danger { background: linear-gradient(135deg, #dc3545, #c82333); border: none; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-wallet"></i> <strong>Трекер Финансов</strong>
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/dashboard"><i class="fas fa-home"></i> Главная</a>
                <a class="nav-link" href="/history"><i class="fas fa-history"></i> Расходы</a>
                <a class="nav-link" href="/incomes"><i class="fas fa-plus-circle"></i> Доходы</a>
                <a class="nav-link" href="/stats"><i class="fas fa-chart-pie"></i> Статистика</a>
                <a class="nav-link" href="/logout"><i class="fas fa-sign-out-alt"></i> Выйти</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endwith %}

        <div class="row">
            <div class="col-md-4">
                <div class="card balance">
                    <div class="card-body">
                        <h6 class="card-title"><i class="fas fa-balance-scale"></i> Баланс</h6>
                        <h3>{{ "%.2f"|format(balance) }} ₽</h3>
                        <small>Доходы - Расходы</small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card income">
                    <div class="card-body">
                        <h6 class="card-title"><i class="fas fa-arrow-up"></i> Доходы за месяц</h6>
                        <h3>{{ "%.2f"|format(income_stats.total_amount or 0) }} ₽</h3>
                        <small>{{ income_stats.total_count or 0 }} операций</small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card expense">
                    <div class="card-body">
                        <h6 class="card-title"><i class="fas fa-arrow-down"></i> Расходы за месяц</h6>
                        <h3>{{ "%.2f"|format(stats.total_amount or 0) }} ₽</h3>
                        <small>{{ stats.total_count or 0 }} операций</small>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-arrow-down text-danger"></i> Добавить расход</h5>
                        <form method="POST" action="/add_expense">
                            <div class="row">
                                <div class="col-md-6 mb-3">
                                    <input type="text" class="form-control" name="name" placeholder="Название" required>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <input type="number" step="0.01" class="form-control" name="amount" placeholder="Сумма" required>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <select class="form-control" name="category" required>
                                        <option value="">Выберите категорию</option>
                                        {% for key, cat in categories.items() %}
                                            <option value="{{ key }}">{{ cat.name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <input type="date" class="form-control" name="date" id="dateInput">
                                </div>
                                <div class="col-12 mb-3">
                                    <textarea class="form-control" name="description" placeholder="Описание" rows="2"></textarea>
                                </div>
                                <div class="col-12">
                                    <button type="submit" class="btn btn-danger w-100">
                                        <i class="fas fa-save"></i> Сохранить расход
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-arrow-up text-success"></i> Добавить доход</h5>
                        <form method="POST" action="/add_income">
                            <div class="row">
                                <div class="col-md-6 mb-3">
                                    <input type="text" class="form-control" name="name" placeholder="Название" required>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <input type="number" step="0.01" class="form-control" name="amount" placeholder="Сумма" required>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <select class="form-control" name="source">
                                        {% for key, src in income_sources.items() %}
                                            <option value="{{ key }}">{{ src.name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <input type="date" class="form-control" name="date" id="incomeDateInput">
                                </div>
                                <div class="col-12">
                                    <button type="submit" class="btn btn-success w-100">
                                        <i class="fas fa-save"></i> Сохранить доход
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-clock"></i> Последние расходы</h5>
                        {% if recent_expenses %}
                            <div class="table-responsive">
                                <table class="table table-sm table-hover">
                                    <thead>
                                        <tr>
                                            <th>Дата</th>
                                            <th>Название</th>
                                            <th>Сумма</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for exp in recent_expenses %}
                                            <tr>
                                                <td>{{ exp.date }}</td>
                                                <td>{{ exp.name }}</td>
                                                <td class="text-danger">{{ "%.2f"|format(exp.amount) }} ₽</td>
                                            </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                            <a href="/history" class="btn btn-outline-secondary btn-sm">Вся история →</a>
                        {% else %}
                            <p class="text-center text-muted">Нет расходов</p>
                        {% endif %}
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-clock"></i> Последние доходы</h5>
                        {% if recent_incomes %}
                            <div class="table-responsive">
                                <table class="table table-sm table-hover">
                                    <thead>
                                        <tr>
                                            <th>Дата</th>
                                            <th>Название</th>
                                            <th>Сумма</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for inc in recent_incomes %}
                                            <tr>
                                                <td>{{ inc.date }}</td>
                                                <td>{{ inc.name }}</td>
                                                <td class="text-success">{{ "%.2f"|format(inc.amount) }} ₽</td>
                                            </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                            <a href="/incomes" class="btn btn-outline-secondary btn-sm">Все доходы →</a>
                        {% else %}
                            <p class="text-center text-muted">Нет доходов</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const today = new Date().toISOString().split('T')[0];
        const dateInput = document.getElementById('dateInput');
        const incomeDateInput = document.getElementById('incomeDateInput');
        if (dateInput) dateInput.value = today;
        if (incomeDateInput) incomeDateInput.value = today;
    </script>
</body>
</html>
''', categories=EXPENSE_CATEGORIES, income_sources=INCOME_SOURCES,
                                  recent_expenses=recent_expenses, recent_incomes=recent_incomes,
                                  stats=stats, income_stats=income_stats, balance=balance)


@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense_route():
    user_id = session['user_id']
    name = request.form.get('name')
    amount = request.form.get('amount')
    category = request.form.get('category')
    description = request.form.get('description', '')
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

    if not name or not amount or not category:
        flash('Заполните все обязательные поля', 'danger')
        return redirect(url_for('dashboard'))

    try:
        amount = float(amount)
        if amount <= 0:
            flash('Сумма должна быть положительной', 'danger')
            return redirect(url_for('dashboard'))

        add_expense(user_id, name, amount, category, description, date)
        flash('Расход успешно добавлен!', 'success')
    except ValueError:
        flash('Неверный формат суммы', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/add_income', methods=['POST'])
@login_required
def add_income_route():
    user_id = session['user_id']
    name = request.form.get('name')
    amount = request.form.get('amount')
    source = request.form.get('source')
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

    if not name or not amount:
        flash('Заполните название и сумму', 'danger')
        return redirect(url_for('dashboard'))

    try:
        amount = float(amount)
        if amount <= 0:
            flash('Сумма должна быть положительной', 'danger')
            return redirect(url_for('dashboard'))

        add_income(user_id, name, amount, source, date)
        flash('Доход успешно добавлен!', 'success')
    except ValueError:
        flash('Неверный формат суммы', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/history')
@login_required
def history():
    user_id = session['user_id']
    category = request.args.get('category', 'all')
    expenses = get_user_expenses(user_id, category)

    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>История расходов - Трекер расходов</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: #f5f5f5; }
        .navbar { background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card { border: none; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .table th { border-top: none; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-wallet"></i> <strong>Трекер расходов</strong>
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/dashboard">Главная</a>
                <a class="nav-link active" href="/history">Расходы</a>
                <a class="nav-link" href="/incomes">Доходы</a>
                <a class="nav-link" href="/stats">Статистика</a>
                <a class="nav-link" href="/logout">Выйти</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title"><i class="fas fa-list"></i> История расходов</h5>

                <div class="mb-3">
                    <label class="form-label">Фильтр по категории:</label>
                    <select class="form-control" id="categoryFilter" onchange="filterCategory()">
                        <option value="all">Все категории</option>
                        {% for key, cat in categories.items() %}
                            <option value="{{ key }}" {% if current_category == key %}selected{% endif %}>
                                {{ cat.name }}
                            </option>
                        {% endfor %}
                    </select>
                </div>

                {% if expenses %}
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Дата</th>
                                    <th>Название</th>
                                    <th>Категория</th>
                                    <th>Сумма</th>
                                    <th>Описание</th>
                                    <th>Действия</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for exp in expenses %}
                                    <tr>
                                        <td>{{ exp.date }}</td>
                                        <td>{{ exp.name }}</td>
                                        <td>{{ categories[exp.category].name if exp.category in categories else exp.category }}</td>
                                        <td class="text-danger fw-bold">{{ "%.2f"|format(exp.amount) }} ₽</td>
                                        <td>{{ exp.description or '-' }}</td>
                                        <td>
                                            <form method="POST" action="/expense/{{ exp.id }}/delete" style="display:inline">
                                                <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Удалить расход?')">
                                                    <i class="fas fa-trash"></i>
                                                </button>
                                            </form>
                                        </td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <p class="text-center text-muted">Нет расходов</p>
                {% endif %}
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function filterCategory() {
            const category = document.getElementById('categoryFilter').value;
            window.location.href = "/history?category=" + category;
        }
    </script>
</body>
</html>
''', expenses=expenses, categories=EXPENSE_CATEGORIES, current_category=category)


@app.route('/incomes')
@login_required
def incomes_list():
    user_id = session['user_id']
    incomes = get_user_incomes(user_id)
    stats, source_stats = get_income_stats(user_id)

    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Доходы - Трекер расходов</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: #f5f5f5; }
        .navbar { background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card { border: none; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .stat-card { background: linear-gradient(135deg, #28a745, #20c997); color: white; border: none; border-radius: 15px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-wallet"></i> <strong>Трекер расходов</strong>
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/dashboard">Главная</a>
                <a class="nav-link" href="/history">Расходы</a>
                <a class="nav-link active" href="/incomes">Доходы</a>
                <a class="nav-link" href="/stats">Статистика</a>
                <a class="nav-link" href="/logout">Выйти</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row">
            <div class="col-md-4">
                <div class="card stat-card">
                    <div class="card-body">
                        <h6 class="card-title">Всего доходов</h6>
                        <h3>{{ "%.2f"|format(stats.total_amount or 0) }} ₽</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card stat-card">
                    <div class="card-body">
                        <h6 class="card-title">Количество поступлений</h6>
                        <h3>{{ stats.total_count or 0 }}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card stat-card">
                    <div class="card-body">
                        <h6 class="card-title">Средний доход</h6>
                        <h3>{{ "%.2f"|format(stats.average_amount or 0) }} ₽</h3>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-body">
                <h5 class="card-title"><i class="fas fa-list"></i> Все доходы</h5>
                {% if incomes %}
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Дата</th>
                                    <th>Название</th>
                                    <th>Источник</th>
                                    <th>Сумма</th>
                                    <th>Действия</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for inc in incomes %}
                                    <tr>
                                        <td>{{ inc.date }}</td>
                                        <td>{{ inc.name }}</td>
                                        <td>
                                            {% if inc.source == 'salary' %}💰 Зарплата
                                            {% elif inc.source == 'freelance' %}💻 Фриланс
                                            {% elif inc.source == 'business' %}🏢 Бизнес
                                            {% elif inc.source == 'investment' %}📈 Инвестиции
                                            {% elif inc.source == 'gift' %}🎁 Подарок
                                            {% else %}📦 Другое
                                            {% endif %}
                                        </td>
                                        <td class="text-success fw-bold">{{ "%.2f"|format(inc.amount) }} ₽</td>
                                        <td>
                                            <form method="POST" action="/income/{{ inc.id }}/delete" style="display:inline">
                                                <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Удалить доход?')">
                                                    <i class="fas fa-trash"></i>
                                                </button>
                                            </form>
                                        </td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <p class="text-center text-muted">Нет добавленных доходов</p>
                {% endif %}
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
''', incomes=incomes, stats=stats)


@app.route('/expense/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense_route(expense_id):
    user_id = session['user_id']

    if delete_expense(expense_id, user_id):
        flash('Расход успешно удален!', 'success')
    else:
        flash('Расход не найден', 'danger')

    return redirect(url_for('history'))


@app.route('/income/<int:income_id>/delete', methods=['POST'])
@login_required
def delete_income_route(income_id):
    user_id = session['user_id']

    if delete_income(income_id, user_id):
        flash('Доход успешно удален!', 'success')
    else:
        flash('Доход не найден', 'danger')

    return redirect(url_for('incomes_list'))


@app.route('/stats')
@login_required
def stats():
    user_id = session['user_id']
    period = request.args.get('period', 'month')

    stats, category_stats = get_expense_stats(user_id, period)
    income_stats, source_stats = get_income_stats(user_id, period)
    balance = get_balance(user_id)

    period_names = {
        'week': 'за неделю',
        'month': 'за месяц',
        'year': 'за год',
        'all': 'за всё время'
    }

    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Статистика - Трекер расходов</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: #f5f5f5; }
        .navbar { background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card { border: none; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        canvas { max-height: 400px; }
        .period-btn { margin: 0 5px; }
        .period-btn.active { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-wallet"></i> <strong>Трекер расходов</strong>
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/dashboard">Главная</a>
                <a class="nav-link" href="/history">Расходы</a>
                <a class="nav-link" href="/incomes">Доходы</a>
                <a class="nav-link active" href="/stats">Статистика</a>
                <a class="nav-link" href="/logout">Выйти</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row">
            <div class="col-12 mb-3">
                <div class="btn-group" role="group">
                    <a href="/stats?period=week" class="btn btn-outline-primary period-btn {% if period == 'week' %}active{% endif %}">Неделя</a>
                    <a href="/stats?period=month" class="btn btn-outline-primary period-btn {% if period == 'month' %}active{% endif %}">Месяц</a>
                    <a href="/stats?period=year" class="btn btn-outline-primary period-btn {% if period == 'year' %}active{% endif %}">Год</a>
                    <a href="/stats?period=all" class="btn btn-outline-primary period-btn {% if period == 'all' %}active{% endif %}">Всё время</a>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body text-center">
                        <h6>💰 Баланс</h6>
                        <h3 class="{% if balance >= 0 %}text-success{% else %}text-danger{% endif %}">
                            {{ "%.2f"|format(balance) }} ₽
                        </h3>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body text-center">
                        <h6>📈 Доходы {{ period_name }}</h6>
                        <h3 class="text-success">{{ "%.2f"|format(income_stats.total_amount or 0) }} ₽</h3>
                        <small>{{ income_stats.total_count or 0 }} операций</small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body text-center">
                        <h6>📉 Расходы {{ period_name }}</h6>
                        <h3 class="text-danger">{{ "%.2f"|format(stats.total_amount or 0) }} ₽</h3>
                        <small>{{ stats.total_count or 0 }} операций</small>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-chart-pie"></i> Распределение расходов</h5>
                        <canvas id="expenseChart"></canvas>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-table"></i> Детализация расходов</h5>
                        {% if category_stats %}
                            <div class="table-responsive">
                                <table class="table table-hover">
                                    <thead>
                                        <tr>
                                            <th>Категория</th>
                                            <th>Сумма</th>
                                            <th>Количество</th>
                                            <th>%</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% set total = stats.total_amount or 1 %}
                                        {% for stat in category_stats %}
                                            <tr>
                                                <td>{{ categories[stat.category].name if stat.category in categories else stat.category }}</td>
                                                <td class="text-danger">{{ "%.2f"|format(stat.total) }} ₽</td>
                                                <td>{{ stat.count }}</td>
                                                <td>{{ "%.1f"|format((stat.total / total * 100) if total > 0 else 0) }}%</td>
                                            </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        {% else %}
                            <p class="text-center text-muted">Нет данных</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const categoryStats = {{ category_stats|tojson }};
        const categories = {{ categories|tojson }};

        if (categoryStats.length > 0) {
            const ctx = document.getElementById('expenseChart').getContext('2d');
            new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: categoryStats.map(s => categories[s.category] ? categories[s.category].name : s.category),
                    datasets: [{
                        data: categoryStats.map(s => s.total),
                        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FF6384', '#36A2EB'],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'bottom' },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const total = categoryStats.reduce((sum, s) => sum + s.total, 0);
                                    const percentage = ((context.raw / total) * 100).toFixed(1);
                                    return `${context.label}: ${context.raw.toFixed(2)} ₽ (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    </script>
</body>
</html>
''', stats=stats, category_stats=category_stats, categories=EXPENSE_CATEGORIES,
                                  income_stats=income_stats, balance=balance, period=period,
                                  period_name=period_names.get(period, 'за месяц'))


@app.context_processor
def utility_processor():
    return {'now': datetime.now}


if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)