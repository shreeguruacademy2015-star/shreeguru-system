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
app.secret_key = "shreeguru_complete_bulletproof_v53_onscreen_cert"

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
    "टॉयलेट क्लिनर (हार्पिक)", "काच पुसण्याचा लिक्विड", "हॅन्ड वॉश लिक्विड रिफिल", "नॅप्थालीन बॉल्स (फिनाइल गोळ्या)", "कचऱ्याच्या मोठ्या पिशव्या",
    "सुती कापडी नॅपकिन्स", "पोळे पुसण्याचे मॉप", "झोपडी झाडू (सॉफ्ट)", "रफ झाडू (बाहेरसाठी)", "फ्लोअर वायपर",
    "एल्युमिनियम फॉइल पेपर", "बटर पेपर रोल", "प्लास्टिक फूड रॅप", "कागदी पत्रावळी (Eco)", "द्रोण (कागदी)",
    "डिस्पोजेबल पाण्याचे ग्लास", "चहाचे पेपर कप", "प्लास्टिक चमचे", "झिपर पिशव्या", "प्लास्टिक बरण्या/डबे",
    "एल्युमिनियम पार्सल बॉक्स", "ताट झाकण्याच्या जाळ्या", "कमर्शियल गॅस सिलिंडर", "गॅस लायटर", "काडेपेटी बॉक्स",
    "पिण्याच्या पाचे जार", "स्टील ताटे (मेस)", "स्टील वाट्या", "स्टील ग्लास", "स्टील चमचे",
    "चपाती हॉट केस / कॅसरोल", "मोठे एल्युमिनियम हंडे", "भाजीचे मोठे उलथणे", "स्टील चाळणी", "प्लास्टिक बाल्टी व मग",
    "उंदराचे औषध / स्प्रे", "मच्छर रिपेलेंट कॉइल", "फर्स्ट एड बॉक्स (मेस)", "अग्निशामक यंत्र (Fire Ext.)", "डायनिंग टेबल कव्हर",
    "हँडवॉश पेपर सोप", "टूथपिक बॉक्स", "बडीशेप व खडीसाखर जार", "तिश्यू पेपर नॅपकिन्स", "कचराकुंडी (Dustbins)",
    "मीठ (अतिरिक्त साठा)", "साखर (अतिरिक्त साठा)", "चहा पत्ती (बल्क)", "कॉफी पावडर (बल्क)", "लोणचे जार (मोठे)",
    "टोमॅटो सॉस (मोठी बॉटल)", "ग्रीन चिली सॉस", "सोया सॉस (बल्क)", "विनेगर (Sirka)", "शेजवान चटणी (जार)",
    "टोमॅटो प्युरी टिन", "गुलाब जामुन मिक्स", "कस्टर्ड पावडर (बल्क)", "पास्ता मसाला प्युरी", "मध (Honey Jar)",
    "ग्लुकोज डी पावडर", "ओआरएस पॅकेट्स", "ग्रीन टी बॅग्ज", "पीनट बटर जार", "डार्क चॉकलेट्स",
    "राजगिरा लाडू", "शेंगदाणा चिक्की", "खोबरे-गूळ वडी", "मेसचे अतिरिक्त कापड", "कॅन्टीन स्टेशनरी",
    "अतिरिक्त कॅन्टीन साहित्य #496", "अतिरिक्त कॅन्टीन साहित्य #497", "अतिरिक्त कॅन्टीन साहित्य #498", "अतिरिक्त कॅन्टीन साहित्य #499", "अतिरिक्त कॅन्टीन साहित्य #500"
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
        <h3 style="color:#7c3aed; margin-top:0;">❓ ऑनलाइन टेस्ट प्रश्न व्यवस्थापन व लॉन्च कंट्रोल (Admin Only)</h3>
        
        <div style="background:#f0fdf4; border:2px solid #15803d; padding:15px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
                <b style="color:#166534; font-size:15px;">🚀 टेस्ट ऑनलाईन लॉन्च स्टेटस (Test Launch Control):</b><br>
                <span style="font-size:13px; color:#475569;">सध्याची स्थिती: 
                    {% if test_launched == 'yes' %}
                        <b style="color:green; font-size:14px;">✅ टेस्ट लाईव्ह (Launched) आहे. विद्यार्थी सोडवू शकतात.</b>
                    {% else %}
                        <b style="color:red; font-size:14px;">❌ टेस्ट बंद (Unlaunched) आहे. प्रश्न टाकून झाल्यावरच लॉन्च करा.</b>
                    {% endif %}
                </span>
            </div>
            <div>
                <form action="/toggle_test_launch" method="POST" style="display:inline;">
                    {% if test_launched == 'yes' %}
                    <button type="submit" class="btn-act" style="background:#dc2626; padding:10px 16px; font-size:13px;">🔴 टेस्ट बंद करा (Unlaunch)</button>
                    {% else %}
                    <button type="submit" class="btn-act" style="background:#16a34a; padding:10px 16px; font-size:13px;">🟢 टेस्ट लाईव्ह करा (Launch Test)</button>
                    {% endif %}
                </form>
                <a href="/test" target="_blank" class="btn-act" style="background:#0284c7; padding:10px 16px; font-size:13px; margin-left:5px;">🌐 टेस्ट पेज तपासा</a>
            </div>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
                <h4 style="margin-top:0; color:#0b3c5d;">१. नवीन प्रश्न मॅन्युअल टाईप करा:</h4>
                <form action="/add_single_question" method="POST">
                    <label>प्रश्न:</label>
                    <textarea name="question" required style="width:100%; height:60px;" placeholder="प्रश्नाचा मजकूर..."></textarea>
                    
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
                        <div> पर्याय A: <input type="text" name="opt_a" required style="width:100%;"></div>
                        <div> पर्याय B: <input type="text" name="opt_b" required style="width:100%;"></div>
                        <div> पर्याय C: <input type="text" name="opt_c" required style="width:100%;"></div>
                        <div> पर्याय D: <input type="text" name="opt_d" required style="width:100%;"></div>
                    </div><br>
                    <label>अचूक पर्याय (Correct Option):</label>
                    <select name="correct" style="width:100%; padding:6px;">
                        <option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option>
                    </select><br><br>
                    <button type="submit" class="btn-act" style="background:#7c3aed; width:100%; padding:8px;">+ प्रश्न सेव्ह करा</button>
                </form>
            </div>

            <div style="background:#f0fdf4; padding:15px; border-radius:6px; border:1px solid #bbf7d0;">
                <h4 style="margin-top:0; color:#15803d;">२. बल्क प्रश्न (Bulk Copy-Paste):</h4>
                <p style="font-size:12px; color:#475569;">एका ओळीत: <br><code>प्रश्न | पर्यायA | पर्यायB | पर्यायC | पर्यायD | अचूक (A/B/C/D)</code></p>
                <form action="/add_bulk_questions" method="POST">
                    <textarea name="bulk_text" rows="8" placeholder="महाराष्ट्राची राजधानी कोणती? | पुणे | मुंबई | नागपूर | नाशिक | B" style="width:100%;" required></textarea><br>
                    <button type="submit" class="btn-act" style="background:#15803d; width:100%; padding:8px;">📥 सर्व प्रश्न बल्कमध्ये अपलोड करा</button>
                </form>
            </div>
        </div>

        <h4 style="margin-top:25px;">📋 सद्यस्थितीतील सर्व प्रश्न यादी ({{ questions|length }} प्रश्न):</h4>
        <table>
            <thead><tr><th>क्र.</th><th>प्रश्न</th><th>पर्याय A, B, C, D</th><th>अचूक</th><th>कृती</th></tr></thead>
            <tbody>
                {% for q in questions %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td><b>{{ q.question }}</b></td>
                    <td>A) {{ q.opt_a }}<br>B) {{ q.opt_b }}<br>C) {{ q.opt_c }}<br>D) {{ q.opt_d }}</td>
                    <td><b style="color:green;">{{ q.correct }}</b></td>
                    <td><a href="/delete_question/{{ q.id }}" onclick="return confirm('हा प्रश्न हटवायचा?')" class="btn-act" style="background:red;">🗑️</a></td>
                </tr>
                {% else %}
                <tr><td colspan="5" style="text-align:center; color:#64748b;">कोणतेही प्रश्न उपलब्ध नाहीत.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'students' %}
    <div class="admin-tab">
        <h3 style="margin:0;">📋 विद्यार्थी यादी</h3>
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
    <div class="admin-tab">
        <h3 style="color:#0284c7; margin-top:0;">🏃‍♂️ फिजिकल टेस्ट रेकॉर्ड</h3>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>कोर्स</th><th>1600m</th><th>100m</th><th>गोळा</th><th>पुल-अप्स</th><th>एकूण</th></tr></thead>
            <tbody>
                {% for pt in physical_records %}
                <tr><td>{{ pt.test_date }}</td><td><b>{{ pt.name }}</b></td><td>{{ pt.course }}</td><td>{{ pt.run_time }}</td><td>{{ pt.sprint_time }}</td><td>{{ pt.shot_put_dist }}</td><td>{{ pt.pullups }}</td><td><b style="color:green;">{{ pt.total_obtained }}/50</b></td></tr>
                {% else %}<tr><td colspan="8">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'written' %}
    <div class="admin-tab">
        <h3 style="color:#10b981; margin-top:0;">📝 रिटर्न टेस्ट रेकॉर्ड</h3>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>परीक्षा</th><th>एकूण</th><th>मिळालेले गुण</th></tr></thead>
            <tbody>
                {% for wt in written_records %}
                <tr><td>{{ wt.test_date }}</td><td><b>{{ wt.name }}</b></td><td>{{ wt.test_name }}</td><td>{{ wt.total_marks }}</td><td><b style="color:green;">{{ wt.obtained_marks }}</b></td></tr>
                {% else %}<tr><td colspan="5">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'requests' %}
    <div class="admin-tab">
        <h3 style="color:#e11d48; margin-top:0;">📩 स्टाफ विनंत्या</h3>
        <table>
            <thead><tr><th>तारीख</th><th>कर्मचारी</th><th>विषय</th><th>तपशील</th><th>स्थिती</th></tr></thead>
            <tbody>
                {% for req in all_requests %}
                <tr><td>{{ req.req_date }}</td><td><b>{{ req.req_role }}</b></td><td><b>{{ req.request_title }}</b></td><td>{{ req.request_details }}</td><td><b>{{ req.status }}</b></td></tr>
                {% else %}<tr><td colspan="5">नोंद नाही.</td></tr>{% endfor %}
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
        <h3>🏠 हॉस्टेल व मेस फी नोंद</h3>
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
        <h3>📋 हजेरी नोंद</h3>
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
        <h3 style="color:#6366f1;">🥗 मेस डाएट वेळापत्रक</h3>
        <table>
            <thead><tr><th>वार</th><th>सकाळ नाश्ता</th><th>दुपार जेवण</th><th>रात्र जेवण</th><th>विशेष आहार</th></tr></thead>
            <tbody>
                {% for d in diet_list %}
                <tr><td><b>{{ d.day_name }}</b></td><td>{{ d.breakfast }}</td><td>{{ d.lunch }}</td><td>{{ d.dinner }}</td><td>{{ d.special_diet }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'disc' %}
    <div class="admin-tab">
        <h3 style="color:#6b21a8; margin-top:0;">⚠️ गेटपास व शिस्तभंग नोंद</h3>
        <table>
            <thead><tr><th>तारीख</th><th>नाव</th><th>प्रकार</th><th>कारण</th></tr></thead>
            <tbody>
                {% for d in discipline_logs %}
                <tr><td>{{ d.record_date }}</td><td><b>{{ d.name }}</b></td><td>{{ d.record_type }}</td><td>{{ d.reason }}</td></tr>
                {% else %}<tr><td colspan="4">नोंद नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'exp' %}
    <div class="admin-tab">
        <h3>💵 दैनिक खर्च वही</h3>
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

    {% if curr_tab == 'wa' %}
    <div class="admin-tab">
        <h3>📲 WhatsApp मेसेज</h3>
        <table><thead><tr><th>नाव</th><th>फोन</th><th>मेसेज</th></tr></thead><tbody>
            {% for s in students %}
            <tr><td>{{ s.name }}</td><td>{{ s.parent_phone }}</td><td><a href="https://wa.me/91{{ s.parent_phone }}" target="_blank" class="btn-act" style="background:#25D366;">📲 मेसेज</a></td></tr>
            {% endfor %}
        </tbody></table>
    </div>
    {% endif %}

    {% if curr_tab == 'staff' %}
    <div class="admin-tab">
        <h3 style="color:#4f46e5; margin-top:0;">👔 स्टाफ पगार</h3>
        <table>
            <thead><tr><th>नाव</th><th>पद</th><th>फोन</th><th>पगार</th></tr></thead>
            <tbody>
                {% for st in staff_members %}
                <tr><td><b>{{ st.name }}</b></td><td>{{ st.role }}</td><td>{{ st.phone }}</td><td>₹{{ st.salary }}</td></tr>
                {% else %}<tr><td colspan="4">स्टाफ नाही.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'tasks' %}
    <div class="admin-tab">
        <h3 style="color:#d97706; margin-top:0;">📌 काम सांगा</h3>
        <p>स्टाफसाठी कामे सोपवा.</p>
    </div>
    {% endif %}

    {% if curr_tab == 'staff_tracking' %}
    <div class="admin-tab">
        <h3 style="color:#059669; margin-top:0;">👁️ स्टाफ हालचाली</h3>
        <table>
            <thead><tr><th>वेळ</th><th>कर्मचारी</th><th>हालचाल नोंद</th></tr></thead>
            <tbody>
                {% for log in all_staff_logs %}
                <tr><td>{{ log.act_time }}</td><td><b>{{ log.staff_role }}</b></td><td>{{ log.activity_text }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'passwords' %}
    <div class="admin-tab">
        <h3 style="color:#dc2626; margin-top:0;">🔐 युजर पासवर्ड</h3>
        <table>
            <thead><tr><th>Role</th><th>Password</th></tr></thead>
            <tbody>
                {% for u in users_list %}
                <tr><td><b>{{ u.role }}</b></td><td>{{ u.password }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if curr_tab == 'bak' %}
    <div class="admin-tab">
        <h3 style="color:#0b3c5d;">💾 डेटाबेस बॅकअप</h3>
        <p>क्लाउड डेटाबेस (Neon PostgreSQL) कार्यरत आहे.</p>
    </div>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- MANAGER & CLERK LAYOUTS -----------------
MANAGER_LAYOUT = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>मॅनेजर डॅशबोर्ड - श्रीगुरु अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; }
        .header { background: #065f46; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
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
            for(var i=0, n=checkboxes.length; i<n; i++) {
                checkboxes[i].checked = source.checked;
            }
        }
    </script>
</head>
<body>
<div class="header">
    <h2 style="margin:0;">🥗 मॅनेजर पोर्टल (मेस व कॅन्टीन विभाग - ५०० मास्टर यादी)</h2>
    <div>
        <a href="/logout" style="background:#ef4444; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px;">Logout</a>
    </div>
</div>
<div class="container">
    <div class="tab-box">
        <h3 style="color:#065f46; margin-top:0;">🛒 कॅन्टीन व मेस किराणा, भाजीपाला आणि खाद्यसाहित्य खरेदी यादी</h3>
        <p style="font-size:13px; color:#475569;">१ ते १०० क्रमांकांवर कडधान्ये, फळे, भाजीपाला आणि मसाले दिले आहेत. खालील बटणांचा वापर करून हवे ते साहित्य निवडा किंवा प्रिंट काढा:</p>
        
        <form action="/print_grocery_slip" method="POST" target="_blank">
            <div style="margin-bottom:15px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                <button type="submit" class="btn">🖨️ निवडलेल्या साहित्याची पावती प्रिंट करा (Compact 50+ per page)</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBox').checked = true; toggleAll(document.getElementById('selectAllBox'));">✅ सर्व निवडा (Select All)</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBox').checked = false; toggleAll(document.getElementById('selectAllBox'));">❌ सर्व काढा (Deselect All)</button>
                <label style="font-size:12px; font-weight:bold; margin-left:10px;"><input type="checkbox" id="selectAllBox" onchange="toggleAll(this)"> सर्व ऑन/ऑफ करा</label>
            </div>
            <table>
                <thead>
                    <tr><th style="width:40px; text-align:center;">निवड</th><th style="width:50px;">क्र.</th><th>साहित्याचे अचूक नाव (भाजीपाला, कडधान्य, मसाले व ५०० मेनू)</th><th style="width:130px;">वजन / प्रमाण</th></tr>
                </thead>
                <tbody>
                    {% for item in grocery_items %}
                    <tr>
                        <td style="text-align:center;"><input type="checkbox" name="items" value="{{ item }}"></td>
                        <td><b>{{ loop.index }}</b></td>
                        <td><b>{{ item }}</b></td>
                        <td><input type="text" name="qty_{{ item }}" value="लागेल तेवढे" style="padding:3px; width:120px; border:1px solid #cbd5e1; border-radius:4px; font-size:12px;"></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <br><button type="submit" class="btn">🖨️ निवडलेल्या साहित्याची पावती प्रिंट करा</button>
        </form>
    </div>
</div>
</body>
</html>'''

CLERK_LAYOUT = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>क्लार्क डॅशबोर्ड - श्रीगुरु अकॅडमी</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; }
        .header { background: #1e40af; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
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
            for(var i=0, n=checkboxes.length; i<n; i++) {
                checkboxes[i].checked = source.checked;
            }
        }
    </script>
</head>
<body>
<div class="header">
    <h2 style="margin:0;">💼 क्लार्क पोर्टल (कार्यालय व किराणा नियोजन - ५०० मास्टर यादी)</h2>
    <div>
        <a href="/logout" style="background:#ef4444; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px;">Logout</a>
    </div>
</div>
<div class="container">
    <div class="tab-box">
        <h3 style="color:#1e40af; margin-top:0;">🛒 मेस व कॅन्टीन खरेदी मास्टर यादी (५०० वस्तू)</h3>
        <p style="font-size:13px; color:#475569;">भाजीपाला, कडधान्य, फळे आणि रोजचे मसाले सुरुवातीला दिले आहेत. हवे ते साहित्य निवडून प्रिंट काढा:</p>
        
        <form action="/print_grocery_slip" method="POST" target="_blank">
            <div style="margin-bottom:15px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                <button type="submit" class="btn">🖨️ निवडलेल्या साहित्याची पावती प्रिंट करा (Compact 50+ per page)</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBoxClerk').checked = true; toggleAll(document.getElementById('selectAllBoxClerk'));">✅ सर्व निवडा (Select All)</button>
                <button type="button" class="btn-alt" onclick="document.getElementById('selectAllBoxClerk').checked = false; toggleAll(document.getElementById('selectAllBoxClerk'));">❌ सर्व काढा (Deselect All)</button>
                <label style="font-size:12px; font-weight:bold; margin-left:10px;"><input type="checkbox" id="selectAllBoxClerk" onchange="toggleAll(this)"> सर्व ऑन/ऑफ करा</label>
            </div>
            <table>
                <thead>
                    <tr><th style="width:40px; text-align:center;">निवड</th><th style="width:50px;">क्र.</th><th>साहित्याचे अचूक नाव (भाजीपाला, कडधान्य, मसाले व ५०० मेनू)</th><th style="width:130px;">वजन / प्रमाण</th></tr>
                </thead>
                <tbody>
                    {% for item in grocery_items %}
                    <tr>
                        <td style="text-align:center;"><input type="checkbox" name="items" value="{{ item }}"></td>
                        <td><b>{{ loop.index }}</b></td>
                        <td><b>{{ item }}</b></td>
                        <td><input type="text" name="qty_{{ item }}" value="लागेल तेवढे" style="padding:3px; width:120px; border:1px solid #cbd5e1; border-radius:4px; font-size:12px;"></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <br><button type="submit" class="btn">🖨️ निवडलेल्या साहित्याची पावती प्रिंट करा</button>
        </form>
    </div>
</div>
</body>
</html>'''

# ----------------- SECURE PUBLIC TEST TEMPLATE (ON-SCREEN CERTIFICATE & REVIEW) -----------------
MOCK_TEST_HTML = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>महाराष्ट्र पोलीस भरती - मोफत ऑनलाइन सराव टेस्ट</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { margin: 0; background: #f1f5f9; color: #1e293b; padding: 15px; }
        .box { max-width: 650px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 5px solid #0284c7; }
        h2 { margin: 0 0 5px; color: #0b2545; text-align: center; }
        .q-item { margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #e2e8f0; }
        .q-text { font-weight: bold; margin-bottom: 8px; font-size: 15px; color: #0f172a; }
        .opt-label { display: block; margin-bottom: 6px; font-size: 14px; cursor: pointer; }
        input[type="text"], input[type="tel"] { width: 100%; padding: 9px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-bottom: 10px; }
        .btn-submit { width: 100%; background: #059669; color: white; padding: 12px; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .cert-box { border: 4px double #b45309; padding: 25px; border-radius: 10px; background: #fffbeb; text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
<div class="box">
    <h2>🎯 श्रीगुरु राज्यस्तरीय महासराव टेस्ट</h2>
    <p style="text-align:center; color:#64748b; font-size:13px; margin-bottom:20px;">पोलीस व सैन्य भरती विशेष सराव परीक्षा</p>

    {% if not launched %}
    <div style="background:#fef2f2; border:2px solid #f87171; border-radius:8px; padding:25px; text-align:center;">
        <h3 style="margin:0 0 10px; color:#991b1b;">⚠️ टेस्ट सध्या बंद आहे!</h3>
        <p style="color:#475569; font-size:15px; line-height:1.6;">
            श्रीगुरु करिअर अकॅडमीतर्फे नवीन सराव टेस्ट लवकरच लॉन्च केली जाईल. कृपया ॲडमिनने टेस्ट लाईव्ह (Launch) केल्यावर पुन्हा भेट द्या!
        </p>
    </div>
    {% elif submitted %}
    <div style="background:#f0fdf4; border:2px solid #86efac; border-radius:8px; padding:20px; text-align:center; margin-bottom:20px;">
        <h3 style="margin:0 0 10px; color:#166534;">हार्दिक अभिनंदन, {{ name }}! 🎉</h3>
        <p style="font-size:18px; margin:5px 0;">तुमचा अंतिम स्कोअर: <b style="color:#059669; font-size:24px;">{{ score }} / {{ total }}</b></p>
        <p style="color:#475569; font-size:13px;">तुमचा ओरिजनल मोबाईल नंबर डेटाबेसमध्ये सेव्ह झाला आहे.</p>
        <a href="{{ wa_share }}" target="_blank" style="display:inline-block; background:#25D366; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; margin-top:10px; font-size:14px;">
            📲 WhatsApp वर निकाल शेअर करा
        </a>
    </div>

    <!-- Right/Wrong Review -->
    <div style="background:#f8fafc; border:1px solid #cbd5e1; padding:15px; border-radius:8px; margin-bottom:20px;">
        <h3 style="margin-top:0; color:#0b3c5d; font-size:16px;">📖 सविस्तर प्रश्न व अचूक उत्तर रिव्ह्यू:</h3>
        {% for r in review_list %}
        <div style="margin-bottom:12px; padding-bottom:8px; border-bottom:1px dashed #cbd5e1; font-size:13px;">
            <b>प्र. {{ loop.index }}. {{ r.question }}</b><br>
            तुमचे उत्तर: <span style="color:{{ 'green' if r.is_correct else 'red' }}; font-weight:bold;">{{ r.user_ans or 'सोडवले नाही' }}</span> | 
            अचूक उत्तर: <b style="color:green;">{{ r.correct_ans }}</b>
            {% if r.is_correct %} <span style="color:green; font-weight:bold;">✔️ बरोबर</span> {% else %} <span style="color:red; font-weight:bold;">❌ चूक</span> {% endif %}
        </div>
        {% endfor %}
    </div>

    <!-- Digital Certificate -->
    <div class="cert-box">
        <h3 style="margin:0; color:#b45309; font-size:20px;">🏆 डिजिटल प्रशस्तीपत्र (Certificate of Merit)</h3>
        <p style="font-size:12px; color:#78350f; margin:5px 0 15px;">श्रीगुरु करिअर अकॅडमी, आडूर (ता. करवीर, जि. कोल्हापूर)</p>
        <hr style="border:1px solid #fde68a; margin:10px 0;">
        <p style="font-size:14px; color:#1e293b; line-height:1.6;">
            प्रमाणपत्र देण्यात येते की, श्री/सौ/कुमार <b>{{ name }}</b> (जिल्हा: {{ district }}) यांनी श्रीगुरु करिअर अकॅडमीतर्फे आयोजित राज्यस्तरीय पोलीस भरती सराव टेस्टमध्ये सहभाग घेऊन <b>{{ score }} / {{ total }}</b> गुण प्राप्त केले आहेत.
        </p>
        <p style="font-size:13px; color:#92400e; font-weight:bold; margin-top:15px; line-height:1.5;">
            मा. सचिन चौगले सर तसेच श्रीगुरु करिअर अकॅडमी परिवारातर्फे घेण्यात आलेल्या या राज्यस्तरीय लेखी स्पर्धेमध्ये सहभागी झाल्याबद्दल खूप खूप अभिनंदन! आपले पोलीस बनण्याचे व इतर शासकीय सेवांमध्ये जाण्याचे स्वप्न लवकरच पूर्ण होवो, अशा सदिच्छा! 🌟
        </p>
        <div style="margin-top:20px; display:flex; justify-content:space-between; font-size:12px; font-weight:bold; color:#78350f;">
            <div>दिनांक: {{ today_date }}</div>
            <div>संचालक / मार्गदर्शक<br>मा. सचिन चौगले सर व परिवार<br>श्रीगुरु करिअर अकॅडमी, आडूर</div>
        </div>
    </div>
    <br>
    <div style="text-align:center;"><a href="/test" style="color:#0284c7; font-weight:bold; text-decoration:none;">🔄 नवीन टेस्ट सोडवा</a></div>

    {% else %}
    <form method="POST" action="/test">
        <div style="background:#f8fafc; padding:15px; border-radius:8px; margin-bottom:20px; border:1px solid #cbd5e1; border-left:4px solid #b45309;">
            <b style="color:#b45309; display:block; margin-bottom:8px;">⚠️ सूचना: निकाल व प्रशस्तीपत्र पाहण्यासाठी तुमचा ओरिजनल WhatsApp नंबर भरणे अनिवार्य आहे:</b>
            <label style="font-weight:bold; font-size:13px;">विद्यार्थ्याचे पूर्ण नाव *:</label>
            <input type="text" name="student_name" placeholder="उदा. गणेश पाटील" required>
            
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                <div>
                    <label style="font-weight:bold; font-size:13px;">जिल्हा *:</label>
                    <input type="text" name="district" placeholder="उदा. सातारा / सांगली" required>
                </div>
                <div>
                    <label style="font-weight:bold; font-size:13px;">व्हॉट्सॲप मोबाईल नंबर *:</label>
                    <input type="tel" name="phone" placeholder="१० अंकी ओरिजनल नंबर" pattern="[0-9]{10}" required>
                </div>
            </div>
        </div>

        {% for q in questions %}
        <div class="q-item">
            <div class="q-text">प्र. {{ loop.index }}. {{ q.question }}</div>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="A" required> A) {{ q.opt_a }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="B"> B) {{ q.opt_b }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="C"> C) {{ q.opt_c }}</label>
            <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="D"> D) {{ q.opt_d }}</label>
        </div>
        {% endfor %}

        <button type="submit" class="btn-submit">✅ टेस्ट सबमिट करा व निकाल पहा</button>
    </form>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- PUBLIC INQUIRY & INQUIRIES DESK -----------------
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
    return render_template_string(MANAGER_LAYOUT, grocery_items=GROCERY_MASTER_500)

@app.route('/trainer')
def trainer_view():
    if session.get('user_role') != 'Trainer': return redirect(url_for('login'))
    return "Trainer Dashboard Active"

@app.route('/clerk')
def clerk_view():
    if session.get('user_role') != 'Clerk': return redirect(url_for('login'))
    return render_template_string(CLERK_LAYOUT, grocery_items=GROCERY_MASTER_500)

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect(url_for('login'))
    curr_tab = request.args.get('tab', 'students')
    today_date = date.today().strftime("%Y-%m-%d")
    lang = session.get('site_lang', 'mr')
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='test_launched'")
            res_launch = cur.fetchone()
            test_launched = res_launch['value'] if res_launch else 'no'

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
            cur.execute("SELECT * FROM questions ORDER BY id DESC")
            questions = cur.fetchall()

    total_paid = sum(safe_float(s['paid_fees']) for s in students)
    total_pending = sum(safe_float(s['total_fees']) - safe_float(s['paid_fees']) for s in students)
    total_expenses = sum(safe_float(ex['amount']) for ex in expenses_list)

    return render_template_string(ADMIN_DASHBOARD_LAYOUT, curr_tab=curr_tab, students=students, expenses_list=expenses_list, users_list=users_list, diet_list=diet_list, staff_members=staff_members, staff_tasks=staff_tasks, all_requests=all_requests, all_staff_logs=all_staff_logs, discipline_logs=discipline_logs, hostel_logs=hostel_logs, physical_records=physical_records, written_records=written_records, questions=questions, total_paid=total_paid, total_pending=total_pending, total_expenses=total_expenses, today_date=today_date, lang=lang, test_launched=test_launched)

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

# ----------------- QUESTION MANAGEMENT ROUTES -----------------
@app.route('/add_single_question', methods=['POST'])
def add_single_question():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    q = request.form.get('question')
    a = request.form.get('opt_a')
    b = request.form.get('opt_b')
    c = request.form.get('opt_c')
    d = request.form.get('opt_d')
    corr = request.form.get('correct')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO questions (question, opt_a, opt_b, opt_c, opt_d, correct) VALUES (%s, %s, %s, %s, %s, %s)", (q, a, b, c, d, corr))
            conn.commit()
    return redirect('/admin?tab=questions')

@app.route('/add_bulk_questions', methods=['POST'])
def add_bulk_questions():
    if session.get('user_role') not in ['Admin', 'Clerk']: return "Unauthorized", 403
    text = request.form.get('bulk_text', '')
    lines = text.strip().split('\n')
    with get_db() as conn:
        with conn.cursor() as cur:
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) == 6:
                    cur.execute("INSERT INTO questions (question, opt_a, opt_b, opt_c, opt_d, correct) VALUES (%s, %s, %s, %s, %s, %s)", 
                                (parts[0], parts[1], parts[2], parts[3], parts[4], parts[5].upper()))
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

# ----------------- PUBLIC INQUIRY & ON-SCREEN CERTIFICATE TEST ROUTES -----------------
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
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='test_launched'")
            res_launch = cur.fetchone()
            launched = (res_launch['value'] == 'yes') if res_launch else False

            cur.execute("SELECT * FROM questions ORDER BY id ASC")
            questions = cur.fetchall()

    score = None
    total = 0
    name = ""
    district = ""
    phone = ""
    submitted = False
    review_list = []
    today_date = date.today().strftime("%d/%m/%Y")
    wa_share = ""

    if request.method == 'POST' and launched:
        name = request.form.get('student_name')
        district = request.form.get('district')
        phone = request.form.get('phone')

        if phone and len(phone.strip()) >= 10:
            submitted = True
            current_score = 0
            total = len(questions)

            with get_db() as conn:
                with conn.cursor() as cur:
                    for q in questions:
                        user_ans = request.form.get(f"q_{q['id']}")
                        is_corr = (user_ans and user_ans == q['correct'])
                        if is_corr:
                            current_score += 1
                        review_list.append({
                            'question': q['question'],
                            'user_ans': user_ans,
                            'correct_ans': q['correct'],
                            'is_correct': is_corr
                        })

                    t_date = date.today().strftime("%Y-%m-%d")
                    cur.execute("""
                        INSERT INTO mock_test_leads (test_date, student_name, district, phone, score, total_marks, test_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (t_date, name, district, phone, current_score, total, "राज्यस्तरीय पोलीस सराव टेस्ट"))
                    conn.commit()

            score = current_score
            wa_text = f"नमस्कार, मी {name} ({district}). श्रीगुरु करिअर अकॅडमीच्या ऑनलाईन टेस्टमध्ये मला {score}/{total} गुण मिळाले आहेत!"
            wa_share = f"https://wa.me/?text={urllib.parse.quote(wa_text)}"

    return render_template_string(MOCK_TEST_HTML, questions=questions, submitted=submitted, score=score, total=total, name=name, district=district, phone=phone, review_list=review_list, today_date=today_date, launched=launched, wa_share=wa_share)

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

# ----------------- COMPACT MULTI-COLUMN PRINT GROCERY SLIP ROUTE -----------------
@app.route('/print_grocery_slip', methods=['POST'])
def print_grocery_slip():
    items = request.form.getlist('items')
    rows = "".join([f"<tr><td style='padding:3px 6px; border:1px solid #333; text-align:center;'>{loop_idx+1}</td><td style='padding:3px 6px; border:1px solid #333; font-weight:600;'>{itm}</td><td style='padding:3px 6px; border:1px solid #333;'>{request.form.get('qty_'+itm, 'लागेल तेवढे')}</td><td style='padding:3px 6px; border:1px solid #333; text-align:center;'>[  ]</td></tr>" for loop_idx, itm in enumerate(items)])
    html = f'''<!DOCTYPE html><html><head><title>कॅन्टीन व मेस खरेदी पावती - श्रीगुरु अकॅडमी</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; padding: 15px; color: #1e293b; font-size: 11px; }}
        h2 {{ margin: 0; color: #065f46; font-size: 18px; text-align: center; }}
        p {{ margin: 2px 0 10px; font-size: 10px; text-align: center; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 11px; page-break-inside: auto; }}
        tr {{ page-break-inside: avoid; page-break-after: auto; }}
        th, td {{ border: 1px solid #333; padding: 3px 6px; }}
        th {{ background: #065f46; color: white; font-size: 11px; }}
    </style>
    </head>
    <body onload="window.print()">
        <div style="max-width: 100%; margin: auto;">
            <h2>श्रीगुरु करिअर अकॅडमी (मेस व कॅन्टीन विभाग)</h2>
-            <p>आडूर, ता. करवीर, जि. कोल्हापूर | संपर्क: ९९२११११९६०</p>
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
    </body></html>'''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

