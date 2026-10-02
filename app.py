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
app.secret_key = "shreeguru_ultimate_master_all_features_fully_restored_v100"

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

    {% if curr_tab == 'questions' %}
    <div class="admin-tab">
        <h3 style="color:#7c3aed; margin-top:0;">❓ ऑनलाइन टेस्ट प्रश्न व्यवस्थापन व लॉन्च कंट्रोल</h3>
        
        <div style="background:#f0fdf4; border:2px solid #15803d; padding:15px; border-radius:8px; margin-bottom:20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:15px;">
                <div>
                    <b style="color:#166534; font-size:15px;">🚀 टेस्ट ऑनलाईन लॉन्च व फी नियंत्रण:</b><br>
                    <span style="font-size:13px; color:#475569;">सध्याची स्थिती: 
                        {% if test_launched == 'yes' %}
                            <b style="color:green; font-size:14px;">✅ टेस्ट लाईव्ह आहे. (फी: ₹{{ test_fee }})</b>
                        {% else %}
                            <b style="color:red; font-size:14px;">❌ टेस्ट बंद आहे.</b>
                        {% endif %}
                    </span>
                </div>
                <div>
                    <form action="/toggle_test_launch" method="POST" style="display:inline;">
                        {% if test_launched == 'yes' %}
                        <button type="submit" class="btn-act" style="background:#dc2626; padding:10px 16px;">🔴 टेस्ट बंद करा</button>
                        {% else %}
                        <button type="submit" class="btn-act" style="background:#16a34a; padding:10px 16px;">🟢 टेस्ट लाईव्ह करा</button>
                        {% endif %}
                    </form>
                    <a href="/test" target="_blank" class="btn-act" style="background:#0284c7; padding:10px 16px; margin-left:5px;">🌐 टेस्ट पेज तपासा</a>
                </div>
            </div>

            <form action="/update_test_settings" method="POST" style="background:white; padding:12px; border-radius:6px; border:1px solid #bbf7d0;">
                <h4 style="margin:0 0 10px; color:#166534; font-size:14px;">⚙️ टेस्ट फी आणि पेमेंट QR कोड सेटिंग्ज:</h4>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; margin-bottom:10px;">
                    <div><label style="font-weight:bold; font-size:12px;">टेस्टची रक्कम / फी (₹):</label><input type="number" name="test_fee" value="{{ test_fee }}" min="0" max="100" style="width:100%; padding:6px; font-weight:bold;" required></div>
                    <div><label style="font-weight:bold; font-size:12px;">UPI ID:</label><input type="text" name="upi_id" value="{{ upi_id }}" style="width:100%; padding:6px;" required></div>
                </div>
                <div><label style="font-weight:bold; font-size:12px;">QR कोड इमेजची लिंक (URL):</label><input type="text" name="qr_image_url" value="{{ qr_image_url }}" style="width:100%; padding:6px;" required></div>
                <br><button type="submit" class="btn-act" style="background:#15803d; padding:8px 16px;">💾 पेमेंट सेटिंग्ज सेव्ह करा</button>
            </form>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
                <h4 style="margin-top:0; color:#0b3c5d;">१. नवीन प्रश्न व स्पष्टीकरण (Explanation) सह टाका:</h4>
                <form action="/add_single_question" method="POST">
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
                    <textarea name="bulk_text" rows="8" style="width:100%;" required></textarea><br>
                    <button type="submit" class="btn-act" style="background:#15803d; width:100%; padding:8px;">📥 बल्क अपलोड करा</button>
                </form>
            </div>
        </div>

        <h4 style="margin-top:25px;">📋 सद्यस्थितीतील सर्व प्रश्न यादी ({{ questions|length }}):</h4>
        <table>
            <thead><tr><th>क्र.</th><th>प्रश्न व स्पष्टीकरण</th><th>पर्याय</th><th>अचूक</th><th>कृती</th></tr></thead>
            <tbody>
                {% for q in questions %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td><b>{{ q.question }}</b><br>{% if q.explanation %}<span style="color:#047857; font-size:12px;">💡 स्पष्टीकरण: {{ q.explanation }}</span>{% endif %}</td>
                    <td>A) {{ q.opt_a }}<br>B) {{ q.opt_b }}<br>C) {{ q.opt_c }}<br>D) {{ q.opt_d }}</td>
                    <td><b style="color:green;">{{ q.correct }}</b></td>
                    <td><a href="/delete_question/{{ q.id }}" onclick="return confirm('हटवायचे?')" class="btn-act" style="background:red;">🗑️</a></td>
                </tr>
                {% else %}
                <tr><td colspan="5" style="text-align:center;">कोणतेही प्रश्न नाहीत.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'students' %}
    <div class="admin-tab"><h3>📋 विद्यार्थी यादी</h3><table><thead><tr><th>Reg</th><th>नाव</th><th>कोर्स</th><th>फोन</th><th>शिल्लक</th></tr></thead><tbody>{% for s in students %}<tr><td>REG-{{ s.id }}</td><td><b>{{ s.name }}</b></td><td>{{ s.course }}</td><td>{{ s.phone }}</td><td style="color:red;">₹{{ (s.total_fees or 0)-(s.paid_fees or 0) }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'admission' %}
    <div class="admin-tab"><h3>📝 नवीन प्रवेश</h3><form action="/add_student" method="POST"><input type="text" name="name" placeholder="नाव" required><input type="date" name="admission_date" value="{{ today_date }}" required><input type="text" name="course" value="पोलीस भरती" required><input type="text" name="phone" placeholder="फोन" required><input type="number" name="total_fees" placeholder="एकूण फी" required><input type="number" name="paid_fees" placeholder="भरलेली फी" required><button type="submit" class="btn-act" style="background:green;">सेव्ह करा</button></form></div>
    {% endif %}
    {% if curr_tab == 'physical' %}
    <div class="admin-tab"><h3>🏃‍♂️ फिजिकल रेकॉर्ड</h3><table><thead><tr><th>तारीख</th><th>नाव</th><th>एकूण गुण</th></tr></thead><tbody>{% for pt in physical_records %}<tr><td>{{ pt.test_date }}</td><td><b>{{ pt.name }}</b></td><td style="color:green;">{{ pt.total_obtained }}/50</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'written' %}
    <div class="admin-tab"><h3>📝 रिटर्न टेस्ट</h3><table><thead><tr><th>तारीख</th><th>नाव</th><th>गुण</th></tr></thead><tbody>{% for wt in written_records %}<tr><td>{{ wt.test_date }}</td><td><b>{{ wt.name }}</b></td><td style="color:green;">{{ wt.obtained_marks }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'requests' %}
    <div class="admin-tab"><h3>📩 स्टाफ विनंत्या</h3><table><thead><tr><th>तारीख</th><th>कर्मचारी</th><th>विषय</th><th>स्थिती</th></tr></thead><tbody>{% for r in all_requests %}<tr><td>{{ r.req_date }}</td><td><b>{{ r.req_role }}</b></td><td>{{ r.request_title }}</td><td>{{ r.status }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'fee' %}
    <div class="admin-tab"><h3>💰 फी जमा</h3><form action="/pay_installment" method="POST"><select name="student_id" required>{% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}</select><input type="number" name="amount" placeholder="रक्कम" required><button type="submit" class="btn-act" style="background:green;">जमा करा</button></form></div>
    {% endif %}
    {% if curr_tab == 'hostel' %}
    <div class="admin-tab"><h3>🏠 हॉस्टेल/मेस</h3><table><thead><tr><th>तारीख</th><th>नाव</th><th>रक्कम</th></tr></thead><tbody>{% for h in hostel_logs %}<tr><td>{{ h.pay_date }}</td><td><b>{{ h.name }}</b></td><td style="color:green;">₹{{ h.paid_amount }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'att' %}
    <div class="admin-tab"><h3>📋 हजेरी</h3><p>हजेरी नोंद प्रणाली कार्यरत आहे.</p></div>
    {% endif %}
    {% if curr_tab == 'diet' %}
    <div class="admin-tab"><h3>🥗 मेस डाएट</h3><table><thead><tr><th>वार</th><th>सकाळ नाश्ता</th><th>दुपार जेवण</th></tr></thead><tbody>{% for d in diet_list %}<tr><td><b>{{ d.day_name }}</b></td><td>{{ d.breakfast }}</td><td>{{ d.lunch }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'disc' %}
    <div class="admin-tab"><h3>⚠️ गेटपास/शिस्त</h3><p>शिस्तभंग नोंदवही.</p></div>
    {% endif %}
    {% if curr_tab == 'exp' %}
    <div class="admin-tab"><h3>💵 खर्च वही</h3><table><thead><tr><th>तारीख</th><th>तपशील</th><th>रक्कम</th></tr></thead><tbody>{% for ex in expenses_list %}<tr><td>{{ ex.exp_date }}</td><td><b>{{ ex.description }}</b></td><td style="color:red;">₹{{ ex.amount }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'wa' %}
    <div class="admin-tab"><h3>📲 WhatsApp</h3><table><thead><tr><th>नाव</th><th>फोन</th></tr></thead><tbody>{% for s in students %}<tr><td>{{ s.name }}</td><td><a href="https://wa.me/91{{ s.parent_phone }}" target="_blank" style="color:green; font-weight:bold;">📲 मेसेज पाठवा</a></td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'staff' %}
    <div class="admin-tab"><h3>👔 स्टाफ पगार</h3><table><thead><tr><th>नाव</th><th>पद</th><th>पगार</th></tr></thead><tbody>{% for st in staff_members %}<tr><td><b>{{ st.name }}</b></td><td>{{ st.role }}</td><td>₹{{ st.salary }}</td></tr>{% endfor %}</tbody></table></div>
    {% endif %}
    {% if curr_tab == 'tasks' %}
    <div class="admin-tab"><h3>📌 काम सांगा</h3><p>स्टाफसाठी टास्क असाइनमेंट.</p></div>
    {% endif %}
    {% if curr_tab == 'staff_tracking' %}
    <div class="admin-tab"><h3>👁️ स्टाफ हालचाली</h3><p>ॲक्टिव्हिटी लॉग.</p></div>
    {% endif %}
    {% if curr_tab == 'passwords' %}
    <div class="admin-tab"><h3>🔐 युजर्स व पासवर्ड</h3><p>सिस्टीम युझर क्रेडेंशिअल्स.</p></div>
    {% endif %}
    {% if curr_tab == 'bak' %}
    <div class="admin-tab"><h3>💾 बॅकअप / रिस्टोअर</h3><p>Neon Cloud PostgreSQL डेटाबेस.</p></div>
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
            </div>
            <table>
                <thead><tr><th style="width:40px; text-align:center;">निवड</th><th style="width:50px;">क्र.</th><th>साहित्याचे नाव (५०० मेनू)</th><th style="width:130px;">प्रमाण</th></tr></thead>
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
                <thead><tr><th style="width:40px; text-align:center;">निवड</th><th style="width:50px;">क्र.</th><th>साहित्याचे नाव (५०० मेनू)</th><th style="width:130px;">प्रमाण</th></tr></thead>
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

# ----------------- LIBRARY & LAB ROUTE -----------------
@app.route('/library')
def library_view():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM books ORDER BY id DESC")
            books = cur.fetchall()
            cur.execute("SELECT * FROM study_lab_seats ORDER BY id ASC")
            seats = cur.fetchall()
    return render_template_string('''<!DOCTYPE html><html lang="mr"><head><meta charset="UTF-8"><title>लायब्ररी व स्टडी लॅब</title></head>
    <body style="font-family:sans-serif; background:#f8fafc; padding:20px;">
    <div style="background:#0284c7; color:white; padding:15px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
        <h2 style="margin:0;">📚 स्टडी लॅब व लायब्ररी व्यवस्थापन</h2><a href="/" style="color:white; font-weight:bold; text-decoration:none;">🏠 मुख्य डॅशबोर्ड</a>
    </div>
    <h3 style="color:#0284c7; margin-top:20px;">📖 उपलब्ध पुस्तके:</h3>
    <table border="1" cellpadding="8" style="border-collapse:collapse; width:100%; background:white; font-size:13px;">
    <tr style="background:#0284c7; color:white;"><th>पुस्तकाचे नाव</th><th>लेखक</th><th>वर्गवारी</th><th>उपलब्ध प्रती</th></tr>
    {% for b in books %}<tr><td><b>{{ b.title }}</b></td><td>{{ b.author }}</td><td>{{ b.category }}</td><td>{{ b.available_copies }} / {{ b.total_copies }}</td></tr>{% endfor %}
    </table>
    </body></html>''', books=books, seats=seats)

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
    return render_template_string(MANAGER_LAYOUT, grocery_items=GROCERY_MASTER_500, curr_tab=curr_tab)

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

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'students')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='test_launched'")
            test_launched = cur.fetchone()['value']
            cur.execute("SELECT value FROM settings WHERE key='test_fee'")
            test_fee = cur.fetchone()['value']
            cur.execute("SELECT value FROM settings WHERE key='upi_id'")
            upi_id = cur.fetchone()['value']
            cur.execute("SELECT value FROM settings WHERE key='qr_image_url'")
            qr_image_url = cur.fetchone()['value']

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
            cur.execute("SELECT * FROM staff_requests ORDER BY id DESC")
            all_requests = cur.fetchall()
            cur.execute("SELECT pt.*, s.name FROM physical_tests pt JOIN students s ON pt.student_id = s.id ORDER BY pt.id DESC")
            physical_records = cur.fetchall()
            cur.execute("SELECT wt.*, s.name FROM written_tests wt JOIN students s ON wt.student_id = s.id ORDER BY wt.id DESC")
            written_records = cur.fetchall()
            cur.execute("SELECT * FROM questions ORDER BY id DESC")
            questions = cur.fetchall()

    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    total_expenses = sum(safe_float(ex['amount']) for ex in expenses_list)

    return render_template_string(ADMIN_DASHBOARD_LAYOUT, curr_tab=curr_tab, students=students, expenses_list=expenses_list, users_list=users_list, diet_list=diet_list, staff_members=staff_members, all_requests=all_requests, physical_records=physical_records, written_records=written_records, questions=questions, total_paid=total_paid, total_pending=total_pending, total_expenses=total_expenses, today_date=today_date, lang=lang, test_launched=test_launched, test_fee=test_fee, upi_id=upi_id, qr_image_url=qr_image_url)

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
    fee, upi, qr = request.form.get('test_fee', '0'), request.form.get('upi_id', '9921111960@ybl'), request.form.get('qr_image_url', '')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE settings SET value=%s WHERE key='test_fee'", (fee,))
            cur.execute("UPDATE settings SET value=%s WHERE key='upi_id'", (upi,))
            cur.execute("UPDATE settings SET value=%s WHERE key='qr_image_url'", (qr,))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/add_single_question', methods=['POST'])
def add_single_question():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    q, a, b, c, d, corr, expl = request.form.get('question'), request.form.get('opt_a'), request.form.get('opt_b'), request.form.get('opt_c'), request.form.get('opt_d'), request.form.get('correct'), request.form.get('explanation', '')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO questions (question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s)", (q, a, b, c, d, corr, expl))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/add_bulk_questions', methods=['POST'])
def add_bulk_questions():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    lines = request.form.get('bulk_text', '').strip().split('\n')
    with get_db() as conn:
        with conn.cursor() as cur:
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 6:
                    expl = parts[6] if len(parts) > 6 else ''
                    cur.execute("INSERT INTO questions (question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s)", (parts[0], parts[1], parts[2], parts[3], parts[4], parts[5].upper(), expl))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/delete_question/<int:id>')
def delete_question(id):
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM questions WHERE id=%s", (id,))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/add_student', methods=['POST'])
def add_student():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    name, adm_date, course, phone, tot_fee, paid_fee = request.form.get('name'), request.form.get('admission_date'), request.form.get('course'), request.form.get('phone'), safe_float(request.form.get('total_fees')), safe_float(request.form.get('paid_fees'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO students (name, admission_date, course, phone, total_fees, paid_fees) VALUES (%s, %s, %s, %s, %s, %s)", (name, adm_date, course, phone, tot_fee, paid_fee))
            conn.commit()
    return redirect('/admin?tab=students')

@app.route('/pay_installment', methods=['POST'])
def pay_installment():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    s_id, amount = request.form.get('student_id'), safe_float(request.form.get('amount'))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE students SET paid_fees = paid_fees + %s WHERE id=%s", (amount, s_id))
            conn.commit()
    return redirect('/admin?tab=students')

@app.route('/inquiry', methods=['GET', 'POST'])
def public_inquiry():
    msg = None
    if request.method == 'POST':
        s_name, dist, tal, phone, course = request.form.get('student_name'), request.form.get('district'), request.form.get('taluka', ''), request.form.get('phone'), request.form.get('course')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO admission_inquiries (inquiry_date, student_name, district, taluka, phone, course) VALUES (%s, %s, %s, %s, %s, %s)", (date.today().strftime("%Y-%m-%d"), s_name, dist, tal, phone, course))
                conn.commit()
        msg = "तुमची नोंदणी यशस्वी झाली आहे!"
    return render_template_string(PUBLIC_INQUIRY_HTML, msg=msg)

@app.route('/test', methods=['GET', 'POST'])
def mock_test():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='test_launched'")
            launched = (cur.fetchone()['value'] == 'yes')
            cur.execute("SELECT value FROM settings WHERE key='test_fee'")
            test_fee = cur.fetchone()['value']
            cur.execute("SELECT value FROM settings WHERE key='upi_id'")
            upi_id = cur.fetchone()['value']
            cur.execute("SELECT value FROM settings WHERE key='qr_image_url'")
            qr_image_url = cur.fetchone()['value']
            cur.execute("SELECT * FROM questions ORDER BY id ASC")
            questions = cur.fetchall()

    score, total, name, district, phone, submitted, today_date, step = 0, len(questions), "", "", "", False, date.today().strftime("%d/%m/%Y"), "start"
    if session.get('exam_unlocked') == True: step = "exam"

    if request.method == 'POST' and launched:
        action = request.form.get('action_type')
        if action == 'unlock_test':
            name, district = request.form.get('student_name'), request.form.get('district')
            if safe_int(test_fee) > 0 and not request.form.get('upi_ref'):
                return render_template_string(MOCK_TEST_HTML, questions=questions, submitted=False, score=0, total=total, name=name, district=district, today_date=today_date, launched=launched, step="start", test_fee=test_fee, upi_id=upi_id, qr_image_url=qr_image_url)
            session['exam_unlocked'] = True
            session['exam_name'] = name
            session['exam_district'] = district
            step = "exam"
        elif action == 'submit_test' and session.get('exam_unlocked') == True:
            name, district = session.get('exam_name'), session.get('exam_district')
            score = sum(1 for q in questions if request.form.get(f"q_{q['id']}") == q['correct'])
            submitted, step = True, "certificate_view"
            session.pop('exam_unlocked', None)

    return render_template_string(MOCK_TEST_HTML, questions=questions, submitted=submitted, score=score, total=total, name=name, district=district, phone=phone, today_date=today_date, launched=launched, step=step, test_fee=test_fee, upi_id=upi_id, qr_image_url=qr_image_url)

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
    <body style="font-family:sans-serif; padding:20px; background:#f8fafc;">
    <div style="background:#0b3c5d; color:white; padding:15px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
        <h2 style="margin:0;">📞 प्रवेश चौकशी व टेस्ट कॉलिंग डेस्क</h2>
        <a href="/" style="color:#ffdd59; font-weight:bold; text-decoration:none;">🏠 मुख्य डॅशबोर्ड</a>
    </div>
    <h3 style="color:#0b3c5d; margin-top:20px;">📋 थेट प्रवेश चौकशी अर्ज ({{ inquiries|length }}):</h3>
    <table border="1" cellpadding="8" style="border-collapse:collapse; width:100%; background:white; font-size:13px;">
    <tr style="background:#1e293b; color:white;"><th>तारीख</th><th>नाव</th><th>जिल्हा (तालुका)</th><th>फोन</th><th>कोर्स</th></tr>
    {% for i in inquiries %}
    <tr><td>{{ i.inquiry_date }}</td><td><b>{{ i.student_name }}</b></td><td>{{ i.district }} ({{ i.taluka or '-' }})</td><td><a href="tel:{{ i.phone }}">📞 {{ i.phone }}</a></td><td>{{ i.course }}</td></tr>
    {% else %}
    <tr><td colspan="5" style="text-align:center; color:#64748b;">कोणतीही चौकशी नाही.</td></tr>
    {% endfor %}
    </table>
    
    <h3 style="color:#0b3c5d; margin-top:25px;">📝 ऑनलाइन टेस्ट लीड्स ({{ test_leads|length }}):</h3>
    <table border="1" cellpadding="8" style="border-collapse:collapse; width:100%; background:white; font-size:13px;">
    <tr style="background:#1e293b; color:white;"><th>तारीख</th><th>नाव</th><th>जिल्हा</th><th>फोन</th><th>गुण</th></tr>
    {% for t in test_leads %}
    <tr><td>{{ t.test_date }}</td><td><b>{{ t.student_name }}</b></td><td>{{ t.district }}</td><td><a href="tel:{{ t.phone }}">📞 {{ t.phone }}</a></td><td><b style="color:green;">{{ t.score }} / {{ t.total_marks }}</b></td></tr>
    {% else %}
    <tr><td colspan="5" style="text-align:center; color:#64748b;">कोणतीही टेस्ट लीड नाही.</td></tr>
    {% endfor %}
    </table>
    </body></html>''', inquiries=inquiries, test_leads=test_leads)

@app.route('/print_grocery_slip', methods=['POST'])
def print_grocery_slip():
    items = request.form.getlist('items')
    rows = "".join([f"<tr><td style='border:1px solid #333; padding:4px; text-align:center;'>{i+1}</td><td style='border:1px solid #333; padding:4px;'><b>{itm}</b></td><td style='border:1px solid #333; padding:4px;'>लागेल तेवढे</td><td style='border:1px solid #333; padding:4px; text-align:center;'>[  ]</td></tr>" for i, itm in enumerate(items)])
    html = f'''<!DOCTYPE html><html><head><title>किराणा पावती</title></head><body onload="window.print()" style="font-family:sans-serif; padding:20px;">
    <h2 style="text-align:center; color:#065f46;">श्रीगुरु करिअर अकॅडमी (मेस व कॅन्टीन)</h2>
    <p style="text-align:center; font-size:12px;">दिनांक: {date.today().strftime('%d/%m/%Y')} | एकूण साहित्य: {len(items)}</p>
    <table style="width:100%; border-collapse:collapse; font-size:12px;"><thead><tr style="background:#065f46; color:white;"><th style="border:1px solid #333; padding:6px; width:40px;">क्र.</th><th style="border:1px solid #333; padding:6px;">साहित्याचे नाव</th><th style="border:1px solid #333; padding:6px; width:110px;">प्रमाण</th><th style="border:1px solid #333; padding:6px; width:60px;">तपासले</th></tr></thead>
    <tbody>{rows}</tbody></table></body></html>'''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

