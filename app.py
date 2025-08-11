import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv
import requests
import json
from flask import make_response  

load_dotenv()

API_BASE = os.getenv("API_BASE")
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


def validate_keystroke_consistency(attempts, threshold=0.7):
    """
    Valida que los patrones de keystroke sean consistentes entre intentos
    """
    if len(attempts) < 3:
        return False, "Se requieren al menos 3 intentos"
    
    # Verificar contraseñas iguales
    passwords = [attempt.get('password', '') for attempt in attempts]
    if not all(pwd == passwords[0] for pwd in passwords):
        return False, "Las contraseñas no coinciden"
    
    # Verificar que todos los intentos tengan datos de keystroke
    if any(not attempt.get('keystroke_timings') for attempt in attempts):
        return False, "Faltan datos de keystroke en algunos intentos"
    
    # Calcular similitud entre intentos
    similarities = []
    for i in range(len(attempts) - 1):
        for j in range(i + 1, len(attempts)):
            sim = calculate_similarity(attempts[i], attempts[j])
            similarities.append(sim)
    
    avg_similarity = sum(similarities) / len(similarities) if similarities else 0
    
    if avg_similarity < threshold:
        return False, f"Patrón inconsistente (similitud: {avg_similarity:.2%})"
    
    return True, f"Patrón válido (similitud: {avg_similarity:.2%})"


def calculate_similarity(attempt1, attempt2):
    """
    Calcula similitud entre dos intentos de keystroke
    """
    timings1 = attempt1.get('keystroke_timings', [])
    timings2 = attempt2.get('keystroke_timings', [])
    
    if len(timings1) != len(timings2) or len(timings1) == 0:
        return 0.0
    
    total_diff = 0
    valid_comparisons = 0
    
    for i in range(min(len(timings1), len(timings2))):
        t1 = timings1[i]
        t2 = timings2[i]
        
        if t1.get('key') == t2.get('key'):
            dwell1 = t1.get('release_time', 0) - t1.get('press_time', 0)
            dwell2 = t2.get('release_time', 0) - t2.get('press_time', 0)
            
            diff = abs(dwell1 - dwell2)
            total_diff += diff
            valid_comparisons += 1
    
    if valid_comparisons == 0:
        return 0.0
    
    avg_diff = total_diff / valid_comparisons
    max_allowed_diff = 200  # ms
    
    similarity = max(0.0, 1.0 - (avg_diff / max_allowed_diff))
    return similarity


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
    keystroke_data = request.form.get("keystroke_data")

    # Preparar datos como form-data (no multipart/form-data)
    data = {
        "username": email,
        "password": password,
    }
    
    # Agregar keystroke_data si existe
    if keystroke_data:
        data["keystroke_data"] = keystroke_data

    try:
        # Enviar como form-data a FastAPI
        r = requests.post(
            f"{API_BASE}/api/users/login/",
            data=data,  # Cambié de 'files' a 'data'
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if r.status_code != 200:
            detail = r.json().get("detail", "Credenciales inválidas")
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
    # Limpiar cualquier sesión de práctica anterior
    session.pop('practice_attempts', None)
    return render_template("register.html")

@app.post("/register/practice")
def register_practice():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        # Asegurarnos de que los datos tienen la estructura correcta
        if 'password' not in data or 'keystroke_timings' not in data:
            return jsonify({"error": "Datos de keystroke incompletos"}), 400
        
        # Obtener intentos previos de la sesión
        practice_attempts = session.get('practice_attempts', [])
        
        # Agregar el nuevo intento (asegurando el formato)
        practice_attempts.append({
            'password': data['password'],
            'keystroke_timings': data['keystroke_timings'],
            'total_time': data.get('total_time', 0)
        })
        
        # Guardar en sesión (asegurando que se persista)
        session['practice_attempts'] = practice_attempts
        session.modified = True  # Esto fuerza a Flask a guardar los cambios
        
        attempt_number = len(practice_attempts)
        
        if attempt_number < 3:
            return jsonify({
                "success": True,
                "message": f"Intento {attempt_number} completado",
                "attempts_remaining": 3 - attempt_number,
                "can_register": False
            })
        
        # Validar consistencia después del tercer intento
        is_valid, message = validate_keystroke_consistency(practice_attempts)
        
        return jsonify({
            "success": is_valid,
            "message": message,
            "attempts_remaining": 0,
            "can_register": is_valid,
            "reset_required": not is_valid
        })
            
    except Exception as e:
        return jsonify({"error": f"Error del servidor: {str(e)}"}), 500

@app.post("/register")
def do_register():
    # Obtener datos del formulario
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    secretu = request.form.get("secretu") or None
    passwordu = request.form.get("passwordu", "")
    tpu_json = request.form.get("tpu_json")
    
    if not tpu_json:
        flash("Debes completar la práctica de contraseña", "danger")
        return redirect(url_for("register"))
    
    try:
        tpu_data = json.loads(tpu_json)
    except json.JSONDecodeError:
        flash("Error en los datos de keystroke", "danger")
        return redirect(url_for("register"))
    
    # Validar que la contraseña final coincide con la práctica
    if not passwordu or passwordu != tpu_data.get('password', ''):
        flash("La contraseña final no coincide con la práctica", "danger")
        return redirect(url_for("register"))
    
    # Preparar payload para la API
    payload = {
        "name": name,
        "email": email,
        "passwordu": passwordu,
        "secretu": secretu,
        "tpu": {
            "password": tpu_data['password'],
            "keystroke_timings": tpu_data['keystroke_timings'],
            "total_time": tpu_data['total_time']
        }
    }
    
    try:
        # Enviar a tu API
        r = requests.post(f"{API_BASE}/api/users/registrar/", json=payload, timeout=15)
        
        if r.status_code not in (200, 201):
            detail = r.json().get("detail", "No se pudo registrar") 
            flash(f"Error: {detail}", "danger")
            return redirect(url_for("register"))
        
        flash("Cuenta creada exitosamente", "success")
        
        # Auto-login
        files = {"username": (None, email), "password": (None, passwordu)}
        lr = requests.post(f"{API_BASE}/api/users/login/", files=files, timeout=10)
        
        if lr.status_code == 200:
            data = lr.json()
            session["token"] = data["access_token"]
            session["user"] = data["user_info"]
            return redirect(url_for("dashboard"))
        
        return redirect(url_for("login"))
        
    except Exception as e:
        flash(f"Error de conexión: {e}", "danger")
        return redirect(url_for("register"))
    
@app.route('/dashboard')
def dashboard():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    return render_template("dashboard.html", user=session["user"])



@app.post("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada", "info")
    return redirect(url_for("login"))

# ---------- Endpoint para debug de keystroke ----------
@app.get("/keystroke/debug")
def keystroke_debug():
    """Endpoint para debugging de patrones de keystroke"""
    if not session.get("token"):
        return redirect(url_for("login"))
    
    practice_attempts = session.get('practice_attempts', [])
    return jsonify({
        "attempts": len(practice_attempts),
        "data": practice_attempts
    })

# ---------- Validación en tiempo real de keystroke ----------
@app.post("/keystroke/validate")
def validate_keystroke():
    """
    Valida un patrón de keystroke contra los patrones guardados del usuario
    """
    if not session.get("token"):
        return jsonify({"error": "No autorizado"}), 401
    
    try:
        data = request.get_json()
        keystroke_data = data.get('keystroke_data')
        
        if not keystroke_data:
            return jsonify({"error": "Datos de keystroke requeridos"}), 400
        
        # Aquí podrías comparar contra los patrones guardados del usuario
        # Por ahora, solo validamos que el patrón sea válido
        analysis = analyze_pattern(keystroke_data)
        
        return jsonify({
            "valid": analysis['valid'],
            "analysis": analysis,
            "message": "Patrón analizado correctamente"
        })
        
    except Exception as e:
        return jsonify({"error": f"Error del servidor: {str(e)}"}), 500


def analyze_pattern(keystroke_data):
    """
    Analiza un patrón individual de keystroke
    """
    timings = keystroke_data.get('keystroke_timings', [])
    
    if len(timings) == 0:
        return {"valid": False, "reason": "Sin datos de timing"}
    
    # Calcular métricas básicas
    dwell_times = []
    flight_times = []
    
    for timing in timings:
        dwell = timing.get('release_time', 0) - timing.get('press_time', 0)
        if dwell > 0:
            dwell_times.append(dwell)
    
    for i in range(len(timings) - 1):
        flight = timings[i + 1].get('press_time', 0) - timings[i].get('release_time', 0)
        flight_times.append(flight)
    
    # Validaciones básicas
    if not dwell_times:
        return {"valid": False, "reason": "No hay dwell times válidos"}
    
    avg_dwell = sum(dwell_times) / len(dwell_times)
    avg_flight = sum(flight_times) / len(flight_times) if flight_times else 0
    
    # Criterios de validación
    valid = True
    issues = []
    
    if avg_dwell < 30:
        valid = False
        issues.append("Dwell time promedio demasiado corto")
    
    if avg_dwell > 800:
        valid = False
        issues.append("Dwell time promedio demasiado largo")
    
    extreme_dwells = sum(1 for d in dwell_times if d > 1000 or d < 20)
    if extreme_dwells > len(dwell_times) * 0.3:
        valid = False
        issues.append("Demasiados dwell times extremos")
    
    return {
        "valid": valid,
        "issues": issues,
        "metrics": {
            "avg_dwell": round(avg_dwell, 2),
            "avg_flight": round(avg_flight, 2),
            "total_keys": len(timings),
            "valid_keys": len(dwell_times)
        }
    }

# Agregar estas rutas a tu app.py

@app.route("/vault")
def vault():
    """Página principal de la bóveda"""
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("vault.html", user=session["user"])

@app.route("/verify-vault-access", methods=["POST"])
def verify_vault_access():
    """Verificar acceso con contraseña maestra"""
    if "user" not in session:
        return jsonify({"success": False, "message": "No autenticado"})
    
    password = request.form.get("password")
    keystroke_data = request.form.get("keystroke_data")
    
    # Verificar contraseña usando tu API
    try:
        data = {
            "username": session["user"]["email"],
            "password": password,
            "keystroke_data": keystroke_data
        }
        
        r = requests.post(f"{API_BASE}/api/users/login/", data=data)
        
        if r.status_code == 200:
            return jsonify({"success": True, "message": "Acceso autorizado"})
        else:
            return jsonify({"success": False, "message": "Verificación fallida"})
            
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

def analyze_pattern(keystroke_data):
    """
    Analiza un patrón individual de keystroke
    """
    timings = keystroke_data.get('keystroke_timings', [])
    
    if len(timings) == 0:
        return {"valid": False, "reason": "Sin datos de timing"}
    
    # Calcular métricas básicas
    dwell_times = []
    
    for timing in timings:
        dwell = timing.get('release_time', 0) - timing.get('press_time', 0)
        if dwell > 0:
            dwell_times.append(dwell)
    
    # Validaciones básicas
    if not dwell_times:
        return {"valid": False, "reason": "No hay dwell times válidos"}
    
    avg_dwell = sum(dwell_times) / len(dwell_times)
    
    # Criterios de validación
    valid = True
    reason = "Patrón válido"
    
    if avg_dwell < 30:
        valid = False
        reason = "Dwell time promedio demasiado corto"
    elif avg_dwell > 800:
        valid = False
        reason = "Dwell time promedio demasiado largo"
    
    extreme_dwells = sum(1 for d in dwell_times if d > 1000 or d < 20)
    if extreme_dwells > len(dwell_times) * 0.3:
        valid = False
        reason = "Demasiados dwell times extremos"
    
    return {
        "valid": valid,
        "reason": reason,
        "avg_dwell": round(avg_dwell, 2),
        "total_keys": len(timings)
    }

@app.route("/save-password", methods=["POST"])
def save_password():
    """Guardar nueva contraseña en la bóveda"""
    if "user" not in session:
        return jsonify({"success": False, "message": "No autenticado"})
    
    site_name = request.form.get("site_name")
    credentials = request.form.get("credentials")
    
    data = {
        "site_name": site_name,
        "credentials": credentials,
        "user_id": session["user"]["id"]
    }
    
    try:
        r = requests.post(f"{API_BASE}/api/users/vault/passwords/", data=data)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route("/get-passwords")
def get_passwords():
    """Obtener lista de contraseñas del usuario"""
    if "user" not in session:
        return jsonify({"success": False, "message": "No autenticado"})
    
    try:
        r = requests.get(f"{API_BASE}/api/users/vault/passwords/{session['user']['id']}")
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route('/decrypt-password/<int:password_id>', methods=['POST'])
def decrypt_password(password_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        password = request.form.get('password')
        keystroke_data = request.form.get('keystroke_data')
        
        print(f"🔍 DEBUG: Desencriptando password_id={password_id}")
        print(f"🔍 DEBUG: password length={len(password) if password else 0}")
        print(f"🔍 DEBUG: user_id={session['user']['id']}")
        
        headers = {
            'Authorization': f'Bearer {session["token"]}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'password': password,
            'keystroke_data': keystroke_data,
            'user_id': session['user']['id']
        }
        
        response = requests.post(
            f"{API_BASE}/api/passwords/decrypt/{password_id}",
            data=data,
            headers=headers
        )
        
        print(f"🔍 DEBUG: API response status={response.status_code}")
        print(f"🔍 DEBUG: API response={response.text}")
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({
                'success': False, 
                'message': f'Error API: {response.status_code}'
            })
        
    except Exception as e:
        print(f"🔍 DEBUG: Exception={str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route("/delete-password/<int:password_id>", methods=["DELETE"])
def delete_password(password_id):
    """Eliminar una contraseña"""
    if "user" not in session:
        return jsonify({"success": False, "message": "No autenticado"})
    
    try:
        r = requests.delete(f"{API_BASE}/api/users/vault/passwords/{password_id}?user_id={session['user']['id']}")
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route("/upload-file", methods=["POST"])
def upload_file():
    """Subir archivo a la bóveda"""
    if "user" not in session:
        return jsonify({"success": False, "message": "No autenticado"})
    
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No se seleccionó archivo"})
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "Archivo vacío"})
    
    try:
        files = {"file": (file.filename, file.stream, file.content_type)}
        data = {"user_id": session["user"]["id"]}
        
        r = requests.post(f"{API_BASE}/api/users/vault/files/", files=files, data=data)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route("/get-files")
def get_files():
    """Obtener lista de archivos del usuario"""
    if "user" not in session:
        return jsonify({"success": False, "message": "No autenticado"})
    
    try:
        r = requests.get(f"{API_BASE}/api/users/vault/files/{session['user']['id']}")
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})

@app.route("/download-file/<int:file_id>")
def download_file(file_id):
    """Descargar archivo de la bóveda"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    try:
        r = requests.get(f"{API_BASE}/api/users/vault/files/download/{file_id}?user_id={session['user']['id']}")
        
        if r.status_code == 200:
            response = make_response(r.content)
            response.headers["Content-Type"] = r.headers.get("Content-Type", "application/octet-stream")
            response.headers["Content-Disposition"] = r.headers.get("Content-Disposition", "attachment")
            return response
        else:
            flash("Error al descargar archivo", "danger")
            return redirect(url_for("vault"))
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for("vault"))

@app.route("/delete-file/<int:file_id>", methods=["DELETE"])
def delete_file(file_id):
    """Eliminar archivo de la bóveda"""
    if "user" not in session:
        return jsonify({"success": False, "message": "No autenticado"})
    
    try:
        r = requests.delete(f"{API_BASE}/api/users/vault/files/{file_id}?user_id={session['user']['id']}")
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {e}"})
    

if __name__ == "__main__":
    app.run(debug=True, port=5000)