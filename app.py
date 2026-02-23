from flask import Flask, render_template, request, redirect, session, jsonify, flash
from db import get_connection
import requests
from datetime import datetime
import hashlib
import os
from flask_cloudflared import run_with_cloudflared

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "climate06")
run_with_cloudflared(app)

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY  = os.environ.get("WEATHER_API_KEY", "f9f9634345344dcd62cfbcb5873f7c4b")
CITIES   = ["Chennai", "Delhi", "New York", "London", "Tokyo"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    """Simple decorator to protect routes."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            flash("Please log in first.", "warning")
            return redirect("/")
        return f(*args, **kwargs)
    return decorated

def fetch_real_time_weather(city):
    """Fetch weather from OpenWeatherMap and return a dict ready for DB insert."""
    url = (
        f"http://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&units=metric&appid={API_KEY}"
    )
    try:
        response = requests.get(url, timeout=5).json()
    except requests.exceptions.RequestException:
        return None

    if response.get("cod") != 200:
        return None

    return {
        "country":     response.get("sys", {}).get("country", "Unknown"),
        "region":      city,
        "date":        datetime.utcfromtimestamp(response["dt"]).strftime("%Y-%m-%d"),
        "temperature": response["main"]["temp"],
        "rainfall":    response.get("rain", {}).get("1h", 0),
        "co2":         400,   # placeholder – no free CO₂ API
        "humidity":    response["main"]["humidity"],
    }

def save_weather_to_db(data):
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            """INSERT INTO climate_data
               (country, region, date, temperature, rainfall, co2, humidity)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (data["country"], data["region"], data["date"],
             data["temperature"], data["rainfall"], data["co2"], data["humidity"]),
        )
        con.commit()
    finally:
        cur.close()
        con.close()

# ── LOGIN / LOGOUT ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect("/dashboard")

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Both fields are required.", "danger")
            return render_template("login.html")

        con = get_connection()
        try:
            cur = con.cursor(dictionary=True)
            # Supports both plain-text passwords (legacy) and sha256 hashed ones
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
        finally:
            cur.close()
            con.close()

        if user and (user["password"] == password or
                     user["password"] == hash_password(password)):
            session["user"]    = user["name"]
            session["user_id"] = user["id"]
            session["role"]    = user["role"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect("/dashboard")

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/")

# ── DASHBOARD ──────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    con = get_connection()
    try:
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM climate_data ORDER BY id DESC LIMIT 50")
        records = cur.fetchall()

        # Summary stats
        cur.execute("""
            SELECT
                COUNT(*)                  AS total_records,
                ROUND(AVG(temperature),1) AS avg_temp,
                ROUND(AVG(co2),1)         AS avg_co2,
                ROUND(AVG(humidity),1)    AS avg_humidity,
                COUNT(DISTINCT country)   AS total_countries
            FROM climate_data
        """)
        stats = cur.fetchone()
    finally:
        cur.close()
        con.close()

    return render_template("dashboard.html",
                           user=session["user"],
                           role=session.get("role"),
                           records=records,
                           stats=stats)

# ── JSON ENDPOINT (kept for AJAX / future use) ─────────────────────────────────
@app.route("/get_latest_data")
@login_required
def get_latest_data():
    con = get_connection()
    try:
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM climate_data ORDER BY id DESC LIMIT 50")
        data = cur.fetchall()
    finally:
        cur.close()
        con.close()

    # Convert date objects to strings for JSON serialisation
    for row in data:
        if hasattr(row.get("date"), "isoformat"):
            row["date"] = row["date"].isoformat()
    return jsonify(data)

# ── ADD ────────────────────────────────────────────────────────────────────────
@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        con = get_connection()
        try:
            cur = con.cursor()
            cur.execute(
                """INSERT INTO climate_data
                   (country, region, date, temperature, rainfall, co2, humidity)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    request.form["country"].strip(),
                    request.form["region"].strip(),
                    request.form["date"],
                    float(request.form["temperature"]),
                    float(request.form["rainfall"]),
                    float(request.form["co2"]),
                    float(request.form["humidity"]),
                ),
            )
            con.commit()
        finally:
            cur.close()
            con.close()

        flash("Climate record added successfully!", "success")
        return redirect("/dashboard")

    return render_template("add.html")

# ── UPDATE ─────────────────────────────────────────────────────────────────────
@app.route("/update/<int:id>", methods=["GET", "POST"])
@login_required
def update(id):
    con = get_connection()
    try:
        cur = con.cursor(dictionary=True)

        if request.method == "POST":
            cur.execute(
                """UPDATE climate_data
                   SET country=%s, region=%s, date=%s,
                       temperature=%s, rainfall=%s, co2=%s, humidity=%s
                   WHERE id=%s""",
                (
                    request.form["country"].strip(),
                    request.form["region"].strip(),
                    request.form["date"],
                    float(request.form["temperature"]),
                    float(request.form["rainfall"]),
                    float(request.form["co2"]),
                    float(request.form["humidity"]),
                    id,
                ),
            )
            con.commit()
            flash("Record updated successfully!", "success")
            return redirect("/dashboard")

        cur.execute("SELECT * FROM climate_data WHERE id = %s", (id,))
        data = cur.fetchone()
    finally:
        cur.close()
        con.close()

    if not data:
        flash("Record not found.", "danger")
        return redirect("/dashboard")

    return render_template("update.html", data=data)

# ── DELETE ─────────────────────────────────────────────────────────────────────
@app.route("/delete/<int:id>")
@login_required
def delete(id):
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute("DELETE FROM climate_data WHERE id = %s", (id,))
        con.commit()
    finally:
        cur.close()
        con.close()

    flash("Record deleted.", "info")
    return redirect("/dashboard")

# ── REPORT ─────────────────────────────────────────────────────────────────────
@app.route("/report")
@login_required
def report():
    con = get_connection()
    try:
        cur = con.cursor(dictionary=True)
        cur.execute("""
            SELECT
                country,
                ROUND(AVG(temperature), 2) AS avg_temp,
                ROUND(AVG(co2), 2)         AS avg_co2,
                ROUND(AVG(humidity), 2)    AS avg_humidity,
                ROUND(AVG(rainfall), 2)    AS avg_rainfall,
                COUNT(*)                   AS total_rows
            FROM climate_data
            GROUP BY country
            ORDER BY avg_temp DESC
        """)
        report_data = cur.fetchall()
    finally:
        cur.close()
        con.close()

    return render_template("report.html", report=report_data)

# ── RESEARCHERS ────────────────────────────────────────────────────────────────
@app.route("/researchers")
@login_required
def researchers():
    con = get_connection()
    try:
        cur = con.cursor(dictionary=True)
        # Never expose passwords to the template
        cur.execute("SELECT id, name, email, role FROM users")
        users = cur.fetchall()
    finally:
        cur.close()
        con.close()

    return render_template("researchers.html", users=users)

# ── LIVE WEATHER FETCH ─────────────────────────────────────────────────────────
@app.route("/fetch_live", methods=["GET", "POST"])
@login_required
def fetch_live():
    if request.method == "POST":
        city = request.form.get("city", "Chennai")
        data = fetch_real_time_weather(city)
        if data:
            save_weather_to_db(data)
            flash(f"Live weather for {city} saved to database!", "success")
        else:
            flash(f"Could not fetch weather for '{city}'. Check your API key.", "danger")
        return redirect("/dashboard")

    return render_template("fetch_live.html", cities=CITIES)

# ── REGISTER ──────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect("/dashboard")

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        role     = request.form.get("role", "viewer")

        if not all([name, email, password, confirm]):
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")

        con = get_connection()
        try:
            cur = con.cursor(dictionary=True)
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash("An account with that email already exists.", "danger")
                return render_template("register.html")

            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s,%s,%s,%s)",
                (name, email, password, role)
            )
            con.commit()
        finally:
            cur.close()
            con.close()

        flash("Account created! You can now log in.", "success")
        return redirect("/")

    return render_template("register.html")


# ── PROFILE ────────────────────────────────────────────────────────────────────
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    con = get_connection()
    try:
        cur = con.cursor(dictionary=True)

        if request.method == "POST":
            action = request.form.get("action")

            if action == "update_info":
                name  = request.form.get("name", "").strip()
                email = request.form.get("email", "").strip()
                if not name or not email:
                    flash("Name and email are required.", "danger")
                else:
                    cur.execute(
                        "UPDATE users SET name=%s, email=%s WHERE id=%s",
                        (name, email, session["user_id"])
                    )
                    con.commit()
                    session["user"] = name
                    flash("Profile updated successfully!", "success")

            elif action == "change_password":
                current  = request.form.get("current_password", "")
                new_pw   = request.form.get("new_password", "")
                confirm  = request.form.get("confirm_password", "")

                cur.execute("SELECT password FROM users WHERE id=%s", (session["user_id"],))
                row = cur.fetchone()

                if row["password"] != current and row["password"] != hash_password(current):
                    flash("Current password is incorrect.", "danger")
                elif new_pw != confirm:
                    flash("New passwords do not match.", "danger")
                elif len(new_pw) < 6:
                    flash("Password must be at least 6 characters.", "danger")
                else:
                    cur.execute(
                        "UPDATE users SET password=%s WHERE id=%s",
                        (new_pw, session["user_id"])
                    )
                    con.commit()
                    flash("Password changed successfully!", "success")

        cur.execute(
            "SELECT id, name, email, role FROM users WHERE id=%s",
            (session["user_id"],)
        )
        user_data = cur.fetchone()

        # Stats for this session
        cur.execute("SELECT COUNT(*) AS total FROM climate_data")
        db_stats = cur.fetchone()

    finally:
        cur.close()
        con.close()

    return render_template("profile.html", user_data=user_data, db_stats=db_stats)


# ── CHART DATA (JSON for Chart.js) ────────────────────────────────────────────
@app.route("/chart_data")
@login_required
def chart_data():
    con = get_connection()
    try:
        cur = con.cursor(dictionary=True)
        cur.execute("""
            SELECT
                country,
                ROUND(AVG(temperature), 1) AS avg_temp,
                ROUND(AVG(co2), 1)         AS avg_co2,
                ROUND(AVG(humidity), 1)    AS avg_humidity,
                ROUND(AVG(rainfall), 1)    AS avg_rainfall
            FROM climate_data
            GROUP BY country
            ORDER BY avg_temp DESC
        """)
        rows = cur.fetchall()
    finally:
        cur.close()
        con.close()

    return jsonify({
        "labels":      [r["country"]     for r in rows],
        "temperature": [r["avg_temp"]    for r in rows],
        "co2":         [r["avg_co2"]     for r in rows],
        "humidity":    [r["avg_humidity"] for r in rows],
        "rainfall":    [r["avg_rainfall"] for r in rows],
    })


# ── RUN ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(port=5000)