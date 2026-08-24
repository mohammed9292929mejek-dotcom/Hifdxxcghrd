import os
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "PARTO_2026_CHANGE_THIS")


def db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            emoji TEXT DEFAULT '👤',
            bio TEXT DEFAULT '',
            admin BOOLEAN DEFAULT FALSE,
            banned BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL,
            owner TEXT NOT NULL,
            emoji TEXT DEFAULT '👥',
            bio TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            room INTEGER,
            room_id INTEGER,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT DEFAULT '',
            created TEXT DEFAULT '',
            reply INTEGER DEFAULT 0,
            edited BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS private_messages (
            id SERIAL PRIMARY KEY,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            text TEXT NOT NULL
        )
    """)

    for sql in [
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS room INTEGER",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS room_id INTEGER",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS created_at TEXT DEFAULT ''",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS created TEXT DEFAULT ''",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reply INTEGER DEFAULT 0",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited BOOLEAN DEFAULT FALSE",
    ]:
        cur.execute(sql)

    cur.execute("""
        UPDATE messages
        SET room = room_id
        WHERE room IS NULL AND room_id IS NOT NULL
    """)
    cur.execute("""
        UPDATE messages
        SET room_id = room
        WHERE room_id IS NULL AND room IS NOT NULL
    """)

    now = datetime.now().isoformat(timespec="seconds")
    cur.execute("""
        UPDATE messages SET created_at=%s
        WHERE created_at IS NULL OR created_at=''
    """, (now,))
    cur.execute("""
        UPDATE messages SET created=created_at
        WHERE created IS NULL OR created=''
    """)

    cur.execute("SELECT id FROM users WHERE username=%s", ("parto",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users
            (username,email,password,emoji,bio,admin,banned)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            "parto", "parto@local",
            generate_password_hash("123456"),
            "⚡", "مدیر رسمی پرتو", True, False
        ))

    cur.execute("SELECT id FROM rooms WHERE username=%s", ("parto",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO rooms
            (name,username,kind,owner,emoji,bio)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            "پرتو", "parto", "channel", "parto",
            "⚡", "کانال رسمی پرتو"
        ))

    conn.commit()
    cur.close()
    conn.close()


def me():
    if "user" not in session:
        return None
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (session["user"],))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def safe(value):
    if value is None:
        return ""
    return (str(value).replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


CSS = """
*{box-sizing:border-box}
:root{--bg:#070b14;--panel:#0d1422;--line:#223047;--text:#f5f7fb;--muted:#8e9bb0;--accent:#7c5cff}
html,body{margin:0;min-height:100%;background:radial-gradient(circle at 15% 0%,#17245a 0,transparent 32%),radial-gradient(circle at 100% 30%,#073e55 0,transparent 28%),var(--bg);color:var(--text);font-family:Tahoma,Arial,sans-serif;direction:rtl}
body{min-height:100vh}a{color:var(--text);text-decoration:none}
.app{min-height:100vh;display:flex;overflow:hidden}
.menu{width:88px;background:rgba(13,20,34,.82);backdrop-filter:blur(18px);border-left:1px solid var(--line);overflow:auto;flex-shrink:0}
.menu a{display:block;text-align:center;padding:14px 4px;color:#cbd5e7;border-bottom:1px solid rgba(255,255,255,.04);font-size:12px}
.menu a:hover{background:rgba(124,92,255,.15);color:#fff}
.main{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh}
.head{padding:16px 18px;background:rgba(13,20,34,.78);backdrop-filter:blur(18px);border-bottom:1px solid var(--line);font-size:18px;font-weight:bold}
.msgs{flex:1;overflow:auto;padding:18px}
.msg{background:rgba(17,27,43,.92);border:1px solid rgba(255,255,255,.05);padding:11px 13px;margin:9px 0;border-radius:17px;max-width:min(86%,560px);box-shadow:0 8px 22px rgba(0,0,0,.12);line-height:1.8;word-wrap:break-word}
.mine{margin-right:auto;background:linear-gradient(135deg,#263f7c,#29325f);border-color:rgba(124,92,255,.3)}
.send{display:flex;gap:8px;padding:10px;background:rgba(13,20,34,.9);border-top:1px solid var(--line)}
.send input{flex:1;margin:0!important;border-radius:24px!important}.send button{width:58px;margin:0!important;border-radius:20px!important}
input,textarea,select,button{width:100%;padding:12px;margin:6px 0;border:1px solid transparent;border-radius:12px;font:inherit}
input,textarea,select{background:#111c2d;color:#fff;outline:none}input:focus,textarea:focus,select:focus{border-color:var(--accent)}
button{background:linear-gradient(135deg,var(--accent),#5a7cff);color:white;font-weight:bold;cursor:pointer}
.box{width:92%;max-width:540px;margin:35px auto;background:rgba(13,20,34,.88);border:1px solid var(--line);backdrop-filter:blur(20px);padding:24px;border-radius:24px;box-shadow:0 20px 70px rgba(0,0,0,.35)}
.card{background:#111c2d;border:1px solid var(--line);padding:12px;margin:8px 0;border-radius:15px}
.avatar{font-size:64px;text-align:center}.tick{background:linear-gradient(135deg,#ffd43b,#ffad1f);color:#16120a;padding:3px 8px;border-radius:20px;font-size:12px}
.small{color:var(--muted);font-size:12px}.danger{color:#ff6b6b}.success{color:#51cf66}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.stat{background:#111c2d;border:1px solid var(--line);padding:15px;border-radius:15px;text-align:center}.stat b{display:block;font-size:22px;margin-bottom:5px}
@media(max-width:600px){.menu{width:72px}.menu a{padding:12px 2px;font-size:10px}.msgs{padding:10px}.msg{max-width:92%}.head{padding:13px}.box{margin:18px auto;padding:18px}}
"""


def page(html):
    return "<!doctype html><html lang='fa' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>پرتو</title><style>" + CSS + "</style></head><body>" + html + "</body></html>"


@app.route("/")
def home():
    if me():
        return redirect("/chat")
    return page("""
    <div class="box"><div class="avatar">⚡</div><h1>پرتو</h1>
    <p class="small">پیام‌رسان وب پرتو</p>
    <form method="post" action="/login">
    <input name="email" type="email" placeholder="ایمیل" required>
    <input name="password" type="password" placeholder="رمز عبور" required>
    <button>ورود</button></form><br><a href="/register">ثبت‌نام</a></div>
    """)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return page("""
        <div class="box"><h2>ثبت‌نام</h2><form method="post">
        <input name="username" placeholder="آیدی" required>
        <input name="email" type="email" placeholder="ایمیل" required>
        <input name="password" type="password" placeholder="رمز عبور" required>
        <button>ساخت حساب</button></form><a href="/">بازگشت</a></div>
        """)

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if len(username) < 3:
        return "آیدی حداقل ۳ کاراکتر باشد."
    if len(username) > 40:
        return "آیدی بیش از حد طولانی است."
    if len(password) < 6:
        return "رمز حداقل ۶ کاراکتر باشد."

    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users(username,email,password)
            VALUES(%s,%s,%s)
        """, (username, email, generate_password_hash(password)))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        return "آیدی یا ایمیل قبلاً استفاده شده."
    cur.close()
    conn.close()
    session["user"] = username
    return redirect("/chat")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    u = cur.fetchone()
    cur.close()
    conn.close()

    if not u:
        return "کاربر پیدا نشد."
    if u["banned"]:
        return "حساب شما مسدود است."
    if not check_password_hash(u["password"], password):
        return "رمز عبور اشتباه است."
    session["user"] = u["username"]
    return redirect("/chat")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/profile/<username>")
def profile(username):
    u = me()
    if not u:
        return redirect("/")
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    target = cur.fetchone()
    cur.close()
    conn.close()
    if not target:
        return "کاربر پیدا نشد."

    tick = "<span class='tick'>✓ تأیید شده</span>" if target["admin"] else ""
    edit = "<br><a href='/editprofile'>⚙️ ویرایش پروفایل</a>" if u["username"] == username else ""

    return page(
        "<div class='box'><div class='avatar'>" + safe(target["emoji"]) +
        "</div><h2>@" + safe(target["username"]) + " " + tick +
        "</h2><p>" + safe(target["bio"] or "بدون بیو") +
        "</p><a href='/private/" + safe(target["username"]) +
        "'>💬 پیام خصوصی</a>" + edit +
        "<br><br><a href='/chat'>بازگشت</a></div>"
    )


@app.route("/editprofile", methods=["GET", "POST"])
def editprofile():
    u = me()
    if not u:
        return redirect("/")

    if request.method == "GET":
        return page("""
        <div class="box"><h2>👤 پروفایل</h2><form method="post">
        <select name="emoji"><option>👤</option><option>👻</option><option>😎</option><option>⚡</option><option>💻</option><option>🕷️</option><option>☠️</option><option>🤖</option><option>🔥</option></select>
        <textarea name="bio" placeholder="بیوگرافی" maxlength="200"></textarea>
        <button>ذخیره</button></form><a href="/chat">بازگشت</a></div>
        """)

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET emoji=%s,bio=%s WHERE username=%s",
                (request.form.get("emoji", "👤"), request.form.get("bio", "")[:200], u["username"]))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/profile/" + u["username"])


@app.route("/private/<username>")
def private(username):
    u = me()
    if not u:
        return redirect("/")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    target = cur.fetchone()
    if not target:
        cur.close()
        conn.close()
        return "کاربر پیدا نشد."

    cur.execute("""
        SELECT * FROM private_messages
        WHERE (sender=%s AND receiver=%s)
           OR (sender=%s AND receiver=%s)
        ORDER BY id
    """, (u["username"], username, username, u["username"]))
    messages = cur.fetchall()
    cur.close()
    conn.close()

    body = ""
    for m in messages:
        cls = "msg mine" if m["sender"] == u["username"] else "msg"
        body += "<div class='" + cls + "'><b>@" + safe(m["sender"]) + "</b><br>" + safe(m["text"]) + "</div>"

    return page(
        "<div class='app'><div class='main'><div class='head'>" +
        safe(target["emoji"]) + " @" + safe(target["username"]) +
        "</div><div class='msgs'>" + body +
        "</div><form class='send' method='post' action='/private/" +
        safe(username) + "/send'><input name='text' placeholder='پیام خصوصی...' maxlength='2000' required><button>➤</button></form></div></div>"
    )


@app.route("/private/<username>/send", methods=["POST"])
def private_send(username):
    u = me()
    if not u:
        return redirect("/")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username=%s", (username,))
    target = cur.fetchone()
    if not target:
        cur.close()
        conn.close()
        return "کاربر پیدا نشد."

    text = request.form.get("text", "").strip()
    if text:
        cur.execute("""
            INSERT INTO private_messages(sender,receiver,text)
            VALUES(%s,%s,%s)
        """, (u["username"], username, text[:2000]))
        conn.commit()

    cur.close()
    conn.close()
    return redirect("/private/" + username)


@app.route("/chat")
def chat():
    u = me()
    if not u:
        return redirect("/")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms ORDER BY id")
    rooms = cur.fetchall()

    if not rooms:
        cur.close()
        conn.close()
        return "هیچ اتاقی وجود ندارد."

    rid = request.args.get("room")
    try:
        rid = int(rid) if rid else None
    except ValueError:
        rid = None

    room = next((r for r in rooms if r["id"] == rid), rooms[0])

    cur.execute("SELECT * FROM messages WHERE room=%s ORDER BY id", (room["id"],))
    messages = cur.fetchall()

    menu = ""
    for r in rooms:
        menu += "<a href='/chat?room=" + str(r["id"]) + "'>" + safe(r["emoji"]) + "<br>" + safe(r["name"]) + "</a>"

    body = ""
    for m in messages:
        cls = "msg mine" if m["username"] == u["username"] else "msg"
        reply_html = ""

        if m["reply"]:
            cur.execute("SELECT username,text FROM messages WHERE id=%s", (m["reply"],))
            old = cur.fetchone()
            if old:
                reply_html = "<div class='card'>↩️ @" + safe(old["username"]) + "<br>" + safe(old["text"]) + "</div>"

        actions = "<a href='/reply/" + str(m["id"]) + "'>↩️</a>"
        if m["username"] == u["username"] or u["admin"]:
            actions += " <a href='/edit/" + str(m["id"]) + "'>✏️</a> <a href='/delete/" + str(m["id"]) + "'>🗑️</a>"

        body += (
            "<div class='" + cls + "'>" + reply_html +
            "<a href='/profile/" + safe(m["username"]) + "'>@" + safe(m["username"]) +
            "</a><br>" + safe(m["text"]) +
            (" ✏️" if m["edited"] else "") +
            "<br>" + actions + "</div>"
        )

    form = ""
    if room["kind"] == "group" or room["owner"] == u["username"] or u["admin"]:
        form = "<form class='send' method='post' action='/send/" + str(room["id"]) + "'><input name='text' placeholder='پیام...' maxlength='2000' required><button>➤</button></form>"

    admin_link = "<a href='/admin'>👑<br>ادمین</a>" if u["admin"] else ""

    html = (
        "<div class='app'><div class='menu'>" + menu +
        "<a href='/profile/" + safe(u["username"]) + "'>👤<br>پروفایل</a>" +
        "<a href='/editprofile'>⚙️<br>تنظیمات</a>" +
        "<a href='/create'>➕<br>ساخت</a>" +
        admin_link +
        "<a href='/logout'>🚪<br>خروج</a></div>" +
        "<div class='main'><div class='head'>" + safe(room["emoji"]) + " " +
        safe(room["name"]) +
        (" <span class='tick'>✓</span>" if room["username"] == "parto" else "") +
        "</div><div class='msgs'>" + body + "</div>" + form +
        "</div></div>"
    )

    cur.close()
    conn.close()
    return page(html)


@app.route("/send/<int:rid>", methods=["POST"])
def send(rid):
    u = me()
    if not u:
        return redirect("/")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms WHERE id=%s", (rid,))
    room = cur.fetchone()

    if not room:
        cur.close()
        conn.close()
        return "اتاق پیدا نشد."

    if room["kind"] == "channel" and room["owner"] != u["username"] and not u["admin"]:
        cur.close()
        conn.close()
        return "فقط مالک کانال می‌تواند پیام بدهد."

    text = request.form.get("text", "").strip()
    if text:
        now = datetime.now().isoformat(timespec="seconds")
        cur.execute("""
            INSERT INTO messages
            (room,room_id,username,text,created_at,created,reply,edited)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
        """, (rid, rid, u["username"], text[:2000], now, now, 0, False))
        conn.commit()

    cur.close()
    conn.close()
    return redirect("/chat?room=" + str(rid))


@app.route("/create", methods=["GET", "POST"])
def create():
    u = me()
    if not u:
        return redirect("/")

    if request.method == "GET":
        return page("""
        <div class="box"><h2>➕ ساخت گروه یا کانال</h2><form method="post">
        <input name="name" placeholder="نام" maxlength="80" required>
        <input name="username" placeholder="آیدی" maxlength="40" required>
        <select name="kind"><option value="group">👥 گروه</option><option value="channel">📢 کانال</option></select>
        <select name="emoji"><option>👥</option><option>📢</option><option>⚡</option><option>👻</option><option>💻</option><option>🤖</option></select>
        <input name="bio" placeholder="توضیح" maxlength="200">
        <button>ساخت</button></form><a href="/chat">بازگشت</a></div>
        """)

    name = request.form.get("name", "").strip()[:80]
    username = request.form.get("username", "").strip()[:40].lstrip("@")
    kind = request.form.get("kind", "group")
    emoji = request.form.get("emoji", "👥")
    bio = request.form.get("bio", "").strip()[:200]

    if kind not in ("group", "channel"):
        kind = "group"
    if len(username) < 3:
        return "آیدی حداقل ۳ کاراکتر باشد."

    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO rooms(name,username,kind,owner,emoji,bio)
            VALUES(%s,%s,%s,%s,%s,%s)
        """, (name, username, kind, u["username"], emoji, bio))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        return "این آیدی قبلاً استفاده شده."

    cur.close()
    conn.close()
    return redirect("/chat")


@app.route("/reply/<int:mid>", methods=["GET", "POST"])
def reply(mid):
    u = me()
    if not u:
        return redirect("/")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM messages WHERE id=%s", (mid,))
    m = cur.fetchone()

    if not m:
        cur.close()
        conn.close()
        return "پیام پیدا نشد."

    if request.method == "GET":
        html = "<div class='box'><h2>↩️ پاسخ</h2><div class='card'>" + safe(m["text"]) + "</div><form method='post'><input name='text' placeholder='پاسخ...' maxlength='2000' required><button>ارسال</button></form></div>"
        cur.close()
        conn.close()
        return page(html)

    text = request.form.get("text", "").strip()
    if text:
        now = datetime.now().isoformat(timespec="seconds")
        cur.execute("""
            INSERT INTO messages
            (room,room_id,username,text,created_at,created,reply,edited)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
        """, (m["room"], m["room"], u["username"], text[:2000], now, now, mid, False))
        conn.commit()

    room = m["room"]
    cur.close()
    conn.close()
    return redirect("/chat?room=" + str(room))


@app.route("/edit/<int:mid>", methods=["GET", "POST"])
def edit(mid):
    u = me()
    if not u:
        return redirect("/")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM messages WHERE id=%s", (mid,))
    m = cur.fetchone()

    if not m:
        cur.close()
        conn.close()
        return "پیام پیدا نشد."

    if m["username"] != u["username"] and not u["admin"]:
        cur.close()
        conn.close()
        return "اجازه ویرایش این پیام را ندارید."

    if request.method == "GET":
        html = "<div class='box'><h2>✏️ ویرایش پیام</h2><form method='post'><textarea name='text' maxlength='2000' required>" + safe(m["text"]) + "</textarea><button>ذخیره</button></form></div>"
        cur.close()
        conn.close()
        return page(html)

    text = request.form.get("text", "").strip()
    if not text:
        cur.close()
        conn.close()
        return "متن پیام نمی‌تواند خالی باشد."

    cur.execute("UPDATE messages SET text=%s,edited=TRUE WHERE id=%s", (text[:2000], mid))
    conn.commit()
    room = m["room"]
    cur.close()
    conn.close()
    return redirect("/chat?room=" + str(room))


@app.route("/delete/<int:mid>")
def delete(mid):
    u = me()
    if not u:
        return redirect("/")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM messages WHERE id=%s", (mid,))
    m = cur.fetchone()

    if not m:
        cur.close()
        conn.close()
        return "پیام پیدا نشد."

    if m["username"] != u["username"] and not u["admin"]:
        cur.close()
        conn.close()
        return "اجازه حذف این پیام را ندارید."

    room = m["room"]
    cur.execute("DELETE FROM messages WHERE id=%s", (mid,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/chat?room=" + str(room))


@app.route("/admin")
def admin():
    u = me()
    if not u:
        return redirect("/")
    if not u["admin"]:
        return "دسترسی غیرمجاز."

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY id")
    users = cur.fetchall()
    cur.execute("SELECT * FROM rooms ORDER BY id")
    rooms = cur.fetchall()
    cur.close()
    conn.close()

    cards = ""
    for x in users:
        action = ""
        if x["username"] != u["username"]:
            if x["banned"]:
                action = "<a href='/admin/unban/" + safe(x["username"]) + "'>✅ رفع مسدودی</a>"
            else:
                action = "<a href='/admin/ban/" + safe(x["username"]) + "'>🚫 مسدود</a>"

        cards += (
            "<div class='card'>" + safe(x["emoji"]) +
            " <b>@" + safe(x["username"]) + "</b>" +
            (" <span class='tick'>✓</span>" if x["admin"] else "") +
            "<br>" + safe(x["email"]) + "<br>" + action + "</div>"
        )

    room_cards = ""
    for r in rooms:
        room_cards += (
            "<div class='card'>" + safe(r["emoji"]) +
            " <b>" + safe(r["name"]) + "</b><br>" +
            "@" + safe(r["username"]) + " · " + safe(r["kind"]) +
            "</div>"
        )

    html = """
    <div class="box">
        <div class="admin-title">👑 پنل مدیریت پرتو</div>
        <div class="stats">
            <div class="stat"><b>%d</b>کاربر</div>
            <div class="stat"><b>%d</b>اتاق</div>
        </div>
        <h3>👤 کاربران</h3>
        %s
        <h3>💬 اتاق‌ها</h3>
        %s
        <br><a href="/chat">بازگشت به چت</a>
    </div>
    """ % (len(users), len(rooms), cards, room_cards)

    return page(html)


@app.route("/admin/ban/<username>")
def ban(username):
    u = me()
    if not u or not u["admin"]:
        return "دسترسی غیرمجاز."

    if username == u["username"]:
        return "نمی‌توانید خودتان را مسدود کنید."

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET banned=TRUE WHERE username=%s", (username,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/admin/unban/<username>")
def unban(username):
    u = me()
    if not u or not u["admin"]:
        return "دسترسی غیرمجاز."

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET banned=FALSE WHERE username=%s", (username,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/health")
def health():
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        return "OK"
    except Exception as e:
        return "DATABASE ERROR: " + safe(e), 500


@app.route("/init")
def init_route():
    # فقط برای راه‌اندازی اولیه دیتابیس
    try:
        init_db()
        return "PARTO DATABASE INITIALIZED"
    except Exception as e:
        return "INIT ERROR: " + safe(e), 500


if __name__ == "__main__":
    # Render PORT را خودش تنظیم می‌کند.
    port = int(os.environ.get("PORT", "8080"))
    init_db()
    app.run(host="0.0.0.0", port=port)
