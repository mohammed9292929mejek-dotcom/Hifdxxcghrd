import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, session,
    jsonify, send_from_directory, render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "PARTO_CHANGE_THIS_SECRET")
PORT = int(os.environ.get("PORT", "8080"))
DB = os.environ.get("PARTO_DB", "parto.db")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_AUDIO = {".mp3", ".wav", ".ogg", ".m4a"}
ALLOWED_FILES = ALLOWED_IMAGES | ALLOWED_AUDIO


HTML = r"""
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>پرتو</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0e1621;color:#eee;font-family:Tahoma,Arial,sans-serif}
.app{max-width:520px;min-height:100vh;margin:auto;background:#17212b}
.top{height:62px;padding:12px 15px;background:#202b36;display:flex;
justify-content:space-between;align-items:center;position:sticky;top:0;z-index:5}
.logo{font-size:20px;font-weight:bold}
a{text-decoration:none;color:inherit}
.search{margin:10px 12px;padding:12px;border:0;border-radius:12px;
background:#242f3a;color:white;width:calc(100% - 24px)}
.item{display:flex;gap:12px;padding:13px 15px;align-items:center;
border-bottom:1px solid #22303b}
.avatar{width:48px;height:48px;border-radius:50%;background:#52606d;
display:flex;align-items:center;justify-content:center;overflow:hidden;
font-size:22px;flex:none}
.avatar img{width:100%;height:100%;object-fit:cover}
.name{font-weight:bold}.sub{font-size:12px;color:#9daab5;margin-top:5px}
.badge{font-size:13px;margin-right:4px}.red{color:#ff4d67}.yellow{color:#ffd43b}
.box{margin:14px;padding:15px;background:#202b36;border-radius:14px}
.center{text-align:center;padding:30px 18px}
input,textarea{width:100%;padding:11px;margin:7px 0;border:0;border-radius:10px;
background:#2b3945;color:white}
.btn{display:inline-block;border:0;border-radius:10px;padding:10px 14px;
background:#2aabee;color:white;cursor:pointer;margin:3px}
.chat{min-height:calc(100vh - 62px);padding:15px 12px 82px;background:#0e1621}
.msg{max-width:82%;background:#182533;padding:9px 11px;border-radius:12px;margin:7px 0}
.mine{margin-right:auto;background:#245d4b}
.msg small{display:block;color:#8d9aa5;font-size:10px;margin-top:4px}
.composer{position:fixed;bottom:0;max-width:520px;width:100%;padding:9px;
background:#202b36;display:flex;gap:6px;z-index:10}
.composer input[type=text]{margin:0;flex:1}
.composer input[type=file]{width:105px;margin:0}
.composer button{border:0;border-radius:50%;width:45px;background:#2aabee;color:white}
table{width:100%;border-collapse:collapse}
td,th{padding:8px;border-bottom:1px solid #33414c;text-align:right;font-size:12px}
audio{max-width:100%;margin-top:6px}
img.chatimg{max-width:100%;border-radius:10px;margin-top:6px}
</style>
</head>
<body>
<div class="app">{{ content|safe }}</div>
</body>
</html>
"""


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    con = db()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        display_name TEXT NOT NULL,
        avatar TEXT,
        is_pro INTEGER NOT NULL DEFAULT 0,
        yellow_tick INTEGER NOT NULL DEFAULT 0,
        banned INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        title TEXT NOT NULL,
        username TEXT UNIQUE,
        owner_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS chat_members (
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        banned INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(chat_id,user_id),
        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        text TEXT,
        file_name TEXT,
        file_type TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
        FOREIGN KEY(sender_id) REFERENCES users(id)
    );
    """)

    admin_user = os.environ.get("PARTO_ADMIN_USER", "admin")
    admin_pass = os.environ.get("PARTO_ADMIN_PASS", "m123")

    admin = con.execute(
        "SELECT id FROM users WHERE username=?",
        (admin_user,)
    ).fetchone()

    if not admin:
        con.execute(
            """INSERT INTO users
            (username,password,display_name,yellow_tick,created_at)
            VALUES(?,?,?,?,?)""",
            (
                admin_user,
                generate_password_hash(admin_pass),
                "مدیر پرتو",
                1,
                datetime.now().isoformat()
            )
        )

    con.commit()
    con.close()


def current_user():
    uid = session.get("uid")
    if not uid:
        return None

    con = db()
    user = con.execute(
        "SELECT * FROM users WHERE id=?",
        (uid,)
    ).fetchone()
    con.close()
    return user


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = current_user()
        admin_user = os.environ.get("PARTO_ADMIN_USER", "admin")

        if not user or user["username"] != admin_user:
            return "دسترسی غیرمجاز", 403

        return func(*args, **kwargs)
    return wrapper


def page(content):
    return render_template_string(HTML, content=content)


def badges(user):
    result = ""

    if user["is_pro"]:
        result += '<span class="badge red">●</span>'

    if user["yellow_tick"]:
        result += '<span class="badge yellow">●</span>'

    return result


@app.route("/")
def index():
    user = current_user()

    if not user:
        return redirect(url_for("login"))

    con = db()

    saved = con.execute(
        "SELECT * FROM chats WHERE kind='saved' AND owner_id=?",
        (user["id"],)
    ).fetchone()

    if not saved:
        cur = con.execute(
            """INSERT INTO chats
            (kind,title,username,owner_id,created_at)
            VALUES(?,?,?,?,?)""",
            (
                "saved",
                "پیام‌های ذخیره‌شده",
                "saved_" + str(user["id"]),
                user["id"],
                datetime.now().isoformat()
            )
        )

        chat_id = cur.lastrowid

        con.execute(
            """INSERT INTO chat_members
            (chat_id,user_id,role) VALUES(?,?,?)""",
            (chat_id, user["id"], "owner")
        )

        con.commit()

        saved = con.execute(
            "SELECT * FROM chats WHERE id=?",
            (chat_id,)
        ).fetchone()

    chats = con.execute(
        """
        SELECT
            c.*,
            m.text AS last_text
        FROM chats c
        JOIN chat_members cm
          ON cm.chat_id=c.id
         AND cm.user_id=?
        LEFT JOIN messages m
          ON m.id=(
             SELECT MAX(id)
             FROM messages
             WHERE chat_id=c.id
          )
        WHERE c.kind!='saved'
        ORDER BY COALESCE(m.id,0) DESC,c.id DESC
        """,
        (user["id"],)
    ).fetchall()

    con.close()

    body = f"""
    <div class="top">
        <div class="logo">⚡ پرتو</div>
        <a href="{url_for('profile')}">👤</a>
    </div>

    <form action="{url_for('search')}" method="get">
        <input class="search" name="q" placeholder="🔍 جستجو / آیدی">
    </form>

    <a class="item" href="{url_for('chat', chat_id=saved['id'])}">
        <div class="avatar">💾</div>
        <div>
            <div class="name">پیام‌های ذخیره‌شده</div>
            <div class="sub">پیام‌های شخصی</div>
        </div>
    </a>
    """

    for chat in chats:
        icon = {
            "private": "💬",
            "group": "👥",
            "channel": "📢"
        }.get(chat["kind"], "💬")

        body += f"""
        <a class="item" href="{url_for('chat', chat_id=chat['id'])}">
            <div class="avatar">{icon}</div>
            <div>
                <div class="name">{chat['title']}</div>
                <div class="sub">
                    @{chat['username'] or ''}
                    {chat['last_text'] or ''}
                </div>
            </div>
        </a>
        """

    body += f"""
    <div class="box">
        <a class="btn" href="{url_for('create_group')}">+ گروه</a>
        <a class="btn" href="{url_for('create_channel')}">+ کانال</a>
        <a class="btn" href="{url_for('logout')}">خروج</a>
    </div>
    """

    if user["username"] == os.environ.get("PARTO_ADMIN_USER", "admin"):
        body += f"""
        <div class="box">
            <a class="btn" href="{url_for('admin')}">
                🛠 پنل ادمین
            </a>
        </div>
        """

    return page(body)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip().lower().lstrip("@")
        name = request.form["name"].strip() or username
        password = request.form["password"]

        if len(username) < 3 or len(password) < 4:
            return page('<div class="box">آیدی حداقل ۳ و رمز حداقل ۴ کاراکتر باشد.</div>')

        try:
            con = db()

            user_id = con.execute(
                """INSERT INTO users
                (username,password,display_name,created_at)
                VALUES(?,?,?,?)""",
                (
                    username,
                    generate_password_hash(password),
                    name,
                    datetime.now().isoformat()
                )
            ).lastrowid

            chat_id = con.execute(
                """INSERT INTO chats
                (kind,title,username,owner_id,created_at)
                VALUES(?,?,?,?,?)""",
                (
                    "saved",
                    "پیام‌های ذخیره‌شده",
                    "saved_" + str(user_id),
                    user_id,
                    datetime.now().isoformat()
                )
            ).lastrowid

            con.execute(
                """INSERT INTO chat_members
                (chat_id,user_id,role)
                VALUES(?,?,?)""",
                (chat_id, user_id, "owner")
            )

            con.commit()
            con.close()

            session["uid"] = user_id
            return redirect(url_for("index"))

        except sqlite3.IntegrityError:
            return page('<div class="box">این آیدی قبلاً گرفته شده.</div>')

    return page("""
    <div class="center">
        <h2>⚡ ثبت‌نام پرتو</h2>
        <form method="post" class="box">
            <input name="name" placeholder="نام نمایشی" required>
            <input name="username" placeholder="آیدی" required>
            <input name="password" type="password" placeholder="رمز عبور" required>
            <button class="btn">ثبت‌نام</button>
        </form>
        <a href="/login">ورود</a>
    </div>
    """)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower().lstrip("@")
        password = request.form["password"]

        con = db()

        user = con.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        con.close()

        if (
            user
            and check_password_hash(user["password"], password)
            and not user["banned"]
        ):
            session["uid"] = user["id"]
            return redirect(url_for("index"))

        return page('<div class="box">ورود ناموفق یا حساب مسدود است.</div>')

    return page("""
    <div class="center">
        <h2>⚡ ورود به پرتو</h2>
        <form method="post" class="box">
            <input name="username" placeholder="آیدی">
            <input name="password" type="password" placeholder="رمز عبور">
            <button class="btn">ورود</button>
        </form>
        <a href="/register">ساخت حساب</a>
    </div>
    """)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/search")
@login_required
def search():
    query = request.args.get("q", "").strip().lstrip("@")

    con = db()

    users = con.execute(
        """SELECT * FROM users
        WHERE username LIKE ?
        OR display_name LIKE ?
        LIMIT 30""",
        (f"%{query}%", f"%{query}%")
    ).fetchall()

    chats = con.execute(
        """SELECT * FROM chats
        WHERE username LIKE ?
        OR title LIKE ?
        LIMIT 30""",
        (f"%{query}%", f"%{query}%")
    ).fetchall()

    con.close()

    body = '<div class="top"><a href="/">‹</a><b>جستجو</b></div>'

    for user in users:
        body += f"""
        <div class="item">
            <div class="avatar">👤</div>
            <div>
                <div class="name">
                    {user['display_name']} {badges(user)}
                </div>
                <div class="sub">@{user['username']}</div>
            </div>

            <form style="margin-right:auto"
                  method="post"
                  action="{url_for('start_chat', other_id=user['id'])}">
                <button class="btn">پیام</button>
            </form>
        </div>
        """

    for chat in chats:
        icon = "📢" if chat["kind"] == "channel" else "👥"

        body += f"""
        <a class="item" href="{url_for('join', chat_id=chat['id'])}">
            <div class="avatar">{icon}</div>
            <div>
                <div class="name">{chat['title']}</div>
                <div class="sub">@{chat['username']}</div>
            </div>
        </a>
        """

    return page(body or '<div class="center">چیزی پیدا نشد.</div>')


@app.post("/start/<int:other_id>")
@login_required
def start_chat(other_id):
    me = current_user()

    if me["id"] == other_id:
        return redirect(url_for("index"))

    con = db()

    existing = con.execute(
        """
        SELECT c.id
        FROM chats c
        JOIN chat_members a ON a.chat_id=c.id
        JOIN chat_members b ON b.chat_id=c.id
        WHERE c.kind='private'
          AND a.user_id=?
          AND b.user_id=?
        """,
        (me["id"], other_id)
    ).fetchone()

    if existing:
        chat_id = existing["id"]
    else:
        other = con.execute(
            "SELECT * FROM users WHERE id=?",
            (other_id,)
        ).fetchone()

        if not other:
            con.close()
            return "کاربر پیدا نشد", 404

        username = "p_" + uuid.uuid4().hex[:12]

        chat_id = con.execute(
            """INSERT INTO chats
            (kind,title,username,owner_id,created_at)
            VALUES(?,?,?,?,?)""",
            (
                "private",
                other["display_name"],
                username,
                me["id"],
                datetime.now().isoformat()
            )
        ).lastrowid

        con.execute(
            "INSERT INTO chat_members(chat_id,user_id,role) VALUES(?,?,?)",
            (chat_id, me["id"], "member")
        )

        con.execute(
            "INSERT INTO chat_members(chat_id,user_id,role) VALUES(?,?,?)",
            (chat_id, other_id, "member")
        )

        con.commit()

    con.close()

    return redirect(url_for("chat", chat_id=chat_id))


def create_space(kind):
    user = current_user()

    title = request.form["title"].strip()
    username = request.form["username"].strip().lstrip("@").lower()

    con = db()

    try:
        chat_id = con.execute(
            """INSERT INTO chats
            (kind,title,username,owner_id,created_at)
            VALUES(?,?,?,?,?)""",
            (
                kind,
                title,
                username,
                user["id"],
                datetime.now().isoformat()
            )
        ).lastrowid

        con.execute(
            """INSERT INTO chat_members
            (chat_id,user_id,role)
            VALUES(?,?,?)""",
            (chat_id, user["id"], "owner")
        )

        con.commit()
        con.close()

        return redirect(url_for("chat", chat_id=chat_id))

    except sqlite3.IntegrityError:
        con.close()
        return page('<div class="box">این آیدی قبلاً استفاده شده.</div>')


@app.route("/create/group", methods=["GET", "POST"])
@login_required
def create_group():
    if request.method == "POST":
        return create_space("group")

    return page("""
    <div class="box">
        <h3>👥 ساخت گروه</h3>
        <form method="post">
            <input name="title" placeholder="نام گروه" required>
            <input name="username" placeholder="آیدی گروه" required>
            <button class="btn">ساخت گروه</button>
        </form>
    </div>
    """)


@app.route("/create/channel", methods=["GET", "POST"])
@login_required
def create_channel():
    if request.method == "POST":
        return create_space("channel")

    return page("""
    <div class="box">
        <h3>📢 ساخت کانال</h3>
        <form method="post">
            <input name="title" placeholder="نام کانال" required>
            <input name="username" placeholder="آیدی کانال" required>
            <button class="btn">ساخت کانال</button>
        </form>
    </div>
    """)


@app.route("/join/<int:chat_id>")
@login_required
def join(chat_id):
    user = current_user()

    con = db()

    chat = con.execute(
        "SELECT * FROM chats WHERE id=?",
        (chat_id,)
    ).fetchone()

    if not chat:
        con.close()
        return "پیدا نشد", 404

    member = con.execute(
        """SELECT * FROM chat_members
        WHERE chat_id=? AND user_id=?""",
        (chat_id, user["id"])
    ).fetchone()

    if not member:
        con.execute(
            """INSERT INTO chat_members
            (chat_id,user_id,role)
            VALUES(?,?,?)""",
            (chat_id, user["id"], "member")
        )

    con.commit()
    con.close()

    return redirect(url_for("chat", chat_id=chat_id))


@app.route("/chat/<int:chat_id>", methods=["GET", "POST"])
@login_required
def chat(chat_id):
    user = current_user()

    con = db()

    member = con.execute(
        """SELECT * FROM chat_members
        WHERE chat_id=? AND user_id=?""",
        (chat_id, user["id"])
    ).fetchone()

    chat_row = con.execute(
        "SELECT * FROM chats WHERE id=?",
        (chat_id,)
    ).fetchone()

    if not chat_row or not member or member["banned"]:
        con.close()
        return "دسترسی ندارید", 403

    if request.method == "POST":
        text = request.form.get("text", "").strip()

        upload = request.files.get("file")

        file_name = None
        file_type = None

        if upload and upload.filename:
            original = secure_filename(upload.filename)
            ext = os.path.splitext(original)[1].lower()

            if ext not in ALLOWED_FILES:
                con.close()
                return "نوع فایل مجاز نیست", 400

            file_name = uuid.uuid4().hex + ext

            upload.save(
                os.path.join(UPLOAD_DIR, file_name)
            )

            file_type = (
                "audio"
                if ext in ALLOWED_AUDIO
                else "image"
            )

        if text or file_name:
            con.execute(
                """INSERT INTO messages
                (chat_id,sender_id,text,file_name,file_type,created_at)
                VALUES(?,?,?,?,?,?)""",
                (
                    chat_id,
                    user["id"],
                    text,
                    file_name,
                    file_type,
                    datetime.now().isoformat()
                )
            )

            con.commit()

        con.close()

        return redirect(url_for("chat", chat_id=chat_id))

    messages = con.execute(
        """
        SELECT
            m.*,
            u.display_name,
            u.username,
            u.avatar,
            u.is_pro,
            u.yellow_tick
        FROM messages m
        JOIN users u ON u.id=m.sender_id
        WHERE m.chat_id=?
        ORDER BY m.id
        """,
        (chat_id,)
    ).fetchall()

    con.close()

    icon = {
        "private": "💬",
        "group": "👥",
        "channel": "📢",
        "saved": "💾"
    }.get(chat_row["kind"], "💬")

    body = f"""
    <div class="top">
        <a href="/">‹</a>
        <div>
            <b>{chat_row['title']}</b>
            <div style="font-size:11px">
                @{chat_row['username']}
            </div>
        </div>
        <span>{icon}</span>
    </div>

    <div class="chat">
    """

    for message in messages:
        own = message["sender_id"] == user["id"]
        css = "msg mine" if own else "msg"

        body += f"""
        <div class="{css}">
            <b>
                {message['display_name']}
                {badges(message)}
            </b>
        """

        if message["text"]:
            body += f"<div>{message['text']}</div>"

        if message["file_type"] == "image":
            body += f"""
            <img class="chatimg"
                 src="/uploads/{message['file_name']}">
            """

        elif message["file_type"] == "audio":
            body += f"""
            <audio controls
                   src="/uploads/{message['file_name']}">
            </audio>
            """

        body += f"""
            <small>{message['created_at'][11:16]}</small>
        </div>
        """

    body += """
    </div>

    <form class="composer"
          method="post"
          enctype="multipart/form-data">

        <input type="text"
               name="text"
               placeholder="پیام...">

        <input type="file"
               name="file"
               accept="image/*,audio/*">

        <button>➤</button>
    </form>
    """

    return page(body)


@app.route("/uploads/<path:name>")
def uploads(name):
    return send_from_directory(UPLOAD_DIR, name)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()

    if request.method == "POST":
        name = request.form.get(
            "name",
            user["display_name"]
        ).strip()

        avatar = request.files.get("avatar")
        filename = user["avatar"]

        if avatar and avatar.filename:
            original = secure_filename(avatar.filename)
            ext = os.path.splitext(original)[1].lower()

            if ext not in ALLOWED_IMAGES:
                return "فرمت تصویر مجاز نیست", 400

            filename = uuid.uuid4().hex + ext

            avatar.save(
                os.path.join(UPLOAD_DIR, filename)
            )

        con = db()

        con.execute(
            """UPDATE users
            SET display_name=?,avatar=?
            WHERE id=?""",
            (name, filename, user["id"])
        )

        con.commit()
        con.close()

        return redirect(url_for("profile"))

    if user["avatar"]:
        avatar_html = (
            f'<img src="/uploads/{user["avatar"]}">'
        )
    else:
        avatar_html = "👤"

    return page(f"""
    <div class="top">
        <a href="/">‹</a>
        <b>پروفایل</b>
    </div>

    <div class="box center">
        <div class="avatar"
             style="margin:auto;width:90px;height:90px">
            {avatar_html}
        </div>

        <h2>
            {user['display_name']}
            {badges(user)}
        </h2>

        <div>@{user['username']}</div>

        <form method="post"
              enctype="multipart/form-data">

            <input name="name"
                   value="{user['display_name']}">

            <input type="file"
                   name="avatar"
                   accept="image/*">

            <button class="btn">
                ذخیره
            </button>
        </form>
    </div>
    """)


@app.route("/admin")
@admin_required
def admin():
    con = db()

    users = con.execute(
        "SELECT * FROM users ORDER BY id DESC"
    ).fetchall()

    chats = con.execute(
        """
        SELECT c.*,u.username owner
        FROM chats c
        LEFT JOIN users u
          ON u.id=c.owner_id
        WHERE c.kind IN ('group','channel')
        ORDER BY c.id DESC
        """
    ).fetchall()

    con.close()

    body = """
    <div class="top">
        <a href="/">‹</a>
        <b>🛠 پنل مدیریت پرتو</b>
    </div>

    <div class="box">
        <h3>کاربران</h3>

        <table>
        <tr>
            <th>کاربر</th>
            <th>وضعیت</th>
            <th>مدیریت</th>
        </tr>
    """

    for user in users:
        body += f"""
        <tr>
            <td>
                {user['display_name']}<br>
                @{user['username']}
            </td>

            <td>
                {badges(user)}
                {'🚫' if user['banned'] else ''}
            </td>

            <td>
                <a class="btn"
                   href="/admin/user/{user['id']}">
                   مدیریت
                </a>
            </td>
        </tr>
        """

    body += """
        </table>
    </div>

    <div class="box">
        <h3>گروه‌ها و کانال‌ها</h3>
    """

    for chat_row in chats:
        body += f"""
        <div class="item">
            <div>
                {chat_row['title']}<br>
                <small>@{chat_row['username']}</small>
            </div>

            <a class="btn"
               style="margin-right:auto"
               href="/admin/chat/{chat_row['id']}">
               مدیریت
            </a>
        </div>
        """

    body += "</div>"

    return page(body)


@app.route("/admin/user/<int:user_id>", methods=["GET", "POST"])
@admin_required
def admin_user(user_id):
    con = db()

    user = con.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if not user:
        con.close()
        return "کاربر پیدا نشد", 404

    if request.method == "POST":
        action = request.form.get("action")

        if action == "pro":
            con.execute(
                "UPDATE users SET is_pro=1-is_pro WHERE id=?",
                (user_id,)
            )

        elif action == "yellow":
            con.execute(
                "UPDATE users SET yellow_tick=1-yellow_tick WHERE id=?",
                (user_id,)
            )

        elif action == "ban":
            con.execute(
                "UPDATE users SET banned=1 WHERE id=?",
                (user_id,)
            )

        elif action == "unban":
            con.execute(
                "UPDATE users SET banned=0 WHERE id=?",
                (user_id,)
            )

        con.commit()
        con.close()

        return redirect(url_for("admin"))

    con.close()

    return page(f"""
    <div class="box">
        <h3>
            مدیریت {user['display_name']}
        </h3>

        <p>
            @{user['username']}
            {badges(user)}
        </p>

        <form method="post">

            <button class="btn"
                    name="action"
                    value="pro">
                🔴 تغییر Pro
            </button>

            <button class="btn"
                    name="action"
                    value="yellow">
                🟡 تغییر تیک زرد
            </button>

            <button class="btn"
                    name="action"
                    value="ban">
                🚫 بن
            </button>

            <button class="btn"
                    name="action"
                    value="unban">
                ✅ آن‌بن
            </button>

        </form>
    </div>
    """)


@app.route("/admin/chat/<int:chat_id>", methods=["GET", "POST"])
@admin_required
def admin_chat(chat_id):
    con = db()

    chat_row = con.execute(
        "SELECT * FROM chats WHERE id=?",
        (chat_id,)
    ).fetchone()

    if not chat_row:
        con.close()
        return "پیدا نشد", 404

    if request.method == "POST":
        action = request.form.get("action")

        if action == "ban":
            con.execute(
                "UPDATE chat_members SET banned=1 WHERE chat_id=?",
                (chat_id,)
            )

        elif action == "unban":
            con.execute(
                "UPDATE chat_members SET banned=0 WHERE chat_id=?",
                (chat_id,)
            )

        elif action == "yellow":
            owner = con.execute(
                "SELECT owner_id FROM chats WHERE id=?",
                (chat_id,)
            ).fetchone()

            if owner:
                con.execute(
                    "UPDATE users SET yellow_tick=1-yellow_tick WHERE id=?",
                    (owner["owner_id"],)
                )

        elif action == "pro":
            owner = con.execute(
                "SELECT owner_id FROM chats WHERE id=?",
                (chat_id,)
            ).fetchone()

            if owner:
                con.execute(
                    "UPDATE users SET is_pro=1-is_pro WHERE id=?",
                    (owner["owner_id"],)
                )

        con.commit()
        con.close()

        return redirect(url_for("admin"))

    con.close()

    return page(f"""
    <div class="box">
        <h3>مدیریت {chat_row['title']}</h3>

        <p>@{chat_row['username']}</p>

        <form method="post">

            <button class="btn"
                    name="action"
                    value="pro">
                🔴 Pro
            </button>

            <button class="btn"
                    name="action"
                    value="yellow">
                🟡 تیک زرد
            </button>

            <button class="btn"
                    name="action"
                    value="ban">
                🚫 بن اعضا
            </button>

            <button class="btn"
                    name="action"
                    value="unban">
                ✅ آن‌بن اعضا
            </button>

        </form>
    </div>
    """)


@app.route("/health")
def health():
    return jsonify(
        ok=True,
        service="parto",
        database="sqlite"
    )


init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
