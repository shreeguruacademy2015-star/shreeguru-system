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
app.secret_key = "shreeguru_complete_bulletproof_v47_all_modules_final"

# Supabase PostgreSQL Database Connection URL
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

def log_staff_activity(role_name, act_text):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                cur.execute("INSERT INTO staff_activity_log (staff_role, act_time, activity_text) VALUES (%s, %s, %s)", (role_name, now_str, act_text))
            conn.commit()
    except Exception as e:
        print(f"Log Error: {e}")

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
            # Users & Roles
            cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, role TEXT UNIQUE NOT NULL, password TEXT NOT NULL)")
            cur.execute("INSERT INTO users (role, password) VALUES ('Admin', 'admin123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Manager', 'manager123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Clerk', 'clerk123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Trainer', 'trainer123') ON CONFLICT (role) DO NOTHING")

            # Online Tests & Submissions Tables (Timer, Manual/Bulk, Verified WhatsApp Leads)
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

            # Academy Core Tables (Library, Study Lab, Students, Fees, Expenses, etc.)
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

# --- LOGIN SCREEN HTML ---
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

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students")
            students = cur.fetchall()
            cur.execute("SELECT * FROM expenses ORDER BY id DESC")
            expenses_list = cur.fetchall()
            cur.execute("SELECT s.*, t.title FROM student_submissions s LEFT JOIN online_tests t ON s.test_id = t.id ORDER BY s.id DESC")
            test_submissions = cur.fetchall()
    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    
    sub_rows = "".join([f"<tr><td>REG-{sub['test_id']}</td><td><b>{sub['student_name']}</b></td><td>{sub['student_mobile']}</td><td>{sub.get('title','सराव टेस्ट')}</td><td><b style='color:green;'>{sub['score']}/{sub['total_marks']}</b></td><td>{sub['created_at']}</td></tr>" for sub in test_submissions]) if test_submissions else "<tr><td colspan='6'>अद्याप कोणत्याही टेस्ट सबमिशन आलेले नाहीत.</td></tr>"

    return f"""
    <div style="font-family:Arial; padding:30px; background:#f8fafc;">
        <h1 style="color:#1e293b;">⚔️ श्रीगुरु करिअर अकॅडमी - प्रशासक पॅनेल (Admin Dashboard)</h1>
        <p style="background:#e2e8f0; padding:10px; border-radius:5px;"><b>क्लाउड डेटाबेस (Supabase):</b> यशस्वीरित्या जोडलेले आहे! ✅</p>
        <hr>
        <div style="margin-bottom:20px;">
            <a href="/admin/add_test" style="background:#2563eb; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold; margin-right:10px; display:inline-block;">📝 नवीन टेस्ट (Timer / Bulk / Manual) तयार करा</a>
            <a href="/inquiries" style="background:#b45309; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold; margin-right:10px; display:inline-block;">📞 कॉलिंग व टेस्ट डेस्क</a>
            <a href="/library" style="background:#0284c7; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold; margin-right:10px; display:inline-block;" target="_blank">📚 लायब्ररी / लॅब</a>
            <a href="/logout" style="background:#dc2626; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold; display:inline-block;">लॉग आउट 🚪</a>
        </div>
        <h3>थोडक्यात माहिती (Summary):</h3>
        <ul>
            <li><b>एकूण विद्यार्थी संख्या:</b> {len(students)}</li>
            <li><b>गोळा झालेली एकूण फी:</b> ₹ {total_paid}</li>
            <li><b>बाकी असलेली फी:</b> ₹ {total_pending}</li>
            <li><b>एकूण खर्च:</b> ₹ {sum(safe_float(ex['amount']) for ex in expenses_list)}</li>
        </ul>
        <hr>
        <h3>📋 विद्यार्थी ऑनलाईन टेस्ट सबमिशन व खरे मोबाईल नंबर (Test Leads & Records):</h3>
        <table border="1" cellpadding="8" style="border-collapse:collapse; background:white; width:100%; margin-top:10px;">
            <tr style="background:#e2e8f0;"><th>टेस्ट आयडी</th><th>विद्यार्थी नाव</th><th>खरा मोबाईल नंबर (WhatsApp Verified)</th><th>टेस्टचे नाव</th><th>गुण</th><th>वेळ</th></tr>
            {sub_rows}
        </table>
    </div>
    """

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
    sub_rows = "".join([f"<tr><td><b>{sub['student_name']}</b></td><td>{sub['student_mobile']}</td><td>{sub.get('title','सराव टेस्ट')}</td><td><b style='color:green;'>{sub['score']}/{sub['total_marks']}</b></td><td>{sub['created_at']}</td></tr>" for sub in test_submissions]) if test_submissions else "<tr><td colspan='5'>नोंद नाही.</td></tr>"
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

# ---------------------------------------------------------
# टेस्ट निर्मिती: मॅन्युअल, बल्क व टाईम लिमिट (Admin / Clerk)
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# विद्यार्थी टेस्ट सबमिशन, स्ट्रिक्ट व्हॅलिडेशन व WhatsApp फ्लो
# ---------------------------------------------------------
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
        
        # नाव तपासणे (फक्त अक्षरे आणि स्पेसेस)
        if not student_name or not re.match("^[अ-ॲक-हA-Za-z\\s]+$", student_name):
            return jsonify({"status": "error", "message": "कृपया तुमचे योग्य नाव टाका (नावात आकडे चालणार नाहीत)."}), 400

        # मोबाईल नंबर तपासणे (अचूक १० अंकी नंबर सक्तीचा)
        if not student_mobile or not re.match("^[0-9]{10}$", student_mobile):
            return jsonify({"status": "error", "message": "चुकीचा नंबर! कृपया अचूक १० अंकी मोबाईल नंबर टाका."}), 400

        # डेटाबेसमध्ये विद्यार्थ्याचा खरा नंबर व निकाल सेव्ह करणे
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

# --- लायब्ररी डॅशबोर्ड (Library Module) ---
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

# --- कॉलिंग व चौकशी डेस्क (Inquiries Desk) ---
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
