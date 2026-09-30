import os
import sqlite3   
import shutil
from datetime import date, datetime 
from flask import Flask, redirect, render_template, render_template_string, request, send_file, send_from_directory, url_for, session, Response
from werkzeug.utils import secure_filename
import io
import csv
import urllib.parse
 
app = Flask(__name__)
app.secret_key = "shreeguru_complete_bulletproof_v43_5parts"
DB_NAME = "shreeguru_master_v43.db"

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
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def log_staff_activity(role_name, act_text):
    try:
        with get_db() as conn:
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            conn.execute("INSERT INTO staff_activity_log (staff_role, act_time, activity_text) VALUES (?, ?, ?)", (role_name, now_str, act_text))
            conn.commit()
    except Exception as e:
        print(f"Log Error: {e}")

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        conn.execute("INSERT OR IGNORE INTO users (role, password) VALUES ('Admin', 'admin123')")
        conn.execute("INSERT OR IGNORE INTO users (role, password) VALUES ('Manager', 'manager123')")
        conn.execute("INSERT OR IGNORE INTO users (role, password) VALUES ('Clerk', 'clerk123')")
        conn.execute("INSERT OR IGNORE INTO users (role, password) VALUES ('Trainer', 'trainer123')")

        conn.execute('''CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            category TEXT,
            total_copies INTEGER DEFAULT 1,
            available_copies INTEGER DEFAULT 1
        )''')

        conn.execute('''CREATE TABLE IF NOT EXISTS book_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            student_id INTEGER,
            student_name TEXT,
            issue_date TEXT,
            return_date TEXT,
            status TEXT DEFAULT 'Issued'
        )''')

        conn.execute('''CREATE TABLE IF NOT EXISTS study_lab_seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seat_number TEXT NOT NULL,
            shift TEXT NOT NULL,
            student_id INTEGER,
            student_name TEXT,
            status TEXT DEFAULT 'Available'
        )''')

        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_role TEXT NOT NULL,
                act_time TEXT NOT NULL,
                activity_text TEXT NOT NULL,
                admin_reply TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                req_role TEXT NOT NULL,
                req_date TEXT NOT NULL,
                request_title TEXT NOT NULL,
                request_details TEXT NOT NULL,
                status TEXT DEFAULT 'प्रलंबित (Pending)'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_type TEXT NOT NULL,
                person_id INTEGER NOT NULL,
                att_type TEXT NOT NULL,
                att_date TEXT NOT NULL,
                status TEXT NOT NULL,
                marked_by TEXT DEFAULT 'Staff'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS hostel_mess_fees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS physical_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS written_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                test_date TEXT,
                test_name TEXT,
                subject TEXT,
                total_marks REAL DEFAULT 100,
                obtained_marks REAL DEFAULT 0,
                logged_by TEXT DEFAULT 'Staff'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS trainer_practice_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date TEXT NOT NULL,
                session_time TEXT NOT NULL,
                ground_status TEXT NOT NULL,
                workout_details TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS injuries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                injury_date TEXT NOT NULL,
                injury_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                rest_days INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                phone TEXT NOT NULL,
                salary REAL DEFAULT 0,
                advance_paid REAL DEFAULT 0,
                joining_date TEXT,
                total_leaves INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exp_date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                logged_by TEXT DEFAULT 'Clerk'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS kit_distribution (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                item_details TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                logged_by TEXT DEFAULT 'Clerk'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS discipline_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                record_type TEXT NOT NULL,
                record_date TEXT NOT NULL,
                reason TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS mess_diet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_name TEXT NOT NULL UNIQUE,
                breakfast TEXT,
                lunch TEXT,
                dinner TEXT,
                special_diet TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_role TEXT NOT NULL,
                task_text TEXT NOT NULL,
                task_date TEXT NOT NULL,
                status TEXT DEFAULT 'Unseen'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS canteen_staff_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_name TEXT NOT NULL,
                work_role TEXT NOT NULL
            )
        """)
        conn.execute("INSERT OR IGNORE INTO canteen_staff_list (id, staff_name, work_role) VALUES (1, 'सुरेखा ताई', 'मुख्य स्वयंपाक')")
        conn.execute("INSERT OR IGNORE INTO canteen_staff_list (id, staff_name, work_role) VALUES (2, 'सुनीता ताई', 'चपाती व भांडी')")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS kitchen_staff_att (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_name TEXT NOT NULL,
                att_date TEXT NOT NULL,
                session_time TEXT NOT NULL,
                day_name TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_care_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                care_date TEXT NOT NULL,
                issue_details TEXT NOT NULL,
                special_diet_note TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                staff_name TEXT,
                activity_date TEXT,
                action_text TEXT,
                remark TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                activity_date TEXT,
                diet_plan TEXT,
                remark TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ground_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                test_date TEXT NOT NULL,
                event_name TEXT NOT NULL,
                raw_value REAL NOT NULL,
                marks INTEGER NOT NULL,
                trainer_name TEXT,
                remark TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
         conn.execute("""CREATE TABLE IF NOT EXISTS admission_inquiries (id INTEGER PRIMARY KEY AUTOINCREMENT, inquiry_date TEXT NOT NULL, student_name TEXT NOT NULL, district TEXT NOT NULL, taluka TEXT, phone TEXT NOT NULL, course TEXT NOT NULL, hostel_interest TEXT DEFAULT 'होय', call_status TEXT DEFAULT 'नवीन चौकशी (New)', staff_note TEXT DEFAULT '')""")
            )
         """)
        conn.commit()

        days = ['सोमवार', 'मंगळवार', 'बुधवार', 'गुरुवार', 'शुक्रवार', 'शनिवार', 'रविवार']
        for d in days:
            conn.execute("INSERT OR IGNORE INTO mess_diet (day_name, breakfast, lunch, dinner, special_diet) VALUES (?, 'पोहे / उपमा', 'डाळ, भात, चपाती, उसळ', 'भाकरी, सुकी भाजी, आमटी', 'दूध, केळी, भिजवलेले हरभरे-गूळ')", (d,))
        conn.commit()
     # ----------------- POLICE & DEFENCE HD THEME LOGIN HTML -----------------
LOGIN_HTML = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SHREEGURU DEFENCE ACADEMY - OFFICIAL LOGIN</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body {
            margin: 0; padding: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
            background: linear-gradient(135deg, rgba(5, 20, 36, 0.88), rgba(15, 23, 42, 0.92)),
                        url('https://images.unsplash.com/photo-1541872703-74c5e44368f9?auto=format&fit=crop&w=1920&q=80') center/cover no-repeat;
        }
        .login-box {
            background: rgba(255, 255, 255, 0.97); width: 380px; padding: 35px 30px; border-radius: 12px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6), 0 0 0 2px #d97706; text-align: center; position: relative;
        }
        .insignia {
            background: #b45309; color: #fff; padding: 4px 14px; border-radius: 20px;
            font-size: 11px; font-weight: bold; letter-spacing: 1px; display: inline-block; margin-bottom: 8px;
        }
        .title { color: #0b2545; font-size: 22px; font-weight: 800; margin: 4px 0; }
        .subtitle { font-size: 11px; color: #475569; margin-bottom: 20px; font-weight: 600; line-height: 1.4; }
        select, input {
            width: 100%; padding: 11px 12px; margin-bottom: 15px; border: 1.5px solid #cbd5e1;
            border-radius: 6px; font-size: 13px; font-weight: 600; outline: none;
        }
        select:focus, input:focus { border-color: #0284c7; box-shadow: 0 0 0 3px rgba(2,132,199,0.25); }
        .btn-sub {
            width: 100%; padding: 12px; background: linear-gradient(135deg, #15803d, #16a34a);
            color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold;
            cursor: pointer; letter-spacing: 0.5px; box-shadow: 0 4px 12px rgba(22,163,74,0.3);
        }
        .lang-btn {
            position: absolute; top: 12px; right: 12px; background: #fef08a; color: #854d0e;
            border: 1px solid #facc15; padding: 3px 8px; border-radius: 4px; font-size: 11px;
            font-weight: bold; text-decoration: none;
        }
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

# ----------------- MANAGER PORTAL -----------------
MANAGER_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ 'Manager Portal' if lang == 'en' else 'व्यवस्थापिका कक्ष' }} - Shreeguru Academy</title>
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
    </style>
</head>
<body>
<div class="header">
    <div>
        <h2 style="margin:0; font-size:19px; color:#fde047;">🌸 {{ 'MANAGER PORTAL' if lang == 'en' else 'व्यवस्थापिका कक्ष' }}</h2>
        <small>श्रीगुरु करिअर अकॅडमी | सौ. नीलम सचिन चौगले</small>
    </div>
    <div>
        <a href="/toggle_lang" style="background:#ffdd59; color:#064e3b; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold; text-decoration:none; margin-right:8px;">🌐 {{ 'MR (मराठी)' if lang == 'en' else 'EN (English)' }}</a>
        <a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">{{ 'Logout' if lang == 'en' else 'बाहेर पडा' }}</a>
    </div>
</div>

<div class="nav-bar">
    <a href="/manager?tab=grocery" class="mgr-btn {% if curr_tab == 'grocery' %}active{% endif %}">🛒 {{ 'Grocery Slip' if lang == 'en' else '१-क्लिक किराणा स्लिप' }}</a>
    <a href="/library" target="_blank" class="mgr-btn" style="background: linear-gradient(135deg, #0284c7, #06b6d4); color: white;">📚 स्टडी लॅब / लायब्ररी</a>
    <a href="/manager?tab=diet" class="mgr-btn {% if curr_tab == 'diet' %}active{% endif %}">🍱 {{ 'Food Menu' if lang == 'en' else 'शाकाहारी डाएट शेड्युल' }}</a>
    <a href="/manager?tab=cook" class="mgr-btn {% if curr_tab == 'cook' %}active{% endif %}">👩‍🍳 {{ 'Kitchen Attendance' if lang == 'en' else 'स्वयंपाकी महिला हजेरी' }}</a>
    <a href="/manager?tab=physical" class="mgr-btn {% if curr_tab == 'physical' %}active{% endif %}" style="background:#0284c7; color:white;">🏃‍♂️ {{ 'Physical Records' if lang == 'en' else 'फिजिकल रेकॉर्ड' }}</a>
    <a href="/manager?tab=written" class="mgr-btn {% if curr_tab == 'written' %}active{% endif %}" style="background:#10b981; color:white;">📝 {{ 'Written Exam' if lang == 'en' else 'रिटर्न टेस्ट रेकॉर्ड' }}</a>
    <a href="/manager?tab=care" class="mgr-btn {% if curr_tab == 'care' %}active{% endif %}">🌸 {{ 'Hostel Care' if lang == 'en' else 'मुलींचे हॉस्टेल व काळजी' }}</a>
    <a href="/manager?tab=req" class="mgr-btn {% if curr_tab == 'req' %}active{% endif %}" style="background:#e11d48; color:white;">📩 {{ 'Send Request' if lang == 'en' else 'ॲडमिनला विनंती' }}</a>
    <a href="/manager?tab=tasks" class="mgr-btn {% if curr_tab == 'tasks' %}active{% endif %}">📢 {{ 'Tasks' if lang == 'en' else 'संचालक सूचना' }}</a>
</div>

<div class="container">
    {% if curr_tab == 'grocery' %}
    <div class="card" style="border-left:5px solid #059669;">
        <form method="POST" id="groceryForm">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                    <h3 style="margin:0; color:#065f46;">🛒 {{ 'Canteen Complete Grocery & Veg Slip' if lang == 'en' else 'कॅन्टीन संपूर्ण किराणा, भाजीपाला व डाएट खरेदी स्लिप' }}</h3>
                </div>
                <div>
                    <button type="submit" formaction="/print_grocery_slip" formtarget="_blank" class="btn-act" style="background:#059669;">🖨️ {{ 'Print Slip' if lang == 'en' else 'खरेदी पावती प्रिंट' }}</button>
                    <button type="submit" formaction="/whatsapp_grocery_slip" formtarget="_blank" class="btn-act" style="background:#25D366;">📲 WhatsApp</button>
                </div>
            </div>
            <hr style="margin:12px 0;">

            <h4 style="color:#b45309; margin:0 0 8px;">⭐ १. रोज लागणारे महत्त्वाचे साहित्य (Top Priority)</h4>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:10px; background:#fffbeb; padding:12px; border-radius:6px; margin-bottom:12px;">
                <div>
                    <b style="color:#b45309;">ताजी भाजी व नाश्ता:</b><br><br>
                    <label class="g-label"><input type="checkbox" name="items" value="कांदे"> कांदे: <input type="text" name="qty_कांदे" placeholder="१० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="बटाटे"> बटाटे: <input type="text" name="qty_बटाटे" placeholder="१० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="टोमॅटो"> टोमॅटो: <input type="text" name="qty_टोमॅटो" placeholder="५ kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="हिरवी मिरची"> हिरवी मिरची: <input type="text" name="qty_हिरवी मिरची" placeholder="१ kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="कोथिंबीर"> कोथिंबीर: <input type="text" name="qty_कोथिंबीर" placeholder="२ जुड्या" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="चालू भाजी"> चालू भाजी: <input type="text" name="qty_चालू भाजी" placeholder="५ kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="आले-लसूण"> आले-लसूण: <input type="text" name="qty_आले-लसूण" placeholder="२ kg" style="width:75px;"></label>
                </div>
                <div>
                    <b style="color:#b45309;">दूध, अंडी व डाएट:</b><br><br>
                    <label class="g-label"><input type="checkbox" name="items" value="ताजे दूध (लिटर)"> ताजं दूध: <input type="text" name="qty_ताजे दूध (लिटर)" placeholder="१५ लिटर" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="केळी (डझन)"> केळी: <input type="text" name="qty_केळी (डझन)" placeholder="५ डझन" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="देशी चणे"> देशी चणे: <input type="text" name="qty_देशी चणे" placeholder="५ kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="गूळ"> सेंद्रिय गूळ: <input type="text" name="qty_गूळ" placeholder="५ kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="अंडी (ट्रे)"> अंडी (ट्रे): <input type="text" name="qty_अंडी (ट्रे)" placeholder="१ ट्रे" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="जाड पोहे"> जाड पोहे: <input type="text" name="qty_जाड पोहे" placeholder="१० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="बारीक रवा"> बारीक रवा: <input type="text" name="qty_बारीक रवा" placeholder="५ kg" style="width:75px;"></label>
                </div>
                <div>
                    <b style="color:#b45309;">अन्नधान्य व तेल:</b><br><br>
                    <label class="g-label"><input type="checkbox" name="items" value="गहू पीठ (आटा)"> गहू पीठ: <input type="text" name="qty_गहू पीठ (आटा)" placeholder="५० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="तांदूळ"> तांदूळ: <input type="text" name="qty_तांदूळ" placeholder="५० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="गोडेतेल (डबा)"> गोडेतेल: <input type="text" name="qty_गोडेतेल (डबा)" placeholder="१ डबा" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="तूर डाळ"> तूर डाळ: <input type="text" name="qty_तूर डाळ" placeholder="१० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="ज्वारी पीठ"> ज्वारी पीठ: <input type="text" name="qty_ज्वारी पीठ" placeholder="१० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="बाजरी पीठ"> बाजरी पीठ: <input type="text" name="qty_बाजरी पीठ" placeholder="१० kg" style="width:75px;"></label>
                    <label class="g-label"><input type="checkbox" name="items" value="मीठ पुडे"> मीठ: <input type="text" name="qty_मीठ पुडे" placeholder="२ पुडे" style="width:75px;"></label>
                </div>
            </div>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'diet' %}
    <div class="card">
        <h3 style="margin:0 0 10px; color:#065f46;">🍱 {{ 'Weekly Veg Food Menu' if lang == 'en' else 'साप्ताहिक शाकाहारी जेवण वेळापत्रक' }}</h3>
        <table>
            <thead><tr><th>वार</th><th>सकाळ नाश्ता</th><th>दुपार जेवण</th><th>रात्र जेवण</th><th>विशेष आहार</th><th>सेव्ह</th></tr></thead>
            <tbody>
                {% for d in diet_list %}
                <form action="/update_diet/{{ d.id }}" method="POST">
                <tr>
                    <td><b>{{ d.day_name }}</b></td>
                    <td><input type="text" name="breakfast" value="{{ d.breakfast }}" style="width:90%;"></td>
                    <td><input type="text" name="lunch" value="{{ d.lunch }}" style="width:90%;"></td>
                    <td><input type="text" name="dinner" value="{{ d.dinner }}" style="width:90%;"></td>
                    <td><input type="text" name="special_diet" value="{{ d.special_diet }}" style="width:90%;"></td>
                    <td><button type="submit" class="btn-act" style="background:#059669;">सेव्ह 💾</button></td>
                </tr>
                </form>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'cook' %}
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="margin:0; color:#065f46;">👩‍🍳 {{ 'Kitchen Staff Attendance' if lang == 'en' else 'स्वयंपाकी महिला कर्मचारी हजेरी' }}</h3>
            <button onclick="document.getElementById('addCookBox').style.display='block'" class="btn-act" style="background:#0b3c5d;">+ नवीन कर्मचारी जोडा</button>
        </div>
        <div id="addCookBox" style="display:none; background:#f0fdf4; border:1px solid #bbf7d0; padding:10px; border-radius:6px; margin-top:10px;">
            <form action="/add_canteen_staff" method="POST">
                नाव: <input type="text" name="staff_name" required> काम: <input type="text" name="work_role" required>
                <button type="submit" class="btn-act" style="background:green;">सेव्ह</button>
            </form>
        </div>
        <hr style="margin:12px 0;">
        <form action="/save_kitchen_att_dynamic" method="POST">
            <div style="display:flex; gap:10px; margin-bottom:10px;">
                <div>तारीख: <input type="date" name="att_date" value="{{ today_date }}" required></div>
                <div>सत्र: <select name="session_time"><option value="सकाळ सत्र">🌅 सकाळ</option><option value="संध्याकाळ सत्र">🌇 संध्याकाळ</option></select></div>
            </div>
            <table>
                <thead><tr><th>नाव</th><th>काम</th><th>हजेरी</th><th>हटवा</th></tr></thead>
                <tbody>
                    {% for cs in canteen_staff %}
                    <tr>
                        <td><b>{{ cs.staff_name }}</b></td><td>{{ cs.work_role }}</td>
                        <td>
                            <label><input type="radio" name="status_{{ cs.id }}" value="हजर" checked> P</label>
                            <label style="margin-left:10px; color:red;"><input type="radio" name="status_{{ cs.id }}" value="रजा"> A</label>
                        </td>
                        <td><a href="/delete_canteen_staff/{{ cs.id }}" onclick="return confirm('हटवायचे?')" style="color:red; font-weight:bold;">🗑️</a></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <br><button type="submit" class="btn-act" style="background:#059669;">💾 हजेरी सेव्ह करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'physical' %}
    <div class="card">
        <h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ {{ 'Physical Test Records' if lang == 'en' else 'सर्व विद्यार्थ्यांचे फिजिकल टेस्ट रेकॉर्ड' }}</h3>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>कोर्स</th><th>1600/800m</th><th>100m</th><th>गोळाफेक</th><th>पुल-अप्स</th><th>एकूण गुण</th></tr></thead>
            <tbody>
                {% for pt in physical_records %}
                <tr>
                    <td>{{ pt.test_date }}</td><td><b>{{ pt.name }}</b></td><td>{{ pt.course }}</td>
                    <td>{{ pt.run_time or '-' }}</td><td>{{ pt.sprint_time or '-' }}</td><td>{{ pt.shot_put_dist or '-' }} मी.</td>
                    <td>{{ pt.pullups }}</td><td><b style="color:green;">{{ pt.total_obtained }}/50</b></td>
                </tr>
                {% else %}<tr><td colspan="8">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'written' %}
    <div class="card">
        <h3 style="color:#10b981; margin-top:0;">📝 {{ 'Written Exam Records' if lang == 'en' else 'विद्यार्थ्यांचे रिटर्न टेस्ट रेकॉर्ड' }}</h3>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>परीक्षेचे नाव</th><th>विषय</th><th>एकूण</th><th>मिळालेले गुण</th></tr></thead>
            <tbody>
                {% for wt in written_records %}
                <tr><td>{{ wt.test_date }}</td><td><b>{{ wt.name }}</b></td><td>{{ wt.test_name }}</td><td>{{ wt.subject or '-' }}</td><td>{{ wt.total_marks }}</td><td><b style="color:green;">{{ wt.obtained_marks }}</b></td></tr>
                {% else %}<tr><td colspan="6">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'care' %}
    <div class="card">
        <h3 style="color:#db2777; margin-top:0;">🌸 {{ 'Girls Hostel & Student Care' if lang == 'en' else 'मुलींचे हॉस्टेल व विद्यार्थी काळजी नोंद' }}</h3>
        <form action="/add_care_log" method="POST">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select><br><br>
            आरोग्य अडचण / आजारपण: <input type="text" name="issue_details" required style="width:100%;"><br><br>
            विशेष आहार सूचना: <input type="text" name="special_diet_note" style="width:100%;"><br><br>
            <button type="submit" class="btn-act" style="background:#db2777;">+ नोंद सेव्ह करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'req' %}
    <div class="card">
        <h3 style="color:#e11d48; margin-top:0;">📩 {{ 'Send Request to Director' if lang == 'en' else 'संचालकांना विनंती पाठवा व स्टेटस' }}</h3>
        <form action="/send_staff_request" method="POST" style="background:#fff1f2; padding:12px; border-radius:6px; margin-bottom:15px;">
            विषय: <input type="text" name="request_title" required style="width:100%; margin-bottom:8px;"><br>
            तपशील: <textarea name="request_details" required style="width:100%; height:60px;"></textarea><br><br>
            <button type="submit" class="btn-act" style="background:#e11d48;">+ विनंती पाठवा</button>
        </form>
        <h4>📋 तुम्ही पाठवलेल्या विनंत्यांचा इतिहास व निर्णय:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>विषय</th><th>तपशील</th><th>स्थिती</th></tr></thead>
            <tbody>
                {% for r in my_requests %}
                <tr><td>{{ r.req_date }}</td><td><b>{{ r.request_title }}</b></td><td>{{ r.request_details }}</td><td><b style="color:{% if 'स्वीकृत' in r.status %}green{% elif 'नाकारली' in r.status %}red{% else %}orange{% endif %};">{{ r.status }}</b></td></tr>
                {% else %}<tr><td colspan="4">कोणतीही विनंती नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'tasks' %}
    <div class="card">
        <h3 style="color:#065f46; margin-top:0;">📢 {{ 'Director Instructions' if lang == 'en' else 'संचालकांनी दिलेल्या सूचना' }}</h3>
        <table>
            <thead><tr><th>तारीख</th><th>काम / सूचना</th><th>स्थिती</th><th>कृती</th></tr></thead>
            <tbody>
                {% for t in staff_tasks %}
                {% if t.target_role in ['Manager', 'सर्व'] %}
                <tr>
                    <td>{{ t.task_date }}</td><td><b>{{ t.task_text }}</b></td>
                    <td><b style="color:{% if t.status=='Seen' %}#0284c7{% else %}orange{% endif %};">{{ 'Seen ✓✓' if t.status=='Seen' else 'Unseen' }}</b></td>
                    <td>{% if t.status != 'Seen' %}<a href="/mark_task_seen/{{ t.id }}" class="btn-act" style="background:#0284c7;">वाचले ✓✓</a>{% else %}-{% endif %}</td>
                </tr>
                {% endif %}
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
</div>
</body>
</html>'''
# ----------------- PHYSICAL TRAINER / COACH PORTAL -----------------
TRAINER_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coach Portal - Shreeguru Academy</title>
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
        input, select { width: 100%; padding: 8px; background: white; border: 1px solid #94a3b8; border-radius: 4px; font-size: 13px; margin-bottom: 8px; }
        .btn-act { width: 100%; padding: 10px; background: #10b981; color: white; border: none; border-radius: 4px; font-size: 13px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
<div class="header">
    <div><b style="font-size:16px;">🏃‍♂️ {{ 'COACH / TRAINER PORTAL' if lang == 'en' else 'फिजिकल ट्रेनर पोर्टल' }}</b><br><small style="color:#e0f2fe;">श्रीगुरु करिअर अकॅडमी</small></div>
    <div>
        <a href="/toggle_lang" style="background:#ffdd59; color:#0284c7; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold; text-decoration:none; margin-right:8px;">🌐 {{ 'MR (मराठी)' if lang == 'en' else 'EN (English)' }}</a>
        <a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">बाहेर पडा</a>
    </div>
</div>
<div class="nav-bar">
    <a href="/trainer?tab=practice" class="nav-btn {% if curr_tab == 'practice' %}active{% endif %}">🏃‍♂️ {{ 'Practice' if lang == 'en' else 'आजचा सराव' }}</a>
    <a href="/trainer?tab=stopwatch" class="nav-btn {% if curr_tab == 'stopwatch' %}active{% endif %}" style="background:#f59e0b; color:#111;">⏱️ {{ 'Stopwatch' if lang == 'en' else 'स्टॉपवॉच' }}</a>
    <a href="/trainer?tab=physical" class="nav-btn {% if curr_tab == 'physical' %}active{% endif %}">🏃‍♂️ {{ 'Physical Test' if lang == 'en' else 'फिजिकल रेकॉर्ड नोंद' }}</a>
    <a href="/trainer?tab=student_diet" class="nav-btn {% if curr_tab == 'student_diet' %}active{% endif %}" style="background:#10b981; color:white;">🥗 {{ 'Diet Plan' if lang == 'en' else 'डाएट शिफारस' }}</a>
    <a href="/trainer?tab=att" class="nav-btn {% if curr_tab == 'att' %}active{% endif %}">📋 {{ 'Attendance' if lang == 'en' else 'मैदानी हजेरी' }}</a>
    <a href="/trainer?tab=written" class="nav-btn {% if curr_tab == 'written' %}active{% endif %}">📝 {{ 'Written Exam' if lang == 'en' else 'रिटर्न टेस्ट' }}</a>
    <a href="/trainer?tab=inj" class="nav-btn {% if curr_tab == 'inj' %}active{% endif %}">🩹 {{ 'Injuries' if lang == 'en' else 'इजा व सुट्टी नोंद' }}</a>
    <a href="/trainer?tab=req" class="nav-btn {% if curr_tab == 'req' %}active{% endif %}" style="background:#e11d48; color:white;">📩 {{ 'Request' if lang == 'en' else 'ॲडमिनला विनंती' }}</a>
    <a href="/trainer?tab=tasks" class="nav-btn {% if curr_tab == 'tasks' %}active{% endif %}">📢 {{ 'Tasks' if lang == 'en' else 'ॲडमिन सूचना' }}</a>
</div>
<div class="container">
    {% if curr_tab == 'practice' %}
    <div class="card">
        <h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ {{ 'Daily Practice Entry' if lang == 'en' else 'आजचा प्रत्यक्ष मैदानी सराव नोंदवा' }}</h3>
        <form action="/save_trainer_practice" method="POST">
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                <div>
                    सत्र: 
                    <select name="session_time">
                        <option value="सकाळ सत्र (Morning)">🌅 सकाळ सत्र (Morning)</option>
                        <option value="संध्याकाळ सत्र (Evening)">🌇 संध्याकाळ सत्र (Evening)</option>
                    </select>
                </div>
                <div>
                    मैदानाची प्रत्यक्ष स्थिती (Ground Status):
                    <select name="ground_status">
                        <option value="सराव योग्य (Ground Ready)">✔️ सराव योग्य (Ground Ready)</option>
                        <option value="पावसामुळे ग्राउंड ओले / चिखल">🌧️ पावसामुळे ग्राउंड ओले / चिखल</option>
                        <option value="ट्रॅक दुरुस्ती सुरू">🛠️ ट्रॅक दुरुस्ती काम सुरू</option>
                        <option value="खराब हवामान / मुसळधार पाऊस">⛈️ खराब हवामान / मुसळधार पाऊस</option>
                        <option value="इतर तांत्रिक अडचण">⚠️ इतर अडचणीमुळे ग्राउंड होऊ शकले नाही</option>
                    </select>
                </div>
            </div>
            सराव तपशील / कारण:
            <input type="text" name="workout_details" placeholder="उदा. १६०० मी. ५ राउंड्स टाईम ट्रायल किंवा पावसामुळे इनडोअर व्यायाम घेतला" required>
            <button type="submit" class="btn-act">+ आजचा सराव ॲडमिनकडे नोंदवा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'stopwatch' %}
    <div class="card" style="text-align:center;">
        <h3 style="color:#0284c7; margin-top:0;">⏱️ डिजिटल मैदानी स्टॉपवॉच (लॅप फिचरसह)</h3>
        <div id="sw_display" style="font-size:46px; font-weight:bold; color:#0b3c5d; font-family:monospace; margin:15px 0;">00:00.00</div>
        <div style="display:flex; justify-content:center; gap:8px; flex-wrap:wrap;">
            <button onclick="startSW()" class="btn-act" style="background:green; width:95px;">Start ▶️</button>
            <button onclick="pauseSW()" class="btn-act" style="background:#f59e0b; width:95px;">Pause ⏸️</button>
            <button onclick="lapSW()" class="btn-act" style="background:#0284c7; width:95px;">Lap ⏱️</button>
            <button onclick="resetSW()" class="btn-act" style="background:red; width:95px;">Reset 🔄</button>
        </div>
        <div style="max-width:320px; margin:15px auto 0; text-align:left;">
            <b>लॅप नोंदी:</b>
            <table id="lap_table"><thead><tr><th>Lap</th><th>Split Time</th></tr></thead><tbody></tbody></table>
        </div>
    </div>
    <script>
    var sw_t, sw_ms = 0, lap_c = 0;
    function startSW() { if(!sw_t) { sw_t = setInterval(function() { sw_ms += 10; updateSW(); }, 10); } }
    function pauseSW() { clearInterval(sw_t); sw_t = null; }
    function resetSW() { pauseSW(); sw_ms = 0; lap_c = 0; updateSW(); document.querySelector("#lap_table tbody").innerHTML = ""; }
    function lapSW() {
        if(sw_ms > 0) {
            lap_c++;
            var cur = document.getElementById('sw_display').innerText;
            document.querySelector("#lap_table tbody").insertAdjacentHTML('afterbegin', "<tr><td>Lap " + lap_c + "</td><td><b>" + cur + "</b></td></tr>");
        }
    }
    function updateSW() {
        var m = Math.floor(sw_ms / 60000), s = Math.floor((sw_ms % 60000) / 1000), cs = Math.floor((sw_ms % 1000) / 10);
        document.getElementById('sw_display').innerText = String(m).padStart(2,'0') + ":" + String(s).padStart(2,'0') + "." + String(cs).padStart(2,'0');
    }
    </script>
    {% endif %}

    {% if curr_tab == 'physical' %}
    <div class="card">
        <h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ फिजिकल चाचणी गुण भरणे व तक्ता</h3>
        <form action="/add_physical_record" method="POST" style="background:#f0f9ff; padding:12px; border-radius:6px; margin-bottom:15px;">
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:8px;">
                <div>विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></div>
                <div>तारीख: <input type="date" name="test_date" value="{{ today_date }}" required></div>
                <div>१६००/८०० मी.: <input type="text" name="run_time" placeholder="05:10"></div>
                <div>१०० मी.: <input type="text" name="sprint_time" placeholder="12.2s"></div>
                <div>गोळाफेक: <input type="text" name="shot_put_dist" placeholder="8.5m"></div>
                <div>पुल-अप्स: <input type="number" name="pullups" value="8"></div>
                <div>एकूण गुण: <input type="number" name="total_obtained" placeholder="45" required></div>
            </div>
            <br><button type="submit" class="btn-act" style="background:#0284c7;">+ फिजिकल गुण सेव्ह करा</button>
        </form>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>1600m</th><th>100m</th><th>गोळा</th><th>पुल-अप्स</th><th>एकूण</th></tr></thead>
            <tbody>
                {% for pt in physical_records %}
                <tr><td>{{ pt.test_date }}</td><td><b>{{ pt.name }}</b></td><td>{{ pt.run_time }}</td><td>{{ pt.sprint_time }}</td><td>{{ pt.shot_put_dist }}</td><td>{{ pt.pullups }}</td><td><b style="color:green;">{{ pt.total_obtained }}/50</b></td></tr>
                {% else %}<tr><td colspan="7">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'student_diet' %}
    <div class="card">
        <h3 style="color:#10b981; margin-top:0;">🥗 विद्यार्थीनिहाय विशेष डाएट शिफारस</h3>
        <form action="/save_trainer_student_diet" method="POST" style="background:#f0fdf4; padding:12px; border-radius:6px; margin-bottom:15px;">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            डाएट शिफारस: <input type="text" name="diet_text" placeholder="उदा. रोज २ केळी व हळदीचे दूध, रनिंगनंतर ओआरएस" required>
            <button type="submit" class="btn-act" style="background:#10b981;">+ डाएट शिफारस नोंदवा</button>
        </form>
        <h4>📋 तुम्ही दिलेल्या डाएट शिफारशींची नोंदवही:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>दिलेला डाएट प्लॅन</th></tr></thead>
            <tbody>
                {% for sc in trainer_diet_logs %}
                <tr><td>{{ sc.care_date }}</td><td><b>{{ sc.name }}</b></td><td>{{ sc.special_diet_note }}</td></tr>
                {% else %}<tr><td colspan="3">सध्या कोणतीही डाएट शिफारस दिलेली नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'inj' %}
    <div class="card">
        <h3 style="color:#ef4444; margin-top:0;">🩹 विद्यार्थी इजा व सुट्टी नोंद</h3>
        <form action="/add_injury" method="POST" style="background:#fff1f2; padding:12px; border-radius:6px; margin-bottom:15px;">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            इजा प्रकार: <input type="text" name="injury_type" placeholder="उदा. शिन स्प्लिंट" required>
            सुट्टी दिवस: <input type="number" name="rest_days" value="2">
            <button type="submit" class="btn-act" style="background:#ef4444;">+ इजा नोंदवा</button>
        </form>
        <h4>📋 इजा झालेल्या विद्यार्थ्यांची सुट्टी नोंदवही:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>इजा</th><th>सुट्टी दिवस</th></tr></thead>
            <tbody>
                {% for inj in trainer_injury_logs %}
                <tr><td>{{ inj.injury_date }}</td><td><b>{{ inj.name }}</b></td><td>{{ inj.injury_type }}</td><td><b>{{ inj.rest_days }} दिवस</b></td></tr>
                {% else %}<tr><td colspan="4">सध्या कोणतीही इजा नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'att' %}
    <div class="card">
        <h3 style="color:#0284c7; margin-top:0;">📋 सकाळ/संध्याकाळ मैदानी हजेरी</h3>
        <form action="/save_coach_attendance" method="POST">
            <select name="att_type"><option value="सकाळचे ग्राउंड सत्र">🌅 सकाळ सत्र</option><option value="संध्याकाळचे ग्राउंड सत्र">🌇 संध्याकाळ सत्र</option></select>
            <table>
                <thead><tr><th>नाव</th><th>कोर्स</th><th>हजेरी</th></tr></thead>
                <tbody>
                    {% for s in students %}
                    <tr>
                        <td><b>{{ s.name }}</b></td><td>{{ s.course }}</td>
                        <td>
                            <label style="color:#10b981; font-weight:bold;"><input type="radio" name="status_{{ s.id }}" value="हजर" checked> P</label>
                            <label style="color:#ef4444; font-weight:bold; margin-left:10px;"><input type="radio" name="status_{{ s.id }}" value="गैरहजर"> A</label>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <br><button type="submit" class="btn-act">💾 हजेरी सेव्ह करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'written' %}
    <div class="card">
        <h3 style="color:#10b981; margin-top:0;">📝 विद्यार्थ्यांचे रिटर्न टेस्ट रेकॉर्ड</h3>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>परीक्षा</th><th>गुण</th></tr></thead>
            <tbody>
                {% for wt in written_records %}
                <tr><td>{{ wt.test_date }}</td><td><b>{{ wt.name }}</b></td><td>{{ wt.test_name }}</td><td><b>{{ wt.obtained_marks }}/{{ wt.total_marks }}</b></td></tr>
                {% else %}<tr><td colspan="4">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'req' %}
    <div class="card">
        <h3 style="color:#e11d48; margin-top:0;">📩 संचालकांना विनंती पाठवा व स्टेटस</h3>
        <form action="/send_staff_request" method="POST" style="background:#fff1f2; padding:12px; border-radius:6px; margin-bottom:15px;">
            विषय: <input type="text" name="request_title" required><br>
            तपशील: <textarea name="request_details" required style="width:100%; height:60px;"></textarea><br><br>
            <button type="submit" class="btn-act" style="background:#e11d48;">+ विनंती पाठवा</button>
        </form>
        <h4>📋 पाठवलेल्या विनंत्यांचा इतिहास:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>विषय</th><th>तपशील</th><th>स्थिती</th></tr></thead>
            <tbody>
                {% for r in my_requests %}
                <tr><td>{{ r.req_date }}</td><td><b>{{ r.request_title }}</b></td><td>{{ r.request_details }}</td><td><b style="color:{% if 'स्वीकृत' in r.status %}green{% elif 'नाकारली' in r.status %}red{% else %}orange{% endif %};">{{ r.status }}</b></td></tr>
                {% else %}<tr><td colspan="4">कोणतीही विनंती नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'tasks' %}
    <div class="card">
        <h3 style="color:#d97706; margin-top:0;">📢 संचालकांनी दिलेली कामे</h3>
        <table>
            <thead><tr><th>तारीख</th><th>काम / सूचना</th><th>स्थिती</th><th>कृती</th></tr></thead>
            <tbody>
                {% for t in staff_tasks %}
                {% if t.target_role in ['Trainer', 'सर्व'] %}
                <tr>
                    <td>{{ t.task_date }}</td><td><b>{{ t.task_text }}</b></td>
                    <td><b>{{ t.status }}</b></td>
                    <td>{% if t.status != 'Seen' %}<a href="/mark_task_seen/{{ t.id }}" class="btn-act" style="background:#0284c7;">वाचले ✓✓</a>{% else %}-{% endif %}</td>
                </tr>
                {% endif %}
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- CLERK PORTAL -----------------
CLERK_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8"><title>Clerk Portal - Shreeguru Academy</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #eef2f7; }
        .header { background: #0b3c5d; color: white; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }
        .nav-bar { background: #111c24; display: flex; justify-content: center; gap: 6px; padding: 8px; flex-wrap: wrap; }
        .clk-btn { border: none; padding: 8px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 11px; color: white; background: #2563eb; text-decoration: none; display: inline-block; }
        .clk-btn.active { background: #f59e0b !important; }
        .container { max-width: 1200px; margin: 15px auto; padding: 0 10px; }
        .card { background: white; padding: 15px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 12px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #ddd; padding: 7px; text-align: left; }
        th { background: #0b3c5d; color: white; }
        input, select { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; }
        .btn-act { padding: 6px 12px; border-radius: 3px; color: white; text-decoration: none; font-size: 11px; font-weight: bold; cursor: pointer; border: none; display: inline-block; }
    </style>
</head>
<body>
<div class="header">
    <div><h2 style="margin:0; font-size:18px;">📋 {{ 'OFFICE CLERK PORTAL' if lang == 'en' else 'ऑफिस क्लार्क कक्ष' }}</h2><small>श्रीगुरु करिअर अकॅडमी</small></div>
    <div>
        <a href="/toggle_lang" style="background:#ffdd59; color:#0b3c5d; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold; text-decoration:none; margin-right:8px;">🌐 {{ 'MR (मराठी)' if lang == 'en' else 'EN (English)' }}</a>
        <a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">बाहेर पडा</a>
    </div>
</div>
<div class="nav-bar"> 
    <a href="/clerk?tab=stud" class="clk-btn {% if curr_tab == 'stud' %}active{% endif %}">👥 {{ 'Students List' if lang == 'en' else 'विद्यार्थी यादी' }}</a>
    <a href="/clerk?tab=adm" class="clk-btn {% if curr_tab == 'adm' %}active{% endif %}">📝 {{ 'New Admission' if lang == 'en' else 'नवीन प्रवेश' }}</a>
    <a href="/clerk?tab=fee" class="clk-btn {% if curr_tab == 'fee' %}active{% endif %}">💰 {{ 'Collect Fee' if lang == 'en' else 'फी जमा' }}</a>
    <a href="/attendance" target="_blank" class="clk-btn" style="background: linear-gradient(135deg, #6366f1, #a855f7); color: white; font-weight: bold; border-radius: 4px; padding: 6px 12px; text-decoration: none; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">📋 हजेरी</a>
    <a href="/library" target="_blank" class="clk-btn" style="background: linear-gradient(135deg, #0284c7, #06b6d4); color: white; font-weight: bold; border-radius: 4px; padding: 6px 12px; text-decoration: none; box-shadow: 0 2px 5px rgba(0,0,0,0.2); margin-left: 6px;">📚 स्टडी लॅब / लायब्ररी</a>
    <a href="/clerk?tab=hostel" class="clk-btn {% if curr_tab == 'hostel' %}active{% endif %}" style="background:#8e2de2;">🏠 {{ 'Hostel/Mess Fee' if lang == 'en' else 'हॉस्टेल/मेस फी' }}</a>
    <a href="/clerk?tab=physical" class="clk-btn {% if curr_tab == 'physical' %}active{% endif %}" style="background:#0284c7;">🏃‍♂️ {{ 'Physical Test' if lang == 'en' else 'फिजिकल टेस्ट नोंद' }}</a>
    <a href="/clerk?tab=written" class="clk-btn {% if curr_tab == 'written' %}active{% endif %}" style="background:#10b981;">📝 {{ 'Written Exam' if lang == 'en' else 'रिटर्न टेस्ट नोंद' }}</a>
    <a href="/clerk?tab=exp" class="clk-btn {% if curr_tab == 'exp' %}active{% endif %}">💵 {{ 'Expense Entry' if lang == 'en' else 'खर्च नोंद' }}</a>
    <a href="/clerk?tab=kit" class="clk-btn {% if curr_tab == 'kit' %}active{% endif %}">📦 {{ 'Kit Distribution' if lang == 'en' else 'किट वाटप' }}</a>
    <a href="/clerk?tab=req" class="clk-btn {% if curr_tab == 'req' %}active{% endif %}" style="background:#e11d48;">📩 {{ 'Send Request' if lang == 'en' else 'ॲडमिनला विनंती' }}</a>
    <a href="/clerk?tab=tasks" class="clk-btn {% if curr_tab == 'tasks' %}active{% endif %}">📢 {{ 'Tasks' if lang == 'en' else 'ॲडमिन सूचना' }}</a>
</div>
<div class="container">
    {% if curr_tab == 'stud' %}
    <div class="card">
        <h3>📋 सर्व विद्यार्थी यादी</h3>
        <table>
            <thead><tr><th>फोटो</th><th>Reg</th><th>नाव</th><th>कोर्स</th><th>फोन</th><th>शिल्लक फी</th><th>पावती</th></tr></thead>
            <tbody>
                {% for s in students %}
                <tr>
                    <td>{% if s.photo_filename %}<img src="/uploads/{{ s.photo_filename }}" width="35" height="40">{% else %}-{% endif %}</td>
                    <td>REG-{{ s.id }}</td><td><b>{{ s.name }}</b></td><td>{{ s.course }}</td><td>{{ s.phone }}</td>
                    <td style="color:red; font-weight:bold;">₹{{ (s.total_fees or 0) - (s.paid_fees or 0) }}</td>
                    <td><a href="/receipt/{{ s.id }}" target="_blank" class="btn-act" style="background:#10b981;">🧾 पावती प्रिंट</a><a href="/student_report/{{ s.id }}" target="_blank" class="btn-act" style="background:#6366f1; color:white; text-decoration:none; padding:4px 8px; border-radius:4px; font-weight:bold; margin-left:5px;">📋 स्टुडन्ट रिपोर्ट</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'hostel' %}
    <div class="card">
        <h3 style="color:#8e2de2; margin-top:0;">🏠 हॉस्टेल व मेस फी जमा (क्लार्क डेस्क)</h3>
        <form action="/add_hostel_fee" method="POST" style="background:#fdf4ff; padding:12px; border-radius:6px; margin-bottom:15px;">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            रक्कम: <input type="number" name="paid_amount" placeholder="भरलेली रक्कम (₹)" required>
            <button type="submit" class="btn-act" style="background:#8e2de2;">+ हॉस्टेल फी जमा करा</button>
        </form>
        <h4>📋 जमा हॉस्टेल व मेस फी इतिहास:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>पॅकेज</th><th>जमा रक्कम</th></tr></thead>
            <tbody>
                {% for h in hostel_logs %}
                <tr><td>{{ h.pay_date }}</td><td><b>{{ h.name }}</b></td><td>{{ h.package_type }}</td><td style="color:green; font-weight:bold;">₹{{ h.paid_amount }}</td></tr>
                {% else %}<tr><td colspan="4">सध्या कोणतीही फी नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'physical' %}
    <div class="card">
        <h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ फिजिकल चाचणी गुण भरणे (क्लार्क)</h3>
        <form action="/add_physical_record" method="POST" style="background:#f0f9ff; padding:12px; border-radius:6px; margin-bottom:15px;">
            <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            <input type="date" name="test_date" value="{{ today_date }}" required>
            <input type="text" name="run_time" placeholder="1600m (05:10)">
            <input type="text" name="sprint_time" placeholder="100m (12.2)">
            <input type="text" name="shot_put_dist" placeholder="Shot Put (8.5)">
            <input type="number" name="pullups" value="8">
            <input type="number" name="total_obtained" placeholder="एकूण गुण" required>
            <button type="submit" class="btn-act" style="background:#0284c7;">+ गुण सेव्ह करा</button>
        </form>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>1600m</th><th>100m</th><th>गोळा</th><th>पुल-अप्स</th><th>एकूण गुण</th></tr></thead>
            <tbody>
                {% for pt in physical_records %}
                <tr><td>{{ pt.test_date }}</td><td><b>{{ pt.name }}</b></td><td>{{ pt.run_time }}</td><td>{{ pt.sprint_time }}</td><td>{{ pt.shot_put_dist }}</td><td>{{ pt.pullups }}</td><td><b>{{ pt.total_obtained }}/50</b></td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'written' %}
    <div class="card">
        <h3 style="color:#10b981; margin-top:0;">📝 लेखी परीक्षा निकाल भरणे (क्लार्क)</h3>
        <form action="/add_written_record" method="POST" style="background:#f0fdf4; padding:12px; border-radius:6px; margin-bottom:15px;">
            <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            <input type="date" name="test_date" value="{{ today_date }}" required>
            <input type="text" name="test_name" placeholder="सराव टेस्ट क्र." required>
            <input type="number" name="total_marks" value="100" required>
            <input type="number" name="obtained_marks" placeholder="मिळालेले गुण" required>
            <button type="submit" class="btn-act" style="background:#10b981;">+ निकाल सेव्ह करा</button>
        </form>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>परीक्षेचे नाव</th><th>एकूण</th><th>मिळालेले गुण</th></tr></thead>
            <tbody>
                {% for wt in written_records %}
                <tr><td>{{ wt.test_date }}</td><td><b>{{ wt.name }}</b></td><td>{{ wt.test_name }}</td><td>{{ wt.total_marks }}</td><td><b>{{ wt.obtained_marks }}</b></td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'adm' %}
    <div class="card">
        <h3>📝 नवीन विद्यार्थी प्रवेश नोंदणी</h3>
        <form action="/add_student" method="POST" enctype="multipart/form-data">
            <input type="text" name="name" placeholder="विद्यार्थी पूर्ण नाव" required>
            <input type="date" name="admission_date" value="{{ today_date }}" required>
            <input type="text" name="course" value="पोलीस भरती" required>
            <input type="text" name="phone" placeholder="मोबाईल" required>
            <input type="text" name="parent_phone" placeholder="पालक मोबाईल" required>
            <input type="number" name="total_fees" placeholder="एकूण फी" required>
            <input type="number" name="paid_fees" placeholder="भरलेली फी" required>
            <input type="file" name="photo" accept="image/*">
            <button type="submit" class="btn-act" style="background:green;">+ प्रवेश नोंदवा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'fee' %}
    <div class="card">
        <h3>💰 फी हप्ता जमा</h3>
        <form action="/pay_installment" method="POST">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }} (बाकी: ₹{{ (s.total_fees or 0)-(s.paid_fees or 0) }})</option>{% endfor %}</select>
            रक्कम: <input type="number" name="amount" placeholder="रक्कम (₹)" required>
            <button type="submit" class="btn-act" style="background:green;">जमा करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'exp' %}
    <div class="card">
        <h3>💵 दैनिक खर्च नोंद व इतिहास</h3>
        <form action="/add_expense" method="POST">
            प्रकार: <input type="text" name="category" placeholder="उदा. भाजीपाला" required>
            रक्कम: <input type="number" name="amount" placeholder="रक्कम" required>
            तपशील: <input type="text" name="description" placeholder="खर्च तपशील" required>
            <button type="submit" class="btn-act" style="background:green;">नोंदवा</button>
        </form>
        <h4>📋 तुम्ही केलेल्या खर्चाची नोंदवही:</h4>
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

    {% if curr_tab == 'kit' %}
    <div class="card">
        <h3>📦 किट वाटप नोंद व इतिहास</h3>
        <form action="/add_kit_distribution" method="POST">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            साहित्य: <input type="text" name="item_details" placeholder="उदा. टी-शर्ट, ट्रॅक, बॅग" required>
            <button type="submit" class="btn-act" style="background:green;">+ किट वाटप सेव्ह करा</button>
        </form>
        <h4>📋 किट वाटप इतिहास:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>विद्यार्थी नाव</th><th>वाटप साहित्य</th></tr></thead>
            <tbody>
                {% for k in kit_logs %}
                <tr><td>{{ k.issue_date }}</td><td><b>{{ k.name }}</b></td><td>{{ k.item_details }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'req' %}
    <div class="card">
        <h3 style="color:#e11d48; margin-top:0;">📩 संचालकांना विनंती पाठवा व स्टेटस</h3>
        <form action="/send_staff_request" method="POST" style="background:#fff1f2; padding:12px; border-radius:6px; margin-bottom:15px;">
            विषय: <input type="text" name="request_title" required>
            तपशील: <textarea name="request_details" required style="width:100%; height:60px;"></textarea><br><br>
            <button type="submit" class="btn-act" style="background:#e11d48;">+ विनंती पाठवा</button>
        </form>
        <h4>📋 पाठवलेल्या विनंत्यांचा इतिहास:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>विषय</th><th>तपशील</th><th>स्थिती</th></tr></thead>
            <tbody>
                {% for r in my_requests %}
                <tr><td>{{ r.req_date }}</td><td><b>{{ r.request_title }}</b></td><td>{{ r.request_details }}</td><td><b style="color:{% if 'स्वीकृत' in r.status %}green{% elif 'नाकारली' in r.status %}red{% else %}orange{% endif %};">{{ r.status }}</b></td></tr>
                {% else %}<tr><td colspan="4">कोणतीही विनंती नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'tasks' %}
    <div class="card">
        <h3 style="color:#0b3c5d; margin-top:0;">📢 संचालकांनी दिलेली कामे</h3>
        <table>
            <thead><tr><th>तारीख</th><th>काम / सूचना</th><th>स्थिती</th><th>कृती</th></tr></thead>
            <tbody>
                {% for t in staff_tasks %}
                {% if t.target_role in ['Clerk', 'सर्व'] %}
                <tr>
                    <td>{{ t.task_date }}</td><td><b>{{ t.task_text }}</b></td>
                    <td><b>{{ t.status }}</b></td>
                    <td>{% if t.status != 'Seen' %}<a href="/mark_task_seen/{{ t.id }}" class="btn-act" style="background:#0284c7;">वाचले ✓✓</a>{% else %}-{% endif %}</td>
                </tr>
                {% endif %}
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
</div>
</body>
</html>'''
# ----------------- ADMIN DASHBOARD -----------------
ADMIN_DASHBOARD_LAYOUT = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8"><title>Admin Dashboard - SHREEGURU ACADEMY</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #eef2f7; }
        .header { background: #0b3c5d; color: white; padding: 12px 20px; text-align: center; position: relative; }
        .clock { position: absolute; left: 15px; top: 10px; background: rgba(255,255,255,0.15); padding: 4px 8px; border-radius: 4px; font-size: 11px; text-align: left; }
        .top-right { position: absolute; right: 15px; top: 12px; display: flex; align-items: center; gap: 8px; }
        .menu-bar { background: #111c24; display: flex; justify-content: center; gap: 4px; padding: 8px; flex-wrap: wrap; }
        .menu-btn { border: none; padding: 7px 11px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; color: white; text-decoration: none; display: inline-block; }
        .menu-btn.active { background: #fde047 !important; color: #0b3c5d !important; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
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
    <div class="clock"><div id="liveTime" style="font-weight:bold; color:#ffdd59;">04:15:32 PM</div><div id="liveDate">२५/९/२०२६</div></div>
    <h1 style="margin:0; color:#ffdd59; font-size:24px;">SHREEGURU CAREER ACADEMY</h1>
    <p style="margin:3px 0 0; font-size:12px;">पत्ता: आडूर, करवीर, कोल्हापूर | संपर्क: ९९२११११९६०</p>
    <div class="top-right">
        <a href="/toggle_lang" style="background:#ffdd59; color:#0b3c5d; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold; text-decoration:none;">🌐 {{ 'MR (मराठी)' if lang == 'en' else 'EN (English)' }}</a>
        <span style="color:#ffdd59; font-size:12px;">👤 Admin</span>
        <a href="/logout" style="background:#ef4444; color:white; padding:3px 8px; border-radius:4px; text-decoration:none; font-size:11px; font-weight:bold;">Logout</a>
    </div>
</div>

<div class="menu-bar">
    <a href="/admin?tab=students" class="menu-btn {% if curr_tab == 'students' %}active{% endif %}" style="background:#2563eb;">👥 {{ 'All Students' if lang == 'en' else 'सर्व विद्यार्थी' }}</a>
    <a href="/admin?tab=admission" class="menu-btn {% if curr_tab == 'admission' %}active{% endif %}" style="background:#2563eb;">📝 {{ 'New Admission' if lang == 'en' else 'नवीन प्रवेश' }}</a>
    <a href="/admin?tab=physical" class="menu-btn {% if curr_tab == 'physical' %}active{% endif %}" style="background:#0284c7;">🏃‍♂️ {{ 'Physical Test' if lang == 'en' else 'फिजिकल रेकॉर्ड' }}</a>
    <a href="/admin?tab=written" class="menu-btn {% if curr_tab == 'written' %}active{% endif %}" style="background:#10b981;">📝 {{ 'Written Exam' if lang == 'en' else 'रिटर्न टेस्ट' }}</a>
    <a href="/admin?tab=requests" class="menu-btn {% if curr_tab == 'requests' %}active{% endif %}" style="background:#e11d48; border:2px solid #ffdd59;">📩 {{ 'Staff Requests' if lang == 'en' else 'स्टाफ विनंत्या' }}</a>
    <a href="/admin?tab=fee" class="menu-btn {% if curr_tab == 'fee' %}active{% endif %}" style="background:#f59e0b;">💰 {{ 'Fee Collection' if lang == 'en' else 'फी जमा' }}</a>
    <a href="/admin?tab=hostel" class="menu-btn {% if curr_tab == 'hostel' %}active{% endif %}" style="background:#8e2de2;">🏠 {{ 'Hostel / Mess' if lang == 'en' else 'हॉस्टेल/मेस' }}</a>
    <a href="/admin?tab=att" class="menu-btn {% if curr_tab == 'att' %}active{% endif %}" style="background:#e11d48;">📋 {{ 'Attendance' if lang == 'en' else 'सर्व हजेरी' }}</a>
    <a href="/library" target="_blank" class="menu-btn" style="background: linear-gradient(135deg, #0284c7, #06b6d4); color: white;">📚 स्टडी लॅब / लायब्ररी</a>
    <a href="/admin?tab=diet" class="menu-btn {% if curr_tab == 'diet' %}active{% endif %}" style="background:#6366f1;">🥗 {{ 'Mess Diet' if lang == 'en' else 'मेस डाएट' }}</a>
    <a href="/admin?tab=disc" class="menu-btn {% if curr_tab == 'disc' %}active{% endif %}" style="background:#6b21a8;">⚠️ {{ 'Discipline & Gatepass' if lang == 'en' else 'गेटपास/शिस्त' }}</a>
    <a href="/admin?tab=exp" class="menu-btn {% if curr_tab == 'exp' %}active{% endif %}" style="background:#ff416c;">💵 {{ 'Expenses' if lang == 'en' else 'खर्च वही' }}</a>
    <a href="/admin?tab=wa" class="menu-btn {% if curr_tab == 'wa' %}active{% endif %}" style="background:#10b981;">📲 WhatsApp</a>
    <a href="/admin?tab=staff" class="menu-btn {% if curr_tab == 'staff' %}active{% endif %}" style="background:#4f46e5;">👔 {{ 'Staff Salary' if lang == 'en' else 'स्टाफ पगार' }}</a>
    <a href="/admin?tab=tasks" class="menu-btn {% if curr_tab == 'tasks' %}active{% endif %}" style="background:#d97706;">📌 {{ 'Assign Tasks' if lang == 'en' else 'काम सांगा' }}</a>
    <a href="/admin?tab=staff_tracking" class="menu-btn {% if curr_tab == 'staff_tracking' %}active{% endif %}" style="background:#059669; border:2px solid #ffdd59;">👁️ {{ 'Staff Log' if lang == 'en' else 'स्टाफ हालचाली' }}</a>
    <a href="/admin?tab=passwords" class="menu-btn {% if curr_tab == 'passwords' %}active{% endif %}" style="background:#dc2626;">🔐 {{ 'Users & Passwords' if lang == 'en' else 'युजर्स व पासवर्ड' }}</a>
    <a href="/admin?tab=bak" class="menu-btn {% if curr_tab == 'bak' %}active{% endif %}" style="background:#334155;">💾 {{ 'Backup & Restore' if lang == 'en' else 'बॅकअप / रिस्टोअर' }}</a>
</div>

<div class="container">
    <div class="kpis">
        <div class="kpi"><b>{{ 'Total Students:' if lang == 'en' else 'एकूण विद्यार्थी:' }}</b> {{ students|length }}</div>
        <div class="kpi" style="border-color:#10b981;"><b>{{ 'Paid Fees:' if lang == 'en' else 'जमा फी:' }}</b> ₹{{ total_paid }}</div>
        <div class="kpi" style="border-color:#ef4444;"><b>{{ 'Pending Fees:' if lang == 'en' else 'शिल्लक फी:' }}</b> <span style="color:red;">₹{{ total_pending }}</span></div>
        <div class="kpi" style="border-color:#ff416c;"><b>{{ 'Total Expenses:' if lang == 'en' else 'एकूण खर्च:' }}</b> ₹{{ total_expenses }}</div>
    </div>

    {% if curr_tab == 'students' %}
    <div class="admin-tab">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="margin:0;">📋 विद्यार्थी यादी</h3>
            <a href="/export_students_csv" class="btn-act" style="background:green;">📊 CSV डाऊनलोड</a>
        </div>
        <table>
            <thead><tr><th>फोटो</th><th>Reg</th><th>नाव</th><th>कोर्स</th><th>फोन</th><th>शिल्लक</th><th>कृती</th></tr></thead>
            <tbody>
                {% for s in students %}
                <tr>
                    <td>{% if s.photo_filename %}<img src="/uploads/{{ s.photo_filename }}" width="35" height="40">{% else %}-{% endif %}</td>
                    <td>REG-{{ s.id }}</td><td><b>{{ s.name }}</b></td><td>{{ s.course }}</td><td>{{ s.phone }}</td>
                    <td style="color:red; font-weight:bold;">₹{{ (s.total_fees or 0) - (s.paid_fees or 0) }}</td>
                    <td>
                        <a href="/receipt/{{ s.id }}" target="_blank" class="btn-act" style="background:#10b981;">🧾 पावती प्रिंट</a> <a href="/student_report/{{ s.id }}" target="_blank" class="btn-act" style="background:#6366f1; color:white; text-decoration:none; padding:4px 8px; border-radius:4px; font-weight:bold; margin-left:5px;">📋 स्टुडन्ट रिपोर्ट</a> 
                        <a href="/delete_student/{{ s.id }}" onclick="return confirm('हटवायचे?')" class="btn-act" style="background:red;">हटवा</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'admission' %}
    <div class="admin-tab">
        <h3>📝 नवीन विद्यार्थी प्रवेश नोंदणी</h3>
        <form action="/add_student" method="POST" enctype="multipart/form-data">
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap:10px;">
                <div>नाव *: <input type="text" name="name" required style="width:100%;"></div>
                <div>तारीख *: <input type="date" name="admission_date" value="{{ today_date }}" required style="width:100%;"></div>
                <div>कोर्स *: <input type="text" name="course" value="पोलीस भरती" required style="width:100%;"></div>
                <div>मोबाईल *: <input type="text" name="phone" required style="width:100%;"></div>
                <div>पालक फोन *: <input type="text" name="parent_phone" required style="width:100%;"></div>
                <div>एकूण फी *: <input type="number" name="total_fees" required style="width:100%;"></div>
                <div>भरलेली फी *: <input type="number" name="paid_fees" required style="width:100%;"></div>
                <div>फोटो: <input type="file" name="photo" accept="image/*" style="width:100%;"></div>
            </div>
            <br><button type="submit" class="btn-act" style="background:green; padding:8px 15px;">+ प्रवेश सेव्ह करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'physical' %}
    <div class="admin-tab">
        <h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ विद्यार्थ्यांचे फिजिकल टेस्ट रेकॉर्ड</h3>
        <form action="/add_physical_record" method="POST" style="background:#f0f9ff; padding:12px; border-radius:6px; margin-bottom:15px;">
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:8px;">
                <div>विद्यार्थी: <select name="student_id" required style="width:100%;"><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></div>
                <div>तारीख: <input type="date" name="test_date" value="{{ today_date }}" required style="width:100%;"></div>
                <div>१६००/८०० मी.: <input type="text" name="run_time" placeholder="05:10" style="width:100%;"></div>
                <div>१०० मी.: <input type="text" name="sprint_time" placeholder="12.2" style="width:100%;"></div>
                <div>गोळाफेक: <input type="text" name="shot_put_dist" placeholder="8.5m" style="width:100%;"></div>
                <div>पुल-अप्स: <input type="number" name="pullups" value="8" style="width:100%;"></div>
                <div>एकूण गुण: <input type="number" name="total_obtained" placeholder="45" required style="width:100%;"></div>
            </div>
            <br><button type="submit" class="btn-act" style="background:#0284c7;">+ गुण सेव्ह करा</button>
        </form>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>कोर्स</th><th>1600m</th><th>100m</th><th>गोळा</th><th>पुल-अप्स</th><th>एकूण</th><th>हटवा</th></tr></thead>
            <tbody>
                {% for pt in physical_records %}
                <tr><td>{{ pt.test_date }}</td><td><b>{{ pt.name }}</b></td><td>{{ pt.course }}</td><td>{{ pt.run_time }}</td><td>{{ pt.sprint_time }}</td><td>{{ pt.shot_put_dist }}</td><td>{{ pt.pullups }}</td><td><b style="color:green;">{{ pt.total_obtained }}/50</b></td><td><a href="/delete_physical_record/{{ pt.id }}" onclick="return confirm('हटवायचे?')" style="color:red;">🗑️</a></td></tr>
                {% else %}<tr><td colspan="9">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'written' %}
    <div class="admin-tab">
        <h3 style="color:#10b981; margin-top:0;">📝 विद्यार्थ्यांचे रिटर्न टेस्ट रेकॉर्ड</h3>
        <form action="/add_written_record" method="POST" style="background:#f0fdf4; padding:12px; border-radius:6px; margin-bottom:15px;">
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:8px;">
                <div>विद्यार्थी: <select name="student_id" required style="width:100%;"><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select></div>
                <div>तारीख: <input type="date" name="test_date" value="{{ today_date }}" required style="width:100%;"></div>
                <div>परीक्षेचे नाव: <input type="text" name="test_name" placeholder="टेस्ट क्र. १" required style="width:100%;"></div>
                <div>एकूण गुण: <input type="number" name="total_marks" value="100" required style="width:100%;"></div>
                <div>मिळालेले गुण: <input type="number" name="obtained_marks" placeholder="82" required style="width:100%;"></div>
            </div>
            <br><button type="submit" class="btn-act" style="background:#10b981;">+ निकाल सेव्ह करा</button>
        </form>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>परीक्षा</th><th>एकूण</th><th>मिळालेले गुण</th><th>हटवा</th></tr></thead>
            <tbody>
                {% for wt in written_records %}
                <tr><td>{{ wt.test_date }}</td><td><b>{{ wt.name }}</b></td><td>{{ wt.test_name }}</td><td>{{ wt.total_marks }}</td><td><b style="color:green;">{{ wt.obtained_marks }}</b></td><td><a href="/delete_written_record/{{ wt.id }}" onclick="return confirm('हटवायचे?')" style="color:red;">🗑️</a></td></tr>
                {% else %}<tr><td colspan="6">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'requests' %}
    <div class="admin-tab">
        <h3 style="color:#e11d48; margin-top:0;">📩 स्टाफने पाठवलेल्या विनंत्या (Requests Desk)</h3>
        <table>
            <thead><tr><th>तारीख</th><th>कर्मचारी</th><th>विषय</th><th>तपशील</th><th>स्थिती</th><th>निर्णय</th></tr></thead>
            <tbody>
                {% for req in all_requests %}
                <tr>
                    <td>{{ req.req_date }}</td><td><b>{{ req.req_role }}</b></td><td><b>{{ req.request_title }}</b></td><td>{{ req.request_details }}</td><td><b>{{ req.status }}</b></td>
                    <td>
                        <a href="/handle_request/{{ req.id }}/स्वीकृत" class="btn-act" style="background:green;">स्वीकृत ✅</a>
                        <a href="/handle_request/{{ req.id }}/नाकारली" class="btn-act" style="background:red;">नाकारा ❌</a>
                    </td>
                </tr>
                {% else %}<tr><td colspan="6">सध्या कोणतीही विनंती नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
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

    {% if curr_tab == 'hostel' %}
    <div class="admin-tab">
        <h3>🏠 हॉस्टेल व मेस फी नोंद व इतिहास</h3>
        <form action="/add_hostel_fee" method="POST" style="margin-bottom:15px;">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            रक्कम: <input type="number" name="paid_amount" placeholder="रक्कम (₹)" required>
            <button type="submit" class="btn-act" style="background:green;">नोंदवा</button>
        </form>
        <h4>📋 जमा हॉस्टेल व मेस फी इतिहास:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>पॅकेज</th><th>रक्कम</th></tr></thead>
            <tbody>
                {% for h in hostel_logs %}
                <tr><td>{{ h.pay_date }}</td><td><b>{{ h.name }}</b></td><td>{{ h.package_type }}</td><td style="color:green; font-weight:bold;">₹{{ h.paid_amount }}</td></tr>
                {% else %}<tr><td colspan="4">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'att' %}
    <div class="admin-tab">
        <h3>📋 दैनिक हजेरी नोंद</h3>
        <form action="/save_attendance" method="POST">
            <input type="hidden" name="att_type" value="मैदानी हजेरी">
            <table><thead><tr><th>नाव</th><th>हजेरी</th></tr></thead><tbody>
                {% for s in students %}
                <tr><td><b>{{ s.name }}</b></td><td><label><input type="radio" name="status_{{ s.id }}" value="हजर" checked> P</label> <label style="color:red;"><input type="radio" name="status_{{ s.id }}" value="गैरहजर"> A</label></td></tr>
                {% endfor %}
            </tbody></table><br><button type="submit" class="btn-act" style="background:#e11d48;">💾 सेव्ह करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'diet' %}
    <div class="admin-tab">
        <h3 style="color:#6366f1;">🥗 मेस डाएट वेळापत्रक (संपादन / एडिट पर्यायासह)</h3>
        <table>
            <thead><tr><th>वार</th><th>सकाळ नाश्ता</th><th>दुपार जेवण</th><th>रात्र जेवण</th><th>विशेष आहार</th><th>बदल सेव्ह</th></tr></thead>
            <tbody>
                {% for d in diet_list %}
                <form action="/update_diet/{{ d.id }}" method="POST">
                <tr>
                    <td><b>{{ d.day_name }}</b></td>
                    <td><input type="text" name="breakfast" value="{{ d.breakfast }}" style="width:90%;"></td>
                    <td><input type="text" name="lunch" value="{{ d.lunch }}" style="width:90%;"></td>
                    <td><input type="text" name="dinner" value="{{ d.dinner }}" style="width:90%;"></td>
                    <td><input type="text" name="special_diet" value="{{ d.special_diet }}" style="width:90%;"></td>
                    <td><button type="submit" class="btn-act" style="background:#6366f1;">बदला 💾</button></td>
                </tr>
                </form>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'disc' %}
    <div class="admin-tab">
        <h3 style="color:#6b21a8; margin-top:0;">⚠️ सुट्टी गेटपास व शिस्तभंग नोंद (एडिट व रद्द पर्यायासह)</h3>
        <form action="/add_discipline" method="POST" style="background:#f5f3ff; padding:12px; border-radius:6px; margin-bottom:15px;">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            प्रकार: <select name="record_type"><option value="सुट्टी गेटपास">सुट्टी गेटपास</option><option value="शिस्तभंग ताकीद">शिस्तभंग ताकीद</option></select>
            कारण: <input type="text" name="reason" placeholder="गेटपासचे कारण (उदा. आजारी असल्याने घरी जाणे)" required style="width:50%;">
            <button type="submit" class="btn-act" style="background:#6b21a8;">+ नोंद करा</button>
        </form>
        <h4>📋 दिलेल्या गेटपास व शिस्तभंग नोंदींची यादी:</h4>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>प्रकार</th><th>कारण</th><th>कृती</th></tr></thead>
            <tbody>
                {% for d in discipline_logs %}
                <form action="/edit_discipline/{{ d.id }}" method="POST">
                <tr>
                    <td>{{ d.record_date }}</td><td><b>{{ d.name }}</b></td>
                    <td>
                        <select name="record_type">
                            <option value="सुट्टी गेटपास" {% if d.record_type=='सुट्टी गेटपास' %}selected{% endif %}>सुट्टी गेटपास</option>
                            <option value="शिस्तभंग ताकीद" {% if d.record_type=='शिस्तभंग ताकीद' %}selected{% endif %}>शिस्तभंग ताकीद</option>
                        </select>
                    </td>
                    <td><input type="text" name="reason" value="{{ d.reason }}" style="width:90%;"></td>
                    <td>
                        <button type="submit" class="btn-act" style="background:#2563eb;">बदला 💾</button>
                        <a href="/delete_discipline/{{ d.id }}" onclick="return confirm('गेटपास रद्द करायचा?')" class="btn-act" style="background:red;">रद्द 🗑️</a>
                    </td>
                </tr>
                </form>
                {% else %}<tr><td colspan="5">कोणताही गेटपास दिलेला नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'exp' %}
    <div class="admin-tab">
        <h3>💵 दैनिक खर्च वही</h3>
        <table>
            <thead><tr><th>तारीख</th><th>प्रकार</th><th>तपशील</th><th>नोंद करणारा</th><th>रक्कम</th></tr></thead>
            <tbody>
                {% for ex in expenses_list %}
                <tr><td>{{ ex.exp_date }}</td><td>{{ ex.category }}</td><td><b>{{ ex.description }}</b></td><td>{{ ex.logged_by }}</td><td style="color:red; font-weight:bold;">₹{{ ex.amount }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'wa' %}
    <div class="admin-tab">
        <h3>📲 १-क्लिक व्हॉट्सॲप मेसेज</h3>
        <table><thead><tr><th>नाव</th><th>फोन</th><th>मेसेज</th></tr></thead><tbody>
            {% for s in students %}
            <tr><td>{{ s.name }}</td><td>{{ s.parent_phone }}</td><td><a href="https://wa.me/91{{ s.parent_phone }}" target="_blank" class="btn-act" style="background:#25D366;">📲 मेसेज</a></td></tr>
            {% endfor %}
        </tbody></table>
    </div>
    {% endif %}

    {% if curr_tab == 'staff' %}
    <div class="admin-tab">
        <h3 style="color:#4f46e5; margin-top:0;">👔 स्टाफ पगार, उचल व रजा व्यवस्थापन</h3>
        <form action="/add_staff" method="POST" style="background:#f8fafc; padding:12px; border-radius:6px; margin-bottom:15px;">
            नाव: <input type="text" name="name" required> पद: <input type="text" name="role" required> फोन: <input type="text" name="phone" required> पगार: <input type="number" name="salary" required>
            <button type="submit" class="btn-act" style="background:green;">+ स्टाफ जोडा</button>
        </form>
        <table>
            <thead><tr><th>नाव</th><th>पद</th><th>फोन</th><th>पगार</th><th>उचल</th><th>रजा</th><th>पगार देणे बाकी</th><th>कृती</th></tr></thead>
            <tbody>
                {% for st in staff_members %}
                {% set per_day = (st.salary or 0) / 30 if (st.salary or 0) > 0 else 0 %}
                {% set leave_cut = per_day * (st.total_leaves or 0) %}
                {% set net_pay = (st.salary or 0) - ((st.advance_paid or 0) + leave_cut) %}
                {% if net_pay < 0 %}{% set net_pay = 0 %}{% endif %}
                <tr>
                    <td><b>{{ st.name }}</b></td><td>{{ st.role }}</td><td>{{ st.phone }}</td><td>₹{{ st.salary }}</td><td style="color:red;">₹{{ st.advance_paid or 0 }}</td><td>{{ st.total_leaves or 0 }} दिवस</td><td style="color:green; font-weight:bold;">₹{{ net_pay|round|int }}</td>
                    <td>
                        <form action="/update_staff_advance/{{ st.id }}" method="POST" style="display:inline-flex; gap:3px;">
                            <input type="number" name="advance_amount" placeholder="+ उचल" style="width:65px;">
                            <button type="submit" class="btn-act" style="background:#f59e0b;">उचल</button>
                        </form>
                        <form action="/add_staff_leave/{{ st.id }}" method="POST" style="display:inline-flex; gap:3px; margin-left:3px;">
                            <input type="number" name="leave_days" value="1" style="width:40px;">
                            <button type="submit" class="btn-act" style="background:#6366f1;">+ रजा</button>
                        </form>
                        <form action="/pay_staff_salary/{{ st.id }}" method="POST" style="display:inline-block; margin-left:5px; background:#f1f5f9; padding:5px; border-radius:4px; border:1px solid #cbd5e1;">
                            <span style="font-size:11px; font-weight:bold; color:#0b3c5d;">कालावधी:</span>
                            <input type="date" name="from_date" required style="padding:2px; font-size:12px;">
                            <span style="font-size:11px;">ते</span>
                            <input type="date" name="to_date" required style="padding:2px; font-size:12px;">
                            <input type="number" name="amount" value="{{ net_pay|round|int }}" style="width:75px; font-weight:bold; color:green; padding:2px;">
                            <button type="submit" class="btn-act" style="background:#0b3c5d; color:white; padding:3px 8px;" onclick="return confirm('पगार वाटप नोंद करायची का?')">पगार द्या</button>
                        </form>
                        <a href="/delete_staff/{{ st.id }}" onclick="return confirm('हटवायचा?')" style="color:red; margin-left:5px;">🗑️</a>
                    </td>
                </tr>
                {% else %}<tr><td colspan="8">स्टाफ नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'tasks' %}
    <div class="admin-tab">
        <h3 style="color:#d97706; margin-top:0;">📌 स्टाफला काम सांगा (एडिट व डिलीट पर्यायासह)</h3>
        <form action="/assign_task" method="POST" style="background:#fffbeb; padding:12px; border-radius:6px; margin-bottom:15px;">
            कोणाला: <select name="target_role"><option value="Trainer">ट्रेनर</option><option value="Clerk">क्लार्क</option><option value="Manager">मॅनेजर</option><option value="सर्व">सर्व</option></select>
            काम: <input type="text" name="task_text" required style="width:55%;">
            <button type="submit" class="btn-act" style="background:green;">+ पाठवा</button>
        </form>
        <table>
            <thead><tr><th>तारीख</th><th>कोणाला</th><th>काम / सूचना</th><th>स्थिती</th><th>कृती</th></tr></thead>
            <tbody>
                {% for t in staff_tasks %}
                <form action="/edit_staff_task/{{ t.id }}" method="POST">
                <tr>
                    <td>{{ t.task_date }}</td>
                    <td>
                        <select name="target_role">
                            <option value="Trainer" {% if t.target_role=='Trainer' %}selected{% endif %}>ट्रेनर</option>
                            <option value="Clerk" {% if t.target_role=='Clerk' %}selected{% endif %}>क्लार्क</option>
                            <option value="Manager" {% if t.target_role=='Manager' %}selected{% endif %}>मॅनेजर</option>
                            <option value="सर्व" {% if t.target_role=='सर्व' %}selected{% endif %}>सर्व</option>
                        </select>
                    </td>
                    <td><input type="text" name="task_text" value="{{ t.task_text }}" style="width:95%;"></td>
                    <td><b>{{ t.status }}</b></td>
                    <td>
                        <button type="submit" class="btn-act" style="background:#2563eb;">बदला 💾</button>
                        <a href="/delete_staff_task/{{ t.id }}" onclick="return confirm('हटवायची?')" class="btn-act" style="background:red;">हटवा 🗑️</a>
                    </td>
                </tr>
                </form>
                {% else %}<tr><td colspan="5">सूचना नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'staff_tracking' %}
    <div class="admin-tab">
        <h3 style="color:#059669; margin-top:0;">👁️ तिन्ही स्टाफच्या दैनंदिन हालचाली (Admin Reply सह)</h3>
        <table>
            <thead><tr><th style="width:160px;">वेळ</th><th>कर्मचारी</th><th>हालचाल नोंद</th><th>ॲडमिन शेरा/रिप्लाय</th><th>कृती</th></tr></thead>
            <tbody>
                {% for log in all_staff_logs %}
                <form action="/reply_staff_activity/{{ log.id }}" method="POST">
                <tr>
                    <td>{{ log.act_time }}</td><td><b>{{ log.staff_role }}</b></td><td>{{ log.activity_text }}</td>
                    <td>{% if log.admin_reply %}<b style="color:blue;">{{ log.admin_reply }}</b><br>{% endif %}<input type="text" name="admin_reply" placeholder="रिप्लाय द्या..." style="width:90%;"></td>
                    <td><button type="submit" class="btn-act" style="background:#2563eb;">रिप्लाय 💬</button></td>
                </tr>
                </form>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'passwords' %}
    <div class="admin-tab">
        <h3 style="color:#dc2626; margin-top:0;">🔐 युजर पासवर्ड व नवीन युजर तयार करा</h3>
        <form action="/add_new_system_user" method="POST" style="background:#fef2f2; padding:12px; border-radius:6px; margin-bottom:15px;">
            नवीन पद/युजर नाव: <input type="text" name="new_role" placeholder="उदा. Assistant Trainer" required>
            पासवर्ड: <input type="text" name="new_password" placeholder="उदा. pass123" required>
            <button type="submit" class="btn-act" style="background:green;">+ युजर बनवा</button>
        </form>
        <table>
            <thead><tr><th>Role</th><th>Password</th><th>Action</th></tr></thead>
            <tbody>
                {% for u in users_list %}
                <form action="/change_password/{{ u.id }}" method="POST">
                <tr>
                    <td><b>{{ u.role }}</b></td><td><input type="text" name="new_password" value="{{ u.password }}"></td>
                    <td>
                        <button type="submit" class="btn-act" style="background:#10b981;">अपडेट</button>
                        {% if u.role not in ['Admin', 'Manager', 'Clerk', 'Trainer'] %}
                        <a href="/delete_system_user/{{ u.id }}" onclick="return confirm('हटवायचा?')" class="btn-act" style="background:red;">हटवा</a>
                        {% endif %}
                    </td>
                </tr>
                </form>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'bak' %}
    <div class="admin-tab">
        <h3 style="color:#0b3c5d;">💾 डेटाबेस बॅकअप व रिस्टोअर व्यवस्थापन</h3>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:#f8fafc; padding:15px; border:1px solid #cbd5e1; border-radius:6px;">
                <h4 style="margin:0 0 10px; color:#2563eb;">१. चालू डेटाबेस डाऊनलोड करा (Backup)</h4>
                <a href="/download_backup" class="btn-act" style="background:#2563eb; padding:8px 15px;">📥 डाऊनलोड बॅकअप (.db)</a>
            </div>
            <div style="background:#fffbeb; padding:15px; border:1px solid #fde68a; border-radius:6px;">
                <h4 style="margin:0 0 10px; color:#b45309;">२. जुना डेटाबेस अपलोड करा (Restore)</h4>
                <form action="/upload_restore_backup" method="POST" enctype="multipart/form-data">
                    <input type="file" name="backup_file" accept=".db" required style="margin-bottom:10px;"><br>
                    <button type="submit" onclick="return confirm('सावधान! जुना बॅकअप अपलोड केल्याने सध्याचा डेटा बदलला जाईल. पुढे जायचे का?')" class="btn-act" style="background:#b45309; padding:8px 15px;">📤 अपलोड व रिस्टोअर करा</button>
                </form>
            </div>
        </div>
    </div>
    {% endif %}
</div>
<script>
function updateClock() {
    var now = new Date();
    var h = now.getHours(), m = String(now.getMinutes()).padStart(2,'0'), s = String(now.getSeconds()).padStart(2,'0');
    var ap = h>=12 ? 'PM':'AM'; h = h%12; h = h?h:12;
    document.getElementById('liveTime').innerText = String(h).padStart(2,'0') + ":" + m + ":" + s + " " + ap;
    document.getElementById('liveDate').innerText = now.toLocaleDateString();
}
setInterval(updateClock, 1000); updateClock();
</script>
</body>
</html>'''
# ----------------- FLASK MAIN CONTROLLER ROUTING -----------------
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
        users_list = conn.execute("SELECT * FROM users").fetchall()
    if request.method == 'POST':
        role = request.form.get('role')
        pwd = request.form.get('password')
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE role=? AND password=?", (role, pwd)).fetchone()
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

@app.route('/manager')
def manager_view():
    if session.get('user_role') != 'Manager': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'grocery')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students").fetchall()
        diet_list = conn.execute("SELECT * FROM mess_diet").fetchall()
        canteen_staff = conn.execute("SELECT * FROM canteen_staff_list").fetchall()
        staff_tasks = conn.execute("SELECT * FROM staff_tasks ORDER BY id DESC").fetchall()
        my_requests = conn.execute("SELECT * FROM staff_requests WHERE req_role='Manager' ORDER BY id DESC").fetchall()
        physical_records = conn.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC").fetchall()
        written_records = conn.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC").fetchall()
    return render_template_string(MANAGER_LAYOUT, curr_tab=curr_tab, students=students, diet_list=diet_list, canteen_staff=canteen_staff, staff_tasks=staff_tasks, my_requests=my_requests, physical_records=physical_records, written_records=written_records, today_date=today_date, lang=lang)

@app.route('/trainer')
def trainer_view():
    if session.get('user_role') != 'Trainer': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'practice')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students").fetchall()
        staff_tasks = conn.execute("SELECT * FROM staff_tasks ORDER BY id DESC").fetchall()
        my_requests = conn.execute("SELECT * FROM staff_requests WHERE req_role='Trainer' ORDER BY id DESC").fetchall()
        physical_records = conn.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC").fetchall()
        written_records = conn.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC").fetchall()
        trainer_diet_logs = conn.execute("SELECT sc.*, s.name FROM student_care_log sc JOIN students s ON sc.student_id = s.id WHERE sc.issue_details='ट्रेनर डाएट शिफारस' ORDER BY sc.id DESC").fetchall()
        trainer_injury_logs = conn.execute("SELECT i.*, s.name FROM injuries i JOIN students s ON i.student_id = s.id ORDER BY i.id DESC").fetchall()
    return render_template_string(TRAINER_LAYOUT, curr_tab=curr_tab, students=students, staff_tasks=staff_tasks, my_requests=my_requests, physical_records=physical_records, written_records=written_records, trainer_diet_logs=trainer_diet_logs, trainer_injury_logs=trainer_injury_logs, today_date=today_date, lang=lang)

@app.route('/clerk')
def clerk_view():
    if session.get('user_role') != 'Clerk': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'stud')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students").fetchall()
        staff_tasks = conn.execute("SELECT * FROM staff_tasks ORDER BY id DESC").fetchall()
        expenses_list = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
        kit_logs = conn.execute("SELECT k.*, s.name FROM kit_distribution k JOIN students s ON k.student_id = s.id ORDER BY k.id DESC").fetchall()
        my_requests = conn.execute("SELECT * FROM staff_requests WHERE req_role='Clerk' ORDER BY id DESC").fetchall()
        hostel_logs = conn.execute("SELECT h.*, s.name FROM hostel_mess_fees h JOIN students s ON h.student_id = s.id ORDER BY h.id DESC").fetchall()
        physical_records = conn.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC").fetchall()
        written_records = conn.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC").fetchall()
    return render_template_string(CLERK_LAYOUT, curr_tab=curr_tab, students=students, staff_tasks=staff_tasks, expenses_list=expenses_list, kit_logs=kit_logs, my_requests=my_requests, hostel_logs=hostel_logs, physical_records=physical_records, written_records=written_records, today_date=today_date, lang=lang)

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'students')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students").fetchall()
        expenses_list = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
        users_list = conn.execute("SELECT * FROM users").fetchall()
        diet_list = conn.execute("SELECT * FROM mess_diet").fetchall()
        staff_members = conn.execute("SELECT * FROM staff").fetchall()
        staff_tasks = conn.execute("SELECT * FROM staff_tasks ORDER BY id DESC").fetchall()
        all_requests = conn.execute("SELECT * FROM staff_requests ORDER BY id DESC").fetchall()
        all_staff_logs = conn.execute("SELECT * FROM staff_activity_log ORDER BY id DESC LIMIT 40").fetchall()
        discipline_logs = conn.execute("SELECT d.*, s.name FROM discipline_records d JOIN students s ON d.student_id = s.id ORDER BY d.id DESC").fetchall()
        hostel_logs = conn.execute("SELECT h.*, s.name FROM hostel_mess_fees h JOIN students s ON h.student_id = s.id ORDER BY h.id DESC").fetchall()
        physical_records = conn.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC").fetchall()
        written_records = conn.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC").fetchall()

    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    total_expenses = sum(safe_float(ex['amount']) for ex in expenses_list)

    return render_template_string(ADMIN_DASHBOARD_LAYOUT, curr_tab=curr_tab, students=students, expenses_list=expenses_list, users_list=users_list, diet_list=diet_list, staff_members=staff_members, staff_tasks=staff_tasks, all_requests=all_requests, all_staff_logs=all_staff_logs, discipline_logs=discipline_logs, hostel_logs=hostel_logs, physical_records=physical_records, written_records=written_records, total_paid=total_paid, total_pending=total_pending, total_expenses=total_expenses, today_date=today_date, lang=lang)

# ----------------- SYSTEM FUNCTIONAL HANDLERS -----------------
@app.route('/download_backup')
def download_backup():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    if os.path.exists(DB_NAME):
        return send_file(DB_NAME, as_attachment=True)
    return "Database file not found!", 404

@app.route('/upload_restore_backup', methods=['POST'])
def upload_restore_backup():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    file = request.files.get('backup_file')
    if file and file.filename.endswith('.db'):
        file.save(DB_NAME)
        log_staff_activity("Admin", "जुना बॅकअप रिस्टोअर केला.")
        return "<script>alert('डेटाबेस यशस्वीरीत्या रिस्टोअर झाला!'); window.location.href='/admin?tab=bak';</script>"
    return "कृपया .db फाईल निवडा!", 400

@app.route('/add_discipline', methods=['POST'])
def add_discipline():
    sid = safe_int(request.form.get('student_id'))
    r_type = request.form.get('record_type', 'सुट्टी गेटपास')
    reason = request.form.get('reason')
    with get_db() as conn:
        s = conn.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()
        s_name = s['name'] if s else "विद्यार्थी"
        conn.execute("INSERT INTO discipline_records (student_id, record_type, record_date, reason) VALUES (?, ?, ?, ?)",
                     (sid, r_type, date.today().strftime("%Y-%m-%d"), reason))
        conn.commit()
    log_staff_activity("Admin", f"गेटपास/ताकीद नोंद: {s_name} ({r_type} - {reason})")
    return redirect('/admin?tab=disc')

@app.route('/edit_discipline/<int:id>', methods=['POST'])
def edit_discipline(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        conn.execute("UPDATE discipline_records SET record_type=?, reason=? WHERE id=?", (request.form.get('record_type'), request.form.get('reason'), id))
        conn.commit()
    log_staff_activity("Admin", f"गेटपास दुरुस्त केला (ID: {id})")
    return redirect('/admin?tab=disc')

@app.route('/delete_discipline/<int:id>')
def delete_discipline(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        conn.execute("DELETE FROM discipline_records WHERE id=?", (id,))
        conn.commit()
    log_staff_activity("Admin", f"गेटपास रद्द/हटवला (ID: {id})")
    return redirect('/admin?tab=disc')

@app.route('/save_trainer_student_diet', methods=['POST'])
def save_trainer_student_diet():
    sid = safe_int(request.form.get('student_id'))
    d_text = request.form.get('diet_text')
    with get_db() as conn:
        s = conn.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()
        s_name = s['name'] if s else "विद्यार्थी"
        conn.execute("INSERT INTO student_care_log (student_id, care_date, issue_details, special_diet_note) VALUES (?, ?, 'ट्रेनर डाएट शिफारस', ?)",
                     (sid, date.today().strftime("%Y-%m-%d"), d_text))
        conn.commit()
    log_staff_activity("Trainer", f"विद्यार्थी डाएट शिफारस: {s_name} - {d_text}")
    return redirect('/trainer?tab=student_diet')

@app.route('/add_injury', methods=['POST'])
def add_injury():
    sid = safe_int(request.form.get('student_id'))
    with get_db() as conn:
        s = conn.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()
        s_name = s['name'] if s else "विद्यार्थी"
        conn.execute("INSERT INTO injuries (student_id, injury_date, injury_type, severity, rest_days) VALUES (?, ?, ?, 'Moderate', ?)",
                     (sid, date.today().strftime("%Y-%m-%d"), request.form.get('injury_type'), safe_int(request.form.get('rest_days'))))
        conn.commit()
    log_staff_activity("Trainer", f"इजा नोंदवली: {s_name}")
    return redirect('/trainer?tab=inj')

@app.route('/add_physical_record', methods=['POST'])
def add_physical_record():
    sid = safe_int(request.form.get('student_id'))
    with get_db() as conn:
        s = conn.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()
        s_name = s['name'] if s else "विद्यार्थी"
        conn.execute("INSERT INTO physical_tests (student_id, test_date, run_time, sprint_time, shot_put_dist, pullups, total_obtained) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (sid, request.form.get('test_date'), request.form.get('run_time'), request.form.get('sprint_time'), request.form.get('shot_put_dist'), safe_int(request.form.get('pullups')), safe_float(request.form.get('total_obtained'))))
        conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"फिजिकल गुण नोंदवले: {s_name}")
    return redirect(request.referrer or '/')

@app.route('/delete_physical_record/<int:id>')
def delete_physical_record(id):
    with get_db() as conn:
        conn.execute("DELETE FROM physical_tests WHERE id=?", (id,))
        conn.commit()
    return redirect('/admin?tab=physical')

@app.route('/add_written_record', methods=['POST'])
def add_written_record():
    sid = safe_int(request.form.get('student_id'))
    with get_db() as conn:
        s = conn.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()
        s_name = s['name'] if s else "विद्यार्थी"
        conn.execute("INSERT INTO written_tests (student_id, test_date, test_name, subject, total_marks, obtained_marks) VALUES (?, ?, ?, ?, ?, ?)",
                     (sid, request.form.get('test_date'), request.form.get('test_name'), request.form.get('subject'), safe_float(request.form.get('total_marks'), 100), safe_float(request.form.get('obtained_marks'))))
        conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"लेखी परीक्षा निकाल: {s_name}")
    return redirect(request.referrer or '/')

@app.route('/delete_written_record/<int:id>')
def delete_written_record(id):
    with get_db() as conn:
        conn.execute("DELETE FROM written_tests WHERE id=?", (id,))
        conn.commit()
    return redirect('/admin?tab=written')

@app.route('/add_hostel_fee', methods=['POST'])
def add_hostel_fee():
    with get_db() as conn:
        conn.execute("INSERT INTO hostel_mess_fees (student_id, package_type, from_month, to_month, total_amount, paid_amount, pay_date) VALUES (?, '१ महिना', 'सप्टें', 'ऑक्टो', ?, ?, ?)",
                     (safe_int(request.form.get('student_id')), safe_float(request.form.get('paid_amount')), safe_float(request.form.get('paid_amount')), date.today().strftime("%Y-%m-%d")))
        conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"हॉस्टेल फी जमा: रु. {request.form.get('paid_amount')}")
    return redirect(request.referrer or '/')

@app.route('/send_staff_request', methods=['POST'])
def send_staff_request():
    role = session.get('user_role', 'Staff')
    with get_db() as conn:
        conn.execute("INSERT INTO staff_requests (req_role, req_date, request_title, request_details, status) VALUES (?, ?, ?, ?, 'प्रलंबित')",
                     (role, date.today().strftime("%Y-%m-%d"), request.form.get('request_title'), request.form.get('request_details')))
        conn.commit()
    log_staff_activity(role, f"विनंती पाठवली: {request.form.get('request_title')}")
    return redirect(request.referrer or '/')

@app.route('/handle_request/<int:id>/<action>')
def handle_request(id, action):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        conn.execute("UPDATE staff_requests SET status=? WHERE id=?", (action, id))
        conn.commit()
    log_staff_activity("Admin", f"विनंतीवर निर्णय: {action}")
    return redirect('/admin?tab=requests')

@app.route('/reply_staff_activity/<int:id>', methods=['POST'])
def reply_staff_activity(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        conn.execute("UPDATE staff_activity_log SET admin_reply=? WHERE id=?", (request.form.get('admin_reply'), id))
        conn.commit()
    log_staff_activity("Admin", "स्टाफ हालचालीस रिप्लाय दिला.")
    return redirect('/admin?tab=staff_tracking')

@app.route('/add_new_system_user', methods=['POST'])
def add_new_system_user():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        conn.execute("INSERT INTO users (role, password) VALUES (?, ?)", (request.form.get('new_role'), request.form.get('new_password')))
        conn.commit()
    log_staff_activity("Admin", f"नवीन युजर तयार केला: {request.form.get('new_role')}")
    return redirect('/admin?tab=passwords')

@app.route('/delete_system_user/<int:id>')
def delete_system_user(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (id,))
        conn.commit()
    return redirect('/admin?tab=passwords')

@app.route('/save_trainer_practice', methods=['POST'])
def save_trainer_practice():
    with get_db() as conn:
        conn.execute("INSERT INTO trainer_practice_log (log_date, session_time, ground_status, workout_details) VALUES (?, ?, ?, ?)",
                     (date.today().strftime("%Y-%m-%d"), request.form.get('session_time'), request.form.get('ground_status'), request.form.get('workout_details')))
        conn.commit()
    log_staff_activity("Trainer", f"सराव नोंदवला ({request.form.get('ground_status')}): {request.form.get('workout_details')}")
    return "<script>alert('सराव यशस्वी नोंदवला!'); window.location.href='/trainer?tab=practice';</script>"

@app.route('/save_coach_attendance', methods=['POST'])
def save_coach_attendance():
    att_type = request.form.get('att_type')
    today_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        conn.execute("DELETE FROM attendance WHERE att_type=? AND att_date=?", (att_type, today_date))
        for s in conn.execute("SELECT id FROM students").fetchall():
            st = request.form.get(f'status_{s["id"]}', 'हजर')
            conn.execute("INSERT INTO attendance (person_type, person_id, att_type, att_date, status) VALUES ('student', ?, ?, ?, ?)", (s['id'], att_type, today_date, st))
        conn.commit()
    log_staff_activity("Trainer", f"मैदानी हजेरी नोंदवली ({att_type})")
    return redirect('/trainer?tab=att')

@app.route('/add_canteen_staff', methods=['POST'])
def add_canteen_staff():
    with get_db() as conn:
        conn.execute("INSERT INTO canteen_staff_list (staff_name, work_role) VALUES (?, ?)", (request.form.get('staff_name'), request.form.get('work_role')))
        conn.commit()
    return redirect('/manager?tab=cook')

@app.route('/delete_canteen_staff/<int:id>')
def delete_canteen_staff(id):
    with get_db() as conn:
        conn.execute("DELETE FROM canteen_staff_list WHERE id=?", (id,))
        conn.commit()
    return redirect('/manager?tab=cook')

@app.route('/save_kitchen_att_dynamic', methods=['POST'])
def save_kitchen_att_dynamic():
    att_date = request.form.get('att_date')
    session_time = request.form.get('session_time')
    with get_db() as conn:
        for cs in conn.execute("SELECT * FROM canteen_staff_list").fetchall():
            st = request.form.get(f'status_{cs["id"]}', 'हजर')
            conn.execute("DELETE FROM kitchen_staff_att WHERE staff_name=? AND att_date=? AND session_time=?", (cs['staff_name'], att_date, session_time))
            conn.execute("INSERT INTO kitchen_staff_att (staff_name, att_date, session_time, day_name, status) VALUES (?, ?, ?, 'सोमवार', ?)", (cs['staff_name'], att_date, session_time, st))
        conn.commit()
    return redirect('/manager?tab=cook')

@app.route('/add_student', methods=['POST'])
def add_student():
    photo = request.files.get('photo')
    photo_filename = secure_filename(f"{date.today()}_{photo.filename}") if photo and photo.filename != "" else ""
    if photo_filename: photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
    with get_db() as conn:
        conn.execute("INSERT INTO students (name, course, phone, parent_phone, total_fees, paid_fees, photo_filename, admission_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (request.form.get('name'), request.form.get('course'), request.form.get('phone'), request.form.get('parent_phone'), safe_float(request.form.get('total_fees')), safe_float(request.form.get('paid_fees')), photo_filename, request.form.get('admission_date')))
        conn.commit()
    role = session.get('user_role', 'Admin')
    log_staff_activity(role, f"नवीन प्रवेश: {request.form.get('name')}")
    return redirect(request.referrer or '/')

@app.route('/pay_installment', methods=['POST'])
def pay_installment():
    with get_db() as conn:
        conn.execute("UPDATE students SET paid_fees = paid_fees + ? WHERE id = ?", (safe_float(request.form.get('amount')), safe_int(request.form.get('student_id'))))
        conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"फी जमा: रु. {request.form.get('amount')}")
    return redirect(request.referrer or '/')

@app.route('/add_expense', methods=['POST'])
def add_expense():
    with get_db() as conn:
        conn.execute("INSERT INTO expenses (exp_date, category, description, amount, logged_by) VALUES (?, ?, ?, ?, ?)",
                     (date.today().strftime("%Y-%m-%d"), request.form.get('category'), request.form.get('description'), safe_float(request.form.get('amount')), session.get('user_role', 'Clerk')))
        conn.commit()
    log_staff_activity("Clerk", f"खर्च नोंदवला: रु. {request.form.get('amount')}")
    return redirect(request.referrer or '/')

@app.route('/add_kit_distribution', methods=['POST'])
def add_kit_distribution():
    with get_db() as conn:
        conn.execute("INSERT INTO kit_distribution (student_id, item_details, issue_date, logged_by) VALUES (?, ?, ?, ?)",
                     (safe_int(request.form.get('student_id')), request.form.get('item_details'), date.today().strftime("%Y-%m-%d"), session.get('user_role', 'Clerk')))
        conn.commit()
    return redirect(request.referrer or '/')

@app.route('/save_attendance', methods=['POST'])
def save_attendance():
    att_type = request.form.get('att_type')
    today_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        conn.execute("DELETE FROM attendance WHERE att_type=? AND att_date=?", (att_type, today_date))
        for s in conn.execute("SELECT id FROM students").fetchall():
            st = request.form.get(f'status_{s["id"]}', 'हजर')
            conn.execute("INSERT INTO attendance (person_type, person_id, att_type, att_date, status) VALUES ('student', ?, ?, ?, ?)", (s['id'], att_type, today_date, st))
        conn.commit()
    return redirect('/admin?tab=att')

@app.route('/attendance')
def clerk_attendance_portal():
    if session.get('user_role') not in ['Clerk', 'Admin', 'Manager']:
        return redirect(url_for('login'))
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students ORDER BY name ASC").fetchall()
    return render_template_string('''<!DOCTYPE html>
    <html lang="mr">
    <head><meta charset="UTF-8"><title>हजेरी पोर्टल</title>
    <style>body{font-family:sans-serif;background:#f8fafc;padding:20px;}</style>
    </head><body>
    <h2>📋 विद्यार्थी दैनिक हजेरी</h2>
    <form action="/save_attendance" method="POST">
        <input type="hidden" name="att_type" value="ऑफिस हजेरी">
        <table border="1" cellpadding="8" style="border-collapse:collapse; background:white; width:100%; max-width:600px;">
        <tr style="background:#0b3c5d; color:white;"><th>विद्यार्थी</th><th>हजेरी</th></tr>
        {% for s in students %}
        <tr><td><b>{{ s.name }}</b></td><td><label><input type="radio" name="status_{{ s.id }}" value="हजर" checked> P</label> <label style="color:red; margin-left:10px;"><input type="radio" name="status_{{ s.id }}" value="गैरहजर"> A</label></td></tr>
        {% endfor %}
        </table><br><button type="submit" style="background:green; color:white; padding:8px 15px; border:none; border-radius:4px; font-weight:bold; cursor:pointer;">💾 हजेरी सेव्ह करा</button>
    </form></body></html>''', students=students)

@app.route('/add_staff', methods=['POST'])
def add_staff():
    with get_db() as conn:
        conn.execute("INSERT INTO staff (name, role, phone, salary, joining_date, advance_paid, total_leaves) VALUES (?, ?, ?, ?, ?, 0, 0)",
                     (request.form.get('name'), request.form.get('role'), request.form.get('phone'), safe_float(request.form.get('salary')), request.form.get('joining_date')))
        conn.commit()
    log_staff_activity("Admin", f"स्टाफ जोडला: {request.form.get('name')}")
    return redirect('/admin?tab=staff')

@app.route('/update_staff_advance/<int:id>', methods=['POST'])
def update_staff_advance(id):
    with get_db() as conn:
        conn.execute("UPDATE staff SET advance_paid = advance_paid + ? WHERE id=?", (safe_float(request.form.get('advance_amount')), id))
        conn.commit()
    return redirect('/admin?tab=staff')

@app.route('/add_staff_leave/<int:id>', methods=['POST'])
def add_staff_leave(id):
    with get_db() as conn:
        conn.execute("UPDATE staff SET total_leaves = total_leaves + ? WHERE id=?", (safe_int(request.form.get('leave_days'), 1), id))
        conn.commit()
    return redirect('/admin?tab=staff')

@app.route('/delete_staff/<int:id>')
def delete_staff(id):
    with get_db() as conn:
        conn.execute("DELETE FROM staff WHERE id=?", (id,))
        conn.commit()
    return redirect('/admin?tab=staff')

@app.route('/pay_staff_salary/<int:id>', methods=['POST'])
def pay_staff_salary(id):
    from_date = request.form.get('from_date', '')
    to_date = request.form.get('to_date', '')
    amount = safe_float(request.form.get('amount'))
    with get_db() as conn:
        staff = conn.execute("SELECT name FROM staff WHERE id=?", (id,)).fetchone()
        staff_name = staff['name'] if staff else f"ID {id}"
        desc = f"स्टाफ पगार: {staff_name} (कालावधी: {from_date} ते {to_date})"
        conn.execute("INSERT INTO expenses (exp_date, category, description, amount, logged_by) VALUES (date('now'), 'Staff Salary', ?, ?, 'Admin')", (desc, amount))
        conn.execute("UPDATE staff SET advance_paid = 0 WHERE id=?", (id,))
        conn.commit()
    log_staff_activity("Admin", f"पगार वाटप: {staff_name} - ₹{amount} ({from_date} ते {to_date})")
    return redirect('/admin?tab=staff')

@app.route('/assign_task', methods=['POST'])
def assign_task():
    with get_db() as conn:
        conn.execute("INSERT INTO staff_tasks (target_role, task_text, task_date, status) VALUES (?, ?, ?, 'Unseen')",
                     (request.form.get('target_role'), request.form.get('task_text'), date.today().strftime("%Y-%m-%d")))
        conn.commit()
    return redirect('/admin?tab=tasks')

@app.route('/edit_staff_task/<int:id>', methods=['POST'])
def edit_staff_task(id):
    with get_db() as conn:
        conn.execute("UPDATE staff_tasks SET target_role=?, task_text=? WHERE id=?", (request.form.get('target_role'), request.form.get('task_text'), id))
        conn.commit()
    return redirect('/admin?tab=tasks')

@app.route('/delete_staff_task/<int:id>')
def delete_staff_task(id):
    with get_db() as conn:
        conn.execute("DELETE FROM staff_tasks WHERE id=?", (id,))
        conn.commit()
    return redirect('/admin?tab=tasks')

@app.route('/mark_task_seen/<int:id>')
def mark_task_seen(id):
    with get_db() as conn:
        conn.execute("UPDATE staff_tasks SET status='Seen' WHERE id=?", (id,))
        conn.commit()
    return redirect(request.referrer or '/')

@app.route('/change_password/<int:id>', methods=['POST'])
def change_password(id):
    with get_db() as conn:
        conn.execute("UPDATE users SET password=? WHERE id=?", (request.form.get('new_password'), id))
        conn.commit()
    return redirect('/admin?tab=passwords')

@app.route('/delete_student/<int:id>')
def delete_student(id):
    with get_db() as conn:
        conn.execute("DELETE FROM students WHERE id=?", (id,))
        conn.commit()
    return redirect('/admin?tab=students')

# ----------------- ATTRACTIVE OFFICIAL RECEIPTS & SLIPS -----------------
@app.route('/print_grocery_slip', methods=['POST'])
def print_grocery_slip():
    items = request.form.getlist('items')
    rows = "".join([f"<tr><td style='padding:10px; border:1px solid #333; font-weight:600;'>{itm}</td><td style='padding:10px; border:1px solid #333;'>{request.form.get('qty_'+itm, 'लागेल तेवढे')}</td><td style='padding:10px; border:1px solid #333;'>[  ]</td></tr>" for itm in items])
    html = f'''<!DOCTYPE html><html><head><title>कॅन्टीन खरेदी पावती</title></head>
    <body style="font-family:'Segoe UI',sans-serif; padding:30px; color:#1e293b;">
        <div style="border:2px solid #065f46; padding:25px; border-radius:8px; max-width:700px; margin:auto;">
            <div style="text-align:center; border-bottom:2px solid #065f46; padding-bottom:12px;">
                <h2 style="margin:0; color:#065f46; font-size:24px;">श्रीगुरु करिअर अकॅडमी (कॅन्टीन विभाग)</h2>
                <p style="margin:4px 0 0; font-size:12px;">आडूर, ता. करवीर, जि. कोल्हापूर | संपर्क: ९९२११११९६०</p>
                <b style="display:inline-block; margin-top:8px; background:#065f46; color:white; padding:3px 12px; border-radius:4px; font-size:13px;">किराणा व भाजीपाला खरेदी मागणी पत्र</b>
            </div>
            <div style="display:flex; justify-content:space-between; margin:15px 0 10px; font-size:13px;">
                <div><b>दिनांक:</b> {date.today().strftime('%d/%m/%Y')}</div>
                <div><b>मागणी सादरकर्ता:</b> व्यवस्थापिका (कॅन्टीन विभाग)</div>
            </div>
            <table style="width:100%; border-collapse:collapse; margin-top:10px; font-size:13px;">
                <thead><tr style="background:#f0fdf4;"><th style="padding:10px; border:1px solid #333; text-align:left;">साहित्य नाव</th><th style="padding:10px; border:1px solid #333; text-align:left;">वजन / नग</th><th style="padding:10px; border:1px solid #333; text-align:left;">मिळाले (Tick)</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <div style="margin-top:50px; display:flex; justify-content:space-between; font-size:13px; font-weight:bold;">
                <div>व्यवस्थापिका सही<br><small>(सौ. नीलम सचिन चौगले)</small></div>
                <div>दुकानदार / सप्लायर सही</div>
            </div>
        </div>
        <script>window.print();</script>
    </body></html>'''
    return render_template_string(html)

@app.route('/whatsapp_grocery_slip', methods=['POST'])
def whatsapp_grocery_slip():
    items = request.form.getlist('items')
    msg = f"श्रीगुरु करिअर अकॅडमी - कॅन्टीन खरेदी यादी:\nदिनांक: {date.today().strftime('%d/%m/%Y')}\n--------------------\n" + "\n".join([f"- {itm}: {request.form.get('qty_'+itm, 'लागेल तेवढे')}" for itm in items])
    return redirect("https://wa.me/?text=" + urllib.parse.quote(msg))

@app.route('/receipt/<int:id>')
def print_receipt(id):
    with get_db() as conn:
        student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
    if not student: return "विद्यार्थी सापडला नाही!", 404
    bal = safe_float(student['total_fees']) - safe_float(student['paid_fees'])
    
    html = f'''<!DOCTYPE html><html><head><title>अधिकृत फी पावती - {student['name']}</title></head>
    <body style="font-family:'Segoe UI',sans-serif; padding:30px; background:#fafafa; color:#0f172a;">
        <div style="border:3px double #0b3c5d; padding:25px; border-radius:10px; max-width:700px; margin:auto; background:white; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
            <div style="text-align:center; border-bottom:2px solid #0b3c5d; padding-bottom:12px;">
                <h1 style="margin:0; color:#0b3c5d; font-size:26px; letter-spacing:0.5px;">श्रीगुरु करिअर अकॅडमी</h1>
                <p style="margin:4px 0 0; font-size:12px; font-weight:600; color:#475569;">पोलीस व सैन्य भरती पूर्व प्रशिक्षण केंद्र | आडूर, ता. करवीर, जि. कोल्हापूर</p>
                <p style="margin:2px 0 0; font-size:11px; color:#64748b;">मोबाईल: ९९२११११९६० | अधिकृत पावती क्र: SG-REC-{student['id']:04d}</p>
                <div style="margin-top:8px;"><span style="background:#0b3c5d; color:#fde047; padding:4px 14px; border-radius:20px; font-size:12px; font-weight:bold; letter-spacing:1px;">अधिकृत फी पावती (FEE RECEIPT)</span></div>
            </div>
            <div style="display:flex; justify-content:space-between; margin:18px 0 10px; font-size:13px; font-weight:600;">
                <div><b>विद्यार्थी नाव:</b> {student['name']}</div>
                <div><b>दिनांक:</b> {date.today().strftime('%d/%m/%Y')}</div>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:15px; font-size:13px; font-weight:600;">
                <div><b>कोर्स नाव:</b> {student['course']}</div>
                <div><b>नोंदणी क्र (Reg No):</b> REG-{student['id']}</div>
            </div>
            <table style="width:100%; border-collapse:collapse; margin-top:5px; font-size:13px;">
                <thead><tr style="background:#f1f5f9;"><th style="padding:10px; border:1px solid #cbd5e1; text-align:left;">तपशील (Particulars)</th><th style="padding:10px; border:1px solid #cbd5e1; text-align:right;">रक्कम (₹)</th></tr></thead>
                <tbody>
                    <tr><td style="padding:10px; border:1px solid #cbd5e1;">एकूण मंजूर प्रवेश व प्रशिक्षण फी</td><td style="padding:10px; border:1px solid #cbd5e1; text-align:right;">₹{student['total_fees']:,.2f}</td></tr>
                    <tr style="background:#f0fdf4;"><td style="padding:10px; border:1px solid #cbd5e1; font-weight:bold; color:#15803d;">आतापर्यंत प्रत्यक्ष जमा केलेली फी</td><td style="padding:10px; border:1px solid #cbd5e1; text-align:right; font-weight:bold; color:#15803d;">₹{student['paid_fees']:,.2f}</td></tr>
                    <tr style="background:#fef2f2;"><td style="padding:10px; border:1px solid #cbd5e1; font-weight:bold; color:#b91c1c;">शिल्लक फी (Pending Balance)</td><td style="padding:10px; border:1px solid #cbd5e1; text-align:right; font-weight:bold; color:#b91c1c;">₹{bal:,.2f}</td></tr>
                </tbody>
            </table>
            <div style="margin-top:12px; font-size:11px; color:#64748b;">* ही पावती कॉम्प्युटरद्वारे तयार केलेली असून श्रीगुरु अकॅडमीच्या अधिकृत शिक्क्यानिशी ग्राह्य आहे.</div>
            <div style="margin-top:45px; display:flex; justify-content:space-between; align-items:flex-end; font-size:13px; font-weight:bold;">
                <div style="text-align:center;">-------------------------<br>विद्यार्थी / पालक स्वाक्षरी</div>
                <div style="text-align:center; border:2px dashed #94a3b8; padding:8px 15px; border-radius:50%; font-size:11px; color:#475569;">श्रीगुरु करिअर अकॅडमी<br>★ आडूर ★</div>
                <div style="text-align:center;">-------------------------<br>अधिकृत स्वाक्षरी व शिक्का</div>
            </div>
        </div>
        <script>window.print();</script>
    </body></html>'''
    return render_template_string(html)

# ----- STUDENT FULL REPORT ROUTE (FIXED & COMPLETE) -----
@app.route('/student_report/<int:student_id>', methods=['GET', 'POST'])
def student_report(student_id):
    if 'user_role' not in session and 'role' not in session:
        return redirect(url_for('login'))

    with get_db() as conn:
        student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not student:
            return "विद्यार्थी सापडला नाही!", 404

        if request.method == 'POST':
            diet_plan = request.form.get('diet_plan')
            admin_remark = request.form.get('admin_remark')
            conn.execute("UPDATE students SET diet_plan = ?, admin_remark = ? WHERE id = ?", (diet_plan, admin_remark, student_id))
            conn.commit()
            return redirect(url_for('student_report', student_id=student_id))

        # १. हजेरी नोंदी (Attendance)
        try:
            attendance_records = conn.execute("""
                SELECT att_date as date, status, att_type as marked_by 
                FROM attendance 
                WHERE person_id = ? 
                ORDER BY att_date DESC LIMIT 30
            """, (student_id,)).fetchall()
        except Exception:
            attendance_records = []

        # २. मैदानी चाचणी अहवाल (Physical Tests - Clerk & Trainer)
        try:
            physical_records = conn.execute("""
                SELECT * FROM physical_tests 
                WHERE student_id = ? 
                ORDER BY test_date DESC
            """, (student_id,)).fetchall()
        except Exception:
            physical_records = []

        # ३. लेखी परीक्षा गुण निकाल (Written Tests)
        try:
            written_records = conn.execute("""
                SELECT * FROM written_tests 
                WHERE student_id = ? 
                ORDER BY test_date DESC
            """, (student_id,)).fetchall()
        except Exception:
            written_records = []

        # ४. आरोग्य व ट्रेनर डाएट शिफारस (Student Care & Diet Log)
        try:
            care_logs = conn.execute("""
                SELECT * FROM student_care_log 
                WHERE student_id = ? 
                ORDER BY care_date DESC
            """, (student_id,)).fetchall()
        except Exception:
            care_logs = []

        # ५. सुट्टी गेटपास व शिस्तभंग नोंदी (Discipline & Gatepass)
        try:
            discipline_logs = conn.execute("""
                SELECT * FROM discipline_records 
                WHERE student_id = ? 
                ORDER BY record_date DESC
            """, (student_id,)).fetchall()
        except Exception:
            discipline_logs = []

        # ६. किट वाटप नोंदी (Kit Distribution)
        try:
            kit_logs = conn.execute("""
                SELECT * FROM kit_distribution 
                WHERE student_id = ? 
                ORDER BY issue_date DESC
            """, (student_id,)).fetchall()
        except Exception:
            kit_logs = []

    return render_template('student_report.html', 
                           student=student, 
                           attendance=attendance_records, 
                           physical_records=physical_records,
                           written_records=written_records,
                           care_logs=care_logs,
                           discipline_logs=discipline_logs,
                           kit_logs=kit_logs)
# ================= PHYSICAL / GROUND FITNESS TRACKER =================
def calculate_ground_marks(gender, event_name, val):
    try:
        val = float(val)
    except Exception:
        return 0

    gender = str(gender or 'पुरुष')

    if any(k in gender for k in ['पुरुष', 'Boy', 'Male', 'boy', 'male']):
        if event_name == '1600m':
            if val <= 310: return 20
            elif val <= 330: return 18
            elif val <= 350: return 15
            elif val <= 370: return 12
            elif val <= 390: return 9
            elif val <= 410: return 5
            else: return 0
        elif event_name == '100m':
            if val <= 11.50: return 15
            elif val <= 12.50: return 12
            elif val <= 13.50: return 9
            elif val <= 14.50: return 6
            elif val <= 15.50: return 3
            else: return 0
        elif event_name == 'shot_put':
            if val >= 8.50: return 15
            elif val >= 7.90: return 12
            elif val >= 7.30: return 9
            elif val >= 6.70: return 6
            elif val >= 6.10: return 3
            else: return 0
    else:
        if event_name == '800m':
            if val <= 170: return 20
            elif val <= 190: return 18
            elif val <= 210: return 15
            elif val <= 230: return 12
            elif val <= 250: return 9
            elif val <= 270: return 5
            else: return 0
        elif event_name == '100m':
            if val <= 14.00: return 15
            elif val <= 15.00: return 12
            elif val <= 16.00: return 9
            elif val <= 17.00: return 6
            elif val <= 18.00: return 3
            else: return 0
        elif event_name == 'shot_put':
            if val >= 6.00: return 15
            elif val >= 5.50: return 12
            elif val >= 5.00: return 9
            elif val >= 4.50: return 6
            elif val >= 4.00: return 3
            else: return 0
    return 0

@app.route('/ground_tracker', methods=['GET', 'POST'])
def ground_tracker():
    user_role = session.get('user_role') or session.get('role', '')
    if not user_role:
        return redirect(url_for('login'))

    user_name = session.get('name', user_role)
    today_str = datetime.now().strftime('%Y-%m-%d')
    msg = None

    try:
        with get_db() as conn:
            if request.method == 'POST':
                student_id = request.form.get('student_id')
                test_date = request.form.get('test_date', today_str)
                event_name = request.form.get('event_name')
                raw_value = request.form.get('raw_value', 0)
                remark = request.form.get('remark', '')

                student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
                gender = 'पुरुष'
                if student:
                    try:
                        gender = student['gender'] if 'gender' in student.keys() else 'पुरुष'
                    except Exception:
                        gender = 'पुरुष'

                marks = calculate_ground_marks(gender, event_name, raw_value)
                conn.execute("""
                    INSERT INTO ground_records (student_id, test_date, event_name, raw_value, marks, trainer_name, remark)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, test_date, event_name, raw_value, marks, user_name, remark))
                conn.commit()
                msg = f"चाचणी यशस्वीरित्या नोंदवली गेली! मिळालेले गुण: {marks}"

            students = conn.execute("SELECT id, name FROM students ORDER BY name ASC").fetchall()
            
            recent_records = conn.execute("""
                SELECT g.id, g.student_id, g.test_date, g.event_name, g.raw_value, g.marks, g.trainer_name, g.remark, s.name as student_name
                FROM ground_records g
                LEFT JOIN students s ON g.student_id = s.id
                ORDER BY g.id DESC LIMIT 25
            """).fetchall()

    except Exception as e:
        return f"<h3>एरर आला आहे: {str(e)}</h3>"

    student_options = "".join([f"<option value='{s['id']}'>{s['name']} (हजेरी क्र./ID: {s['id']})</option>" for s in students])
    
    table_rows = ""
    for r in recent_records:
        s_name = r['student_name'] if r['student_name'] else f"ID: {r['student_id']}"
        t_name = r['trainer_name'] if r['trainer_name'] else '-'
        rem = r['remark'] if r['remark'] else ''
        table_rows += f"""<tr>
            <td>{r['test_date']}</td>
            <td><b>{s_name}</b></td>
            <td>{r['event_name']}</td>
            <td>{r['raw_value']}</td>
            <td><b style='color:#065f46; font-size:16px;'>{r['marks']}</b></td>
            <td>{t_name}<br><small style='color:#64748b;'>{rem}</small></td>
        </tr>"""

    if not table_rows:
        table_rows = "<tr><td colspan='6' style='text-align:center; padding:15px; color:#64748b;'>अजून कोणतीही मैदानी चाचणी नोंदवलेली नाही.</td></tr>"

    alert_box = f"<div style='background:#dcfce7; border:1px solid #86efac; color:#166534; padding:12px; border-radius:6px; margin-bottom:15px; font-weight:bold;'>✅ {msg}</div>" if msg else ""

    html = f"""<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>मैदानी चाचणी ट्रॅकर</title>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f1f5f9; margin: 0; padding: 15px; color: #1e293b; }}
  .container {{ max-width: 900px; margin: auto; background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.06); padding: 20px; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #065f46; padding-bottom: 12px; margin-bottom: 20px; }}
  .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin-bottom: 25px; }}
  .form-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
  label {{ font-size: 13px; font-weight: bold; margin-bottom: 5px; display: block; }}
  input, select {{ width: 100%; padding: 9px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-size: 14px; }}
  .btn {{ background: #065f46; color: white; border: none; padding: 10px 22px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: left; }}
  th {{ background: #f8fafc; color: #334155; }}
  .badge {{ background: #e2e8f0; padding: 4px 10px; border-radius: 4px; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h2 style="margin:0; color:#065f46;">🏃 मैदानी चाचणी ट्रॅकर (Ground Tracker)</h2>
      <small style="color:#64748b;">पोलीस भरती ५० गुण मैदानी रेकॉर्ड</small>
    </div>
    <div>
      <span class="badge">युजर: {user_name}</span>
      <a href="/" style="margin-left: 12px; color: #065f46; text-decoration: none; font-weight: bold;">मुख्य डॅशबोर्ड</a>
    </div>
  </div>

  {alert_box}

  <div class="card">
    <h3 style="margin-top:0; color:#065f46; font-size:16px;">➕ नवीन चाचणी नोंदवा</h3>
    <form method="POST">
      <div class="form-grid">
        <div>
          <label>विद्यार्थी निवडा:</label>
          <select name="student_id" required>
            <option value="">-- निवडा --</option>
            {student_options}
          </select>
        </div>
        <div>
          <label>तारीख:</label>
          <input type="date" name="test_date" required value="{today_str}">
        </div>
        <div>
          <label>इव्हेंट:</label>
          <select name="event_name" required>
            <option value="1600m">१६०० मी. धावणे (मुले)</option>
            <option value="800m">८०० मी. धावणे (मुली)</option>
            <option value="100m">१०० मी. स्प्रिंट</option>
            <option value="shot_put">गोळाफेक (मीटर)</option>
          </select>
        </div>
        <div>
          <label>कामगिरी (वेळ किंवा अंतर):</label>
          <input type="number" step="0.01" name="raw_value" placeholder="उदा. धावणे: सेकंद, गोळा: मीटर" required>
          <small style="color:#64748b; font-size:11px;">धावण्यासाठी एकूण सेकंद (उदा. 5 मि. 10 से. = 310) व गोळ्यासाठी मीटर टाका.</small>
        </div>
      </div>
      <div style="margin-top: 15px;">
        <label>शेरा (पर्यायी):</label>
        <input type="text" name="remark" placeholder="उदा. स्टॅमिना चांगला, सुधारणा आवश्यक">
      </div>
      <div style="margin-top: 18px;">
        <button type="submit" class="btn">💾 चाचणी व गुण सेव्ह करा</button>
      </div>
    </form>
  </div>

  <h3 style="margin-bottom:8px; color:#334155;">📋 मैदानी चाचणी नोंदवही (Recent Records)</h3>
  <table>
    <thead>
      <tr>
        <th>तारीख</th>
        <th>विद्यार्थी</th>
        <th>इव्हेंट</th>
        <th>नोंदवलेली वेळ/अंतर</th>
        <th>मिळालेले गुण</th>
        <th>ट्रेनर / शेरा</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</div>
</body>
</html>"""
    return render_template_string(html)  

# ----------------- ADMIN: STAFF ACTIVITIES & STUDENT REMARKS (EDIT & DELETE) -----------------
@app.route('/delete_staff_activity/<int:act_id>', methods=['POST', 'GET'])
def delete_staff_activity(act_id):
    if session.get('user_role') != 'Admin' and session.get('role') != 'admin':
        return "अनधिकृत प्रवेश! फक्त ॲडमिन ही नोंद डिलीट करू शकतात.", 403

    with get_db() as conn:
        conn.execute("DELETE FROM staff_activities WHERE id = ?", (act_id,))
        conn.commit()

    return redirect(request.referrer or url_for('admin_view'))

@app.route('/edit_staff_activity/<int:act_id>', methods=['GET', 'POST'])
def edit_staff_activity(act_id):
    if session.get('user_role') != 'Admin' and session.get('role') != 'admin':
        return "अनधिकृत प्रवेश! फक्त ॲडमिन ही नोंद एडिट करू शकतात.", 403

    with get_db() as conn:
        if request.method == 'POST':
            new_date = request.form.get('activity_date')
            new_action = request.form.get('action_text')
            new_remark = request.form.get('remark', '')

            conn.execute("""
                UPDATE staff_activities 
                SET activity_date = ?, action_text = ?, remark = ?
                WHERE id = ?
            """, (new_date, new_action, new_remark, act_id))
            conn.commit()
            return redirect(url_for('admin_view'))

        record = conn.execute("SELECT * FROM staff_activities WHERE id = ?", (act_id,)).fetchone()

    if not record:
        return "नोंद सापडली नाही!", 404

    form_html = f"""<!DOCTYPE html>
    <html lang="mr">
    <head>
    <meta charset="UTF-8"><title>स्टाफ नोंद दुरुस्त करा</title>
    <style>
      body {{ font-family: sans-serif; background: #f1f5f9; padding: 20px; }}
      .box {{ max-width: 500px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
      input, textarea {{ width: 100%; padding: 10px; margin: 8px 0 16px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }}
      .btn {{ background: #065f46; color: white; border: none; padding: 10px 18px; border-radius: 5px; cursor: pointer; font-weight: bold; }}
      .cancel {{ color: #dc2626; text-decoration: none; margin-left: 15px; }}
    </style>
    </head>
    <body>
    <div class="box">
      <h3 style="color:#065f46; margin-top:0;">✏️ स्टाफ नोंद दुरुस्त करा</h3>
      <p><b>कर्मचारी:</b> {record['staff_name']}</p>
      <form method="POST">
        <label>तारीख:</label>
        <input type="text" name="activity_date" value="{record['activity_date']}" required>
        
        <label>काम / कृती:</label>
        <textarea name="action_text" rows="3" required>{record['action_text']}</textarea>
        
        <label>शेरा / तपशील:</label>
        <input type="text" name="remark" value="{record['remark'] if record['remark'] else ''}">
        
        <button type="submit" class="btn">बदल सेव्ह करा</button>
        <a href="javascript:history.back()" class="cancel">रद्द करा</a>
      </form>
    </div>
    </body>
    </html>"""
    return render_template_string(form_html)

@app.route('/delete_student_remark/<int:record_id>', methods=['POST', 'GET'])
def delete_student_remark(record_id):
    if session.get('user_role') != 'Admin' and session.get('role') != 'admin':
        return "फक्त ॲडमिनला ही नोंद हटवण्याची परवानगी आहे.", 403

    with get_db() as conn:
        rec = conn.execute("SELECT student_id FROM student_activities WHERE id = ?", (record_id,)).fetchone()
        student_id = rec['student_id'] if rec else None
        
        conn.execute("DELETE FROM student_activities WHERE id = ?", (record_id,))
        conn.commit()

    if student_id:
        return redirect(f"/student_report/{student_id}")
    return redirect(request.referrer or url_for('admin_view'))

@app.route('/edit_student_remark/<int:record_id>', methods=['GET', 'POST'])
def edit_student_remark(record_id):
    if session.get('user_role') != 'Admin' and session.get('role') != 'admin':
        return "फक्त ॲडमिनला ही नोंद दुरुस्त करण्याची परवानगी आहे.", 403

    with get_db() as conn:
        if request.method == 'POST':
            new_date = request.form.get('activity_date')
            new_remark = request.form.get('remark')
            new_diet = request.form.get('diet_plan', '')
            student_id = request.form.get('student_id')

            conn.execute("""
                UPDATE student_activities 
                SET activity_date = ?, remark = ?, diet_plan = ?
                WHERE id = ?
            """, (new_date, new_remark, new_diet, record_id))
            conn.commit()
            return redirect(f"/student_report/{student_id}")

        record = conn.execute("SELECT * FROM student_activities WHERE id = ?", (record_id,)).fetchone()

    if not record:
        return "नोंद सापडली नाही!", 404

    form_html = f"""<!DOCTYPE html>
    <html lang="mr">
    <head>
    <meta charset="UTF-8"><title>विद्यार्थी अहवाल नोंद दुरुस्त करा</title>
    <style>
      body {{ font-family: sans-serif; background: #f1f5f9; padding: 20px; }}
      .box {{ max-width: 500px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
      label {{ font-size: 13px; font-weight: bold; margin-bottom: 5px; display: block; }}
      input, textarea {{ width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }}
      .btn {{ background: #065f46; color: white; border: none; padding: 10px 18px; border-radius: 5px; cursor: pointer; font-weight: bold; }}
      .cancel {{ color: #dc2626; text-decoration: none; margin-left: 15px; }}
    </style>
    </head>
    <body>
    <div class="box">
      <h3 style="color:#065f46; margin-top:0;">✏️ अहवाल नोंद दुरुस्त करा (Admin)</h3>
      <form method="POST">
        <input type="hidden" name="student_id" value="{record['student_id']}">
        
        <label>तारीख:</label>
        <input type="date" name="activity_date" value="{record['activity_date']}" required>
        
        <label>डाएट प्लॅन व विशेष सूचना:</label>
        <textarea name="diet_plan" rows="3">{record['diet_plan'] if 'diet_plan' in record.keys() and record['diet_plan'] else ''}</textarea>
        
        <label>ट्रेनरचा / विशेष शेरा:</label>
        <textarea name="remark" rows="3" required>{record['remark'] if record['remark'] else ''}</textarea>
        
        <button type="submit" class="btn">💾 बदल सेव्ह करा</button>
        <a href="javascript:history.back()" class="cancel">रद्द करा</a>
      </form>
    </div>
    </body>
    </html>"""
    return render_template_string(form_html)

# --- STUDY LAB & LIBRARY ROUTES ---
@app.route('/library')
def library_dashboard():
    with get_db() as conn:
        books = conn.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
        issues = conn.execute("SELECT * FROM book_issues WHERE status = 'Issued' ORDER BY id DESC").fetchall()
        seats = conn.execute("SELECT * FROM study_lab_seats ORDER BY seat_number ASC").fetchall()
    return render_template('library.html', books=books, issues=issues, seats=seats)

@app.route('/add_book', methods=['POST'])
def add_book():
    title = request.form.get('title')
    author = request.form.get('author')
    category = request.form.get('category')
    copies = int(request.form.get('copies', 1))
    with get_db() as conn:
        conn.execute("INSERT INTO books (title, author, category, total_copies, available_copies) VALUES (?, ?, ?, ?, ?)",
                     (title, author, category, copies, copies))
        conn.commit()
    return redirect('/library')

@app.route('/issue_book', methods=['POST'])
def issue_book():
    book_id = request.form.get('book_id')
    student_name = request.form.get('student_name')
    issue_date = request.form.get('issue_date')
    with get_db() as conn:
        conn.execute("INSERT INTO book_issues (book_id, student_name, issue_date, status) VALUES (?, ?, ?, 'Issued')",
                     (book_id, student_name, issue_date))
        conn.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ? AND available_copies > 0", (book_id,))
        conn.commit()
    return redirect('/library')

@app.route('/return_book/<int:issue_id>/<int:book_id>')
def return_book(issue_id, book_id):
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')
    with get_db() as conn:
        conn.execute("UPDATE book_issues SET return_date = ?, status = 'Returned' WHERE id = ?", (today, issue_id))
        conn.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = ?", (book_id,))
        conn.commit()
    return redirect('/library')
# ----------------- PUBLIC INQUIRY & CALLING DESK -----------------
PUBLIC_INQUIRY_HTML = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>प्रवेश चौकशी - श्रीगुरु करिअर अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: linear-gradient(135deg, #0b2545, #134e4a); color: #1e293b; min-height: 100vh; padding: 20px 10px; display: flex; align-items: center; justify-content: center; }
        .card { background: white; max-width: 520px; width: 100%; border-radius: 12px; padding: 25px; box-shadow: 0 15px 30px rgba(0,0,0,0.3); border-top: 5px solid #d97706; }
        h2 { margin: 0 0 5px; color: #0b2545; font-size: 22px; text-align: center; }
        p.sub { margin: 0 0 20px; text-align: center; font-size: 13px; color: #64748b; }
        label { font-size: 13px; font-weight: bold; margin-bottom: 4px; display: block; color: #334155; }
        input, select { width: 100%; padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-bottom: 14px; font-size: 14px; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #059669, #10b981); color: white; padding: 12px; border: none; border-radius: 6px; font-size: 15px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
<div class="card">
    <h2>⚔️ श्रीगुरु करिअर अकॅडमी, आडूर</h2>
    <p class="sub">पोलीस व सैन्य भरती पूर्व प्रशिक्षण केंद्र (जि. कोल्हापूर)<br><b>मोफत प्रवेश व हॉस्टेल माहिती अर्ज</b></p>
    {% if msg %}<div style="background:#dcfce7; color:#166534; padding:10px; border-radius:6px; margin-bottom:15px; text-align:center; font-weight:bold;">{{ msg }}</div>{% endif %}
    <form method="POST" action="/inquiry">
        <label>विद्यार्थ्याचे पूर्ण नाव *:</label>
        <input type="text" name="student_name" placeholder="उदा. सचिन दत्तात्रय चौगले" required>
        
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
            <div>
                <label>जिल्हा *:</label>
                <input type="text" name="district" placeholder="उदा. कोल्हापूर / सातारा" required>
            </div>
            <div>
                <label>तालुका:</label>
                <input type="text" name="taluka" placeholder="उदा. करवीर">
            </div>
        </div>

        <label>व्हॉट्सॲप / संपर्क मोबाईल *:</label>
        <input type="tel" name="phone" placeholder="१० अंकी मोबाईल नंबर" pattern="[0-9]{10}" required>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
            <div>
                <label>कोणत्या भरतीसाठी? *:</label>
                <select name="course">
                    <option value="महाराष्ट्र पोलीस भरती">महाराष्ट्र पोलीस भरती</option>
                    <option value="आर्मी भरती (अग्निवीर)">आर्मी भरती (अग्निवीर)</option>
                    <option value="SSC GD भरती">SSC GD भरती</option>
                    <option value="वनरक्षक / इतर भरती">वनरक्षक / इतर भरती</option>
                </select>
            </div>
            <div>
                <label>हॉस्टेल/मेस हवी का?:</label>
                <select name="hostel_interest">
                    <option value="होय (हॉस्टेल आवश्यक)">होय (हॉस्टेल आवश्यक)</option>
                    <option value="नाही (फक्त ग्राउंड व क्लास)">नाही (फक्त ग्राउंड व क्लास)</option>
                </select>
            </div>
        </div>

        <button type="submit" class="btn-submit">📲 मोफत माहिती मिळवा / नोंदणी करा</button>
    </form>
    <div style="text-align:center; margin-top:15px; font-size:12px; color:#64748b;">
        संपर्क: ९९२११११९६० | आडूर, ता. करवीर, जि. कोल्हापूर
    </div>
</div>
</body>
</html>'''

@app.route('/inquiry', methods=['GET', 'POST'])
def public_inquiry():
    msg = None
    if request.method == 'POST':
        s_name = request.form.get('student_name')
        dist = request.form.get('district')
        tal = request.form.get('taluka', '')
        phone = request.form.get('phone')
        course = request.form.get('course')
        hostel = request.form.get('hostel_interest', 'होय')
        t_date = date.today().strftime("%Y-%m-%d")

        with get_db() as conn:
            conn.execute("""
                INSERT INTO admission_inquiries (inquiry_date, student_name, district, taluka, phone, course, hostel_interest)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (t_date, s_name, dist, tal, phone, course, hostel))
            conn.commit()
        log_staff_activity("Website", f"नवीन चौकशी अर्ज: {s_name} ({dist} - {course})")
        msg = "तुमची नोंदणी यशस्वी झाली आहे! श्रीगुरु अकॅडमीकडून तुम्हाला लवकरच कॉल येईल."
    return render_template_string(PUBLIC_INQUIRY_HTML, msg=msg)

@app.route('/inquiries')
def inquiry_desk():
    if session.get('user_role') not in ['Admin', 'Clerk', 'Manager']:
        return redirect(url_for('login'))
    with get_db() as conn:
        inquiries = conn.execute("SELECT * FROM admission_inquiries ORDER BY id DESC").fetchall()
    
    html = '''<!DOCTYPE html>
    <html lang="mr"><head><meta charset="UTF-8"><title>चौकशी व कॉलिंग डेस्क</title>
    <style>
        body { font-family:'Segoe UI',sans-serif; background:#f8fafc; padding:15px; color:#1e293b; }
        table { width:100%; border-collapse:collapse; background:white; font-size:13px; margin-top:10px; }
        th, td { border:1px solid #cbd5e1; padding:8px; text-align:left; }
        th { background:#0b3c5d; color:white; }
        .btn-wa { background:#25D366; color:white; padding:4px 8px; border-radius:4px; text-decoration:none; font-weight:bold; }
        .btn-call { background:#0284c7; color:white; padding:4px 8px; border-radius:4px; text-decoration:none; font-weight:bold; }
    </style></head><body>
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <h2 style="color:#0b3c5d; margin:0;">📞 नवीन प्रवेश चौकशी व कॉलिंग डेस्क (Total: {{ inquiries|length }})</h2>
        <a href="/" style="text-decoration:none; font-weight:bold; color:#0b3c5d;">मुख्य डॅशबोर्ड</a>
    </div>
    <table>
        <thead><tr><th>तारीख</th><th>नाव</th><th>जिल्हा / तालुका</th><th>कोर्स</th><th>हॉस्टेल</th><th>संपर्क</th><th>स्थिती / शेरा</th><th>बदल</th></tr></thead>
        <tbody>
            {% for inq in inquiries %}
            <form action="/update_inquiry/{{ inq.id }}" method="POST">
            <tr>
                <td>{{ inq.inquiry_date }}</td>
                <td><b>{{ inq.student_name }}</b></td>
                <td>{{ inq.district }} ({{ inq.taluka or '-' }})</td>
                <td>{{ inq.course }}</td>
                <td>{{ inq.hostel_interest }}</td>
                <td>
                    <a href="tel:{{ inq.phone }}" class="btn-call">📞 कॉल</a>
                    <a href="https://wa.me/91{{ inq.phone }}?text=नमस्कार%20{{ inq.student_name }},%20श्रीगुरु%20करिअर%20अकॅडमी%20आडूर%20मध्ये%20आपली%20चौकशी%20प्राप्त%20झाली.%20नवीन%20बॅचची%20माहिती%20खालीलप्रमाणे:" target="_blank" class="btn-wa">📲 WA</a>
                </td>
                <td>
                    <select name="call_status">
                        <option value="नवीन चौकशी (New)" {% if inq.call_status=='नवीन चौकशी (New)' %}selected{% endif %}>नवीन चौकशी</option>
                        <option value="कॉल झाला - विचारून सांगणार" {% if inq.call_status=='कॉल झाला - विचारून सांगणार' %}selected{% endif %}>विचारून सांगणार</option>
                        <option value="भेट देणार (Visiting)" {% if inq.call_status=='भेट देणार (Visiting)' %}selected{% endif %}>भेट देणार</option>
                        <option value="प्रवेश निश्चित (Admitted)" {% if inq.call_status=='प्रवेश निश्चित (Admitted)' %}selected{% endif %}>प्रवेश निश्चित</option>
                    </select><br>
                    <input type="text" name="staff_note" value="{{ inq.staff_note or '' }}" placeholder="कॉल शेरा..." style="width:90%; margin-top:3px; padding:3px;">
                </td>
                <td><button type="submit" style="background:#059669; color:white; border:none; padding:4px 8px; border-radius:3px; cursor:pointer;">💾</button></td>
            </tr>
            </form>
            {% else %}
            <tr><td colspan="8" style="text-align:center; color:#64748b;">सध्या कोणतीही चौकशी आलेली नाही.</td></tr>
            {% endfor %}
        </tbody>
    </table>
    </body></html>'''
    return render_template_string(html, inquiries=inquiries)

@app.route('/update_inquiry/<int:id>', methods=['POST'])
def update_inquiry(id):
    c_status = request.form.get('call_status')
    note = request.form.get('staff_note')
    with get_db() as conn:
        conn.execute("UPDATE admission_inquiries SET call_status=?, staff_note=? WHERE id=?", (c_status, note, id))
        conn.commit()
    return redirect('/inquiries') 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

init_db()
