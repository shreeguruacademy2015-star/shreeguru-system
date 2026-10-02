import os
import shutil
import re
from datetime import date, datetime, timedelta 
from flask import Flask, redirect, render_template, render_template_string, request, send_file, send_from_directory, url_for, session, Response
from werkzeug.utils import secure_filename
import io
import csv
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_complete_bulletproof_v75_full_master_complete"

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

            # --- SETTINGS TABLE FOR TEST LAUNCH & UPI ---
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cur.execute("INSERT INTO settings (key, value) VALUES ('test_launched', 'no') ON CONFLICT (key) DO NOTHING")
            cur.execute("INSERT INTO settings (key, value) VALUES ('test_fee', '0') ON CONFLICT (key) DO NOTHING")
            cur.execute("INSERT INTO settings (key, value) VALUES ('upi_id', '9921111960@ybl') ON CONFLICT (key) DO NOTHING")
            cur.execute("INSERT INTO settings (key, value) VALUES ('qr_image_url', 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=upi://pay?pa=9921111960@ybl&pn=ShreeguruCareerAcademy') ON CONFLICT (key) DO NOTHING")

            # --- MULTIPLE TEST PAPERS ---
            cur.execute('''CREATE TABLE IF NOT EXISTS test_papers (
                id SERIAL PRIMARY KEY,
                test_title TEXT NOT NULL,
                test_fee REAL DEFAULT 0,
                status TEXT DEFAULT 'Active'
            )''')

            # --- DYNAMIC QUESTIONS WITH EXPLANATION ---
            cur.execute('''CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                test_id INTEGER DEFAULT 1,
                question TEXT NOT NULL,
                opt_a TEXT NOT NULL,
                opt_b TEXT NOT NULL,
                opt_c TEXT NOT NULL,
                opt_d TEXT NOT NULL,
                correct TEXT NOT NULL,
                explanation TEXT DEFAULT ''
            )''')

            cur.execute('SELECT COUNT(*) as count FROM test_papers')
            if cur.fetchone()['count'] == 0:
                cur.execute("INSERT INTO test_papers (id, test_title, test_fee, status) VALUES (1, 'राज्यस्तरीय पोलीस भरती महासराव टेस्ट #१', 0, 'Active')")
                conn.commit()

            cur.execute('SELECT COUNT(*) as count FROM questions')
            res = cur.fetchone()
            if res['count'] == 0:
                default_qs = [
                    (1, "महाराष्ट्राची राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B", "मुंबई ही महाराष्ट्राची आर्थिक व प्रशासकीय राजधानी आहे."),
                    (1, "क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A", "अहमदनगर हा क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा आहे."),
                    (1, "स्वराज्य स्थापना कोणी केली?", "छत्रपती संभाजी महाराज", "छत्रपती शिवाजी महाराज", "महात्मा ज्योतिराव फुले", "संत ज्ञानेश्वर", "B", "छत्रपती शिवाजी महाराजांनी रयतेच्या राज्याची (स्वराज्य) स्थापना केली."),
                    (1, "भारताचे राष्ट्रगीत 'जन गण मन' कोणी लिहिले?", "बंकिमचंद्र चटर्जी", "रविंद्रनाथ टागोर", "महात्मा गांधी", "लोकमान्य टिळक", "B", "रविंद्रनाथ टागोर यांनी जन गण मन हे राष्ट्रगीत लिहिले."),
                    (1, "महाराष्ट्रात एकूण किती जिल्हे आहेत?", "३४", "३५", "३६", "३७", "C", "महाराष्ट्रात सध्या प्रशासकीयदृष्ट्या एकूण ३६ जिल्हे आहेत.")
                ]
                cur.executemany('INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', default_qs)
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
                CREATE TABLE IF NOT EXISTS staff_activities (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER,
                    staff_name TEXT,
                    activity_date TEXT,
                    action_text TEXT,
                    remark TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS student_activities (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER,
                    activity_date TEXT,
                    diet_plan TEXT,
                    remark TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ground_records (
                    id SERIAL PRIMARY KEY,
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
                    staff_note TEXT DEFAULT '',
                    upi_ref TEXT DEFAULT 'Free',
                    payment_status TEXT DEFAULT 'Approved',
                    valid_till TEXT DEFAULT '',
                    answers_json TEXT DEFAULT ''
                )
            """)

            # Safe column migrations
            try:
                cur.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS test_id INTEGER DEFAULT 1")
                cur.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS explanation TEXT DEFAULT ''")
                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS upi_ref TEXT DEFAULT 'Free'")
                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'Approved'")
                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS valid_till TEXT DEFAULT ''")
                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS answers_json TEXT DEFAULT ''")
                conn.commit()
            except Exception as ex:
                print(f"Migration Info: {ex}")

            conn.commit()

            days = ['सोमवार', 'मंगळवार', 'बुधवार', 'गुरुवार', 'शुक्रवार', 'शनिवार', 'रविवार']
            for d in days:
                cur.execute("INSERT INTO mess_diet (day_name, breakfast, lunch, dinner, special_diet) VALUES (%s, 'पोहे / उपमा', 'डाळ, भात, चपाती, उसळ', 'भाकरी, सुकी भाजी, आमटी', 'दूध, केळी, भिजवलेले हरभरे-गूळ') ON CONFLICT (day_name) DO NOTHING", (d,))
            conn.commit()

init_db()

# ----------------- 500 GROCERY MASTER ITEMS -----------------
GROCERY_MASTER_500 = [
    "तूर डाळ (पिवळी)", "मूग डाळ (सालीसहित)", "मूग डाळ (मऊ डाळ)", "मसूर डाळ (लाल मसूर)", "हरभरा डाळ (चणा डाळ)",
    "उडीद डाळ (पांढरी)", "उडीद डाळ (सालीसहित)", "मटकी डाळ", "पांढरी मटकी", "मटकी (हिरवी/तपकिरी)",
    "मूग (अखंड हिरवे मूग)", "चवळी (लाल व पांढरी)", "काळे वाटाणे", "पांढरे वाटाणे", "काळे चणे (देशी)",
    "काबुली चणे (छोले)", "राजमा (लाल)", "राजमा (चित्रा)", "हरभरा (भिजवण्यासाठी)", "हुलगा (कुळीथ)",
    "मसुरी उसळ", "सोणा मसूर तांदूळ", "बासमती तांदूळ", "उत्तम प्रतीचे गहू", "साबुदाणा (मध्यम व बारीक)",
    "केळी (ताजी डाएट)", "संत्री (रसदार)", "मोसंबी", "डाळिंब", "पपई",
    "कलिंगड", "खरबूज", "सफरचंद (Apple)", "हिरवी व काळी द्राक्षे", "आंबा (सिझननुसार)",
    "लिंबू (रसदार पिवळी)", "काजू तुकडे / अखंड", "बदाम (किरमिजी)", "मनुका (काळी/पिवळी)", "अक्रोड गिरी (Walnut)",
    "पिस्ता तुकडे", "खजूर (बिया काढलेले)", "अंजीर (सुके)", "टरबूज बिया (मगज)", "किसलेले खोबरे (सुके)",
    "ओले नारळ", "सीताफळ", "अननस (Pineapple)", "पेरू (Guava)", "चिकू",
    "कांदा (नवीन व जुना)", "बटाटा (मध्यम साईज)", "लसूण (देशी व चायनीज)", "आले (ताजे कंद)", "टोमॅटो (लाल व रसरशीत)",
    "हिरवी मिरची", "कढीपत्ता", "कोथिंबीर", "पुदिना", "मेथी भाजी",
    "पालक भाजी", "शेपू भाजी", "कांदापात", "मुळा व मुळ्याची पाने", "भेंडी",
    "गवार शेंगा", "कोवळी वांगी", "कोबी (Band Gobhi)", "फ्लॉवर (Cauliflower)", "सिमला मिरची (Capsicum)",
    "दुधी भोपळा (लौकी)", "पडवळ", "कारले", "शेवग्याची शेंग", "मटार दाणे (हिरवे)",
    "मोहरी (राई)", "जिरे (साधे)", "शाहजिरे", "काळे मिरे (अखंड)", "लवंग",
    "वेलची (हिरवी)", "दालचिनी (टुकडे)", "तमालपत्र", "चक्रफूल (बडियन)", "जायफळ",
    "कसुरी मेथी", "हळद पावडर (शुद्ध)", "लाल मिरची पावडर", "लाल तिखट (तूरट)", "धना पावडर",
    "जिरा पावडर", "गोडा मसाला", "गरम मसाला पावडर", "किचन किंग मसाला", "सांबर मसाला",
    "पावभाजी मसाला", "काळा मसाला (कोल्हापुरी)", "हिंग (पावडर व खडा)", "पांढरे मीठ", "खडे मीठ (शेल मीठ)",
    "पोहे (जाड व पातळ)", "रवा (बारीक व मोठा)", "मैदा व बेसन पीठ", "गहू पीठ (आटा)", "ज्वारी व बाजरी पीठ",
    "शेंगदाणा तेल", "सोयाबीन तेल", "सूर्यफूल तेल", "शुद्ध साजूक तूप", "वनस्पती तूप",
    "ताजे दूध", "दही (मोठे डबे)", "छास / ताक", "पनीर", "खवा / मावा",
    "अंडी (ट्रे)", "सोयाबीन वड्या", "मोड आलेले मूग/मटकी", "ओट्स पॅकेट", "ग्लुकोज ड्रिंक पावडर",
    "डिशवॉश लिक्विड (कॅन)", "फिनाइल / क्लिनर", "हार्पिक टॉयलेट क्लिनर", "कचऱ्याच्या पिशव्या", "सुती नॅपकिन्स",
    "डिस्पोजेबल पत्रावळी व द्रोण", "पेपर कप व चमचे", "एलपीजी गॅस सिलिंडर", "काडेपेटी व लायटर", "पिण्याच्या पाचे जार"
] + [f"इतर अतिरिक्त खाद्य/कॅन्टीन साहित्याचा साठा #{i}" for i in range(131, 501)]

# ----------------- LOGIN HTML -----------------
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
        .btn-alt { background: #475569; color: white; padding: 6px 12px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; margin-right: 5px; }
    </style>
    <script>
        function toggleAll(source) {
            checkboxes = document.getElementsByName('items');
            for(var i=0, n=checkboxes.length; i<n; i++) {
                checkboxes[i].checked = source.checked;
            }
        }
    </script>
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
    <a href="/inquiries" class="mgr-btn" style="background:#b45309; color:white;">📞 चौकशी व टेस्ट डेस्क</a>
    <a href="/manager?tab=grocery" class="mgr-btn {% if curr_tab == 'grocery' %}active{% endif %}">🛒 {{ 'Grocery Slip' if lang == 'en' else '५०० किराणा मास्टर स्लिप' }}</a>
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
        <form action="/print_grocery_slip" method="POST" target="_blank">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <h3 style="margin:0; color:#065f46;">🛒 कॅन्टीन संपूर्ण ५०० वस्तूंची किराणा व भाजीपाला खरेदी स्लिप</h3>
                <div>
                    <button type="submit" class="btn-act" style="background:#059669;">🖨️ {{ 'Print Slip' if lang == 'en' else 'खरेदी पावती प्रिंट' }}</button>
                    <button type="submit" formaction="/whatsapp_grocery_slip" formtarget="_blank" class="btn-act" style="background:#25D366;">📲 WhatsApp</button>
                </div>
            </div>
            <div style="margin:12px 0; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBoxMgr').checked = true; toggleAll(document.getElementById('selectAllBoxMgr'));">✅ सर्व निवडा</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBoxMgr').checked = false; toggleAll(document.getElementById('selectAllBoxMgr'));">❌ सर्व काढा</button>
                <label style="font-size:12px; font-weight:bold;"><input type="checkbox" id="selectAllBoxMgr" onchange="toggleAll(this)"> सर्व ऑन/ऑफ करा</label>
            </div>
            <table>
                <thead><tr><th style="width:40px; text-align:center;">निवड</th><th style="width:50px;">क्र.</th><th>साहित्याचे अचूक नाव (५०० वस्तू)</th><th style="width:130px;">वजन / प्रमाण</th></tr></thead>
                <tbody>
                    {% for item in grocery_items %}
                    <tr>
                        <td style="text-align:center;"><input type="checkbox" name="items" value="{{ item }}"></td>
                        <td><b>{{ loop.index }}</b></td>
                        <td><b>{{ item }}</b></td>
                        <td><input type="text" name="qty_{{ item }}" value="लागेल तेवढे" style="width:110px; padding:3px;"></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
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
    <div><a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">बाहेर पडा</a></div>
</div>
<div class="nav-bar">
    <a href="/inquiries" class="nav-btn" style="background:#b45309; color:white;">📞 चौकशी व टेस्ट डेस्क</a>
    <a href="/trainer?tab=practice" class="nav-btn {% if curr_tab == 'practice' %}active{% endif %}">🏃‍♂️ आजचा सराव</a>
    <a href="/trainer?tab=stopwatch" class="nav-btn {% if curr_tab == 'stopwatch' %}active{% endif %}" style="background:#f59e0b; color:#111;">⏱️ स्टॉपवॉच</a>
    <a href="/trainer?tab=physical" class="nav-btn {% if curr_tab == 'physical' %}active{% endif %}">🏃‍♂️ फिजिकल रेकॉर्ड नोंद</a>
    <a href="/trainer?tab=student_diet" class="nav-btn {% if curr_tab == 'student_diet' %}active{% endif %}" style="background:#10b981; color:white;">🥗 डाएट शिफारस</a>
    <a href="/trainer?tab=att" class="nav-btn {% if curr_tab == 'att' %}active{% endif %}">📋 मैदानी हजेरी</a>
    <a href="/trainer?tab=written" class="nav-btn {% if curr_tab == 'written' %}active{% endif %}">📝 रिटर्न टेस्ट</a>
    <a href="/trainer?tab=inj" class="nav-btn {% if curr_tab == 'inj' %}active{% endif %}">🩹 इजा व सुट्टी नोंद</a>
    <a href="/trainer?tab=req" class="nav-btn {% if curr_tab == 'req' %}active{% endif %}" style="background:#e11d48; color:white;">📩 ॲडमिन विनंती</a>
    <a href="/trainer?tab=tasks" class="nav-btn {% if curr_tab == 'tasks' %}active{% endif %}">📢 ॲडमिन सूचना</a>
</div>
<div class="container">
    {% if curr_tab == 'practice' %}
    <div class="card">
        <h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ आजचा प्रत्यक्ष मैदानी सराव नोंदवा</h3>
        <form action="/save_trainer_practice" method="POST">
            सत्र: <select name="session_time"><option value="सकाळ सत्र">🌅 सकाळ</option><option value="संध्याकाळ सत्र">🌇 संध्याकाळ</option></select>
            मैदानाची स्थिती: <select name="ground_status"><option value="सराव योग्य">✔️ सराव योग्य</option><option value="चिखल">🌧️ चिखल</option></select>
            सराव तपशील: <input type="text" name="workout_details" placeholder="उदा. 1600m run" required>
            <button type="submit" class="btn-act">+ सराव नोंदवा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'stopwatch' %}
    <div class="card" style="text-align:center;">
        <h3 style="color:#0284c7; margin-top:0;">⏱️️ डिजिटल स्टॉपवॉच</h3>
        <div id="sw_display" style="font-size:46px; font-weight:bold; color:#0b3c5d; font-family:monospace; margin:15px 0;">00:00.00</div>
        <div style="display:flex; justify-content:center; gap:8px;">
            <button onclick="startSW()" class="btn-act" style="background:green; width:95px;">Start</button>
            <button onclick="pauseSW()" class="btn-act" style="background:#f59e0b; width:95px;">Pause</button>
            <button onclick="lapSW()" class="btn-act" style="background:#0284c7; width:95px;">Lap</button>
            <button onclick="resetSW()" class="btn-act" style="background:red; width:95px;">Reset</button>
        </div>
    </div>
    <script>
    var sw_t, sw_ms = 0, lap_c = 0;
    function startSW() { if(!sw_t) { sw_t = setInterval(function() { sw_ms += 10; updateSW(); }, 10); } }
    function pauseSW() { clearInterval(sw_t); sw_t = null; }
    function resetSW() { pauseSW(); sw_ms = 0; lap_c = 0; updateSW(); }
    function updateSW() {
        var m = Math.floor(sw_ms / 60000), s = Math.floor((sw_ms % 60000) / 1000), cs = Math.floor((sw_ms % 1000) / 10);
        document.getElementById('sw_display').innerText = String(m).padStart(2,'0') + ":" + String(s).padStart(2,'0') + "." + String(cs).padStart(2,'0');
    }
    </script>
    {% endif %}

    {% if curr_tab == 'physical' %}
    <div class="card">
        <h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ फिजिकल चाचणी गुण भरणे</h3>
        <form action="/add_physical_record" method="POST">
            विद्यार्थी: <select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select>
            तारीख: <input type="date" name="test_date" value="{{ today_date }}" required>
            1600m: <input type="text" name="run_time" placeholder="05:10">
            100m: <input type="text" name="sprint_time" placeholder="12.2">
            गोळाफेक: <input type="text" name="shot_put_dist" placeholder="8.5">
            पुल-अप्स: <input type="number" name="pullups" value="8">
            एकूण गुण: <input type="number" name="total_obtained" required>
            <button type="submit" class="btn-act">+ गुण सेव्ह करा</button>
        </form>
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
    <div><h2 style="margin:0; font-size:18px;">📋 ऑफिस क्लार्क कक्ष</h2><small>श्रीगुरु करिअर अकॅडमी</small></div>
    <div><a href="/logout" style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">बाहेर पडा</a></div>
</div>
<div class="nav-bar"> 
    <a href="/inquiries" class="clk-btn" style="background:#b45309;">📞 चौकशी व टेस्ट डेस्क</a>
    <a href="/clerk?tab=stud" class="clk-btn {% if curr_tab == 'stud' %}active{% endif %}">👥 विद्यार्थी यादी</a>
    <a href="/clerk?tab=adm" class="clk-btn {% if curr_tab == 'adm' %}active{% endif %}">📝 नवीन प्रवेश</a>
    <a href="/clerk?tab=fee" class="clk-btn {% if curr_tab == 'fee' %}active{% endif %}">💰 फी जमा</a>
    <a href="/attendance" target="_blank" class="clk-btn" style="background: linear-gradient(135deg, #6366f1, #a855f7); color: white;">📋 हजेरी</a>
    <a href="/library" target="_blank" class="clk-btn" style="background: linear-gradient(135deg, #0284c7, #06b6d4); color: white;">📚 लायब्ररी</a>
    <a href="/clerk?tab=hostel" class="clk-btn {% if curr_tab == 'hostel' %}active{% endif %}" style="background:#8e2de2;">🏠 हॉस्टेल/मेस फी</a>
    <a href="/clerk?tab=physical" class="clk-btn {% if curr_tab == 'physical' %}active{% endif %}" style="background:#0284c7;">🏃‍♂️ फिजिकल टेस्ट</a>
    <a href="/clerk?tab=written" class="clk-btn {% if curr_tab == 'written' %}active{% endif %}" style="background:#10b981;">📝 रिटर्न टेस्ट</a>
    <a href="/clerk?tab=exp" class="clk-btn {% if curr_tab == 'exp' %}active{% endif %}">💵 खर्च नोंद</a>
    <a href="/clerk?tab=kit" class="clk-btn {% if curr_tab == 'kit' %}active{% endif %}">📦 किट वाटप</a>
    <a href="/clerk?tab=grocery" class="clk-btn {% if curr_tab == 'grocery' %}active{% endif %}" style="background:#059669;">🛒 ५०० किराणा स्लिप</a>
    <a href="/clerk?tab=req" class="clk-btn {% if curr_tab == 'req' %}active{% endif %}" style="background:#e11d48;">📩 ॲडमिन विनंती</a>
    <a href="/clerk?tab=tasks" class="clk-btn {% if curr_tab == 'tasks' %}active{% endif %}">📢 ॲडमिन सूचना</a>
</div>
<div class="container">
    {% if curr_tab == 'stud' %}
    <div class="card">
        <h3>📋 सर्व विद्यार्थी यादी</h3>
        <table>
            <thead><tr><th>Reg</th><th>नाव</th><th>कोर्स</th><th>फोन</th><th>शिल्लक फी</th><th>कृती</th></tr></thead>
            <tbody>
                {% for s in students %}
                <tr>
                    <td>REG-{{ s.id }}</td><td><b>{{ s.name }}</b></td><td>{{ s.course }}</td><td>{{ s.phone }}</td>
                    <td style="color:red; font-weight:bold;">₹{{ (s.total_fees or 0) - (s.paid_fees or 0) }}</td>
                    <td><a href="/receipt/{{ s.id }}" target="_blank" class="btn-act" style="background:#10b981;">🧾 पावती</a><a href="/student_report/{{ s.id }}" target="_blank" class="btn-act" style="background:#6366f1;">📋 रिपोर्ट</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'grocery' %}
    <div class="card">
        <h3 style="color:#065f46; margin-top:0;">🛒 कॅन्टीन व मेस खरेदी मास्टर यादी (५०० वस्तू)</h3>
        <form action="/print_grocery_slip" method="POST" target="_blank">
            <div style="margin-bottom:15px; display:flex; gap:10px; align-items:center;">
                <button type="submit" class="btn-act" style="background:#059669;">🖨️ निवडलेल्या साहित्याची पावती प्रिंट करा</button>
            </div>
            <table>
                <thead><tr><th style="width:40px; text-align:center;">निवड</th><th style="width:50px;">क्र.</th><th>साहित्याचे नाव</th><th style="width:130px;">प्रमाण</th></tr></thead>
                <tbody>
                    {% for item in grocery_items %}
                    <tr>
                        <td style="text-align:center;"><input type="checkbox" name="items" value="{{ item }}"></td>
                        <td><b>{{ loop.index }}</b></td>
                        <td><b>{{ item }}</b></td>
                        <td><input type="text" name="qty_{{ item }}" value="लागेल तेवढे" style="width:110px; padding:3px;"></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </form>
    </div>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- DETAILED REVIEW TEMPLATE -----------------
REVIEW_HTML = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>टेस्ट सविस्तर उत्तरपत्रिका व विश्लेषण</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #f8fafc; color: #1e293b; padding: 20px; margin: 0; }
        .container { max-width: 750px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #0b2545; text-align: center; }
        .score-card { background: #f0fdf4; border: 2px solid #86efac; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 25px; }
        .q-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .ans-tag { display: inline-block; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-top: 5px; }
        .correct-ans { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
        .wrong-ans { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
        .exp-box { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px; margin-top: 10px; font-size: 13px; color: #1e40af; }
    </style>
</head>
<body>
<div class="container">
    <h2>🎯 श्रीगुरु करिअर अकॅडमी - टेस्ट विश्लेषण</h2>
    <p style="text-align:center; color:#64748b; font-size:13px;">विद्यार्थ्याचे नाव: <b>{{ lead.student_name }}</b> | जिल्हा: <b>{{ lead.district }}</b> | टेस्ट: <b>{{ lead.test_name }}</b></p>
    
    <div class="score-card">
        <h3 style="margin:0; color:#166534; font-size:22px;">प्राप्त गुण: {{ lead.score }} / {{ lead.total_marks }}</h3>
    </div>

    <h3>📋 प्रश्न व स्पष्टीकरण तक्ता:</h3>
    {% for item in review_data %}
    <div class="q-box">
        <div style="font-weight:bold; font-size:15px; margin-bottom:8px;">प्र. {{ loop.index }}. {{ item.question }}</div>
        <div style="font-size:13px; color:#334155; margin-bottom:8px;">
            A) {{ item.opt_a }}<br>B) {{ item.opt_b }}<br>C) {{ item.opt_c }}<br>D) {{ item.opt_d }}
        </div>
        <div>
            <span style="font-size:12px; font-weight:bold;">तुमचे उत्तर: </span>
            <span class="ans-tag {{ 'correct-ans' if item.is_correct else 'wrong-ans' }}">{{ item.user_ans or 'सोडवले नाही' }}</span>
            &nbsp;|&nbsp;
            <span style="font-size:12px; font-weight:bold;">अचूक उत्तर: </span>
            <span class="ans-tag correct-ans">{{ item.correct }}</span>
        </div>
        {% if item.explanation %}
        <div class="exp-box"><b>💡 स्पष्टीकरण:</b> {{ item.explanation }}</div>
        {% endif %}
    </div>
    {% endfor %}
    <div style="text-align:center; margin-top:25px;">
        <a href="/test" style="background:#0284c7; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold;">🔄 नवीन टेस्ट पेजवर जा</a>
    </div>
</div>
</body>
</html>'''

# ----------------- SECURE PUBLIC TEST TEMPLATE -----------------
MOCK_TEST_HTML = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>महाराष्ट्र पोलीस भरती - मोफत / सशुल्क ऑनलाइन सराव टेस्ट</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f1f5f9; color: #1e293b; padding: 15px; }
        .box { max-width: 650px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 5px solid #0284c7; }
        h2 { margin: 0 0 5px; color: #0b2545; text-align: center; }
        .q-item { margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #e2e8f0; }
        .q-text { font-weight: bold; margin-bottom: 8px; font-size: 15px; color: #0f172a; }
        .opt-label { display: block; margin-bottom: 6px; font-size: 14px; cursor: pointer; }
        input[type="text"], input[type="tel"], select { width: 100%; padding: 9px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-bottom: 10px; }
        .btn-submit { width: 100%; background: #059669; color: white; padding: 12px; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .cert-box { border: 4px double #b45309; padding: 25px; border-radius: 10px; background: #fffbeb; text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
<div class="box">
    <h2>🎯 श्रीगुरु राज्यस्तरीय महासराव टेस्ट</h2>
    <p style="text-align:center; color:#64748b; font-size:13px; margin-bottom:10px;">पोलीस व सैन्य भरती विशेष सराव परीक्षा</p>

    {% if not launched %}
    <div style="background:#fef2f2; border:2px solid #f87171; border-radius:8px; padding:25px; text-align:center;">
        <h3 style="margin:0 0 10px; color:#991b1b;">⚠️ टेस्ट सध्या बंद आहे!</h3>
        <p style="color:#475569; font-size:15px; line-height:1.6;">श्रीगुरु करिअर अकॅडमीतर्फे नवीन सराव टेस्ट लवकरच लॉन्च केली जाईल.</p>
    </div>
    {% elif step == 'start' %}
    <div style="background:#f8fafc; padding:20px; border-radius:8px; border:1px solid #cbd5e1;">
        <form method="GET" action="/test" style="margin-bottom:15px;">
            <label style="font-weight:bold; font-size:13px; color:#5b21b6;">📚 सोडवण्यासाठी टेस्ट पेपर निवडा *:</label>
            <select name="test_id" onchange="this.form.submit()" style="font-weight:bold; background:#faf5ff;">
                {% for tp in all_test_papers %}
                <option value="{{ tp.id }}" {% if tp.id == current_test_id %}selected{% endif %}>{{ tp.test_title }} (फी: ₹{{ tp.test_fee }})</option>
                {% endfor %}
            </select>
        </form>

        {% if current_test_fee|int > 0 %}
        <div style="background:#fefce8; border:2px solid #facc15; padding:15px; border-radius:8px; text-align:center; margin-bottom:15px;">
            <b style="color:#854d0e; font-size:16px;">💰 या टेस्टची परीक्षा फी: ₹{{ current_test_fee }}</b><br>
            <img src="{{ qr_image_url }}" alt="QR Code" width="160" height="160" style="border:1px solid #ccc; border-radius:6px; background:white; padding:4px;"><br>
            <span style="font-size:13px; font-weight:bold;">UPI ID: {{ upi_id }}</span>
        </div>
        {% else %}
        <div style="background:#f0fdf4; border:1px solid #86efac; padding:10px; border-radius:6px; text-align:center; font-size:13px; color:#166534; margin-bottom:15px; font-weight:bold;">
            ✨ ही टेस्ट पूर्णपणे **मोफत (Free)** आहे!
        </div>
        {% endif %}

        {% if error_msg %}
        <div style="background:#fee2e2; color:#991b1b; padding:8px; border-radius:4px; font-size:13px; font-weight:bold; margin-bottom:10px;">{{ error_msg }}</div>
        {% endif %}

        <form method="POST" action="/test">
            <input type="hidden" name="action_type" value="unlock_test">
            <input type="hidden" name="test_id" value="{{ current_test_id }}">
            <label style="font-weight:bold; font-size:13px;">विद्यार्थ्याचे पूर्ण नाव *:</label>
            <input type="text" name="student_name" placeholder="उदा. राहुल पाटील" required>
            <label style="font-weight:bold; font-size:13px;">जिल्हा *:</label>
            <input type="text" name="district" placeholder="उदा. कोल्हापूर" required>
            {% if current_test_fee|int > 0 %}
            <label style="font-weight:bold; font-size:13px;">UPI ट्रान्झॅक्शन नंबर (Ref No) *:</label>
            <input type="text" name="upi_ref" placeholder="उदा. 4235xxxxxxxx" required>
            {% endif %}
            <button type="submit" class="btn-submit" style="background:#0284c7; margin-top:10px;">🔓 प्रश्नपत्रिका ओपन करा व टेस्ट सोडवा</button>
        </form>
    </div>

    {% elif step == 'exam' %}
    <div style="background:#f0fdf4; border:1px solid #bbf7d0; padding:10px; border-radius:6px; margin-bottom:15px; font-size:13px; color:#166534; display:flex; justify-content:space-between; align-items:center;">
        <div>👤 सोडवणारे विद्यार्थी: <b>{{ session.get('exam_name') }}</b> | टेस्ट: <b>{{ current_test_title }}</b></div>
        <a href="/test" style="color:red; font-size:11px; text-decoration:none; font-weight:bold;">[ रद्द् करा ]</a>
    </div>

    <form method="POST" action="/test">
        <input type="hidden" name="action_type" value="submit_test">
        <input type="hidden" name="test_id" value="{{ current_test_id }}">
        {% for q in questions %}
        <div class="q-item">
            <div class="q-text">प्र. {{ loop.index }}. {{ q.question }}</div>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="A" required> A) {{ q.opt_a }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="B"> B) {{ q.opt_b }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="C"> C) {{ q.opt_c }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="D"> D) {{ q.opt_d }}</label>
        </div>
        {% endfor %}
        <button type="submit" class="btn-submit">✅ टेस्ट सबमिट करा व प्रशस्तीपत्र पहा</button>
    </form>

    {% elif submitted %}
    <div style="background:#f0fdf4; border:2px solid #86efac; border-radius:8px; padding:20px; text-align:center; margin-bottom:20px;">
        <h3 style="margin:0 0 5px; color:#166534;">टेस्ट यशस्वीरीत्या पूर्ण झाली आहे! 🎉</h3>
        <p style="color:#475569; font-size:14px;">खाली तुमचे डिजिटल प्रशस्तीपत्र दिले आहे.</p>
    </div>

    <div class="cert-box">
        <h3 style="margin:0; color:#b45309; font-size:20px;">🏆 डिजिटल प्रशस्तीपत्र (Certificate of Participation)</h3>
        <p style="font-size:12px; color:#78350f; margin:5px 0 15px;">श्रीगुरु करिअर अकॅडमी, आडूर (ता. करवीर, जि. कोल्हापूर)</p>
        <hr style="border:1px solid #fde68a; margin:10px 0;">
        <p style="font-size:14px; color:#1e293b; line-height:1.6;">
            प्रमाणपत्र देण्यात येते की, श्री/सौ/कुमार <b>{{ name }}</b> (जिल्हा: {{ district }}) यांनी श्रीगुरु करिअर अकॅडमीतर्फे आयोजित <b>{{ current_test_title }}</b> मध्ये सहभाग घेऊन <b>{{ score }} / {{ total }}</b> गुण प्राप्त केले आहेत.
        </p>
        <p style="font-size:13px; color:#92400e; font-weight:bold; margin-top:15px; line-height:1.5;">
            मा. सचिन चौगले सर तसेच श्रीगुरु करिअर अकॅडमी परिवारातर्फे हार्दिक अभिनंदन! आपले ध्येय निश्चितच पूर्ण होवो. 🌟
        </p>
        <div style="margin-top:20px; display:flex; justify-content:space-between; font-size:12px; font-weight:bold; color:#78350f;">
            <div>दिनांक: {{ today_date }}</div>
            <div>संचालक / मार्गदर्शक<br>मा. सचिन चौगले सर व परिवार<br>श्रीगुरु करिअर अकॅडमी, आडूर</div>
        </div>
    </div>

    <!-- WhatsApp Number Box -->
    <div style="background:#fffbeb; border:2px dashed #f59e0b; padding:20px; border-radius:8px; margin-top:20px; text-align:center;">
        <h4 style="margin-top:0; color:#b45309; font-size:16px;">📊 तुमचे गुण व स्पष्टीकरण लिंक हवी का?</h4>
        <form method="POST" action="/test">
            <input type="hidden" name="action_type" value="send_whatsapp_score">
            <input type="hidden" name="saved_name" value="{{ name }}">
            <input type="hidden" name="saved_district" value="{{ district }}">
            <input type="hidden" name="saved_score" value="{{ score }}">
            <input type="hidden" name="saved_total" value="{{ total }}">
            <input type="hidden" name="saved_upi_ref" value="{{ upi_ref }}">
            <input type="hidden" name="saved_test_name" value="{{ current_test_title }}">
            <input type="tel" name="whatsapp_phone" placeholder="१० अंकी WhatsApp नंबर" pattern="[6-9][0-9]{9}" required style="max-width:300px; margin:0 auto 10px; display:block; text-align:center; font-weight:bold;">
            <button type="submit" style="background:#25D366; color:white; border:none; padding:10px 20px; border-radius:6px; font-weight:bold; cursor:pointer;">📲 WhatsApp वर निकाल व रिव्ह्यू लिंक मिळवा</button>
        </form>
    </div>
    <br><div style="text-align:center;"><a href="/test" style="color:#0284c7; font-weight:bold; text-decoration:none;">🔄 नवीन टेस्ट सोडवा</a></div>

    {% elif step == 'whatsapp_sent' %}
    <div style="background:#f0fdf4; border:2px solid #86efac; border-radius:8px; padding:25px; text-align:center;">
        <h3 style="margin:0 0 10px; color:#166534;">निकालाची लिंक तयार आहे! 🎉</h3>
        <a href="{{ wa_link }}" target="_blank" style="display:inline-block; background:#25D366; color:white; padding:12px 25px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:15px;">📲 WhatsApp वर निकाल उघडा व पाठवा</a>
        <br><br><div style="margin-top:15px;"><a href="/test" style="color:#0284c7; font-weight:bold; text-decoration:none;">🔄 नवीन टेस्ट सोडवा</a></div>
    </div>
    {% endif %}
</div>
</body>
</html>'''

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
        p.sub { margin: 0 0 20px; text-align: center; font-size: 13px; color: #64748b; line-height: 1.5; }
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
            <div><label>जिल्हा *:</label><input type="text" name="district" placeholder="कोल्हापूर" required></div>
            <div><label>तालुका:</label><input type="text" name="taluka" placeholder="करवीर"></div>
        </div>
        <label>व्हॉट्सॲप / संपर्क मोबाईल *:</label>
        <input type="tel" name="phone" placeholder="१० अंकी मोबाईल" pattern="[0-9]{10}" required>
        <button type="submit" class="btn-submit">📲 नोंदणी करा</button>
    </form>
</div>
</body>
</html>'''

# ----------------- FLASK ROUTING & CONTROLLERS -----------------
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
            error = "चुकीचा पासवर्ड!"
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
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students")
            students = cur.fetchall()
            cur.execute("SELECT * FROM mess_diet")
            diet_list = cur.fetchall()
            cur.execute("SELECT * FROM canteen_staff_list")
            canteen_staff = cur.fetchall()
            cur.execute("SELECT * FROM staff_tasks ORDER BY id DESC")
            staff_tasks = cur.fetchall()
            cur.execute("SELECT * FROM staff_requests WHERE req_role='Manager' ORDER BY id DESC")
            my_requests = cur.fetchall()
            cur.execute("SELECT pt.*, s.name, s.course FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC")
            physical_records = cur.fetchall()
            cur.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC")
            written_records = cur.fetchall()
    return render_template_string(MANAGER_LAYOUT, curr_tab=curr_tab, students=students, diet_list=diet_list, canteen_staff=canteen_staff, staff_tasks=staff_tasks, my_requests=my_requests, physical_records=physical_records, written_records=written_records, today_date=today_date, lang=lang, grocery_items=GROCERY_MASTER_500)

@app.route('/trainer')
def trainer_view():
    if session.get('user_role') != 'Trainer': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'practice')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students")
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

@app.route('/clerk')
def clerk_view():
    if session.get('user_role') != 'Clerk': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'stud')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students")
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
    return render_template_string(CLERK_LAYOUT, curr_tab=curr_tab, students=students, staff_tasks=staff_tasks, expenses_list=expenses_list, kit_logs=kit_logs, my_requests=my_requests, hostel_logs=hostel_logs, physical_records=physical_records, written_records=written_records, today_date=today_date, lang=lang, grocery_items=GROCERY_MASTER_500)

@app.route('/toggle_test_launch', methods=['POST'])
def toggle_test_launch():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='test_launched'")
            res = cur.fetchone()
            current = res['value'] if res else 'no'
            new_val = 'no' if current == 'yes' else 'yes'
            cur.execute("UPDATE settings SET value=%s WHERE key='test_launched'", (new_val,))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/update_test_settings', methods=['POST'])
def update_test_settings():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    upi = request.form.get('upi_id', '9921111960@ybl')
    qr = request.form.get('qr_image_url', '')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE settings SET value=%s WHERE key='upi_id'", (upi,))
            cur.execute("UPDATE settings SET value=%s WHERE key='qr_image_url'", (qr,))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/add_test_paper', methods=['POST'])
def add_test_paper():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    title = request.form.get('test_title')
    fee = safe_float(request.form.get('test_fee', 0))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_papers (test_title, test_fee) VALUES (%s, %s)", (title, fee))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/delete_test_paper/<int:id>')
def delete_test_paper(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    if id == 1: return "Default test cannot be deleted", 400
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM questions WHERE test_id=%s", (id,))
            cur.execute("DELETE FROM test_papers WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/approve_payment/<int:id>')
def approve_payment(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET payment_status='Approved' WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=payments')

@app.route('/update_student_validity/<int:id>', methods=['POST'])
def update_student_validity(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    valid_till = request.form.get('valid_till', '')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE mock_test_leads SET valid_till=%s, payment_status='Approved' WHERE id=%s", (valid_till, id))
            conn.commit()
    return redirect('/admin?tab=payments')

@app.route('/delete_test_lead/<int:id>')
def delete_test_lead(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mock_test_leads WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=payments')

@app.route('/delete_inquiry/<int:id>')
def delete_inquiry(id):
    if session.get('user_role') not in ['Admin', 'Clerk', 'Manager']: return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admission_inquiries WHERE id=%s", (id,))
            conn.commit()
    return redirect('/inquiries')

@app.route('/add_single_question', methods=['POST'])
def add_single_question():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    test_id = safe_int(request.form.get('test_id', 1), 1)
    q = request.form.get('question')
    a = request.form.get('opt_a')
    b = request.form.get('opt_b')
    c = request.form.get('opt_c')
    d = request.form.get('opt_d')
    corr = request.form.get('correct')
    expl = request.form.get('explanation', '')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", 
                        (test_id, q, a, b, c, d, corr, expl))
            conn.commit()
    return redirect(f'/admin?tab=questions&test_id={test_id}')

@app.route('/add_bulk_questions', methods=['POST'])
def add_bulk_questions():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    test_id = safe_int(request.form.get('test_id', 1), 1)
    text = request.form.get('bulk_text', '')
    lines = text.strip().split('\n')
    with get_db() as conn:
        with conn.cursor() as cur:
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 6:
                    expl = parts[6] if len(parts) > 6 else ''
                    cur.execute("INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", 
                                (test_id, parts[0], parts[1], parts[2], parts[3], parts[4], parts[5].upper(), expl))
            conn.commit()
    return redirect(f'/admin?tab=questions&test_id={test_id}')

@app.route('/delete_question/<int:id>')
def delete_question(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT test_id FROM questions WHERE id=%s", (id,))
            res = cur.fetchone()
            t_id = res['test_id'] if res else 1
            cur.execute("DELETE FROM questions WHERE id=%s", (id,))
            conn.commit()
    return redirect(f'/admin?tab=questions&test_id={t_id}')

@app.route('/inquiry', methods=['GET', 'POST'])
def public_inquiry():
    msg = None
    if request.method == 'POST':
        s_name = request.form.get('student_name')
        dist = request.form.get('district')
        tal = request.form.get('taluka', '')
        phone = request.form.get('phone')
        course = request.form.get('course', 'पोलीस भरती')
        hostel = request.form.get('hostel_interest', 'होय')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO admission_inquiries (inquiry_date, student_name, district, taluka, phone, course, hostel_interest) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                            (date.today().strftime("%Y-%m-%d"), s_name, dist, tal, phone, course, hostel))
                conn.commit()
        msg = "नोंदणी यशस्वी झाली!"
    return render_template_string(PUBLIC_INQUIRY_HTML, msg=msg)

@app.route('/print_grocery_slip', methods=['POST'])
def print_grocery_slip():
    items = request.form.getlist('items')
    rows = "".join([f"<tr><td style='padding:8px; border:1px solid #333; text-align:center;'>{loop_idx+1}</td><td style='padding:8px; border:1px solid #333; font-weight:600;'>{itm}</td><td style='padding:8px; border:1px solid #333;'>{request.form.get('qty_'+itm, 'लागेल तेवढे')}</td><td style='padding:8px; border:1px solid #333; text-align:center;'>[  ]</td></tr>" for loop_idx, itm in enumerate(items)])
    html = f'''<!DOCTYPE html><html><head><title>कॅन्टीन व मेस खरेदी पावती</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; padding: 15px; color: #1e293b; font-size: 11px; }}
        h2 {{ margin: 0; color: #065f46; font-size: 18px; text-align: center; }}
        p {{ margin: 2px 0 10px; font-size: 10px; text-align: center; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 11px; }}
        th, td {{ border: 1px solid #333; padding: 3px 6px; }}
        th {{ background: #065f46; color: white; font-size: 11px; }}
    </style></head>
    <body>
        <div style="max-width: 100%; margin: auto;">
            <h2>श्रीगुरु करिअर अकॅडमी (मेस व कॅन्टीन विभाग)</h2>
            <p>आडूर, ता. करवीर, जि. कोल्हापूर | संपर्क: ९९२११११९६०</p>
            <div style="display:flex; justify-content:space-between; margin-bottom:5px; font-weight:bold; font-size:11px;">
                <div>दिनांक: {date.today().strftime('%d/%m/%Y')}</div>
                <div>निवडलेले साहित्य एकूण: {len(items)}</div>
            </div>
            <table>
                <thead>
                    <tr><th style="width:40px;">क्र.</th><th>साहित्याचे नाव (कॅन्टीन व मेस मास्टर यादी)</th><th style="width:110px;">प्रमाण / वजन</th><th style="width:60px; text-align:center;">तपासले</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <div style="margin-top:25px; display:flex; justify-content:space-between; font-size:11px; font-weight:bold;">
                <div>व्यवस्थापक / क्लार्क सही</div>
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

