import os
import shutil
from datetime import date, datetime 
from flask import Flask, redirect, render_template, render_template_string, request, send_file, send_from_directory, url_for, session, Response, jsonify
from werkzeug.utils import secure_filename
import io
import csv
import urllib.parse
import re
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_complete_bulletproof_v51_master_all_tabs_fixed"

# Supabase PostgreSQL Database Connection URL (पासवर्डमधील @ चे %40 केलेले आहे)
DATABASE_URL = "postgresql://postgres:Shreeguru%40123@db.pcwdribwbcuoxkqhozmu.supabase.co:5432/postgres"

DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
UPLOAD_FOLDER = os.path.join(DESKTOP_PATH, "student_photos")
DOCS_FOLDER = os.path.join(DESKTOP_PATH, "student_documents")
BACKUP_FOLDER = os.path.join(DESKTOP_PATH, "shreeguru_auto_backups")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOCS_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOCS_FOLDER'] = DOCS_FOLDER

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

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

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, role TEXT UNIQUE NOT NULL, password TEXT NOT NULL)")
            cur.execute("INSERT INTO users (role, password) VALUES ('Admin', 'admin123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Manager', 'manager123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Clerk', 'clerk123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Trainer', 'trainer123') ON CONFLICT (role) DO NOTHING")

            cur.execute("""CREATE TABLE IF NOT EXISTS online_tests (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                time_limit INTEGER DEFAULT NULL,
                manual_questions TEXT,
                raw_questions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")

            cur.execute("""CREATE TABLE IF NOT EXISTS student_submissions (
                id SERIAL PRIMARY KEY,
                test_id INTEGER,
                student_name TEXT,
                student_mobile TEXT,
                score REAL DEFAULT 0,
                total_marks REAL DEFAULT 0,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")

            cur.execute('''CREATE TABLE IF NOT EXISTS books (id SERIAL PRIMARY KEY, title TEXT NOT NULL, author TEXT, category TEXT, total_copies INTEGER DEFAULT 1, available_copies INTEGER DEFAULT 1)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS book_issues (id SERIAL PRIMARY KEY, book_id INTEGER, student_id INTEGER, student_name TEXT, issue_date TEXT, return_date TEXT, status TEXT DEFAULT 'Issued')''')
            cur.execute('''CREATE TABLE IF NOT EXISTS study_lab_seats (id SERIAL PRIMARY KEY, seat_number TEXT NOT NULL, shift TEXT NOT NULL, student_id INTEGER, student_name TEXT, status TEXT DEFAULT 'Available')''')
            cur.execute("CREATE TABLE IF NOT EXISTS staff_activity_log (id SERIAL PRIMARY KEY, staff_role TEXT NOT NULL, act_time TEXT NOT NULL, activity_text TEXT NOT NULL, admin_reply TEXT DEFAULT '')")
            cur.execute("CREATE TABLE IF NOT EXISTS staff_requests (id SERIAL PRIMARY KEY, req_role TEXT NOT NULL, req_date TEXT NOT NULL, request_title TEXT NOT NULL, request_details TEXT NOT NULL, status TEXT DEFAULT 'प्रलंबित (Pending)')")
            
            cur.execute("""CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, dob TEXT, gender TEXT, category TEXT, height TEXT, weight TEXT, chest TEXT,
                course TEXT NOT NULL, phone TEXT NOT NULL, parent_phone TEXT, address TEXT, hostel_needed TEXT DEFAULT 'नाही',
                total_fees REAL DEFAULT 0, paid_fees REAL DEFAULT 0, photo_filename TEXT, admission_form_scan TEXT, admission_date TEXT NOT NULL,
                diet_plan TEXT, admin_remark TEXT
            )""")
            
            cur.execute("CREATE TABLE IF NOT EXISTS attendance (id SERIAL PRIMARY KEY, person_type TEXT NOT NULL, person_id INTEGER NOT NULL, att_type TEXT NOT NULL, att_date TEXT NOT NULL, status TEXT NOT NULL, marked_by TEXT DEFAULT 'Staff')")
            cur.execute("CREATE TABLE IF NOT EXISTS hostel_mess_fees (id SERIAL PRIMARY KEY, student_id INTEGER, package_type TEXT, from_month TEXT, to_month TEXT, total_amount REAL DEFAULT 0, paid_amount REAL DEFAULT 0, pay_date TEXT, logged_by TEXT DEFAULT 'Clerk')")
            cur.execute("CREATE TABLE IF NOT EXISTS physical_tests (id SERIAL PRIMARY KEY, student_id INTEGER, test_date TEXT, run_time TEXT, sprint_time TEXT, shot_put_dist TEXT, pullups INTEGER DEFAULT 0, total_obtained REAL DEFAULT 0, logged_by TEXT DEFAULT 'Staff')")
            cur.execute("CREATE TABLE IF NOT EXISTS written_tests (id SERIAL PRIMARY KEY, student_id INTEGER, test_date TEXT, test_name TEXT, subject TEXT, total_marks REAL DEFAULT 100, obtained_marks REAL DEFAULT 0, logged_by TEXT DEFAULT 'Staff')")
            cur.execute("CREATE TABLE IF NOT EXISTS trainer_practice_log (id SERIAL PRIMARY KEY, log_date TEXT NOT NULL, session_time TEXT NOT NULL, ground_status TEXT NOT NULL, workout_details TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS injuries (id SERIAL PRIMARY KEY, student_id INTEGER NOT NULL, injury_date TEXT NOT NULL, injury_type TEXT NOT NULL, severity TEXT NOT NULL, rest_days INTEGER DEFAULT 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS staff (id SERIAL PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, phone TEXT NOT NULL, salary REAL DEFAULT 0, advance_paid REAL DEFAULT 0, joining_date TEXT, total_leaves INTEGER DEFAULT 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, exp_date TEXT NOT NULL, category TEXT NOT NULL, description TEXT, amount REAL NOT NULL, logged_by TEXT DEFAULT 'Clerk')")
            cur.execute("CREATE TABLE IF NOT EXISTS kit_distribution (id SERIAL PRIMARY KEY, student_id INTEGER NOT NULL, item_details TEXT NOT NULL, issue_date TEXT NOT NULL, logged_by TEXT DEFAULT 'Clerk')")
            cur.execute("CREATE TABLE IF NOT EXISTS discipline_records (id SERIAL PRIMARY KEY, student_id INTEGER NOT NULL, record_type TEXT NOT NULL, record_date TEXT NOT NULL, reason TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS mess_diet (id SERIAL PRIMARY KEY, day_name TEXT NOT NULL UNIQUE, breakfast TEXT, lunch TEXT, dinner TEXT, special_diet TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS staff_tasks (id SERIAL PRIMARY KEY, target_role TEXT NOT NULL, task_text TEXT NOT NULL, task_date TEXT NOT NULL, status TEXT DEFAULT 'Unseen')")
            
            cur.execute("CREATE TABLE IF NOT EXISTS canteen_staff_list (id SERIAL PRIMARY KEY, staff_name TEXT NOT NULL, work_role TEXT NOT NULL)")
            cur.execute("INSERT INTO canteen_staff_list (id, staff_name, work_role) VALUES (1, 'सुरेखा ताई', 'मुख्य स्वयंपाक') ON CONFLICT (id) DO NOTHING")
            cur.execute("INSERT INTO canteen_staff_list (id, staff_name, work_role) VALUES (2, 'सुनीता ताई', 'चपाती व भांडी') ON CONFLICT (id) DO NOTHING")
            
            cur.execute("CREATE TABLE IF NOT EXISTS kitchen_staff_att (id SERIAL PRIMARY KEY, staff_name TEXT NOT NULL, att_date TEXT NOT NULL, session_time TEXT NOT NULL, day_name TEXT NOT NULL, status TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS student_care_log (id SERIAL PRIMARY KEY, student_id INTEGER NOT NULL, care_date TEXT NOT NULL, issue_details TEXT NOT NULL, special_diet_note TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS staff_activities (id SERIAL PRIMARY KEY, student_id INTEGER, staff_name TEXT, activity_date TEXT, action_text TEXT, remark TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS student_activities (id SERIAL PRIMARY KEY, student_id INTEGER, activity_date TEXT, diet_plan TEXT, remark TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS ground_records (id SERIAL PRIMARY KEY, student_id INTEGER NOT NULL, test_date TEXT NOT NULL, event_name TEXT NOT NULL, raw_value REAL NOT NULL, marks REAL NOT NULL, trainer_name TEXT, remark TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS admission_inquiries (id SERIAL PRIMARY KEY, inquiry_date TEXT NOT NULL, student_name TEXT NOT NULL, district TEXT NOT NULL, taluka TEXT, phone TEXT NOT NULL, course TEXT NOT NULL, hostel_interest TEXT DEFAULT 'होय', call_status TEXT DEFAULT 'नवीन चौकशी (New)', staff_note TEXT DEFAULT '')")
            cur.execute("CREATE TABLE IF NOT EXISTS mock_test_leads (id SERIAL PRIMARY KEY, test_date TEXT NOT NULL, student_name TEXT NOT NULL, district TEXT NOT NULL, phone TEXT NOT NULL, score INTEGER NOT NULL, total_marks INTEGER NOT NULL, test_name TEXT NOT NULL, call_status TEXT DEFAULT 'नवीन टेस्ट निकाल', staff_note TEXT DEFAULT '')")
            conn.commit()

            days = ['सोमवार', 'मंगळवार', 'बुधवार', 'गुरुवार', 'शुक्रवार', 'शनिवार', 'रविवार']
            for d in days:
                cur.execute("INSERT INTO mess_diet (day_name, breakfast, lunch, dinner, special_diet) VALUES (%s, 'पोहे / उपमा', 'डाळ, भात, चपाती, उसळ', 'भाकरी, सुकी भाजी, आमटी', 'दूध, केळी, भिजवलेले हरभरे-गूळ') ON CONFLICT (day_name) DO NOTHING", (d,))
            conn.commit()

LOGIN_HTML = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SHREEGURU DEFENCE ACADEMY - OFFICIAL LOGIN</title>
<style>
* { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
body { margin: 0; padding: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #0f172a; }
.login-box { background: rgba(255, 255, 255, 0.97); width: 380px; padding: 35px 30px; border-radius: 12px; box-shadow: 0 20px 40px rgba(0,0,0,0.6); text-align: center; position: relative; }
.insignia { background: #b45309; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: bold; display: inline-block; margin-bottom: 8px; }
.title { color: #0b2545; font-size: 22px; font-weight: 800; margin: 4px 0; }
.subtitle { font-size: 11px; color: #475569; margin-bottom: 20px; font-weight: 600; }
select, input { width: 100%; padding: 11px 12px; margin-bottom: 15px; border: 1.5px solid #cbd5e1; border-radius: 6px; font-size: 13px; font-weight: 600; }
.btn-sub { width: 100%; padding: 12px; background: linear-gradient(135deg, #15803d, #16a34a); color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer; }
.lang-btn { position: absolute; top: 12px; right: 12px; background: #fef08a; color: #854d0e; border: 1px solid #facc15; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-decoration: none; }
</style></head>
<body>
<div class="login-box">
    <a href="/toggle_lang" class="lang-btn">🌐 {{ 'MR' if lang == 'en' else 'EN' }}</a>
    <span class="insignia">⚔️ POLICE & DEFENCE ACADEMY</span>
    <h2 class="title">श्रीगुरु करिअर अकॅडमी</h2>
    <div class="subtitle">पोलीस व सैन्य भरती पूर्व प्रशिक्षण केंद्र<br>आडूर, ता. करवीर, जि. कोल्हापूर</div>
    {% if error %}<div style="color:#dc2626; font-size:12px; font-weight:bold; margin-bottom:12px;">{{ error }}</div>{% endif %}
    <form action="/login" method="POST">
        <select name="role">{% for u in users_list %}<option value="{{ u.role }}">{{ u.role }}</option>{% endfor %}</select>
        <input type="password" name="password" required placeholder="{{ 'Enter Password' if lang == 'en' else 'पासवर्ड टाका' }}">
        <button type="submit" class="btn-sub">{{ 'SECURE LOGIN 🔐' if lang == 'en' else 'सुरक्षित लॉगिन करा 🔐' }}</button>
    </form>
</div></body></html>'''

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
            cur.execute("SELECT * FROM users")
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
            if role == 'Manager': return redirect('/manager')
            elif role == 'Trainer': return redirect('/trainer')
            elif role == 'Clerk': return redirect('/clerk')
            else: return redirect('/admin')
        else:
            error = "Invalid Password!" if lang == 'en' else "चुकीचा पासवर्ड! पुन्हा प्रयत्न करा."
    return render_template_string(LOGIN_HTML, error=error, lang=lang, users_list=users_list)

@app.route('/logout')
def logout():
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

ADMIN_DASHBOARD_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8"><title>Admin Dashboard - SHREEGURU ACADEMY</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #eef2f7; }
        .header { background: #0b3c5d; color: white; padding: 12px 20px; text-align: center; position: relative; }
        .top-right { position: absolute; right: 15px; top: 12px; display: flex; align-items: center; gap: 8px; }
        .menu-bar { background: #111c24; display: flex; justify-content: center; gap: 4px; padding: 8px; flex-wrap: wrap; }
        .menu-btn { border: none; padding: 7px 11px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; color: white; text-decoration: none; display: inline-block; }
        .menu-btn.active { background: #fde047 !important; color: #0b3c5d !important; }
        .container { max-width: 1350px; margin: 15px auto; padding: 0 10px; }
        .kpis { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 15px; }
        .kpi { background: white; padding: 10px 14px; border-radius: 4px; flex: 1; min-width: 150px; border-left: 4px solid #0b3c5d; font-size: 13px; }
        .admin-tab { background: white; padding: 15px; border-radius: 4px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #ddd; padding: 7px; text-align: left; }
        th { background: #0b3c5d; color: white; }
        input, select { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; }
        .btn-act { padding: 4px 7px; border-radius: 3px; color: white; text-decoration: none; font-size: 11px; font-weight: bold; display: inline-block; cursor: pointer; border: none; }
    </style>
</head>
<body>
<div class="header">
    <h1 style="margin:0; color:#ffdd59; font-size:24px;">SHREEGURU CAREER ACADEMY</h1>
    <p style="margin:3px 0 0; font-size:12px;">पत्ता: आडूर, करवीर, कोल्हापूर | संपर्क: ९९२११११९६०</p>
    <div class="top-right">
        <a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">Logout 🚪</a>
    </div>
</div>

<div class="menu-bar">
    <a href="/admin/add_test" class="menu-btn" style="background:#059669; border:2px solid #fde047;">📝 नवीन टेस्ट (Timer/Bulk)</a>
    <a href="/inquiries" class="menu-btn" style="background:#b45309; border:2px solid #fde047;">📞 कॉलिंग व टेस्ट डेस्क</a>
    <a href="/admin?tab=students" class="menu-btn {% if curr_tab == 'students' %}active{% endif %}" style="background:#2563eb;">👥 सर्व विद्यार्थी</a>
    <a href="/admin?tab=admission" class="menu-btn {% if curr_tab == 'admission' %}active{% endif %}" style="background:#2563eb;">📝 नवीन प्रवेश</a>
    <a href="/admin?tab=test_leads" class="menu-btn {% if curr_tab == 'test_leads' %}active{% endif %}" style="background:#10b981; border:2px solid #ffdd59;">📊 टेस्ट लीड्स व नंबर</a>
    <a href="/library" target="_blank" class="menu-btn" style="background:#0284c7;">📚 लायब्ररी</a>
    <a href="/admin?tab=fee" class="menu-btn {% if curr_tab == 'fee' %}active{% endif %}" style="background:#f59e0b;">💰 फी जमा</a>
    <a href="/admin?tab=exp" class="menu-btn {% if curr_tab == 'exp' %}active{% endif %}" style="background:#ff416c;">💵 खर्च वही</a>
    <a href="/admin?tab=passwords" class="menu-btn {% if curr_tab == 'passwords' %}active{% endif %}" style="background:#dc2626;">🔐 पासवर्ड</a>
</div>

<div class="container">
    <div class="kpis">
        <div class="kpi"><b>एकूण विद्यार्थी:</b> {{ students|length }}</div>
        <div class="kpi" style="border-color:#10b981;"><b>जमा फी:</b> ₹{{ total_paid }}</div>
        <div class="kpi" style="border-color:#ef4444;"><b>शिल्लक फी:</b> <span style="color:red;">₹{{ total_pending }}</span></div>
        <div class="kpi" style="border-color:#ff416c;"><b>एकूण खर्च:</b> ₹{{ total_expenses }}</div>
    </div>

    {% if curr_tab == 'students' %}
    <div class="admin-tab">
        <h3>📋 विद्यार्थी यादी</h3>
        <table>
            <thead><tr><th>Reg</th><th>नाव</th><th>कोर्स</th><th>फोन</th><th>शिल्लक</th></tr></thead>
            <tbody>
                {% for s in students %}
                <tr><td>REG-{{ s.id }}</td><td><b>{{ s.name }}</b></td><td>{{ s.course }}</td><td>{{ s.phone }}</td><td style="color:red; font-weight:bold;">₹{{ (s.total_fees or 0) - (s.paid_fees or 0) }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'test_leads' %}
    <div class="admin-tab">
        <h3 style="color:#059669;">📊 ऑनलाईन टेस्ट सबमिशन व पडताळणी केलेले खरे मोबाईल नंबर (Test Leads & WhatsApp Verified Numbers)</h3>
        <table>
            <thead><tr><th>टेस्ट आयडी</th><th>विद्यार्थी नाव</th><th>खरा मोबाईल नंबर (WhatsApp Verified)</th><th>टेस्टचे नाव</th><th>गुण</th><th>वेळ</th></tr></thead>
            <tbody>
                {% for sub in test_submissions %}
                <tr>
                    <td>REG-{{ sub.test_id }}</td>
                    <td><b>{{ sub.student_name }}</b></td>
                    <td><b style="color:#16a34a; font-size:14px;">{{ sub.student_mobile }}</b> <a href="https://wa.me/91{{ sub.student_mobile }}" target="_blank" class="btn-act" style="background:#25D366; margin-left:8px;">📲 मेसेज</a></td>
                    <td>{{ sub.title or 'सराव टेस्ट' }}</td>
                    <td><b style="color:green;">{{ sub.score }} / {{ sub.total_marks }}</b></td>
                    <td>{{ sub.created_at }}</td>
                </tr>
                {% else %}
                <tr><td colspan="6">अद्याप कोणतीही टेस्ट सबमिशन आलेली नाही.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'admission' %}
    <div class="admin-tab">
        <h3>📝 नवीन विद्यार्थी प्रवेश नोंदणी</h3>
        <form action="/add_student" method="POST">
            <input type="text" name="name" placeholder="नाव" required>
            <input type="date" name="admission_date" value="{{ today_date }}" required>
            <input type="text" name="course" value="पोलीस भरती" required>
            <input type="text" name="phone" placeholder="मोबाईल" required>
            <input type="number" name="total_fees" placeholder="एकूण फी" required>
            <input type="number" name="paid_fees" placeholder="भरलेली फी" required>
            <button type="submit" class="btn-act" style="background:green; padding:8px 15px;">+ प्रवेश सेव्ह करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'fee' %}
    <div class="admin-tab">
        <h3>💰 फी हप्ता जमा</h3>
        <form action="/pay_installment" method="POST">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }} (बाकी: ₹{{ (s.total_fees or 0)-(s.paid_fees or 0) }})</option>{% endfor %}</select>
            रक्कम: <input type="number" name="amount" placeholder="रक्कम (₹)" required>
            <button type="submit" class="btn-act" style="background:green;">जमा करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'exp' %}
    <div class="admin-tab">
        <h3>💵 दैनिक खर्च वही</h3>
        <form action="/add_expense" method="POST">
            प्रकार: <input type="text" name="category" placeholder="उदा. भाजीपाला" required>
            रक्कम: <input type="number" name="amount" placeholder="रक्कम" required>
            तपशील: <input type="text" name="description" placeholder="तपशील" required>
            <button type="submit" class="btn-act" style="background:green;">नोंदवा</button>
        </form>
        <table>
            <thead><tr><th>तारीख</th><th>प्रकार</th><th>तपशील</th><th>रक्कम</th></tr></thead>
            <tbody>
                {% for ex in expenses_list %}
                <tr><td>{{ ex.exp_date }}</td><td>{{ ex.category }}</td><td><b>{{ ex.description }}</b></td><td style="color:red; font-weight:bold;">₹{{ ex.amount }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'passwords' %}
    <div class="admin-tab">
        <h3 style="color:#dc2626;">🔐 युजर पासवर्ड व्यवस्थापन</h3>
        <table>
            <thead><tr><th>Role</th><th>Password</th><th>Action</th></tr></thead>
            <tbody>
                {% for u in users_list %}
                <form action="/change_password/{{ u.id }}" method="POST">
                <tr>
                    <td><b>{{ u.role }}</b></td><td><input type="text" name="new_password" value="{{ u.password }}"></td>
                    <td><button type="submit" class="btn-act" style="background:#10b981;">अपडेट</button></td>
                </tr>
                </form>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
</div>
</body>
</html>'''

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'test_leads')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students")
            students = cur.fetchall()
            cur.execute("SELECT * FROM expenses ORDER BY id DESC")
            expenses_list = cur.fetchall()
            cur.execute("SELECT * FROM users")
            users_list = cur.fetchall()
            cur.execute("SELECT s.*, t.title FROM student_submissions s LEFT JOIN online_tests t ON s.test_id = t.id ORDER BY s.id DESC")
            test_submissions = cur.fetchall()

    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    total_expenses = sum(safe_float(ex['amount']) for ex in expenses_list)

    return render_template_string(ADMIN_DASHBOARD_LAYOUT, curr_tab=curr_tab, students=students, expenses_list=expenses_list, users_list=users_list, test_submissions=test_submissions, total_paid=total_paid, total_pending=total_pending, total_expenses=total_expenses, today_date=today_date, lang=lang)

@app.route('/manager')
def manager_view():
    if session.get('user_role') != 'Manager': return redirect(url_for('login'))
    return "<h2>Manager Dashboard - श्रीगुरु करिअर अकॅडमी</h2><a href='/logout'>Logout</a>"

@app.route('/trainer')
def trainer_view():
    if session.get('user_role') != 'Trainer': return redirect(url_for('login'))
    return "<h2>Trainer Dashboard - श्रीगुरु करिअर अकॅडमी</h2><a href='/logout'>Logout</a>"

@app.route('/clerk')
def clerk_view():
    if session.get('user_role') != 'Clerk': return redirect(url_for('login'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT s.*, t.title FROM student_submissions s LEFT JOIN online_tests t ON s.test_id = t.id ORDER BY s.id DESC")
            test_submissions = cur.fetchall()
    sub_rows = "".join([f"<tr><td><b>{sub['student_name']}</b></td><td><b style='color:#16a34a;'>{sub['student_mobile']}</b></td><td>{sub.get('title','सराव टेस्ट')}</td><td><b style='color:green;'>{sub['score']}/{sub['total_marks']}</b></td><td>{sub['created_at']}</td></tr>" for sub in test_submissions]) if test_submissions else "<tr><td colspan='5'>नोंद नाही.</td></tr>"
    return f"""
    <div style="font-family:Arial; padding:30px; background:#f8fafc;">
        <h2>Clerk Dashboard - श्रीगुरु करिअर अकॅडमी</h2>
        <a href="/admin/add_test" style="background:#059669; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold; display:inline-block; margin-bottom:15px;">📝 नवीन टेस्ट तयार करा (Timer/Bulk/Manual)</a>
        <hr>
        <h3>📋 ऑनलाईन टेस्ट सबमिशन व अचूक नंबर रेकॉर्ड:</h3>
        <table border="1" cellpadding="8" style="border-collapse:collapse; background:white; width:100%;">
            <tr style="background:#e2e8f0;"><th>विद्यार्थी नाव</th><th>खरा मोबाईल नंबर</th><th>टेस्ट नाव</th><th>गुण</th><th>वेळ</th></tr>
            {sub_rows}
        </table>
        <br><a href='/logout' style="color:red; font-weight:bold;">Logout</a>
    </div>
    """

@app.route('/admin/add_test', methods=['GET', 'POST'])
def add_test():
    role = session.get('user_role')
    if role not in ['Admin', 'Clerk']:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        test_title = request.form.get('test_title')
        time_limit = request.form.get('time_limit') 
        time_limit = int(time_limit) if time_limit and time_limit.isdigit() else None
        manual_questions = request.form.get('manual_questions', '')
        raw_content = request.form.get('raw_content', '')
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO online_tests (title, time_limit, manual_questions, raw_questions) VALUES (%s, %s, %s, %s);",
                    (test_title, time_limit, manual_questions, raw_content)
                )
            conn.commit()
            
        return jsonify({
            "status": "success",
            "message": "टेस्ट, टाईम लिमिट, मॅन्युअल व बल्क प्रश्न यशस्वीपणे जतन झाले आहेत!"
        })
        
    return """
    <div style="font-family:Arial; padding:30px; max-width:700px; margin:auto; background:#f8fafc; border-radius:8px; box-shadow:0 4px 10px rgba(0,0,0,0.05); margin-top:30px;">
        <h2>📝 नवीन टेस्ट तयार करा (Manual / Bulk Import & Timer)</h2>
        <form method="POST">
            <label><b>टेस्टचे नाव (Title):</b></label><br>
            <input type="text" name="test_title" required style="width:100%; padding:10px; margin:8px 0; border:1px solid #cbd5e1; border-radius:4px;"><br>
            
            <label><b>टाईम लिमिट (मिनिटांत - रिकामे ठेवल्यास अनलमीटेड वेळ):</b></label><br>
            <input type="number" name="time_limit" placeholder="उदा. 10 किंवा 30" style="width:100%; padding:10px; margin:8px 0; border:1px solid #cbd5e1; border-radius:4px;"><br>
            
            <label><b>पर्याय १: मॅन्युअल प्रश्न टायपिंग (Manual Input):</b></label><br>
            <textarea name="manual_questions" rows="5" placeholder="येथे एक-एक प्रश्न टायप करा..." style="width:100%; padding:10px; margin:8px 0; border:1px solid #cbd5e1; border-radius:4px;"></textarea><br>

            <label><b>पर्याय २: सर्व प्रश्न आणि आन्सर की (Bulk Copy-Paste Box):</b></label><br>
            <textarea name="raw_content" rows="8" placeholder="येथे सर्व प्रश्न एकाच वेळी कॉपी-पेस्ट करा..." style="width:100%; padding:10px; margin:8px 0; border:1px solid #cbd5e1; border-radius:4px;"></textarea><br>
            
            <button type="submit" style="background:#15803d; color:white; padding:12px 20px; border:none; border-radius:5px; font-weight:bold; cursor:pointer; width:100%;">टेस्ट सेव्ह करा</button>
        </form>
        <br><a href="/admin" style="color:#2563eb; text-decoration:none; font-weight:bold;">🔙 डॅशबोर्डकडे जा</a>
    </div>
    """

@app.route('/submit_test', methods=['POST'])
def submit_test():
    try:
        data = request.json or request.form
        student_name = data.get('name', '').strip()
        student_mobile = data.get('mobile', '').strip()
        test_id = data.get('test_id')
        score = safe_float(data.get('score', 0))
        total_marks = safe_float(data.get('total_marks', 100))
        details = data.get('details', 'सविस्तर निकाल')
        
        if not student_name or not re.match("^[अ-ॲक-हA-Za-z\\s]+$", student_name):
            return jsonify({"status": "error", "message": "कृपया तुमचे योग्य नाव टाका (नावात आकडे चालणार नाहीत)."}), 400

        if not student_mobile or not re.match("^[0-9]{10}$", student_mobile):
            return jsonify({"status": "error", "message": "चुकीचा नंबर! कृपया अचूक १० अंकी मोबाईल नंबर टाका."}), 400

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO student_submissions (test_id, student_name, student_mobile, score, total_marks, details) 
                       VALUES (%s, %s, %s, %s, %s, %s);""",
                    (test_id, student_name, student_mobile, score, total_marks, details)
                )
            conn.commit()

        academy_whatsapp = "919921111960"
        wa_text = f"नमस्कार {student_name}, श्रीगुरु करिअर अकॅडमी ऑनलाइन टेस्ट निकाल:\nतुमचे गुण: {score}/{total_marks}\nअभिनंदन! आपले डिजिटल प्रशस्तीपत्रक व आन्सर की अधिकृतपणे जतन झाली आहे."
        whatsapp_url = f"https://wa.me/{academy_whatsapp}?text={urllib.parse.quote(wa_text)}"

        return jsonify({
            "status": "success", 
            "message": "तुमची टेस्ट यशस्वीरित्या सबमिट झाली आहे! तुमचा खरा नंबर डेटाबेसमध्ये जतन झाला आहे.",
            "whatsapp_link": whatsapp_url
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/library')
def library_dashboard():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM books ORDER BY id DESC")
            books = cur.fetchall()
            cur.execute("SELECT * FROM book_issues WHERE status = 'Issued' ORDER BY id DESC")
            issues = cur.fetchall()
            cur.execute("SELECT * FROM study_lab_seats ORDER BY seat_number ASC")
            seats = cur.fetchall()
    return render_template_string('''<!DOCTYPE html>
    <html lang="mr"><head><meta charset="UTF-8"><title>लायब्ररी व स्टडी लॅब</title>
    <style>body{font-family:sans-serif;background:#f8fafc;padding:20px;}</style>
    </head><body>
    <h2>📚 स्टडी लॅब व लायब्ररी व्यवस्थापन</h2>
    <a href="/" style="background:#0b3c5d; color:white; padding:8px 15px; text-decoration:none; border-radius:4px; font-weight:bold;">🏠 मुख्य डॅशबोर्ड</a>
    <hr>
    <h3>पुस्तकांची यादी (Books Available):</h3>
    <table border="1" cellpadding="8" style="border-collapse:collapse; background:white; width:100%;">
    <tr style="background:#0b3c5d; color:white;"><th>पुस्तकाचे नाव</th><th>लेखक</th><th>वर्गवारी</th><th>एकूण प्रती</th><th>उपलब्ध प्रती</th></tr>
    {% for b in books %}
    <tr><td><b>{{ b.title }}</b></td><td>{{ b.author }}</td><td>{{ b.category }}</td><td>{{ b.total_copies }}</td><td>{{ b.available_copies }}</td></tr>
    {% else %}
    <tr><td colspan="5">पुस्तके उपलब्ध नाहीत.</td></tr>
    {% endfor %}
    </table>
    </body></html>''', books=books, issues=issues, seats=seats)

@app.route('/inquiries')
def inquiry_desk():
    if session.get('user_role') not in ['Admin', 'Clerk', 'Manager']:
        return redirect(url_for('login'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM admission_inquiries ORDER BY id DESC")
            inquiries = cur.fetchall()
    return render_template_string('''<!DOCTYPE html>
    <html lang="mr"><head><meta charset="UTF-8"><title>कॉलिंग व चौकशी डेस्क</title>
    <style>body{font-family:sans-serif;background:#f8fafc;padding:20px;}</style>
    </head><body>
    <h2>📞 श्रीगुरु ॲडमिशन कॉलिंग डेस्क</h2>
    <a href="/" style="background:#0b3c5d; color:white; padding:8px 15px; text-decoration:none; border-radius:4px; font-weight:bold;">🏠 मुख्य डॅशबोर्ड</a>
    <hr>
    <table border="1" cellpadding="8" style="border-collapse:collapse; background:white; width:100%; margin-top:10px;">
    <tr style="background:#1e293b; color:white;"><th>तारीख</th><th>नाव</th><th>जिल्हा</th><th>फोन</th><th>कोर्स</th><th>स्थिती</th></tr>
    {% for inq in inquiries %}
    <tr><td>{{ inq.inquiry_date }}</td><td><b>{{ inq.student_name }}</b></td><td>{{ inq.district }}</td><td><a href="tel:{{ inq.phone }}">{{ inq.phone }}</a></td><td>{{ inq.course }}</td><td>{{ inq.call_status }}</td></tr>
    {% else %}
    <tr><td colspan="6">चौकशी अर्ज नाहीत.</td></tr>
    {% endfor %}
    </table>
    </body></html>''', inquiries=inquiries)

init_db()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
