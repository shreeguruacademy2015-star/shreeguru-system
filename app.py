import os
import shutil
from datetime import date, datetime
from flask import Flask, redirect, render_template_string, request, send_file, send_from_directory, url_for, session, Response
from werkzeug.utils import secure_filename
import io
import csv
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_complete_bulletproof_v45_cloud_neon"

# --- NEON CLOUD DATABASE CONNECTION ---
DATABASE_URL = os.environ.get("DATABASE_URL")

DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
UPLOAD_FOLDER = os.path.join(DESKTOP_PATH, "student_photos")
DOCS_FOLDER = os.path.join(DESKTOP_PATH, "student_documents")
BACKUP_FOLDER = os.path.join(DESKTOP_PATH, "shreeguru_auto_backups")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOCS_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOCS_FOLDER'] = DOCS_FOLDER

def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == "": return default
        return float(val)
    except: return default

def safe_int(val, default=0):
    try:
        if val is None or str(val).strip() == "": return default
        return int(val)
    except: return default

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def log_staff_activity(role_name, act_text):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                cur.execute("INSERT INTO staff_activity_log (staff_role, act_time, activity_text) VALUES (%s, %s, %s)", (role_name, now_str, act_text))
                conn.commit()
    except Exception as e:
        print(f"Log Error: {e}")

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    role TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            """)
            cur.execute("INSERT INTO users (role, password) VALUES ('Admin', 'admin123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Manager', 'manager123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Clerk', 'clerk123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Trainer', 'trainer123') ON CONFLICT (role) DO NOTHING")

            cur.execute('''CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                opt_a TEXT NOT NULL,
                opt_b TEXT NOT NULL,
                opt_c TEXT NOT NULL,
                opt_d TEXT NOT NULL,
                correct TEXT NOT NULL
            )''')

            cur.execute('SELECT COUNT(*) as count FROM questions')
            res = cur.fetchone()
            if res['count'] == 0:
                default_qs = [
                    ("महाराष्ट्राची राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B"),
                    ("क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A"),
                    ("स्वराज्य स्थापना कोणी केली?", "छत्रपती संभाजी महाराज", "छत्रपती शिवाजी महाराज", "महात्मा ज्योतिराव फुले", "संत ज्ञानेश्वर", "B"),
                    ("भारताचे राष्ट्रगीत 'जन गण मन' कोणी लिहिले?", "बंकिमचंद्र चटर्जी", "रविंद्रनाथ टागोर", "महात्मा गांधी", "लोकमान्य टिळक", "B"),
                    ("महाराष्ट्रात एकूण किती जिल्हे आहेत?", "३४", "३५", "३६", "३७", "C")
                ]
                cur.executemany('INSERT INTO questions (question, opt_a, opt_b, opt_c, opt_d, correct) VALUES (%s, %s, %s, %s, %s, %s)', default_qs)
                conn.commit()

            cur.execute('''CREATE TABLE IF NOT EXISTS books (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                category TEXT,
                total_copies INTEGER DEFAULT 1,
                available_copies INTEGER DEFAULT 1
            )''')

            cur.execute('''CREATE TABLE IF NOT EXISTS book_issues (
                id SERIAL PRIMARY KEY,
                book_id INTEGER,
                student_id INTEGER,
                student_name TEXT,
                issue_date TEXT,
                return_date TEXT,
                status TEXT DEFAULT 'Issued'
            )''')

            cur.execute('''CREATE TABLE IF NOT EXISTS study_lab_seats (
                id SERIAL PRIMARY KEY,
                seat_number TEXT NOT NULL,
                shift TEXT NOT NULL,
                student_id INTEGER,
                student_name TEXT,
                status TEXT DEFAULT 'Available'
            )''')

            cur.execute("""
                CREATE TABLE IF NOT EXISTS staff_activity_log (
                    id SERIAL PRIMARY KEY,
                    staff_role TEXT NOT NULL,
                    act_time TEXT NOT NULL,
                    activity_text TEXT NOT NULL,
                    admin_reply TEXT DEFAULT ''
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS staff_requests (
                    id SERIAL PRIMARY KEY,
                    req_role TEXT NOT NULL,
                    req_date TEXT NOT NULL,
                    request_title TEXT NOT NULL,
                    request_details TEXT NOT NULL,
                    status TEXT DEFAULT 'प्रलंबित (Pending)'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    dob TEXT,
                    gender TEXT,
                    category TEXT,
                    height TEXT,
                    weight TEXT,
                    chest TEXT,
                    course TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    parent_phone TEXT,
                    address TEXT,
                    hostel_needed TEXT DEFAULT 'नाही',
                    total_fees REAL DEFAULT 0,
                    paid_fees REAL DEFAULT 0,
                    photo_filename TEXT,
                    admission_form_scan TEXT,
                    admission_date TEXT NOT NULL,
                    diet_plan TEXT,
                    admin_remark TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id SERIAL PRIMARY KEY,
                    person_type TEXT NOT NULL,
                    person_id INTEGER NOT NULL,
                    att_type TEXT NOT NULL,
                    att_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    marked_by TEXT DEFAULT 'Staff'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS hostel_mess_fees (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER,
                    package_type TEXT,
                    from_month TEXT,
                    to_month TEXT,
                    total_amount REAL DEFAULT 0,
                    paid_amount REAL DEFAULT 0,
                    pay_date TEXT,
                    logged_by TEXT DEFAULT 'Clerk'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS physical_tests (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER,
                    test_date TEXT,
                    run_time TEXT,
                    sprint_time TEXT,
                    shot_put_dist TEXT,
                    pullups INTEGER DEFAULT 0,
                    total_obtained REAL DEFAULT 0,
                    logged_by TEXT DEFAULT 'Staff'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS written_tests (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER,
                    test_date TEXT,
                    test_name TEXT,
                    subject TEXT,
                    total_marks REAL DEFAULT 100,
                    obtained_marks REAL DEFAULT 0,
                    logged_by TEXT DEFAULT 'Staff'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS trainer_practice_log (
                    id SERIAL PRIMARY KEY,
                    log_date TEXT NOT NULL,
                    session_time TEXT NOT NULL,
                    ground_status TEXT NOT NULL,
                    workout_details TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS injuries (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    injury_date TEXT NOT NULL,
                    injury_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    rest_days INTEGER DEFAULT 0
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS staff (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    salary REAL DEFAULT 0,
                    advance_paid REAL DEFAULT 0,
                    joining_date TEXT,
                    total_leaves INTEGER DEFAULT 0
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    exp_date TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    logged_by TEXT DEFAULT 'Clerk'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS kit_distribution (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    item_details TEXT NOT NULL,
                    issue_date TEXT NOT NULL,
                    logged_by TEXT DEFAULT 'Clerk'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS discipline_records (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    record_type TEXT NOT NULL,
                    record_date TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS mess_diet (
                    id SERIAL PRIMARY KEY,
                    day_name TEXT NOT NULL UNIQUE,
                    breakfast TEXT,
                    lunch TEXT,
                    dinner TEXT,
                    special_diet TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS staff_tasks (
                    id SERIAL PRIMARY KEY,
                    target_role TEXT NOT NULL,
                    task_text TEXT NOT NULL,
                    task_date TEXT NOT NULL,
                    status TEXT DEFAULT 'Unseen'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS canteen_staff_list (
                    id SERIAL PRIMARY KEY,
                    staff_name TEXT NOT NULL,
                    work_role TEXT NOT NULL
                )
            """)
            cur.execute("INSERT INTO canteen_staff_list (id, staff_name, work_role) VALUES (1, 'सुरेखा ताई', 'मुख्य स्वयंपाक') ON CONFLICT (id) DO NOTHING")
            cur.execute("INSERT INTO canteen_staff_list (id, staff_name, work_role) VALUES (2, 'सुनीता ताई', 'चपाती व भांडी') ON CONFLICT (id) DO NOTHING")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS kitchen_staff_att (
                    id SERIAL PRIMARY KEY,
                    staff_name TEXT NOT NULL,
                    att_date TEXT NOT NULL,
                    session_time TEXT NOT NULL,
                    day_name TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS student_care_log (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    care_date TEXT NOT NULL,
                    issue_details TEXT NOT NULL,
                    special_diet_note TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS admission_inquiries (
                    id SERIAL PRIMARY KEY,
                    inquiry_date TEXT NOT NULL,
                    student_name TEXT NOT NULL,
                    district TEXT NOT NULL,
                    taluka TEXT,
                    phone TEXT NOT NULL,
                    course TEXT NOT NULL,
                    hostel_interest TEXT DEFAULT 'होय',
                    call_status TEXT DEFAULT 'नवीन चौकशी (New)',
                    staff_note TEXT DEFAULT ''
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS mock_test_leads (
                    id SERIAL PRIMARY KEY,
                    test_date TEXT NOT NULL,
                    student_name TEXT NOT NULL,
                    district TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    total_marks INTEGER NOT NULL,
                    test_name TEXT NOT NULL,
                    call_status TEXT DEFAULT 'नवीन टेस्ट निकाल',
                    staff_note TEXT DEFAULT ''
                )
            """)

            days = ['सोमवार', 'मंगळवार', 'बुधवार', 'गुरुवार', 'शुक्रवार', 'शनिवार', 'रविवार']
            for d in days:
                cur.execute("INSERT INTO mess_diet (day_name, breakfast, lunch, dinner, special_diet) VALUES (%s, 'पोहे / उपमा', 'डाळ, भात, चपाती, उसळ', 'भाकरी, सुकी भाजी, आमटी', 'दूध, केळी, भिजवलेले हरभरे-गूळ') ON CONFLICT (day_name) DO NOTHING", (d,))

            conn.commit()

init_db()

# ----------------- COMMON FUNCTIONAL HANDLERS -----------------

@app.route('/toggle_lang')
def toggle_lang():
    cur = session.get('site_lang', 'mr')
    session['site_lang'] = 'en' if cur == 'mr' else 'mr'
    return redirect(request.referrer or '/')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY id ASC")
            users_list = cur.fetchall()
    if request.method == 'POST':
        role = request.form.get('role')
        pwd = request.form.get('password')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE role=%s AND password=%s", (role, pwd))
                user = cur.fetchone()
        if user:
            session['user_role'] = role
            session['role'] = role
            log_staff_activity(role, "सिस्टीममध्ये लॉगिन केले")
            if role == 'Manager': return redirect('/manager')
            elif role == 'Trainer': return redirect('/trainer')
            elif role == 'Clerk': return redirect('/clerk')
            else: return redirect('/admin')
        else:
            error = "Invalid Password!" if lang == 'en' else "चुकीचा पासवर्ड! पुन्हा प्रयत्न करा."
    return render_template_string(LOGIN_HTML, error=error, lang=lang, users_list=users_list)

@app.route('/logout')
def logout():
    role = session.get('user_role', 'Unknown')
    log_staff_activity(role, "सिस्टीममधून लॉगआउट झाले")
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def root():
    role = session.get('user_role')
    if not role: return redirect(url_for('login'))
    if role == 'Manager': return redirect('/manager')
    elif role == 'Trainer': return redirect('/trainer')
    elif role == 'Clerk': return redirect('/clerk')
    else: return redirect('/admin')

# ----------------- ADMIN ROUTES -----------------
@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'students')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students ORDER BY id DESC")
            students = cur.fetchall()
            cur.execute("SELECT * FROM expenses ORDER BY id DESC")
            expenses_list = cur.fetchall()
            cur.execute("SELECT * FROM users ORDER BY id ASC")
            users_list = cur.fetchall()
            cur.execute("SELECT * FROM mess_diet ORDER BY id ASC")
            diet_list = cur.fetchall()
            cur.execute("SELECT * FROM staff ORDER BY id DESC")
            staff_members = cur.fetchall()
            cur.execute("SELECT * FROM staff_tasks ORDER BY id DESC")
            staff_tasks = cur.fetchall()
            cur.execute("SELECT * FROM staff_requests ORDER BY id DESC")
            all_requests = cur.fetchall()
            cur.execute("SELECT * FROM staff_activity_log ORDER BY id DESC LIMIT 50")
            all_staff_logs = cur.fetchall()
            cur.execute("SELECT d.*, s.name FROM discipline_records d JOIN students s ON d.student_id = s.id ORDER BY d.id DESC")
            discipline_logs = cur.fetchall()
            cur.execute("SELECT h.*, s.name FROM hostel_mess_fees h JOIN students s ON h.student_id = s.id ORDER BY h.id DESC")
            hostel_logs = cur.fetchall()
            cur.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC")
            physical_records = cur.fetchall()
            cur.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC")
            written_records = cur.fetchall()

    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    total_expenses = sum(safe_float(ex['amount']) for ex in expenses_list)

    return render_template_string(ADMIN_DASHBOARD_LAYOUT, curr_tab=curr_tab, students=students, expenses_list=expenses_list, users_list=users_list, diet_list=diet_list, staff_members=staff_members, staff_tasks=staff_tasks, all_requests=all_requests, all_staff_logs=all_staff_logs, discipline_logs=discipline_logs, hostel_logs=hostel_logs, physical_records=physical_records, written_records=written_records, total_paid=total_paid, total_pending=total_pending, total_expenses=total_expenses, today_date=today_date, lang=lang)

# ----------------- MANAGER ROUTES -----------------
@app.route('/manager')
def manager_view():
    if session.get('user_role') != 'Manager': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'grocery')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students ORDER BY id DESC")
            students = cur.fetchall()
            cur.execute("SELECT * FROM mess_diet ORDER BY id ASC")
            diet_list = cur.fetchall()
            cur.execute("SELECT * FROM canteen_staff_list ORDER BY id ASC")
            canteen_staff = cur.fetchall()
            cur.execute("SELECT * FROM staff_tasks ORDER BY id DESC")
            staff_tasks = cur.fetchall()
            cur.execute("SELECT * FROM staff_requests WHERE req_role='Manager' ORDER BY id DESC")
            my_requests = cur.fetchall()
            cur.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC")
            physical_records = cur.fetchall()
            cur.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC")
            written_records = cur.fetchall()
    return render_template_string(MANAGER_LAYOUT, curr_tab=curr_tab, students=students, diet_list=diet_list, canteen_staff=canteen_staff, staff_tasks=staff_tasks, my_requests=my_requests, physical_records=physical_records, written_records=written_records, today_date=today_date, lang=lang)

# ----------------- TRAINER ROUTES -----------------
@app.route('/trainer')
def trainer_view():
    if session.get('user_role') != 'Trainer': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'practice')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students ORDER BY id DESC")
            students = cur.fetchall()
            cur.execute("SELECT * FROM staff_tasks ORDER BY id DESC")
            staff_tasks = cur.fetchall()
            cur.execute("SELECT * FROM staff_requests WHERE req_role='Trainer' ORDER BY id DESC")
            my_requests = cur.fetchall()
            cur.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC")
            physical_records = cur.fetchall()
            cur.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC")
            written_records = cur.fetchall()
            cur.execute("SELECT sc.*, s.name FROM student_care_log sc JOIN students s ON sc.student_id = s.id WHERE sc.issue_details='ट्रेनर डाएट शिफारस' ORDER BY sc.id DESC")
            trainer_diet_logs = cur.fetchall()
            cur.execute("SELECT i.*, s.name FROM injuries i JOIN students s ON i.student_id = s.id ORDER BY i.id DESC")
            trainer_injury_logs = cur.fetchall()
    return render_template_string(TRAINER_LAYOUT, curr_tab=curr_tab, students=students, staff_tasks=staff_tasks, my_requests=my_requests, physical_records=physical_records, written_records=written_records, trainer_diet_logs=trainer_diet_logs, trainer_injury_logs=trainer_injury_logs, today_date=today_date, lang=lang)

# ----------------- CLERK ROUTES -----------------
@app.route('/clerk')
def clerk_view():
    if session.get('user_role') != 'Clerk': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'stud')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students ORDER BY id DESC")
            students = cur.fetchall()
            cur.execute("SELECT * FROM staff_tasks ORDER BY id DESC")
            staff_tasks = cur.fetchall()
            cur.execute("SELECT * FROM expenses ORDER BY id DESC")
            expenses_list = cur.fetchall()
            cur.execute("SELECT k.*, s.name FROM kit_distribution k JOIN students s ON k.student_id = s.id ORDER BY k.id DESC")
            kit_logs = cur.fetchall()
            cur.execute("SELECT * FROM staff_requests WHERE req_role='Clerk' ORDER BY id DESC")
            my_requests = cur.fetchall()
            cur.execute("SELECT h.*, s.name FROM hostel_mess_fees h JOIN students s ON h.student_id = s.id ORDER BY h.id DESC")
            hostel_logs = cur.fetchall()
            cur.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC")
            physical_records = cur.fetchall()
            cur.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC")
            written_records = cur.fetchall()
    return render_template_string(CLERK_LAYOUT, curr_tab=curr_tab, students=students, staff_tasks=staff_tasks, expenses_list=expenses_list, kit_logs=kit_logs, my_requests=my_requests, hostel_logs=hostel_logs, physical_records=physical_records, written_records=written_records, today_date=today_date, lang=lang)

# ----------------- OPERATIONS: STUDENT & FEES -----------------
@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form.get('name')
    adm_date = request.form.get('admission_date', date.today().strftime("%Y-%m-%d"))
    course = request.form.get('course', 'पोलीस भरती')
    phone = request.form.get('phone', '')
    parent_phone = request.form.get('parent_phone', '')
    total_fees = safe_float(request.form.get('total_fees'))
    paid_fees = safe_float(request.form.get('paid_fees'))
    photo = request.files.get('photo')
    photo_name = None
    if photo and photo.filename != '':
        fname = secure_filename(f"{int(datetime.now().timestamp())}_{photo.filename}")
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        photo_name = fname

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO students (name, admission_date, course, phone, parent_phone, total_fees, paid_fees, photo_filename)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, adm_date, course, phone, parent_phone, total_fees, paid_fees, photo_name))
            conn.commit()

    role = session.get('user_role', 'Clerk')
    log_staff_activity(role, f"नवीन विद्यार्थी प्रवेश नोंदवला: {name} (फी: {paid_fees}/{total_fees})")
    return redirect(request.referrer or '/')

@app.route('/pay_installment', methods=['POST'])
def pay_installment():
    sid = request.form.get('student_id')
    amount = safe_float(request.form.get('amount'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE students SET paid_fees = COALESCE(paid_fees, 0) + %s WHERE id = %s RETURNING name", (amount, sid))
            st = cur.fetchone()
            conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"फी हप्ता जमा केला: {st['name'] if st else sid} - ₹{amount}")
    return redirect(request.referrer or '/')

@app.route('/delete_student/<int:id>')
def delete_student(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM students WHERE id = %s", (id,))
            conn.commit()
    log_staff_activity('Admin', f"विद्यार्थी हटवला ID: {id}")
    return redirect(request.referrer or '/')

@app.route('/add_hostel_fee', methods=['POST'])
def add_hostel_fee():
    sid = request.form.get('student_id')
    amount = safe_float(request.form.get('paid_amount'))
    today = date.today().strftime("%Y-%m-%d")
    role = session.get('user_role', 'Staff')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO hostel_mess_fees (student_id, package_type, paid_amount, pay_date, logged_by)
                VALUES (%s, 'हॉस्टेल + मेस', %s, %s, %s)
            """, (sid, amount, today, role))
            conn.commit()
    log_staff_activity(role, f"हॉस्टेल/मेस फी जमा केली विद्यार्थी ID {sid} - ₹{amount}")
    return redirect(request.referrer or '/')

# ----------------- OPERATIONS: TESTS & PRACTICE -----------------
@app.route('/add_physical_record', methods=['POST'])
def add_physical_record():
    sid = request.form.get('student_id')
    t_date = request.form.get('test_date', date.today().strftime("%Y-%m-%d"))
    run_time = request.form.get('run_time', '')
    sprint_time = request.form.get('sprint_time', '')
    shot_put = request.form.get('shot_put_dist', '')
    pullups = safe_int(request.form.get('pullups'))
    tot = safe_float(request.form.get('total_obtained'))
    role = session.get('user_role', 'Staff')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO physical_tests (student_id, test_date, run_time, sprint_time, shot_put_dist, pullups, total_obtained, logged_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (sid, t_date, run_time, sprint_time, shot_put, pullups, tot, role))
            conn.commit()
    log_staff_activity(role, f"फिजिकल चाचणी गुण नोंदवले: विद्यार्थी ID {sid} - {tot}/50")
    return redirect(request.referrer or '/')

@app.route('/delete_physical_record/<int:id>')
def delete_physical_record(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM physical_tests WHERE id = %s", (id,))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/add_written_record', methods=['POST'])
def add_written_record():
    sid = request.form.get('student_id')
    t_date = request.form.get('test_date', date.today().strftime("%Y-%m-%d"))
    t_name = request.form.get('test_name', 'लेखी सराव टेस्ट')
    tot_marks = safe_float(request.form.get('total_marks', 100))
    obt_marks = safe_float(request.form.get('obtained_marks'))
    role = session.get('user_role', 'Staff')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO written_tests (student_id, test_date, test_name, total_marks, obtained_marks, logged_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (sid, t_date, t_name, tot_marks, obt_marks, role))
            conn.commit()
    log_staff_activity(role, f"लेखी परीक्षा गुण नोंदवले: विद्यार्थी ID {sid} - {obt_marks}/{tot_marks}")
    return redirect(request.referrer or '/')

@app.route('/delete_written_record/<int:id>')
def delete_written_record(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM written_tests WHERE id = %s", (id,))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/save_trainer_practice', methods=['POST'])
def save_trainer_practice():
    session_time = request.form.get('session_time')
    status = request.form.get('ground_status')
    details = request.form.get('workout_details')
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trainer_practice_log (log_date, session_time, ground_status, workout_details)
                VALUES (%s, %s, %s, %s)
            """, (t_date, session_time, status, details))
            conn.commit()
    log_staff_activity("Trainer", f"मैदानी सराव नोंद: {session_time} - {status} ({details})")
    return redirect(request.referrer or '/')

@app.route('/save_trainer_student_diet', methods=['POST'])
def save_trainer_student_diet():
    sid = request.form.get('student_id')
    diet_text = request.form.get('diet_text')
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO student_care_log (student_id, care_date, issue_details, special_diet_note)
                VALUES (%s, %s, 'ट्रेनर डाएट शिफारस', %s)
            """, (sid, t_date, diet_text))
            conn.commit()
    log_staff_activity("Trainer", f"डाएट शिफारस दिली विद्यार्थी ID: {sid} - {diet_text}")
    return redirect(request.referrer or '/')

@app.route('/add_injury', methods=['POST'])
def add_injury():
    sid = request.form.get('student_id')
    i_type = request.form.get('injury_type')
    r_days = safe_int(request.form.get('rest_days', 0))
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO injuries (student_id, injury_date, injury_type, severity, rest_days)
                VALUES (%s, %s, %s, 'मध्यम', %s)
            """, (sid, t_date, i_type, r_days))
            conn.commit()
    log_staff_activity("Trainer", f"इजा नोंदवली विद्यार्थी ID: {sid} - {i_type} ({r_days} दिवस सुट्टी)")
    return redirect(request.referrer or '/')

@app.route('/save_coach_attendance', methods=['POST'])
def save_coach_attendance():
    att_type = request.form.get('att_type', 'मैदानी हजेरी')
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students")
            studs = cur.fetchall()
            for s in studs:
                st = request.form.get(f"status_{s['id']}", "हजर")
                cur.execute("""
                    INSERT INTO attendance (person_type, person_id, att_type, att_date, status, marked_by)
                    VALUES ('Student', %s, %s, %s, %s, 'Trainer')
                """, (s['id'], att_type, t_date, st))
            conn.commit()
    log_staff_activity("Trainer", f"{att_type} हजेरी नोंदवली तारीख {t_date}")
    return redirect(request.referrer or '/')

# ----------------- OPERATIONS: CANTEEN & MANAGER -----------------
@app.route('/update_diet/<int:id>', methods=['POST'])
def update_diet(id):
    bf = request.form.get('breakfast')
    lu = request.form.get('lunch')
    di = request.form.get('dinner')
    sd = request.form.get('special_diet')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE mess_diet SET breakfast=%s, lunch=%s, dinner=%s, special_diet=%s WHERE id=%s
            """, (bf, lu, di, sd, id))
            conn.commit()
    role = session.get('user_role', 'Manager')
    log_staff_activity(role, f"मेस डाएट वेळापत्रक अपडेट केले ID {id}")
    return redirect(request.referrer or '/')

@app.route('/add_canteen_staff', methods=['POST'])
def add_canteen_staff():
    name = request.form.get('staff_name')
    role = request.form.get('work_role')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO canteen_staff_list (staff_name, work_role) VALUES (%s, %s)", (name, role))
            conn.commit()
    log_staff_activity("Manager", f"नवीन स्वयंपाकी कर्मचारी जोडले: {name}")
    return redirect(request.referrer or '/')

@app.route('/delete_canteen_staff/<int:id>')
def delete_canteen_staff(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM canteen_staff_list WHERE id=%s", (id,))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/save_kitchen_att_dynamic', methods=['POST'])
def save_kitchen_att_dynamic():
    att_date = request.form.get('att_date', date.today().strftime("%Y-%m-%d"))
    session_time = request.form.get('session_time', 'सकाळ सत्र')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM canteen_staff_list")
            c_staff = cur.fetchall()
            for cs in c_staff:
                st = request.form.get(f"status_{cs['id']}", 'हजर')
                cur.execute("""
                    INSERT INTO kitchen_staff_att (staff_name, att_date, session_time, day_name, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (cs['staff_name'], att_date, session_time, date.today().strftime("%A"), st))
            conn.commit()
    log_staff_activity("Manager", f"किचन स्टाफ हजेरी नोंदवली: {att_date} ({session_time})")
    return redirect(request.referrer or '/')

@app.route('/add_care_log', methods=['POST'])
def add_care_log():
    sid = request.form.get('student_id')
    issue = request.form.get('issue_details')
    diet_note = request.form.get('special_diet_note', '')
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO student_care_log (student_id, care_date, issue_details, special_diet_note)
                VALUES (%s, %s, %s, %s)
            """, (sid, t_date, issue, diet_note))
            conn.commit()
    log_staff_activity("Manager", f"हॉस्टेल विद्यार्थी काळजी नोंद: विद्यार्थी ID {sid} - {issue}")
    return redirect(request.referrer or '/')

@app.route('/print_grocery_slip', methods=['POST'])
def print_grocery_slip():
    items = request.form.getlist('items')
    item_rows = []
    for it in items:
        qty = request.form.get(f"qty_{it}", "")
        item_rows.append({"name": it, "qty": qty})
    t_date = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    html = f'''<!DOCTYPE html>
    <html lang="mr"><head><meta charset="UTF-8"><title>कॅन्टीन किराणा स्लिप</title>
    <style>body {{ font-family:sans-serif; padding:25px; }} table {{ width:100%; border-collapse:collapse; margin-top:15px; }} th, td {{ border:1px solid #000; padding:8px; text-align:left; }}</style></head>
    <body onload="window.print()">
        <h2 style="text-align:center; margin:0;">श्रीगुरु करिअर अकॅडमी, आडूर</h2>
        <h4 style="text-align:center; margin:5px 0;">कॅन्टीन किराणा, भाजीपाला व डाएट खरेदी पावती</h4>
        <p style="text-align:center; font-size:12px;">दिनांक: {t_date}</p><hr>
        <table>
            <thead><tr><th>अ.क्र.</th><th>साहित्य / वस्तूचे नाव</th><th>प्रमाण / नग</th></tr></thead>
            <tbody>
                {''.join([f"<tr><td>{idx+1}</td><td><b>{r['name']}</b></td><td>{r['qty'] or '-'}</td></tr>" for idx, r in enumerate(item_rows)])}
            </tbody>
        </table>
        <br><br><div style="display:flex; justify-content:space-between;"><p>व्यवस्थापिका सही: _________</p><p>दुकानदार सही: _________</p></div>
    </body></html>'''
    return render_template_string(html)

@app.route('/whatsapp_grocery_slip', methods=['POST'])
def whatsapp_grocery_slip():
    items = request.form.getlist('items')
    msg = f"*श्रीगुरु करिअर अकॅडमी - कॅन्टीन खरेदी स्लिप*\nदिनांक: {datetime.now().strftime('%d-%m-%Y')}\n\n"
    for idx, it in enumerate(items, 1):
        qty = request.form.get(f"qty_{it}", "")
        msg += f"{idx}. {it}: {qty or '-'}\n"
    msg += "\nकृपया हे साहित्य तातडीने पाठवून द्यावे."
    return redirect("https://wa.me/?text=" + urllib.parse.quote(msg))

# ----------------- OPERATIONS: CLERK & EXPENSES -----------------
@app.route('/add_expense', methods=['POST'])
def add_expense():
    cat = request.form.get('category')
    amt = safe_float(request.form.get('amount'))
    desc = request.form.get('description')
    t_date = date.today().strftime("%Y-%m-%d")
    role = session.get('user_role', 'Staff')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO expenses (exp_date, category, description, amount, logged_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (t_date, cat, desc, amt, role))
            conn.commit()
    log_staff_activity(role, f"खर्च नोंदवला: {cat} - ₹{amt} ({desc})")
    return redirect(request.referrer or '/')

@app.route('/add_kit_distribution', methods=['POST'])
def add_kit_distribution():
    sid = request.form.get('student_id')
    items = request.form.get('item_details')
    t_date = date.today().strftime("%Y-%m-%d")
    role = session.get('user_role', 'Staff')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kit_distribution (student_id, item_details, issue_date, logged_by)
                VALUES (%s, %s, %s, %s)
            """, (sid, items, t_date, role))
            conn.commit()
    log_staff_activity(role, f"किट वाटप केले: विद्यार्थी ID {sid} - {items}")
    return redirect(request.referrer or '/')

# ----------------- OPERATIONS: STAFF REQUESTS & TASKS -----------------
@app.route('/send_staff_request', methods=['POST'])
def send_staff_request():
    role = session.get('user_role', 'Staff')
    title = request.form.get('request_title')
    details = request.form.get('request_details')
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO staff_requests (req_role, req_date, request_title, request_details)
                VALUES (%s, %s, %s, %s)
            """, (role, t_date, title, details))
            conn.commit()
    log_staff_activity(role, f"संचालकांना विनंती पाठवली: {title}")
    return redirect(request.referrer or '/')

@app.route('/handle_request/<int:id>/<action>')
def handle_request(id, action):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff_requests SET status = %s WHERE id = %s", (action, id))
            conn.commit()
    log_staff_activity('Admin', f"विनंतीवर निर्णय: ID {id} - {action}")
    return redirect(request.referrer or '/')

@app.route('/assign_task', methods=['POST'])
def assign_task():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    target = request.form.get('target_role')
    text = request.form.get('task_text')
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO staff_tasks (target_role, task_text, task_date)
                VALUES (%s, %s, %s)
            """, (target, text, t_date))
            conn.commit()
    log_staff_activity('Admin', f"स्टाफला काम नेमून दिले: {target} - {text}")
    return redirect(request.referrer or '/')

@app.route('/mark_task_seen/<int:id>')
def mark_task_seen(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff_tasks SET status='Seen' WHERE id=%s", (id,))
            conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"संचालकांची सूचना वाचली (Task ID: {id})")
    return redirect(request.referrer or '/')

@app.route('/edit_staff_task/<int:id>', methods=['POST'])
def edit_staff_task(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    target = request.form.get('target_role')
    text = request.form.get('task_text')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff_tasks SET target_role=%s, task_text=%s WHERE id=%s", (target, text, id))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/delete_staff_task/<int:id>')
def delete_staff_task(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM staff_tasks WHERE id=%s", (id,))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/reply_staff_activity/<int:id>', methods=['POST'])
def reply_staff_activity(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    reply = request.form.get('admin_reply')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff_activity_log SET admin_reply=%s WHERE id=%s", (reply, id))
            conn.commit()
    return redirect(request.referrer or '/')

# ----------------- OPERATIONS: DISCIPLINE & GATEPASS -----------------
@app.route('/add_discipline', methods=['POST'])
def add_discipline():
    sid = request.form.get('student_id')
    r_type = request.form.get('record_type')
    reason = request.form.get('reason')
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO discipline_records (student_id, record_type, record_date, reason)
                VALUES (%s, %s, %s, %s)
            """, (sid, r_type, t_date, reason))
            conn.commit()
    log_staff_activity('Admin', f"{r_type} नोंदवली: विद्यार्थी ID {sid} - {reason}")
    return redirect(request.referrer or '/')

@app.route('/edit_discipline/<int:id>', methods=['POST'])
def edit_discipline(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    r_type = request.form.get('record_type')
    reason = request.form.get('reason')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE discipline_records SET record_type=%s, reason=%s WHERE id=%s", (r_type, reason, id))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/delete_discipline/<int:id>')
def delete_discipline(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM discipline_records WHERE id=%s", (id,))
            conn.commit()
    return redirect(request.referrer or '/')

# ----------------- OPERATIONS: STAFF SALARY & LEAVES -----------------
@app.route('/add_staff', methods=['POST'])
def add_staff():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    name = request.form.get('name')
    role = request.form.get('role')
    phone = request.form.get('phone')
    salary = safe_float(request.form.get('salary'))
    today = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO staff (name, role, phone, salary, advance_paid, joining_date, total_leaves)
                VALUES (%s, %s, %s, %s, 0, %s, 0)
            """, (name, role, phone, salary, today))
            conn.commit()
    log_staff_activity('Admin', f"नवीन स्टाफ नोंदवला: {name} ({role})")
    return redirect(request.referrer or '/')

@app.route('/update_staff_advance/<int:id>', methods=['POST'])
def update_staff_advance(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    amt = safe_float(request.form.get('advance_amount'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff SET advance_paid = COALESCE(advance_paid, 0) + %s WHERE id = %s RETURNING name", (amt, id))
            st = cur.fetchone()
            conn.commit()
    log_staff_activity('Admin', f"स्टाफ उचल नोंदवली: {st['name'] if st else id} - ₹{amt}")
    return redirect(request.referrer or '/')

@app.route('/add_staff_leave/<int:id>', methods=['POST'])
def add_staff_leave(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    days = safe_int(request.form.get('leave_days', 1))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff SET total_leaves = COALESCE(total_leaves, 0) + %s WHERE id = %s RETURNING name", (days, id))
            st = cur.fetchone()
            conn.commit()
    log_staff_activity('Admin', f"स्टाफ रजा नोंदवली: {st['name'] if st else id} - {days} दिवस")
    return redirect(request.referrer or '/')

@app.route('/pay_staff_salary/<int:id>', methods=['POST'])
def pay_staff_salary(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    amt = safe_float(request.form.get('amount'))
    from_d = request.form.get('from_date')
    to_d = request.form.get('to_date')
    t_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, role FROM staff WHERE id = %s", (id,))
            st = cur.fetchone()
            st_name = st['name'] if st else f"Staff-{id}"
            cur.execute("""
                INSERT INTO expenses (exp_date, category, description, amount, logged_by)
                VALUES (%s, 'स्टाफ पगार', %s, %s, 'Admin')
            """, (t_date, f"{st_name} पगार ({from_d} ते {to_d})", amt))
            cur.execute("UPDATE staff SET advance_paid = 0, total_leaves = 0 WHERE id = %s", (id,))
            conn.commit()
    log_staff_activity('Admin', f"{st_name} पगार अदा केला: ₹{amt} ({from_d} ते {to_d})")
    return redirect(request.referrer or '/')

@app.route('/delete_staff/<int:id>')
def delete_staff(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM staff WHERE id = %s", (id,))
            conn.commit()
    log_staff_activity('Admin', f"स्टाफ हटवला ID: {id}")
    return redirect(request.referrer or '/')

# ----------------- OPERATIONS: SYSTEM USERS & PASSWORDS -----------------
@app.route('/add_new_system_user', methods=['POST'])
def add_new_system_user():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    role = request.form.get('new_role')
    pwd = request.form.get('new_password')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (role, password) VALUES (%s, %s) ON CONFLICT (role) DO UPDATE SET password=EXCLUDED.password", (role, pwd))
            conn.commit()
    log_staff_activity('Admin', f"नवीन सिस्टीम युजर जोडला: {role}")
    return redirect(request.referrer or '/')

@app.route('/change_password/<int:id>', methods=['POST'])
def change_password(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    pwd = request.form.get('new_password')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password = %s WHERE id = %s RETURNING role", (pwd, id))
            u = cur.fetchone()
            conn.commit()
    log_staff_activity('Admin', f"युजर पासवर्ड बदलला: {u['role'] if u else id}")
    return redirect(request.referrer or '/')

@app.route('/delete_system_user/<int:id>')
def delete_system_user(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s AND role NOT IN ('Admin', 'Manager', 'Clerk', 'Trainer')", (id,))
            conn.commit()
    return redirect(request.referrer or '/')

# ----------------- REPORTS & PRINTING -----------------
@app.route('/receipt/<int:id>')
def receipt(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE id = %s", (id,))
            s = cur.fetchone()
    if not s: return "Student not found", 404
    pending = safe_float(s['total_fees']) - safe_float(s['paid_fees'])
    html = f'''<!DOCTYPE html>
    <html lang="mr"><head><meta charset="UTF-8"><title>फी पावती - {s['name']}</title>
    <style>body {{ font-family:sans-serif; padding:30px; }} .box {{ border:2px solid #000; padding:20px; border-radius:8px; max-width:600px; margin:auto; }}</style></head>
    <body onload="window.print()">
        <div class="box">
            <h2 style="text-align:center; margin:0; color:#0b2545;">श्रीगुरु करिअर अकॅडमी</h2>
            <p style="text-align:center; margin:4px 0; font-size:13px;">पत्ता: आडूर, ता. करवीर, जि. कोल्हापूर | मो. ९९२११११९६०</p><hr>
            <h4 style="text-align:center; text-decoration:underline; margin:10px 0;">अधिकृत फी पावती</h4>
            <p><b>पावती क्र.:</b> RCP-{s['id']} &nbsp;&nbsp;&nbsp;&nbsp; <b>तारीख:</b> {date.today().strftime('%d-%m-%Y')}</p>
            <p><b>विद्यार्थ्याचे नाव:</b> {s['name']}</p>
            <p><b>कोर्स:</b> {s['course']} &nbsp;&nbsp;&nbsp;&nbsp; <b>मोबाईल:</b> {s['phone']}</p><hr>
            <table style="width:100%; font-size:14px;">
                <tr><td>एकूण ठरलेली फी:</td><td><b>₹{s['total_fees']}</b></td></tr>
                <tr><td>आजअखेर भरलेली फी:</td><td><b style="color:green;">₹{s['paid_fees']}</b></td></tr>
                <tr><td>शिल्लक फी:</td><td><b style="color:red;">₹{pending}</b></td></tr>
            </table><br><br><br>
            <div style="display:flex; justify-content:space-between;"><p>विद्यार्थी सही: _______</p><p>अधिकृत स्वाक्षरी: _______</p></div>
        </div>
    </body></html>'''
    return render_template_string(html)

@app.route('/student_report/<int:id>')
def student_report(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE id = %s", (id,))
            s = cur.fetchone()
            cur.execute("SELECT * FROM physical_tests WHERE student_id = %s ORDER BY id DESC", (id,))
            pts = cur.fetchall()
            cur.execute("SELECT * FROM written_tests WHERE student_id = %s ORDER BY id DESC", (id,))
            wts = cur.fetchall()
    if not s: return "Student not found", 404
    html = f'''<!DOCTYPE html>
    <html lang="mr"><head><meta charset="UTF-8"><title>प्रगती अहवाल - {s['name']}</title>
    <style>body {{ font-family:sans-serif; padding:25px; }} table {{ width:100%; border-collapse:collapse; margin-top:10px; }} th, td {{ border:1px solid #000; padding:6px; font-size:12px; }}</style></head>
    <body onload="window.print()">
        <h2 style="text-align:center; margin:0;">श्रीगुरु करिअर अकॅडमी, आडूर</h2>
        <h4 style="text-align:center; margin:5px 0;">विद्यार्थी संपूर्ण प्रगती व कामगिरी अहवाल</h4><hr>
        <p><b>नाव:</b> {s['name']} | <b>कोर्स:</b> {s['course']} | <b>मोबाईल:</b> {s['phone']} | <b>प्रवेश:</b> {s['admission_date']}</p>
        <h4>🏃‍♂️ फिजिकल चाचण्यांचा इतिहास:</h4>
        <table><thead><tr><th>तारीख</th><th>1600/800m</th><th>100m</th><th>गोळा</th><th>पुल-अप्स</th><th>एकूण गुण</th></tr></thead><tbody>
        {''.join([f"<tr><td>{p['test_date']}</td><td>{p['run_time']}</td><td>{p['sprint_time']}</td><td>{p['shot_put_dist']}</td><td>{p['pullups']}</td><td><b>{p['total_obtained']}/50</b></td></tr>" for p in pts]) or '<tr><td colspan="6">नोंद नाही.</td></tr>'}
        </tbody></table>
        <h4>📝 लेखी परीक्षांचा इतिहास:</h4>
        <table><thead><tr><th>तारीख</th><th>परीक्षेचे नाव</th><th>एकूण</th><th>मिळालेले गुण</th></tr></thead><tbody>
        {''.join([f"<tr><td>{w['test_date']}</td><td>{w['test_name']}</td><td>{w['total_marks']}</td><td><b>{w['obtained_marks']}</b></td></tr>" for w in wts]) or '<tr><td colspan="4">नोंद नाही.</td></tr>'}
        </tbody></table>
    </body></html>'''
    return render_template_string(html)

@app.route('/export_students_csv')
def export_students_csv():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, course, phone, parent_phone, admission_date, total_fees, paid_fees FROM students ORDER BY id ASC")
            studs = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Reg ID', 'Name', 'Course', 'Phone', 'Parent Phone', 'Admission Date', 'Total Fees', 'Paid Fees', 'Pending Fees'])
    for s in studs:
        pending = safe_float(s['total_fees']) - safe_float(s['paid_fees'])
        writer.writerow([s['id'], s['name'], s['course'], s['phone'], s['parent_phone'], s['admission_date'], s['total_fees'], s['paid_fees'], pending])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=students_list.csv"})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
