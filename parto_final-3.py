from flask import Flask, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "PARTO_2026"
DB = "parto.db"


def db():
    x = sqlite3.connect(DB)
    x.row_factory = sqlite3.Row
    return x


def init_db():
    x = db()

    x.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY,"
        "username TEXT UNIQUE NOT NULL,"
        "email TEXT UNIQUE,"
        "password TEXT NOT NULL,"
        "emoji TEXT DEFAULT '👤',"
        "bio TEXT DEFAULT '',"
        "admin INTEGER DEFAULT 0,"
        "banned INTEGER DEFAULT 0)"
    )

    x.execute(
        "CREATE TABLE IF NOT EXISTS rooms ("
        "id INTEGER PRIMARY KEY,"
        "name TEXT NOT NULL,"
        "username TEXT UNIQUE NOT NULL,"
        "kind TEXT NOT NULL,"
        "owner TEXT NOT NULL,"
        "emoji TEXT DEFAULT '👥',"
        "bio TEXT DEFAULT '')"
    )

    x.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "id INTEGER PRIMARY KEY,"
        "room INTEGER,"
        "room_id INTEGER,"
        "username TEXT NOT NULL,"
        "text TEXT NOT NULL,"
        "created_at TEXT DEFAULT '',"
        "created TEXT DEFAULT '',"
        "reply INTEGER DEFAULT 0,"
        "edited INTEGER DEFAULT 0)"
    )

    x.execute(
        "CREATE TABLE IF NOT EXISTS private_messages ("
        "id INTEGER PRIMARY KEY,"
        "sender TEXT NOT NULL,"
        "receiver TEXT NOT NULL,"
        "text TEXT NOT NULL)"
    )

    # Safe migration: add missing columns without deleting old data.
    def cols(table):
        return {
            row[1] for row in x.execute(
                "PRAGMA table_info(" + table + ")"
            ).fetchall()
        }

    mc = cols("messages")

    if "room" not in mc:
        x.execute("ALTER TABLE messages ADD COLUMN room INTEGER")
    if "room_id" not in mc:
        x.execute("ALTER TABLE messages ADD COLUMN room_id INTEGER")
    if "created_at" not in mc:
        x.execute(
            "ALTER TABLE messages ADD COLUMN created_at TEXT DEFAULT ''"
        )
    if "created" not in mc:
        x.execute(
            "ALTER TABLE messages ADD COLUMN created TEXT DEFAULT ''"
        )
    if "reply" not in mc:
        x.execute(
            "ALTER TABLE messages ADD COLUMN reply INTEGER DEFAULT 0"
        )
    if "edited" not in mc:
        x.execute(
            "ALTER TABLE messages ADD COLUMN edited INTEGER DEFAULT 0"
        )

    # Copy old room references to the new field and vice versa.
    x.execute(
        "UPDATE messages SET room=room_id "
        "WHERE room IS NULL AND room_id IS NOT NULL"
    )
    x.execute(
        "UPDATE messages SET room_id=room "
        "WHERE room_id IS NULL AND room IS NOT NULL"
    )

    now = datetime.now().isoformat(timespec="seconds")
    x.execute(
        "UPDATE messages SET created_at=? "
        "WHERE created_at IS NULL OR created_at=''",
        (now,)
    )
    x.execute(
        "UPDATE messages SET created=created_at "
        "WHERE created IS NULL OR created=''"
    )

    # Keep the default Parto account/channel.
    if not x.execute(
        "SELECT id FROM users WHERE username='parto'"
    ).fetchone():
        x.execute(
            "INSERT INTO users "
            "(username,email,password,emoji,bio,admin) "
            "VALUES(?,?,?,?,?,?)",
            ("parto", "parto@local",
             generate_password_hash("123456"),
             "⚡", "مدیر رسمی پرتو", 1)
        )

    if not x.execute(
        "SELECT id FROM rooms WHERE username='parto'"
    ).fetchone():
        x.execute(
            "INSERT INTO rooms "
            "(name,username,kind,owner,emoji,bio) "
            "VALUES(?,?,?,?,?,?)",
            ("پرتو", "parto", "channel", "parto",
             "⚡", "کانال رسمی پرتو")
        )

    x.commit()
    x.close()
    print("PARTO DATABASE MIGRATION OK")


def me():
    if "user" not in session:
        return None
    x = db()
    u = x.execute(
        "SELECT * FROM users WHERE username=?",
        (session["user"],)
    ).fetchone()
    x.close()
    return u


CSS = '\n*{box-sizing:border-box}\n:root{--bg:#070b14;--panel:#0d1422;--panel2:#111b2b;--line:#223047;\n--text:#f5f7fb;--muted:#8e9bb0;--accent:#7c5cff;--accent2:#00d4ff}\nhtml,body{margin:0;min-height:100%;background:\nradial-gradient(circle at 15% 0%,#17245a 0,transparent 32%),\nradial-gradient(circle at 100% 30%,#073e55 0,transparent 28%),var(--bg);\ncolor:var(--text);font-family:Tahoma,Arial,sans-serif;direction:rtl}\nbody{min-height:100vh}a{color:var(--text);text-decoration:none}\n.app{min-height:100vh;display:flex;overflow:hidden}\n.menu{width:88px;background:rgba(13,20,34,.82);backdrop-filter:blur(18px);\nborder-left:1px solid var(--line);overflow:auto;flex-shrink:0}\n.menu a{display:block;text-align:center;padding:14px 4px;color:#cbd5e7;\nborder-bottom:1px solid rgba(255,255,255,.04);font-size:12px}\n.menu a:hover{background:rgba(124,92,255,.15);color:#fff}\n.main{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh}\n.head{padding:16px 18px;background:rgba(13,20,34,.78);backdrop-filter:blur(18px);\nborder-bottom:1px solid var(--line);font-size:18px;font-weight:bold}\n.msgs{flex:1;overflow:auto;padding:18px;scroll-behavior:smooth}\n.msg{background:rgba(17,27,43,.92);border:1px solid rgba(255,255,255,.05);\npadding:11px 13px;margin:9px 0;border-radius:17px;max-width:min(86%,560px);\nbox-shadow:0 8px 22px rgba(0,0,0,.12);line-height:1.8;word-wrap:break-word}\n.mine{margin-right:auto;background:linear-gradient(135deg,#263f7c,#29325f);\nborder-color:rgba(124,92,255,.3)}\n.send{display:flex;gap:8px;padding:10px;background:rgba(13,20,34,.9);\nborder-top:1px solid var(--line);backdrop-filter:blur(18px)}\n.send input{flex:1;margin:0!important;border-radius:24px!important}\n.send button{width:58px;margin:0!important;border-radius:20px!important}\ninput,textarea,select,button{width:100%;padding:12px;margin:6px 0;border:1px solid transparent;\nborder-radius:12px;font:inherit}\ninput,textarea,select{background:#111c2d;color:#fff;outline:none}\ninput:focus,textarea:focus,select:focus{border-color:var(--accent)}\nbutton{background:linear-gradient(135deg,var(--accent),#5a7cff);color:white;font-weight:bold}\nbutton:hover{filter:brightness(1.1)}\n.box{width:92%;max-width:540px;margin:35px auto;background:rgba(13,20,34,.88);\nborder:1px solid var(--line);backdrop-filter:blur(20px);padding:24px;border-radius:24px;\nbox-shadow:0 20px 70px rgba(0,0,0,.35)}\n.card{background:#111c2d;border:1px solid var(--line);padding:12px;margin:8px 0;border-radius:15px}\n.avatar{font-size:64px;text-align:center;filter:drop-shadow(0 10px 25px rgba(124,92,255,.25))}\n.tick{background:linear-gradient(135deg,#ffd43b,#ffad1f);color:#16120a;\npadding:3px 8px;border-radius:20px;font-size:12px}\nh1,h2{margin-top:5px}\n@media(max-width:600px){.menu{width:72px}.menu a{padding:12px 2px;font-size:10px}\n.msgs{padding:10px}.msg{max-width:92%}.head{padding:13px}.box{margin:18px auto;padding:18px}}\n'


def page(html):
    return (
        "<meta name='viewport' "
        "content='width=device-width,initial-scale=1'>"
        "<style>" + CSS + "</style>" + html
    )


@app.route("/")
def home():
    if me():
        return redirect("/chat")
    return page("""
    <div class="box">
        <div class="avatar">⚡</div>
        <h1>پرتو</h1>
        <form method="post" action="/login">
            <input name="email" placeholder="ایمیل" required>
            <input name="password" type="password"
                   placeholder="رمز عبور" required>
            <button>ورود</button>
        </form>
        <a href="/register">ثبت‌نام</a>
    </div>
    """)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return page("""
        <div class="box">
            <h2>ثبت‌نام</h2>
            <form method="post">
                <input name="username" placeholder="آیدی" required>
                <input name="email" placeholder="ایمیل" required>
                <input name="password" type="password"
                       placeholder="رمز عبور" required>
                <button>ساخت حساب</button>
            </form>
        </div>
        """)
    username = request.form["username"].strip()
    email = request.form["email"].strip()
    password = request.form["password"]
    if len(username) < 3:
        return "آیدی حداقل ۳ کاراکتر باشد."
    if len(password) < 6:
        return "رمز حداقل ۶ کاراکتر باشد."
    x = db()
    try:
        x.execute(
            "INSERT INTO users (username,email,password) "
            "VALUES(?,?,?)",
            (username, email, generate_password_hash(password))
        )
        x.commit()
    except sqlite3.IntegrityError:
        x.close()
        return "آیدی یا ایمیل قبلاً استفاده شده."
    x.close()
    session["user"] = username
    return redirect("/chat")


@app.route("/login", methods=["POST"])
def login():
    x = db()
    u = x.execute(
        "SELECT * FROM users WHERE email=?",
        (request.form["email"],)
    ).fetchone()
    x.close()
    if not u:
        return "کاربر پیدا نشد."
    if u["banned"]:
        return "حساب شما مسدود است."
    if not check_password_hash(
        u["password"], request.form["password"]
    ):
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
    x = db()
    target = x.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()
    x.close()
    if not target:
        return "کاربر پیدا نشد."
    tick = "<span class='tick'>✓</span>" if target["admin"] else ""
    edit = ""
    if u["username"] == username:
        edit = "<br><a href='/editprofile'>⚙️ ویرایش پروفایل</a>"
    return page(
        "<div class='box'>"
        "<div class='avatar'>" + target["emoji"] + "</div>"
        "<h2>@" + target["username"] + " " + tick + "</h2>"
        "<p>" + (target["bio"] or "بدون بیو") + "</p>"
        "<a href='/private/" + username + "'>💬 پیام خصوصی</a>"
        + edit + "<br><br><a href='/chat'>بازگشت</a>"
        "</div>"
    )


@app.route("/editprofile", methods=["GET", "POST"])
def editprofile():
    u = me()
    if not u:
        return redirect("/")
    if request.method == "GET":
        return page("""
        <div class="box">
            <h2>👤 پروفایل</h2>
            <form method="post">
                <select name="emoji">
                    <option>👤</option><option>👻</option>
                    <option>😎</option><option>⚡</option>
                    <option>💻</option><option>🕷️</option>
                    <option>☠️</option><option>🤖</option>
                    <option>🔥</option>
                </select>
                <textarea name="bio" placeholder="بیوگرافی"></textarea>
                <button>ذخیره</button>
            </form>
        </div>
        """)
    x = db()
    x.execute(
        "UPDATE users SET emoji=?,bio=? WHERE username=?",
        (request.form["emoji"], request.form["bio"][:200],
         u["username"])
    )
    x.commit()
    x.close()
    return redirect("/profile/" + u["username"])


@app.route("/private/<username>")
def private(username):
    u = me()
    if not u:
        return redirect("/")
    x = db()
    target = x.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()
    if not target:
        x.close()
        return "کاربر پیدا نشد."
    messages = x.execute(
        "SELECT * FROM private_messages "
        "WHERE (sender=? AND receiver=?) "
        "OR (sender=? AND receiver=?) ORDER BY id",
        (u["username"], username, username, u["username"])
    ).fetchall()
    body = ""
    for m in messages:
        cls = "msg"
        if m["sender"] == u["username"]:
            cls += " mine"
        body += (
            "<div class='" + cls + "'><b>@" +
            m["sender"] + "</b><br>" + m["text"] + "</div>"
        )
    x.close()
    return page(
        "<div class='app'><div class='main'>"
        "<div class='head'>" + target["emoji"] +
        " @" + target["username"] + "</div>"
        "<div class='msgs'>" + body + "</div>"
        "<form class='send' method='post' action='/private/" +
        username + "/send'>"
        "<input name='text' placeholder='پیام خصوصی...' required>"
        "<button>➤</button></form></div></div>"
    )


@app.route("/private/<username>/send", methods=["POST"])
def private_send(username):
    u = me()
    if not u:
        return redirect("/")
    x = db()
    target = x.execute(
        "SELECT id FROM users WHERE username=?",
        (username,)
    ).fetchone()
    if not target:
        x.close()
        return "کاربر پیدا نشد."
    x.execute(
        "INSERT INTO private_messages "
        "(sender,receiver,text) VALUES(?,?,?)",
        (u["username"], username, request.form["text"][:2000])
    )
    x.commit()
    x.close()
    return redirect("/private/" + username)


@app.route("/chat")
def chat():
    u = me()
    if not u:
        return redirect("/")
    x = db()
    rooms = x.execute(
        "SELECT * FROM rooms ORDER BY id"
    ).fetchall()
    if not rooms:
        x.close()
        return "هیچ اتاقی وجود ندارد."
    rid = request.args.get("room")
    if rid:
        room = x.execute(
            "SELECT * FROM rooms WHERE id=?",
            (rid,)
        ).fetchone()
    else:
        room = rooms[0]
    if not room:
        x.close()
        return "اتاق پیدا نشد."
    messages = x.execute(
        "SELECT * FROM messages WHERE room=? ORDER BY id",
        (room["id"],)
    ).fetchall()
    menu = ""
    for r in rooms:
        menu += (
            "<a href='/chat?room=" + str(r["id"]) + "'>" +
            r["emoji"] + "<br>" + r["name"] + "</a>"
        )
    body = ""
    for m in messages:
        cls = "msg mine" if m["username"] == u["username"] else "msg"
        reply_html = ""
        if m["reply"]:
            old = x.execute(
                "SELECT username,text FROM messages WHERE id=?",
                (m["reply"],)
            ).fetchone()
            if old:
                reply_html = (
                    "<div class='card'>↩️ @" +
                    old["username"] + "<br>" + old["text"] +
                    "</div>"
                )
        actions = (
            "<a href='/reply/" + str(m["id"]) + "'>↩️</a>"
        )
        if m["username"] == u["username"] or u["admin"]:
            actions += (
                " <a href='/edit/" + str(m["id"]) + "'>✏️</a>"
                " <a href='/delete/" + str(m["id"]) + "'>🗑️</a>"
            )
        body += (
            "<div class='" + cls + "'>" + reply_html +
            "<a href='/profile/" + m["username"] + "'>@" +
            m["username"] + "</a><br>" + m["text"] +
            "<br>" + actions + "</div>"
        )
    form = ""
    if room["kind"] == "group" or room["owner"] == u["username"]:
        form = (
            "<form class='send' method='post' action='/send/" +
            str(room["id"]) + "'>"
            "<input name='text' placeholder='پیام...' required>"
            "<button>➤</button></form>"
        )
    admin = "<a href='/admin'>👑<br>ادمین</a>" if u["admin"] else ""
    html = (
        "<div class='app'><div class='menu'>" + menu +
        "<a href='/profile/" + u["username"] +
        "'>👤<br>پروفایل</a>"
        "<a href='/editprofile'>⚙️<br>تنظیمات</a>"
        "<a href='/create'>➕<br>ساخت</a>" +
        admin +
        "<a href='/logout'>🚪<br>خروج</a></div>"
        "<div class='main'><div class='head'>" +
        room["emoji"] + " " + room["name"] +
        (" <span class='tick'>✓</span>"
         if room["username"] == "parto" else "") +
        "</div><div class='msgs'>" + body +
        "</div>" + form + "</div></div>"
    )
    x.close()
    return page(html)


@app.route("/send/<int:rid>", methods=["POST"])
def send(rid):
    u = me()
    if not u:
        return redirect("/")

    x = db()
    room = x.execute(
        "SELECT * FROM rooms WHERE id=?",
        (rid,)
    ).fetchone()

    if not room:
        x.close()
        return "اتاق پیدا نشد."

    if room["kind"] == "channel" and room["owner"] != u["username"]:
        x.close()
        return "فقط مالک کانال می‌تواند پیام بدهد."

    text = request.form.get("text", "").strip()
    if text:
        now = datetime.now().isoformat(timespec="seconds")
        x.execute(
            "INSERT INTO messages "
            "(room,room_id,username,text,created_at,created,reply,edited) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (rid, rid, u["username"], text[:2000],
             now, now, 0, 0)
        )
        x.commit()

    x.close()
    return redirect("/chat?room=" + str(rid))


@app.route("/create", methods=["GET", "POST"])
def create():
    u = me()
    if not u:
        return redirect("/")
    if request.method == "GET":
        return page("""
        <div class="box">
            <h2>➕ ساخت گروه یا کانال</h2>
            <form method="post">
                <input name="name" placeholder="نام" required>
                <input name="username" placeholder="آیدی" required>
                <select name="kind">
                    <option value="group">👥 گروه</option>
                    <option value="channel">📢 کانال</option>
                </select>
                <select name="emoji">
                    <option>👥</option><option>📢</option>
                    <option>⚡</option><option>👻</option>
                    <option>💻</option><option>🕷️</option>
                    <option>☠️</option><option>🤖</option>
                </select>
                <input name="bio" placeholder="توضیح">
                <button>ساخت</button>
            </form>
        </div>
        """)
    x = db()
    try:
        x.execute(
            "INSERT INTO rooms "
            "(name,username,kind,owner,emoji,bio) "
            "VALUES(?,?,?,?,?,?)",
            (request.form["name"][:80],
             request.form["username"][:40],
             request.form["kind"], u["username"],
             request.form["emoji"], request.form["bio"][:200])
        )
        x.commit()
    except sqlite3.IntegrityError:
        x.close()
        return "این آیدی قبلاً استفاده شده."
    x.close()
    return redirect("/chat")


@app.route("/reply/<int:mid>", methods=["GET", "POST"])
def reply(mid):
    u = me()
    if not u:
        return redirect("/")
    x = db()
    m = x.execute(
        "SELECT * FROM messages WHERE id=?",
        (mid,)
    ).fetchone()
    if not m:
        x.close()
        return "پیام پیدا نشد."
    if request.method == "GET":
        html = (
            "<div class='box'><h2>↩️ پاسخ</h2>"
            "<div class='card'>" + m["text"] + "</div>"
            "<form method='post'>"
            "<input name='text' placeholder='پاسخ...' required>"
            "<button>ارسال</button></form></div>"
        )
        x.close()
        return page(html)
    now = datetime.now().isoformat(timespec="seconds")
    x.execute(
        "INSERT INTO messages "
        "(room,room_id,username,text,created_at,created,reply,edited) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (m["room"], m["room"], u["username"],
         request.form.get("text", "")[:2000],
         now, now, mid, 0)
    )
    x.commit()
    room = m["room"]
    x.close()
    return redirect("/chat?room=" + str(room))


@app.route("/edit/<int:mid>", methods=["GET", "POST"])
def edit(mid):
    u = me()
    if not u:
        return redirect("/")
    x = db()
    m = x.execute(
        "SELECT * FROM messages WHERE id=?",
        (mid,)
    ).fetchone()
    if not m:
        x.close()
        return "پیام پیدا نشد."
    if m["username"] != u["username"] and not u["admin"]:
        x.close()
        return "اجازه ویرایش ندارید."
    if request.method == "GET":
        html = (
            "<div class='box'><h2>✏️ ویرایش</h2>"
            "<form method='post'>"
            "<input name='text' value='" + m["text"] + "' required>"
            "<button>ذخیره</button></form></div>"
        )
        x.close()
        return page(html)
    x.execute(
        "UPDATE messages SET text=?,edited=1 WHERE id=?",
        (request.form["text"][:2000], mid)
    )
    x.commit()
    room = m["room"]
    x.close()
    return redirect("/chat?room=" + str(room))


@app.route("/delete/<int:mid>")
def delete(mid):
    u = me()
    if not u:
        return redirect("/")
    x = db()
    m = x.execute(
        "SELECT * FROM messages WHERE id=?",
        (mid,)
    ).fetchone()
    if not m:
        x.close()
        return "پیام پیدا نشد."
    if m["username"] != u["username"] and not u["admin"]:
        x.close()
        return "اجازه حذف ندارید."
    room = m["room"]
    x.execute(
        "DELETE FROM messages WHERE id=?",
        (mid,)
    )
    x.commit()
    x.close()
    return redirect("/chat?room=" + str(room))


@app.route("/admin")
def admin():
    u = me()
    if not u or not u["admin"]:
        return "دسترسی غیرمجاز."
    x = db()
    users = x.execute(
        "SELECT * FROM users ORDER BY id DESC"
    ).fetchall()
    rooms = x.execute(
        "SELECT * FROM rooms ORDER BY id DESC"
    ).fetchall()
    html = "<div class='box'><h2>👑 کاربران</h2>"
    for z in users:
        status = "🚫 بن" if z["banned"] else "✅ فعال"
        html += (
            "<div class='card'>" + z["emoji"] +
            " @" + z["username"] + "<br>" + status +
            "<br><a href='/ban/" + str(z["id"]) +
            "'>تغییر وضعیت</a></div>"
        )
    html += "</div><div class='box'><h2>📢 اتاق‌ها</h2>"
    for r in rooms:
        html += (
            "<div class='card'>" + r["emoji"] + " " +
            r["name"] + "<br>@" + r["username"] +
            "<br>مالک: @" + r["owner"] + "</div>"
        )
    html += "</div>"
    x.close()
    return page(html)


@app.route("/ban/<int:uid>")
def ban(uid):
    u = me()
    if not u or not u["admin"]:
        return "دسترسی غیرمجاز."
    x = db()
    z = x.execute(
        "SELECT * FROM users WHERE id=?",
        (uid,)
    ).fetchone()
    if z and z["username"] != "parto":
        value = 0 if z["banned"] else 1
        x.execute(
            "UPDATE users SET banned=? WHERE id=?",
            (value, uid)
        )
        x.commit()
    x.close()
    return redirect("/admin")


init_db()

if __name__ == "__main__":
    print("PARTO STARTED")
    print("http://127.0.0.1:8080")
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False
    )
