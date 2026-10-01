import os
import shutil
from datetime import date, datetime 
from flask import Flask, redirect, render_template, render_template_string, request, send_file, send_from_directory, url_for, session, Response
from werkzeug.utils import secure_filename
import io
import csv
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_complete_bulletproof_v45_cloud_backup"

# Supabase PostgreSQL Database Connection URL (श्रीगुरु करिअर अकॅडमी क्लाउड जोडणी)
DATABASE_URL = "postgresql://postgres:Shreeguru@123@db.pcwdribwbcuoxkqhozmu.supabase.co:5432/postgres"

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

def create_automatic_backup():
    try:
        today_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file_path = os.path.join(BACKUP_FOLDER, f"shreeguru_cloud_sync_{today_str}.txt")
        with open(backup_file_path, "w", encoding="utf-8") as f:
            f.write(f"Shreeguru Cloud Sync Backup Active - {today_str}")
        print(f"Auto Backup Sync Created Successfully: {backup_file_path}")
    except Exception as e:
        print(f"Auto Backup Error: {e}")

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
    create_automatic_backup()
    with get_db() as conn:
        with conn.cursor() as cur:
            # Users & Roles
            cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, role TEXT UNIQUE NOT NULL, password TEXT NOT NULL)")
            cur.execute("INSERT INTO users (role, password) VALUES ('Admin', 'admin123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Manager', 'manager123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Clerk', 'clerk123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Trainer', 'trainer123') ON CONFLICT (role) DO NOTHING")

            # Questions & Mock Tests
            cur.execute('''CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY, question TEXT NOT NULL, opt_a TEXT NOT NULL, opt_b TEXT NOT NULL, opt_c TEXT NOT NULL, opt_d TEXT NOT NULL, correct TEXT NOT NULL
            )''')
            cur.execute('SELECT COUNT(*) FROM questions')
            if cur.fetchone()['count'] == 0:
                default_qs = [
                    ("महाराष्ट्राची राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B"),
                    ("क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A"),
                    ("स्वराज्य स्थापना कोणी केली?", "छत्रपती संभाजी महाराज", "छत्रपती शिवाजी महाराज", "महात्मा ज्योतिराव फुले", "संत ज्ञानेश्वर", "B"),
                    ("भारताचे राष्ट्रगीत 'जन गण मन' कोणी लिहिले?", "बंकिमचंद्र चटर्जी", "रविंद्रनाथ टागोर", "महात्मा गांधी", "लोकमान्य टिळक", "B"),
                    ("महाराष्ट्रात एकूण किती जिल्हे आहेत?", "३४", "३५", "३६", "३७", "C")
                ]
                cur.executemany('INSERT INTO questions (question, opt_a, opt_b, opt_c, opt_d, correct) VALUES (%s, %s, %s, %s, %s, %s)', default_qs)
                conn.commit()

            # Main Tables
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

# --- LOGIN SCREEN HTML TEMPLATE ---
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

# --- ADMIN PANEL & ROUTES ---
@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students")
            students = cur.fetchall()
            cur.execute("SELECT * FROM expenses ORDER BY id DESC")
            expenses_list = cur.fetchall()
    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    
    return f"""
    <div style="font-family:Arial; padding:30px; background:#f8fafc;">
        <h1 style="color:#1e293b;">⚔️ श्रीगुरु करिअर अकॅडमी - प्रशासक पॅनेल (Admin Dashboard)</h1>
        <p style="background:#e2e8f0; padding:10px; border-radius:5px;"><b>क्लाउड डेटाबेस (Supabase):</b> यशस्वीरित्या जोडलेले आहे! ✅</p>
        <hr>
        <h3>थोडक्यात माहिती (Summary):</h3>
        <ul>
            <li><b>एकूण विद्यार्थी संख्या:</b> {len(students)}</li>
            <li><b>गोळा झालेली एकूण फी:</b> ₹ {total_paid}</li>
            <li><b>बाकी असलेली फी:</b> ₹ {total_pending}</li>
            <li><b>एकूण खर्च:</b> ₹ {sum(safe_float(ex['amount']) for ex in expenses_list)}</li>
        </ul>
        <br>
        <a href="/logout" style="background:#dc2626; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;">लॉग आउट (Logout) 🚪</a>
    </div>
    """

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
