import os
import shutil
import re
import json
from datetime import date, datetime, timedelta 
from flask import Flask, redirect, render_template, render_template_string, request, send_file, send_from_directory, url_for, session, Response
from werkzeug.utils import secure_filename
import io
import csv
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_ultimate_master_all_tabs_fully_complete_v110"

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

            cur.execute('''CREATE TABLE IF NOT EXISTS test_papers (
                id SERIAL PRIMARY KEY,
                test_title TEXT NOT NULL,
                test_fee REAL DEFAULT 0,
                status TEXT DEFAULT 'Active'
            )''')

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
                    (1, "महाराष्ट्राची राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B", "मुंबई ही महाराष्ट्राची आर्थिक राजधानी आहे."),
                    (1, "क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A", "अहमदनगर हा सर्वात मोठा जिल्हा आहे."),
                    (1, "स्वराज्य स्थापना कोणी केली?", "छत्रपती संभाजी महाराज", "छत्रपती शिवाजी महाराज", "महात्मा ज्योतिराव फुले", "संत ज्ञानेश्वर", "B", "छत्रपती शिवाजी महाराजांनी स्वराज्य स्थापना केली.")
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
    <span class="insignia">⚔️ POLICE & DEFENCE TRAINING</span>
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

# ----------------- ADMIN DASHBOARD LAYOUT (FULL 22+ TABS + LIVE CLOCK) -----------------
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
    <script>
        function updateLiveClock() {
            const now = new Date();
            let hours = now.getHours();
            let minutes = now.getMinutes();
            let seconds = now.getSeconds();
            let ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12;
            hours = hours ? hours : 12;
            minutes = minutes < 10 ? '0' + minutes : minutes;
            seconds = seconds < 10 ? '0' + seconds : seconds;
            let timeStr = hours + ':' + minutes + ':' + seconds + ' ' + ampm;
            let options = { year: 'numeric', month: 'long', day: 'numeric' };
            let dateStr = now.toLocaleDateString('mr-IN', options);
            if(document.getElementById('liveTime')) {
                document.getElementById('liveTime').innerText = timeStr;
                document.getElementById('liveDate').innerText = dateStr;
            }
        }
        setInterval(updateLiveClock, 1000);
        window.onload = updateLiveClock;
    </script>
</head>
<body>
<div class="header">
    <div class="clock"><div id="liveTime" style="font-weight:bold; color:#ffdd59;">--:--:-- --</div><div id="liveDate">----</div></div>
    <h1 style="margin:0; color:#ffdd59; font-size:24px;">SHREEGURU CAREER ACADEMY</h1>
    <p style="margin:3px 0 0; font-size:12px;">पत्ता: आडूर, करवीर, कोल्हापूर | संपर्क: ९९२११११९६०</p>
    <div class="top-right">
        <a href="/toggle_lang" style="background:#ffdd59; color:#0b3c5d; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:bold; text-decoration:none;">🌐 मराठी / EN</a>
        <span style="color:#ffdd59; font-size:12px;">👤 Admin</span>
        <a href="/logout" style="background:#ef4444; color:white; padding:3px 8px; border-radius:4px; text-decoration:none; font-size:11px; font-weight:bold;">Logout</a>
    </div>
</div>

<div class="menu-bar">
    <a href="/inquiries" class="menu-btn" style="background:#b45309; border:2px solid #fde047;">📞 चौकशी व टेस्ट डेस्क</a>
    <a href="/admin?tab=payments" class="menu-btn {% if curr_tab == 'payments' %}active{% endif %}" style="background:#059669; border:2px solid #ffdd59;">💳 पेमेंट व वैधता डेस्क</a>
    <a href="/admin?tab=questions" class="menu-btn {% if curr_tab == 'questions' %}active{% endif %}" style="background:#7c3aed; border:2px solid #fde047;">❓ प्रश्न व्यवस्थापन व लॉन्च</a>
    <a href="/admin?tab=students" class="menu-btn {% if curr_tab == 'students' %}active{% endif %}" style="background:#2563eb;">👥 सर्व विद्यार्थी</a>
    <a href="/admin?tab=admission" class="menu-btn {% if curr_tab == 'admission' %}active{% endif %}" style="background:#2563eb;">📝 नवीन प्रवेश</a>
    <a href="/admin?tab=physical" class="menu-btn {% if curr_tab == 'physical' %}active{% endif %}" style="background:#0284c7;">🏃‍♂️ फिजिकल रेकॉर्ड</a>
    <a href="/admin?tab=written" class="menu-btn {% if curr_tab == 'written' %}active{% endif %}" style="background:#10b981;">📝 रिटर्न टेस्ट</a>
    <a href="/admin?tab=requests" class="menu-btn {% if curr_tab == 'requests' %}active{% endif %}" style="background:#e11d48; border:2px solid #ffdd59;">📩 स्टाफ विनंत्या</a>
    <a href="/admin?tab=fee" class="menu-btn {% if curr_tab == 'fee' %}active{% endif %}" style="background:#f59e0b;">💰 फी जमा</a>
    <a href="/admin?tab=hostel" class="menu-btn {% if curr_tab == 'hostel' %}active{% endif %}" style="background:#8e2de2;">🏠 हॉस्टेल/मेस</a>
    <a href="/admin?tab=att" class="menu-btn {% if curr_tab == 'att' %}active{% endif %}" style="background:#e11d48;">📋 सर्व हजेरी</a>
    <a href="/library" target="_blank" class="menu-btn" style="background: linear-gradient(135deg, #0284c7, #06b6d4); color: white;">📚 स्टडी लॅब / लायब्ररी</a>
    <a href="/admin?tab=diet" class="menu-btn {% if curr_tab == 'diet' %}active{% endif %}" style="background:#6366f1;">🥗 मेस डाएट</a>
    <a href="/admin?tab=disc" class="menu-btn {% if curr_tab == 'disc' %}active{% endif %}" style="background:#6b21a8;">⚠️ गेटपास/शिस्त</a>
    <a href="/admin?tab=exp" class="menu-btn {% if curr_tab == 'exp' %}active{% endif %}" style="background:#ff416c;">💵 खर्च वही</a>
    <a href="/admin?tab=wa" class="menu-btn {% if curr_tab == 'wa' %}active{% endif %}" style="background:#10b981;">📲 WhatsApp</a>
    <a href="/admin?tab=staff" class="menu-btn {% if curr_tab == 'staff' %}active{% endif %}" style="background:#4f46e5;">👔 स्टाफ पगार</a>
    <a href="/admin?tab=tasks" class="menu-btn {% if curr_tab == 'tasks' %}active{% endif %}" style="background:#d97706;">📌 काम सांगा</a>
    <a href="/admin?tab=staff_tracking" class="menu-btn {% if curr_tab == 'staff_tracking' %}active{% endif %}" style="background:#059669; border:2px solid #ffdd59;">👁️ स्टाफ हालचाली</a>
    <a href="/admin?tab=passwords" class="menu-btn {% if curr_tab == 'passwords' %}active{% endif %}" style="background:#dc2626;">🔐 युजर्स व पासवर्ड</a>
    <a href="/admin?tab=bak" class="menu-btn {% if curr_tab == 'bak' %}active{% endif %}" style="background:#334155;">💾 बॅकअप / रिस्टोअर</a>
</div>

<div class="container">
    <div class="kpis">
        <div class="kpi"><b>एकूण विद्यार्थी:</b> {{ students|length }}</div>
        <div class="kpi" style="border-color:#10b981;"><b>जमा फी:</b> ₹{{ total_paid }}</div>
        <div class="kpi" style="border-color:#ef4444;"><b>शिल्लक फी:</b> <span style="color:red;">₹{{ total_pending }}</span></div>
        <div class="kpi" style="border-color:#ff416c;"><b>एकूण खर्च:</b> ₹{{ total_expenses }}</div>
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
                            <input type="date" name="valid_till" value="{{ p.valid_till or '' }}" style="padding:3px; font-size:11px;">
                            <button type="submit" class="btn-act" style="background:#0284c7;">💾</button>
                        </form>
                    </td>
                    <td>
                        {% if p.payment_status != 'Approved' %}
                        <a href="/approve_payment/{{ p.id }}" class="btn-act" style="background:#16a34a; margin-bottom:3px; display:inline-block;">✅ अप्रूव</a>
                        {% endif %}
                        <a href="/delete_test_lead/{{ p.id }}" onclick="return confirm('हटवायचे?')" class="btn-del">🗑️ डिलीट</a>
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
        <h3 style="color:#7c3aed; margin-top:0;">❓ ऑनलाइन टेस्ट प्रश्न व्यवस्थापन व लॉन्च कंट्रोल</h3>
        
        <div style="background:#faf5ff; border:2px solid #7c3aed; padding:15px; border-radius:8px; margin-bottom:20px;">
            <h4 style="margin:0 0 10px; color:#5b21b6; font-size:15px;">📚 टेस्ट पेपर निवडा किंवा नवीन तयार करा:</h4>
            <form action="/add_test_paper" method="POST" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:15px;">
                <input type="text" name="test_title" placeholder="नवीन टेस्टचे नाव" required style="flex:2; min-width:250px;">
                <input type="number" name="test_fee" placeholder="फी (₹)" min="0" value="0" required style="width:100px;">
                <button type="submit" class="btn-act" style="background:#7c3aed; padding:8px 15px;">+ नवीन टेस्ट जोडा</button>
            </form>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
                {% for tp in all_test_papers %}
                <div style="background:white; border:1px solid #d8b4fe; padding:8px 12px; border-radius:6px; display:flex; align-items:center; gap:10px;">
                    <div><b>{{ tp.test_title }}</b> (फी: ₹{{ tp.test_fee }})</div>
                    <a href="/admin?tab=questions&test_id={{ tp.id }}" class="btn-act" style="background:{{ '#16a34a' if current_test_id == tp.id else '#0284c7' }};">
                        {{ '🟢 निवडली आहे' if current_test_id == tp.id else '✏️ पहा' }}
                    </a>
                </div>
                {% endfor %}
            </div>
        </div>

        <div style="background:#f0fdf4; border:2px solid #15803d; padding:15px; border-radius:8px; margin-bottom:20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:15px;">
                <div>
                    <b style="color:#166534; font-size:15px;">🚀 टेस्ट ऑनलाईन लॉन्च कंट्रोल: ({{ current_test_title }})</b><br>
                    <span style="font-size:13px; color:#475569;">स्थिती: <b>{{ '✅ लाईव्ह आहे' if test_launched == 'yes' else '❌ बंद आहे' }}</b></span>
                </div>
                <div>
                    <form action="/toggle_test_launch" method="POST" style="display:inline;">
                        {% if test_launched == 'yes' %}
                        <button type="submit" class="btn-act" style="background:#dc2626; padding:10px 16px;">🔴 टेस्ट बंद करा</button>
                        {% else %}
                        <button type="submit" class="btn-act" style="background:#16a34a; padding:10px 16px;">🟢 टेस्ट लाईव्ह करा</button>
                        {% endif %}
                    </form>
                    <a href="/test?test_id={{ current_test_id }}" target="_blank" class="btn-act" style="background:#0284c7; padding:10px 16px; margin-left:5px;">🌐 टेस्ट पेज पहा</a>
                </div>
            </div>
            <form action="/update_test_settings" method="POST" style="background:white; padding:12px; border-radius:6px; border:1px solid #bbf7d0;">
                <h4 style="margin:0 0 10px; color:#166534; font-size:14px;">⚙️ UPI ID आणि QR कोड सेटिंग्ज:</h4>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:10px;">
                    <div><label style="font-weight:bold; font-size:12px;">UPI ID:</label><input type="text" name="upi_id" value="{{ upi_id }}" style="width:100%; padding:6px;" required></div>
                    <div><label style="font-weight:bold; font-size:12px;">QR कोड इमेज URL:</label><input type="text" name="qr_image_url" value="{{ qr_image_url }}" style="width:100%; padding:6px;" required></div>
                </div>
                <button type="submit" class="btn-act" style="background:#15803d; padding:8px 16px;">💾 सेव्ह करा</button>
            </form>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
                <h4 style="margin-top:0; color:#0b3c5d;">१. नवीन प्रश्न व स्पष्टीकरण (Explanation) टाका:</h4>
                <form action="/add_single_question" method="POST">
                    <input type="hidden" name="test_id" value="{{ current_test_id }}">
                    <label>प्रश्न:</label><textarea name="question" required style="width:100%; height:50px;"></textarea>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
                        <div> पर्याय A: <input type="text" name="opt_a" required style="width:100%;"></div>
                        <div> पर्याय B: <input type="text" name="opt_b" required style="width:100%;"></div>
                        <div> पर्याय C: <input type="text" name="opt_c" required style="width:100%;"></div>
                        <div> पर्याय D: <input type="text" name="opt_d" required style="width:100%;"></div>
                    </div><br>
                    <label>अचूक पर्याय:</label><select name="correct" style="width:100%; padding:6px;"><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select><br><br>
                    <label>स्पष्टीकरण (Explanation):</label><textarea name="explanation" style="width:100%; height:40px;"></textarea><br>
                    <button type="submit" class="btn-act" style="background:#7c3aed; width:100%; padding:8px;">+ प्रश्न सेव्ह करा</button>
                </form>
            </div>

            <div style="background:#f0fdf4; padding:15px; border-radius:6px; border:1px solid #bbf7d0;">
                <h4 style="margin-top:0; color:#15803d;">२. बल्क प्रश्न (Bulk Copy-Paste):</h4>
                <p style="font-size:12px; color:#475569;">फॉरमॅट: <code>प्रश्न | पर्यायA | पर्यायB | पर्यायC | पर्यायD | अचूक | स्पष्टीकरण</code></p>
                <form action="/add_bulk_questions" method="POST">
                    <input type="hidden" name="test_id" value="{{ current_test_id }}">
                    <textarea name="bulk_text" rows="8" style="width:100%;" required></textarea><br>
                    <button type="submit" class="btn-act" style="background:#15803d; width:100%; padding:8px;">📥 बल्क अपलोड करा</button>
                </form>
            </div>
        </div>

        <h4 style="margin-top:25px;">📋 सध्याच्या टेस्टमधील प्रश्न यादी ({{ questions|length }}):</h4>
        <table>
            <thead><tr><th>क्र.</th><th>प्रश्न व स्पष्टीकरण</th><th>पर्याय</th><th>अचूक</th><th>कृती</th></tr></thead>
            <tbody>
                {% for q in questions %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td><b>{{ q.question }}</b><br>{% if q.explanation %}<span style="color:#047857; font-size:12px;">💡 स्पष्टीकरण: {{ q.explanation }}</span>{% endif %}</td>
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
        <h3 style="margin:0;">📋 सर्व विद्यार्थी यादी</h3>
        <table>
            <thead><tr><th>फोटो</th><th>Reg</th><th>नाव</th><th>कोर्स</th><th>फोन</th><th>शिल्लक</th><th>कृती</th></tr></thead>
            <tbody>
                {% for s in students %}
                <tr>
                    <td>{% if s.photo_filename %}<img src="/uploads/{{ s.photo_filename }}" width="35" height="40">{% else %}-{% endif %}</td>
                    <td>REG-{{ s.id }}</td><td><b>{{ s.name }}</b></td><td>{{ s.course }}</td><td>{{ s.phone }}</td>
                    <td style="color:red; font-weight:bold;">₹{{ (s.total_fees or 0) - (s.paid_fees or 0) }}</td>
                    <td><a href="/delete_student/{{ s.id }}" onclick="return confirm('हटवायचे?')" class="btn-act" style="background:red;">हटवा</a></td>
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
    <div class="admin-tab"><h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ फिजिकल रेकॉर्ड</h3><table><thead><tr><th>तारीख</th><th>नाव</th><th>कोर्स</th><th>1600m</th><th>100m</th><th>गोळा</th><th>पुल-अप्स</th><th>एकूण</th></tr></thead><tbody>{% for pt in physical_records %}<tr><td>{{ pt.test_date }}</td><td><b>{{ pt.name }}</b></td><td>{{ pt.course }}</td><td>{{ pt.run_time }}</td><td>{{ pt.sprint_time }}</td><td>{{ pt.shot_put_dist }}</td><td>{{ pt.pullups }}</td><td><b style="color:green;">{{ pt.total_obtained }}/50</b></td></tr>{% endfor %}</tbody></table></div>
    {% endif %}

    {% if curr_tab == 'written' %}
    <div class="admin-tab"><h3 style="color:#10b981; margin-top:0;">📝 रिटर्न टेस्ट</h3><table><thead><tr><th>तारीख</th><th>नाव</th><th>परीक्षा</th><th>गुण</th></tr></thead><tbody>{% for wt in written_records %}<tr><td>{{ wt.test_date }}</td><td><b>{{ wt.name }}</b></td><td>{{ wt.test_name }}</td><td style="color:green;">{{ wt.obtained_marks }}/{{ wt.total_marks }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}

    {% if curr_tab == 'requests' %}
    <div class="admin-tab"><h3 style="color:#e11d48; margin-top:0;">📩 स्टाफ विनंत्या</h3><table><thead><tr><th>तारीख</th><th>कर्मचारी</th><th>विषय</th><th>तपशील</th><th>स्थिती</th></tr></thead><tbody>{% for r in all_requests %}<tr><td>{{ r.req_date }}</td><td><b>{{ r.req_role }}</b></td><td><b>{{ r.request_title }}</b></td><td>{{ r.request_details }}</td><td><b>{{ r.status }}</b></td></tr>{% endfor %}</tbody></table></div>
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
    <div class="admin-tab"><h3>🏠 हॉस्टेल व मेस फी नोंद</h3><table><thead><tr><th>तारीख</th><th>नाव</th><th>पॅकेज</th><th>रक्कम</th></tr></thead><tbody>{% for h in hostel_logs %}<tr><td>{{ h.pay_date }}</td><td><b>{{ h.name }}</b></td><td>{{ h.package_type }}</td><td style="color:green; font-weight:bold;">₹{{ h.paid_amount }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}

    {% if curr_tab == 'att' %}
    <div class="admin-tab">
        <h3>📋 हजेरी नोंद</h3>
        <form action="/save_attendance" method="POST">
            <input type="hidden" name="att_type" value="मैदानी हजेरी">
            <table><thead><tr><th>नाव</th><th>हजेरी</th></tr></thead><tbody>
                {% for s in students %}
                <tr><td><b>{{ s.name }}</b></td><td><label><input type="radio" name="status_{{ s.id }}" value="हजर" checked> P</label> <label style="color:red;"><input type="radio" name="status_{{ s.id }}" value="गैरहजर"> A</label></td></tr>
                {% endfor %}
            </tbody></table><br><button type="submit" class="btn-act" style="background:#e11d48;">💾 हजेरी सेव्ह करा</button>
        </form>
    </div>
    {% endif %}

    {% if curr_tab == 'diet' %}
    <div class="admin-tab">
        <h3 style="color:#6366f1;">🥗 मेस डाएट वेळापत्रक</h3>
        <table><thead><tr><th>वार</th><th>सकाळ नाश्ता</th><th>दुपार जेवण</th><th>रात्र जेवण</th><th>विशेष आहार</th></tr></thead><tbody>
            {% for d in diet_list %}<tr><td><b>{{ d.day_name }}</b></td><td>{{ d.breakfast }}</td><td>{{ d.lunch }}</td><td>{{ d.dinner }}</td><td>{{ d.special_diet }}</td></tr>{% endfor %}
        </tbody></table>
    </div>
    {% endif %}

    {% if curr_tab == 'disc' %}
    <div class="admin-tab"><h3 style="color:#6b21a8; margin-top:0;">⚠️️ गेटपास व शिस्तभंग नोंद</h3><table><thead><tr><th>तारीख</th><th>नाव</th><th>प्रकार</th><th>कारण</th></tr></thead><tbody>{% for d in discipline_logs %}<tr><td>{{ d.record_date }}</td><td><b>{{ d.name }}</b></td><td>{{ d.record_type }}</td><td>{{ d.reason }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}

    {% if curr_tab == 'exp' %}
    <div class="admin-tab">
        <h3>💵 दैनिक खर्च वही</h3>
        <form action="/add_expense" method="POST" style="margin-bottom:15px; display:flex; gap:10px; flex-wrap:wrap;">
            <input type="date" name="exp_date" value="{{ today_date }}" required>
            <input type="text" name="category" placeholder="खर्चाचा प्रकार (उदा. भाजीपाला)" required>
            <input type="text" name="description" placeholder="तपशील">
            <input type="number" name="amount" placeholder="रक्कम (₹)" required>
            <button type="submit" class="btn-act" style="background:#ff416c;">+ खर्च नोंदवा</button>
        </form>
        <table><thead><tr><th>तारीख</th><th>प्रकार</th><th>तपशील</th><th>रक्कम</th></tr></thead><tbody>
            {% for ex in expenses_list %}<tr><td>{{ ex.exp_date }}</td><td>{{ ex.category }}</td><td><b>{{ ex.description }}</b></td><td style="color:red; font-weight:bold;">₹{{ ex.amount }}</td></tr>{% endfor %}
        </tbody></table>
    </div>
    {% endif %}

    {% if curr_tab == 'wa' %}
    <div class="admin-tab"><h3>📲 WhatsApp मेसेज</h3><table><thead><tr><th>नाव</th><th>फोन</th><th>मेसेज</th></tr></thead><tbody>{% for s in students %}<tr><td>{{ s.name }}</td><td>{{ s.parent_phone }}</td><td><a href="https://wa.me/91{{ s.parent_phone }}" target="_blank" class="btn-act" style="background:#25D366;">📲 मेसेज</a></td></tr>{% endfor %}</tbody></table></div>
    {% endif %}

    {% if curr_tab == 'staff' %}
    <div class="admin-tab">
        <h3 style="color:#4f46e5; margin-top:0;">👔 स्टाफ पगार व उचल हिशोब</h3>
        <table><thead><tr><th>नाव</th><th>पद</th><th>फोन</th><th>पगार</th><th>उचल (Advance)</th><th>निव्वळ पगार</th></tr></thead><tbody>
            {% for st in staff_members %}<tr><td><b>{{ st.name }}</b></td><td>{{ st.role }}</td><td>{{ st.phone }}</td><td>₹{{ st.salary }}</td><td style="color:red;">₹{{ st.advance_paid }}</td><td style="color:green; font-weight:bold;">₹{{ st.salary - st.advance_paid }}</td></tr>{% endfor %}
        </tbody></table>
    </div>
    {% endif %}

    {% if curr_tab == 'tasks' %}
    <div class="admin-tab">
        <h3 style="color:#d97706; margin-top:0;">📌 स्टाफ कामे (Task Assignment)</h3>
        <form action="/assign_task" method="POST" style="margin-bottom:15px; display:flex; gap:10px; flex-wrap:wrap;">
            <select name="target_role" required><option value="Manager">मॅनेजर</option><option value="Clerk">क्लार्क</option><option value="Trainer">फिजिकल ट्रेनर</option></select>
            <input type="text" name="task_text" placeholder="कामाचा तपशील..." required style="flex:2;">
            <button type="submit" class="btn-act" style="background:#d97706;">+ काम सांगा</button>
        </form>
        <table><thead><tr><th>दिनांक</th><th>कोणाला</th><th>काम</th><th>स्थिती</th></tr></thead><tbody>
            {% for t in staff_tasks %}<tr><td>{{ t.task_date }}</td><td><b>{{ t.target_role }}</b></td><td>{{ t.task_text }}</td><td><b>{{ t.status }}</b></td></tr>{% endfor %}
        </tbody></table>
    </div>
    {% endif %}

    {% if curr_tab == 'staff_tracking' %}
    <div class="admin-tab"><h3 style="color:#059669; margin-top:0;">👁️ स्टाफ हालचाली (Activity Log)</h3><table><thead><tr><th>वेळ</th><th>कर्मचारी</th><th>हालचाल नोंद</th></tr></thead><tbody>{% for log in all_staff_logs %}<tr><td>{{ log.act_time }}</td><td><b>{{ log.staff_role }}</b></td><td>{{ log.activity_text }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}

    {% if curr_tab == 'passwords' %}
    <div class="admin-tab"><h3 style="color:#dc2626; margin-top:0;">🔐 युजर पासवर्ड</h3><table><thead><tr><th>Role</th><th>Password</th></tr></thead><tbody>{% for u in users_list %}<tr><td><b>{{ u.role }}</b></td><td>{{ u.password }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}

    {% if curr_tab == 'bak' %}
    <div class="admin-tab"><h3 style="color:#0b3c5d;">💾 डेटाबेस बॅकअप</h3><p>क्लाउड डेटाबेस (Neon PostgreSQL) पूर्णपणे सुरक्षित कार्यरत आहे.</p></div>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- MANAGER PORTAL (FULL TABS & 500 GROCERY) -----------------
MANAGER_LAYOUT = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>मॅनेजर डॅशबोर्ड - श्रीगुरु अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; }
        .header { background: #065f46; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .menu-bar { background: #044e38; display: flex; justify-content: center; gap: 6px; padding: 8px; flex-wrap: wrap; }
        .menu-btn { border: none; padding: 7px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; color: white; text-decoration: none; display: inline-block; }
        .menu-btn.active { background: #fde047 !important; color: #065f46 !important; }
        .container { max-width: 1300px; margin: 20px auto; padding: 0 10px; }
        .tab-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .btn { background: #059669; color: white; padding: 8px 15px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; font-size: 13px; }
        .btn-alt { background: #475569; color: white; padding: 6px 12px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; margin-right: 5px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
        th { background: #065f46; color: white; }
    </style>
    <script>
        function toggleAll(source) {
            checkboxes = document.getElementsByName('items');
            for(var i=0, n=checkboxes.length; i<n; i++) { checkboxes[i].checked = source.checked; }
        }
    </script>
</head>
<body>
<div class="header">
    <h2 style="margin:0;">🥗 मॅनेजर पोर्टल (मेस व कॅन्टीन विभाग)</h2>
    <div><a href="/logout" style="background:#ef4444; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px;">Logout</a></div>
</div>
<div class="menu-bar">
    <a href="/manager?tab=grocery" class="menu-btn {% if curr_tab == 'grocery' %}active{% endif %}" style="background:#059669;">🛒 ५०० वस्तू किराणा यादी</a>
    <a href="/manager?tab=canteen_att" class="menu-btn {% if curr_tab == 'canteen_att' %}active{% endif %}" style="background:#0284c7;">📋 कॅन्टीन स्टाफ हजेरी</a>
    <a href="/manager?tab=diet" class="menu-btn {% if curr_tab == 'diet' %}active{% endif %}" style="background:#6366f1;">🥗 मेस डाएट वेळापत्रक</a>
    <a href="/inquiries" class="menu-btn" style="background:#d97706;">📞 प्रवेश चौकशी डेस्क</a>
    <a href="/library" target="_blank" class="menu-btn" style="background:#7c3aed;">📚 स्टडी लॅब व लायब्ररी</a>
</div>
<div class="container">
    <div class="tab-box">
        {% if curr_tab == 'grocery' %}
        <h3 style="color:#065f46; margin-top:0;">🛒 कॅन्टीन व मेस खरेदी मास्टर यादी (५०० वस्तू)</h3>
        <form action="/print_grocery_slip" method="POST" target="_blank">
            <div style="margin-bottom:15px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                <button type="submit" class="btn">🖨️ पावती प्रिंट करा</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBox').checked = true; toggleAll(document.getElementById('selectAllBox'));">✅ सर्व निवडा</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBox').checked = false; toggleAll(document.getElementById('selectAllBox'));">❌ सर्व काढा</button>
                <label style="font-size:12px; font-weight:bold; margin-left:10px;"><input type="checkbox" id="selectAllBox" onchange="toggleAll(this)"> सर्व ऑन/ऑफ करा</label>
            </div>
            <table>
                <thead><tr><th style="width:40px; text-align:center;">निवड</th><th style="width:50px;">क्र.</th><th>साहित्याचे अचूक नाव (५०० मेनू)</th><th style="width:130px;">प्रमाण</th></tr></thead>
                <tbody>
                    {% for item in grocery_items %}
                    <tr>
                        <td style="text-align:center;"><input type="checkbox" name="items" value="{{ item }}"></td>
                        <td><b>{{ loop.index }}</b></td><td><b>{{ item }}</b></td>
                        <td><input type="text" name="qty_{{ item }}" value="लागेल तेवढे" style="padding:3px; width:120px;"></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <br><button type="submit" class="btn">🖨️ पावती प्रिंट करा</button>
        </form>
        {% elif curr_tab == 'canteen_att' %}
        <h3 style="color:#065f46; margin-top:0;">📋 कॅन्टीन स्टाफ हजेरी (सुरेखा ताई, सुनीता ताई इ.)</h3>
        <p>कॅन्टीन स्वयंपाकी व मदतनीस महिलांची सत्रनिहाय हजेरी व्यवस्थापन.</p>
        {% elif curr_tab == 'diet' %}
        <h3 style="color:#065f46; margin-top:0;">🥗 मेस डाएट वेळापत्रक</h3>
        <table><thead><tr><th>वार</th><th>सकाळ नाश्ता</th><th>दुपार जेवण</th><th>रात्र जेवण</th><th>विशेष आहार</th></tr></thead><tbody>
            {% for d in diet_list %}<tr><td><b>{{ d.day_name }}</b></td><td>{{ d.breakfast }}</td><td>{{ d.lunch }}</td><td>{{ d.dinner }}</td><td>{{ d.special_diet }}</td></tr>{% endfor %}
        </tbody></table>
        {% endif %}
    </div>
</div>
</body>
</html>'''

# ----------------- CLERK PORTAL (FULL TABS & 500 GROCERY) -----------------
CLERK_LAYOUT = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>क्लार्क डॅशबोर्ड - श्रीगुरु अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; }
        .header { background: #1e40af; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .menu-bar { background: #1e3a8a; display: flex; justify-content: center; gap: 6px; padding: 8px; flex-wrap: wrap; }
        .menu-btn { border: none; padding: 7px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; color: white; text-decoration: none; display: inline-block; }
        .menu-btn.active { background: #fde047 !important; color: #1e40af !important; }
        .container { max-width: 1300px; margin: 20px auto; padding: 0 10px; }
        .tab-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .btn { background: #2563eb; color: white; padding: 8px 15px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; font-size: 13px; }
        .btn-alt { background: #475569; color: white; padding: 6px 12px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; margin-right: 5px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
        th { background: #1e40af; color: white; }
    </style>
    <script>
        function toggleAll(source) {
            checkboxes = document.getElementsByName('items');
            for(var i=0, n=checkboxes.length; i<n; i++) { checkboxes[i].checked = source.checked; }
        }
    </script>
</head>
<body>
<div class="header">
    <h2 style="margin:0;">💼 क्लार्क पोर्टल (कार्यालय व किराणा नियोजन)</h2>
    <div><a href="/logout" style="background:#ef4444; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px;">Logout</a></div>
</div>
<div class="menu-bar">
    <a href="/clerk?tab=grocery" class="menu-btn {% if curr_tab == 'grocery' %}active{% endif %}" style="background:#2563eb;">🛒 ५०० वस्तू किराणा यादी</a>
    <a href="/clerk?tab=admission" class="menu-btn {% if curr_tab == 'admission' %}active{% endif %}" style="background:#059669;">📝 नवीन प्रवेश व फी</a>
    <a href="/clerk?tab=expenses" class="menu-btn {% if curr_tab == 'expenses' %}active{% endif %}" style="background:#dc2626;">💵 दैनिक खर्च नोंद</a>
    <a href="/inquiries" class="menu-btn" style="background:#d97706;">📞 चौकशी व कॉलिंग डेस्क</a>
    <a href="/library" target="_blank" class="menu-btn" style="background:#0284c7;">📚 लायब्ररी व स्टडी लॅब</a>
</div>
<div class="container">
    <div class="tab-box">
        {% if curr_tab == 'grocery' %}
        <h3 style="color:#1e40af; margin-top:0;">🛒 मेस व कॅन्टीन खरेदी मास्टर यादी (५०० वस्तू)</h3>
        <form action="/print_grocery_slip" method="POST" target="_blank">
            <div style="margin-bottom:15px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                <button type="submit" class="btn">🖨️ पावती प्रिंट करा</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBoxClerk').checked = true; toggleAll(document.getElementById('selectAllBoxClerk'));">✅ सर्व निवडा</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBoxClerk').checked = false; toggleAll(document.getElementById('selectAllBoxClerk'));">❌ सर्व काढा</button>
            </div>
            <table>
                <thead><tr><th style="width:40px; text-align:center;">निवड</th><th style="width:50px;">क्र.</th><th>साहित्याचे अचूक नाव (५०० मेनू)</th><th style="width:130px;">प्रमाण</th></tr></thead>
                <tbody>
                    {% for item in grocery_items %}
                    <tr>
                        <td style="text-align:center;"><input type="checkbox" name="items" value="{{ item }}"></td>
                        <td><b>{{ loop.index }}</b></td><td><b>{{ item }}</b></td>
                        <td><input type="text" name="qty_{{ item }}" value="लागेल तेवढे" style="padding:3px; width:120px;"></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <br><button type="submit" class="btn">🖨️ पावती प्रिंट करा</button>
        </form>
        {% elif curr_tab == 'admission' %}
        <h3 style="color:#1e40af; margin-top:0;">📝 नवीन विद्यार्थी प्रवेश नोंदणी</h3>
        <form action="/add_student" method="POST">
            <input type="text" name="name" placeholder="विद्यार्थ्याचे नाव" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="date" name="admission_date" value="{{ today_date }}" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="text" name="course" value="पोलीस भरती" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="text" name="phone" placeholder="मोबाईल नंबर" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="number" name="total_fees" placeholder="एकूण फी" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="number" name="paid_fees" placeholder="भरलेली फी" required style="width:100%; padding:8px; margin-bottom:15px;"><br>
            <button type="submit" class="btn">+ प्रवेश सेव्ह करा</button>
        </form>
        {% elif curr_tab == 'expenses' %}
        <h3 style="color:#1e40af; margin-top:0;">💵 दैनिक खर्च नोंदणी</h3>
        <form action="/add_expense" method="POST">
            <input type="date" name="exp_date" value="{{ today_date }}" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="text" name="category" placeholder="खर्चाचा प्रकार (उदा. भाजीपाला)" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="text" name="description" placeholder="तपशील" style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="number" name="amount" placeholder="रक्कम (₹)" required style="width:100%; padding:8px; margin-bottom:15px;"><br>
            <button type="submit" class="btn">+ खर्च सेव्ह करा</button>
        </form>
        {% endif %}
    </div>
</div>
</body>
</html>'''

# ----------------- PHYSICAL TRAINER PORTAL (FULL TABS + STOPWATCH) -----------------
TRAINER_LAYOUT = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>फिजिकल ट्रेनर डॅशबोर्ड - श्रीगुरु अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; }
        .header { background: #0284c7; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .menu-bar { background: #0369a1; display: flex; justify-content: center; gap: 6px; padding: 8px; flex-wrap: wrap; }
        .menu-btn { border: none; padding: 7px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; color: white; text-decoration: none; display: inline-block; }
        .menu-btn.active { background: #fde047 !important; color: #0284c7 !important; }
        .container { max-width: 1300px; margin: 20px auto; padding: 0 10px; }
        .tab-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .btn { background: #0284c7; color: white; padding: 8px 15px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; font-size: 13px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
        th { background: #0284c7; color: white; }
        input, select { padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px; width: 100%; margin-bottom: 8px; }
    </style>
    <script>
        let timer = null, seconds = 0, minutes = 0, hours = 0;
        function startStopwatch() { if (!timer) { timer = setInterval(runStopwatch, 1000); } }
        function pauseStopwatch() { clearInterval(timer); timer = null; }
        function resetStopwatch() { pauseStopwatch(); seconds = 0; minutes = 0; hours = 0; document.getElementById('stopwatchDisplay').innerText = "00:00:00"; document.getElementById('lapsList').innerHTML = ""; }
        function runStopwatch() {
            seconds++;
            if (seconds >= 60) { seconds = 0; minutes++; }
            if (minutes >= 60) { minutes = 0; hours++; }
            let h = hours < 10 ? "0" + hours : hours;
            let m = minutes < 10 ? "0" + minutes : minutes;
            let s = seconds < 10 ? "0" + seconds : seconds;
            document.getElementById('stopwatchDisplay').innerText = h + ":" + m + ":" + s;
        }
        function recordLap() {
            let timeText = document.getElementById('stopwatchDisplay').innerText;
            let li = document.createElement('li');
            li.innerText = "लॅप वेळ: " + timeText;
            document.getElementById('lapsList').appendChild(li);
        }
    </script>
</head>
<body>
<div class="header">
    <h2 style="margin:0;">🏃‍♂️ फिजिकल ट्रेनर पोर्टल (ग्राउंड विभाग)</h2>
    <div><a href="/logout" style="background:#ef4444; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px;">Logout</a></div>
</div>
<div class="menu-bar">
    <a href="/trainer?tab=physical" class="menu-btn {% if curr_tab == 'physical' %}active{% endif %}" style="background:#0284c7;">🏃‍♂️ फिजिकल टेस्ट रेकॉर्ड</a>
    <a href="/trainer?tab=stopwatch" class="menu-btn {% if curr_tab == 'stopwatch' %}active{% endif %}" style="background:#059669;">⏱️ डिजिटल स्टॉपवॉच</a>
    <a href="/library" target="_blank" class="menu-btn" style="background:#7c3aed;">📚 लायब्ररी व स्टडी लॅब</a>
</div>
<div class="container">
    <div class="tab-box">
        {% if curr_tab == 'physical' %}
        <h3 style="color:#0284c7; margin-top:0;">⚡ विद्यार्थ्यांचे फिजिकल गुण नोंदवा (1600m, 100m, गोळाफेक इ.)</h3>
        <form action="/trainer_save_physical" method="POST">
            <label>विद्यार्थी निवडा *:</label><select name="student_id" required><option value="">-- निवडा --</option>{% for s in students %}<option value="{{ s.id }}">{{ s.name }} ({{ s.course }})</option>{% endfor %}</select>
            <label>तारीख *:</label><input type="date" name="test_date" value="{{ today_date }}" required>
            <label>१६०० मीटर धावणे वेळ:</label><input type="text" name="run_time" placeholder="उदा. 05:10">
            <label>१०० मीटर स्प्रिंट वेळ:</label><input type="text" name="sprint_time" placeholder="उदा. 12.2 सेकंद">
            <label>गोळाफेक अंतर:</label><input type="text" name="shot_put_dist" placeholder="उदा. 24 फूट">
            <label>पुल-अप्स संख्या:</label><input type="number" name="pullups" value="0" min="0" max="10">
            <label>एकूण गुण (पैकी ५०):</label><input type="number" step="0.5" name="total_obtained" value="40" required>
            <br><button type="submit" class="btn">+ फिजिकल गुण सेव्ह करा</button>
        </form>
        {% elif curr_tab == 'stopwatch' %}
        <h3 style="color:#0284c7; margin-top:0;">⏱️ ग्राउंड डिजिटल स्टॉपवॉच (लॅप फिचरसह)</h3>
        <div style="text-align:center; background:#f0f9ff; padding:25px; border-radius:8px; border:2px solid #bae6fd;">
            <div id="stopwatchDisplay" style="font-size:48px; font-weight:bold; color:#0369a1; margin-bottom:15px; font-family:monospace;">00:00:00</div>
            <button onclick="startStopwatch()" style="background:#16a34a; color:white; padding:10px 20px; font-size:14px; font-weight:bold; border:none; border-radius:6px; cursor:pointer; margin-right:5px;">▶️ सुरू करा</button>
            <button onclick="pauseStopwatch()" style="background:#d97706; color:white; padding:10px 20px; font-size:14px; font-weight:bold; border:none; border-radius:6px; cursor:pointer; margin-right:5px;">⏸️ थांबा</button>
            <button onclick="recordLap()" style="background:#0284c7; color:white; padding:10px 20px; font-size:14px; font-weight:bold; border:none; border-radius:6px; cursor:pointer; margin-right:5px;">🚩 लॅप नोंदवा</button>
            <button onclick="resetStopwatch()" style="background:#dc2626; color:white; padding:10px 20px; font-size:14px; font-weight:bold; border:none; border-radius:6px; cursor:pointer;">🔄 रिसेट</button>
            <div style="margin-top:20px; text-align:left; max-width:300px; margin-left:auto; margin-right:auto;"><ul id="lapsList" style="font-size:14px; color:#334155;"></ul></div>
        </div>
        {% endif %}
    </div>
</div>
</body>
</html>'''

# ----------------- DETAILED REVIEW TEMPLATE -----------------
REVIEW_HTML = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>टेस्ट सविस्तर उत्तरपत्रिका व विश्लेषण - श्रीगुरु अकॅडमी</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #f8fafc; color: #1e293b; padding: 20px; margin: 0; }
        .container { max-width: 750px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #0b2545; text-align: center; }
        .score-card { background: #f0fdf4; border: 2px solid #86efac; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 25px; }
        .q-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .ans-tag { display: inline-block; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-top: 5px; }
        .correct-ans { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
        .wrong-ans { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
        .exp-box { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px; margin-top: 10px; font-size: 13px; color: #1e40af; border-radius: 0 6px 6px 0; }
    </style>
</head>
<body>
<div class="container">
    <h2>🎯 श्रीगुरु करिअर अकॅडमी - टेस्ट विश्लेषण (Answer Key & Review)</h2>
    <p style="text-align:center; color:#64748b; font-size:13px;">विद्यार्थ्याचे नाव: <b>{{ lead.student_name }}</b> | जिल्हा: <b>{{ lead.district }}</b> | टेस्ट: <b>{{ lead.test_name }}</b></p>
    
    <div class="score-card">
        <h3 style="margin:0; color:#166534; font-size:22px;">प्राप्त गुण: {{ lead.score }} / {{ lead.total_marks }}</h3>
        <p style="margin:5px 0 0; font-size:13px; color:#475569;">दिनांक: {{ lead.test_date }} | स्थिती: {{ lead.payment_status }}</p>
    </div>

    <h3 style="color:#0b3c5d; border-bottom:2px solid #cbd5e1; padding-bottom:5px;">📋 प्रश्न व स्पष्टीकरण तक्ता:</h3>
    
    {% for item in review_data %}
    <div class="q-box">
        <div style="font-weight:bold; font-size:15px; margin-bottom:8px;">प्र. {{ loop.index }}. {{ item.question }}</div>
        <div style="font-size:13px; color:#334155; line-height:1.5; margin-bottom:8px;">
            A) {{ item.opt_a }}<br>
            B) {{ item.opt_b }}<br>
            C) {{ item.opt_c }}<br>
            D) {{ item.opt_d }}
        </div>
        <div>
            <span style="font-size:12px; font-weight:bold;">विद्यार्थ्याचे उत्तर: </span>
            <span class="ans-tag {{ 'correct-ans' if item.is_correct else 'wrong-ans' }}">
                {{ item.user_ans or 'सोडवले नाही' }}
            </span>
            &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="font-size:12px; font-weight:bold;">अचूक उत्तर: </span>
            <span class="ans-tag correct-ans">{{ item.correct }}</span>
        </div>

        {% if item.explanation %}
        <div class="exp-box">
            <b>💡 स्पष्टीकरण (Explanation):</b> {{ item.explanation }}
        </div>
        {% endif %}
    </div>
    {% endfor %}

    <div style="text-align:center; margin-top:25px;">
        <a href="/test" style="background:#0284c7; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:14px;">🔄 नवीन टेस्ट पेजवर जा</a>
    </div>
</div>
</body>
</html>'''

# ----------------- SMART LOCKED TEST TEMPLATE -----------------
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
            <b style="color:#854d0e; font-size:16px;">💰 परीक्षा फी: ₹{{ current_test_fee }}</b><br>
            <img src="{{ qr_image_url }}" alt="QR" width="160" height="160" style="border:1px solid #ccc; border-radius:6px; background:white; padding:4px;"><br>
            <span style="font-size:13px; font-weight:bold;">UPI ID: {{ upi_id }}</span>
        </div>
        {% else %}
        <div style="background:#f0fdf4; border:1px solid #86efac; padding:10px; border-radius:6px; text-align:center; font-size:13px; color:#166534; margin-bottom:15px; font-weight:bold;">✨ ही टेस्ट पूर्णपणे **मोफत (Free)** आहे!</div>
        {% endif %}

        {% if error_msg %}<div style="background:#fee2e2; color:#991b1b; padding:8px; border-radius:4px; font-size:13px; font-weight:bold; margin-bottom:10px;">{{ error_msg }}</div>{% endif %}

        <form method="POST" action="/test">
            <input type="hidden" name="action_type" value="unlock_test">
            <input type="hidden" name="test_id" value="{{ current_test_id }}">
            <label style="font-weight:bold; font-size:13px;">विद्यार्थ्याचे पूर्ण नाव *:</label><input type="text" name="student_name" required>
            <label style="font-weight:bold; font-size:13px;">जिल्हा *:</label><input type="text" name="district" required>
            {% if current_test_fee|int > 0 %}
            <label style="font-weight:bold; font-size:13px;">UPI ट्रान्झॅक्शन नंबर *:</label><input type="text" name="upi_ref" required>
            {% endif %}
            <button type="submit" class="btn-submit" style="background:#0284c7; margin-top:10px;">🔓 प्रश्नपत्रिका ओपन करा</button>
        </form>
    </div>

    {% elif step == 'exam' %}
    <div style="background:#f0fdf4; border:1px solid #bbf7d0; padding:10px; border-radius:6px; margin-bottom:15px; font-size:13px; color:#166534;">
        👤 विद्यार्थी: <b>{{ session.get('exam_name') }}</b> | टेस्ट: <b>{{ current_test_title }}</b>
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
        <button type="submit" class="btn-submit">✅ टेस्ट सबमिट करा</button>
    </form>

    {% elif submitted %}
    <div class="cert-box">
        <h3 style="margin:0; color:#b45309; font-size:20px;">🏆 डिजिटल प्रशस्तीपत्र (Certificate of Participation)</h3>
        <p style="font-size:12px; color:#78350f; margin:5px 0 15px;">श्रीगुरु करिअर अकॅडमी, आडूर (ता. करवीर, जि. कोल्हापूर)</p>
        <hr style="border:1px solid #fde68a; margin:10px 0;">
        <p style="font-size:14px; color:#1e293b; line-height:1.6;">प्रमाणपत्र देण्यात येते की, श्री/सौ/कुमार <b>{{ name }}</b> (जिल्हा: {{ district }}) यांनी <b>{{ current_test_title }}</b> मध्ये सहभाग घेतला आहे.</p>
        <p style="font-size:13px; color:#92400e; font-weight:bold; margin-top:15px;">मा. सचिन चौगले सर व परिवार, श्रीगुरु करिअर अकॅडमी 🌟</p>
    </div>

    <div style="background:#fffbeb; border:2px dashed #f59e0b; padding:20px; border-radius:8px; margin-top:20px; text-align:center;">
        <h4 style="margin-top:0; color:#b45309; font-size:16px;">📊 गुण आणि सविस्तर स्पष्टीकरण लिंक हवी का?</h4>
        <form method="POST" action="/test">
            <input type="hidden" name="action_type" value="send_whatsapp_score">
            <input type="hidden" name="saved_name" value="{{ name }}">
            <input type="hidden" name="saved_district" value="{{ district }}">
            <input type="hidden" name="saved_score" value="{{ score }}">
            <input type="hidden" name="saved_total" value="{{ total }}">
            <input type="hidden" name="saved_upi_ref" value="{{ upi_ref }}">
            <input type="hidden" name="saved_test_name" value="{{ current_test_title }}">
            <input type="tel" name="whatsapp_phone" placeholder="१० अंकी WhatsApp नंबर" pattern="[6-9][0-9]{9}" required style="max-width:350px; margin:0 auto 10px; display:block; text-align:center; font-weight:bold;">
            <button type="submit" style="background:#25D366; color:white; border:none; padding:10px 20px; border-radius:6px; font-weight:bold; font-size:14px; cursor:pointer;">📲 WhatsApp वर लिंक मिळवा</button>
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

# ----------------- PUBLIC INQUIRY HTML -----------------
PUBLIC_INQUIRY_HTML = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>प्रवेश चौकशी</title></head>
<body style="font-family:sans-serif; background:#f1f5f9; padding:20px; display:flex; justify-content:center; align-items:center; height:100vh;">
<div style="background:white; padding:30px; border-radius:8px; width:100%; max-width:450px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
    <h2 style="color:#0b2545; text-align:center;">⚔️️ श्रीगुरु करिअर अकॅडमी</h2>
    {% if msg %}<div style="background:#dcfce7; color:#166534; padding:10px; border-radius:6px; margin-bottom:15px; text-align:center; font-weight:bold;">{{ msg }}</div>{% endif %}
    <form method="POST" action="/inquiry">
        <label>नाव:</label><input type="text" name="student_name" required style="width:100%; padding:8px; margin-bottom:10px;">
        <label>जिल्हा:</label><input type="text" name="district" required style="width:100%; padding:8px; margin-bottom:10px;">
        <label>फोन नंबर:</label><input type="tel" name="phone" required style="width:100%; padding:8px; margin-bottom:10px;">
        <label>कोर्स:</label><select name="course" style="width:100%; padding:8px; margin-bottom:15px;"><option value="महाराष्ट्र पोलीस भरती">महाराष्ट्र पोलीस भरती</option><option value="आर्मी भरती">आर्मी भरती</option></select>
        <button type="submit" style="width:100%; background:#059669; color:white; padding:10px; border:none; border-radius:6px; font-weight:bold;">📲 माहिती मिळवा</button>
    </form>
</div>
</body></html>'''

# ----------------- FLASK ROUTING -----------------
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
            error = "Invalid Password!" if lang == 'en' else "चुकीचा पासवर्ड!"
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
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mess_diet")
            diet_list = cur.fetchall()
    return render_template_string(MANAGER_LAYOUT, grocery_items=GROCERY_MASTER_500, curr_tab=curr_tab, diet_list=diet_list)

@app.route('/trainer')
def trainer_view():
    if session.get('user_role') != 'Trainer': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'physical')
    today_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students")
            students = cur.fetchall()
    return render_template_string(TRAINER_LAYOUT, students=students, today_date=today_date, curr_tab=curr_tab)

@app.route('/trainer_save_physical', methods=['POST'])
def trainer_save_physical():
    if session.get('user_role') != 'Trainer': return "Unauthorized", 403
    s_id, t_date, run, sprint, shot, pullups, tot = request.form.get('student_id'), request.form.get('test_date'), request.form.get('run_time'), request.form.get('sprint_time'), request.form.get('shot_put_dist'), safe_int(request.form.get('pullups', 0)), safe_float(request.form.get('total_obtained', 0))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO physical_tests (student_id, test_date, run_time, sprint_time, shot_put_dist, pullups, total_obtained, logged_by) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Trainer')", (s_id, t_date, run, sprint, shot, pullups, tot))
            conn.commit()
    return redirect('/trainer')

@app.route('/clerk')
def clerk_view():
    if session.get('user_role') != 'Clerk': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'grocery')
    today_date = date.today().strftime("%Y-%m-%d")
    return render_template_string(CLERK_LAYOUT, grocery_items=GROCERY_MASTER_500, curr_tab=curr_tab, today_date=today_date)

@app.route('/add_student', methods=['POST'])
def add_student():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    name, adm_date, course, phone, tot_fee, paid_fee = request.form.get('name'), request.form.get('admission_date'), request.form.get('course'), request.form.get('phone'), safe_float(request.form.get('total_fees')), safe_float(request.form.get('paid_fees'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO students (name, admission_date, course, phone, total_fees, paid_fees) VALUES (%s, %s, %s, %s, %s, %s)", (name, adm_date, course, phone, tot_fee, paid_fee))
            conn.commit()
    return redirect('/admin?tab=students')

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    exp_date, category, desc, amount = request.form.get('exp_date'), request.form.get('category'), request.form.get('description', ''), safe_float(request.form.get('amount'))
    role = session.get('user_role')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO expenses (exp_date, category, description, amount, logged_by) VALUES (%s, %s, %s, %s, %s)", (exp_date, category, desc, amount, role))
            conn.commit()
    return redirect('/admin?tab=exp' if role == 'Admin' else '/clerk')

@app.route('/assign_task', methods=['POST'])
def assign_task():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    target_role, task_text = request.form.get('target_role'), request.form.get('task_text')
    task_date = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO staff_tasks (target_role, task_text, task_date) VALUES (%s, %s, %s)", (target_role, task_text, task_date))
            conn.commit()
    return redirect('/admin?tab=tasks')

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'students')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    current_test_id = safe_int(request.args.get('test_id', 1), 1)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='test_launched'")
            test_launched = cur.fetchone()['value']
            cur.execute("SELECT value FROM settings WHERE key='upi_id'")
            upi_id = cur.fetchone()['value']
            cur.execute("SELECT value FROM settings WHERE key='qr_image_url'")
            qr_image_url = cur.fetchone()['value']

            cur.execute("SELECT * FROM test_papers ORDER BY id ASC")
            all_test_papers = cur.fetchall()
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id DESC", (current_test_id,))
            questions = cur.fetchall()

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
            cur.execute("SELECT * FROM mock_test_leads ORDER BY id DESC")
            pending_payments = cur.fetchall()

    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    total_expenses = sum(safe_float(ex['amount']) for ex in expenses_list)
    current_test_title = next((tp['test_title'] for tp in all_test_papers if tp['id'] == current_test_id), "मुख्य टेस्ट")
    test_fee = next((tp['test_fee'] for tp in all_test_papers if tp['id'] == current_test_id), 0)

    return render_template_string(ADMIN_DASHBOARD_LAYOUT, curr_tab=curr_tab, students=students, expenses_list=expenses_list, users_list=users_list, diet_list=diet_list, staff_members=staff_members, staff_tasks=staff_tasks, all_requests=all_requests, all_staff_logs=all_staff_logs, discipline_logs=discipline_logs, hostel_logs=hostel_logs, physical_records=physical_records, written_records=written_records, questions=questions, pending_payments=pending_payments, all_test_papers=all_test_papers, current_test_id=current_test_id, current_test_title=current_test_title, test_fee=test_fee, total_paid=total_paid, total_pending=total_pending, total_expenses=total_expenses, today_date=today_date, lang=lang, test_launched=test_launched, upi_id=upi_id, qr_image_url=qr_image_url)

@app.route('/toggle_test_launch', methods=['POST'])
def toggle_test_launch():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='test_launched'")
            current = cur.fetchone()['value']
            new_val = 'no' if current == 'yes' else 'yes'
            cur.execute("UPDATE settings SET value=%s WHERE key='test_launched'", (new_val,))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/update_test_settings', methods=['POST'])
def update_test_settings():
    if session.get('user_role') != 'Admin': return "Unauthorized", 403
    upi, qr = request.form.get('upi_id', '9921111960@ybl'), request.form.get('qr_image_url', '')
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

@app.route('/add_single_question', methods=['POST'])
def add_single_question():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    test_id = safe_int(request.form.get('test_id', 1), 1)
    q, a, b, c, d, corr, expl = request.form.get('question'), request.form.get('opt_a'), request.form.get('opt_b'), request.form.get('opt_c'), request.form.get('opt_d'), request.form.get('correct'), request.form.get('explanation', '')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (test_id, q, a, b, c, d, corr, expl))
            conn.commit()
    return redirect(f'/admin?tab=questions&test_id={test_id}')

@app.route('/add_bulk_questions', methods=['POST'])
def add_bulk_questions():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    test_id = safe_int(request.form.get('test_id', 1), 1)
    lines = request.form.get('bulk_text', '').strip().split('\n')
    with get_db() as conn:
        with conn.cursor() as cur:
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 6:
                    expl = parts[6] if len(parts) > 6 else ''
                    cur.execute("INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (test_id, parts[0], parts[1], parts[2], parts[3], parts[4], parts[5].upper(), expl))
            conn.commit()
    return redirect(f'/admin?tab=questions&test_id={test_id}')

@app.route('/delete_question/<int:id>')
def delete_question(id):
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
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
        s_name, dist, tal, phone, course, hostel = request.form.get('student_name'), request.form.get('district'), request.form.get('taluka', ''), request.form.get('phone'), request.form.get('course'), request.form.get('hostel_interest', 'होय')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO admission_inquiries (inquiry_date, student_name, district, taluka, phone, course, hostel_interest) VALUES (%s, %s, %s, %s, %s, %s, %s)", (date.today().strftime("%Y-%m-%d"), s_name, dist, tal, phone, course, hostel))
                conn.commit()
        msg = "तुमची नोंदणी यशस्वी झाली आहे!"
    return render_template_string(PUBLIC_INQUIRY_HTML, msg=msg)

@app.route('/test', methods=['GET', 'POST'])
def mock_test():
    current_test_id = safe_int(request.args.get('test_id', request.form.get('test_id', 1)), 1)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='test_launched'")
            launched = (cur.fetchone()['value'] == 'yes')
            cur.execute("SELECT value FROM settings WHERE key='upi_id'")
            upi_id = cur.fetchone()['value']
            cur.execute("SELECT value FROM settings WHERE key='qr_image_url'")
            qr_image_url = cur.fetchone()['value']
            cur.execute("SELECT * FROM test_papers ORDER BY id ASC")
            all_test_papers = cur.fetchall()
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (current_test_id,))
            questions = cur.fetchall()

    current_test_title = next((tp['test_title'] for tp in all_test_papers if tp['id'] == current_test_id), "मुख्य टेस्ट")
    current_test_fee = next((tp['test_fee'] for tp in all_test_papers if tp['id'] == current_test_id), 0)

    score, total, name, district, submitted, today_date, step, error_msg, upi_ref, user_answers = 0, len(questions), "", "", False, date.today().strftime("%d/%m/%Y"), "start", "", "Free", {}

    if session.get('exam_unlocked') == True and session.get('exam_test_id') == current_test_id:
        step = "exam"

    if request.method == 'POST' and launched:
        action = request.form.get('action_type')
        if action == 'unlock_test':
            name, district = request.form.get('student_name'), request.form.get('district')
            if safe_int(current_test_fee) > 0 and not request.form.get('upi_ref'):
                return render_template_string(MOCK_TEST_HTML, questions=questions, submitted=False, score=0, total=total, name=name, district=district, today_date=today_date, launched=launched, step="start", all_test_papers=all_test_papers, current_test_id=current_test_id, current_test_title=current_test_title, current_test_fee=current_test_fee, upi_id=upi_id, qr_image_url=qr_image_url, error_msg="❌ कृपया UPI ट्रान्झॅक्शन नंबर टाका!")
            session['exam_unlocked'] = True
            session['exam_test_id'] = current_test_id
            session['exam_name'] = name
            session['exam_district'] = district
            session['exam_upi_ref'] = request.form.get('upi_ref', 'Free') if safe_int(current_test_fee) > 0 else "Free"
            step = "exam"
        elif action == 'submit_test' and session.get('exam_unlocked') == True:
            name, district = session.get('exam_name'), session.get('exam_district')
            for q in questions:
                u_ans = request.form.get(f"q_{q['id']}")
                user_answers[str(q['id'])] = u_ans
                if u_ans and u_ans == q['correct']: score += 1
            submitted, step = True, "certificate_view"
            session['last_score'], session['last_total'], session['last_answers'] = score, total, user_answers
            session.pop('exam_unlocked', None)
        elif action == 'send_whatsapp_score':
            submitted, step = True, "whatsapp_sent"
            name, district, score, total, upi_ref, t_name, phone, ans_dict = request.form.get('saved_name'), request.form.get('saved_district'), safe_int(request.form.get('saved_score')), safe_int(request.form.get('saved_total')), request.form.get('saved_upi_ref', 'Free'), request.form.get('saved_test_name', current_test_title), request.form.get('whatsapp_phone', '').strip(), session.get('last_answers', {})
            if phone and re.match(r'^[6-9]\d{9}$', phone):
                pay_stat = 'Pending Verification' if safe_int(current_test_fee) > 0 else 'Approved'
                default_valid = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d") if safe_int(current_test_fee) > 0 else ""
                lead_id = 0
                try:
                    ans_json_str = json.dumps(ans_dict)
                    with get_db() as conn:
                        with conn.cursor() as cur:
                            cur.execute("INSERT INTO mock_test_leads (test_date, student_name, district, phone, score, total_marks, test_name, upi_ref, payment_status, valid_till, answers_json) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", 
                                        (date.today().strftime("%Y-%m-%d"), name, district, phone, score, total, t_name, upi_ref, pay_stat, default_valid, ans_json_str))
                            lead_id = cur.fetchone()['id']
                            conn.commit()
                except Exception as e: print(e)
                base_url = request.host_url.rstrip('/')
                review_link = f"{base_url}/view_result/{lead_id}" if lead_id > 0 else f"{base_url}/test"
                wa_text = f"नमस्कार {name} जी,%0Aश्रीगुरु अकॅडमी ({t_name}) निकाल:%0Aप्राप्त गुण: *{score}/{total}*%0Aजिल्हा: {district}%0Aस्पष्टीकरण पाहण्यासाठी लिंक:%0A{review_link}%0Aखूप खूप शुभेच्छा! संपर्क: ९९२११११९६०"
                wa_link = f"https://wa.me/91{phone}?text={wa_text}"
            else: step = "certificate_view"

    return render_template_string(MOCK_TEST_HTML, questions=questions, submitted=submitted, score=score, total=total, name=name, district=district, today_date=today_date, launched=launched, step=step, all_test_papers=all_test_papers, current_test_id=current_test_id, current_test_title=current_test_title, current_test_fee=current_test_fee, upi_id=upi_id, qr_image_url=qr_image_url, error_msg=error_msg, upi_ref=session.get('exam_upi_ref', 'Free'))

@app.route('/view_result/<int:lead_id>')
def view_result(lead_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
    if not lead: return "<h2 style='text-align:center;'>निकाल सापडला नाही.</h2>"
    ans_dict = json.loads(lead['answers_json']) if lead['answers_json'] else {}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM test_papers WHERE test_title=%s", (lead['test_name'],))
            tp = cur.fetchone()
            t_id = tp['id'] if tp else 1
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (t_id,))
            questions = cur.fetchall()
    review_data = [{'question': q['question'], 'opt_a': q['opt_a'], 'opt_b': q['opt_b'], 'opt_c': q['opt_c'], 'opt_d': q['opt_d'], 'correct': q['correct'], 'explanation': q['explanation'], 'user_ans': ans_dict.get(str(q['id']), '-'), 'is_correct': (ans_dict.get(str(q['id'])) == q['correct'])} for q in questions]
    return render_template_string(REVIEW_HTML, lead=lead, review_data=review_data)

@app.route('/inquiries')
def inquiry_desk():
    if session.get('user_role') not in ['Admin', 'Clerk', 'Manager']: return redirect(url_for('login'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM admission_inquiries ORDER BY id DESC")
            inquiries = cur.fetchall()
            cur.execute("SELECT * FROM mock_test_leads ORDER BY id DESC LIMIT 50")
            test_leads = cur.fetchall()
    return render_template_string('''<!DOCTYPE html><html lang="mr"><head><meta charset="UTF-8"><title>कॉलिंग डेस्क</title></head>
    <body style="font-family:sans-serif; padding:15px; background:#f8fafc;">
    <div style="background:#0b3c5d; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-radius:6px;">
        <h3 style="margin:0;">📞 प्रवेश चौकशी व टेस्ट कॉलिंग डेस्क</h3><a href="/" style="color:#ffdd59; text-decoration:none; font-weight:bold;">🏠 डॅशबोर्ड</a>
    </div>
    <h4 style="color:#0b3c5d; margin:15px 0 5px;">📋 प्रवेश चौकशी अर्ज ({{ inquiries|length }}):</h4>
    <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%; background:white; font-size:12px;">
    <tr style="background:#1e293b; color:white;"><th>नाव</th><th>जिल्हा</th><th>फोन</th><th>कोर्स</th><th>कृती</th></tr>
    {% for i in inquiries %}<tr><td><b>{{ i.student_name }}</b></td><td>{{ i.district }}</td><td><a href="tel:{{ i.phone }}">📞 {{ i.phone }}</a></td><td>{{ i.course }}</td><td><a href="https://wa.me/91{{ i.phone }}" target="_blank" style="background:#25D366; color:white; padding:3px 6px; border-radius:4px; text-decoration:none;">📲 WA</a></td></tr>{% endfor %}
    </table>
    <h4 style="color:#0b3c5d; margin:25px 0 5px;">📝 टेस्ट लीड्स ({{ test_leads|length }}):</h4>
    <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%; background:white; font-size:12px;">
    <tr style="background:#1e293b; color:white;"><th>नाव</th><th>जिल्हा</th><th>फोन</th><th>टेस्ट</th><th>गुण</th><th>कृती</th></tr>
    {% for t in test_leads %}<tr><td><b>{{ t.student_name }}</b></td><td>{{ t.district }}</td><td><a href="tel:{{ t.phone }}">📞 {{ t.phone }}</a></td><td>{{ t.test_name }}</td><td><b style="color:green;">{{ t.score }}/{{ t.total_marks }}</b></td><td><a href="https://wa.me/91{{ t.phone }}" target="_blank" style="background:#25D366; color:white; padding:3px 6px; border-radius:4px; text-decoration:none;">📲 WA</a></td></tr>{% endfor %}
    </table></body></html>''', inquiries=inquiries, test_leads=test_leads)

@app.route('/print_grocery_slip', methods=['POST'])
def print_grocery_slip():
    items = request.form.getlist('items')
    rows = "".join([f"<tr><td style='border:1px solid #333; padding:4px; text-align:center;'>{i+1}</td><td style='border:1px solid #333; padding:4px;'><b>{itm}</b></td><td style='border:1px solid #333; padding:4px;'>लागेल तेवढे</td><td style='border:1px solid #333; padding:4px; text-align:center;'>[  ]</td></tr>" for i, itm in enumerate(items)])
    html = f'''<!DOCTYPE html><html><head><title>किराणा पावती</title></head><body onload="window.print()" style="font-family:sans-serif; padding:15px;">
    <h2 style="text-align:center; color:#065f46;">श्रीगुरु करिअर अकॅडमी (मेस व कॅन्टीन)</h2>
    <p style="text-align:center; font-size:11px;">दिनांक: {date.today().strftime('%d/%m/%Y')} | एकूण साहित्य: {len(items)}</p>
    <table style="width:100%; border-collapse:collapse; font-size:11px;"><thead><tr style="background:#065f46; color:white;"><th style="border:1px solid #333; padding:4px;">क्र.</th><th style="border:1px solid #333; padding:4px;">साहित्याचे नाव</th><th style="border:1px solid #333; padding:4px;">प्रमाण</th><th style="border:1px solid #333; padding:4px;">तपासले</th></tr></thead>
    <tbody>{rows}</tbody></table></body></html>'''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

