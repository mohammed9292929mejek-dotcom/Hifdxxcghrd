import os
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "PARTO_2026_CHANGE_THIS")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "parto.db")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            emoji TEXT DEFAULT '👤',
            bio TEXT DEFAULT '',
            admin INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('group','channel')),
            owner TEXT NOT NULL,
            emoji TEXT DEFAULT '👥',
            bio TEXT DEFAULT '',
            banned INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room INTEGER NOT NULL,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            image_url TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            reply INTEGER DEFAULT 0,
            edited INTEGER DEFAULT 0,
            FOREIGN KEY(room) REFERENCES rooms(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS private_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Admin default
    cur.execute("SELECT id FROM users WHERE username=?", ("parto",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users
            (username,email,password,emoji,bio,admin,banned)
            VALUES (?,?,?,?,?,?,?)
        """, (
            "parto",
            "parto@local",
            generate_password_hash("123456"),
            "⚡",
            "مدیر رسمی پرتو",
            1,
            0
        ))

    # Official channel
    cur.execute("SELECT id FROM rooms WHERE username=?", ("parto",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO rooms
            (name,username,kind,owner,emoji,bio,banned)
            VALUES (?,?,?,?,?,?,?)
        """, (
            "پرتو",
            "parto",
            "channel",
            "parto",
            "⚡",
            "کانال رسمی پرتو",
            0
        ))

    conn.commit()
    conn.close()


def me():
    username = session.get("user")
    if not username:
        return None
    conn = db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=?", (username,)
    ).fetchone()
    conn.close()
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


CSS = r"""
*{box-sizing:border-box}
:root{--bg:#07101d;--panel:#0d1726;--panel2:#111f31;--line:#23344c;--text:#f5f7fb;--muted:#91a0b6;--accent:#735cff}
html,body{margin:0;min-height:100%;background:radial-gradient(circle at 15% 0,#1a2860 0,transparent 32%),radial-gradient(circle at 100% 30%,#06495b 0,transparent 28%),var(--bg);color:var(--text);font-family:Tahoma,Arial,sans-serif;direction:rtl}
body{min-height:100vh}a{color:var(--text);text-decoration:none}
.app{min-height:100vh;display:flex}
.sidebar{width:88px;background:rgba(10,18,31,.9);border-left:1px solid var(--line);flex-shrink:0;overflow:auto}
.sidebar a{display:block;text-align:center;padding:14px 3px;border-bottom:1px solid rgba(255,255,255,.04);font-size:11px;color:#d4dbea}
.sidebar a:hover{background:rgba(115,92,255,.16)}
.main{height:100vh;flex:1;min-width:0;display:flex;flex-direction:column}
.top{padding:14px 17px;background:rgba(10,18,31,.9);border-bottom:1px solid var(--line);font-size:17px;font-weight:bold}
.content{flex:1;overflow:auto;padding:14px}
.msg{max-width:min(82%,600px);background:#122035;border:1px solid rgba(255,255,255,.05);border-radius:18px;padding:10px 13px;margin:8px 0;line-height:1.8;word-break:break-word}
.mine{margin-right:auto;background:linear-gradient(135deg,#263f7d,#2b315f)}
.msg .meta{font-size:11px;color:#9aa9bf}
.reply{background:#0c1625;border-right:3px solid var(--accent);padding:7px 10px;border-radius:10px;font-size:12px;margin-bottom:7px}
.composer{display:flex;gap:7px;padding:9px;background:rgba(10,18,31,.96);border-top:1px solid var(--line)}
.composer input{flex:1;margin:0}.composer button{width:58px;margin:0}
input,textarea,select,button{width:100%;padding:12px;border-radius:12px;border:1px solid transparent;font:inherit;margin:6px 0}
input,textarea,select{background:#101d2f;color:#fff;outline:none}
input:focus,textarea:focus,select:focus{border-color:var(--accent)}
button{background:linear-gradient(135deg,#735cff,#557cff);color:#fff;font-weight:bold;cursor:pointer}
.box{width:92%;max-width:560px;margin:25px auto;background:rgba(11,20,34,.94);border:1px solid var(--line);padding:22px;border-radius:22px;box-shadow:0 20px 70px rgba(0,0,0,.35)}
.avatar{text-align:center;font-size:62px}.muted{color:var(--muted);font-size:12px}
.card{background:#111f31;border:1px solid var(--line);padding:12px;border-radius:14px;margin:8px 0}
.tick{background:linear-gradient(135deg,#ffd43b,#ffad1f);color:#171207;border-radius:20px;padding:3px 8px;font-size:11px}
.room-card{display:flex;align-items:center;gap:12px;background:#111f31;border:1px solid var(--line);padding:13px;border-radius:16px;margin:8px 0}
.room-card .emoji{font-size:32px}.room-card small{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.stat{background:#111f31;border:1px solid var(--line);padding:14px;border-radius:14px;text-align:center}.stat b{display:block;font-size:22px}
.admin-danger{color:#ff7777}
@media(max-width:600px){.sidebar{width:72px}.sidebar a{font-size:10px;padding:12px 2px}.content{padding:9px}.msg{max-width:93%}.box{margin:15px auto;padding:17px}}
"""


def page(body, title="پرتو"):
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>{body}</body>
</html>"""


@app.before_request
def startup():
    # SQLite is local; no DATABASE_URL is needed.
    init_db()


@app.route("/")
def home():
    if me():
        return redirect("/chat")
    return page("""
    <div class="box">
      <div class="avatar">⚡</div>
      <h1>پرتو</h1>
      <p class="muted">پیام‌رسان وب پرتو</p>
      <form method="post" action="/login">
        <input name="email" type="email" placeholder="ایمیل" required>
        <input name="password" type="password" placeholder="رمز عبور" required>
        <button>ورود</button>
      </form>
      <a href="/register">ساخت حساب جدید</a>
    </div>
    """)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return page("""
        <div class="box">
          <h2>ثبت‌نام</h2>
          <form method="post">
            <input name="username" placeholder="آیدی" minlength="3" maxlength="40" required>
            <input name="email" type="email" placeholder="ایمیل" maxlength="120" required>
            <input name="password" type="password" placeholder="رمز عبور" minlength="6" required>
            <button>ساخت حساب</button>
          </form>
          <a href="/">بازگشت</a>
        </div>
        """)
    username = request.form.get("username","").strip()
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    if len(username) < 3:
        return "آیدی حداقل ۳ کاراکتر باشد."
    if len(password) < 6:
        return "رمز حداقل ۶ کاراکتر باشد."
    conn = db()
    try:
        conn.execute(
            "INSERT INTO users(username,email,password) VALUES(?,?,?)",
            (username,email,generate_password_hash(password))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "آیدی یا ایمیل قبلاً استفاده شده."
    conn.close()
    session["user"] = username
    return redirect("/chat")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect("/")
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if not user:
        return "کاربر پیدا نشد."
    if user["banned"]:
        return "حساب شما مسدود است."
    if not check_password_hash(user["password"], password):
        return "رمز عبور اشتباه است."
    session["user"] = user["username"]
    return redirect("/chat")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/health")
def health():
    try:
        conn = db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return {"status":"ok","database":"sqlite"}
    except Exception as e:
        return {"status":"error","database":"sqlite","error":str(e)},500


@app.route("/chat")
def chat():
    user = me()
    if not user:
        return redirect("/")

    conn = db()
    rooms = conn.execute(
        "SELECT * FROM rooms WHERE banned=0 ORDER BY id"
    ).fetchall()

    rid = request.args.get("room", type=int)
    room = None
    for r in rooms:
        if r["id"] == rid:
            room = r
            break
    if room is None and rooms:
        room = rooms[0]

    if room is None:
        conn.close()
        return "هنوز هیچ گروه یا کانالی وجود ندارد."

    messages = conn.execute("""
        SELECT m.*, u.emoji
        FROM messages m
        LEFT JOIN users u ON u.username=m.username
        WHERE m.room=?
        ORDER BY m.id
    """, (room["id"],)).fetchall()

    menu = ""
    for r in rooms:
        menu += f"""<a href="/chat?room={r['id']}">
        {esc(r['emoji'])}<br>{esc(r['name'])}
        </a>"""

    body = ""
    for m in messages:
        cls = "msg mine" if m["username"] == user["username"] else "msg"
        reply_html = ""
        if m["reply"]:
            old = conn.execute(
                "SELECT username,text FROM messages WHERE id=?",
                (m["reply"],)
            ).fetchone()
            if old:
                reply_html = f"""<div class="reply">↩️ @{esc(old['username'])}<br>{esc(old['text'])}</div>"""

        actions = f"""<a href="/reply/{m['id']}">↩️</a>"""
        if m["username"] == user["username"] or user["admin"]:
            actions += f"""　<a href="/edit/{m['id']}">✏️</a>
            <a href="/delete/{m['id']}">🗑️</a>"""

        image = ""
        if m["image_url"]:
            image = f"""<br><img src="{esc(m['image_url'])}" style="max-width:100%;border-radius:12px;margin-top:7px">"""

        body += f"""
        <div class="{cls}">
          {reply_html}
          <a href="/profile/{esc(m['username'])}">@{esc(m['username'])}</a><br>
          {esc(m['text'])}{image}
          {" ✏️" if m["edited"] else ""}
          <div class="meta">{esc(m["created_at"])}　{actions}</div>
        </div>
        """

    composer = ""
    if room["kind"] == "group" or room["owner"] == user["username"] or user["admin"]:
        composer = f"""
        <form class="composer" method="post" action="/send/{room['id']}">
          <input name="text" maxlength="2000" placeholder="پیام..." required>
          <button>➤</button>
        </form>
        """

    admin = '<a href="/admin">👑<br>ادمین</a>' if user["admin"] else ""

    html = f"""
    <div class="app">
      <aside class="sidebar">
        {menu}
        <a href="/profile/{esc(user['username'])}">👤<br>پروفایل</a>
        <a href="/create">➕<br>ساخت</a>
        {admin}
        <a href="/logout">🚪<br>خروج</a>
      </aside>
      <main class="main">
        <div class="top">{esc(room['emoji'])} {esc(room['name'])}
          {" <span class='tick'>✓</span>" if room["username"]=="parto" else ""}
        </div>
        <div class="content">{body}</div>
        {composer}
      </main>
    </div>
    """
    conn.close()
    return page(html, room["name"])


@app.route("/send/<int:rid>", methods=["POST"])
def send(rid):
    user = me()
    if not user:
        return redirect("/")
    conn = db()
    room = conn.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
    if not room or room["banned"]:
        conn.close()
        return "این اتاق در دسترس نیست."
    if room["kind"] == "channel" and room["owner"] != user["username"] and not user["admin"]:
        conn.close()
        return "فقط مالک کانال می‌تواند پیام ارسال کند."
    text = request.form.get("text","").strip()
    if text:
        conn.execute("""
            INSERT INTO messages(room,username,text,created_at)
            VALUES(?,?,?,?)
        """, (rid,user["username"],text[:2000],datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    conn.close()
    return redirect(f"/chat?room={rid}")


@app.route("/reply/<int:mid>", methods=["GET","POST"])
def reply(mid):
    user = me()
    if not user:
        return redirect("/")
    conn = db()
    msg = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    if not msg:
        conn.close()
        return "پیام پیدا نشد."
    if request.method == "GET":
        html = f"""
        <div class="box">
          <h2>↩️ پاسخ</h2>
          <div class="card">{esc(msg['text'])}</div>
          <form method="post">
            <input name="text" maxlength="2000" placeholder="پاسخ..." required>
            <button>ارسال</button>
          </form>
        </div>
        """
        conn.close()
        return page(html)
    text = request.form.get("text","").strip()
    if text:
        conn.execute("""
            INSERT INTO messages(room,username,text,created_at,reply)
            VALUES(?,?,?,?,?)
        """, (msg["room"],user["username"],text[:2000],
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"),mid))
        conn.commit()
    room = msg["room"]
    conn.close()
    return redirect(f"/chat?room={room}")


@app.route("/edit/<int:mid>", methods=["GET","POST"])
def edit(mid):
    user = me()
    if not user:
        return redirect("/")
    conn = db()
    msg = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    if not msg:
        conn.close()
        return "پیام پیدا نشد."
    if msg["username"] != user["username"] and not user["admin"]:
        conn.close()
        return "اجازه ویرایش ندارید."
    if request.method == "GET":
        html = f"""
        <div class="box">
          <h2>✏️ ویرایش</h2>
          <form method="post">
            <textarea name="text" maxlength="2000" required>{esc(msg['text'])}</textarea>
            <button>ذخیره</button>
          </form>
        </div>
        """
        conn.close()
        return page(html)
    text = request.form.get("text","").strip()
    if not text:
        conn.close()
        return "متن خالی است."
    conn.execute(
        "UPDATE messages SET text=?,edited=1 WHERE id=?",
        (text[:2000],mid)
    )
    conn.commit()
    room = msg["room"]
    conn.close()
    return redirect(f"/chat?room={room}")


@app.route("/delete/<int:mid>")
def delete(mid):
    user = me()
    if not user:
        return redirect("/")
    conn = db()
    msg = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    if not msg:
        conn.close()
        return "پیام پیدا نشد."
    if msg["username"] != user["username"] and not user["admin"]:
        conn.close()
        return "اجازه حذف ندارید."
    room = msg["room"]
    conn.execute("DELETE FROM messages WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return redirect(f"/chat?room={room}")


@app.route("/profile/<username>")
def profile(username):
    user = me()
    if not user:
        return redirect("/")
    conn = db()
    target = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not target:
        return "کاربر پیدا نشد."
    tick = "<span class='tick'>✓ تأیید شده</span>" if target["admin"] else ""
    edit = "<br><a href='/editprofile'>⚙️ ویرایش پروفایل</a>" if user["username"] == username else ""
    return page(f"""
    <div class="box">
      <div class="avatar">{esc(target['emoji'])}</div>
      <h2>@{esc(target['username'])} {tick}</h2>
      <p>{esc(target['bio'] or 'بدون بیو')}</p>
      <a href="/private/{esc(target['username'])}">💬 پیام خصوصی</a>
      {edit}
      <br><br><a href="/chat">بازگشت</a>
    </div>
    """)


@app.route("/editprofile", methods=["GET","POST"])
def editprofile():
    user = me()
    if not user:
        return redirect("/")
    if request.method == "GET":
        return page("""
        <div class="box">
          <h2>👤 ویرایش پروفایل</h2>
          <form method="post">
            <select name="emoji">
              <option>👤</option><option>👻</option><option>😎</option>
              <option>⚡</option><option>💻</option><option>🕷️</option>
              <option>☠️</option><option>🤖</option><option>🔥</option>
            </select>
            <textarea name="bio" maxlength="200" placeholder="بیوگرافی"></textarea>
            <button>ذخیره</button>
          </form>
          <a href="/chat">بازگشت</a>
        </div>
        """)
    conn = db()
    conn.execute(
        "UPDATE users SET emoji=?,bio=? WHERE username=?",
        (request.form.get("emoji","👤"),request.form.get("bio","")[:200],user["username"])
    )
    conn.commit()
    conn.close()
    return redirect(f"/profile/{user['username']}")


@app.route("/private/<username>")
def private(username):
    user = me()
    if not user:
        return redirect("/")
    conn = db()
    target = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not target:
        conn.close()
        return "کاربر پیدا نشد."
    messages = conn.execute("""
        SELECT * FROM private_messages
        WHERE (sender=? AND receiver=?)
           OR (sender=? AND receiver=?)
        ORDER BY id
    """, (user["username"],username,username,user["username"])).fetchall()
    conn.close()

    body = ""
    for m in messages:
        cls = "msg mine" if m["sender"] == user["username"] else "msg"
        body += f"""<div class="{cls}"><b>@{esc(m['sender'])}</b><br>{esc(m['text'])}</div>"""

    return page(f"""
    <div class="app">
      <main class="main">
        <div class="top">{esc(target['emoji'])} @{esc(target['username'])}</div>
        <div class="content">{body}</div>
        <form class="composer" method="post" action="/private/{esc(username)}/send">
          <input name="text" maxlength="2000" placeholder="پیام خصوصی..." required>
          <button>➤</button>
        </form>
      </main>
    </div>
    """)


@app.route("/private/<username>/send", methods=["POST"])
def private_send(username):
    user = me()
    if not user:
        return redirect("/")
    conn = db()
    target = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if not target:
        conn.close()
        return "کاربر پیدا نشد."
    text = request.form.get("text","").strip()
    if text:
        conn.execute("""
            INSERT INTO private_messages(sender,receiver,text,created_at)
            VALUES(?,?,?,?)
        """, (user["username"],username,text[:2000],datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    conn.close()
    return redirect(f"/private/{username}")


@app.route("/create", methods=["GET","POST"])
def create():
    user = me()
    if not user:
        return redirect("/")
    if request.method == "GET":
        return page("""
        <div class="box">
          <h2>➕ ساخت گروه یا کانال</h2>
          <form method="post">
            <input name="name" maxlength="80" placeholder="نام" required>
            <input name="username" maxlength="40" placeholder="آیدی، مثل mychannel" required>
            <select name="kind">
              <option value="group">👥 گروه</option>
              <option value="channel">📢 کانال</option>
            </select>
            <select name="emoji">
              <option>👥</option><option>📢</option><option>⚡</option>
              <option>👻</option><option>💻</option><option>🤖</option>
            </select>
            <input name="bio" maxlength="200" placeholder="توضیح">
            <button>ساخت</button>
          </form>
          <a href="/chat">بازگشت</a>
        </div>
        """)
    name = request.form.get("name","").strip()
    username = request.form.get("username","").strip().lstrip("@")
    kind = request.form.get("kind","group")
    emoji = request.form.get("emoji","👥")
    bio = request.form.get("bio","")[:200]
    if len(username) < 3:
        return "آیدی حداقل ۳ کاراکتر باشد."
    conn = db()
    try:
        conn.execute("""
            INSERT INTO rooms(name,username,kind,owner,emoji,bio)
            VALUES(?,?,?,?,?,?)
        """, (name[:80],username[:40],kind,user["username"],emoji,bio))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "این آیدی قبلاً استفاده شده."
    conn.close()
    return redirect("/chat")


@app.route("/admin")
def admin():
    user = me()
    if not user:
        return redirect("/")
    if not user["admin"]:
        return "دسترسی غیرمجاز."
    conn = db()
    users = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    rooms = conn.execute("SELECT * FROM rooms ORDER BY id").fetchall()
    conn.close()

    ucards = ""
    for x in users:
        action = ""
        if x["username"] != user["username"]:
            if x["banned"]:
                action = f"""<a href="/admin/user/unban/{esc(x['username'])}">✅ رفع مسدودی</a>"""
            else:
                action = f"""<a class="admin-danger" href="/admin/user/ban/{esc(x['username'])}">🚫 بن کاربر</a>"""
        ucards += f"""
        <div class="card">
          {esc(x['emoji'])} <b>@{esc(x['username'])}</b>
          {" ✓" if x["admin"] else ""}<br>
          <span class="muted">{esc(x['email'])}</span><br>{action}
        </div>
        """

    rcards = ""
    for r in rooms:
        action = ""
        if r["username"] != "parto":
            if r["banned"]:
                action = f"""<a href="/admin/room/unban/{r['id']}">✅ رفع بن</a>"""
            else:
                action = f"""<a class="admin-danger" href="/admin/room/ban/{r['id']}">🚫 بن {esc(r['kind'])}</a>"""
        rcards += f"""
        <div class="card">
          {esc(r['emoji'])} <b>{esc(r['name'])}</b>
          <span class="muted">@{esc(r['username'])} · {esc(r['kind'])}</span><br>
          {action}
        </div>
        """

    return page(f"""
    <div class="box">
      <div class="admin-title">👑 پنل مدیریت پرتو</div>
      <div class="grid">
        <div class="stat"><b>{len(users)}</b>کاربر</div>
        <div class="stat"><b>{len(rooms)}</b>گروه/کانال</div>
      </div>
      <h3>کاربران</h3>
      {ucards}
      <h3>گروه‌ها و کانال‌ها</h3>
      {rcards}
      <br><a href="/chat">بازگشت به چت</a>
    </div>
    """)


@app.route("/admin/user/ban/<username>")
def admin_user_ban(username):
    user = me()
    if not user or not user["admin"]:
        return "دسترسی غیرمجاز."
    if username == "parto":
        return "مدیر اصلی قابل بن نیست."
    conn = db()
    conn.execute("UPDATE users SET banned=1 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/admin/user/unban/<username>")
def admin_user_unban(username):
    user = me()
    if not user or not user["admin"]:
        return "دسترسی غیرمجاز."
    conn = db()
    conn.execute("UPDATE users SET banned=0 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/admin/room/ban/<int:rid>")
def admin_room_ban(rid):
    user = me()
    if not user or not user["admin"]:
        return "دسترسی غیرمجاز."
    conn = db()
    conn.execute("UPDATE rooms SET banned=1 WHERE id=? AND username!='parto'", (rid,))
    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/admin/room/unban/<int:rid>")
def admin_room_unban(rid):
    user = me()
    if not user or not user["admin"]:
        return "دسترسی غیرمجاز."
    conn = db()
    conn.execute("UPDATE rooms SET banned=0 WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return redirect("/admin")


# Initialize once at import time so Gunicorn sees a ready database.
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
