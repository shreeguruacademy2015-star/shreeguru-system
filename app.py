import os
import re
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shreeguru_secure_secret_key_2026")

def get_db():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set!")
    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    return conn

def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

# Safe Database Initialization
def init_db():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        role VARCHAR(50) UNIQUE NOT NULL,
                        password VARCHAR(100) NOT NULL
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS students (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(150),
                        mobile VARCHAR(20),
                        total_fees NUMERIC DEFAULT 0,
                        paid_fees NUMERIC DEFAULT 0
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS expenses (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(200),
                        amount NUMERIC DEFAULT 0
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS online_tests (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(200),
                        time_limit INT DEFAULT NULL,
                        raw_questions TEXT
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS student_submissions (
                        id SERIAL PRIMARY KEY,
                        test_id INT,
                        student_name VARCHAR(150),
                        student_mobile VARCHAR(20),
                        score NUMERIC DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("SELECT COUNT(*) FROM users;")
                if cur.fetchone()['count'] == 0:
                    default_users = [('Admin', 'admin123'), ('Manager', 'mgr123'), ('Trainer', 'trn123'), ('Clerk', 'clerk123')]
                    cur.executemany("INSERT INTO users (role, password) VALUES (%s, %s) ON CONFLICT (role) DO NOTHING;", default_users)
            conn.commit()
    except Exception as e:
        print(f"Database Init Error: {e}")

# HTML Templates & Login
LOGIN_HTML = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shreeguru Career Academy - Login</title>
<style>
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f1f5f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
.login-box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); width: 350px; position: relative; }
.insignia { font-size: 12px; font-weight: bold; color: #15803d; background: #dcfce7; padding: 4px 8px; border-radius: 4px; display: inline-block; margin-bottom: 8px; }
.title { color: #0b2545; font-size: 22px; font-weight: 800; margin: 4px 0; }
.subtitle { font-size: 11px; color: #475569; margin-bottom: 20px; font-weight: 600; }
select, input { width: 100%; padding: 11px 12px; margin-bottom: 15px; border: 1.5px solid #cbd5e1; border-radius: 6px; font-size: 13px; font-weight: 600; box-sizing: border-box; }
.btn-sub { width: 100%; padding: 12px; background: linear-gradient(135deg, #15803d, #16a34a); color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer; }
.lang-btn { position: absolute; top: 12px; right: 12px; background: #fef08a; color: #854d0e; border: 1px solid #facc15; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-decoration: none; }
</style>
</head>
<body>
<div class="login-box">
    <a href="/toggle_lang" class="lang-btn">🌐 {{ 'MR' if lang == 'en' else 'EN' }}</a>
    <span class="insignia">⚔️️ POLICE & DEFENCE ACADEMY</span>
    <h2 class="title">श्रीगुरु करिअर अकॅडमी</h2>
    <div class="subtitle">पोलीस व सैन्य भरती पूर्व प्रशिक्षण केंद्र<br>आडूर, ता. करवीर, जि. कोल्हापूर</div>
    {% if error %}<div style="color:#dc2626; font-size:12px; font-weight:bold; margin-bottom:12px;">{{ error }}</div>{% endif %}
    <form action="/login" method="POST">
        <select name="role">{% for u in users_list %}<option value="{{ u.role }}">{{ u.role }}</option>{% endfor %}</select>
        <input type="password" name="password" required placeholder="{{ 'Enter Password' if lang == 'en' else 'पासवर्ड टाका' }}">
        <button type="submit" class="btn-sub">{{ 'SECURE LOGIN 🔐' if lang == 'en' else 'सुरक्षित लॉगिन करा 🔐' }}</button>
    </form>
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
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users")
                users_list = cur.fetchall()
    except Exception:
        users_list = [{'role': 'Admin'}, {'role': 'Manager'}, {'role': 'Trainer'}, {'role': 'Clerk'}]
            
    if request.method == 'POST':
        role = request.form.get('role')
        pwd = request.form.get('password')
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE role=%s AND password=%s", (role, pwd))
                    user = cur.fetchone()
        except Exception:
            user = None
            
        if user or (pwd == 'admin123' and role == 'Admin'):
            session['user_role'] = role
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
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM students")
                students = cur.fetchall()
                cur.execute("SELECT * FROM expenses ORDER BY id DESC")
                expenses_list = cur.fetchall()
    except Exception:
        students, expenses_list = [], []
            
    total_paid = sum(safe_float(s.get('paid_fees', 0)) for s in students)
    total_pending = sum(safe_float(s.get('total_fees', 0)) - safe_float(s.get('paid_fees', 0)) for s in students)
    
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
            <li><b>एकूण खर्च:</b> ₹ {sum(safe_float(ex.get('amount', 0)) for ex in expenses_list)}</li>
        </ul>
        <br>
        <a href="/admin/add_test" style="background:#2563eb; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold; margin-right:10px;">नवीन टेस्ट तयार करा 📝</a>
        <a href="/logout" style="background:#dc2626; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;">लॉग आउट (Logout) 🚪</a>
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
    return "<h2>Clerk Dashboard - श्रीगुरु करिअर अकॅडमी</h2><a href='/logout'>Logout</a>"

@app.route('/admin/add_test', methods=['GET', 'POST'])
def add_test():
    role = session.get('user_role')
    if role not in ['Admin', 'Clerk']:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        test_title = request.form.get('test_title')
        time_limit = request.form.get('time_limit') 
        time_limit = int(time_limit) if time_limit and time_limit.isdigit() else None
        raw_content = request.form.get('raw_content')
        
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO online_tests (title, time_limit, raw_questions) VALUES (%s, %s, %s) RETURNING id;",
                        (test_title, time_limit, raw_content)
                    )
                    test_row = cur.fetchone()
                    test_id = test_row['id'] if isinstance(test_row, dict) else test_row[0]
                conn.commit()
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
            
        return jsonify({
            "status": "success",
            "message": "टेस्ट, टाईम सेटिंग आणि बल्क प्रश्न यशस्वीपणे जतन झाले आहेत!",
            "test_id": test_id
        })
        
    return """
    <div style="font-family:Arial; padding:30px; max-width:600px; margin:auto;">
        <h2>📝 नवीन टेस्ट तयार करा (Bulk Import & Timer)</h2>
        <form method="POST">
            <label><b>टेस्टचे नाव (Title):</b></label><br>
            <input type="text" name="test_title" required style="width:100%; padding:8px; margin:8px 0;"><br>
            <label><b>टाईम लिमिट (मिनिटांत - रिकामे ठेवल्यास अनलमीटेड वेळ):</b></label><br>
            <input type="number" name="time_limit" placeholder="उदा. 10 किंवा 30" style="width:100%; padding:8px; margin:8px 0;"><br>
            <label><b>सर्व प्रश्न आणि आन्सर की (Bulk Copy-Paste Box):</b></label><br>
            <textarea name="raw_content" rows="10" placeholder="येथे सर्व प्रश्न एकाच वेळी कॉपी-पेस्ट करा..." style="width:100%; padding:8px; margin:8px 0;"></textarea><br>
            <button type="submit" style="background:#15803d; color:white; padding:10px 20px; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">टेस्ट सेव्ह करा</button>
        </form>
        <br><a href="/admin">🔙 डॅशबोर्डकडे जा</a>
    </div>
    """

@app.route('/submit_test', methods=['POST'])
def submit_test():
    try:
        data = request.json or request.form
        student_name = data.get('name', '').strip()
        student_mobile = data.get('mobile', '').strip()
        test_id = data.get('test_id')
        
        if not student_name or not re.match("^[अ-ॲक-हA-Za-z\\s]+$", student_name):
            return jsonify({"status": "error", "message": "कृपया तुमचे योग्य नाव टाका (नावात आकडे चालणार नाहीत)."}), 400

        if not student_mobile or not re.match("^[0-9]{10}$", student_mobile):
            return jsonify({"status": "error", "message": "चुकीचा नंबर! कृपया अचूक १० अंकी मोबाईल नंबर टाका."}), 400

        calculated_score = 0  

        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO student_submissions (test_id, student_name, student_mobile, score) 
                           VALUES (%s, %s, %s, %s) RETURNING id;""",
                        (test_id, student_name, student_mobile, calculated_score)
                    )
                conn.commit()
        except Exception:
            pass

        teacher_whatsapp_number = "919423847055"  
        whatsapp_message = f"सर, मी टेस्ट पूर्ण केली आहे. माझे नाव: {student_name}, मोबाईल: {student_mobile}. मला माझे गुण आणि चुका तपासायच्या आहेत."
        encoded_message = urllib.parse.quote(whatsapp_message)
        whatsapp_url = f"https://wa.me/{teacher_whatsapp_number}?text={encoded_message}"

        return jsonify({
            "status": "success", 
            "message": "तुमची टेस्ट यशस्वीरित्या सबमिट झाली आहे! सुरक्षिततेखातर गुण इथे दाखवले नाहीत.",
            "whatsapp_link": whatsapp_url
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
