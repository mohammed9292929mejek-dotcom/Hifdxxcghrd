import os
import base64
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "PARTO_CHANGE_ME_2026")

MAX_IMAGE = 2 * 1024 * 1024
ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}


# =========================================================
# DATABASE
# =========================================================

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
            avatar_data TEXT DEFAULT '',
            admin BOOLEAN DEFAULT FALSE,
            banned BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('group','channel')),
            owner TEXT NOT NULL,
            emoji TEXT DEFAULT '👥',
            bio TEXT DEFAULT '',
            avatar_data TEXT DEFAULT '',
            banned BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            room INTEGER NOT NULL,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reply INTEGER DEFAULT 0,
            edited BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS private_messages (
            id SERIAL PRIMARY KEY,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_data TEXT DEFAULT ''",
        "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS avatar_data TEXT DEFAULT ''",
        "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS banned BOOLEAN DEFAULT FALSE",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reply INTEGER DEFAULT 0",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited BOOLEAN DEFAULT FALSE",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE private_messages ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    ]

    for sql in migrations:
        cur.execute(sql)

    # Compatibility with older versions that used room_id.
    cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS room_id INTEGER")
    cur.execute("""
        UPDATE messages
        SET room = room_id
        WHERE (room IS NULL OR room = 0) AND room_id IS NOT NULL
    """)
    cur.execute("""
        UPDATE messages
        SET room_id = room
        WHERE room_id IS NULL AND room IS NOT NULL
    """)

    # Default admin.
    cur.execute("SELECT id FROM users WHERE username=%s", ("parto",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users
            (username,email,password,emoji,bio,admin,banned)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            "parto",
            "parto@local",
            generate_password_hash("123456"),
            "⚡",
            "مدیر رسمی پرتو",
            True,
            False
        ))

    # Official channel.
    cur.execute("SELECT id FROM rooms WHERE username=%s", ("parto",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO rooms
            (name,username,kind,owner,emoji,bio,banned)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            "پرتو", "parto", "channel", "parto",
            "⚡", "کانال رسمی پرتو", False
        ))

    conn.commit()
    cur.close()
    conn.close()
    print("PARTO PostgreSQL DATABASE OK")


# =========================================================
# HELPERS
# =========================================================

def me():
    username = session.get("user")
    if not username:
        return None

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and user["banned"]:
        session.clear()
        return None

    return user


def esc(value):
    if value is None:
        return ""
    return (str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def image_from_request(field="avatar"):
    f = request.files.get(field)
    if not f or not f.filename:
        return None

    ext = secure_filename(f.filename).rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return "ERROR"

    data = f.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        return "ERROR"

    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
    }[ext]

    return "data:%s;base64,%s" % (
        mime,
        base64.b64encode(data).decode("ascii")
    )


def avatar_html(emoji, image, cls="avatar"):
    if image:
        return "<img class='%s-img' src='%s' alt='avatar'>" % (
            cls, esc(image)
        )
    return "<div class='%s'>%s</div>" % (cls, esc(emoji or "👤"))


def page(content, title="پرتو"):
    css = """
    *{box-sizing:border-box}
    :root{--bg:#070b14;--panel:#0d1422;--panel2:#111b2b;--line:#223047;
    --text:#f5f7fb;--muted:#8e9bb0;--accent:#7c5cff}
    html,body{margin:0;min-height:100%;background:
    radial-gradient(circle at 15% 0%,#17245a 0,transparent 32%),
    radial-gradient(circle at 100% 30%,#073e55 0,transparent 28%),var(--bg);
    color:var(--text);font-family:Tahoma,Arial,sans-serif;direction:rtl}
    body{min-height:100vh}a{color:var(--text);text-decoration:none}
    a:hover{opacity:.85}.app{min-height:100vh;display:flex}
    .sidebar{width:280px;background:rgba(13,20,34,.9);border-left:1px solid var(--line);
    display:flex;flex-direction:column;flex-shrink:0}.brand{padding:18px;font-size:22px;font-weight:bold;
    border-bottom:1px solid var(--line)}.room-list{overflow:auto;flex:1;padding:8px}
    .room{display:flex;align-items:center;gap:10px;padding:10px;border-radius:14px;margin:4px 0}
    .room:hover,.room.active{background:#17223a}.room-name{font-weight:bold}.room-user{font-size:11px;color:var(--muted)}
    .room-avatar,.room-avatar-img{width:46px;height:46px;border-radius:50%;object-fit:cover;display:flex;
    align-items:center;justify-content:center;background:#18233a;font-size:25px;flex-shrink:0}
    .profile-mini{padding:10px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center}
    .main{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh}
    .head{height:68px;padding:10px 16px;background:rgba(13,20,34,.88);border-bottom:1px solid var(--line);
    display:flex;align-items:center;gap:10px}.head-avatar,.head-avatar-img{width:44px;height:44px;border-radius:50%;
    object-fit:cover;display:flex;align-items:center;justify-content:center;background:#18233a;font-size:23px}
    .head-title{font-weight:bold}.head-sub{font-size:11px;color:var(--muted)}
    .msgs{flex:1;overflow:auto;padding:18px}.msg{background:rgba(17,27,43,.94);border:1px solid rgba(255,255,255,.05);
    padding:9px 12px;margin:8px 0;border-radius:16px;max-width:min(78%,600px);line-height:1.8;word-wrap:break-word}
    .mine{margin-right:auto;background:linear-gradient(135deg,#263f7c,#29325f)}
    .msg-user{font-size:12px;color:#b8c5ff}.msg-time{font-size:10px;color:var(--muted)}
    .reply{border-right:3px solid var(--accent);background:#0d1628;padding:6px 9px;border-radius:9px;margin-bottom:6px;font-size:12px}
    .actions{font-size:12px;margin-top:5px}.actions a{margin-left:7px}
    .send{display:flex;gap:8px;padding:10px;background:rgba(13,20,34,.95);border-top:1px solid var(--line)}
    .send input{flex:1;margin:0!important;border-radius:24px!important}.send button{width:58px;margin:0!important;border-radius:20px!important}
    input,textarea,select,button{width:100%;padding:12px;margin:6px 0;border:1px solid transparent;border-radius:12px;font:inherit}
    input,textarea,select{background:#111c2d;color:#fff;outline:none}textarea{min-height:110px;resize:vertical}
    input:focus,textarea:focus,select:focus{border-color:var(--accent)}
    button{background:linear-gradient(135deg,var(--accent),#5a7cff);color:#fff;font-weight:bold;cursor:pointer}
    .box{width:92%;max-width:620px;margin:30px auto;background:rgba(13,20,34,.9);border:1px solid var(--line);
    padding:22px;border-radius:24px;box-shadow:0 20px 70px rgba(0,0,0,.35)}
    .card{background:#111c2d;border:1px solid var(--line);padding:12px;margin:8px 0;border-radius:15px}
    .center{text-align:center}.avatar{width:82px;height:82px;border-radius:50%;background:#18233a;display:flex;
    align-items:center;justify-content:center;font-size:46px;margin:0 auto 10px}.avatar-img{width:82px;height:82px;
    border-radius:50%;object-fit:cover;display:block;margin:0 auto 10px}.tick{background:#ffd43b;color:#17120a;
    padding:3px 7px;border-radius:20px;font-size:11px}.muted{color:var(--muted);font-size:12px}
    .top-actions{display:flex;gap:7px;flex-wrap:wrap}.btn{display:inline-block;background:#17223a;padding:9px 12px;
    border-radius:11px;margin:3px}.danger{color:#ff8585}.ok{color:#63e6be}
    .admin-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.stat{background:#111c2d;border:1px solid var(--line);
    padding:15px;border-radius:15px;text-align:center}.stat b{font-size:24px;display:block}
    .upload{padding:12px;background:#111c2d;border:1px dashed #34425e;border-radius:13px}
    .empty{text-align:center;color:var(--muted);padding:35px}
    @media(max-width:760px){
        .sidebar{width:92px}.brand{font-size:16px;text-align:center;padding:15px 5px}
        .room{justify-content:center}.room-info,.profile-mini .room-info{display:none}
        .profile-mini{justify-content:center}.room-avatar,.room-avatar-img{width:48px;height:48px}
        .msg{max-width:91%}.head{height:62px}.msgs{padding:10px}
    }
    """
    return """<!doctype html><html lang="fa" dir="rtl"><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>%s</title><style>%s</style></head><body>%s</body></html>""" % (
        esc(title), css, content
    )


def room_sidebar(rooms, current_id=None, user=None):
    items = ""
    for r in rooms:
        active = " active" if current_id == r["id"] else ""
        av = avatar_html(r["emoji"], r["avatar_data"], "room-avatar")
        items += """
        <a class="room%s" href="/chat/%s">
            %s
            <div class="room-info">
                <div class="room-name">%s %s</div>
                <div class="room-user">@%s · %s</div>
            </div>
        </a>
        """ % (
            active, r["id"], av, esc(r["name"]),
            "🚫" if r["banned"] else "",
            esc(r["username"]), "کانال" if r["kind"] == "channel" else "گروه"
        )

    if not items:
        items = "<div class='empty'>هنوز گروه یا کانالی ساخته نشده.</div>"

    user_html = ""
    if user:
        user_html = """
        <div class="profile-mini">
            %s
            <div class="room-info">
                <b>@%s</b><br>
                <a class="muted" href="/profile/%s">پروفایل</a>
            </div>
        </div>
        """ % (
            avatar_html(user["emoji"], user["avatar_data"], "room-avatar"),
            esc(user["username"]), esc(user["username"])
        )

    admin = ""
    if user and user["admin"]:
        admin = "<a class='btn' href='/admin'>👑 پنل ادمین</a>"

    return """
    <aside class="sidebar">
        <div class="brand">⚡ پرتو</div>
        <div class="room-list">%s</div>
        <div style="padding:8px;text-align:center">
            <a class="btn" href="/create">➕ ساخت</a>
            %s
        </div>
        %s
    </aside>
    """ % (items, admin, user_html)


# =========================================================
# AUTH
# =========================================================

@app.route("/")
def home():
    if me():
        return redirect("/chat")
    return page("""
    <div class="box center">
        <div class="avatar">⚡</div>
        <h1>پرتو</h1>
        <p class="muted">پیام‌رسان وب</p>
        <form method="post" action="/login">
            <input name="email" type="email" placeholder="ایمیل" required>
            <input name="password" type="password" placeholder="رمز عبور" required>
            <button>ورود</button>
        </form>
        <a class="btn" href="/register">ثبت‌نام</a>
    </div>
    """)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return page("""
        <div class="box">
            <h2>ساخت حساب</h2>
            <form method="post">
                <input name="username" minlength="3" maxlength="40" placeholder="آیدی" required>
                <input name="email" type="email" maxlength="120" placeholder="ایمیل" required>
                <input name="password" type="password" minlength="6" placeholder="رمز عبور" required>
                <button>ثبت‌نام</button>
            </form>
            <a class="back" href="/">← بازگشت</a>
        </div>
        """)

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if len(username) < 3 or len(username) > 40:
        return "آیدی باید بین ۳ تا ۴۰ کاراکتر باشد."
    if len(password) < 6:
        return "رمز باید حداقل ۶ کاراکتر باشد."

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
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

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


# =========================================================
# CHAT LIST / SEPARATE CHAT PAGE
# =========================================================

@app.route("/chat")
def chat_list():
    u = me()
    if not u:
        return redirect("/")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms WHERE banned=FALSE ORDER BY id DESC")
    rooms = cur.fetchall()
    cur.close()
    conn.close()

    sidebar = room_sidebar(rooms, user=u)

    return page("""
    <div class="app">
        %s
        <main class="main">
            <div class="head">
                <div>
                    <div class="head-title">گفتگوها</div>
                    <div class="head-sub">یک گروه یا کانال را انتخاب کن</div>
                </div>
            </div>
            <div class="msgs">
                <div class="empty">
                    از ستون کنار، چنل یا گروه موردنظر را انتخاب کن.
                </div>
            </div>
        </main>
    </div>
    """ % sidebar)


@app.route("/chat/<int:rid>")
def chat_room(rid):
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

    if room["banned"]:
        cur.close()
        conn.close()
        return "این گروه/کانال توسط ادمین مسدود شده است."

    cur.execute("SELECT * FROM rooms WHERE banned=FALSE ORDER BY id DESC")
    rooms = cur.fetchall()

    cur.execute("""
        SELECT * FROM messages
        WHERE room=%s
        ORDER BY id
    """, (rid,))
    messages = cur.fetchall()

    # Reply texts in one simple query per reply for compatibility.
    body = ""
    for m in messages:
        cls = "msg mine" if m["username"] == u["username"] else "msg"
        reply_html = ""
        if m["reply"]:
            cur.execute(
                "SELECT username,text FROM messages WHERE id=%s",
                (m["reply"],)
            )
            old = cur.fetchone()
            if old:
                reply_html = """
                <div class="reply">↩️ @%s<br>%s</div>
                """ % (esc(old["username"]), esc(old["text"][:180]))

        actions = "<a href='/reply/%s'>↩️ پاسخ</a>" % m["id"]
        if m["username"] == u["username"] or u["admin"]:
            actions += " <a href='/edit/%s'>✏️</a>" % m["id"]
            actions += " <a class='danger' href='/delete/%s'>🗑️</a>" % m["id"]

        body += """
        <div class="%s">
            %s
            <div class="msg-user">@%s</div>
            <div>%s%s</div>
            <div class="actions">%s <span class="msg-time">%s</span></div>
        </div>
        """ % (
            cls, reply_html, esc(m["username"]), esc(m["text"]),
            " ✏️" if m["edited"] else "", actions,
            esc(m["created_at"] or "")
        )

    if not body:
        body = "<div class='empty'>هنوز پیامی ارسال نشده.</div>"

    can_send = (
        room["kind"] == "group"
        or room["owner"] == u["username"]
        or u["admin"]
    )

    send_form = ""
    if can_send:
        send_form = """
        <form class="send" method="post" action="/send/%s">
            <input name="text" maxlength="2000" placeholder="پیام..." required>
            <button>➤</button>
        </form>
        """ % rid
    else:
        send_form = """
        <div class="send">
            <div class="muted">📢 فقط مالک این کانال می‌تواند پیام ارسال کند.</div>
        </div>
        """

    sidebar = room_sidebar(rooms, rid, u)
    av = avatar_html(room["emoji"], room["avatar_data"], "head-avatar")

    html = """
    <div class="app">
        %s
        <main class="main">
            <div class="head">
                %s
                <div>
                    <div class="head-title">%s %s</div>
                    <div class="head-sub">@%s · %s</div>
                </div>
            </div>
            <div class="msgs">%s</div>
            %s
        </main>
    </div>
    """ % (
        sidebar, av, esc(room["name"]),
        "<span class='tick'>✓</span>" if room["username"] == "parto" else "",
        esc(room["username"]),
        "کانال" if room["kind"] == "channel" else "گروه",
        body, send_form
    )

    cur.close()
    conn.close()
    return page(html, room["name"])


@app.route("/send/<int:rid>", methods=["POST"])
def send(rid):
    u = me()
    if not u:
        return redirect("/")

    text = request.form.get("text", "").strip()
    if not text:
        return redirect("/chat/%s" % rid)

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms WHERE id=%s", (rid,))
    room = cur.fetchone()

    if not room:
        cur.close()
        conn.close()
        return "اتاق پیدا نشد."

    if room["banned"]:
        cur.close()
        conn.close()
        return "این اتاق مسدود است."

    if room["kind"] == "channel" and room["owner"] != u["username"] and not u["admin"]:
        cur.close()
        conn.close()
        return "فقط مالک کانال می‌تواند پیام بدهد."

    cur.execute("""
        INSERT INTO messages(room,room_id,username,text,reply,edited)
        VALUES(%s,%s,%s,%s,%s,%s)
    """, (rid, rid, u["username"], text[:2000], 0, False))

    conn.commit()
    cur.close()
    conn.close()
    return redirect("/chat/%s" % rid)


# =========================================================
# PROFILE + IMAGE
# =========================================================

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
    edit = ""
    if u["username"] == username:
        edit = "<a class='btn' href='/editprofile'>⚙️ ویرایش</a>"

    return page("""
    <div class="box center">
        %s
        <h2>@%s %s</h2>
        <p>%s</p>
        <div class="top-actions">
            %s
            <a class="btn" href="/private/%s">💬 پیام خصوصی</a>
            <a class="btn" href="/chat">← چت‌ها</a>
        </div>
    </div>
    """ % (
        avatar_html(target["emoji"], target["avatar_data"]),
        esc(target["username"]), tick,
        esc(target["bio"] or "بدون بیو"),
        edit, esc(target["username"])
    ))


@app.route("/editprofile", methods=["GET", "POST"])
def editprofile():
    u = me()
    if not u:
        return redirect("/")

    if request.method == "GET":
        return page("""
        <div class="box">
            <h2>👤 ویرایش پروفایل</h2>
            <form method="post" enctype="multipart/form-data">
                <div class="upload">
                    عکس پروفایل، حداکثر ۲ مگابایت
                    <input type="file" name="avatar" accept="image/*">
                </div>
                <select name="emoji">
                    <option>👤</option><option>👻</option><option>😎</option>
                    <option>⚡</option><option>💻</option><option>🕷️</option>
                    <option>☠️</option><option>🤖</option><option>🔥</option>
                </select>
                <textarea name="bio" maxlength="200" placeholder="بیوگرافی"></textarea>
                <button>ذخیره</button>
            </form>
            <a class="btn" href="/profile/%s">بازگشت</a>
        </div>
        """ % esc(u["username"]))

    image = image_from_request()
    if image == "ERROR":
        return "فرمت عکس مجاز نیست یا حجم عکس بیشتر از ۲ مگابایت است."

    emoji = request.form.get("emoji", "👤")
    bio = request.form.get("bio", "")[:200]

    conn = db()
    cur = conn.cursor()

    if image is None:
        cur.execute("""
            UPDATE users SET emoji=%s,bio=%s WHERE username=%s
        """, (emoji, bio, u["username"]))
    else:
        cur.execute("""
            UPDATE users SET emoji=%s,bio=%s,avatar_data=%s WHERE username=%s
        """, (emoji, bio, image, u["username"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/profile/%s" % u["username"])


# =========================================================
# CREATE GROUP / CHANNEL
# =========================================================

@app.route("/create", methods=["GET", "POST"])
def create():
    u = me()
    if not u:
        return redirect("/")

    if request.method == "GET":
        return page("""
        <div class="box">
            <h2>➕ ساخت گروه یا کانال</h2>
            <form method="post" enctype="multipart/form-data">
                <input name="name" maxlength="80" placeholder="نام" required>
                <input name="username" maxlength="40" placeholder="آیدی مثل mychannel" required>
                <select name="kind">
                    <option value="group">👥 گروه</option>
                    <option value="channel">📢 کانال</option>
                </select>
                <select name="emoji">
                    <option>👥</option><option>📢</option><option>⚡</option>
                    <option>👻</option><option>💻</option><option>🤖</option>
                </select>
                <input name="bio" maxlength="200" placeholder="توضیح">
                <div class="upload">
                    عکس گروه/کانال، حداکثر ۲ مگابایت
                    <input type="file" name="avatar" accept="image/*">
                </div>
                <button>ساخت</button>
            </form>
            <a class="btn" href="/chat">بازگشت</a>
        </div>
        """)

    name = request.form.get("name", "").strip()[:80]
    username = request.form.get("username", "").strip().lower()[:40]
    kind = request.form.get("kind", "group")
    emoji = request.form.get("emoji", "👥")
    bio = request.form.get("bio", "").strip()[:200]

    if not name or len(username) < 3:
        return "نام و آیدی معتبر وارد کن."
    if kind not in ("group", "channel"):
        return "نوع اتاق نامعتبر است."

    image = image_from_request()
    if image == "ERROR":
        return "فرمت عکس مجاز نیست یا حجم عکس بیشتر از ۲ مگابایت است."

    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO rooms
            (name,username,kind,owner,emoji,bio,avatar_data,banned)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            name, username, kind, u["username"], emoji, bio,
            image or "", False
        ))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        return "این آیدی قبلاً استفاده شده."
    cur.close()
    conn.close()

    return redirect("/chat")


# =========================================================
# PRIVATE MESSAGES
# =========================================================

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
        body += """
        <div class="%s">
            <div class="msg-user">@%s</div>
            %s
        </div>
        """ % (cls, esc(m["sender"]), esc(m["text"]))

    if not body:
        body = "<div class='empty'>هنوز پیامی نیست.</div>"

    return page("""
    <div class="app">
        <main class="main">
            <div class="head">
                %s
                <div>
                    <div class="head-title">@%s</div>
                    <div class="head-sub">پیام خصوصی</div>
                </div>
            </div>
            <div class="msgs">%s</div>
            <form class="send" method="post" action="/private/%s/send">
                <input name="text" maxlength="2000" placeholder="پیام خصوصی..." required>
                <button>➤</button>
            </form>
        </main>
    </div>
    """ % (
        avatar_html(target["emoji"], target["avatar_data"], "head-avatar"),
        esc(target["username"]), body, esc(username)
    ))


@app.route("/private/<username>/send", methods=["POST"])
def private_send(username):
    u = me()
    if not u:
        return redirect("/")

    text = request.form.get("text", "").strip()
    if not text:
        return redirect("/private/%s" % username)

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username=%s AND banned=FALSE", (username,))
    target = cur.fetchone()

    if not target:
        cur.close()
        conn.close()
        return "کاربر پیدا نشد."

    cur.execute("""
        INSERT INTO private_messages(sender,receiver,text)
        VALUES(%s,%s,%s)
    """, (u["username"], username, text[:2000]))

    conn.commit()
    cur.close()
    conn.close()
    return redirect("/private/%s" % username)


# =========================================================
# REPLY / EDIT / DELETE
# =========================================================

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
        html = """
        <div class="box">
            <h2>↩️ پاسخ</h2>
            <div class="card">@%s<br>%s</div>
            <form method="post">
                <input name="text" maxlength="2000" placeholder="پاسخ..." required>
                <button>ارسال</button>
            </form>
            <a class="btn" href="/chat/%s">بازگشت</a>
        </div>
        """ % (esc(m["username"]), esc(m["text"]), m["room"])
        cur.close()
        conn.close()
        return page(html)

    text = request.form.get("text", "").strip()
    if text:
        cur.execute("""
            INSERT INTO messages(room,room_id,username,text,reply,edited)
            VALUES(%s,%s,%s,%s,%s,%s)
        """, (m["room"], m["room"], u["username"], text[:2000], mid, False))
        conn.commit()

    room = m["room"]
    cur.close()
    conn.close()
    return redirect("/chat/%s" % room)


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
        html = """
        <div class="box">
            <h2>✏️ ویرایش پیام</h2>
            <form method="post">
                <textarea name="text" maxlength="2000" required>%s</textarea>
                <button>ذخیره</button>
            </form>
            <a class="btn" href="/chat/%s">بازگشت</a>
        </div>
        """ % (esc(m["text"]), m["room"])
        cur.close()
        conn.close()
        return page(html)

    text = request.form.get("text", "").strip()
    if not text:
        cur.close()
        conn.close()
        return "متن نمی‌تواند خالی باشد."

    cur.execute(
        "UPDATE messages SET text=%s,edited=TRUE WHERE id=%s",
        (text[:2000], mid)
    )
    conn.commit()

    room = m["room"]
    cur.close()
    conn.close()
    return redirect("/chat/%s" % room)


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

    cur.execute("DELETE FROM messages WHERE id=%s", (mid,))
    conn.commit()

    room = m["room"]
    cur.close()
    conn.close()
    return redirect("/chat/%s" % room)


# =========================================================
# ADMIN
# =========================================================

@app.route("/admin")
def admin():
    u = me()
    if not u:
        return redirect("/")
    if not u["admin"]:
        return "دسترسی غیرمجاز."

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM users")
    user_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM rooms")
    room_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM messages")
    msg_count = cur.fetchone()["c"]

    cur.execute("SELECT * FROM users ORDER BY id DESC")
    users = cur.fetchall()

    cur.execute("SELECT * FROM rooms ORDER BY id DESC")
    rooms = cur.fetchall()

    cur.close()
    conn.close()

    user_cards = ""
    for x in users:
        action = ""
        if x["username"] != u["username"]:
            action = (
                "<a class='btn' href='/admin/unban-user/%s'>✅ رفع بن</a>"
                if x["banned"]
                else "<a class='btn danger' href='/admin/ban-user/%s'>🚫 بن</a>"
            ) % esc(x["username"])

        user_cards += """
        <div class="card">
            <b>@%s</b> %s<br>
            <span class="muted">%s</span><br>
            %s
        </div>
        """ % (
            esc(x["username"]),
            "<span class='tick'>ادمین</span>" if x["admin"] else "",
            esc(x["email"]), action
        )

    room_cards = ""
    for r in rooms:
        room_action = (
            "<a class='btn' href='/admin/unban-room/%s'>✅ رفع بن</a>"
            if r["banned"]
            else "<a class='btn danger' href='/admin/ban-room/%s'>🚫 بن</a>"
        ) % r["id"]

        delete_action = ""
        if r["username"] != "parto":
            delete_action = "<a class='btn danger' href='/admin/delete-room/%s'>🗑️ حذف</a>" % r["id"]

        room_cards += """
        <div class="card">
            %s
            <b>%s</b>
            <span class="muted">@%s · %s</span><br>
            %s %s
        </div>
        """ % (
            avatar_html(r["emoji"], r["avatar_data"], "room-avatar"),
            esc(r["name"]), esc(r["username"]),
            "کانال" if r["kind"] == "channel" else "گروه",
            room_action, delete_action
        )

    return page("""
    <div class="box">
        <div class="admin-title">👑 پنل مدیریت پرتو</div>

        <div class="admin-grid">
            <div class="stat"><b>%s</b>کاربر</div>
            <div class="stat"><b>%s</b>گروه/کانال</div>
            <div class="stat"><b>%s</b>پیام</div>
            <div class="stat"><b>✓</b>آنلاین</div>
        </div>

        <h3>👤 کاربران</h3>
        %s

        <h3>📢 گروه‌ها و کانال‌ها</h3>
        %s

        <a class="btn" href="/chat">← بازگشت به چت</a>
        <a class="btn" href="/logout">🚪 خروج</a>
    </div>
    """ % (user_count, room_count, msg_count, user_cards, room_cards))


def admin_only():
    u = me()
    if not u:
        return None, redirect("/")
    if not u["admin"]:
        return None, ("دسترسی غیرمجاز.", 403)
    return u, None


@app.route("/admin/ban-user/<username>")
def admin_ban_user(username):
    u, err = admin_only()
    if err:
        return err

    if username == u["username"]:
        return "نمی‌توانی خودت را بن کنی."

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET banned=TRUE WHERE username=%s", (username,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/admin/unban-user/<username>")
def admin_unban_user(username):
    u, err = admin_only()
    if err:
        return err

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET banned=FALSE WHERE username=%s", (username,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/admin/ban-room/<int:rid>")
def admin_ban_room(rid):
    u, err = admin_only()
    if err:
        return err

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT username FROM rooms WHERE id=%s", (rid,))
    room = cur.fetchone()
    if room and room["username"] == "parto":
        cur.close()
        conn.close()
        return "کانال رسمی پرتو قابل بن نیست."

    cur.execute("UPDATE rooms SET banned=TRUE WHERE id=%s", (rid,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/admin/unban-room/<int:rid>")
def admin_unban_room(rid):
    u, err = admin_only()
    if err:
        return err

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE rooms SET banned=FALSE WHERE id=%s", (rid,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/admin/delete-room/<int:rid>")
def admin_delete_room(rid):
    u, err = admin_only()
    if err:
        return err

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT username FROM rooms WHERE id=%s", (rid,))
    room = cur.fetchone()

    if not room:
        cur.close()
        conn.close()
        return "اتاق پیدا نشد."

    if room["username"] == "parto":
        cur.close()
        conn.close()
        return "کانال رسمی قابل حذف نیست."

    cur.execute("DELETE FROM messages WHERE room=%s", (rid,))
    cur.execute("DELETE FROM rooms WHERE id=%s", (rid,))
    conn.commit()

    cur.close()
    conn.close()
    return redirect("/admin")


# =========================================================
# STARTUP
# =========================================================

try:
    init_db()
except Exception as e:
    print("DATABASE INIT ERROR:", repr(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
