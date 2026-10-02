import os
import shutil
from datetime import date, datetime 
from flask import Flask, redirect, render_template, render_template_string, request, send_file, url_for, session, Response
from werkzeug.utils import secure_filename
import urllib.parse
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = "shreeguru_complete_neon_postgres_v44_final_full"

# ==========================================
# ⚡ NEON DATABASE CONNECTION (PostgreSQL)
# ==========================================
NEON_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:YOUR_NEON_PASSWORD@YOUR_NEON_HOST.neon.tech/neondb?sslmode=require")

def get_db():
    conn = psycopg2.connect(NEON_DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
    return conn

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

def log_staff_activity(role_name, act_text):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                cursor.execute("INSERT INTO staff_activity_log (staff_role, act_time, activity_text) VALUES (%s, %s, %s)", (role_name, now_str, act_text))
                conn.commit()
    except Exception as e:
        print(f"Log Error: {e}")

def init_db():
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    role TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            """)
            cursor.execute("INSERT INTO users (role, password) VALUES ('Admin', 'admin123') ON CONFLICT (role) DO NOTHING")
            cursor.execute("INSERT INTO users (role, password) VALUES ('Manager', 'manager123') ON CONFLICT (role) DO NOTHING")
            cursor.execute("INSERT INTO users (role, password) VALUES ('Clerk', 'clerk123') ON CONFLICT (role) DO NOTHING")
            cursor.execute("INSERT INTO users (role, password) VALUES ('Trainer', 'trainer123') ON CONFLICT (role) DO NOTHING")

            cursor.execute('''CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                opt_a TEXT NOT NULL,
                opt_b TEXT NOT NULL,
                opt_c TEXT NOT NULL,
                opt_d TEXT NOT NULL,
                correct TEXT NOT NULL
            )''')

            cursor.execute('SELECT COUNT(*) FROM questions')
            count_res = cursor.fetchone()
            if count_res[0] == 0:
                default_qs = [
                    ("महाराष्ट्राची राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B"),
                    ("क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A"),
                    ("स्वराज्य स्थापना कोणी केली?", "छत्रपती संभाजी महाराज", "छत्रपती शिवाजी महाराज", "महात्मा ज्योतिराव फुले", "संत ज्ञानेश्वर", "B"),
                    ("भारताचे राष्ट्रगीत 'जन गण मन' कोणी लिहिले?", "बंकिमचंद्र चटर्जी", "रविंद्रनाथ टागोर", "महात्मा गांधी", "लोकमान्य टिळक", "B"),
                    ("महाराष्ट्रात एकूण किती जिल्हे आहेत?", "३४", "३५", "३६", "३७", "C")
                ]
                cursor.executemany('INSERT INTO questions (question, opt_a, opt_b, opt_c, opt_d, correct) VALUES (%s, %s, %s, %s, %s, %s)', default_qs)

            cursor.execute('''CREATE TABLE IF NOT EXISTS books (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                category TEXT,
                total_copies INTEGER DEFAULT 1,
                available_copies INTEGER DEFAULT 1
            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS book_issues (
                id SERIAL PRIMARY KEY,
                book_id INTEGER,
                student_id INTEGER,
                student_name TEXT,
                issue_date TEXT,
                return_date TEXT,
                status TEXT DEFAULT 'Issued'
            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS study_lab_seats (
                id SERIAL PRIMARY KEY,
                seat_number TEXT NOT NULL,
                shift TEXT NOT NULL,
                student_id INTEGER,
                student_name TEXT,
                status TEXT DEFAULT 'Available'
            )''')

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS staff_activity_log (
                    id SERIAL PRIMARY KEY,
                    staff_role TEXT NOT NULL,
                    act_time TEXT NOT NULL,
                    activity_text TEXT NOT NULL,
                    admin_reply TEXT DEFAULT ''
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS staff_requests (
                    id SERIAL PRIMARY KEY,
                    req_role TEXT NOT NULL,
                    req_date TEXT NOT NULL,
                    request_title TEXT NOT NULL,
                    request_details TEXT NOT NULL,
                    status TEXT DEFAULT 'प्रलंबित (Pending)'
                )
            """)

            cursor.execute("""
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

            cursor.execute("""
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

            cursor.execute("""
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

            cursor.execute("""
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

            cursor.execute("""
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trainer_practice_log (
                    id SERIAL PRIMARY KEY,
                    log_date TEXT NOT NULL,
                    session_time TEXT NOT NULL,
                    ground_status TEXT NOT NULL,
                    workout_details TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS injuries (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    injury_date TEXT NOT NULL,
                    injury_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    rest_days INTEGER DEFAULT 0
                )
            """)

            cursor.execute("""
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    exp_date TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    logged_by TEXT DEFAULT 'Clerk'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kit_distribution (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    item_details TEXT NOT NULL,
                    issue_date TEXT NOT NULL,
                    logged_by TEXT DEFAULT 'Clerk'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discipline_records (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    record_type TEXT NOT NULL,
                    record_date TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mess_diet (
                    id SERIAL PRIMARY KEY,
                    day_name TEXT NOT NULL UNIQUE,
                    breakfast TEXT,
                    lunch TEXT,
                    dinner TEXT,
                    special_diet TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS staff_tasks (
                    id SERIAL PRIMARY KEY,
                    target_role TEXT NOT NULL,
                    task_text TEXT NOT NULL,
                    task_date TEXT NOT NULL,
                    status TEXT DEFAULT 'Unseen'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS canteen_staff_list (
                    id SERIAL PRIMARY KEY,
                    staff_name TEXT NOT NULL,
                    work_role TEXT NOT NULL
                )
            """)
            cursor.execute("INSERT INTO canteen_staff_list (id, staff_name, work_role) VALUES (1, 'सुरेखा ताई', 'मुख्य स्वयंपाक') ON CONFLICT (id) DO NOTHING")
            cursor.execute("INSERT INTO canteen_staff_list (id, staff_name, work_role) VALUES (2, 'सुनीता ताई', 'चपाती व भांडी') ON CONFLICT (id) DO NOTHING")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kitchen_staff_att (
                    id SERIAL PRIMARY KEY,
                    staff_name TEXT NOT NULL,
                    att_date TEXT NOT NULL,
                    session_time TEXT NOT NULL,
                    day_name TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_care_log (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    care_date TEXT NOT NULL,
                    issue_details TEXT NOT NULL,
                    special_diet_note TEXT
                )
            """)

            cursor.execute("""
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

            cursor.execute("""
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

            conn.commit()

        days = ['सोमवार', 'मंगळवार', 'बुधवार', 'गुरुवार', 'शुक्रवार', 'शनिवार', 'रविवार']
        with get_db() as conn:
            with conn.cursor() as cursor:
                for d in days:
                    cursor.execute("INSERT INTO mess_diet (day_name, breakfast, lunch, dinner, special_diet) VALUES (%s, 'पोहे / उपमा', 'डाळ, भात, चपाती, उसळ', 'भाकरी, सुकी भाजी, आमटी', 'दूध, केळी, भिजवलेले हरभरे-गूळ') ON CONFLICT (day_name) DO NOTHING", (d,))
                conn.commit()

# ----------------- HTML TEMPLATES -----------------
LOGIN_HTML = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SHREEGURU DEFENCE ACADEMY - OFFICIAL LOGIN</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; padding: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #0f172a; }
        .login-box { background: rgba(255, 255, 255, 0.97); width: 380px; padding: 35px 30px; border-radius: 12px; box-shadow: 0 20px 40px rgba(0,0,0,0.6), 0 0 0 2px #d97706; text-align: center; position: relative; }
        .insignia { background: #b45309; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1px; display: inline-block; margin-bottom: 8px; }
        .title { color: #0b2545; font-size: 22px; font-weight: 800; margin: 4px 0; }
        .subtitle { font-size: 11px; color: #475569; margin-bottom: 20px; font-weight: 600; line-height: 1.4; }
        select, input { width: 100%; padding: 11px 12px; margin-bottom: 15px; border: 1.5px solid #cbd5e1; border-radius: 6px; font-size: 13px; font-weight: 600; outline: none; }
        .btn-sub { width: 100%; padding: 12px; background: linear-gradient(135deg, #15803d, #16a34a); color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer; }
        .lang-btn { position: absolute; top: 12px; right: 12px; background: #fef08a; color: #854d0e; border: 1px solid #facc15; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-decoration: none; }
    </style>
</head>
<body>
<div class="login-box">
    <a href="/toggle_lang" class="lang-btn">🌐 {{ 'MR' if lang == 'en' else 'EN' }}</a>
    <span class="insignia">⚔️ POLICE & DEFENCE ACADEMY</span>
    <h2 class="title">श्रीगुरु करिअर अकॅडमी</h2>
    <div class="subtitle">पोलीस व सैन्य भरती पूर्व प्रशिक्षण केंद्र<br>आडूर, ता. करवीर, जि. कोल्हापूर</div>
    {% if error %}<div style="color:#dc2626; font-size:12px; font-weight:bold; margin-bottom:12px;">{{ error }}</div>{% endif %}
    <form action="/login" method="POST">
        <select name="role">
            {% for u in users_list %}
            <option value="{{ u.role }}">{{ u.role }}</option>
            {% endfor %}
        </select>
        <input type="password" name="password" required placeholder="{{ 'Enter Password' if lang == 'en' else 'पासवर्ड टाका' }}">
        <button type="submit" class="btn-sub">{{ 'SECURE LOGIN 🔐' if lang == 'en' else 'सुरक्षित लॉगिन करा 🔐' }}</button>
    </form>
</div>
</body>
</html>'''

MANAGER_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head><meta charset="UTF-8"><title>Manager Portal - Shreeguru Academy</title>
<style>
* { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
body { margin: 0; background: #fdfbf7; color: #333; padding-bottom: 50px; }
.header { background: linear-gradient(135deg, #065f46, #047857); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
.nav-bar { background: #064e3b; display: flex; justify-content: center; gap: 6px; padding: 10px; flex-wrap: wrap; }
.mgr-btn { background: #047857; color: white; border: none; padding: 8px 12px; border-radius: 20px; font-weight: bold; cursor: pointer; font-size: 11px; text-decoration: none; display: inline-block; }
.mgr-btn.active { background: #fde047 !important; color: #064e3b !important; }
.container { max-width: 1250px; margin: 15px auto; padding: 0 12px; }
.card { background: white; border-radius: 8px; padding: 16px; margin-bottom: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); border: 1px solid #e5e7eb; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background: #065f46; color: white; }
input, select { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.btn-act { padding: 6px 14px; border-radius: 4px; color: white; text-decoration: none; font-size: 12px; font-weight: bold; cursor: pointer; border: none; display: inline-block; }
.g-label { display: block; margin-bottom: 6px; font-size: 12px; cursor: pointer; }
</style></head>
<body>
<div class="header">
    <div><h2 style="margin:0; font-size:19px; color:#fde047;">🌸 व्यवस्थापिका कक्ष</h2><small>श्रीगुरु करिअर अकॅडमी | सौ. नीलम सचिन चौगले</small></div>
    <div><a href="/toggle_lang" style="background:#ffdd59; color:#064e3b; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold; text-decoration:none; margin-right:8px;">🌐 भाषा</a> <a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">बाहेर पडा</a></div>
</div>
<div class="nav-bar">
    <a href="/inquiries" class="mgr-btn" style="background:#b45309; color:white;">📞 चौकशी व टेस्ट डेस्क</a>
    <a href="/manager?tab=grocery" class="mgr-btn {% if curr_tab == 'grocery' %}active{% endif %}">🛒 किराणा स्लिप</a>
    <a href="/library" target="_blank" class="mgr-btn" style="background:#0284c7; color: white;">📚 लायब्ररी</a>
    <a href="/manager?tab=diet" class="mgr-btn {% if curr_tab == 'diet' %}active{% endif %}">🍱 जेवण वेळापत्रक</a>
    <a href="/manager?tab=req" class="mgr-btn {% if curr_tab == 'req' %}active{% endif %}" style="background:#e11d48; color:white;">📩 विनंती</a>
</div>
<div class="container">
    {% if curr_tab == 'grocery' %}
    <div class="card">
        <form method="POST" id="groceryForm">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3>🛒 कॅन्टीन किराणा व भाजीपाला स्लिप</h3>
                <div>
                    <button type="submit" formaction="/print_grocery_slip" formtarget="_blank" class="btn-act" style="background:#059669;">🖨️ प्रिंट</button>
                    <button type="submit" formaction="/whatsapp_grocery_slip" formtarget="_blank" class="btn-act" style="background:#25D366;">📲 WhatsApp</button>
                </div>
            </div>
            <hr>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:10px; background:#fffbeb; padding:12px; border-radius:6px;">
                <div>
                    <label class="g-label"><input type="checkbox" name="items" value="तूर डाळ"> तूर डाळ: <input type="text" name="qty_तूर डाळ" placeholder="१० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="तांदूळ"> तांदूळ: <input type="text" name="qty_तांदूळ" placeholder="५० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="गहू पीठ"> गहू पीठ: <input type="text" name="qty_गहू पीठ" placeholder="५० kg" style="width:75px;"></label>
                </div>
                <div>
                    <label class="g-label"><input type="checkbox" name="items" value="कांदे"> कांदे: <input type="text" name="qty_कांदे" placeholder="१५ kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="बटाटे"> बटाटे: <input type="text" name="qty_बटाटे" placeholder="१५ kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="दूध"> ताजे दूध: <input type="text" name="qty_दूध" placeholder="१५ लिटर" style="width:75px;"></label>
                </div>
            </div>
        </form>
    </div>
    {% endif %}
</div>
</body></html>'''

TRAINER_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head><meta charset="UTF-8"><title>Coach Portal - Shreeguru Academy</title>
<style>
* { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
body { margin: 0; background: #f1f5f9; color: #1e293b; padding-bottom: 60px; }
.header { background: #0284c7; color: white; padding: 12px 15px; display: flex; justify-content: space-between; align-items: center; }
.nav-bar { display: flex; overflow-x: auto; background: #0369a1; padding: 6px; gap: 6px; }
.nav-btn { background: #0284c7; color: white; border: none; padding: 7px 11px; border-radius: 20px; font-size: 11px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; white-space: nowrap; }
.nav-btn.active { background: #fde047 !important; color: #0284c7 !important; }
.container { padding: 12px; max-width: 950px; margin: auto; }
.card { background: white; border-radius: 8px; padding: 14px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
th, td { padding: 8px 6px; text-align: left; border-bottom: 1px solid #cbd5e1; }
th { background: #f8fafc; color: #0284c7; }
input, select { width: 100%; padding: 8px; border: 1px solid #94a3b8; border-radius: 4px; font-size: 13px; margin-bottom: 8px; }
.btn-act { width: 100%; padding: 10px; background: #10b981; color: white; border: none; border-radius: 4px; font-size: 13px; font-weight: bold; cursor: pointer; }
</style></head>
<body>
<div class="header">
    <div><b>🏃‍♂️ फिजिकल ट्रेनर पोर्टल</b><br><small>श्रीगुरु करिअर अकॅडमी</small></div>
    <div><a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">बाहेर पडा</a></div>
</div>
<div class="container">
    <div class="card">
        <h3>🏃‍♂️ आजचा प्रत्यक्ष मैदानी सराव नोंदवा</h3>
        <form action="/save_trainer_practice" method="POST">
            सत्र: <select name="session_time"><option value="सकाळ">सकाळ</option><option value="संध्याकाळ">संध्याकाळ</option></select>
            स्थिती: <select name="ground_status"><option value="सराव योग्य">सराव योग्य</option><option value="पाऊस/चिखल">पाऊस/चिखल</option></select>
            तपशील: <input type="text" name="workout_details" placeholder="उदा. १६०० मी. रनिंग" required>
            <button type="submit" class="btn-act">+ सराव सेव्ह करा</button>
        </form>
    </div>
</div>
</body></html>'''

CLERK_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head><meta charset="UTF-8"><title>Clerk Portal</title>
<style>
* { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
body { margin: 0; background: #eef2f7; }
.header { background: #0b3c5d; color: white; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }
.nav-bar { background: #111c24; display: flex; justify-content: center; gap: 6px; padding: 8px; flex-wrap: wrap; }
.clk-btn { border: none; padding: 8px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 11px; color: white; background: #2563eb; text-decoration: none; display: inline-block; }
.container { max-width: 1200px; margin: 15px auto; padding: 0 10px; }
.card { background: white; padding: 15px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 12px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
th, td { border: 1px solid #ddd; padding: 7px; text-align: left; }
th { background: #0b3c5d; color: white; }
input, select { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; }
.btn-act { padding: 6px 12px; border-radius: 3px; color: white; text-decoration: none; font-size: 11px; font-weight: bold; cursor: pointer; border: none; }
</style></head>
<body>
<div class="header">
    <div><h2>📋 ऑफिस क्लार्क कक्ष</h2><small>श्रीगुरु करिअर अकॅडमी</small></div>
    <div><a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px;">बाहेर पडा</a></div>
</div>
<div class="nav-bar">
    <a href="/inquiries" class="clk-btn" style="background:#b45309;">📞 चौकशी व टेस्ट डेस्क</a>
    <a href="/clerk?tab=adm" class="clk-btn">📝 नवीन प्रवेश</a>
    <a href="/library" target="_blank" class="clk-btn" style="background:#0284c7;">📚 लायब्ररी</a>
</div>
<div class="container">
    <div class="card">
        <h3>📝 नवीन विद्यार्थी प्रवेश नोंदणी</h3>
        <form action="/add_student" method="POST">
            <input type="text" name="name" placeholder="विद्यार्थी पूर्ण नाव" required style="width:100%; margin-bottom:8px;"><br>
            <input type="date" name="admission_date" value="{{ today_date }}" required style="width:100%; margin-bottom:8px;"><br>
            <input type="text" name="course" value="पोलीस भरती" required style="width:100%; margin-bottom:8px;"><br>
            <input type="text" name="phone" placeholder="मोबाईल नंबर" required style="width:100%; margin-bottom:8px;"><br>
            <input type="number" name="total_fees" placeholder="एकूण फी" required style="width:100%; margin-bottom:8px;"><br>
            <input type="number" name="paid_fees" placeholder="भरलेली फी" required style="width:100%; margin-bottom:8px;"><br>
            <button type="submit" class="btn-act" style="background:green;">+ प्रवेश नोंदवा</button>
        </form>
    </div>
</div>
</body></html>'''

ADMIN_DASHBOARD_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head><meta charset="UTF-8"><title>Admin Dashboard - SHREEGURU ACADEMY</title>
<style>
* { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
body { margin: 0; background: #eef2f7; }
.header { background: #0b3c5d; color: white; padding: 12px 20px; text-align: center; }
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
</style></head>
<body>
<div class="header">
    <h1 style="margin:0; color:#ffdd59; font-size:24px;">SHREEGURU CAREER ACADEMY</h1>
    <p style="margin:3px 0 0; font-size:12px;">आडूर, करवीर, कोल्हापूर | संपर्क: ९९२११११९६०</p>
</div>
<div class="menu-bar">
    <a href="/inquiries" class="menu-btn" style="background:#b45309;">📞 चौकशी व टेस्ट डेस्क</a>
    <a href="/admin?tab=students" class="menu-btn">👥 सर्व विद्यार्थी</a>
    <a href="/admin?tab=questions" class="menu-btn" style="background:#059669;">📝 प्रश्न व्यवस्थापन</a>
    <a href="/logout" class="menu-btn" style="background:#ef4444;">Logout</a>
</div>
<div class="container">
    <div class="kpis">
        <div class="kpi"><b>एकूण विद्यार्थी:</b> {{ students|length }}</div>
        <div class="kpi"><b>जमा फी:</b> ₹{{ total_paid }}</div>
        <div class="kpi"><b>शिल्लक फी:</b> ₹{{ total_pending }}</div>
    </div>
    <div class="admin-tab">
        <h3>📋 विद्यार्थी यादी</h3>
        <table>
            <thead><tr><th>Reg</th><th>नाव</th><th>कोर्स</th><th>फोन</th><th>शिल्लक</th></tr></thead>
            <tbody>
                {% for s in students %}
                <tr><td>REG-{{ s.id }}</td><td><b>{{ s.name }}</b></td><td>{{ s.course }}</td><td>{{ s.phone }}</td><td style="color:red;">₹{{ (s.total_fees or 0) - (s.paid_fees or 0) }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
</body></html>'''

# ----------------- APP ROUTES -----------------
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
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            users_list = cursor.fetchall()
    if request.method == 'POST':
        role = request.form.get('role')
        pwd = request.form.get('password')
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE role=%s AND password=%s", (role, pwd))
                user = cursor.fetchone()
        if user:
            session['user_role'] = role
            if role == 'Manager': return redirect('/manager')
            elif role == 'Trainer': return redirect('/trainer')
            elif role == 'Clerk': return redirect('/clerk')
            else: return redirect('/admin')
        else:
            error = "चुकीचा पासवर्ड! पुन्हा प्रयत्न करा."
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

@app.route('/manager')
def manager_view():
    if session.get('user_role') != 'Manager': return redirect(url_for('login'))
    return render_template_string(MANAGER_LAYOUT, curr_tab=request.args.get('tab', 'grocery'), lang=session.get('site_lang', 'mr'))

@app.route('/trainer')
def trainer_view():
    if session.get('user_role') != 'Trainer': return redirect(url_for('login'))
    return render_template_string(TRAINER_LAYOUT, curr_tab=request.args.get('tab', 'practice'), lang=session.get('site_lang', 'mr'))

@app.route('/clerk')
def clerk_view():
    if session.get('user_role') != 'Clerk': return redirect(url_for('login'))
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM students")
            students = cursor.fetchall()
    return render_template_string(CLERK_LAYOUT, curr_tab=request.args.get('tab', 'stud'), students=students, today_date=date.today().strftime("%Y-%m-%d"), lang=session.get('site_lang', 'mr'))

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM students")
            students = cursor.fetchall()
    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    return render_template_string(ADMIN_DASHBOARD_LAYOUT, curr_tab=request.args.get('tab', 'students'), students=students, total_paid=total_paid, total_pending=total_pending, lang=session.get('site_lang', 'mr'))

@app.route('/add_student', methods=['POST'])
def add_student():
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO students (name, course, phone, total_fees, paid_fees, admission_date) VALUES (%s, %s, %s, %s, %s, %s)",
                           (request.form.get('name'), request.form.get('course'), request.form.get('phone'), safe_float(request.form.get('total_fees')), safe_float(request.form.get('paid_fees')), request.form.get('admission_date')))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/inquiries')
def inquiry_desk():
    if session.get('user_role') not in ['Admin', 'Clerk', 'Manager']: return redirect(url_for('login'))
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM admission_inquiries ORDER BY id DESC")
            inquiries = cursor.fetchall()
    return f"<h3>प्रवेश चौकशी डेस्क (एकूण: {len(inquiries)})</h3><a href='/'>होम पेज</a>"

@app.route('/library')
def library_dashboard():
    return "<h3>लायब्ररी व स्टडी लॅब डॅशबोर्ड</h3><a href='/'>होम पेज</a>"

# ----------------- INITIALIZE & RUN -----------------
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

