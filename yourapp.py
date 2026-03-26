from flask import Flask, render_template, request, redirect
import stripe
import sqlite3
import uuid
import os
from werkzeug.utils import secure_filename
from flask import session

app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- Config ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

stripe.api_key = "sk_test_51TBJi9CWLpTu3fjIi7Rrys9ZeaW20qnPyTJbVAT9KFHZkFZfzkj7Q93JlbRsqkSdTGedLcu3MJYg6wjvabCC49Jw00XkdXRidI"

# --- Helpers ---
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file):
    if file and allowed_file(file.filename):
        filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        return f"{UPLOAD_FOLDER}/{filename}"
    return ""

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()

    # Users
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT
    )
    """)

    #ticket
    c.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       event_id INTEGER,
       ticket_number TEXT,
       amount INTEGER,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Products
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        price INTEGER,
        description TEXT,
        image_url TEXT,
        is_promoted INTEGER DEFAULT 0
    )
    """)
    # Events
    c.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    location TEXT,
    date TEXT,
    description TEXT,
    image_url TEXT,
    price INTEGER,
    zip_code TEXT,
    street TEXT,
    city TEXT,
    organizer TEXT,
    state TEXT,
    country TEXT,
    is_promoted INTEGER DEFAULT 0
)
""")
    # Transactions
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER,
        status TEXT
    )
    """)
    # Payment Links
    c.execute("""
    CREATE TABLE IF NOT EXISTS payment_links (
        id TEXT PRIMARY KEY,
        amount INTEGER
    )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Home / Products ---
@app.route("/")
def home():
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()
    c.execute("SELECT id, name, price, description, image_url FROM products")
    products = c.fetchall()
    conn.close()

    
    html = "<h1>Product Marketplace</h1>"
    html += '<a href="/register">register</a> | <a href="/login">login</a> | <a href="/logout">Logout</a><br><br>'
    html += '<a href="/post-product">Post Product</a> | <a href="/events">Events</a><br><br>'

    for p in products:
        html += "<div style='border:1px solid #ccc;padding:10px;margin:10px'>"
        if p[4]:
            html += f"<img src='/{p[4]}' width='200'><br>"
        html += f"<h3><a href='/product/{p[0]}'>{p[1]}</a></h3>"
        html += f"<p>Price: ${p[2]}</p>"
        html += f"<p>{p[3]}</p>"
        html += "</div>"

    return html

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = sqlite3.connect("payments.db")
        c = conn.cursor()

        # check if user exists
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        existing = c.fetchone()

        if existing:
            conn.close()
            return "User already exists"

        # save user
        c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
        conn.commit()
        conn.close()

        return redirect("/login")

    return """
    <h1>Register</h1>
    <form method="POST">
        <input name="email" placeholder="Email" required><br><br>
        <input name="password" type="password" placeholder="Password" required><br><br>
        <button type="submit">Register</button>
    </form>
    """

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = sqlite3.connect("payments.db")
        c = conn.cursor()

        c.execute("SELECT id FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            return redirect("/")
        else:
            return "Invalid credentials"

    return """
    <h1>Login</h1>
    <form method="POST">
        <input name="email" placeholder="Email" required><br><br>
        <input name="password" type="password" placeholder="Password" required><br><br>
        <button type="submit">Login</button>
    </form>
    """

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")

@app.route("/product/<int:product_id>")
def product_page(product_id):
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()
    c.execute("SELECT id, name, price, description, image_url FROM products WHERE id=?", (product_id,))
    product = c.fetchone()
    conn.close()
    if not product:
        return "Product not found"

    html = f"""
    <h1>{product[1]}</h1>
    <img src="/{product[4]}" width="300"><br><br>
    <p>{product[3]}</p>
    <h3>Price: ${product[2]}</h3>
    <form action="/buy/{product[0]}" method="POST">
        <button type="submit">Buy Now</button>
    </form>
    """
    return html

@app.route("/post-product", methods=["GET", "POST"])
def post_product():
    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        description = request.form.get("description")
        image = request.files.get("image")
        image_path = save_file(image)

        conn = sqlite3.connect("payments.db")
        c = conn.cursor()
        c.execute("""
        INSERT INTO products (user_id, name, price, description, image_url)
        VALUES (?, ?, ?, ?, ?)
        """, (1, name, price, description, image_path))
        conn.commit()
        conn.close()
        return redirect("/")

    return """
    <h1>Post Product</h1>
    <form method="POST" enctype="multipart/form-data">
        <input name="name" placeholder="Product name" required><br><br>
        <input name="price" placeholder="Price" required><br><br>
        <input type="file" name="image"><br><br>
        <textarea name="description" placeholder="Description"></textarea><br><br>
        <button type="submit">Post Product</button>
    </form>
    """

# --- Buy Product ---
@app.route("/buy/<int:product_id>", methods=["POST"])
def buy(product_id):
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()
    c.execute("SELECT name, price FROM products WHERE id=?", (product_id,))
    product = c.fetchone()
    conn.close()
    if not product:
        return "Product not found"

    name, price = product
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": name},
                "unit_amount": int(price) * 100
            },
            "quantity": 1
        }],
        mode="payment",
        success_url="http://127.0.0.1:5000/success",
        cancel_url="http://127.0.0.1:5000",
    )
    return redirect(session.url)

# --- Events ---
@app.route("/events")
def events():
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()

    #if "user_id" in session:
     # html += '<a href="/post-event">Post Event</a>'
    #else:
     # html += '<a href="/login">Login to Post Event</a>'

    c.execute("""
    SELECT id, title, location, date, city, state, country, image_url 
    FROM events 
    ORDER BY is_promoted DESC, date ASC
    """)

    events = c.fetchall()
    conn.close()

    html = "<h1>Events</h1>"
    html += '<a href="/">Home</a><br><br>'
    html += '<a href="/post-event">Post Event</a> | <a href="/search">Search event</a> | <a href="/">Products</a><br><br>'

    for e in events:
        html += "<div style='border:1px solid #ccc;padding:10px;margin:10px'>"

        # ✅ image (INSIDE loop)
        if e[7]:
            html += f"<img src='/{e[7]}' width='200'><br>"

        html += f"<h3><a href='/event/{e[0]}'>{e[1]}</a></h3>"
        html += f"<p>{e[2]}</p>"
        html += f"<p>{e[3]}</p>"

        # ✅ address preview
        html += f"<p><b>{e[4]}, {e[5]}, {e[6]}</b></p>"

        html += "</div>"

    return html

@app.route("/event/<int:event_id>")
def event_detail(event_id):
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()
    c.execute("SELECT * FROM events WHERE id=?", (event_id,))
    event = c.fetchone()
    conn.close()

    if not event:
        return "Event not found"

    html = f"""
    <h1>{event[1]}</h1>
    <img src='/{event[5]}' width='300'><br><br>
    <p><b>Location:</b> {event[9]}</p>
    <p><b>Date:</b> {event[3]}</p>
    <p><b>Price:</b> ${event[6]}</p>
    <p><b>Address:</b> {event[7]}, {event[8]}, {event[9]}, {event[10]}, {event[11]}</p>
    <p>{event[4]}</p>
    <form action="/buy-ticket/{event[0]}" method="POST">
        <button type="submit">Buy Ticket</button>
    </form>
    """
    return html

# --- Country and state options ---
COUNTRIES = ["United States", "Canada", "Nigeria", "United Kingdom", "India"]
STATES = {
    "United States": ["California", "New York", "Texas", "Florida"],
    "Canada": ["Ontario", "Quebec", "British Columbia"],
    "Nigeria": ["Lagos", "Abuja", "Kano"],
    "United Kingdom": ["England", "Scotland", "Wales"],
    "India": ["Maharashtra", "Delhi", "Karnataka"]
}

from flask import session

@app.route("/post-event", methods=["GET", "POST"])
def post_event():

    # 🔐 require login
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        # --- form data ---
        title = request.form.get("title")
        location = request.form.get("location")
        date = request.form.get("date")
        description = request.form.get("description")
        price = request.form.get("price")

        # --- address fields ---
        zip_code = request.form.get("zip_code")
        street = request.form.get("street")
        city = request.form.get("city")
        state = request.form.get("state")
        country = request.form.get("country")

        # --- image upload ---
        image = request.files.get("image")
        image_path = ""

        if image and image.filename != "" and allowed_file(image.filename):
            filename = str(uuid.uuid4()) + "_" + secure_filename(image.filename)

            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(filepath)

            # ✅ VERY IMPORTANT (correct path for browser)
            image_path = f"static/uploads/{filename}"

        # --- save to database ---
        conn = sqlite3.connect("payments.db")
        c = conn.cursor()

        c.execute("""
            INSERT INTO events 
            (title, location, date, description, image_url, price, zip_code, street, city, state, country)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, location, date, description,
            image_path, price,
            zip_code, street, city, state, country
        ))

        conn.commit()
        conn.close()

        return redirect("/events")

    # --- show form ---
    return render_template("post_event.html", countries=COUNTRIES, states=STATES)

    # --- Buy Ticket ---
@app.route("/buy-ticket/<int:event_id>", methods=["POST"])
def buy_ticket(event_id):
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()
    c.execute("SELECT title, price FROM events WHERE id=?", (event_id,))
    event = c.fetchone()
    conn.close()

    if not event:
        return "Event not found"

    title, price = event

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": title},
                "unit_amount": int(price) * 100
            },
            "quantity": 1
        }],
        mode="payment",

        # ✅ metadata goes here
        metadata={
            "event_id": str(event_id)
        },

        success_url="http://127.0.0.1:5000/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://127.0.0.1:5000/events",
    )

    return redirect(session.url)

# --- Search ---
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    conn = sqlite3.connect("payments.db")
    c = conn.cursor()

    c.execute("""
        SELECT id, title, city, state, country, organizer
        FROM events
        WHERE 
            LOWER(title) LIKE LOWER(?) OR
            LOWER(city) LIKE LOWER(?) OR
            LOWER(state) LIKE LOWER(?) OR
            LOWER(country) LIKE LOWER(?) OR
            LOWER(organizer) LIKE LOWER(?)
    """, (f"%{query}%",)*5)

    results = c.fetchall()
    conn.close()

    return render_template("search.html", query=query, results=results)

# --- Payment Success ---
@app.route("/success")
def success():

    session_id = request.args.get("session_id")

    if not session_id:
        return "Missing session ID"

    # get session from Stripe
    checkout_session = stripe.checkout.Session.retrieve(session_id)

    event_id = checkout_session.metadata.get("event_id")
    amount = checkout_session.amount_total // 100

    # 🎟 generate ticket number
    ticket_number = str(uuid.uuid4()).split("-")[0].upper()

    # save ticket
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()

    c.execute("""
        INSERT INTO tickets (event_id, ticket_number, amount)
        VALUES (?, ?, ?)
    """, (event_id, ticket_number, amount))

    conn.commit()
    conn.close()

    return f"""
    <h1>Payment Successful 🎉</h1>
    <h2>Your Ticket Number:</h2>
    <h1>{ticket_number}</h1>
    <a href="/events">Back to Events</a>
    """
# --- Dashboard ---
@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()
    c.execute("SELECT * FROM transactions")
    transactions = c.fetchall()
    conn.close()

    html = "<h1>Payment Dashboard</h1>"
    html += "<table border=1>"
    html += "<tr><th>ID</th><th>Amount</th><th>Status</th></tr>"
    for t in transactions:
        html += f"<tr><td>{t[0]}</td><td>{t[1]}</td><td>{t[2]}</td></tr>"
    html += "</table>"
    return html

if __name__ == "__main__":
    app.run(debug=True)
