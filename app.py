import os
import base64
import secrets
import json
from flask import Flask, request, redirect, render_template, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Users database
USERS = {
    "arka": "1234",
    "shresth": "pars",
    "maulik": "para",
    "siddheeka": "ray",
    "admin": "adminpass"
}

# Logged-in users with session tokens
logged_in_users = {}

# Log file
LOG_FILE = "logs/user_log.txt"
os.makedirs("static/selfies", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Geofence check (expanded by ~20m)
def is_within_geofence(lat, lon):
    return 22.2 <= lat <= 22.6 and 88.1 <= lon <= 88.6

@app.route("/")
def home():
    return redirect("/login")
@app.route("/login", methods=["GET", "POST"])
def login():
    # Load flag from latest_volume.json
    flag = 0
    try:
        with open("latest_volume.json", "r") as f:
            data = json.load(f)
            flag = int(data.get("Flag", 0))
    except Exception:
        pass

    if flag != 1:
        return render_template("error.html", code=405, message="Login Disabled: No one near entrance.")

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        selfie_data = request.form.get("selfie")
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")

        # Validate location
        try:
            lat = float(latitude)
            lon = float(longitude)
            if not is_within_geofence(lat, lon):
                return render_template("error.html", code=401, message="Access Denied: You are outside the permitted location.")
        except (ValueError, TypeError):
            return render_template("error.html", code=402, message="Invalid or missing location data.")

        # Validate selfie
        if not selfie_data or not selfie_data.startswith("data:image"):
            return render_template("error.html", code=403, message="Selfie Required: Please capture a selfie to proceed.")

        # Authenticate
        if username in USERS and USERS[username] == password:
            new_token = secrets.token_hex(8)

            # Invalidate previous session
            if username in logged_in_users and logged_in_users[username]["status"] == "logged_in":
                logged_in_users[username]["status"] = "logged_out"
                with open(LOG_FILE, "a") as f:
                    f.write(f"{username}, logged_out, {datetime.now()}\n")

            # Save selfie
            img_data = selfie_data.split(",")[1]
            img_bytes = base64.b64decode(img_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"static/selfies/{username}_{timestamp}.png"
            with open(filename, "wb") as f:
                f.write(img_bytes)

            # Mark as logged in
            logged_in_users[username] = {
                "login_time": datetime.now(),
                "status": "logged_in",
                "token": new_token
            }
            session["username"] = username
            session["token"] = new_token

            # Log entry with location
            with open(LOG_FILE, "a") as f:
                f.write(f"{username}, logged_in, {datetime.now()}, lat={lat}, lon={lon}\n")

            return redirect("/dashboard")

        return render_template("error.html", code=404, message="Invalid Credentials: Username or password is incorrect.")

    return render_template("login.html")
@app.route("/dashboard")
def dashboard():
    username = session.get("username")
    token = session.get("token")
    if not username or username not in logged_in_users:
        return redirect("/login")
    user_data = logged_in_users[username]
    if user_data["status"] != "logged_in" or user_data["token"] != token:
        session.pop("username", None)
        session.pop("token", None)
        return redirect("/login")
    # --- Load latest sensor data ---
    blynk_volume = None
    try:
        with open("latest_volume.json", "r") as f:
            blynk_volume = json.load(f)
    except Exception:
        blynk_volume = None  # File not ready yet
    return render_template("dashboard.html", username=username, blynk_volume=blynk_volume)

@app.route("/logout")
def logout():
    username = session.get("username")
    if username:
        logged_in_users[username]["status"] = "logged_out"
        with open(LOG_FILE, "a") as f:
            f.write(f"{username}, logged_out, {datetime.now()}\n")
        session.pop("username", None)
        session.pop("token", None)
    return redirect("/login")
@app.route("/admin")
def admin_panel():
    selfies = os.listdir("static/selfies")
    entrance_message = ""
    try:
        with open("latest_volume.json", "r") as f:
            data = json.load(f)
            if int(data.get("Flag", 0)) == 1:
                entrance_message = "Someone at entrance"
    except Exception:
        pass
    return render_template("admin.html", users=logged_in_users, selfies=selfies, entrance_message=entrance_message)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
