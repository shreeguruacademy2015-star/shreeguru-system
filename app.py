import json
import os
import re
import secrets
import urllib.parse
from datetime import date, datetime, timedelta
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for, send_from_directory
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_master_test_platform_2026_ultimate_safe"

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- NEON CLOUD DATABASE CONNECTION ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_master_db():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # १. टेस्ट पेपर्स टेबल
                cur.execute('''CREATE TABLE IF NOT EXISTS test_papers (
                    id SERIAL PRIMARY KEY,
                    test_title TEXT NOT NULL,
                    test_type TEXT DEFAULT 'Free',
                    test_fee REAL DEFAULT 0,
                    duration_minutes INTEGER DEFAULT 60,
                    status TEXT DEFAULT 'Active'
                )''')

                # २. प्रश्न टेबल
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

                # ३. विद्यार्थी लीड्स व निकाल टेबल
                cur.execute('''CREATE TABLE IF NOT EXISTS mock_test_leads (
                    id SERIAL PRIMARY KEY,
                    test_id INTEGER DEFAULT 1,
                    test_date TEXT NOT NULL,
                    student_name TEXT NOT NULL,
                    district TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    whatsapp_verified INTEGER DEFAULT 0,
                    payment_status TEXT DEFAULT 'Pending',
                    utr_number TEXT DEFAULT '',
                    score REAL DEFAULT 0,
                    total_marks INTEGER DEFAULT 0,
                    test_name TEXT NOT NULL,
                    answers_json TEXT DEFAULT '',
                    otp_code TEXT DEFAULT '',
                    valid_until TEXT DEFAULT '',
                    access_token TEXT DEFAULT '',
                    token_expires_at TEXT DEFAULT ''
                )''')

                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS access_token TEXT DEFAULT ''")
                cur.execute("ALTER TABLE mock_test_leads ADD COLUMN IF NOT EXISTS token_expires_at TEXT DEFAULT ''")

                # ४. विद्यार्थी अभिप्राय (Feedback) टेबल
                cur.execute('''CREATE TABLE IF NOT EXISTS student_feedbacks (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER,
                    student_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    feedback_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )''')

                # ५. स्पेशल ॲक्सेस टेबल्स
                cur.execute('''CREATE TABLE IF NOT EXISTS special_unlimited_attempts (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    student_name TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    added_on TEXT NOT NULL
                )''')

                cur.execute('''CREATE TABLE IF NOT EXISTS special_free_pass (
                    id SERIAL PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    student_name TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    added_on TEXT NOT NULL
                )''')

                # ६. ॲकॅडमी सेटिंग्स
                cur.execute('''CREATE TABLE IF NOT EXISTS academy_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )''')

                defaults = [
                    ('qr_code_url', 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=ShreeguruUPIpayment'),
                    ('upi_mobile', '9921111960'),
                    ('admin_pass', 'shreeguru2026'),
                    ('admin_phone', '9921111960'),
                    ('insta_link', ''),
                    ('yt_link', ''),
                    ('toppers_link', ''),
                    ('recruitment_pdf', ''),
                    ('eligibility_pdf', '')
                ]
                for k, v in defaults:
                    cur.execute("INSERT INTO academy_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO NOTHING", (k, v))

                cur.execute('SELECT COUNT(*) as count FROM test_papers')
                if cur.fetchone()['count'] == 0:
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (1, 'पोलीस भरती विशेष महासराव टेस्ट #१', 'Free', 0, 60, 'Active')")
                    cur.execute("INSERT INTO test_papers (id, test_title, test_type, test_fee, duration_minutes, status) VALUES (2, 'आर्मी भरती बौद्धिक व गणित टेस्ट #२', 'Paid', 49, 45, 'Active')")

                cur.execute('SELECT COUNT(*) as count FROM questions')
                if cur.fetchone()['count'] == 0:
                    default_qs = [
                        (1, "महाराष्ट्राची आर्थिक व व्यापारी राजधानी कोणती?", "पुणे", "मुंबई", "नागपूर", "नाशिक", "B", "मुंबई ही महाराष्ट्राची आर्थिक व व्यापारी राजधानी आहे."),
                        (1, "क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा कोणता?", "अहमदनगर", "पुणे", "नाशिक", "सोलापूर", "A", "अहमदनगर हा क्षेत्रफळाच्या दृष्टीने महाराष्ट्रातील सर्वात मोठा जिल्हा आहे."),
                        (2, "भारताचे राष्ट्रीय गीत कोणते?", "जन गण मन", "वंदे मातरम्", "सारा जहाँ से अच्छा", "जय हिंद", "B", "वंदे मातरम् हे बंकिमचंद्र चटोपाध्याय यांनी रचलेले भारताचे राष्ट्रीय गीत आहे.")
                    ]
                    cur.executemany('INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', default_qs)
                conn.commit()
    except Exception as e:
        print(f"Init DB Error: {e}")

init_master_db()

# ----------------- 1. PUBLIC HOME TEMPLATE -----------------
HOME_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</title>
    <link href="https://fonts.googleapis.com/css2?family=Baloo+Bhaina+2:wght@500;700&family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', 'Baloo Bhaina 2', sans-serif; }
        body { margin: 0; background: linear-gradient(135deg, #f0fdf4, #e6fffa); color: #1e293b; padding: 15px; }
        .top-bar { max-width: 850px; margin: 0 auto 10px; display: flex; justify-content: space-between; align-items: center; background: white; padding: 10px 15px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
        .clock { font-weight: bold; color: #065f46; font-size: 14px; }
        .box { max-width: 850px; margin: 0 auto; background: white; border-radius: 14px; padding: 25px; box-shadow: 0 12px 30px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 26px; font-family: 'Baloo Bhaina 2', cursive; }
        .quote-box { background: #ecfdf5; border-left: 4px solid #059669; padding: 12px 15px; border-radius: 6px; font-size: 15px; color: #065f46; font-weight: 600; text-align: center; margin-bottom: 20px; line-height: 1.5; }
        .test-card { background: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 10px; padding: 18px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; transition: 0.2s; }
        .test-card:hover { border-color: #059669; box-shadow: 0 4px 12px rgba(5,150,105,0.1); }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; box-shadow: 0 3px 8px rgba(5,150,105,0.3); }
        .badge-free { background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-paid { background: #fef9c3; color: #854d0e; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .bottom-docs { display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; margin-top: 25px; margin-bottom: 15px; }
        .doc-btn { display: inline-flex; align-items: center; gap: 6px; background: #f1f5f9; color: #0f172a; padding: 9px 16px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600; border: 1.5px solid #cbd5e1; transition: 0.2s; }
        .doc-btn:hover { background: #e2e8f0; border-color: #059669; color: #065f46; }
        .footer-terms { text-align: center; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 12px; }
        .footer-terms a { color: #0369a1; text-decoration: none; font-weight: 600; }
        .footer-terms a:hover { text-decoration: underline; }
    </style>
    <script>
        function updateClock() {
            const now = new Date();
            document.getElementById('live-clock').innerText = now.toLocaleDateString('mr-IN') + ' ' + now.toLocaleTimeString();
        }
        setInterval(updateClock, 1000);
    </script>
</head>
<body onload="updateClock()">

<div class="top-bar">
    <div class="clock">🕒 <span id="live-clock">लोडिंग...</span></div>
    {% if is_admin %}
    <div><a href="/admin/dashboard" style="background:#059669; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">⚙ ॲडमिन डॅशबोर्ड</a></div>
    {% endif %}
</div>

<div class="box">
    <h2>⚔ राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</h2>
    <div class="quote-box">
        🔥 हातात उरलेल्या दिवसात काबाड कष्ट करून तुला तुझे वर्दीचे स्वप्न पूर्ण करायचे आहे (लक्षात ठेव तुला घडविण्यासाठी कुणाचे तरी हात झिजत आहेत) 🌟
    </div>
    <p style="font-size:15px; font-weight:600; color:#0b3c5d; margin-bottom:20px; border-bottom:2px solid #e2e8f0; padding-bottom:8px; text-align:center;">
        खालील प्रश्नपत्रिका सोडवा आणि संपूर्ण राज्यात तुमचा रँक तपासा
    </p>

    {% for t in tests %}
    <div class="test-card">
        <div>
            <h4 style="margin:0 0 6px; color:#0f172a; font-size:17px; font-family:'Baloo Bhaina 2', cursive;">{{ t.test_title }}</h4>
            <span class="{{ 'badge-free' if t.test_type == 'Free' else 'badge-paid' }}">
                {{ '🟢 मोफत महासराव टेस्ट' if t.test_type == 'Free' else '⭐ सशुल्क (Paid) टेस्ट - ₹' ~ t.test_fee }}
            </span>
            <div style="font-size:12px; color:#64748b; margin-top:4px;">⏱️ वेळ मर्यादा: {{ t.duration_minutes }} मिनिटे</div>
        </div>
        <a href="/take_test/{{ t.id }}" class="btn-start">✨ टेस्ट सोडवा</a>
    </div>
    {% endfor %}

    <div class="bottom-docs">
        {% if recruitment_pdf %}
        <a href="{{ recruitment_pdf }}" target="_blank" class="doc-btn">📄 भरती अधिकृत माहिती (PDF)</a>
        {% endif %}
        {% if eligibility_pdf %}
        <a href="{{ eligibility_pdf }}" target="_blank" class="doc-btn">📋 भरती पात्रता व निकष (PDF)</a>
        {% endif %}
    </div>

    <div class="footer-terms">
        <span>© 2026 Online Mock Platform. All rights reserved. | </span>
        <a href="/terms-and-conditions" target="_blank">Terms & Conditions</a>
    </div>
</div>
</body>
</html>'''

# ----------------- TERMS AND CONDITIONS TEMPLATE -----------------
TERMS_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms and Conditions - Online Mock Test Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; padding: 25px 15px; line-height: 1.6; }
        .terms-container { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 35px; box-shadow: 0 10px 25px rgba(0,0,0,0.06); border-top: 5px solid #059669; }
        h1 { color: #065f46; font-size: 24px; margin-top: 0; }
        h3 { color: #0b3c5d; font-size: 16px; margin-top: 20px; margin-bottom: 6px; }
        p { font-size: 13.5px; color: #475569; margin: 6px 0 12px; }
        ul { font-size: 13.5px; color: #475569; margin: 6px 0 14px; padding-left: 20px; }
        .back-link { display: inline-block; margin-top: 20px; color: #0284c7; text-decoration: none; font-weight: 600; font-size: 13px; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
<div class="terms-container">
    <h1>Terms and Conditions</h1>
    <p>Last updated: October 2026</p>
    <p>Welcome to our Online Mock Test Platform. By accessing or using this test portal, you agree to comply with and be bound by the following terms and conditions.</p>
    <h3>1. Use of the Platform</h3>
    <p>This platform provides online practice examinations for government recruitment preparations (including Maharashtra Police and Defence tests). The test material is intended solely for educational practice and evaluation purposes.</p>
    <h3>2. Registration & Identification</h3>
    <p>Candidates must provide accurate personal details (Name, District, and Mobile Number). Submitting false identity or incorrect contact numbers may lead to forfeiture of test results and access privileges.</p>
    <h3>3. Paid Tests and Access Duration</h3>
    <ul>
        <li>Paid tests require verified UPI payment confirmation by the administrator.</li>
        <li>Once approved, candidate access is provisioned for a maximum duration of 24 hours per link token unless specified otherwise.</li>
        <li>Access links expire automatically after the validity period and cannot be transferred or reused.</li>
    </ul>
    <h3>4. Payments and Refund Policy</h3>
    <p>All fees paid for mock tests and exam access are strictly non-refundable and non-transferable once access credentials or test tokens are dispatched.</p>
    <h3>5. Intellectual Property</h3>
    <p>All question sets, answer keys, explanations, and platform designs are proprietary material. Reproduction, unauthorized copying, distribution, or commercial exploitation is strictly prohibited.</p>
    <h3>6. Result Generation and Disclaimers</h3>
    <p>Mock examination scores and percentile rankings are indicative self-assessment metrics. They do not constitute an official qualification or guarantee of selection in government recruitment.</p>
    <a href="/" class="back-link">⬅ Back to Home Platform</a>
</div>
</body>
</html>'''

# ----------------- 2. EXAM TEMPLATE (बंधन नसलेली थेट टेस्ट + शेवटी निकाल पाहण्यासाठी माहिती) -----------------
EXAM_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ test.test_title }} - परीक्षा कक्ष</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #eef2f7; color: #1e293b; padding: 10px; }
        .exam-header { background: #065f46; color: white; padding: 12px 20px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; max-width: 800px; margin: 0 auto 15px; }
        .box { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border-top: 5px solid #059669; }
        .timer-box { background: #fee2e2; border: 2px solid #ef4444; color: #991b1b; padding: 8px 15px; border-radius: 6px; font-weight: bold; font-size: 15px; }
        .student-details { background: #f0fdf4; border: 2px solid #86efac; border-radius: 8px; padding: 20px; margin-top: 25px; margin-bottom: 20px; }
        .student-details input { width: 100%; padding: 11px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-top: 4px; font-size: 14px; margin-bottom: 6px; transition: border-color 0.2s; }
        .phone-error-msg { display: none; color: #b91c1c; font-size: 12px; font-weight: bold; background: #fee2e2; border-left: 3px solid #dc2626; padding: 6px 10px; border-radius: 4px; margin-bottom: 10px; line-height: 1.4; }
        .q-item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; margin-bottom: 18px; }
        .q-text { font-weight: bold; margin-bottom: 10px; font-size: 15px; color: #0f172a; }
        .opt-label { display: block; margin-bottom: 8px; font-size: 14px; cursor: pointer; background: white; padding: 9px 12px; border-radius: 6px; border: 1px solid #e2e8f0; transition: background 0.2s; }
        .opt-label:hover { background: #ecfdf5; }
        .submit-notice { background: #fef3c7; border: 1px solid #f59e0b; color: #92400e; padding: 10px 15px; border-radius: 6px; font-size: 13px; font-weight: bold; text-align: center; margin-bottom: 12px; }
        .btn-submit { width: 100%; background: linear-gradient(135deg, #059669, #047857); color: white; padding: 14px; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(5,150,105,0.25); }
    </style>
    <script>
        let timeLeft = {{ test.duration_minutes * 60 }};
        function startTimer() {
            const timerDisplay = document.getElementById('time-left');
            let timer = setInterval(function () {
                let minutes = parseInt(timeLeft / 60, 10);
                let seconds = parseInt(timeLeft % 60, 10);
                minutes = minutes < 10 ? "0" + minutes : minutes;
                seconds = seconds < 10 ? "0" + seconds : seconds;
                timerDisplay.innerText = minutes + ":" + seconds;
                if (--timeLeft < 0) {
                    clearInterval(timer);
                    alert("⏰ वेळ संपली! टेस्ट सबमिट होत आहे.");
                    document.getElementById("examForm").submit();
                }
            }, 1000);
        }

        let isPhoneValid = false;
        async function validateStudentDetails() {
            const name = document.getElementById('s_name').value.trim();
            const dist = document.getElementById('s_dist').value.trim();
            const phoneInput = document.getElementById('s_phone');
            const phone = phoneInput.value.trim();
            const phoneErrDiv = document.getElementById('phoneErrorNotice');
            const submitNotice = document.getElementById('submitNotice');
            const submitBtn = document.getElementById('submitBtn');

            const indianPhoneRegex = /^[6-9][0-9]{9}$/;

            if (phone.length > 0) {
                if (!['6', '7', '8', '9'].includes(phone.charAt(0))) {
                    isPhoneValid = false;
                    phoneInput.style.borderColor = "#dc2626";
                    phoneErrDiv.style.display = "block";
                    phoneErrDiv.innerText = "⚠️ आपण चुकीचा मोबाईल नंबर टाकत आहात!";
                } else if (phone.length < 10) {
                    isPhoneValid = false;
                    phoneInput.style.borderColor = "#f59e0b";
                    phoneErrDiv.style.display = "none";
                } else if (phone.length === 10 && indianPhoneRegex.test(phone)) {
                    isPhoneValid = true;
                    phoneInput.style.borderColor = "#16a34a";
                    phoneErrDiv.style.display = "none";
                } else {
                    isPhoneValid = false;
                    phoneInput.style.borderColor = "#dc2626";
                    phoneErrDiv.style.display = "block";
                    phoneErrDiv.innerText = "⚠️ आपण चुकीचा मोबाईल नंबर टाकत आहात!";
                }
            } else {
                isPhoneValid = false;
                phoneInput.style.borderColor = "#cbd5e1";
                phoneErrDiv.style.display = "none";
            }

            if (name !== "" && dist !== "" && isPhoneValid) {
                submitBtn.disabled = false;
                submitNotice.innerHTML = "✅ सर्व माहिती योग्य आहे. आता निकाल पाहण्यासाठी 'निकाल व गुण पहा' बटणावर क्लिक करा.";
                submitNotice.style.background = "#dcfce7";
                submitNotice.style.borderColor = "#86efac";
                submitNotice.style.color = "#166534";
            } else {
                submitBtn.disabled = true;
                if (!phoneErrDiv.style.display || phoneErrDiv.style.display === "none") {
                    submitNotice.innerHTML = "⚠️ टेस्टचे गुण व बरोबर/चूक उत्तरे पाहण्यासाठी कृपया तुमचे नाव, जिल्हा व १० अंकी WhatsApp नंबर भरा.";
                    submitNotice.style.background = "#fef3c7";
                    submitNotice.style.borderColor = "#f59e0b";
                    submitNotice.style.color = "#92400e";
                } else {
                    submitNotice.innerHTML = "⚠️ मोबाईल नंबर दुरुस्त करा. वैध नंबर टाकल्याशिवाय निकाल पाहता येणार नाही.";
                    submitNotice.style.background = "#fee2e2";
                    submitNotice.style.borderColor = "#ef4444";
                    submitNotice.style.color = "#991b1b";
                }
            }
        }

        window.onload = function() {
            startTimer();
            validateStudentDetails();
        };
    </script>
</head>
<body>
<div class="exam-header">
    <div>
        <h3 style="margin:0; font-size:18px;">⚔️ {{ test.test_title }}</h3>
        <small style="opacity:0.9;">राज्यस्तरीय पोलीस भरती सराव परीक्षा कक्ष</small>
    </div>
    <div class="timer-box">
        ⏳ वेळ: <span id="time-left">00:00</span>
    </div>
</div>

<div class="box">
    {% if error_msg %}
    <div style="background:#fee2e2; border:1.5px solid #ef4444; color:#991b1b; padding:12px; border-radius:6px; font-weight:bold; margin-bottom:15px; text-align:center;">
        {{ error_msg }}
    </div>
    {% endif %}

    <div style="background:#ecfdf5; border-left:4px solid #059669; padding:10px 15px; border-radius:6px; font-size:14px; color:#065f46; font-weight:bold; margin-bottom:20px;">
        📝 टेस्ट मोफत सुरू झाली आहे! खालील सर्व प्रश्न मन लावून सोडवा. टेस्ट सोडून झाल्यावर शेवटी आपले नाव, जिल्हा व नंबर टाकून लगेच निकाल व गुण तपासा.
    </div>

    <form id="examForm" method="POST" action="/submit_test/{{ test.id }}">
        <!-- सर्व प्रश्न थेट अनलॉक -->
        <div id="questionsArea">
            {% for q in questions %}
            <div class="q-item">
                <div class="q-text">प्र. {{ loop.index }}. {{ q.question }}</div>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="A"> A) {{ q.opt_a }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="B"> B) {{ q.opt_b }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="C"> C) {{ q.opt_c }}</label>
                <label class="opt-label"><input type="radio" name="q_{{ q.id }}" value="D"> D) {{ q.opt_d }}</label>
            </div>
            {% endfor %}
        </div>

        <!-- टेस्ट सोडवून झाल्यावर स्क्रीनवर निकाल पाहण्यासाठी विद्यार्थी माहिती -->
        <div class="student-details">
            <h4 style="margin:0 0 10px; color:#065f46; font-size:16px;">🎯 निकाल व बरोबर/चूक उत्तरे तपासण्यासाठी खालील माहिती भरा:</h4>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
                <div>
                    <label style="font-size:13px; font-weight:600;">पूर्ण नाव *:</label>
                    <input type="text" name="student_name" id="s_name" placeholder="उदा. राहुल तानाजी पाटील" onkeyup="validateStudentDetails()" required>
                </div>
                <div>
                    <label style="font-size:13px; font-weight:600;">जिल्हा *:</label>
                    <input type="text" name="district" id="s_dist" placeholder="उदा. कोल्हापूर" onkeyup="validateStudentDetails()" required>
                </div>
                <div>
                    <label style="font-size:13px; font-weight:600;">WhatsApp मोबाईल नंबर *:</label>
                    <input type="tel" name="phone" id="s_phone" placeholder="10 अंकी मोबाईल नंबर" pattern="[6-9][0-9]{9}" maxlength="10" onkeyup="validateStudentDetails()" required>
                    <div id="phoneErrorNotice" class="phone-error-msg"></div>
                </div>
            </div>
        </div>

        <div id="submitNotice" class="submit-notice">
            ⚠️ टेस्टचे गुण व बरोबर/चूक उत्तरे पाहण्यासाठी कृपया तुमचे नाव, जिल्हा व १० अंकी WhatsApp नंबर भरा.
        </div>

        <button type="submit" id="submitBtn" class="btn-submit" disabled>🏆 टेस्ट सबमिट करा आणि गुण व अचूक उत्तरे पहा</button>
    </form>
</div>
</body>
</html>'''

# ----------------- PAID ACCESS CHECK TEMPLATE -----------------
ACCESS_CHECK_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>पेमेंट पडताळणी - {{ test.test_title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .box { max-width: 500px; width: 100%; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        h2 { margin: 0 0 5px; color: #065f46; text-align: center; font-size: 20px; }
        input[type="text"], input[type="tel"] { width: 100%; padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
        .btn { width: 100%; background: #059669; color: white; padding: 12px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 15px; }
        .phone-error-msg { display: none; color: #b91c1c; font-size: 12px; font-weight: bold; background: #fee2e2; border-left: 3px solid #dc2626; padding: 6px 10px; border-radius: 4px; margin-bottom: 10px; line-height: 1.4; }
    </style>
    <script>
        async function checkFreePass(val) {
            const phone = val.trim();
            const phoneErrDiv = document.getElementById('phoneErrorNoticePaid');
            const submitBtn = document.getElementById('submitBtn');
            const infoDiv = document.getElementById('freePassInfo');
            const paySection = document.getElementById('paymentSection');

            if (phone.length > 0 && !['6', '7', '8', '9'].includes(phone.charAt(0))) {
                phoneErrDiv.style.display = 'block';
                phoneErrDiv.innerText = '⚠️ आपण चुकीचा मोबाईल नंबर टाकत आहात!';
                submitBtn.disabled = true;
                return;
            } else {
                phoneErrDiv.style.display = 'none';
                submitBtn.disabled = false;
            }

            if (phone.length === 10 && /^[6-9][0-9]{9}$/.test(phone)) {
                try {
                    const res = await fetch(`/api/check_free_pass?phone=${phone}`);
                    const data = await res.json();
                    if (data.is_free) {
                        infoDiv.style.display = 'block';
                        paySection.style.display = 'none';
                        submitBtn.innerText = '✨ मोफत प्रवेश मिळवा व टेस्ट सुरू करा';
                        submitBtn.style.background = '#16a34a';
                    } else {
                        infoDiv.style.display = 'none';
                        paySection.style.display = 'block';
                        submitBtn.innerText = '🚀 ॲडमिनकडे पडताळणीसाठी पाठवा';
                        submitBtn.style.background = '#059669';
                    }
                } catch(e) { console.error(e); }
            }
        }
    </script>
</head>
<body>
<div class="box">
    <h2>🔒 सशुल्क टेस्ट प्रवेश द्वार</h2>
    <p style="text-align:center; font-size:13px; color:#475569;">{{ test.test_title }} (फी: ₹{{ test.test_fee }})</p>

    <div id="freePassInfo" style="display:none; background:#dcfce7; border:1.5px solid #86efac; color:#166534; padding:12px; border-radius:6px; font-size:13px; font-weight:bold; text-align:center; margin-bottom:15px;">
        🎉 अभिनंदन! तुमचा मोबाईल नंबर ॲडमिन विशेष सवलत यादीत आहे. तुम्हाला ही सशुल्क टेस्ट १००% मोफत सोडवता येईल!
    </div>
    
    <div id="paymentSection" style="background:#fffbeb; padding:15px; border-radius:6px; border:1px solid #fcd34d; text-align:center; margin-bottom:15px;">
        <p style="margin:0 0 10px; font-weight:bold; color:#92400e; font-size:13px;">QR कोड स्कॅन करून किंवा <b>{{ upi_mobile }}</b> वर पे करा:</p>
        <img src="{{ qr_url }}" alt="QR" style="max-width:160px; max-height:160px; border-radius:6px; border:1px solid #cbd5e1;">
        <p style="font-size:12px; color:#b45309; font-weight:bold; margin-top:8px;">⚠️ पेमेंट करून झाल्यावर <b>{{ upi_mobile }}</b> या नंबरवर नाव व पेमेंट स्क्रीनशॉट पाठवा!</p>
    </div>

    <form method="POST" action="/request_paid_test/{{ test.id }}">
        <label style="font-size:13px; font-weight:bold;">पूर्ण नाव:</label>
        <input type="text" name="student_name" placeholder="तुमचे नाव" required>
        <label style="font-size:13px; font-weight:bold;">जिल्हा:</label>
        <input type="text" name="district" placeholder="जिल्हा" required>
        <label style="font-size:13px; font-weight:bold;">व्हॉट्सॲप मोबाईल नंबर:</label>
        <input type="tel" name="phone" placeholder="10 अंकी मोबाईल नंबर" pattern="[6-9][0-9]{9}" maxlength="10" onkeyup="checkFreePass(this.value)" required>
        <div id="phoneErrorNoticePaid" class="phone-error-msg"></div>
        <button type="submit" id="submitBtn" class="btn">🚀 ॲडमिनकडे पडताळणीसाठी पाठवा</button>
    </form>
    <div style="text-align:center; margin-top:15px;"><a href="/" style="font-size:12px; color:#0284c7; text-decoration:none;">⬅️ मुख्य पानावर जा</a></div>
</div>
</body>
</html>'''

# ----------------- 3. RESULT SUBMISSION SUMMARY (स्क्रीनवर लगेच गुण + बरोबर/चूक प्रश्न) -----------------
RESULT_SUMMARY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>टेस्ट निकाल - सविस्तर विश्लेषण</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f0fdf4; color: #1e293b; padding: 15px; }
        .box { max-width: 820px; margin: 15px auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 6px solid #059669; }
        .score-card { background: linear-gradient(135deg, #ecfdf5, #d1fae5); border: 2px solid #86efac; border-radius: 10px; padding: 20px; text-align: center; margin-bottom: 25px; }
        .score-num { font-size: 32px; font-weight: bold; color: #065f46; margin: 10px 0; }
        .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-top: 15px; }
        .stat-item { background: white; padding: 10px; border-radius: 6px; font-size: 13px; font-weight: bold; border: 1px solid #cbd5e1; }
        .item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .correct-box { border-left: 6px solid #16a34a; }
        .wrong-box { border-left: 6px solid #dc2626; }
        .cert-box { background: linear-gradient(135deg, #fefce8, #fef3c7); border: 4px double #d97706; padding: 20px; border-radius: 10px; margin: 25px 0; text-align: center; }
        .highlight-share { background: linear-gradient(135deg, #fef9c3, #fef08a); border: 2px dashed #ca8a04; border-radius: 10px; padding: 18px 20px; margin-top: 25px; text-align: center; }
        .promo-box { background: #f8fafc; border: 1.5px solid #cbd5e1; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; }
        .btn-link { display: inline-block; background: #25D366; color: white; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 13px; margin: 4px; }
    </style>
</head>
<body>
<div class="box">
    <h2 style="color:#065f46; margin:0 0 5px; text-align:center;">🎉 तुमची टेस्ट यशस्वीरीत्या सबमिट झाली!</h2>
    <p style="font-size:14px; color:#64748b; margin-bottom:15px; text-align:center;">राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</p>

    <!-- गुण, रँक व विद्यार्थी माहिती -->
    <div class="score-card">
        <h3 style="margin:0; color:#0f172a;">👤 {{ lead.student_name }} ({{ lead.district }})</h3>
        <p style="margin:5px 0; color:#475569; font-size:13px;">मोबाईल: <b>{{ lead.phone }}</b> | टेस्ट: <b>{{ lead.test_name }}</b></p>
        <div class="score-num">मिळालेले गुण: {{ lead.score }} / {{ lead.total_marks }}</div>
        <p style="font-size:20px; color:#b45309; font-weight:bold; margin:6px 0;">
            🏆 संपूर्ण महाराष्ट्रातील तुमचा रँक: <b style="color:#047857; font-size:24px;">#{{ state_rank }}</b>
        </p>

        <div class="stat-grid">
            <div class="stat-item" style="color:#16a34a;">✅ बरोबर: {{ lead.score|int }}</div>
            <div class="stat-item" style="color:#dc2626;">❌ चुकलेले: {{ (lead.total_marks - lead.score)|int }}</div>
            <div class="stat-item" style="color:#0284c7;">🎯 टक्केवारी: {{ "%.2f"|format((lead.score / lead.total_marks) * 100) if lead.total_marks > 0 else 0 }}%</div>
        </div>
    </div>

    <!-- लगेच स्क्रीनवर बरोबर व चुकलेले प्रश्न स्पष्टीकरणासह -->
    <h3 style="color:#065f46; border-bottom:2px solid #86efac; padding-bottom:6px; margin-top:30px;">📋 तुमचे कोणते प्रश्न चुकले व कोणते बरोबर आले ते पहा:</h3>

    {% for item in evaluated_questions %}
    <div class="item {{ 'correct-box' if item.is_correct else 'wrong-box' }}">
        <div style="font-weight:bold; font-size:15px; margin-bottom:8px; color:#0f172a;">
            प्र. {{ loop.index }}. {{ item.q_text }}
        </div>
        
        <div style="font-size:13px; margin-bottom:6px; padding-left:10px; color:#334155;">
            A) {{ item.opt_a }} &nbsp;|&nbsp; B) {{ item.opt_b }} &nbsp;|&nbsp; C) {{ item.opt_c }} &nbsp;|&nbsp; D) {{ item.opt_d }}
        </div>

        <div style="display:flex; gap:20px; font-size:14px; margin:8px 0; padding-left:10px;">
            <div>तुमचे उत्तर: <b style="color:{{ '#16a34a' if item.is_correct else '#dc2626' }};">{{ item.user_ans }}</b></div>
            <div>अचूक उत्तर: <b style="color:#16a34a;">{{ item.correct_ans }}</b></div>
            <div>स्थिती: <b style="color:{{ '#16a34a' if item.is_correct else '#dc2626' }};">{{ '✅ बरोबर' if item.is_correct else '❌ चूक' }}</b></div>
        </div>

        {% if item.explanation %}
        <div style="font-size:12.5px; color:#166534; background:#f0fdf4; padding:8px 12px; border-radius:6px; margin-top:8px; border:1px solid #bbf7d0;">
            💡 <b>स्पष्टीकरण:</b> {{ item.explanation }}
        </div>
        {% endif %}
    </div>
    {% endfor %}

    <!-- डिजिटल प्रशस्तीपत्र -->
    <div class="cert-box">
        <h3 style="color:#92400e; margin:0 0 5px;">📜 सहभाग व अभिनंदन डिजिटल प्रशस्तीपत्र</h3>
        <p style="font-size:12px; color:#78350f; margin-bottom:12px;">राज्यस्तरीय ऑनलाईन सराव कक्ष</p>
        <div style="background:white; padding:15px; border-radius:6px; border:1px dashed #b45309;">
            <p style="font-size:13px; margin:4px 0;">प्रमाणित करण्यात येते की,</p>
            <h2 style="color:#065f46; margin:6px 0; font-size:22px;">{{ lead.student_name }}</h2>
            <p style="font-size:13px; margin:4px 0;">यांनी <b>{{ lead.test_name }}</b> मध्ये <b>{{ lead.score }}/{{ lead.total_marks }}</b> गुण मिळवून यशस्वी सहभाग नोंदवला.</p>
        </div>
    </div>

    <!-- WhatsApp शेअर -->
    <div class="highlight-share">
        <h3 style="margin:0 0 6px; color:#854d0e; font-size:16px;">🔥 राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका 🔥</h3>
        <p style="font-size:13px; color:#713f12; margin:6px 0 12px; line-height:1.5;">
            ही मोफत सराव टेस्ट आपल्या भरती करणाऱ्या सर्व मित्रांना <b>WhatsApp ग्रुप्सवर नक्की शेअर करा!</b>
        </p>
        <a href="https://wa.me/?text={{ share_whatsapp_encoded }}" target="_blank" style="background:#25D366; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px; display:inline-block;">📲 मित्रांना WhatsApp वर शेअर करा</a>
    </div>

    <!-- सोशल मीडिया -->
    <div class="promo-box">
        <h4 style="margin:0 0 8px; color:#065f46;">🌟 अधिकृत सोशल मीडिया व यशोगाथा लिंक्स:</h4>
        {% if insta_link %}<a href="{{ insta_link }}" target="_blank" class="btn-link" style="background:#E1306C;">📸 Instagram</a>{% endif %}
        {% if yt_link %}<a href="{{ yt_link }}" target="_blank" class="btn-link" style="background:#FF0000;">▶ YouTube</a>{% endif %}
        {% if toppers_link %}<a href="{{ toppers_link }}" target="_blank" class="btn-link" style="background:#0284c7;">🏆 यशवंतांचे फोटो</a>{% endif %}
    </div>

    <div style="margin-top:20px; text-align:center;">
        <a href="/" style="background:#0b3c5d; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px;">🏠 मुख्य पानावर जा</a>
    </div>
</div>
</body>
</html>'''

# ----------------- EDIT SINGLE QUESTION TEMPLATE -----------------
EDIT_QUESTION_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><title>प्रश्न संपादित करा</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f1f5f9; padding: 20px; }
        .box { max-width: 650px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 5px solid #059669; }
        input, textarea, select { width: 100%; padding: 9px; margin: 6px 0 14px; border: 1px solid #cbd5e1; border-radius: 5px; }
        .btn { background: #059669; color: white; border: none; padding: 10px 18px; border-radius: 5px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
<div class="box">
    <h3 style="color:#065f46; margin-top:0;">✏️ प्रश्न व पर्याय संपादित करा (ID: {{ q.id }})</h3>
    <form method="POST">
        <label style="font-weight:600; font-size:13px;">प्रश्न:</label>
        <textarea name="question" rows="3" required>{{ q.question }}</textarea>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
            <div>
                <label style="font-weight:600; font-size:13px;">पर्याय A:</label>
                <input type="text" name="opt_a" value="{{ q.opt_a }}" required>
            </div>
            <div>
                <label style="font-weight:600; font-size:13px;">पर्याय B:</label>
                <input type="text" name="opt_b" value="{{ q.opt_b }}" required>
            </div>
            <div>
                <label style="font-weight:600; font-size:13px;">पर्याय C:</label>
                <input type="text" name="opt_c" value="{{ q.opt_c }}" required>
            </div>
            <div>
                <label style="font-weight:600; font-size:13px;">पर्याय D:</label>
                <input type="text" name="opt_d" value="{{ q.opt_d }}" required>
            </div>
        </div>

        <label style="font-weight:600; font-size:13px;">अचूक उत्तर:</label>
        <select name="correct">
            <option value="A" {% if q.correct=='A' %}selected{% endif %}>A</option>
            <option value="B" {% if q.correct=='B' %}selected{% endif %}>B</option>
            <option value="C" {% if q.correct=='C' %}selected{% endif %}>C</option>
            <option value="D" {% if q.correct=='D' %}selected{% endif %}>D</option>
        </select>

        <label style="font-weight:600; font-size:13px;">स्पष्टीकरण:</label>
        <textarea name="explanation" rows="2">{{ q.explanation }}</textarea>

        <button type="submit" class="btn">💾 बदल सेव्ह करा</button>
        <a href="/admin/dashboard?tab=questions&filter_test_id={{ q.test_id }}" style="margin-left:10px; color:#dc2626; text-decoration:none; font-weight:600;">रद्द करा</a>
    </form>
</div>
</body>
</html>'''

# ----------------- 4. DETAILED ANSWER KEY TEMPLATE -----------------
DETAILED_KEY_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>सविस्तर उत्तरपत्रिका व स्पष्टीकरण</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f8fafc; color: #1e293b; padding: 15px; }
        .box { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border-top: 6px solid #059669; }
        .item { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .correct-box { border-left: 5px solid #16a34a; }
        .wrong-box { border-left: 5px solid #dc2626; }
        .highlight-share { background: linear-gradient(135deg, #fef9c3, #fef08a); border: 2px dashed #ca8a04; border-radius: 10px; padding: 18px 20px; margin-top: 25px; text-align: center; }
        .feedback-card { background: #f0fdf4; border: 2px dashed #059669; border-radius: 10px; padding: 20px; margin-top: 20px; }
        .feedback-card textarea { width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; margin: 10px 0; }
        .btn-feedback { background: #059669; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
<div class="box">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">
        <span style="font-size:12px; font-weight:bold; color:#065f46;">📖 राज्यस्तरीय सराव परीक्षा स्पष्टीकरण कक्ष</span>
        <a href="/" style="background:#0284c7; color:white; padding:6px 14px; border-radius:5px; text-decoration:none; font-weight:bold; font-size:12px;">🏠 मुख्य पानावर जा</a>
    </div>

    <h2 style="color:#065f46; margin:0 0 5px; text-align:center;">📋 सविस्तर उत्तरपत्रिका व स्पष्टीकरण</h2>
    <p style="text-align:center; font-size:13px; color:#64748b; margin-bottom:20px;">विद्यार्थी: <b>{{ lead.student_name }}</b> (जिल्हा: {{ lead.district }})</p>

    {% for item in evaluated_questions %}
    <div class="item {{ 'correct-box' if item.is_correct else 'wrong-box' }}">
        <div style="font-weight:bold; font-size:15px; margin-bottom:8px; color:#0f172a;">
            प्र. {{ loop.index }}. {{ item.q_text }}
        </div>
        <div style="font-size:13px; margin-bottom:4px; padding-left:10px;">
            A) {{ item.opt_a }} &nbsp;|&nbsp; B) {{ item.opt_b }} &nbsp;|&nbsp; C) {{ item.opt_c }} &nbsp;|&nbsp; D) {{ item.opt_d }}
        </div>
        <div style="display:flex; gap:15px; font-size:13px; margin:8px 0; padding-left:10px;">
            <div>तुमचे उत्तर: <b style="color:{{ 'green' if item.is_correct else 'red' }}; font-size:15px;">{{ item.user_ans }}</b></div>
            <div>अचूक उत्तर: <b style="color:#16a34a; font-size:15px;">{{ item.correct_ans }}</b></div>
        </div>
        {% if item.explanation %}
        <div style="font-size:12px; color:#166534; background:#f0fdf4; padding:8px 12px; border-radius:6px; margin-top:6px; border:1px solid #bbf7d0;">
            💡 <b>स्पष्टीकरण:</b> {{ item.explanation }}
        </div>
        {% endif %}
    </div>
    {% endfor %}

    <div class="highlight-share">
        <h3 style="margin:0 0 6px; color:#854d0e; font-size:16px;">🔥 राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका 🔥</h3>
        <p style="font-size:13.5px; color:#713f12; margin:6px 0 12px; line-height:1.6; font-weight:500;">
            अशाच दर्जेदार राज्यस्तरीय सराव प्रश्नपत्रिका सोडवण्यासाठी आणि संपूर्ण महाराष्ट्रात आपला रँक तपासण्यासाठी ही लिंक आपल्या मित्रांना <b>WhatsApp वर नक्की शेअर करा!</b>
        </p>
        <div style="display:flex; justify-content:center; gap:10px; flex-wrap:wrap;">
            <a href="https://wa.me/?text={{ share_whatsapp_encoded }}" target="_blank" style="background:#25D366; color:white; padding:9px 18px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px;">📲 मित्रांना WhatsApp वर शेअर करा</a>
            <a href="/" style="background:#0f172a; color:white; padding:9px 18px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px;">🔗 मुख्य टेस्ट पोर्टलवर जा</a>
        </div>
    </div>

    <div class="feedback-card">
        <h4 style="margin:0; color:#065f46;">✍ आपला मौल्यवान अभिप्राय (Feedback) नोंदवा:</h4>
        <p style="font-size:12px; color:#64748b; margin:4px 0 0;">ही टेस्ट सोडवण्याचा तुमचा अनुभव कसा होता? नक्की कळवा:</p>
        {% if feedback_done %}
        <div style="background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-weight:bold; font-size:13px; margin-top:10px; text-align:center;">
            ✅ धन्यवाद! तुमचा अभिप्राय यशस्वीरीत्या सेव्ह झाला आहे.
        </div>
        {% else %}
        <form method="POST" action="/submit_feedback/{{ lead.id }}">
            <textarea name="feedback_text" rows="3" placeholder="येथे आपला अभिप्राय लिहा..." required></textarea>
            <button type="submit" class="btn-feedback">📩 अभिप्राय सबमिट करा</button>
        </form>
        {% endif %}
    </div>

    <div style="text-align:center; margin-top:25px;">
        <a href="/" style="background:#0284c7; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px;">🏠 मुख्य पानावर जा</a>
    </div>
</div>
</body>
</html>'''

# ----------------- 5. ADMIN LOGIN TEMPLATE -----------------
ADMIN_LOGIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ॲडमिन सुरक्षित लॉगिन</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #0f172a; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-box { background: #1e293b; padding: 35px 30px; border-radius: 10px; width: 360px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); border-top: 5px solid #059669; text-align: center; }
        h2 { margin: 0 0 15px; color: #34d399; font-size: 22px; }
        input { width: 100%; padding: 12px; margin: 15px 0 20px; border-radius: 6px; border: 1.5px solid #475569; background: #0f172a; color: white; font-size: 14px; text-align: center; outline: none; }
        button { width: 100%; background: #059669; color: white; border: none; padding: 12px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 15px; }
        .err { color: #f87171; font-size: 13px; font-weight: bold; margin-bottom: 12px; }
    </style>
</head>
<body>
<div class="login-box">
    <h2>⚙️ ॲडमिन सुरक्षित कक्ष</h2>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <form method="POST" action="/admin/login">
        <label style="font-size:13px; color:#cbd5e1;">पासवर्ड टाका:</label>
        <input type="password" name="admin_pass" placeholder="पासवर्ड टाका" required autocomplete="off">
        <button type="submit">🔐 लॉगिन करा</button>
    </form>
    <div style="margin-top:20px;"><a href="/" style="color:#38bdf8; font-size:12px; text-decoration:none;">⬅️️ मुख्य वेबसाईटवर जा</a></div>
</div>
</body>
</html>'''

# ----------------- 6. ADMIN DASHBOARD TEMPLATE -----------------
ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ॲडमिन डॅशबोर्ड</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { margin: 0; background: #f1f5f9; color: #1e293b; padding: 15px; }
        .container { max-width: 1150px; margin: 0 auto; background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        h2 { margin: 0 0 15px; color: #065f46; text-align: center; }
        .nav-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
        .nav-tabs a { padding: 8px 14px; background: #e2e8f0; color: #334155; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; }
        .nav-tabs a.active { background: #059669; color: white; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }
        th { background: #f8fafc; color: #0f172a; }
        input[type="text"], input[type="number"], select, textarea { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; margin-bottom: 8px; font-size: 13px; }
        .btn { background: #059669; color: white; padding: 8px 14px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
        .btn-sm { padding: 4px 8px; font-size: 11px; text-decoration: none; border-radius: 3px; display: inline-block; }
    </style>
    <script>
        function togglePassVis() {
            var p = document.getElementById("new_password");
            var btn = document.getElementById("passEyeBtn");
            if (p.type === "password") { 
                p.type = "text"; 
                btn.innerText = "🙈";
            } else { 
                p.type = "password"; 
                btn.innerText = "👁️";
            }
        }
        function openAiAssist(inputId) {
            var qVal = document.getElementById(inputId).value.trim();
            if (!qVal) {
                alert("कृपया आधी प्रश्न टाईप करा किंवा पेस्ट करा!");
                return;
            }
            var query = encodeURIComponent("मराठी पोलीस भरती प्रश्न अचूक व्याकरण, अचूक पर्याय आणि स्पष्टीकरण: " + qVal);
            window.open("https://www.google.com/search?q=" + query, "_blank");
        }
    </script>
</head>
<body>
<div class="container">
    <h2>⚙️ राज्यस्तरीय परीक्षा प्लॅटफॉर्म - ॲडमिन डॅशबोर्ड</h2>
    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
        <a href="/" style="font-weight:bold; color:#0284c7; text-decoration:none;">⬅️ मुख्य वेबसाईटवर जा</a>
        <a href="/admin/logout" style="font-weight:bold; color:#dc2626; text-decoration:none;">🚪 लॉगआऊट</a>
    </div>

    <div class="nav-tabs">
        <a href="/admin/dashboard?tab=leads" class="{{ 'active' if active_tab == 'leads' else '' }}">📱 Leads (चौकशी व फिल्टर्स)</a>
        <a href="/admin/dashboard?tab=payments" class="{{ 'active' if active_tab == 'payments' else '' }}">💰 Payments & QR (पेमेंट्स व QR)</a>
        <a href="/admin/dashboard?tab=special" class="{{ 'active' if active_tab == 'special' else '' }}">👑 Special Access (खास सवलती)</a>
        <a href="/admin/dashboard?tab=questions" class="{{ 'active' if active_tab == 'questions' else '' }}">📝 Questions (प्रश्न व्यवस्थापन व AI)</a>
        <a href="/admin/dashboard?tab=launch" class="{{ 'active' if active_tab == 'launch' else '' }}">🚀 Test Launch & Edit (टेस्ट व्यवस्थापन)</a>
        <a href="/admin/dashboard?tab=leaderboard" class="{{ 'active' if active_tab == 'leaderboard' else '' }}">🏆 Leaderboard (टॉपर लिस्ट)</a>
        <a href="/admin/dashboard?tab=feedback" class="{{ 'active' if active_tab == 'feedback' else '' }}">💬 Feedback (विद्यार्थी अभिप्राय)</a>
        <a href="/admin/dashboard?tab=notices" class="{{ 'active' if active_tab == 'notices' else '' }}">📢 Recruitment PDF (भरती PDF व्यवस्थापन)</a>
        <a href="/admin/dashboard?tab=settings" class="{{ 'active' if active_tab == 'settings' else '' }}">🔐 Security & Settings</a>
    </div>

    <!-- 1. LEADS SUB-TAB -->
    {% if active_tab == 'leads' %}
    <h3>📱 विद्यार्थ्यांची लीड्स यादी (जिल्हा व टेस्ट वाईस ऑटो-फिल्टर)</h3>
    <div style="background:#f8fafc; padding:12px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:15px;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <input type="hidden" name="tab" value="leads">
            <label style="font-size:12px; font-weight:bold;">जिल्हा फिल्टर:</label>
            <select name="lead_dist" style="width:160px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व जिल्हे --</option>
                {% for d in all_districts %}<option value="{{ d }}" {% if lead_dist==d %}selected{% endif %}>{{ d }}</option>{% endfor %}
            </select>

            <label style="font-size:12px; font-weight:bold; margin-left:10px;">टेस्ट फिल्टर:</label>
            <select name="lead_test_id" style="width:200px; margin-bottom:0;" onchange="this.form.submit()">
                <option value="">-- सर्व टेस्ट्स --</option>
                {% for t in tests %}<option value="{{ t.id }}" {% if lead_test_id==t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <a href="/admin/dashboard?tab=leads" class="btn-sm" style="background:#64748b; color:white;">Clear</a>
        </form>
    </div>

    <table>
        <tr><th>दिनांक</th><th>विद्यार्थी नाव</th><th>जिल्हा</th><th>WhatsApp नंबर</th><th>टेस्टचे नाव</th><th>गुण</th><th>कृती</th></tr>
        {% for l in leads %}
        <tr>
            <td>{{ l.test_date }}</td>
            <td><b>{{ l.student_name }}</b></td>
            <td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td>
            <td><b>{{ l.score }} / {{ l.total_marks }}</b></td>
            <td>
                <a href="/admin/delete_lead/{{ l.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('ही लीड डिलीट करायची का?');">🗑️ डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 2. PAYMENTS SUB-TAB -->
    {% elif active_tab == 'payments' %}
    <h3>💰 पेमेंट व QR कोड व्यवस्थापन</h3>
    <div style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <h4 style="margin:0 0 10px; color:#065f46;">💳 पेमेंट मोबाईल नंबर व QR कोड अपडेट करा:</h4>
        <form method="POST" action="/admin/update_payment_settings" enctype="multipart/form-data">
            <label style="font-weight:bold; font-size:12px;">पेमेंट मोबाईल नंबर / UPI ID:</label>
            <input type="text" name="upi_mobile" value="{{ upi_mobile }}" required>
            <label style="font-weight:bold; font-size:12px;">QR कोड इमेज URL (किंवा खालील फाईल अपलोड करा):</label>
            <input type="text" name="qr_url" value="{{ qr_url }}">
            <label style="font-weight:bold; font-size:12px;">किंवा नवीन QR कोड फाईल अपलोड करा (JPG/PNG):</label>
            <input type="file" name="qr_file" accept="image/*" style="margin-bottom:10px;">
            <button type="submit" class="btn">💾 पेमेंट सेटिंग्ज अपडेट करा</button>
        </form>
    </div>

    <table>
        <tr><th>विद्यार्थी नाव</th><th>मोबाईल</th><th>टेस्ट</th><th>स्थिती</th><th>कृती</th></tr>
        {% for p in payments %}
        <tr>
            <td>{{ p.student_name }}</td>
            <td>{{ p.phone }}</td>
            <td>{{ p.test_name }}</td>
            <td><span style="color:{{ 'green' if p.payment_status == 'Approved' else 'orange' }}; font-weight:bold;">{{ p.payment_status }}</span></td>
            <td>
                {% if p.payment_status != 'Approved' %}
                <form method="POST" action="/admin/approve_payment/{{ p.id }}" style="display:inline-block;">
                    <button type="submit" class="btn-sm" style="background:#16a34a; color:white; border:none; padding:5px 10px; cursor:pointer;">✅ २४ तासांसाठी Unlock करा</button>
                </form>
                {% else %}
                <span style="color:green; font-weight:bold;">Approved (Active)</span>
                {% endif %}
                <a href="/admin/delete_payment/{{ p.id }}" class="btn-sm" style="background:#dc2626; color:white; margin-left:5px;" onclick="return confirm('ही पेमेंट नोंद डिलीट करायची का?');">🗑 डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- SPECIAL ACCESS SUB-TAB -->
    {% elif active_tab == 'special' %}
    <h3>👑 Special Access (विद्यार्थी विशेष सवलत व्यवस्थापन कक्ष)</h3>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:25px; margin-top:15px;">
        <div style="background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:10px; padding:18px;">
            <h4 style="margin-top:0; color:#065f46;">🔄 १. अमर्याद प्रयत्न सवलत (Unlimited Attempts)</h4>
            <p style="font-size:12px; color:#64748b; line-height:1.4; margin-top:-4px;">
                या यादीत असलेल्या नंबरवरून विद्यार्थी कोणतीही टेस्ट कितीही वेळा पुन्हा पुन्हा सोडवू शकतात.
            </p>
            <form method="POST" action="/admin/add_special_unlimited">
                <input type="text" name="phone" placeholder="१० अंकी मोबाईल नंबर टाका" pattern="[6-9][0-9]{9}" required>
                <input type="text" name="student_name" placeholder="विद्यार्थ्याचे नाव (ऐच्छिक)">
                <input type="text" name="note" placeholder="टीप / संदर्भ (उदा. ॲडमिन, शिक्षक, VIP)">
                <button type="submit" class="btn" style="width:100%; background:#059669;">➕ अमर्याद सवलतीत जोडा</button>
            </form>
            <h5 style="margin:15px 0 6px; color:#334155;">सध्या जोडलेले नंबर ({{ unlimited_list|length }}):</h5>
            <table style="font-size:12px;">
                <tr><th>मोबाईल नंबर</th><th>नाव / टीप</th><th>कृती</th></tr>
                {% for u in unlimited_list %}
                <tr>
                    <td><b>{{ u.phone }}</b></td>
                    <td>{{ u.student_name }} <br><small style="color:#64748b;">{{ u.note }}</small></td>
                    <td><a href="/admin/delete_special_unlimited/{{ u.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('हा नंबर काढायचा का?');">🗑️</a></td>
                </tr>
                {% else %}
                <tr><td colspan="3" style="text-align:center; color:#94a3b8;">कोणताही नंबर जोडलेला नाही.</td></tr>
                {% endfor %}
            </table>
        </div>

        <div style="background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:10px; padding:18px;">
            <h4 style="margin-top:0; color:#b45309;">⭐ २. सर्व सशुल्क टेस्ट्स मोफत (All Tests Free Pass)</h4>
            <p style="font-size:12px; color:#64748b; line-height:1.4; margin-top:-4px;">
                या यादीत असलेल्या नंबरसाठी सर्व सशुल्क टेस्ट्स मोफत राहतील.
            </p>
            <form method="POST" action="/admin/add_special_free_pass">
                <input type="text" name="phone" placeholder="१० अंकी मोबाईल नंबर टाका" pattern="[6-9][0-9]{9}" required>
                <input type="text" name="student_name" placeholder="विद्यार्थ्याचे नाव (ऐच्छिक)">
                <input type="text" name="note" placeholder="टीप / संदर्भ (उदा. अकॅडमी विद्यार्थी, टॉपर)">
                <button type="submit" class="btn" style="width:100%; background:#d97706;">➕ मोफत पास यादीत जोडा</button>
            </form>
            <h5 style="margin:15px 0 6px; color:#334155;">सध्या जोडलेले नंबर ({{ free_pass_list|length }}):</h5>
            <table style="font-size:12px;">
                <tr><th>मोबाईल नंबर</th><th>नाव / टीप</th><th>कृती</th></tr>
                {% for f in free_pass_list %}
                <tr>
                    <td><b>{{ f.phone }}</b></td>
                    <td>{{ f.student_name }} <br><small style="color:#64748b;">{{ f.note }}</small></td>
                    <td><a href="/admin/delete_special_free_pass/{{ f.id }}" class="btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('हा नंबर काढायचा का?');">🗑️</a></td>
                </tr>
                {% else %}
                <tr><td colspan="3" style="text-align:center; color:#94a3b8;">कोणताही नंबर जोडलेला नाही.</td></tr>
                {% endfor %}
            </table>
        </div>
    </div>

    <!-- 3. QUESTIONS SUB-TAB -->
    {% elif active_tab == 'questions' %}
    <h3>📝 प्रश्न व्यवस्थापन (Typing Form with AI Assist & Bulk Upload)</h3>
    <div style="background:#ecfdf5; padding:15px; border-radius:6px; margin-bottom:20px; border:1px solid #a7f3d0;">
        <form method="GET" action="/admin/dashboard" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <input type="hidden" name="tab" value="questions">
            <label style="font-weight:bold; font-size:13px; color:#065f46;">प्रश्न पाहण्यासाठी टेस्ट निवडा:</label>
            <select name="filter_test_id" onchange="this.form.submit()" style="max-width:320px; margin-bottom:0;">
                <option value="">-- सर्व टेस्ट्सचे प्रश्न --</option>
                {% for t in tests %}
                <option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>
                {% endfor %}
            </select>
        </form>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:25px;">
        <form method="POST" action="/admin/add_question" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h4 style="margin:0; color:#065f46;">➕ एक प्रश्न टाईप करा / ॲड करा</h4>
                <button type="button" onclick="openAiAssist('single_q_text')" style="background:#8b5cf6; color:white; border:none; padding:4px 9px; border-radius:4px; font-size:11px; cursor:pointer; font-weight:bold;">🤖 AI Assist</button>
            </div>
            <label style="font-weight:bold; font-size:12px; margin-top:8px; display:block;">टेस्ट निवडा:</label>
            <select name="test_id">
                {% for t in tests %}<option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <label style="font-weight:bold; font-size:12px;">प्रश्न:</label>
            <input type="text" name="question" id="single_q_text" placeholder="प्रश्नाची माहिती लिहा किंवा पेस्ट करा" required>
            <input type="text" name="opt_a" placeholder="पर्याय A" required>
            <input type="text" name="opt_b" placeholder="पर्याय B" required>
            <input type="text" name="opt_c" placeholder="पर्याय C" required>
            <input type="text" name="opt_d" placeholder="पर्याय D" required>
            <label style="font-weight:bold; font-size:12px;">अचूक उत्तर (A, B, C किंवा D):</label>
            <input type="text" name="correct" placeholder="उदा. B" maxlength="1" required style="width:100px;">
            <label style="font-weight:bold; font-size:12px;">स्पष्टीकरण:</label>
            <input type="text" name="explanation" placeholder="स्पष्टीकरण लिहा">
            <button type="submit" class="btn" style="margin-top:5px;">प्रश्न सेव्ह करा</button>
        </form>

        <form method="POST" action="/admin/bulk_questions" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h4 style="margin:0; color:#065f46;">⚡ बल्क प्रश्न अपलोडर</h4>
                <button type="button" onclick="openAiAssist('bulk_q_area')" style="background:#8b5cf6; color:white; border:none; padding:4px 9px; border-radius:4px; font-size:11px; cursor:pointer; font-weight:bold;">🤖 AI Assist</button>
            </div>
            <label style="font-weight:bold; font-size:12px; margin-top:8px; display:block;">टेस्ट निवडा:</label>
            <select name="test_id" required>
                {% for t in tests %}<option value="{{ t.id }}" {% if filter_test_id == t.id|string %}selected{% endif %}>{{ t.test_title }}</option>{% endfor %}
            </select>
            <label style="font-weight:bold; font-size:12px;">फॉरमॅट: प्रश्न | पर्यायA | पर्यायB | पर्यायC | पर्यायD | अचूक उत्तर | स्पष्टीकरण</label>
            <textarea name="bulk_questions_text" id="bulk_q_area" rows="6" placeholder="महाराष्ट्राची राजधानी कोणती? | पुणे | मुंबई | नागपूर | नाशिक | B | मुंबई ही प्रशासकीय राजधानी आहे." required></textarea>
            <button type="submit" class="btn" style="margin-top:8px; background:#0284c7; width:100%;">📥 बल्क प्रश्न सेव्ह करा</button>
        </form>
    </div>

    <h4>प्रश्नांची यादी व संपादन (Edit):</h4>
    <table>
        <tr><th>ID</th><th>प्रश्न</th><th>अचूक</th><th>स्पष्टीकरण</th><th>कृती (Actions)</th></tr>
        {% for q in all_questions %}
        <tr>
            <td>{{ q.id }}</td>
            <td><b>{{ q.question }}</b></td>
            <td style="color:green; font-weight:bold;">{{ q.correct }}</td>
            <td style="color:#475569; font-size:12px;">{{ q.explanation }}</td>
            <td style="white-space:nowrap;">
                <a href="/admin/edit_question/{{ q.id }}" class="btn-sm" style="background:#0284c7; color:white;">✏ एडिट</a>
                <a href="/admin/delete_question/{{ q.id }}" class="btn-sm" style="background:#dc2626; color:white; margin-left:4px;" onclick="return confirm('हा प्रश्न डिलीट करायचा आहे का?');">🗑️ डिलीट</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 4. TEST LAUNCH & EDIT SUB-TAB -->
    {% elif active_tab == 'launch' %}
    <h3>🚀 नवीन टेस्ट लॉन्च करा व टेस्ट्स व्यवस्थापित करा</h3>
    <form method="POST" action="/admin/add_test" style="background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
        <input type="text" name="test_title" placeholder="नवीन टेस्टचे नाव लिहा" required>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;">
            <select name="test_type">
                <option value="Free">Free (मोफत)</option>
                <option value="Paid">Paid (सशुल्क)</option>
            </select>
            <input type="number" name="test_fee" placeholder="फी (₹)" value="0">
            <input type="number" name="duration_minutes" placeholder="वेळ (मिनिटे)" value="60">
        </div>
        <button type="submit" class="btn">🚀 नवीन टेस्ट सेव्ह करा</button>
    </form>

    <h4>सध्याच्या टेस्ट्स संपादन (Edit) व स्थिती:</h4>
    <table>
        <tr><th>ID</th><th>टेस्ट नाव</th><th>प्रकार</th><th>फी (₹)</th><th>वेळ (मि.)</th><th>स्थिती</th><th>कृती</th></tr>
        {% for t in tests %}
        <tr>
            <form method="POST" action="/admin/update_test/{{ t.id }}">
                <td>{{ t.id }}</td>
                <td><input type="text" name="test_title" value="{{ t.test_title }}" style="margin-bottom:0;" required></td>
                <td>
                    <select name="test_type" style="margin-bottom:0;">
                        <option value="Free" {% if t.test_type=='Free' %}selected{% endif %}>Free</option>
                        <option value="Paid" {% if t.test_type=='Paid' %}selected{% endif %}>Paid</option>
                    </select>
                </td>
                <td><input type="number" name="test_fee" value="{{ t.test_fee }}" style="width:75px; margin-bottom:0;"></td>
                <td><input type="number" name="duration_minutes" value="{{ t.duration_minutes }}" style="width:75px; margin-bottom:0;"></td>
                <td>
                    <select name="status" style="margin-bottom:0; font-weight:bold; color:{{ '#16a34a' if t.status=='Active' else '#dc2626' }};">
                        <option value="Active" {% if t.status=='Active' %}selected{% endif %}>Active</option>
                        <option value="Closed" {% if t.status=='Closed' %}selected{% endif %}>Closed</option>
                    </select>
                </td>
                <td style="white-space:nowrap;">
                    <button type="submit" class="btn-sm" style="background:#0284c7; color:white; border:none; padding:5px 9px; cursor:pointer;">💾 अपडेट</button>
                    <a href="/admin/print_test/{{ t.id }}" target="_blank" class="btn-sm" style="background:#059669; color:white; margin-left:3px;">🖨️ प्रिंट</a>
                    <a href="/admin/delete_test/{{ t.id }}" class="btn-sm" style="background:#dc2626; color:white; margin-left:3px;" onclick="return confirm('टेस्ट डिलीट करायची का?');">🗑</a>
                </td>
            </form>
        </tr>
        {% endfor %}
    </table>

    <!-- 5. LEADERBOARD SUB-TAB -->
    {% elif active_tab == 'leaderboard' %}
    <h3>🏆 टेस्ट वाईज राज्यस्तरीय लीडरबोर्ड (टॉप १०० विद्यार्थी)</h3>
    <table>
        <tr><th>रँक</th><th>विद्यार्थ्याचे नाव</th><th>जिल्हा</th><th>WhatsApp नंबर</th><th>टेस्टचे नाव</th><th>गुण</th></tr>
        {% for rank, l in top_leads %}
        <tr>
            <td><b>#{{ rank }}</b></td>
            <td>{{ l.student_name }}</td>
            <td>{{ l.district }}</td>
            <td><a href="https://wa.me/91{{ l.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ l.phone }}</a></td>
            <td>{{ l.test_name }}</td>
            <td><b style="color:#059669;">{{ l.score }} / {{ l.total_marks }}</b></td>
        </tr>
        {% endfor %}
    </table>

    <!-- 6. FEEDBACK SUB-TAB -->
    {% elif active_tab == 'feedback' %}
    <h3>💬 विद्यार्थ्यांचे आलेले अभिप्राय (Feedback Desk)</h3>
    <table>
        <tr><th>क्र.</th><th>दिनांक व वेळ</th><th>विद्यार्थ्याचे नाव</th><th>मोबाईल नंबर</th><th>अभिप्राय</th></tr>
        {% for f in feedbacks %}
        <tr>
            <td>{{ loop.index }}</td>
            <td>{{ f.created_at }}</td>
            <td><b>{{ f.student_name }}</b></td>
            <td><a href="https://wa.me/91{{ f.phone }}" target="_blank" style="color:green; font-weight:bold;">💬 {{ f.phone }}</a></td>
            <td style="font-size:13px; line-height:1.4;">{{ f.feedback_text }}</td>
        </tr>
        {% else %}
        <tr><td colspan="5" style="text-align:center; color:#64748b;">सध्या कोणताही अभिप्राय आलेला नाही.</td></tr>
        {% endfor %}
    </table>

    <!-- 7. RECRUITMENT PDF MANAGEMENT -->
    {% elif active_tab == 'notices' %}
    <h3>📢 भरती माहिती व पात्रता निकष PDF व्यवस्थापन</h3>
    <div style="background:#f8fafc; padding:20px; border-radius:8px; border:1px solid #cbd5e1; max-width:650px;">
        <form method="POST" action="/admin/update_pdf_docs" enctype="multipart/form-data">
            <h4 style="margin:0 0 8px; color:#065f46;">१. भरती अधिकृत माहिती PDF:</h4>
            {% if recruitment_pdf %}
            <p style="font-size:12px; margin-top:0;">सध्याची फाईल: <a href="{{ recruitment_pdf }}" target="_blank">PDF पहा</a></p>
            {% endif %}
            <label style="font-size:12px; font-weight:bold;">नवीन PDF अपलोड करा:</label>
            <input type="file" name="recruitment_pdf_file" accept=".pdf" style="margin-bottom:15px;">

            <hr style="margin:15px 0; border:0; border-top:1px solid #cbd5e1;">

            <h4 style="margin:0 0 8px; color:#065f46;">२. भरती पात्रता व निकष PDF:</h4>
            {% if eligibility_pdf %}
            <p style="font-size:12px; margin-top:0;">सध्याची फाईल: <a href="{{ eligibility_pdf }}" target="_blank">PDF पहा</a></p>
            {% endif %}
            <label style="font-size:12px; font-weight:bold;">नवीन PDF अपलोड करा:</label>
            <input type="file" name="eligibility_pdf_file" accept=".pdf" style="margin-bottom:15px;">

            <button type="submit" class="btn">💾 PDF डॉक्युमेंट्स सेव्ह करा</button>
        </form>
    </div>

    <!-- 8. SECURITY & SETTINGS -->
    {% elif active_tab == 'settings' %}
    <h3>🔐 ॲडमिन पासवर्ड व सोशल मीडिया सेटिंग्स</h3>
    <div style="background:#f8fafc; padding:20px; border-radius:6px; border:1px solid #cbd5e1; max-width:650px;">
        <form method="POST" action="/admin/update_password">
            <label style="font-weight:bold; font-size:12px;">नवा ॲडमिन पासवर्ड:</label>
            <div style="position:relative; width:100%; margin-bottom:15px;">
                <input type="password" name="new_password" id="new_password" placeholder="नवा पासवर्ड टाका" style="padding-right:45px; margin-bottom:0;">
                <button type="button" id="passEyeBtn" onclick="togglePassVis()" style="position:absolute; right:10px; top:8px; background:none; border:none; cursor:pointer; font-size:16px;">👁️</button>
            </div>
            <hr style="margin:15px 0; border:0; border-top:1px solid #cbd5e1;">
            <label style="font-weight:bold; font-size:12px;">Instagram लिंक:</label>
            <input type="text" name="insta_link" value="{{ insta_link }}">
            <label style="font-weight:bold; font-size:12px;">YouTube चॅनेल लिंक:</label>
            <input type="text" name="yt_link" value="{{ yt_link }}">
            <label style="font-weight:bold; font-size:12px;">यशवंतांचे फोटो लिंक:</label>
            <input type="text" name="toppers_link" value="{{ toppers_link }}">
            <button type="submit" class="btn" style="margin-top:10px;">💾 सर्व सेटिंग्स सेव्ह करा</button>
        </form>
    </div>
    {% endif %}
</div>
</body>
</html>'''

# ----------------- FLASK ROUTES -----------------

@app.route('/')
def home_tests_list():
    is_admin = session.get('admin_logged', False)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE status='Active' ORDER BY id ASC")
            tests = cur.fetchall()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_pdf'")
            r_row = cur.fetchone()
            recruitment_pdf = r_row['setting_value'] if r_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_pdf'")
            e_row = cur.fetchone()
            eligibility_pdf = e_row['setting_value'] if e_row else ''
    return render_template_string(HOME_TEMPLATE, tests=tests, recruitment_pdf=recruitment_pdf, eligibility_pdf=eligibility_pdf, is_admin=is_admin)

@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template_string(TERMS_TEMPLATE)

@app.route('/api/check_phone_usage')
def check_phone_usage():
    test_id = request.args.get('test_id', type=int)
    phone = request.args.get('phone', '').strip()
    if not test_id or len(phone) != 10:
        return jsonify({'used': False})
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM special_unlimited_attempts WHERE phone=%s LIMIT 1", (phone,))
            if cur.fetchone():
                return jsonify({'used': False})

            cur.execute("SELECT id FROM mock_test_leads WHERE test_id=%s AND phone=%s LIMIT 1", (test_id, phone))
            row = cur.fetchone()
            return jsonify({'used': bool(row)})

@app.route('/api/check_free_pass')
def check_free_pass():
    phone = request.args.get('phone', '').strip()
    if len(phone) != 10:
        return jsonify({'is_free': False})
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM special_free_pass WHERE phone=%s LIMIT 1", (phone,))
            row = cur.fetchone()
            return jsonify({'is_free': bool(row)})

@app.route('/take_test/<int:test_id>')
def take_test(test_id):
    token = request.args.get('token', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='qr_code_url'")
            qr_row = cur.fetchone()
            qr_url = qr_row['setting_value'] if qr_row else ''
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='upi_mobile'")
            upi_row = cur.fetchone()
            upi_mobile = upi_row['setting_value'] if upi_row else '9921111960'

    if not test or test['status'] != 'Active': return "Test not found or currently closed", 404

    # मोफत टेस्ट थेट ओपन होईल (कोणतीही अडचण किंवा लॉक नसेल)
    if test['test_type'] == 'Free':
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                questions = cur.fetchall()
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions, error_msg=None)

    # सशुल्क टेस्टसाठी टोकन पडताळणी
    if token:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM mock_test_leads WHERE test_id=%s AND access_token=%s AND payment_status='Approved'", (test_id, token))
                lead = cur.fetchone()
        if lead and lead['token_expires_at']:
            expires_at = datetime.strptime(lead['token_expires_at'], "%Y-%m-%d %H:%M:%S")
            if datetime.now() <= expires_at:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
                        questions = cur.fetchall()
                return render_template_string(EXAM_TEMPLATE, test=test, questions=questions, error_msg=None)
            else:
                return "<h3 style='color:red; text-align:center;'>❌ या सशुल्क टेस्टची २४ तासांची मुदत संपलेली आहे!</h3>", 403

    return render_template_string(ACCESS_CHECK_TEMPLATE, test=test, qr_url=qr_url, upi_mobile=upi_mobile)

@app.route('/request_paid_test/<int:test_id>', methods=['POST'])
def request_paid_test(test_id):
    name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()
    t_date = date.today().strftime("%Y-%m-%d")

    if not re.match(r'^[6-9]\d{9}$', phone):
        return "<h3 style='color:red; text-align:center;'>⚠️ आपण चुकीचा मोबाईल नंबर टाकत आहात!</h3><div style='text-align:center;'><a href='javascript:history.back()'>मागे जा व दुरुस्त करा</a></div>", 400

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()

    if not test: return "Test not found", 404

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM special_free_pass WHERE phone=%s LIMIT 1", (phone,))
            is_free_user = cur.fetchone()

    if is_free_user:
        token = secrets.token_hex(8)
        expires = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, score, total_marks, test_name, access_token, token_expires_at)
                    VALUES (%s, %s, %s, %s, %s, 'Approved', 0, 0, %s, %s, %s)
                """, (test_id, t_date, name, district, phone, test['test_title'], token, expires))
                conn.commit()
        return redirect(f"/take_test/{test_id}?token={token}")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE test_id=%s AND phone=%s", (test_id, phone))
            existing = cur.fetchone()
            if not existing:
                cur.execute("""
                    INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, payment_status, score, total_marks, test_name)
                    VALUES (%s, %s, %s, %s, %s, 'Pending', 0, 0, %s)
                """, (test_id, t_date, name, district, phone, test['test_title']))
                conn.commit()

    return render_template_string('''<!DOCTYPE html><html lang="mr"><head><meta charset="UTF-8"><title>पेमेंट प्रलंबित</title></head>
    <body style="font-family:sans-serif; text-align:center; padding:50px; background:#f0fdf4;">
        <div style="max-width:450px; margin:auto; background:white; padding:30px; border-radius:10px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
            <h3 style="color:#d97706;">⏳ पडताळणी प्रलंबित आहे!</h3>
            <p style="font-size:14px; color:#475569;">स्क्रीनशॉट पडताळणीनंतर ॲडमिन अप्रूव करतील व २४ तासांची ॲक्सेस लिंक तुमच्या WhatsApp वर पाठवली जाईल.</p>
            <a href="/" style="background:#059669; color:white; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:bold; display:inline-block; margin-top:15px;">🏠 मुख्य पानावर जा</a>
        </div>
    </body></html>''')

@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    student_name = request.form.get('student_name', '').strip()
    district = request.form.get('district', '').strip()
    phone = request.form.get('phone', '').strip()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()

    if not test: return "Test not found", 404

    # मोबाईल नंबर व्हॅलिडेशन
    if not re.match(r'^[6-9]\d{9}$', phone):
        err_msg = "⚠️ आपण चुकीचा मोबाईल नंबर टाकत आहात!"
        return render_template_string(EXAM_TEMPLATE, test=test, questions=questions, error_msg=err_msg)

    score = 0
    total = len(questions)
    user_answers = {}
    evaluated_questions = []

    for q in questions:
        ans = request.form.get(f"q_{q['id']}", "")
        user_answers[str(q['id'])] = ans
        is_corr = (ans == q['correct'])
        if is_corr:
            score += 1
        evaluated_questions.append({
            'q_text': q['question'],
            'opt_a': q['opt_a'],
            'opt_b': q['opt_b'],
            'opt_c': q['opt_c'],
            'opt_d': q['opt_d'],
            'user_ans': ans if ans else 'सोडवले नाही',
            'correct_ans': q['correct'],
            'is_correct': is_corr,
            'explanation': q['explanation']
        })

    t_date = date.today().strftime("%Y-%m-%d")
    ans_json_str = json.dumps(user_answers)
    pay_status = 'Approved'

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mock_test_leads (test_id, test_date, student_name, district, phone, whatsapp_verified, payment_status, score, total_marks, test_name, answers_json)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s) RETURNING id
            """, (test_id, t_date, student_name, district, phone, pay_status, score, total, test['test_title'], ans_json_str))
            new_id = cur.fetchone()['id']
            conn.commit()

            cur.execute("SELECT COUNT(*) as higher FROM mock_test_leads WHERE test_id=%s AND score > %s", (test_id, score))
            higher_count = cur.fetchone()['higher']
            state_rank = higher_count + 1

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            toppers_link = cur.fetchone()['setting_value']

    main_portal_url = request.host_url.rstrip('/')
    share_msg = f"राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका\n\nमी आत्ताच '{test['test_title']}' टेस्ट सोडवली आणि मला {score}/{total} गुण मिळाले (रँक #{state_rank}). आपणही ही मोफत टेस्ट सोडवून आपला अभ्यास तपासा:\n👉 {main_portal_url}"
    share_whatsapp_encoded = urllib.parse.quote(share_msg)

    # टेस्ट सबमिट झाल्यावर थेट गुण आणि बरोबर/चूक प्रश्न स्क्रीनवर दाखवणे
    return render_template_string(
        RESULT_SUMMARY_TEMPLATE,
        lead={'id': new_id, 'student_name': student_name, 'district': district, 'phone': phone, 'test_name': test['test_title'], 'score': score, 'total_marks': total},
        state_rank=state_rank,
        evaluated_questions=evaluated_questions,
        share_whatsapp_encoded=share_whatsapp_encoded,
        insta_link=insta_link,
        yt_link=yt_link,
        toppers_link=toppers_link
    )

@app.route('/detailed_answers/<int:lead_id>')
def detailed_answers(lead_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mock_test_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead: return "Result not found", 404

            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (lead['test_id'],))
            questions = cur.fetchall()

            cur.execute("SELECT COUNT(*) as cnt FROM student_feedbacks WHERE lead_id=%s", (lead_id,))
            feedback_done = cur.fetchone()['cnt'] > 0

    user_ans_dict = json.loads(lead['answers_json'] or '{}')
    evaluated_questions = []

    for q in questions:
        u_ans = user_ans_dict.get(str(q['id']), 'सोडवले नाही')
        evaluated_questions.append({
            'q_text': q['question'],
            'opt_a': q['opt_a'],
            'opt_b': q['opt_b'],
            'opt_c': q['opt_c'],
            'opt_d': q['opt_d'],
            'user_ans': u_ans,
            'correct_ans': q['correct'],
            'is_correct': (u_ans == q['correct']),
            'explanation': q['explanation']
        })

    main_portal_url = request.host_url.rstrip('/')
    share_msg = f"राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका\n\nसराव करण्यासाठी आत्ताच खालील लिंक ओपन करा:\n👉 {main_portal_url}"
    share_whatsapp_encoded = urllib.parse.quote(share_msg)

    return render_template_string(
        DETAILED_KEY_TEMPLATE, 
        lead=lead, 
        evaluated_questions=evaluated_questions, 
        feedback_done=feedback_done,
        share_whatsapp_encoded=share_whatsapp_encoded
    )

@app.route('/submit_feedback/<int:lead_id>', methods=['POST'])
def submit_feedback(lead_id):
    fb_text = request.form.get('feedback_text', '').strip()
    if fb_text:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT student_name, phone FROM mock_test_leads WHERE id=%s", (lead_id,))
                lead = cur.fetchone()
                if lead:
                    c_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                    cur.execute("""
                        INSERT INTO student_feedbacks (lead_id, student_name, phone, feedback_text, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (lead_id, lead['student_name'], lead['phone'], fb_text, c_date))
                    conn.commit()
    return redirect(f'/detailed_answers/{lead_id}')

# ----------------- ADMIN ROUTES -----------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('admin_pass')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='admin_pass'")
                row = cur.fetchone()
                db_pass = row['setting_value'] if row else 'shreeguru2026'

        if password == db_pass:
            session['admin_logged'] = True
            return redirect('/admin/dashboard')
        else:
            error = "चुकीचा पासवर्ड! कृपया पुन्हा प्रयत्न करा."
            
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged', None)
    return redirect('/admin/login')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged'): return redirect('/admin/login')

    active_tab = request.args.get('tab', 'leads')
    filter_test_id = request.args.get('filter_test_id', '')
    lead_dist = request.args.get('lead_dist', '')
    lead_test_id = request.args.get('lead_test_id', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            query = "SELECT * FROM mock_test_leads WHERE 1=1"
            params = []
            if lead_dist:
                query += " AND district = %s"
                params.append(lead_dist)
            if lead_test_id:
                query += " AND test_id = %s"
                params.append(lead_test_id)
            query += " ORDER BY id DESC"
            cur.execute(query, tuple(params))
            leads = cur.fetchall()

            cur.execute("SELECT DISTINCT district FROM mock_test_leads WHERE district != ''")
            all_districts = [r['district'] for r in cur.fetchall()]

            cur.execute("SELECT * FROM test_papers ORDER BY id ASC")
            tests = cur.fetchall()

            if filter_test_id:
                cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id DESC", (filter_test_id,))
            else:
                cur.execute("SELECT * FROM questions ORDER BY id DESC")
            all_questions = cur.fetchall()

            cur.execute("SELECT * FROM mock_test_leads WHERE payment_status != 'Not Required' ORDER BY id DESC")
            payments = cur.fetchall()

            cur.execute("SELECT * FROM mock_test_leads ORDER BY score DESC, id ASC LIMIT 100")
            all_leads_sorted = cur.fetchall()

            cur.execute("SELECT * FROM student_feedbacks ORDER BY id DESC")
            feedbacks = cur.fetchall()

            cur.execute("SELECT * FROM special_unlimited_attempts ORDER BY id DESC")
            unlimited_list = cur.fetchall()

            cur.execute("SELECT * FROM special_free_pass ORDER BY id DESC")
            free_pass_list = cur.fetchall()

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='qr_code_url'")
            r = cur.fetchone()
            qr_url = r['setting_value'] if r else ''

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='upi_mobile'")
            r = cur.fetchone()
            upi_mobile = r['setting_value'] if r else '9921111960'

            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='insta_link'")
            insta_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='yt_link'")
            yt_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='toppers_link'")
            toppers_link = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='recruitment_pdf'")
            recruitment_pdf = cur.fetchone()['setting_value']
            cur.execute("SELECT setting_value FROM academy_settings WHERE setting_key='eligibility_pdf'")
            eligibility_pdf = cur.fetchone()['setting_value']

    top_leads = [(idx, l) for idx, l in enumerate(all_leads_sorted, start=1)]

    return render_template_string(
        ADMIN_TEMPLATE,
        active_tab=active_tab,
        leads=leads,
        tests=tests,
        all_questions=all_questions,
        payments=payments,
        top_leads=top_leads,
        feedbacks=feedbacks,
        unlimited_list=unlimited_list,
        free_pass_list=free_pass_list,
        all_districts=all_districts,
        lead_dist=lead_dist,
        lead_test_id=lead_test_id,
        filter_test_id=filter_test_id,
        qr_url=qr_url,
        upi_mobile=upi_mobile,
        insta_link=insta_link,
        yt_link=yt_link,
        toppers_link=toppers_link,
        recruitment_pdf=recruitment_pdf,
        eligibility_pdf=eligibility_pdf
    )

@app.route('/admin/add_special_unlimited', methods=['POST'])
def add_special_unlimited():
    if not session.get('admin_logged'): return redirect('/admin/login')
    phone = request.form.get('phone', '').strip()
    name = request.form.get('student_name', '').strip()
    note = request.form.get('note', '').strip()
    added_on = datetime.now().strftime("%Y-%m-%d %H:%M")
    if re.match(r'^[6-9]\d{9}$', phone):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO special_unlimited_attempts (phone, student_name, note, added_on)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (phone) DO UPDATE SET student_name=EXCLUDED.student_name, note=EXCLUDED.note
                """, (phone, name, note, added_on))
                conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/delete_special_unlimited/<int:uid>')
def delete_special_unlimited(uid):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM special_unlimited_attempts WHERE id=%s", (uid,))
            conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/add_special_free_pass', methods=['POST'])
def add_special_free_pass():
    if not session.get('admin_logged'): return redirect('/admin/login')
    phone = request.form.get('phone', '').strip()
    name = request.form.get('student_name', '').strip()
    note = request.form.get('note', '').strip()
    added_on = datetime.now().strftime("%Y-%m-%d %H:%M")
    if re.match(r'^[6-9]\d{9}$', phone):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO special_free_pass (phone, student_name, note, added_on)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (phone) DO UPDATE SET student_name=EXCLUDED.student_name, note=EXCLUDED.note
                """, (phone, name, note, added_on))
                conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/delete_special_free_pass/<int:fid>')
def delete_special_free_pass(fid):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM special_free_pass WHERE id=%s", (fid,))
            conn.commit()
    return redirect('/admin/dashboard?tab=special')

@app.route('/admin/update_payment_settings', methods=['POST'])
def admin_update_payment_settings():
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_mobile = request.form.get('upi_mobile', '').strip()
    qr_url_input = request.form.get('qr_url', '').strip()
    qr_file = request.files.get('qr_file')
    
    final_qr_url = qr_url_input
    if qr_file and qr_file.filename != '':
        fname = secure_filename(f"qr_{int(datetime.now().timestamp())}_{qr_file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        qr_file.save(save_path)
        final_qr_url = f"/static/uploads/{fname}"

    with get_db() as conn:
        with conn.cursor() as cur:
            if final_qr_url:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='qr_code_url'", (final_qr_url,))
            if new_mobile:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='upi_mobile'", (new_mobile,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/add_question', methods=['POST'])
def admin_add_question():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    question = request.form.get('question', '').strip()
    oa = request.form.get('opt_a', '').strip()
    ob = request.form.get('opt_b', '').strip()
    oc = request.form.get('opt_c', '').strip()
    od = request.form.get('opt_d', '').strip()
    correct = request.form.get('correct', 'A').strip().upper()
    explanation = request.form.get('explanation', '').strip()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (test_id, question, oa, ob, oc, od, correct, explanation))
            conn.commit()
    return redirect(f'/admin/dashboard?tab=questions&filter_test_id={test_id}')

@app.route('/admin/edit_question/<int:q_id>', methods=['GET', 'POST'])
def admin_edit_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    
    with get_db() as conn:
        with conn.cursor() as cur:
            if request.method == 'POST':
                q_text = request.form.get('question', '').strip()
                oa = request.form.get('opt_a', '').strip()
                ob = request.form.get('opt_b', '').strip()
                oc = request.form.get('opt_c', '').strip()
                od = request.form.get('opt_d', '').strip()
                correct = request.form.get('correct', 'A').strip().upper()
                explanation = request.form.get('explanation', '').strip()

                cur.execute("""
                    UPDATE questions
                    SET question=%s, opt_a=%s, opt_b=%s, opt_c=%s, opt_d=%s, correct=%s, explanation=%s
                    WHERE id=%s
                """, (q_text, oa, ob, oc, od, correct, explanation, q_id))
                conn.commit()

                cur.execute("SELECT test_id FROM questions WHERE id=%s", (q_id,))
                q_row = cur.fetchone()
                test_id = q_row['test_id'] if q_row else ''
                return redirect(f'/admin/dashboard?tab=questions&filter_test_id={test_id}')

            cur.execute("SELECT * FROM questions WHERE id=%s", (q_id,))
            question = cur.fetchone()

    if not question: return "प्रश्न सापडला नाही!", 404
    return render_template_string(EDIT_QUESTION_TEMPLATE, q=question)

@app.route('/admin/bulk_questions', methods=['POST'])
def admin_bulk_questions():
    if not session.get('admin_logged'): return redirect('/admin/login')
    test_id = request.form.get('test_id')
    bulk_data = request.form.get('bulk_questions_text', '').strip()

    lines = [l.strip() for l in bulk_data.split('\n') if l.strip()]
    with get_db() as conn:
        with conn.cursor() as cur:
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 6:
                    q = parts[0]
                    oa, ob, oc, od = parts[1], parts[2], parts[3], parts[4]
                    corr = parts[5].upper()
                    exp = parts[6] if len(parts) > 6 else ''
                    cur.execute("""
                        INSERT INTO questions (test_id, question, opt_a, opt_b, opt_c, opt_d, correct, explanation)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (test_id, q, oa, ob, oc, od, corr, exp))
            conn.commit()

    return redirect(f'/admin/dashboard?tab=questions&filter_test_id={test_id}')

@app.route('/admin/approve_payment/<int:lead_id>', methods=['POST'])
def admin_approve_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    token = secrets.token_hex(8)
    expires = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE mock_test_leads 
                SET payment_status='Approved', access_token=%s, token_expires_at=%s 
                WHERE id=%s RETURNING test_id, phone
            """, (token, expires, lead_id))
            row = cur.fetchone()
            conn.commit()

    test_link = request.host_url.rstrip('/') + f"/take_test/{row['test_id']}?token={token}"
    print(f"--- 24HR TEST LINK --- To: {row['phone']} | Link: {test_link}")
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/update_test/<int:test_id>', methods=['POST'])
def admin_update_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title', '').strip()
    ttype = request.form.get('test_type', 'Free')
    fee = float(request.form.get('test_fee', 0))
    duration = int(request.form.get('duration_minutes', 60))
    status = request.form.get('status', 'Active')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE test_papers 
                SET test_title=%s, test_type=%s, test_fee=%s, duration_minutes=%s, status=%s 
                WHERE id=%s
            """, (title, ttype, fee, duration, status, test_id))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/update_pdf_docs', methods=['POST'])
def admin_update_pdf_docs():
    if not session.get('admin_logged'): return redirect('/admin/login')
    rec_file = request.files.get('recruitment_pdf_file')
    elg_file = request.files.get('eligibility_pdf_file')

    with get_db() as conn:
        with conn.cursor() as cur:
            if rec_file and rec_file.filename != '':
                fname = secure_filename(f"recruitment_{int(datetime.now().timestamp())}_{rec_file.filename}")
                rec_file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='recruitment_pdf'", (f"/static/uploads/{fname}",))
            
            if elg_file and elg_file.filename != '':
                fname = secure_filename(f"eligibility_{int(datetime.now().timestamp())}_{elg_file.filename}")
                elg_file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='eligibility_pdf'", (f"/static/uploads/{fname}",))
            conn.commit()

    return redirect('/admin/dashboard?tab=notices')

@app.route('/admin/update_password', methods=['POST'])
def admin_update_password():
    if not session.get('admin_logged'): return redirect('/admin/login')
    new_pass = request.form.get('new_password')
    insta = request.form.get('insta_link', '')
    yt = request.form.get('yt_link', '')
    top = request.form.get('toppers_link', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            if new_pass:
                cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='admin_pass'", (new_pass,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='insta_link'", (insta,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='yt_link'", (yt,))
            cur.execute("UPDATE academy_settings SET setting_value=%s WHERE setting_key='toppers_link'", (top,))
            conn.commit()
    return redirect('/admin/dashboard?tab=settings')

@app.route('/admin/delete_lead/<int:lead_id>')
def admin_delete_lead(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mock_test_leads WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=leads')

@app.route('/admin/delete_question/<int:q_id>')
def admin_delete_question(q_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM questions WHERE id=%s", (q_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=questions')

@app.route('/admin/add_test', methods=['POST'])
def admin_add_test():
    if not session.get('admin_logged'): return redirect('/admin/login')
    title = request.form.get('test_title')
    ttype = request.form.get('test_type')
    fee = float(request.form.get('test_fee', 0))
    duration = int(request.form.get('duration_minutes', 60))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO test_papers (test_title, test_type, test_fee, duration_minutes, status) VALUES (%s, %s, %s, %s, 'Active')", (title, ttype, fee, duration))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM questions WHERE test_id=%s", (test_id,))
            cur.execute("DELETE FROM test_papers WHERE id=%s", (test_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=launch')

@app.route('/admin/delete_payment/<int:lead_id>')
def admin_delete_payment(lead_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mock_test_leads WHERE id=%s", (lead_id,))
            conn.commit()
    return redirect('/admin/dashboard?tab=payments')

@app.route('/admin/print_test/<int:test_id>')
def admin_print_test(test_id):
    if not session.get('admin_logged'): return redirect('/admin/login')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test_papers WHERE id=%s", (test_id,))
            test = cur.fetchone()
            cur.execute("SELECT * FROM questions WHERE test_id=%s ORDER BY id ASC", (test_id,))
            questions = cur.fetchall()
            
    html = f'''<!DOCTYPE html><html lang="mr"><head><meta charset="UTF-8"><title>{test['test_title']} - Print</title></head>
    <body style="font-family:sans-serif; padding:30px; color:#000;">
        <h2 style="text-align:center;">राज्यस्तरीय पोलीस भरती सराव प्रश्नपत्रिका</h2>
        <h3 style="text-align:center;">{test['test_title']}</h3>
        <hr>
        <ol>{ "".join([f"<li style='margin-bottom:15px;'><b>{q['question']}</b><br>A) {q['opt_a']}&nbsp;&nbsp;&nbsp;B) {q['opt_b']}&nbsp;&nbsp;&nbsp;C) {q['opt_c']}&nbsp;&nbsp;&nbsp;D) {q['opt_d']}<br><small style='color:green;'>अचूक उत्तर: {q['correct']} | स्पष्टीकरण: {q['explanation']}</small></li>" for q in questions]) }</ol>
        <script>window.print();</script>
    </body></html>'''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
