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
app.secret_key = "shreeguru_complete_bulletproof_v80_full_2600_lines_master"

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
    "कांदा पोहे", "बटाटा पोहे", "मटार पोहे", "रवा उपमा", "शेवया उपमा",
    "मूग डाळ खिचडी", "मसाला तांदूळ भात", "साबुदाणा खिचडी", "साबुदाणा वडा", "बटाटा भजी",
    "कांदा भजी (पकोडा)", "पालक भजी", "मिरची भजी", "ब्रेड पकोडा", "वडा पाव",
    "मिसळ पाव", "मटकी भेळ", "उसाळ पाव", "पोहे-तर्री", "इडली-सांबर",
    "मेदू वडा-सांबर", "उत्तप्पा", "प्लेन डोसा", "मसाला डोसा", "चीज डोसा",
    "बटर डोसा", "रवा डोसा", "पुरी भाजी", "चपाती भाजी", "आलू पराठा",
    "मेथी पराठा", "गोबी पराठा", "पनीर पराठा", "मुळा पराठा", "थालिपिथ",
    "बेसन धिरडे", "मूग डाळ धिरडे", "तांदळाचे घावणे", "आंबोळी", "रवा आप्पे",
    "अळू वडी (पात्रा)", "कोथिंबीर वडी", "थालीपीठ भाजणी", "उपवासाची थालिपिथ", "मक्का लाटलेली रोटी",
    "व्हेज सँडविच", "ग्रील सँडविच", "मॅगी नूडल्स", "व्हाइट सॉस पास्ता", "रेड सॉस पास्ता",
    "साधी मऊ चपाती", "फुलकी चपाती", "तेल घातलेली चपाती", "रुमाली रोटी", "तंदूरी रोटी",
    "बटर नान", "लसूणी नान", "मिस्सी रोटी", "ज्वारीची भाकरी", "बाजरीची भाकरी",
    "नाचणीची भाकरी", "मक्याची भाकरी", "तांदळाची भाकरी (अभाकरी)", "सादा पांढरा भात", "जिरा राइस",
    "घी जिरा राइस", "मटर पुलाव", "व्हेज पुलाव", "काश्मिरी पुलाव", "व्हेज बिर्याणी",
    "दम बिर्याणी", "तडका खिचडी", "डाळ खिचडी", "मसाला भात", "वांगी भात",
    "टोमॅटो भात", "पुदिना भात", "कोथिंबीर भात", "लेमन राइस", "दही भात (कर्ड राइस)",
    "मेथी भात", "पालक भात", "शाही पुलाव", "पनीर पुलाव", "कॉर्न राइस",
    "शेजवान फ्राईड राइस", "चायनीज फ्राईड राइस", "हक्का नूडल्स", "मंचुरियन राइस", "टोमॅटो सूप",
    "स्वीट कॉर्न सूप", "हॉट अँड सोअर सूप", "व्हेज मंचाऊ सूप", "डाळ फ्राय", "डाळ तडका",
    "कोल्हापुरी पांढरा रस्सा", "कोल्हापुरी तांबडा रस्सा", "झुणका (पिठलं)", "शेवगा भाजी", "मटकी उसळ",
    "मूग उसळ", "चवळी उसळ", "मटार उसळ", "पालक पनीर", "कढई पनीर",
    "शही पनीर", "मटर पनीर", "राजमा मसाला", "छोले मसाला", "दम आलू",
    "भेंडी मसाला", "सेम भाजी", "गवार भाजी", "कोबी मटार भाजी", "फ्लॉवर बटाटा भाजी",
    "सिमला मिरची बेसन", "दुधी चणा डाळ भाजी", "कारले फ्राय", "पडवळ भाजी", "तोंडली भाजी",
    "पालेभाजी मेथी", "पालक लसूणी", "शेपू भाजी", "अंबाडी भाजी", "चाकवत भाजी",
    "मुळा भाजी", "कढी पकोडा", "सोमवारी स्पेशल भाजी", "मंगळवार स्पेशल भाजी", "बुधवार स्पेशल भाजी",
    "गुरुवार स्पेशल भाजी", "शुक्रवार स्पेशल भाजी", "शनिवार स्पेशल भाजी", "रविवार स्पेशल भाजी", "मेस स्पेशल मिक्स भाजी",
    "आलू जिरा", "आलू मेथी", "आलू पालक", "आलू मटर", "मिक्स व्हेज",
    "कॉर्न पालक", "मेथी मलाई मटर", "मालवणी उसळ", "खास कोल्हापुरी उसळ", "विशेष पालेभाजी आमटी",
    "पुरणपोळी", "गुळाची पोळी", "श्रीखंड", "आम्रखंड", "बासुंदी",
    "रसमलाई", "गुलाब जामुन", "काजू कतली", "बेसन लाडू", "रवा लाडू",
    "मुगाचा हलवा", "गाजर हलवा", "दुधी भोपळा हलवा", "शेवया खीर", "तांदळाची खीर",
    "साबुदाणा खीर", "पाकातली जिलेबी", "इम्रती", "उकडीचे मोदक", "तळलेले मोदक",
    "करंजी", "शकरपाळे", "अनारसे", "दाल ढोकळी (चकोल्या)", "बासुंदी पुरी",
    "मलाई बर्फी", "चॉकलेट बर्फी", "पेढे", "कलकंद", "रसबिहारी",
    "व्हॅनिला आईस्क्रीम", "चॉकलेट आईस्क्रीम", "स्ट्रॉबेरी आईस्क्रीम", "कस्टर्ड फ्रूट सॅलड", "जेली कस्टर्ड",
    "मैसूर पाक", "जलेबी रबडी", "रसमलाई केक", "शाही टुकडा", "गुलाब जामुन विथ आईस्क्रीम",
    "ड्राईफ्रूट खीर", "अंजीर हलवा", "बादाम हलवा", "आटवलेले दूध", "खव्याची बर्फी",
    "नारळी भात", "मोतीचूर लाडू", "बेसन बर्फी", "कोकोनट बर्फी", "स्पेशल पुरणपोळी थाळी",
    "जाड पोहे (बल्क साठा)", "पातळ पोहे (बल्क)", "रवा बारीक (बल्क)", "रवा मोठा (बल्क)", "मैदा (बल्क साठा)",
    "बेसन पीठ (बल्क)", "गहू पीठ (आटा बोरा)", "ज्वारी पीठ (बल्क)", "बाजरी पीठ (बल्क)", "साबुदाणा (बल्क)",
    "शेंगदाणा तेल (डबा)", "सोयाबीन तेल (डबा)", "सूर्यफूल तेल (डबा)", "शुद्ध साजूक तूप (डबा)", "वनस्पती तूप (डबा)",
    "ताजे दूध (कॅन/पॅकेट)", "दही (मोठे कमर्शियल टब)", "छास / ताक (पॅकेट्स)", "पनीर (बल्क ब्लॉक)", "खवा / मावा (बल्क)",
    "अंडी (मोठे ट्रे)", "सोयाबीन वड्या (बल्क)", "मोड आलेले मूग (बल्क)", "मोड आलेली मटकी (बल्क)", "ओट्स (बल्क पॅक)",
    "डिशवॉश लिक्विड (कॅन)", "डिशवॉश बार (साबण)", "स्टील स्क्रबर जाळी", "घासणीचा ब्रश", "फ्लॉवर क्लिनर (फिनाइल)",
    "टॉयलेट क्लिनर (हार्पिक)", "काच पुसण्याचा लिक्विड", "हॅन्ड वॉश लिक्विड रिफिल", "नॅप्थालीन गोळ्या", "कचऱ्याच्या मोठ्या पिशव्या"
]

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

# ----------------- ADMIN DASHBOARD LAYOUT -----------------
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
        input, select, textarea { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; }
        .btn-act { padding: 4px 7px; border-radius: 3px; color: white; text-decoration: none; font-size: 11px; font-weight: bold; display: inline-block; cursor: pointer; border: none; }
        .btn-del { background: #dc2626; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 11px; display: inline-block; }
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
    <a href="/inquiries" class="menu-btn" style="background:#b45309; border:2px solid #fde047;">📞 चौकशी व टेस्ट डेस्क</a>
    <a href="/admin?tab=payments" class="menu-btn {% if curr_tab == 'payments' %}active{% endif %}" style="background:#059669; border:2px solid #ffdd59;">💳 पेमेंट व वैधता डेस्क</a>
    <a href="/admin?tab=questions" class="menu-btn {% if curr_tab == 'questions' %}active{% endif %}" style="background:#7c3aed; border:2px solid #fde047;">❓ प्रश्न व्यवस्थापन व लॉन्च</a>
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

    {% if curr_tab == 'payments' %}
    <div class="admin-tab">
        <h3 style="color:#059669; margin-top:0;">💳 पेमेंट व विद्यार्थी वैधता (Validity) अप्रूवल डेस्क</h3>
        <table>
            <thead><tr><th>तारीख</th><th>विद्यार्थ्याचे नाव</th><th>जिल्हा</th><th>मोबाईल</th><th>टेस्ट नाव</th><th>गुण</th><th>UPI Ref No</th><th>स्थिती</th><th>वैधता (Valid Till)</th><th>कृती</th></tr></thead>
            <tbody>
                {% for p in pending_payments %}
                <tr>
                    <td>{{ p.test_date }}</td>
                    <td><b>{{ p.student_name }}</b></td>
                    <td>{{ p.district }}</td>
                    <td>{{ p.phone }}</td>
                    <td>{{ p.test_name }}</td>
                    <td><b>{{ p.score }} / {{ p.total_marks }}</b></td>
                    <td><code>{{ p.upi_ref }}</code></td>
                    <td><b style="color:{{ 'green' if p.payment_status=='Approved' else 'orange' }};">{{ p.payment_status }}</b></td>
                    <td>
                        <form action="/update_student_validity/{{ p.id }}" method="POST" style="display:flex; gap:4px;">
                            <input type="date" name="valid_till" value="{{ p.valid_till or '' }}" style="padding:3px;">
                            <button type="submit" class="btn-act" style="background:#0284c7;">💾</button>
                        </form>
                    </td>
                    <td>
                        {% if p.payment_status != 'Approved' %}
                        <a href="/approve_payment/{{ p.id }}" class="btn-act" style="background:#16a34a;">✅ अप्रूव</a>
                        {% endif %}
                        <a href="/delete_test_lead/{{ p.id }}" onclick="return confirm('हटवायचे?')" class="btn-del">🗑️️</a>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="10" style="text-align:center;">कोणतेही पेमेंट्स प्रलंबित नाहीत.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'questions' %}
    <div class="admin-tab">
        <h3 style="color:#7c3aed; margin-top:0;">❓ प्रश्न व्यवस्थापन व लॉन्च कंट्रोल (Multiple Test Papers)</h3>
        
        <div style="background:#faf5ff; border:2px solid #7c3aed; padding:15px; border-radius:8px; margin-bottom:20px;">
            <h4 style="margin:0 0 10px; color:#5b21b6;">📚 नवीन टेस्ट पेपर तयार करा:</h4>
            <form action="/add_test_paper" method="POST" style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:15px;">
                <input type="text" name="test_title" placeholder="टेस्टचे नाव (उदा. पोलीस भरती स्पेशल गणित टेस्ट)" required style="flex:2; min-width:250px;">
                <input type="number" name="test_fee" placeholder="फी (₹)" min="0" value="0" required style="width:100px;">
                <button type="submit" class="btn-act" style="background:#7c3aed; padding:8px 15px;">+ नवीन टेस्ट जोडा</button>
            </form>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
                {% for tp in all_test_papers %}
                <div style="background:white; border:1px solid #d8b4fe; padding:8px 12px; border-radius:6px; display:flex; align-items:center; gap:10px;">
                    <div><b>{{ tp.test_title }}</b> (फी: ₹{{ tp.test_fee }})</div>
                    <a href="/admin?tab=questions&test_id={{ tp.id }}" class="btn-act" style="background:{{ '#16a34a' if current_test_id == tp.id else '#0284c7' }};">
                        {{ '🟢 निवडली' if current_test_id == tp.id else '✏️ पहा' }}
                    </a>
                    {% if tp.id != 1 %}
                    <a href="/delete_test_paper/{{ tp.id }}" onclick="return confirm('हा टेस्ट पेपर व त्यातील सर्व प्रश्न डिलीट करायचे?')" style="color:red; font-weight:bold; text-decoration:none;">🗑️</a>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>

        <div style="background:#f0fdf4; border:2px solid #15803d; padding:15px; border-radius:8px; margin-bottom:20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:15px;">
                <div>
                    <b style="color:#166534;">🚀 ऑनलाईन लॉन्च व पेमेंट सेटिंग्ज:</b> वर्तमान टेस्ट: <b style="color:#7c3aed;">{{ current_test_title }}</b>
                </div>
                <div>
                    <form action="/toggle_test_launch" method="POST" style="display:inline;">
                        {% if test_launched == 'yes' %}
                        <button type="submit" class="btn-act" style="background:#dc2626; padding:8px 14px;">🔴 टेस्ट बंद करा</button>
                        {% else %}
                        <button type="submit" class="btn-act" style="background:#16a34a; padding:8px 14px;">🟢 टेस्ट लाईव्ह करा</button>
                        {% endif %}
                    </form>
                    <a href="/test" target="_blank" class="btn-act" style="background:#0284c7; padding:8px 14px; margin-left:5px;">🌐 टेस्ट पेज पहा</a>
                </div>
            </div>
            <form action="/update_test_settings" method="POST" style="background:white; padding:12px; border-radius:6px; border:1px solid #bbf7d0;">
                UPI ID: <input type="text" name="upi_id" value="{{ upi_id }}" required style="width:250px;">
                QR Image URL: <input type="text" name="qr_image_url" value="{{ qr_image_url }}" required style="width:350px;">
                <button type="submit" class="btn-act" style="background:#15803d;">💾 सेव्ह करा</button>
            </form>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
                <h4 style="margin-top:0; color:#0b3c5d;">१. नवीन प्रश्न व स्पष्टीकरण जोडा:</h4>
                <form action="/add_single_question" method="POST">
                    <input type="hidden" name="test_id" value="{{ current_test_id }}">
                    <label>प्रश्न:</label>
                    <textarea name="question" required style="width:100%; height:50px;"></textarea>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:8px;">
                        <div>A: <input type="text" name="opt_a" required style="width:100%;"></div>
                        <div>B: <input type="text" name="opt_b" required style="width:100%;"></div>
                        <div>C: <input type="text" name="opt_c" required style="width:100%;"></div>
                        <div>D: <input type="text" name="opt_d" required style="width:100%;"></div>
                    </div><br>
                    <label>अचूक पर्याय:</label>
                    <select name="correct" style="width:100%;"><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select>
                    <label style="margin-top:8px; display:block;">स्पष्टीकरण (Explanation):</label>
                    <textarea name="explanation" style="width:100%; height:40px;"></textarea><br>
                    <button type="submit" class="btn-act" style="background:#7c3aed; width:100%; margin-top:8px;">+ प्रश्न सेव्ह करा</button>
                </form>
            </div>

            <div style="background:#f0fdf4; padding:15px; border-radius:6px; border:1px solid #bbf7d0;">
                <h4 style="margin-top:0; color:#15803d;">२. बल्क प्रश्न अपलोड:</h4>
                <form action="/add_bulk_questions" method="POST">
                    <input type="hidden" name="test_id" value="{{ current_test_id }}">
                    <textarea name="bulk_text" rows="6" placeholder="प्रश्न | पर्यायA | पर्यायB | पर्यायC | पर्यायD | अचूक | स्पष्टीकरण" style="width:100%;" required></textarea><br>
                    <button type="submit" class="btn-act" style="background:#15803d; width:100%; margin-top:5px;">📥 बल्क अपलोड करा</button>
                </form>
            </div>
        </div>

        <h4 style="margin-top:25px;">📋 प्रश्न यादी ({{ questions|length }} प्रश्न):</h4>
        <table>
            <thead><tr><th>क्र.</th><th>प्रश्न व स्पष्टीकरण</th><th>पर्याय</th><th>अचूक</th><th>कृती</th></tr></thead>
            <tbody>
                {% for q in questions %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td><b>{{ q.question }}</b><br>{% if q.explanation %}<span style="color:green; font-size:11px;">💡 {{ q.explanation }}</span>{% endif %}</td>
                    <td>A) {{ q.opt_a }}<br>B) {{ q.opt_b }}<br>C) {{ q.opt_c }}<br>D) {{ q.opt_d }}</td>
                    <td><b style="color:green;">{{ q.correct }}</b></td>
                    <td><a href="/delete_question/{{ q.id }}" onclick="return confirm('हटवायचे?')" class="btn-del">🗑️</a></td>
                </tr>
                {% else %}
                <tr><td colspan="5" style="text-align:center;">कोणतेही प्रश्न नाहीत.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

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
                        <a href="/receipt/{{ s.id }}" target="_blank" class="btn-act" style="background:#10b981;">🧾 पावती प्रिंट</a>
                        <a href="/student_report/{{ s.id }}" target="_blank" class="btn-act" style="background:#6366f1; color:white; text-decoration:none; padding:4px 8px; border-radius:4px; font-weight:bold; margin-left:5px;">📋 स्टुडन्ट रिपोर्ट</a> 
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
                <tr><td>{{ pt.test_date }}</td><td><b>{{ pt.name }}</b></td><td>{{ pt.course }}</td><td>{{ pt.run_time }}</td><td>{{ pt.sprint_time }}</td><td>{{ pt.shot_put_dist }}</td><td>{{ pt.pullups }}</td><td><b style="color:green;">{{ pt.total_obtained }}/50</b></td><td><a href="/delete_physical_record/{{ pt.id }}" onclick="return confirm('हटवायचे?')" style="color:red;">🗑️️</a></td></tr>
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
        <div style="background:#f8fafc; padding:15px; border:1px solid #cbd5e1; border-radius:6px;">
            <h4 style="margin:0 0 10px; color:#2563eb;">क्लाउड डेटाबेस (Neon PostgreSQL) कार्यरत आहे. तुमचा सर्व डेटा क्लाउडवर सुरक्षितपणे सेव्ह होत आहे.</h4>
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

# ----------------- PUBLIC ADMISSION & TEST ROUTES -----------------
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
        .banner { background: #eff6ff; border: 1px dashed #3b82f6; padding: 10px; border-radius: 6px; font-size: 12px; text-align: center; margin-bottom: 15px; color: #1e40af; }
    </style>
</head>
<body>
<div class="card">
    <h2>⚔️ श्रीगुरु करिअर अकॅडमी, आडूर</h2>
    <p class="sub">पोलीस व सैन्य भरती पूर्व प्रशिक्षण केंद्र (जि. कोल्हापूर)<br><b>मोफत प्रवेश व हॉस्टेल माहिती अर्ज</b></p>
    <div class="banner">✨ फिजिकल ग्राउंड + डिजिटल पॅनेल क्लास + हॉस्टेल व मेस सोय</div>
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

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'students')
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
            cur.execute("SELECT * FROM mess_diet")
            diet_list = cur.fetchall()
            cur.execute("SELECT * FROM staff")
            staff_members = cur.fetchall()
            cur.execute("SELECT * FROM staff_tasks ORDER BY id DESC")
            staff_tasks = cur.fetchall()
            cur.execute("SELECT * FROM staff_requests ORDER BY id DESC")
            all_requests = cur.fetchall()
            cur.execute("SELECT * FROM staff_activity_log ORDER BY id DESC LIMIT 40")
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

# ----------------- INQUIRY & TEST DESK ROUTES -----------------
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
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admission_inquiries (inquiry_date, student_name, district, taluka, phone, course, hostel_interest)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (t_date, s_name, dist, tal, phone, course, hostel))
                conn.commit()
        log_staff_activity("Website", f"नवीन चौकशी अर्ज: {s_name} ({dist} - {course})")
        msg = "तुमची नोंदणी यशस्वी झाली आहे! श्रीगुरु अकॅडमीकडून तुम्हाला लवकरच सविस्तर माहितीचा कॉल येईल."
    return render_template_string(PUBLIC_INQUIRY_HTML, msg=msg)

@app.route('/test', methods=['GET', 'POST'])
def mock_test():
    score = None
    total = 3
    name = ""
    if request.method == 'POST':
        name = request.form.get('student_name')
        dist = request.form.get('district')
        phone = request.form.get('phone')
        
        current_score = 0
        if request.form.get('q1') == 'B': current_score += 1
        if request.form.get('q2') == 'C': current_score += 1
        if request.form.get('q3') == 'B': current_score += 1

        t_date = date.today().strftime("%Y-%m-%d")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mock_test_leads (test_date, student_name, district, phone, score, total_marks, test_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (t_date, name, dist, phone, current_score, total, "पोलीस सराव टेस्ट - १"))
                conn.commit()
        score = current_score

    return render_template_string(MOCK_TEST_HTML, score=score, total=total, name=name)

@app.route('/inquiries')
def inquiry_desk():
    if session.get('user_role') not in ['Admin', 'Clerk', 'Manager']:
        return redirect(url_for('login'))
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM admission_inquiries ORDER BY id DESC")
            inquiries = cur.fetchall()
            cur.execute("SELECT * FROM mock_test_leads ORDER BY id DESC LIMIT 50")
            test_leads = cur.fetchall()
    
    html = '''<!DOCTYPE html>
    <html lang="mr"><head><meta charset="UTF-8"><title>प्रवेश चौकशी व कॉलिंग डेस्क</title>
    <style>
        body { font-family:'Segoe UI',sans-serif; background:#f8fafc; padding:15px; color:#1e293b; margin:0; }
        .header { background:#0b3c5d; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-radius:8px; margin-bottom:20px; }
        table { width:100%; border-collapse:collapse; background:white; font-size:13px; margin-top:10px; border-radius:6px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.1); }
        th, td { border:1px solid #cbd5e1; padding:8px 10px; text-align:left; }
        th { background:#1e293b; color:white; font-weight:600; }
        .btn-wa { background:#25D366; color:white; padding:4px 8px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px; }
        .btn-call { background:#0284c7; color:white; padding:4px 8px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px; margin-right:4px; }
    </style></head><body>

    <div class="header">
        <h3 style="margin:0;">📞 श्रीगुरु ॲडमिशन कॉलिंग डेस्क (एकूण अर्ज: {{ inquiries|length }})</h3>
        <div>
            <a href="/" style="color:white; text-decoration:none; font-weight:bold; margin-right:15px;">🏠 मुख्य डॅशबोर्ड</a>
            <a href="/inquiry" target="_blank" style="color:#fde047; text-decoration:none; font-weight:bold; margin-right:15px;">🌐 प्रवेश अर्ज उघडा</a>
            <a href="/test" target="_blank" style="color:#67e8f9; text-decoration:none; font-weight:bold;">📝 मोफत टेस्ट उघडा</a>
        </div>
    </div>

    <h4 style="color:#0b3c5d; margin:15px 0 5px;">📋 थेट प्रवेश चौकशी अर्ज (Admission Inquiries):</h4>
    <table>
        <thead><tr><th>तारीख</th><th>नाव</th><th>जिल्हा (तालुका)</th><th>कोर्स</th><th>हॉस्टेल</th><th>१-क्लिक संपर्क</th><th>स्थिती / शेरा</th><th>बदल</th></tr></thead>
        <tbody>
            {% for inq in inquiries %}
            <form action="/update_inquiry/{{ inq.id }}" method="POST">
            <tr>
                <td>{{ inq.inquiry_date }}</td>
                <td><b>{{ inq.student_name }}</b></td>
                <td>{{ inq.district }} ({{ inq.taluka or '-' }})</td>
                <td><span style="background:#e0f2fe; padding:2px 6px; border-radius:4px;">{{ inq.course }}</span></td>
                <td>{{ inq.hostel_interest }}</td>
                <td>
                    <a href="tel:{{ inq.phone }}" class="btn-call">📞 कॉल</a>
                    <a href="https://wa.me/91{{ inq.phone }}?text=नमस्कार%20{{ inq.student_name }},%20श्रीगुरु%20करिअर%20अकॅडमी%20आडूर%20मध्ये%20आपली%20चौकशी%20प्राप्त%20झाली.%20नवीन%20बॅचची%20माहिती%20खालीलप्रमाणे:" target="_blank" class="btn-wa">📲 WA</a>
                </td>
                <td>
                    <select name="call_status" style="padding:3px; border-radius:4px; font-size:12px;">
                        <option value="नवीन चौकशी (New)" {% if inq.call_status=='नवीन चौकशी (New)' %}selected{% endif %}>नवीन चौकशी</option>
                        <option value="कॉल झाला - विचारून सांगणार" {% if inq.call_status=='कॉल झाला - विचारून सांगणार' %}selected{% endif %}>विचारून सांगणार</option>
                        <option value="भेट देणार (Visiting)" {% if inq.call_status=='भेट देणार (Visiting)' %}selected{% endif %}>भेट देणार</option>
                        <option value="प्रवेश निश्चित (Admitted)" {% if inq.call_status=='प्रवेश निश्चित (Admitted)' %}selected{% endif %}>प्रवेश निश्चित</option>
                    </select><br>
                    <input type="text" name="staff_note" value="{{ inq.staff_note or '' }}" placeholder="कॉल शेरा..." style="width:90%; margin-top:4px; padding:3px; font-size:12px;">
                </td>
                <td><button type="submit" style="background:#059669; color:white; border:none; padding:5px 8px; border-radius:4px; cursor:pointer;">💾</button></td>
            </tr>
            </form>
            {% else %}
            <tr><td colspan="8" style="text-align:center; color:#64748b;">अद्याप कोणतीही चौकशी आलेली नाही.</td></tr>
            {% endfor %}
        </tbody>
    </table>

    <h4 style="color:#0b3c5d; margin:25px 0 5px;">📝 मोफत ऑनलाइन टेस्ट लीड्स व निकाल (Mock Test Leads):</h4>
    <table>
        <thead><tr><th>तारीख</th><th>नाव</th><th>जिल्हा</th><th>मोबाईल</th><th>मिळालेले गुण</th><th>१-क्लिक संपर्क</th></tr></thead>
        <tbody>
            {% for t in test_leads %}
            <tr>
                <td>{{ t.test_date }}</td>
                <td><b>{{ t.student_name }}</b></td>
                <td>{{ t.district }}</td>
                <td>{{ t.phone }}</td>
                <td><b style="color:#059669;">{{ t.score }} / {{ t.total_marks }}</b></td>
                <td>
                    <a href="tel:{{ t.phone }}" class="btn-call">📞 कॉल</a>
                    <a href="https://wa.me/91{{ t.phone }}?text=नमस्कार%20{{ t.student_name }},%20श्रीगुरु%20अकॅडमीच्या%20टेस्टमध्ये%20तुम्हाला%20{{ t.score }}/{{ t.total_marks }}%20गुण%20मिळाले!%20प्रवेशासाठी%20आमच्याशी%20जोडले%20रहा." target="_blank" class="btn-wa">📲 WA निकाल</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="6" style="text-align:center; color:#64748b;">अद्याप कोणीही ऑनलाइन टेस्ट सोडवलेली नाही.</td></tr>
            {% endfor %}
        </tbody>
    </table>
    </body></html>'''
    return render_template_string(html, inquiries=inquiries, test_leads=test_leads)

@app.route('/update_inquiry/<int:id>', methods=['POST'])
def update_inquiry(id):
    c_status = request.form.get('call_status')
    note = request.form.get('staff_note')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE admission_inquiries SET call_status=%s, staff_note=%s WHERE id=%s", (c_status, note, id))
            conn.commit()
    return redirect('/inquiries')

# ================= SYSTEM FUNCTIONAL HANDLERS =================
@app.route('/download_backup')
def download_backup():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    return "Cloud database active.", 200

@app.route('/upload_restore_backup', methods=['POST'])
def upload_restore_backup():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    return "Cloud database active.", 200

@app.route('/add_discipline', methods=['POST'])
def add_discipline():
    sid = safe_int(request.form.get('student_id'))
    r_type = request.form.get('record_type', 'सुट्टी गेटपास')
    reason = request.form.get('reason')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students WHERE id=%s", (sid,))
            s = cur.fetchone()
            s_name = s['name'] if s else "विद्यार्थी"
            cur.execute("INSERT INTO discipline_records (student_id, record_type, record_date, reason) VALUES (%s, %s, %s, %s)",
                       (sid, r_type, date.today().strftime("%Y-%m-%d"), reason))
            conn.commit()
    log_staff_activity("Admin", f"गेटपास/ताकीद नोंद: {s_name} ({r_type} - {reason})")
    return redirect('/admin?tab=disc')

@app.route('/edit_discipline/<int:id>', methods=['POST'])
def edit_discipline(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE discipline_records SET record_type=%s, reason=%s WHERE id=%s", (request.form.get('record_type'), request.form.get('reason'), id))
            conn.commit()
    log_staff_activity("Admin", f"गेटपास दुरुस्त केला (ID: {id})")
    return redirect('/admin?tab=disc')

@app.route('/delete_discipline/<int:id>')
def delete_discipline(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM discipline_records WHERE id=%s", (id,))
            conn.commit()
    log_staff_activity("Admin", f"गेटपास रद्द/हटवला (ID: {id})")
    return redirect('/admin?tab=disc')

@app.route('/save_trainer_student_diet', methods=['POST'])
def save_trainer_student_diet():
    sid = safe_int(request.form.get('student_id'))
    d_text = request.form.get('diet_text')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students WHERE id=%s", (sid,))
            s = cur.fetchone()
            s_name = s['name'] if s else "विद्यार्थी"
            cur.execute("INSERT INTO student_care_log (student_id, care_date, issue_details, special_diet_note) VALUES (%s, %s, 'ट्रेनर डाएट शिफारस', %s)",
                       (sid, date.today().strftime("%Y-%m-%d"), d_text))
            conn.commit()
    log_staff_activity("Trainer", f"विद्यार्थी डाएट शिफारस: {s_name} - {d_text}")
    return redirect('/trainer?tab=student_diet')

@app.route('/add_injury', methods=['POST'])
def add_injury():
    sid = safe_int(request.form.get('student_id'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students WHERE id=%s", (sid,))
            s = cur.fetchone()
            s_name = s['name'] if s else "विद्यार्थी"
            cur.execute("INSERT INTO injuries (student_id, injury_date, injury_type, severity, rest_days) VALUES (%s, %s, %s, 'Moderate', %s)",
                       (sid, date.today().strftime("%Y-%m-%d"), request.form.get('injury_type'), safe_int(request.form.get('rest_days'))))
            conn.commit()
    log_staff_activity("Trainer", f"इजा नोंदवली: {s_name}")
    return redirect('/trainer?tab=inj')

@app.route('/add_physical_record', methods=['POST'])
def add_physical_record():
    sid = safe_int(request.form.get('student_id'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students WHERE id=%s", (sid,))
            s = cur.fetchone()
            s_name = s['name'] if s else "विद्यार्थी"
            cur.execute("INSERT INTO physical_tests (student_id, test_date, run_time, sprint_time, shot_put_dist, pullups, total_obtained) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                       (sid, request.form.get('test_date'), request.form.get('run_time'), request.form.get('sprint_time'), request.form.get('shot_put_dist'), safe_int(request.form.get('pullups')), safe_float(request.form.get('total_obtained'))))
            conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"फिजिकल गुण नोंदवले: {s_name}")
    return redirect(request.referrer or '/')

@app.route('/delete_physical_record/<int:id>')
def delete_physical_record(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM physical_tests WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=physical')

@app.route('/add_written_record', methods=['POST'])
def add_written_record():
    sid = safe_int(request.form.get('student_id'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students WHERE id=%s", (sid,))
            s = cur.fetchone()
            s_name = s['name'] if s else "विद्यार्थी"
            cur.execute("INSERT INTO written_tests (student_id, test_date, test_name, subject, total_marks, obtained_marks) VALUES (%s, %s, %s, %s, %s, %s)",
                       (sid, request.form.get('test_date'), request.form.get('test_name'), request.form.get('subject'), safe_float(request.form.get('total_marks'), 100), safe_float(request.form.get('obtained_marks'))))
            conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"लेखी परीक्षा निकाल: {s_name}")
    return redirect(request.referrer or '/')

@app.route('/delete_written_record/<int:id>')
def delete_written_record(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM written_tests WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=written')

@app.route('/add_hostel_fee', methods=['POST'])
def add_hostel_fee():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO hostel_mess_fees (student_id, package_type, from_month, to_month, total_amount, paid_amount, pay_date) VALUES (%s, '१ महिना', 'सप्टें', 'ऑक्टो', %s, %s, %s)",
                       (safe_int(request.form.get('student_id')), safe_float(request.form.get('paid_amount')), safe_float(request.form.get('paid_amount')), date.today().strftime("%Y-%m-%d")))
            conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"हॉस्टेल फी जमा: रु. {request.form.get('paid_amount')}")
    return redirect(request.referrer or '/')

@app.route('/send_staff_request', methods=['POST'])
def send_staff_request():
    role = session.get('user_role', 'Staff')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO staff_requests (req_role, req_date, request_title, request_details, status) VALUES (%s, %s, %s, %s, 'प्रलंबित')",
                       (role, date.today().strftime("%Y-%m-%d"), request.form.get('request_title'), request.form.get('request_details')))
            conn.commit()
    log_staff_activity(role, f"विनंती पाठवली: {request.form.get('request_title')}")
    return redirect(request.referrer or '/')

@app.route('/handle_request/<int:id>/<action>')
def handle_request(id, action):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff_requests SET status=%s WHERE id=%s", (action, id))
            conn.commit()
    log_staff_activity("Admin", f"विनंतीवर निर्णय: {action}")
    return redirect('/admin?tab=requests')

@app.route('/reply_staff_activity/<int:id>', methods=['POST'])
def reply_staff_activity(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff_activity_log SET admin_reply=%s WHERE id=%s", (request.form.get('admin_reply'), id))
            conn.commit()
    log_staff_activity("Admin", "स्टाफ हालचालीस रिप्लाय दिला.")
    return redirect('/admin?tab=staff_tracking')

@app.route('/add_new_system_user', methods=['POST'])
def add_new_system_user():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (role, password) VALUES (%s, %s)", (request.form.get('new_role'), request.form.get('new_password')))
            conn.commit()
    log_staff_activity("Admin", f"नवीन युजर तयार केला: {request.form.get('new_role')}")
    return redirect('/admin?tab=passwords')

@app.route('/delete_system_user/<int:id>')
def delete_system_user(id):
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=passwords')

@app.route('/save_trainer_practice', methods=['POST'])
def save_trainer_practice():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO trainer_practice_log (log_date, session_time, ground_status, workout_details) VALUES (%s, %s, %s, %s)",
                       (date.today().strftime("%Y-%m-%d"), request.form.get('session_time'), request.form.get('ground_status'), request.form.get('workout_details')))
            conn.commit()
    log_staff_activity("Trainer", f"सराव नोंदवला ({request.form.get('ground_status')}): {request.form.get('workout_details')}")
    return "<script>alert('सराव यशस्वी नोंदवला!'); window.location.href='/trainer?tab=practice';</script>"

@app.route('/save_coach_attendance', methods=['POST'])
def save_coach_attendance():
    att_type = request.form.get('att_type')
    today_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM attendance WHERE att_type=%s AND att_date=%s", (att_type, today_date))
            cur.execute("SELECT id FROM students")
            for s in cur.fetchall():
                st = request.form.get(f'status_{s["id"]}', 'हजर')
                cur.execute("INSERT INTO attendance (person_type, person_id, att_type, att_date, status) VALUES ('student', %s, %s, %s, %s)", (s['id'], att_type, today_date, st))
            conn.commit()
    log_staff_activity("Trainer", f"मैदानी हजेरी नोंदवली ({att_type})")
    return redirect('/trainer?tab=att')

@app.route('/add_canteen_staff', methods=['POST'])
def add_canteen_staff():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO canteen_staff_list (staff_name, work_role) VALUES (%s, %s)", (request.form.get('staff_name'), request.form.get('work_role')))
            conn.commit()
    return redirect('/manager?tab=cook')

@app.route('/delete_canteen_staff/<int:id>')
def delete_canteen_staff(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM canteen_staff_list WHERE id=%s", (id,))
            conn.commit()
    return redirect('/manager?tab=cook')

@app.route('/save_kitchen_att_dynamic', methods=['POST'])
def save_kitchen_att_dynamic():
    att_date = request.form.get('att_date')
    session_time = request.form.get('session_time')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM canteen_staff_list")
            for cs in cur.fetchall():
                st = request.form.get(f'status_{cs["id"]}', 'हजर')
                cur.execute("DELETE FROM kitchen_staff_att WHERE staff_name=%s AND att_date=%s AND session_time=%s", (cs['staff_name'], att_date, session_time))
                cur.execute("INSERT INTO kitchen_staff_att (staff_name, att_date, session_time, day_name, status) VALUES (%s, %s, %s, 'सोमवार', %s)", (cs['staff_name'], att_date, session_time, st))
            conn.commit()
    return redirect('/manager?tab=cook')

@app.route('/add_student', methods=['POST'])
def add_student():
    photo = request.files.get('photo')
    photo_filename = secure_filename(f"{date.today()}_{photo.filename}") if photo and photo.filename != "" else ""
    if photo_filename: photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO students (name, course, phone, parent_phone, total_fees, paid_fees, photo_filename, admission_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                       (request.form.get('name'), request.form.get('course'), request.form.get('phone'), request.form.get('parent_phone'), safe_float(request.form.get('total_fees')), safe_float(request.form.get('paid_fees')), photo_filename, request.form.get('admission_date')))
            conn.commit()
    role = session.get('user_role', 'Admin')
    log_staff_activity(role, f"नवीन प्रवेश: {request.form.get('name')}")
    return redirect(request.referrer or '/')

@app.route('/pay_installment', methods=['POST'])
def pay_installment():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE students SET paid_fees = paid_fees + %s WHERE id = %s", (safe_float(request.form.get('amount')), safe_int(request.form.get('student_id'))))
            conn.commit()
    role = session.get('user_role', 'Staff')
    log_staff_activity(role, f"फी जमा: रु. {request.form.get('amount')}")
    return redirect(request.referrer or '/')

@app.route('/add_expense', methods=['POST'])
def add_expense():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO expenses (exp_date, category, description, amount, logged_by) VALUES (%s, %s, %s, %s, %s)",
                       (date.today().strftime("%Y-%m-%d"), request.form.get('category'), request.form.get('description'), safe_float(request.form.get('amount')), session.get('user_role', 'Clerk')))
            conn.commit()
    log_staff_activity("Clerk", f"खर्च नोंदवला: रु. {request.form.get('amount')}")
    return redirect(request.referrer or '/')

@app.route('/add_kit_distribution', methods=['POST'])
def add_kit_distribution():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO kit_distribution (student_id, item_details, issue_date, logged_by) VALUES (%s, %s, %s, %s)",
                       (safe_int(request.form.get('student_id')), request.form.get('item_details'), date.today().strftime("%Y-%m-%d"), session.get('user_role', 'Clerk')))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/save_attendance', methods=['POST'])
def save_attendance():
    att_type = request.form.get('att_type')
    today_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM attendance WHERE att_type=%s AND att_date=%s", (att_type, today_date))
            cur.execute("SELECT id FROM students")
            for s in cur.fetchall():
                st = request.form.get(f'status_{s["id"]}', 'हजर')
                cur.execute("INSERT INTO attendance (person_type, person_id, att_type, att_date, status) VALUES ('student', %s, %s, %s, %s)", (s['id'], att_type, today_date, st))
            conn.commit()
    return redirect('/admin?tab=att')

@app.route('/attendance')
def clerk_attendance_portal():
    if session.get('user_role') not in ['Clerk', 'Admin', 'Manager']:
        return redirect(url_for('login'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students ORDER BY name ASC")
            students = cur.fetchall()
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
        with conn.cursor() as cur:
            cur.execute("INSERT INTO staff (name, role, phone, salary, joining_date, advance_paid, total_leaves) VALUES (%s, %s, %s, %s, %s, 0, 0)",
                       (request.form.get('name'), request.form.get('role'), request.form.get('phone'), safe_float(request.form.get('salary')), request.form.get('joining_date')))
            conn.commit()
    log_staff_activity("Admin", f"स्टाफ जोडला: {request.form.get('name')}")
    return redirect('/admin?tab=staff')

@app.route('/update_staff_advance/<int:id>', methods=['POST'])
def update_staff_advance(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff SET advance_paid = advance_paid + %s WHERE id=%s", (safe_float(request.form.get('advance_amount')), id))
            conn.commit()
    return redirect('/admin?tab=staff')

@app.route('/add_staff_leave/<int:id>', methods=['POST'])
def add_staff_leave(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff SET total_leaves = total_leaves + %s WHERE id=%s", (safe_int(request.form.get('leave_days'), 1), id))
            conn.commit()
    return redirect('/admin?tab=staff')

@app.route('/delete_staff/<int:id>')
def delete_staff(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM staff WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=staff')

@app.route('/pay_staff_salary/<int:id>', methods=['POST'])
def pay_staff_salary(id):
    from_date = request.form.get('from_date', '')
    to_date = request.form.get('to_date', '')
    amount = safe_float(request.form.get('amount'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM staff WHERE id=%s", (id,))
            staff = cur.fetchone()
            staff_name = staff['name'] if staff else f"ID {id}"
            desc = f"स्टाफ पगार: {staff_name} (कालावधी: {from_date} ते {to_date})"
            cur.execute("INSERT INTO expenses (exp_date, category, description, amount, logged_by) VALUES (CURRENT_DATE, 'Staff Salary', %s, %s, 'Admin')", (desc, amount))
            cur.execute("UPDATE staff SET advance_paid = 0 WHERE id=%s", (id,))
            conn.commit()
    log_staff_activity("Admin", f"पगार वाटप: {staff_name} - ₹{amount} ({from_date} ते {to_date})")
    return redirect('/admin?tab=staff')

@app.route('/assign_task', methods=['POST'])
def assign_task():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO staff_tasks (target_role, task_text, task_date, status) VALUES (%s, %s, %s, 'Unseen')",
                       (request.form.get('target_role'), request.form.get('task_text'), date.today().strftime("%Y-%m-%d")))
            conn.commit()
    return redirect('/admin?tab=tasks')

@app.route('/edit_staff_task/<int:id>', methods=['POST'])
def edit_staff_task(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff_tasks SET target_role=%s, task_text=%s WHERE id=%s", (request.form.get('target_role'), request.form.get('task_text'), id))
            conn.commit()
    return redirect('/admin?tab=tasks')

@app.route('/delete_staff_task/<int:id>')
def delete_staff_task(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM staff_tasks WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=tasks')

@app.route('/mark_task_seen/<int:id>')
def mark_task_seen(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE staff_tasks SET status='Seen' WHERE id=%s", (id,))
            conn.commit()
    return redirect(request.referrer or '/')

@app.route('/change_password/<int:id>', methods=['POST'])
def change_password(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password=%s WHERE id=%s", (request.form.get('new_password'), id))
            conn.commit()
    return redirect('/admin?tab=passwords')

@app.route('/delete_student/<int:id>')
def delete_student(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM students WHERE id=%s", (id,))
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
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE id=%s", (id,))
            student = cur.fetchone()
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

# ----- STUDENT FULL REPORT ROUTE -----
@app.route('/student_report/<int:student_id>', methods=['GET', 'POST'])
def student_report(student_id):
    if 'user_role' not in session and 'role' not in session:
        return redirect(url_for('login'))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
            student = cur.fetchone()
            if not student:
                return "विद्यार्थी सापडला नाही!", 404

            if request.method == 'POST':
                diet_plan = request.form.get('diet_plan')
                admin_remark = request.form.get('admin_remark')
                cur.execute("UPDATE students SET diet_plan = %s, admin_remark = %s WHERE id = %s", (diet_plan, admin_remark, student_id))
                conn.commit()
                return redirect(url_for('student_report', student_id=student_id))

            try:
                cur.execute("SELECT * FROM staff_activities WHERE student_id = %s ORDER BY id DESC", (student_id,))
                staff_logs = cur.fetchall()
            except Exception:
                staff_logs = []

            try:
                cur.execute("SELECT att_date as date, status, 'Staff' as marked_by FROM attendance WHERE person_id = %s ORDER BY att_date DESC", (student_id,))
                attendance_records = cur.fetchall()
            except Exception:
                attendance_records = []

            try:
                cur.execute("SELECT * FROM ground_records WHERE student_id = %s ORDER BY test_date DESC", (student_id,))
                ground_records = cur.fetchall()
            except Exception:
                ground_records = []

    return render_template('student_report.html', 
                           student=student, 
                           logs=staff_logs, 
                           attendance=attendance_records, 
                           ground_records=ground_records)

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
            with conn.cursor() as cur:
                if request.method == 'POST':
                    student_id = request.form.get('student_id')
                    test_date = request.form.get('test_date', today_str)
                    event_name = request.form.get('event_name')
                    raw_value = request.form.get('raw_value', 0)
                    remark = request.form.get('remark', '')

                    cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
                    student = cur.fetchone()
                    gender = 'पुरुष'
                    if student:
                        try:
                            gender = student['gender'] if 'gender' in student.keys() else 'पुरुष'
                        except Exception:
                            gender = 'पुरुष'

                    marks = calculate_ground_marks(gender, event_name, raw_value)
                    cur.execute("""
                        INSERT INTO ground_records (student_id, test_date, event_name, raw_value, marks, trainer_name, remark)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (student_id, test_date, event_name, raw_value, marks, user_name, remark))
                    conn.commit()
                    msg = f"चाचणी यशस्वीरित्या नोंदवली गेली! मिळालेले गुण: {marks}"

                cur.execute("SELECT id, name FROM students ORDER BY name ASC")
                students = cur.fetchall()
                
                cur.execute("""
                    SELECT g.id, g.student_id, g.test_date, g.event_name, g.raw_value, g.marks, g.trainer_name, g.remark, s.name as student_name
                    FROM ground_records g
                    LEFT JOIN students s ON g.student_id = s.id
                    ORDER BY g.id DESC LIMIT 25
                """)
                recent_records = cur.fetchall()

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
        table_rows = "<tr><td colspan='6' style='text-align:center; padding:15px; color:#64748b;font-size:13px;'>अजून कोणतीही मैदानी चाचणी नोंदवलेली नाही.</td></tr>"

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
        with conn.cursor() as cur:
            cur.execute("DELETE FROM staff_activities WHERE id = %s", (act_id,))
            conn.commit()

    return redirect(request.referrer or url_for('admin_view'))

@app.route('/edit_staff_activity/<int:act_id>', methods=['GET', 'POST'])
def edit_staff_activity(act_id):
    if session.get('user_role') != 'Admin' and session.get('role') != 'admin':
        return "अनधिकृत प्रवेश! फक्त ॲडमिन ही नोंद एडिट करू शकतात.", 403

    with get_db() as conn:
        with conn.cursor() as cur:
            if request.method == 'POST':
                new_date = request.form.get('activity_date')
                new_action = request.form.get('action_text')
                new_remark = request.form.get('remark', '')

                cur.execute("""
                    UPDATE staff_activities 
                    SET activity_date = %s, action_text = %s, remark = %s
                    WHERE id = %s
                """, (new_date, new_action, new_remark, act_id))
                conn.commit()
                return redirect(url_for('admin_view'))

            cur.execute("SELECT * FROM staff_activities WHERE id = %s", (act_id,))
            record = cur.fetchone()

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
        with conn.cursor() as cur:
            cur.execute("SELECT student_id FROM student_activities WHERE id = %s", (record_id,))
            rec = cur.fetchone()
            student_id = rec['student_id'] if rec else None
            
            cur.execute("DELETE FROM student_activities WHERE id = %s", (record_id,))
            conn.commit()

    if student_id:
        return redirect(f"/student_report/{student_id}")
    return redirect(request.referrer or url_for('admin_view'))

@app.route('/edit_student_remark/<int:record_id>', methods=['GET', 'POST'])
def edit_student_remark(record_id):
    if session.get('user_role') != 'Admin' and session.get('role') != 'admin':
        return "फक्त ॲडमिनला ही नोंद दुरुस्त करण्याची परवानगी आहे.", 403

    with get_db() as conn:
        with conn.cursor() as cur:
            if request.method == 'POST':
                new_date = request.form.get('activity_date')
                new_remark = request.form.get('remark')
                new_diet = request.form.get('diet_plan', '')
                student_id = request.form.get('student_id')

                cur.execute("""
                    UPDATE student_activities 
                    SET activity_date = %s, remark = %s, diet_plan = %s
                    WHERE id = %s
                """, (new_date, new_remark, new_diet, record_id))
                conn.commit()
                return redirect(f"/student_report/{student_id}")

            cur.execute("SELECT * FROM student_activities WHERE id = %s", (record_id,))
            record = cur.fetchone()

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
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM books ORDER BY id DESC")
            books = cur.fetchall()
            cur.execute("SELECT * FROM book_issues WHERE status = 'Issued' ORDER BY id DESC")
            issues = cur.fetchall()
            cur.execute("SELECT * FROM study_lab_seats ORDER BY seat_number ASC")
            seats = cur.fetchall()
    return render_template('library.html', books=books, issues=issues, seats=seats)

@app.route('/add_book', methods=['POST'])
def add_book():
    title = request.form.get('title')
    author = request.form.get('author')
    category = request.form.get('category')
    copies = int(request.form.get('copies', 1))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO books (title, author, category, total_copies, available_copies) VALUES (%s, %s, %s, %s, %s)",
                       (title, author, category, copies, copies))
            conn.commit()
    return redirect('/library')

@app.route('/issue_book', methods=['POST'])
def issue_book():
    book_id = request.form.get('book_id')
    student_name = request.form.get('student_name')
    issue_date = request.form.get('issue_date')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO book_issues (book_id, student_name, issue_date, status) VALUES (%s, %s, %s, 'Issued')",
                       (book_id, student_name, issue_date))
            cur.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = %s AND available_copies > 0", (book_id,))
            conn.commit()
    return redirect('/library')

@app.route('/return_book/<int:issue_id>/<int:book_id>')
def return_book(issue_id, book_id):
    today = date.today().strftime('%Y-%m-%d')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE book_issues SET return_date = %s, status = 'Returned' WHERE id = %s", (today, issue_id))
            cur.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = %s", (book_id,))
            conn.commit()
    return redirect('/library')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

