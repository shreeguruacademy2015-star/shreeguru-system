import os
from datetime import date 
from flask import Flask, redirect, render_template_string, request, session, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "shreeguru_complete_fresh_master_2026"

# Supabase PostgreSQL Database Connection URL (password madhla @ = %40)
DATABASE_URL = "postgresql://postgres:Shreeguru%40123@db.pcwdribwbcuoxkqhozmu.supabase.co:5432/postgres"

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == "": return default
        return float(val)
    except: return default

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            # Users & Logins
            cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, role TEXT UNIQUE NOT NULL, password TEXT NOT NULL)")
            cur.execute("INSERT INTO users (role, password) VALUES ('Admin', 'admin123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Manager', 'manager123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Clerk', 'clerk123') ON CONFLICT (role) DO NOTHING")
            cur.execute("INSERT INTO users (role, password) VALUES ('Trainer', 'trainer123') ON CONFLICT (role) DO NOTHING")

            # Online Tests & Leads
            cur.execute("""CREATE TABLE IF NOT EXISTS online_tests (
                id SERIAL PRIMARY KEY, title TEXT NOT NULL, time_limit INTEGER DEFAULT NULL,
                manual_questions TEXT, raw_questions TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            cur.execute("""CREATE TABLE IF NOT EXISTS student_submissions (
                id SERIAL PRIMARY KEY, test_id INTEGER, student_name TEXT, student_mobile TEXT,
                score REAL DEFAULT 0, total_marks REAL DEFAULT 0, details TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")

            # Core Academy Tables
            cur.execute('''CREATE TABLE IF NOT EXISTS books (id SERIAL PRIMARY KEY, title TEXT NOT NULL, author TEXT, category TEXT, total_copies INTEGER DEFAULT 1, available_copies INTEGER DEFAULT 1)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS book_issues (id SERIAL PRIMARY KEY, book_id INTEGER, student_id INTEGER, student_name TEXT, issue_date TEXT, return_date TEXT, status TEXT DEFAULT 'Issued')''')
            cur.execute('''CREATE TABLE IF NOT EXISTS study_lab_seats (id SERIAL PRIMARY KEY, seat_number TEXT NOT NULL, shift TEXT NOT NULL, student_id INTEGER, student_name TEXT, status TEXT DEFAULT 'Available')''')
            cur.execute("""CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, dob TEXT, gender TEXT, category TEXT, course TEXT NOT NULL, 
                phone TEXT NOT NULL, parent_phone TEXT, address TEXT, total_fees REAL DEFAULT 0, paid_fees REAL DEFAULT 0, admission_date TEXT NOT NULL
            )""")
            cur.execute("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, exp_date TEXT NOT NULL, category TEXT NOT NULL, description TEXT, amount REAL NOT NULL, logged_by TEXT DEFAULT 'Clerk')")
            cur.execute("CREATE TABLE IF NOT EXISTS admission_inquiries (id SERIAL PRIMARY KEY, inquiry_date TEXT NOT NULL, student_name TEXT NOT NULL, district TEXT NOT NULL, phone TEXT NOT NULL, course TEXT NOT NULL, call_status TEXT DEFAULT 'नवीन चौकशी')")
            conn.commit()

# --- LOGIN ROUTE ---
LOGIN_HTML = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>SHREEGURU ACADEMY LOGIN</title>
<style>
body { background: #0f172a; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin:0; }
.box { background: white; padding: 30px; border-radius: 8px; width: 350px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
select, input, button { width: 100%; padding: 10px; margin-bottom: 12px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
button { background: #16a34a; color: white; border: none; font-weight: bold; cursor: pointer; }
</style></head>
<body>
<div class="box">
    <h2 style="color:#0b2545; margin-top:0;">श्रीगुरु करिअर अकॅडमी</h2>
    <p style="font-size:12px; color:#555;">पोलीस व सैन्य भरती पूर्व प्रशिक्षण केंद्र, आडूर</p>
    {% if error %}<p style="color:red; font-size:12px;">{{ error }}</p>{% endif %}
    <form method="POST">
        <select name="role">
            <option value="Admin">Admin</option>
            <option value="Manager">Manager</option>
            <option value="Clerk">Clerk</option>
            <option value="Trainer">Trainer</option>
        </select>
        <input type="password" name="password" placeholder="पासवर्ड टाका" required>
        <button type="submit">सुरक्षित लॉगिन करा 🔐</button>
    </form>
</div></body></html>'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        role = request.form.get('role')
        pwd = request.form.get('password')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE role=%s AND password=%s", (role, pwd))
                user = cur.fetchone()
        if user:
            session['user_role'] = role
            if role == 'Manager': return redirect('/manager')
            elif role == 'Trainer': return redirect('/trainer')
            elif role == 'Clerk': return redirect('/clerk')
            else: return redirect('/admin')
        else:
            error = "चुकीचा पासवर्ड! पुन्हा प्रयत्न करा."
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
def root():
    role = session.get('user_role')
    if not role: return redirect('/login')
    if role == 'Manager': return redirect('/manager')
    elif role == 'Trainer': return redirect('/trainer')
    elif role == 'Clerk': return redirect('/clerk')
    else: return redirect('/admin')

# --- ADMIN DASHBOARD (ALL TABS) ---
ADMIN_LAYOUT = '''<!DOCTYPE html>
<html lang="mr">
<head><meta charset="UTF-8"><title>Admin Dashboard - Shreeguru</title>
<style>
body { font-family: sans-serif; margin: 0; background: #f1f5f9; }
.header { background: #0b3c5d; color: white; padding: 15px; text-align: center; position: relative; }
.logout-btn { position: absolute; right: 20px; top: 15px; background: #dc2626; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px; }
.menu { background: #1e293b; display: flex; justify-content: center; gap: 8px; padding: 10px; flex-wrap: wrap; }
.tab-btn { color: white; background: #2563eb; padding: 8px 14px; text-decoration: none; border-radius: 4px; font-size: 13px; font-weight: bold; }
.tab-btn.active { background: #fde047 !important; color: #0b3c5d !important; }
.container { max-width: 1200px; margin: 20px auto; background: white; padding: 20px; border-radius: 6px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
th, td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; }
th { background: #0b3c5d; color: white; }
</style>
</head>
<body>
<div class="header">
    <h2 style="margin:0;">⚔️ श्रीगुरु करिअर अकॅडमी - प्रशासक पॅनेल</h2>
    <a href="/logout" class="logout-btn">लॉग आउट 🚪</a>
</div>
<div class="menu">
    <a href="/admin/add_test" class="tab-btn" style="background:#059669;">📝 नवीन टेस्ट (Timer/Bulk)</a>
    <a href="/admin?tab=students" class="tab-btn {% if curr_tab == 'students' %}active{% endif %}">👥 सर्व विद्यार्थी</a>
    <a href="/admin?tab=admission" class="tab-btn {% if curr_tab == 'admission' %}active{% endif %}">📝 नवीन प्रवेश</a>
    <a href="/admin?tab=test_leads" class="tab-btn {% if curr_tab == 'test_leads' %}active{% endif %}" style="background:#10b981;">📊 टेस्ट लीड्स व नंबर</a>
    <a href="/library" target="_blank" class="tab-btn" style="background:#0284c7;">📚 लायब्ररी</a>
    <a href="/admin?tab=exp" class="tab-btn {% if curr_tab == 'exp' %}active{% endif %}" style="background:#e11d48;">💵 खर्च वही</a>
</div>
<div class="container">
    {% if curr_tab == 'students' %}
        <h3>📋 विद्यार्थी यादी</h3>
        <table>
            <tr><th>Reg ID</th><th>नाव</th><th>कोर्स</th><th>मोबाईल</th><th>शिल्लक फी</th></tr>
            {% for s in students %}
            <tr><td>REG-{{s.id}}</td><td><b>{{s.name}}</b></td><td>{{s.course}}</td><td>{{s.phone}}</td><td style="color:red;">₹{{(s.total_fees or 0)-(s.paid_fees or 0)}}</td></tr>
            {% else %}
            <tr><td colspan="5">विद्यार्थी नोंद नाही.</td></tr>
            {% endfor %}
        </table>
    {% elif curr_tab == 'test_leads' %}
        <h3 style="color:#059669;">📊 ऑनलाईन टेस्ट सबमिशन व खरे मोबाईल नंबर (WhatsApp Verified)</h3>
        <table>
            <tr><th>टेस्ट ID</th><th>विद्यार्थी नाव</th><th>खरा मोबाईल नंबर</th><th>टेस्टचे नाव</th><th>गुण</th><th>वेळ</th></tr>
            {% for sub in test_submissions %}
            <tr>
                <td>REG-{{sub.test_id}}</td>
                <td><b>{{sub.student_name}}</b></td>
                <td><b style="color:green; font-size:14px;">{{sub.student_mobile}}</b> <a href="https://wa.me/91{{sub.student_mobile}}" target="_blank" style="background:#25D366; color:white; padding:3px 6px; text-decoration:none; border-radius:3px; font-size:11px;">📲 WhatsApp</a></td>
                <td>{{sub.title or 'सराव टेस्ट'}}</td>
                <td><b>{{sub.score}} / {{sub.total_marks}}</b></td>
                <td>{{sub.created_at}}</td>
            </tr>
            {% else %}
            <tr><td colspan="6">अद्याप कोणतीही टेस्ट सबमिशन आलेली नाही.</td></tr>
            {% endfor %}
        </table>
    {% elif curr_tab == 'admission' %}
        <h3>📝 नवीन विद्यार्थी प्रवेश</h3>
        <form action="/add_student" method="POST">
            <input type="text" name="name" placeholder="विद्यार्थ्याचे पूर्ण नाव" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="text" name="course" placeholder="कोर्स (उदा. पोलीस भरती)" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="text" name="phone" placeholder="मोबाईल नंबर" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="number" name="total_fees" placeholder="एकूण फी" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="number" name="paid_fees" placeholder="भरलेली फी" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <button type="submit" style="background:green; color:white; padding:10px 20px; border:none; font-weight:bold; cursor:pointer;">प्रवेश सेव्ह करा</button>
        </form>
    {% elif curr_tab == 'exp' %}
        <h3>💵 दैनिक खर्च नोंदवही</h3>
        <form action="/add_expense" method="POST">
            <input type="text" name="category" placeholder="खर्चाचा प्रकार (उदा. भाजीपाला)" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="number" name="amount" placeholder="रक्कम (₹)" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="text" name="description" placeholder="तपशील" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <button type="submit" style="background:green; color:white; padding:10px 20px; border:none; font-weight:bold; cursor:pointer;">खर्च नोंदवा</button>
        </form>
    {% else %}
        <h3>🎛️ प्रशासक डॅशबोर्डमध्ये आपले स्वागत आहे!</h3>
        <p>वडील दिलेल्या मेनू टॅब्जमधून हवी ती माहिती निवडा.</p>
    {% endif %}
</div>
</body>
</html>'''

@app.route('/admin')
def admin_view():
    if session.get('user_role') != 'Admin': return redirect('/login')
    curr_tab = request.args.get('tab', 'test_leads')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students ORDER BY id DESC")
            students = cur.fetchall()
            cur.execute("SELECT s.*, t.title FROM student_submissions s LEFT JOIN online_tests t ON s.test_id = t.id ORDER BY s.id DESC")
            test_submissions = cur.fetchall()
    return render_template_string(ADMIN_LAYOUT, curr_tab=curr_tab, students=students, test_submissions=test_submissions)

@app.route('/add_student', methods=['POST'])
def add_student():
    if session.get('user_role') != 'Admin': return redirect('/login')
    name = request.form.get('name')
    course = request.form.get('course')
    phone = request.form.get('phone')
    total_fees = safe_float(request.form.get('total_fees'))
    paid_fees = safe_float(request.form.get('paid_fees'))
    today = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO students (name, course, phone, total_fees, paid_fees, admission_date) VALUES (%s, %s, %s, %s, %s, %s)",
                        (name, course, phone, total_fees, paid_fees, today))
        conn.commit()
    return redirect('/admin?tab=students')

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if session.get('user_role') != 'Admin': return redirect('/login')
    cat = request.form.get('category')
    amt = safe_float(request.form.get('amount'))
    desc = request.form.get('description')
    today = date.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO expenses (exp_date, category, description, amount) VALUES (%s, %s, %s, %s)", (today, cat, desc, amt))
        conn.commit()
    return redirect('/admin?tab=exp')

@app.route('/manager')
def manager_view():
    if session.get('user_role') != 'Manager': return redirect('/login')
    return "<h2>Manager Dashboard</h2><a href='/logout'>Logout</a>"

@app.route('/trainer')
def trainer_view():
    if session.get('user_role') != 'Trainer': return redirect('/login')
    return "<h2>Trainer Dashboard</h2><a href='/logout'>Logout</a>"

@app.route('/clerk')
def clerk_view():
    if session.get('user_role') != 'Clerk': return redirect('/login')
    return "<h2>Clerk Dashboard</h2><a href='/logout'>Logout</a>"

@app.route('/admin/add_test', methods=['GET', 'POST'])
def add_test():
    if request.method == 'POST':
        test_title = request.form.get('test_title')
        time_limit = request.form.get('time_limit')
        time_limit = int(time_limit) if time_limit and time_limit.isdigit() else None
        raw_content = request.form.get('raw_content', '')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO online_tests (title, time_limit, raw_questions) VALUES (%s, %s, %s);", (test_title, time_limit, raw_content))
            conn.commit()
        return jsonify({"status": "success", "message": "टेस्ट यशस्वीरित्या सेव्ह झाली!"})
    return """
    <div style="font-family:sans-serif; padding:30px; max-width:600px; margin:auto;">
        <h2>📝 नवीन टेस्ट तयार करा</h2>
        <form method="POST">
            <input type="text" name="test_title" placeholder="टेस्टचे नाव" required style="width:100%; padding:10px; margin-bottom:10px;"><br>
            <input type="number" name="time_limit" placeholder="टाईम लिमिट मिनिटांत (उदा. 15)" style="width:100%; padding:10px; margin-bottom:10px;"><br>
            <textarea name="raw_content" rows="6" placeholder="प्रश्न कॉपी-पेस्ट करा..." style="width:100%; padding:10px; margin-bottom:10px;"></textarea><br>
            <button type="submit" style="background:green; color:white; padding:10px 20px; border:none; font-weight:bold; cursor:pointer;">टेस्ट सेव्ह करा</button>
        </form>
        <br><a href="/admin">🔙 डॅशबोर्डकडे जा</a>
    </div>
    """

@app.route('/library')
def library():
    return "<h2>📚 लायब्ररी व स्टडी लॅब डॅशबोर्ड</h2><a href='/admin'>🏠 डॅशबोर्डकडे जा</a>"

init_db()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

