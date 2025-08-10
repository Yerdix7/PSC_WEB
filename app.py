import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
import requests

load_dotenv()

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000/api")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

app = Flask(__name__)
app.secret_key = SECRET_KEY


# -------------- Helpers ----------------
def api_headers():
    hdrs = {"Accept": "application/json"}
    token = session.get("token")
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    return hdrs


# -------------- Rutas -------------------

@app.get("/")
def home():
    if session.get("token"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.get("/login")
def login():
    return render_template("login.html")

@app.post("/login")
def do_login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    # FastAPI espera OAuth2PasswordRequestForm (form-data) con username/password
    files = {
        "username": (None, email),
        "password": (None, password),
    }
    try:
        r = requests.post(f"{API_BASE}/users/login/", files=files, timeout=10)
        if r.status_code != 200:
            detail = r.json().get("detail", "Credenciales inválidas") if r.headers.get("content-type","").startswith("application/json") else r.text
            flash(f"Error: {detail}", "danger")
            return redirect(url_for("login"))

        data = r.json()
        session["token"] = data["access_token"]
        session["user"] = data["user_info"]
        flash("Sesión iniciada", "success")
        return redirect(url_for("dashboard"))
    except Exception as e:
        flash(f"Error de conexión: {e}", "danger")
        return redirect(url_for("login"))

@app.get("/register")
def register():
    return render_template("register.html")

@app.post("/register")
def do_register():
    """Registra usuario + envía tpu (keystroke) capturado con JS."""
    name = request.form.get("name","").strip()
    email = request.form.get("email","").strip().lower()
    passwordu = request.form.get("passwordu","")
    secretu = request.form.get("secretu") or None
    # El hidden viene como string JSON:
    tpu_json = request.form.get("tpu_json")  # puede ser None o "{}"

    payload = {
        "name": name,
        "email": email,
        "passwordu": passwordu,
        "secretu": secretu,
        "tpu": None
    }
    # si vino un JSON válido, pásalo tal cual:
    try:
        if tpu_json and len(tpu_json) > 2:
            # NO lo parses aquí; la API lo aceptará como JSON si vas con requests.json=...
            import json
            payload["tpu"] = json.loads(tpu_json)
    except Exception:
        pass

    try:
        r = requests.post(f"{API_BASE}/users/registrar/", json=payload, timeout=10)
        if r.status_code not in (200, 201):
            detail = r.json().get("detail","No se pudo registrar") if r.headers.get("content-type","").startswith("application/json") else r.text
            flash(f"Error: {detail}", "danger")
            return redirect(url_for("register"))

        flash("Cuenta creada", "success")

        # Auto-login: llama al login de la API con las mismas credenciales
        files = {"username": (None, email), "password": (None, passwordu)}
        lr = requests.post(f"{API_BASE}/users/login/", files=files, timeout=10)
        if lr.status_code == 200:
            data = lr.json()
            session["token"] = data["access_token"]
            session["user"] = data["user_info"]
            return redirect(url_for("dashboard"))

        return redirect(url_for("login"))
    except Exception as e:
        flash(f"Error de conexión: {e}", "danger")
        return redirect(url_for("register"))

@app.get("/dashboard")
def dashboard():
    if not session.get("token"):
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session.get("user"))

@app.post("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada", "info")
    return redirect(url_for("login"))


# ---------- (Opcional) Validación de keystroke en backend ----------
# Cuando creen un endpoint en su API (ej. POST /users/keystroke/verify),
# aquí solo sería:
#
# @app.post("/keystroke-verify")
# def ks_verify():
#     if not session.get("token"):
#         return redirect(url_for("login"))
#     tpu_json = request.form.get("tpu_json")
#     r = requests.post(f"{API_BASE}/users/keystroke/verify", headers=api_headers(), json={"tpu": json.loads(tpu_json)})
#     ...
# -------------------------------------------------------------------


if __name__ == "__main__":
    app.run(debug=True, port=5000)
