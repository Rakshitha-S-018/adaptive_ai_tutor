from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import json
import time
import random

app = Flask(__name__)
app.secret_key = "adaptive_ai_tutor_secret_2024"

# ─────────────────────────────────────────────
#  DATABASE INIT
# ─────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            subject TEXT NOT NULL,
            score REAL DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            last_score REAL DEFAULT 0,
            best_score REAL DEFAULT 0,
            total_time INTEGER DEFAULT 0,
            difficulty_level INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            subject TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            accuracy REAL NOT NULL,
            difficulty INTEGER NOT NULL,
            time_taken INTEGER NOT NULL,
            completed_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ─────────────────────────────────────────────
#  ADAPTIVE QUESTION BANK
# ─────────────────────────────────────────────

QUESTION_BANK = {
    "aptitude": {
        1: [  # Easy
            {"q": "What is 15% of 200?", "opts": ["20", "25", "30", "35"], "ans": "30"},
            {"q": "If 5 apples cost ₹25, what do 8 apples cost?", "opts": ["₹35", "₹40", "₹45", "₹50"], "ans": "₹40"},
            {"q": "A train travels 60 km/h for 2 hours. Distance covered?", "opts": ["100 km", "110 km", "120 km", "130 km"], "ans": "120 km"},
            {"q": "Convert 3/4 to percentage.", "opts": ["65%", "70%", "75%", "80%"], "ans": "75%"},
            {"q": "8 × 9 = ?", "opts": ["62", "70", "72", "74"], "ans": "72"},
        ],
        2: [  # Medium
            {"q": "A student scores 40 out of 50. What is the percentage?", "opts": ["60%", "70%", "80%", "90%"], "ans": "80%"},
            {"q": "Ratio of boys to girls is 3:2. If there are 30 boys, how many girls?", "opts": ["15", "18", "20", "25"], "ans": "20"},
            {"q": "A number increases from 100 to 120. Percentage increase?", "opts": ["10%", "15%", "20%", "25%"], "ans": "20%"},
            {"q": "₹500 divided in ratio 2:3. Second person gets?", "opts": ["₹200", "₹250", "₹300", "₹350"], "ans": "₹300"},
            {"q": "Cost price ₹100, selling price ₹120. Profit %?", "opts": ["10%", "15%", "20%", "25%"], "ans": "20%"},
        ],
        3: [  # Hard
            {"q": "A pipe fills a tank in 6 hours. Another empties in 8 hours. Net fill time?", "opts": ["20 hrs", "22 hrs", "24 hrs", "26 hrs"], "ans": "24 hrs"},
            {"q": "If 6 workers finish a job in 12 days, how many days for 9 workers?", "opts": ["6 days", "7 days", "8 days", "9 days"], "ans": "8 days"},
            {"q": "A car depreciates 20% per year. Value after 2 years if initial ₹1,00,000?", "opts": ["₹60,000", "₹64,000", "₹70,000", "₹72,000"], "ans": "₹64,000"},
            {"q": "Two trains 200m and 300m long cross each other in 20 sec going opposite at 40 & 60 km/h. Correct?", "opts": ["Yes", "No", "Partial", "Can't say"], "ans": "Yes"},
            {"q": "A number decreased by 20% becomes 80. Original number?", "opts": ["90", "95", "100", "120"], "ans": "100"},
        ]
    }
}

def get_questions_for_level(subject, level):
    bank = QUESTION_BANK.get(subject, {})
    questions = bank.get(level, bank.get(1, []))
    return random.sample(questions, min(5, len(questions)))

# ─────────────────────────────────────────────
#  DB HELPERS
# ─────────────────────────────────────────────

def get_user_progress(username):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    subjects = ["aptitude", "python", "html"]
    data = {}
    for sub in subjects:
        c.execute("SELECT score, attempts, last_score, best_score, total_time, difficulty_level FROM progress WHERE username=? AND subject=?", (username, sub))
        row = c.fetchone()
        if row:
            data[sub] = {"score": row[0], "attempts": row[1], "last_score": row[2], "best_score": row[3], "time": row[4], "level": row[5]}
        else:
            data[sub] = {"score": 0, "attempts": 0, "last_score": 0, "best_score": 0, "time": 0, "level": 1}
    conn.close()
    return data

def update_progress(username, subject, score, accuracy, time_taken, difficulty):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT id, score, attempts, best_score, total_time FROM progress WHERE username=? AND subject=?", (username, subject))
    row = c.fetchone()

    new_level = difficulty
    if accuracy >= 80:
        new_level = min(3, difficulty + 1)
    elif accuracy < 40:
        new_level = max(1, difficulty - 1)

    if row:
        avg_score = (row[1] * row[2] + accuracy) / (row[2] + 1)
        best = max(row[3], accuracy)
        c.execute("""UPDATE progress SET score=?, attempts=?, last_score=?, best_score=?, total_time=?, difficulty_level=?, updated_at=datetime('now')
                     WHERE username=? AND subject=?""",
                  (round(avg_score, 1), row[2] + 1, accuracy, best, row[4] + time_taken, new_level, username, subject))
    else:
        c.execute("""INSERT INTO progress (username, subject, score, attempts, last_score, best_score, total_time, difficulty_level)
                     VALUES (?,?,?,1,?,?,?,?)""",
                  (username, subject, accuracy, accuracy, accuracy, time_taken, new_level))

    c.execute("""INSERT INTO quiz_history (username, subject, score, total, accuracy, difficulty, time_taken)
                 VALUES (?,?,?,5,?,?,?)""",
              (username, subject, score, accuracy, difficulty, time_taken))

    conn.commit()
    conn.close()
    return new_level

def get_quiz_history(username):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""SELECT subject, score, total, accuracy, difficulty, time_taken, completed_at
                 FROM quiz_history WHERE username=? ORDER BY completed_at DESC LIMIT 20""", (username,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_leaderboard():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""SELECT p.username, ROUND(AVG(p.score),1) as avg_score, SUM(p.attempts) as total_attempts
                 FROM progress p GROUP BY p.username ORDER BY avg_score DESC LIMIT 10""")
    rows = c.fetchall()
    conn.close()
    return rows

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('about.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        confirm = request.form.get('confirm_password', '')

        if not username or not password:
            error = "All fields are required."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 4:
            error = "Password must be at least 4 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            try:
                conn = sqlite3.connect("users.db")
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password) VALUES (?,?)", (username, password))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = "Username already exists. Please choose another."

    return render_template('signup.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid username or password."
    return render_template('login.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    data = get_user_progress(user)
    history = get_quiz_history(user)
    overall = round(sum(d['score'] for d in data.values()) / 3, 1)
    total_attempts = sum(d['attempts'] for d in data.values())
    return render_template('dashboard.html', user=user, data=data, overall=overall, total_attempts=total_attempts, history=history[:5])

@app.route('/courses')
def courses():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    data = get_user_progress(user)
    return render_template('courses.html', data=data)

@app.route('/aptitude', methods=['GET', 'POST'])
def aptitude():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    data = get_user_progress(user)
    level = data['aptitude']['level']

    if request.method == 'POST' and request.form.get('action') == 'start':
        questions = get_questions_for_level('aptitude', level)
        session['apt_questions'] = questions
        session['apt_index'] = 0
        session['apt_score'] = 0
        session['apt_start'] = int(time.time())
        session['apt_level'] = level
        session['quiz_started'] = True
        return redirect(url_for('aptitude'))

    if session.get('quiz_started'):
        index = session.get('apt_index', 0)
        questions = session.get('apt_questions', [])

        if request.method == 'POST' and request.form.get('answer'):
            selected = request.form.get('answer')
            if selected == questions[index]['ans']:
                session['apt_score'] += 1
            session['apt_index'] = index + 1
            index += 1

        if index >= len(questions):
            final_score = session['apt_score']
            accuracy = round((final_score / len(questions)) * 100, 1)
            time_taken = int(time.time()) - session.get('apt_start', int(time.time()))
            new_level = update_progress(user, 'aptitude', final_score, accuracy, time_taken, session.get('apt_level', 1))

            for k in ['quiz_started', 'apt_questions', 'apt_index', 'apt_score', 'apt_start', 'apt_level']:
                session.pop(k, None)

            return render_template('result.html',
                                   score=final_score,
                                   total=len(questions),
                                   accuracy=accuracy,
                                   time_taken=time_taken,
                                   new_level=new_level,
                                   subject="Aptitude")

        question = questions[index]
        return render_template('aptitude.html',
                               question=question,
                               index=index + 1,
                               total=len(questions),
                               level=level,
                               quiz_started=True)

    return render_template('aptitude.html', level=level, quiz_started=False, data=data)

@app.route('/python_course')
def python_course():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('commingsoon.html', course="Python Programming")

@app.route('/html_course')
def html_course():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('commingsoon.html', course="HTML & Web Dev")

@app.route('/progress')
def progress():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    data = get_user_progress(user)
    history = get_quiz_history(user)
    overall = round(sum(d['score'] for d in data.values()) / 3, 1)
    return render_template('progress.html', data=data, overall_score=overall, history=history)

@app.route('/analytics')
def analytics():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    data = get_user_progress(user)
    history = get_quiz_history(user)
    return render_template('analytics.html', data=data, history=history)

@app.route('/weak')
def weak():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    data = get_user_progress(user)

    weak_subjects = []
    strong_subjects = []

    subject_meta = {
        "aptitude": {"icon": "🧠", "resources": ["Khan Academy Arithmetic", "IndiaBix Aptitude", "RS Aggarwal Book"]},
        "python":   {"icon": "🐍", "resources": ["Python.org Tutorial", "W3Schools Python", "Automate the Boring Stuff"]},
        "html":     {"icon": "💻", "resources": ["MDN Web Docs", "W3Schools HTML", "FreeCodeCamp HTML"]},
    }

    for subj, details in data.items():
        meta = subject_meta.get(subj, {})
        entry = {
            "name": subj.capitalize(),
            "icon": meta.get("icon", "📚"),
            "score": details["score"],
            "attempts": details["attempts"],
            "level": details["level"],
            "resources": meta.get("resources", [])
        }
        if details["attempts"] > 0 and details["score"] < 60:
            entry["tip"] = get_ai_tip(subj, details["score"])
            weak_subjects.append(entry)
        elif details["attempts"] > 0:
            strong_subjects.append(entry)

    return render_template('weak.html', weak_subjects=weak_subjects, strong_subjects=strong_subjects)

def get_ai_tip(subject, score):
    tips = {
        "aptitude": [
            "Focus on percentage and ratio fundamentals. Practice 15 problems daily.",
            "Work on speed — use mental math tricks for multiplication.",
            "Review time & work, profit & loss formulas systematically.",
        ],
        "python": [
            "Review Python data types and basic syntax with hands-on coding.",
            "Practice list comprehensions and functions with small projects.",
            "Focus on loops and conditionals using HackerRank beginner challenges.",
        ],
        "html": [
            "Build simple static pages — 3 pages per day for practice.",
            "Learn Flexbox and Grid layout thoroughly.",
            "Study semantic HTML5 elements and forms.",
        ]
    }
    return random.choice(tips.get(subject, ["Keep practicing regularly!"]))

@app.route('/leaderboard')
def leaderboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    board = get_leaderboard()
    return render_template('leaderboard.html', board=board, current_user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
