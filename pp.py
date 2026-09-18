import os
import html
import secrets
from datetime import datetime, timezone

import psycopg2
from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor
from flask import Flask, request, redirect, session, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-in-render")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE_URL = os.getenv("DATABASE_URL", "")

CSS = r"""
*{box-sizing:border-box}
:root{--bg:#070b14;--panel:#0d1422;--panel2:#111b2b;--line:#223047;--text:#f5f7fb;--muted:#8e9bb0;--accent:#7c5cff;--accent2:#00d4ff;--danger:#ff5577;--success:#36d399}
html,body{margin:0;min-height:100%;background:radial-gradient(circle at 15% 0%,#17245a 0,transparent 32%),radial-gradient(circle at 100% 30%,#073e55 0,transparent 28%),var(--bg);color:var(--text);font-family:Inter,Tahoma,Arial,sans-serif}
body{min-height:100vh}a{color:var(--text);text-decoration:none}
.app{min-height:100vh;display:flex;direction:ltr}
.sidebar{width:250px;background:rgba(13,20,34,.82);backdrop-filter:blur(18px);border-right:1px solid var(--line);padding:18px 12px;flex-shrink:0}
.brand{display:flex;align-items:center;gap:10px;font-size:24px;font-weight:900;padding:10px 12px 24px}
.brand-icon{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 10px 30px rgba(124,92,255,.25)}
.nav a{display:flex;align-items:center;gap:12px;padding:13px 14px;margin:5px 0;border-radius:14px;color:#cbd5e7;transition:.18s}
.nav a:hover,.nav a.active{background:rgba(124,92,255,.14);color:#fff}
.nav-icon{width:24px;text-align:center}
.main{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh;direction:ltr}
.head{padding:16px 20px;background:rgba(13,20,34,.78);backdrop-filter:blur(18px);border-bottom:1px solid var(--line);font-size:18px;font-weight:800;direction:ltr}
.content{flex:1;overflow:auto;padding:20px;direction:ltr}
.card{background:rgba(17,27,43,.92);border:1px solid rgba(255,255,255,.06);padding:15px;margin:10px 0;border-radius:18px;box-shadow:0 10px 30px rgba(0,0,0,.12)}
.box{width:92%;max-width:560px;margin:45px auto;background:rgba(13,20,34,.9);border:1px solid var(--line);backdrop-filter:blur(20px);padding:26px;border-radius:26px;box-shadow:0 20px 70px rgba(0,0,0,.35)}
input,textarea,select,button{width:100%;padding:12px 14px;margin:6px 0;border:1px solid transparent;border-radius:12px;font:inherit}
input,textarea,select{background:#111c2d;color:#fff;outline:none}
input:focus,textarea:focus,select:focus{border-color:var(--accent)}
button,.btn{background:linear-gradient(135deg,var(--accent),#5a7cff);color:#fff;font-weight:800;cursor:pointer;border:0;display:inline-block;text-align:center}
.btn.secondary{background:#182138;border:1px solid var(--line)}
.btn.danger{background:linear-gradient(135deg,#ff5577,#d93662)}
.btn.small{width:auto;padding:8px 11px;border-radius:10px}
.avatar{font-size:64px;text-align:center}
.muted{color:var(--muted)}
.badge{display:inline-block;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:800;margin-left:5px}
.verified{background:#38a0ff;color:white}.pro{background:linear-gradient(135deg,#ffcc33,#ff7a18);color:#17100a}
.notice{padding:12px 14px;border-radius:13px;background:rgba(54,211,153,.09);border:1px solid rgba(54,211,153,.2);margin:10px 0}
.error{background:rgba(255,85,119,.1);border-color:rgba(255,85,119,.25)}
.actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.chatgrid{display:flex;height:100vh;direction:ltr}
.rooms{width:290px;padding:14px;background:rgba(8,11,22,.74);border-right:1px solid var(--line);backdrop-filter:blur(25px);overflow:auto;flex-shrink:0}
.roomtitle{font-size:20px;font-weight:900;padding:12px 10px 18px}
.room{display:flex;gap:11px;align-items:center;padding:11px;border-radius:17px;margin:5px 0;color:#cbd4e6;transition:.18s}
.room:hover,.room.active{background:rgba(77,124,255,.14);color:white}
.room-icon{font-size:29px}.room b{display:block}.room small,.top small{display:block;font-size:11px;color:#8e99ad}
.chat{min-width:0;flex:1;display:flex;flex-direction:column;direction:ltr}
.top{display:flex;align-items:center;gap:11px;padding:14px 18px;border-bottom:1px solid var(--line);background:rgba(13,20,34,.78);backdrop-filter:blur(18px)}
.top .status{margin-left:auto;color:var(--success);font-size:12px}
.bigavatar{font-size:31px}
.messages{flex:1;overflow:auto;padding:18px}
.msg{background:rgba(17,27,43,.92);border:1px solid rgba(255,255,255,.05);padding:11px 13px;margin:9px 0;border-radius:17px;max-width:min(86%,560px);box-shadow:0 8px 22px rgba(0,0,0,.12);line-height:1.8;word-wrap:break-word}
.mine{margin-left:auto;background:linear-gradient(135deg,#263f7c,#29325f);border-color:rgba(124,92,255,.3)}
.meta{font-size:12px;color:#9facbf}.msgtext{white-space:pre-wrap}
.msg-actions{display:flex;gap:8px;margin-top:5px;font-size:12px}.msg-actions a{color:#b9c5d8}
.composer{display:flex;gap:8px;padding:10px;background:rgba(13,20,34,.9);border-top:1px solid var(--line);backdrop-filter:blur(18px)}
.composer input{flex:1;margin:0;border-radius:24px}.composer button{width:58px;margin:0;border-radius:20px}
.profile-card{max-width:620px;margin:35px auto;text-align:center;overflow:hidden;border:1px solid var(--line);border-radius:30px;background:rgba(14,18,32,.8);backdrop-filter:blur(28px);box-shadow:0 25px 90px rgba(0,0,0,.35)}
.profile-cover{height:135px;background:linear-gradient(120deg,#4d7cff,#865cff,#24d9ff)}
.profile-avatar{width:105px;height:105px;margin:-48px auto 12px;border-radius:30px;display:flex;align-items:center;justify-content:center;font-size:52px;background:#11182c;border:4px solid #11182c;box-shadow:0 15px 35px rgba(0,0,0,.3)}
.profile-actions{display:flex;justify-content:center;gap:9px;padding:15px 20px 25px;flex-wrap:wrap}
.profile-actions a{padding:11px 16px;border-radius:14px}
.search{display:flex;gap:8px}.search input{flex:1}.search button{width:100px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.kpi{padding:16px;border:1px solid var(--line);background:#111c2d;border-radius:17px}.kpi b{font-size:24px}
.table-wrap{overflow:auto}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.rtl{direction:rtl;text-align:right}
.rtl .sidebar{border-right:0;border-left:1px solid var(--line)}.rtl .app{direction:rtl}.rtl .main,.rtl .head,.rtl .content,.rtl .chat,.rtl .chatgrid{direction:rtl}.rtl .rooms{border-right:0;border-left:1px solid var(--line)}.rtl .room,.rtl .top{direction:rtl}.rtl .top .status{margin-left:0;margin-right:auto}.rtl .msg.mine{margin-right:auto;margin-left:0}.rtl .msg-actions{direction:rtl}
@media(max-width:760px){.sidebar{width:76px;padding:10px 6px}.brand{justify-content:center;padding:8px 4px 16px}.brand-text,.nav-label{display:none}.nav a{justify-content:center;padding:12px 5px}.rooms{width:78px;padding:7px}.room{justify-content:center;padding:10px}.room div{display:none}.roomtitle{font-size:0}.roomtitle:first-letter{font-size:25px}.content{padding:12px}.messages{padding:10px}.msg{max-width:92%}.box{margin:18px auto;padding:18px}}
"""

TEXT = {
    "en": {
        "app":"Parto","login":"Login","register":"Register","logout":"Logout","profile":"Profile",
        "chat":"Chats","groups":"Groups","channels":"Channels","search":"Search","settings":"Settings",
        "admin":"Admin","create":"Create","private":"Private Chat","username":"Username","email":"Email",
        "password":"Password","bio":"Bio","save":"Save","message":"Message...","send":"Send",
        "reply":"Reply","edit":"Edit","delete":"Delete","online":"Online","language":"Language",
        "english":"English","persian":"Persian / فارسی","welcome":"Welcome to Parto",
        "create_room":"Create group or channel","name":"Name","type":"Type","group":"Group","channel":"Channel",
        "description":"Description","search_users":"Search users and rooms","no_results":"No results.",
        "admin_users":"Users","admin_rooms":"Rooms","ban":"Ban / Unban","verified":"Verified","pro":"PRO",
        "account_saved":"Settings saved.","wrong_login":"Invalid email or password.","not_found":"Not found.",
        "forbidden":"Access denied.","banned":"Your account is banned.","duplicate":"Username or email is already in use.",
        "room_duplicate":"That room username is already in use.","min_password":"Password must be at least 6 characters.",
        "min_username":"Username must be at least 3 characters.","owner_only":"Only the channel owner can post.",
        "permission":"You do not have permission.","created":"Created successfully."
    },
    "fa": {
        "app":"پرتو","login":"ورود","register":"ثبت‌نام","logout":"خروج","profile":"پروفایل",
        "chat":"گفت‌وگوها","groups":"گروه‌ها","channels":"کانال‌ها","search":"جستجو","settings":"تنظیمات",
        "admin":"مدیریت","create":"ساختن","private":"چت خصوصی","username":"نام کاربری","email":"ایمیل",
        "password":"رمز عبور","bio":"بیو","save":"ذخیره","message":"پیام...","send":"ارسال",
        "reply":"پاسخ","edit":"ویرایش","delete":"حذف","online":"آنلاین","language":"زبان",
        "english":"English","persian":"فارسی","welcome":"به پرتو خوش آمدید",
        "create_room":"ساخت گروه یا کانال","name":"نام","type":"نوع","group":"گروه","channel":"کانال",
        "description":"توضیحات","search_users":"جستجوی کاربران و اتاق‌ها","no_results":"نتیجه‌ای پیدا نشد.",
        "admin_users":"کاربران","admin_rooms":"اتاق‌ها","ban":"بن / رفع بن","verified":"تأییدشده","pro":"PRO",
        "account_saved":"تنظیمات ذخیره شد.","wrong_login":"ایمیل یا رمز عبور نادرست است.","not_found":"پیدا نشد.",
        "forbidden":"دسترسی غیرمجاز.","banned":"حساب شما مسدود است.","duplicate":"نام کاربری یا ایمیل قبلاً استفاده شده است.",
        "room_duplicate":"این آیدی اتاق قبلاً استفاده شده است.","min_password":"رمز عبور باید حداقل ۶ کاراکتر باشد.",
        "min_username":"نام کاربری باید حداقل ۳ کاراکتر باشد.","owner_only":"فقط مالک کانال می‌تواند پیام ارسال کند.",
        "permission":"اجازه انجام این کار را ندارید.","created":"با موفقیت ساخته شد."
    }
}

def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)

def q(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description:
            return cur.fetchall()
        return []

def one(conn, sql, params=()):
    rows = q(conn, sql, params)
    return rows[0] if rows else None

def safe(value):
    return html.escape(str(value or ""), quote=True)

def lang_for(user):
    return "fa" if user and user.get("language") == "fa" else "en"

def t(key, user=None):
    return TEXT[lang_for(user)].get(key, key)

def current_user():
    username = session.get("user")
    if not username:
        return None
    conn = db()
    user = one(conn, "SELECT * FROM users WHERE username=%s", (username,))
    conn.close()
    if not user:
        session.clear()
        return None
    return user

def init_db():
    conn = db()
    # Existing tables are preserved. CREATE IF NOT EXISTS only creates missing tables.
    q(conn, """CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE,
        password TEXT NOT NULL,
        emoji TEXT DEFAULT '👤',
        bio TEXT DEFAULT '',
        admin INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0
    )""")
    q(conn, """CREATE TABLE IF NOT EXISTS rooms(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        kind TEXT NOT NULL,
        owner TEXT NOT NULL,
        emoji TEXT DEFAULT '👥',
        bio TEXT DEFAULT ''
    )""")
    q(conn, """CREATE TABLE IF NOT EXISTS messages(
        id SERIAL PRIMARY KEY,
        room INTEGER,
        room_id INTEGER,
        username TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT DEFAULT '',
        created TEXT DEFAULT '',
        reply INTEGER DEFAULT 0,
        edited INTEGER DEFAULT 0
    )""")
    q(conn, """CREATE TABLE IF NOT EXISTS private_messages(
        id SERIAL PRIMARY KEY,
        sender TEXT NOT NULL,
        receiver TEXT NOT NULL,
        text TEXT NOT NULL
    )""")

    def columns(table):
        rows = q(conn, """SELECT column_name FROM information_schema.columns
                          WHERE table_schema='public' AND table_name=%s""", (table,))
        return {r["column_name"] for r in rows}

    user_cols = columns("users")
    migrations = {
        "users": {
            "language": "TEXT DEFAULT 'en'",
            "verified": "INTEGER DEFAULT 0",
            "pro": "INTEGER DEFAULT 0",
            "avatar": "TEXT DEFAULT ''"
        },
        "rooms": {
            "created_at": "TEXT DEFAULT ''"
        },
        "messages": {
            "room": "INTEGER",
            "room_id": "INTEGER",
            "created_at": "TEXT DEFAULT ''",
            "created": "TEXT DEFAULT ''",
            "reply": "INTEGER DEFAULT 0",
            "edited": "INTEGER DEFAULT 0"
        }
    }
    for table, wanted in migrations.items():
        existing = user_cols if table == "users" else columns(table)
        for name, definition in wanted.items():
            if name not in existing:
                q(conn, f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')

    # Backfill only empty/new fields; no rows are deleted.
    q(conn, "UPDATE users SET language='en' WHERE language IS NULL OR language=''")
    q(conn, "UPDATE users SET verified=0 WHERE verified IS NULL")
    q(conn, "UPDATE users SET pro=0 WHERE pro IS NULL")
    q(conn, "UPDATE users SET avatar='' WHERE avatar IS NULL")
    q(conn, "UPDATE messages SET room=room_id WHERE room IS NULL AND room_id IS NOT NULL")
    q(conn, "UPDATE messages SET room_id=room WHERE room_id IS NULL AND room IS NOT NULL")
    q(conn, "UPDATE messages SET created_at=%s WHERE created_at IS NULL OR created_at=''",
      (datetime.now(timezone.utc).isoformat(timespec="seconds"),))
    q(conn, "UPDATE messages SET created=created_at WHERE created IS NULL OR created=''")

    # Preserve the original default Parto account/channel if they do not already exist.
    if not one(conn, "SELECT id FROM users WHERE username='parto'"):
        q(conn, """INSERT INTO users(username,email,password,emoji,bio,admin,language,verified,pro,avatar)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
          ("parto","parto@local",generate_password_hash("123456"),"⚡","Official Parto",1,"en",1,1,"⚡"))
    if not one(conn, "SELECT id FROM rooms WHERE username='parto'"):
        q(conn, """INSERT INTO rooms(name,username,kind,owner,emoji,bio,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
          ("Parto","parto","channel","parto","⚡","Official Parto channel",
           datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()
    conn.close()

def page(title, body, user=None, bare=False):
    direction = "rtl" if lang_for(user) == "fa" else "ltr"
    cls = "rtl" if direction == "rtl" else ""
    if bare:
        return f"""<!doctype html><html lang="{direction}"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>{safe(title)} · Parto</title><style>{CSS}</style></head><body class="{cls}">{body}</body></html>"""
    return f"""<!doctype html><html lang="{direction}"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{safe(title)} · Parto</title><style>{CSS}</style></head><body class="{cls}">
    <div class="app"><aside class="sidebar">
      <div class="brand"><span class="brand-icon">⚡</span><span class="brand-text">Parto</span></div>
      <nav class="nav">
        <a href="/chat"><span class="nav-icon">⌂</span><span class="nav-label">{safe(t("chat",user))}</span></a>
        <a href="/search"><span class="nav-icon">⌕</span><span class="nav-label">{safe(t("search",user))}</span></a>
        <a href="/create"><span class="nav-icon">＋</span><span class="nav-label">{safe(t("create",user))}</span></a>
        <a href="/profile/{safe(user["username"])}"><span class="nav-icon">◉</span><span class="nav-label">{safe(t("profile",user))}</span></a>
        <a href="/settings"><span class="nav-icon">⚙</span><span class="nav-label">{safe(t("settings",user))}</span></a>
        {"<a href='/admin'><span class='nav-icon'>♛</span><span class='nav-label'>"+safe(t("admin",user))+"</span></a>" if user and user["admin"] else ""}
        <a href="/logout"><span class="nav-icon">↪</span><span class="nav-label">{safe(t("logout",user))}</span></a>
      </nav>
    </aside><main class="main"><header class="head">{safe(title)}</header>{body}</main></div>
    </body></html>"""

def require_user():
    user = current_user()
    if not user:
        return redirect("/")
    if user["banned"]:
        session.clear()
        return page("Parto", f'<div class="box"><h2>{safe(t("banned"))}</h2></div>', None, True)
    return user

@app.route("/")
def home():
    user = current_user()
    if user:
        return redirect("/chat")
    body = f"""<div class="box">
      <div class="avatar">⚡</div><h1>Parto</h1><p class="muted">{safe(TEXT["en"]["welcome"])}</p>
      <form method="post" action="/login">
        <input name="email" type="email" placeholder="{safe(TEXT["en"]["email"])}" required>
        <input name="password" type="password" placeholder="{safe(TEXT["en"]["password"])}" required>
        <button>{safe(TEXT["en"]["login"])}</button>
      </form>
      <p><a class="btn secondary" href="/register">{safe(TEXT["en"]["register"])}</a></p>
    </div>"""
    return page("Login", body, None, True)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "GET":
        return page("Register", f"""<div class="box"><h2>{safe(TEXT["en"]["register"])}</h2>
        <form method="post">
          <input name="username" placeholder="{safe(TEXT["en"]["username"])}" required>
          <input name="email" type="email" placeholder="{safe(TEXT["en"]["email"])}" required>
          <input name="password" type="password" placeholder="{safe(TEXT["en"]["password"])}" required>
          <button>{safe(TEXT["en"]["register"])}</button>
        </form><a href="/">{safe(TEXT["en"]["login"])}</a></div>""", None, True)
    username = request.form.get("username","").strip().lower()
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    if len(username) < 3:
        return page("Register", f'<div class="box"><div class="notice error">{safe(TEXT["en"]["min_username"])}</div></div>', None, True)
    if len(password) < 6:
        return page("Register", f'<div class="box"><div class="notice error">{safe(TEXT["en"]["min_password"])}</div></div>', None, True)
    conn = db()
    try:
        q(conn, "INSERT INTO users(username,email,password,language) VALUES(%s,%s,%s,'en')",
          (username,email,generate_password_hash(password)))
        conn.commit()
    except IntegrityError:
        conn.rollback(); conn.close()
        return page("Register", f'<div class="box"><div class="notice error">{safe(TEXT["en"]["duplicate"])}</div><a href="/register">Back</a></div>', None, True)
    conn.close()
    session["user"] = username
    return redirect("/chat")

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    conn = db(); user = one(conn, "SELECT * FROM users WHERE email=%s", (email,)); conn.close()
    if not user or not check_password_hash(user["password"], password):
        return page("Login", f'<div class="box"><div class="notice error">{safe(TEXT["en"]["wrong_login"])}</div><a href="/">Back</a></div>', None, True)
    if user["banned"]:
        return page("Login", f'<div class="box"><div class="notice error">{safe(TEXT["en"]["banned"])}</div></div>', None, True)
    session["user"] = user["username"]
    return redirect("/chat")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/chat")
def chat():
    user = require_user()
    if not isinstance(user, dict):
        return user
    rid = request.args.get("room", type=int)
    conn = db()
    rooms = q(conn, "SELECT * FROM rooms ORDER BY id ASC")
    room = one(conn, "SELECT * FROM rooms WHERE id=%s", (rid,)) if rid else (rooms[0] if rooms else None)
    if not room:
        conn.close()
        return page(t("chat",user), f'<div class="content"><div class="card">{safe(t("not_found",user))}</div></div>', user)
    messages = q(conn, "SELECT * FROM messages WHERE room=%s ORDER BY id ASC", (room["id"],))
    conn.close()
    room_cards = ""
    for r in rooms:
        active = " active" if r["id"] == room["id"] else ""
        room_cards += f"""<a class="room{active}" href="/chat?room={r["id"]}">
          <span class="room-icon">{safe(r["emoji"])}</span><div><b>{safe(r["name"])}</b><small>@{safe(r["username"])}</small></div>
        </a>"""
    body = ""
    for m in messages:
        mine = " mine" if m["username"] == user["username"] else ""
        edited = " · edited" if m["edited"] else ""
        reply_html = f'<div class="card"><small>Reply #{m["reply"]}</small></div>' if m["reply"] else ""
        actions = f'<a href="/reply/{m["id"]}">↩ {safe(t("reply",user))}</a>'
        if m["username"] == user["username"] or user["admin"]:
            actions += f' <a href="/edit/{m["id"]}">✎ {safe(t("edit",user))}</a> <a href="/delete/{m["id"]}">⌫ {safe(t("delete",user))}</a>'
        body += f"""<article class="msg{mine}"><div class="meta">@{safe(m["username"])}{edited}</div>
          {reply_html}<div class="msgtext">{safe(m["text"])}</div><div class="msg-actions">{actions}</div></article>"""
    composer = ""
    if room["kind"] == "group" or room["owner"] == user["username"]:
        composer = f"""<form class="composer" method="post" action="/send/{room["id"]}">
          <input name="text" placeholder="{safe(t("message",user))}" required maxlength="2000"><button>➤</button>
        </form>"""
    body_html = f"""<div class="chatgrid"><aside class="rooms"><div class="roomtitle">💬 {safe(t("app",user))}</div>{room_cards}</aside>
      <section class="chat"><div class="top"><span class="bigavatar">{safe(room["emoji"])}</span>
      <div><b>{safe(room["name"])}</b><small>@{safe(room["username"])}</small></div><span class="status">{safe(t("online",user))}</span></div>
      <div class="messages">{body or '<div class="card muted">No messages yet.</div>'}</div>{composer}</section></div>"""
    return page(room["name"], body_html, user)

@app.route("/send/<int:rid>", methods=["POST"])
def send(rid):
    user = require_user()
    if not isinstance(user, dict):
        return user
    text_value = request.form.get("text","").strip()[:2000]
    conn = db(); room = one(conn, "SELECT * FROM rooms WHERE id=%s", (rid,))
    if not room:
        conn.close(); abort(404)
    if room["kind"] == "channel" and room["owner"] != user["username"] and not user["admin"]:
        conn.close()
        return page(t("chat",user), f'<div class="box">{safe(t("owner_only",user))}</div>', user)
    if text_value:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        q(conn, """INSERT INTO messages(room,room_id,username,text,created_at,created,reply,edited)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
          (rid,rid,user["username"],text_value,now,now,0,0))
        conn.commit()
    conn.close()
    return redirect(url_for("chat", room=rid))

@app.route("/create", methods=["GET","POST"])
def create():
    user = require_user()
    if not isinstance(user, dict):
        return user
    if request.method == "GET":
        return page(t("create_room",user), f"""<div class="content"><div class="box">
        <h2>{safe(t("create_room",user))}</h2><form method="post">
        <input name="name" placeholder="{safe(t("name",user))}" required maxlength="80">
        <input name="username" placeholder="@username" required maxlength="40">
        <select name="kind"><option value="group">{safe(t("group",user))}</option><option value="channel">{safe(t("channel",user))}</option></select>
        <input name="emoji" value="👥" maxlength="8"><input name="bio" placeholder="{safe(t("description",user))}" maxlength="200">
        <button>{safe(t("create",user))}</button></form></div></div>""", user)
    conn = db()
    try:
        q(conn, """INSERT INTO rooms(name,username,kind,owner,emoji,bio,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
          (request.form.get("name","")[:80],request.form.get("username","").strip().lower()[:40],
           request.form.get("kind","group"),user["username"],request.form.get("emoji","👥")[:8],
           request.form.get("bio","")[:200],datetime.now(timezone.utc).isoformat(timespec="seconds")))
        conn.commit()
    except IntegrityError:
        conn.rollback(); conn.close()
        return page(t("create_room",user), f'<div class="box"><div class="notice error">{safe(t("room_duplicate",user))}</div></div>', user)
    conn.close()
    return redirect("/chat")

@app.route("/profile/<username>")
def profile(username):
    user = require_user()
    if not isinstance(user, dict):
        return user
    conn = db(); target = one(conn, "SELECT * FROM users WHERE username=%s", (username,)); conn.close()
    if not target:
        return page(t("profile",user), f'<div class="content"><div class="card">{safe(t("not_found",user))}</div></div>', user)
    badges = ""
    if target["verified"]: badges += f'<span class="badge verified">✓ {safe(t("verified",user))}</span>'
    if target["pro"]: badges += f'<span class="badge pro">{safe(t("pro",user))}</span>'
    own = target["username"] == user["username"]
    actions = f'<a class="btn secondary" href="/settings">{safe(t("settings",user))}</a>' if own else f'<a class="btn" href="/private/{safe(target["username"])}">{safe(t("private",user))}</a>'
    return page(t("profile",user), f"""<div class="content"><div class="profile-card">
      <div class="profile-cover"></div><div class="profile-avatar">{safe(target.get("avatar") or target.get("emoji") or "👤")}</div>
      <h1>@{safe(target["username"])} {badges}</h1><p class="muted">{safe(target["bio"] or "")}</p>
      <div class="profile-actions">{actions}</div></div></div>""", user)

@app.route("/settings", methods=["GET","POST"])
def settings():
    user = require_user()
    if not isinstance(user, dict):
        return user
    if request.method == "POST":
        language = request.form.get("language","en")
        if language not in ("en","fa"): language = "en"
        conn = db(); q(conn, "UPDATE users SET language=%s WHERE id=%s", (language,user["id"])); conn.commit(); conn.close()
        return redirect("/settings")
    user = current_user()
    selected = lang_for(user)
    return page(t("settings",user), f"""<div class="content"><div class="box">
      <h2>{safe(t("settings",user))}</h2><form method="post">
      <label>{safe(t("language",user))}</label><select name="language">
        <option value="en" {"selected" if selected=="en" else ""}>{safe(TEXT["en"]["english"])}</option>
        <option value="fa" {"selected" if selected=="fa" else ""}>{safe(TEXT["en"]["persian"])}</option>
      </select><button>{safe(t("save",user))}</button></form>
      <p class="muted">{safe(t("account_saved",user))}</p></div></div>""", user)

@app.route("/private/<username>")
def private(username):
    user = require_user()
    if not isinstance(user, dict): return user
    conn = db(); target = one(conn,"SELECT * FROM users WHERE username=%s",(username,))
    if not target:
        conn.close(); abort(404)
    messages = q(conn, """SELECT * FROM private_messages
        WHERE (sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s) ORDER BY id""",
        (user["username"],username,username,user["username"]))
    conn.close()
    body = ""
    for m in messages:
        mine = " mine" if m["sender"] == user["username"] else ""
        body += f'<div class="msg{mine}"><div class="meta">@{safe(m["sender"])}</div><div class="msgtext">{safe(m["text"])}</div></div>'
    return page(f"@{username}", f"""<div class="chatgrid"><section class="chat">
      <div class="top"><span class="bigavatar">{safe(target["emoji"])}</span><div><b>@{safe(target["username"])}</b></div></div>
      <div class="messages">{body or '<div class="card muted">No messages yet.</div>'}</div>
      <form class="composer" method="post" action="/private/{safe(username)}/send"><input name="text" placeholder="{safe(t("message",user))}" maxlength="2000" required><button>➤</button></form>
    </section></div>""", user)

@app.route("/private/<username>/send", methods=["POST"])
def private_send(username):
    user = require_user()
    if not isinstance(user, dict): return user
    text_value = request.form.get("text","").strip()[:2000]
    conn = db(); target = one(conn,"SELECT id FROM users WHERE username=%s",(username,))
    if not target: conn.close(); abort(404)
    if text_value:
        q(conn,"INSERT INTO private_messages(sender,receiver,text) VALUES(%s,%s,%s)",
          (user["username"],username,text_value)); conn.commit()
    conn.close(); return redirect(url_for("private",username=username))

@app.route("/search")
def search():
    user = require_user()
    if not isinstance(user, dict): return user
    term = request.args.get("q","").strip()[:80]
    conn = db()
    users = q(conn,"SELECT username,bio,emoji,verified,pro FROM users WHERE username ILIKE %s ORDER BY username LIMIT 30",(f"%{term}%",)) if term else []
    rooms = q(conn,"SELECT id,name,username,kind,emoji,bio FROM rooms WHERE name ILIKE %s OR username ILIKE %s ORDER BY id DESC LIMIT 30",(f"%{term}%",f"%{term}%")) if term else []
    conn.close()
    result = ""
    for x in users:
        result += f'<div class="card"><b>{safe(x["emoji"])} @{safe(x["username"])}</b><p class="muted">{safe(x["bio"])}</p><a class="btn small" href="/profile/{safe(x["username"])}">{safe(t("profile",user))}</a></div>'
    for r in rooms:
        result += f'<div class="card"><b>{safe(r["emoji"])} {safe(r["name"])}</b><p class="muted">@{safe(r["username"])} · {safe(r["kind"])}</p><a class="btn small" href="/chat?room={r["id"]}">{safe(t("chat",user))}</a></div>'
    if term and not result: result = f'<div class="card muted">{safe(t("no_results",user))}</div>'
    return page(t("search",user), f"""<div class="content"><div class="box" style="max-width:800px">
      <h2>{safe(t("search",user))}</h2><form class="search"><input name="q" value="{safe(term)}" placeholder="{safe(t("search_users",user))}"><button>{safe(t("search",user))}</button></form></div>
      <div style="max-width:800px;margin:auto">{result}</div></div>""", user)

@app.route("/reply/<int:mid>", methods=["GET","POST"])
def reply(mid):
    user = require_user()
    if not isinstance(user, dict): return user
    conn = db(); message = one(conn,"SELECT * FROM messages WHERE id=%s",(mid,))
    if not message: conn.close(); abort(404)
    if request.method == "GET":
        body = f"""<div class="content"><div class="box"><h2>{safe(t("reply",user))}</h2>
        <div class="card">{safe(message["text"])}</div><form method="post"><input name="text" maxlength="2000" required><button>{safe(t("send",user))}</button></form></div></div>"""
        conn.close(); return page(t("reply",user),body,user)
    text_value=request.form.get("text","").strip()[:2000]
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    q(conn,"INSERT INTO messages(room,room_id,username,text,created_at,created,reply,edited) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
      (message["room"],message["room"],user["username"],text_value,now,now,mid,0)); conn.commit(); conn.close()
    return redirect(url_for("chat",room=message["room"]))

@app.route("/edit/<int:mid>", methods=["GET","POST"])
def edit(mid):
    user = require_user()
    if not isinstance(user, dict): return user
    conn=db(); message=one(conn,"SELECT * FROM messages WHERE id=%s",(mid,))
    if not message: conn.close(); abort(404)
    if message["username"] != user["username"] and not user["admin"]:
        conn.close(); return page(t("edit",user),f'<div class="box">{safe(t("permission",user))}</div>',user)
    if request.method=="GET":
        body=f"""<div class="content"><div class="box"><h2>{safe(t("edit",user))}</h2>
        <form method="post"><textarea name="text" required maxlength="2000">{safe(message["text"])}</textarea><button>{safe(t("save",user))}</button></form></div></div>"""
        conn.close(); return page(t("edit",user),body,user)
    q(conn,"UPDATE messages SET text=%s,edited=1 WHERE id=%s",(request.form.get("text","")[:2000],mid)); conn.commit()
    room=message["room"]; conn.close(); return redirect(url_for("chat",room=room))

@app.route("/delete/<int:mid>")
def delete(mid):
    user = require_user()
    if not isinstance(user, dict): return user
    conn=db(); message=one(conn,"SELECT * FROM messages WHERE id=%s",(mid,))
    if not message: conn.close(); abort(404)
    if message["username"] != user["username"] and not user["admin"]:
        conn.close(); return page(t("delete",user),f'<div class="box">{safe(t("permission",user))}</div>',user)
    q(conn,"DELETE FROM messages WHERE id=%s",(mid,)); conn.commit(); room=message["room"]; conn.close()
    return redirect(url_for("chat",room=room))

@app.route("/admin")
def admin():
    user = require_user()
    if not isinstance(user, dict): return user
    if not user["admin"]:
        return page(t("admin",user),f'<div class="content"><div class="box">{safe(t("forbidden",user))}</div></div>',user)
    conn=db(); users=q(conn,"SELECT id,username,email,emoji,bio,admin,banned,verified,pro FROM users ORDER BY id DESC")
    rooms=q(conn,"SELECT id,name,username,kind,owner,emoji,bio FROM rooms ORDER BY id DESC"); conn.close()
    rows=""
    for z in users:
        badges=("✓ " if z["verified"] else "")+("PRO" if z["pro"] else "")
        rows += f"""<tr><td>@{safe(z["username"])} {safe(badges)}</td><td>{'Banned' if z["banned"] else 'Active'}</td><td>
        <a class="btn small" href="/admin/toggle/{z["id"]}/banned">{safe(t("ban",user))}</a>
        <a class="btn small" href="/admin/toggle/{z["id"]}/verified">{safe(t("verified",user))}</a>
        <a class="btn small" href="/admin/toggle/{z["id"]}/pro">{safe(t("pro",user))}</a></td></tr>"""
    room_rows="".join(f"<tr><td>{safe(r['emoji'])} {safe(r['name'])}</td><td>@{safe(r['username'])}</td><td>@{safe(r['owner'])}</td></tr>" for r in rooms)
    body=f"""<div class="content"><div class="box" style="max-width:1000px"><h2>{safe(t("admin_users",user))}</h2>
    <div class="table-wrap"><table class="table"><tr><th>User</th><th>Status</th><th>Actions</th></tr>{rows}</table></div></div>
    <div class="box" style="max-width:1000px"><h2>{safe(t("admin_rooms",user))}</h2><div class="table-wrap"><table class="table"><tr><th>Name</th><th>Username</th><th>Owner</th></tr>{room_rows}</table></div></div></div>"""
    return page(t("admin",user),body,user)

@app.route("/admin/toggle/<int:uid>/<field>")
def admin_toggle(uid,field):
    user=require_user()
    if not isinstance(user,dict): return user
    if not user["admin"] or field not in {"banned","verified","pro"}: abort(403)
    conn=db(); target=one(conn,"SELECT username,"+field+" FROM users WHERE id=%s",(uid,))
    if target and target["username"]!="parto":
        q(conn,f"UPDATE users SET {field}=%s WHERE id=%s",(0 if target[field] else 1,uid)); conn.commit()
    conn.close(); return redirect("/admin")

@app.errorhandler(404)
def not_found(_):
    user=current_user()
    return page("404",f'<div class="box"><h2>{safe(t("not_found",user))}</h2><a href="/chat">Parto</a></div>',user),404

@app.errorhandler(500)
def server_error(_):
    # Avoid exposing database/secret details to visitors.
    user=current_user()
    return page("500",'<div class="box"><h2>Server error</h2><p class="muted">Please check the Render logs.</p></div>',user),500

# Run migrations when the application process starts.
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8080")), debug=False)
