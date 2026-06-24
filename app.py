import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import bcrypt
from dotenv import load_dotenv

ENV_SOURCE = None

def load_env():
    candidates = [
        os.environ.get("DOTENV_PATH"),
        r"C:\envsitealx\.env",
        r"C:\envsitealx\.env.txt",
        os.path.join(os.path.dirname(__file__), ".env"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            load_dotenv(p, override=True)
            globals()["ENV_SOURCE"] = p
            return
    load_dotenv()
    globals()["ENV_SOURCE"] = "default"

load_env()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev")

def normalize_env_value(value):
    v = (value or "").strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return v

SUPABASE_URL = normalize_env_value(os.environ.get("SUPABASE_URL")) or "https://ppewtznjwigjowgmhrge.supabase.co"
SUPABASE_URL = SUPABASE_URL.rstrip("/")
SUPABASE_KEY = normalize_env_value(os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY"))

def require_supabase_key():
    if not SUPABASE_KEY:
        raise Exception("SUPABASE_SERVICE_ROLE_KEY (ou SUPABASE_KEY) não configurada nas variáveis de ambiente")

def normalize_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = ("" if v is None else str(v)).strip().lower()
    if s in ("true", "1", "t", "yes", "y", "sim", "verdadeiro"):
        return True
    if s in ("false", "0", "f", "no", "n", "nao", "não", "falso"):
        return False
    return None

def _supa_try_get_admin(table, email, email_field):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json"
    }
    params = {
        "select": "*",
        email_field: f"eq.{email}",
        "limit": "1"
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise Exception(r.text)
    data = r.json()
    return data[0] if data else None

def supa_find_admin(email):
    require_supabase_key()
    table_candidates = []
    env_table = normalize_env_value(os.environ.get("ADMIN_TABLE"))
    if env_table:
        table_candidates.append(env_table)
    table_candidates.extend(["admins", "administradores", "Administradores", "administrador", "Administrador"])
    email_fields = ["email", "e-mail", "E-mail"]
    for table in table_candidates:
        for email_field in email_fields:
            try:
                row = _supa_try_get_admin(table, email, email_field)
            except Exception:
                continue
            if row:
                return {"table": table, "email_field": email_field, "row": row}
    return None

def normalize_admin_row(row):
    email = row.get("email") or row.get("e-mail") or row.get("E-mail")
    password_hash = row.get("password_hash") or row.get("password") or row.get("senha")
    active = (
        normalize_bool(row.get("active")) if "active" in row
        else normalize_bool(row.get("ativo")) if "ativo" in row
        else normalize_bool(row.get("Ativo")) if "Ativo" in row
        else True
    )
    return {"email": email, "password_hash": password_hash, "active": active}

# ==============================
# FUNÇÃO BUSCAR USUÁRIO
# ==============================
def supa_get_user(email):
    found = supa_find_admin(email)
    if not found:
        return None
    return normalize_admin_row(found["row"])


# ==============================
# ROTAS
# ==============================

@app.get("/")
def home():
    return render_template("home.html")

@app.get("/site")
def site_public():
    return render_template("index.html")

@app.get("/fale-conosco")
def fale_conosco():
    return render_template("index.html")

@app.get("/sobre")
def sobre_page():
    return render_template("sobre.html")

@app.get("/login")
def login_page():
    return render_template("login.html")


@app.get("/admin")
def admin_page():
    if not session.get("user"):
        return redirect("/login")
    return render_template("admin.html")


@app.post("/api/login")
def api_login():
    data = request.json
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    try:
        user = supa_get_user(email)

        if not user or user.get("active") is False:
            return jsonify({"ok": False, "error": "Credenciais inválidas"}), 401

        stored = user.get("password_hash") or ""

        try:
            valid = bcrypt.checkpw(password.encode(), stored.encode())
        except:
            valid = stored == password

        if not valid:
            return jsonify({"ok": False, "error": "Credenciais inválidas"}), 401

        session["user"] = email
        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.get("/api/env_status")
def env_status():
    return jsonify({
        "supabase_url_set": bool(SUPABASE_URL),
        "supabase_key_set": bool(SUPABASE_KEY),
        "source": os.environ.get("DOTENV_PATH") or ENV_SOURCE,
        "key_looks_service_role": (SUPABASE_KEY or "").count(".") == 2
    })

def supa_set_password(email, new_password):
    require_supabase_key()
    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(new_password.encode(), salt).decode()
    found = supa_find_admin(email)
    table = (found or {}).get("table") or "admins"
    email_field = (found or {}).get("email_field") or "email"
    row = (found or {}).get("row") or {}
    if "active" in row:
        active_field = "active"
    elif "ativo" in row:
        active_field = "ativo"
    elif "Ativo" in row:
        active_field = "Ativo"
    elif str(table).lower() in ("administradores", "administrador"):
        active_field = "Ativo"
    else:
        active_field = None
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    if found:
        patch_payload = {"password_hash": pw_hash}
        if active_field:
            patch_payload[active_field] = True
        r = requests.patch(url, headers=headers, params={email_field: f"eq.{email}"}, json=patch_payload)
        if r.status_code not in (200, 204):
            raise Exception(r.text)
        return True
    else:
        insert_payload = {email_field: email, "password_hash": pw_hash}
        if active_field:
            insert_payload[active_field] = True
        r = requests.post(url, headers=headers, json=insert_payload)
        if r.status_code not in (200, 201):
            raise Exception(r.text)
        return True

def supa_insert_feedback(row):
    require_supabase_key()
    url = f"{SUPABASE_URL}/rest/v1/feedbacks"
    headers = {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    r = requests.post(url, headers=headers, json=row)
    if r.status_code not in (200, 201):
        raise Exception(r.text)
    return r.json()

def supa_list_feedbacks(hotzone=None, page=1, page_size=10):
    require_supabase_key()
    url = f"{SUPABASE_URL}/rest/v1/feedbacks"
    headers = {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json",
        "Prefer": "count=exact"
    }
    params = {
        "select": "*",
        "order": "created_at.desc",
        "limit": str(page_size),
        "offset": str(max(0, (page - 1) * page_size)),
    }
    if hotzone:
        params["hotzone"] = f"ilike.*{hotzone}*"
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        raise Exception(r.text)
    total = None
    cr = r.headers.get("content-range") or ""
    if "/" in cr:
        try:
            total = int(cr.split("/")[-1])
        except:
            total = None
    return {"data": r.json(), "total": total}
@app.post("/api/admin/reset_password")
def reset_password():
    data = request.json or {}
    secret = (data.get("secret") or "").strip()
    email = (data.get("email") or "").strip().lower()
    new_password = data.get("new_password") or ""
    if secret != (os.environ.get("APP_SECRET") or os.environ.get("FLASK_SECRET_KEY")):
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    if not email or not new_password:
        return jsonify({"ok": False, "error": "Missing email or new_password"}), 400
    try:
        supa_set_password(email, new_password)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/feedback")
def api_feedback():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    print("api_feedback_in", data)
    nome = (data.get("nome_completo") or data.get("nome") or "").strip()
    cpf = "".join([c for c in (data.get("cpf") or "") if c.isdigit()])
    hotzone = (data.get("hotzone") or "").strip()
    allowed_hotzones = {"SANTO AMARO", "MOOCA", "PAULISTA", "NILÓPOLIS", "BANGU", "SANTA CRUZ", "OUTROS"}
    if hotzone and hotzone not in allowed_hotzones:
        hotzone = "OUTROS"
    telefone = (data.get("telefone") or "").strip()
    email = (data.get("email") or "").strip()
    tipo = (data.get("tipo") or "sugestao").strip() or "sugestao"
    if tipo not in ("sugestao", "reclamacao", "outros"):
        tipo = "outros"
    mensagem = (data.get("mensagem") or "").strip()
    try:
        satisfacao = int(data.get("satisfacao") or 10)
    except:
        satisfacao = 10
    if satisfacao < 1:
        satisfacao = 1
    if satisfacao > 10:
        satisfacao = 10
    satisfacao_db = (satisfacao + 1) // 2
    if not all([nome, cpf, hotzone, telefone, email, mensagem]):
        return jsonify({"ok": False, "error": "Dados incompletos"}), 400
    try:
        payload = {
            "nome_completo": nome,
            "cpf": cpf,
            "hotzone": hotzone,
            "telefone": telefone,
            "email": email,
            "tipo": tipo,
            "mensagem": mensagem,
            "satisfacao": satisfacao_db
        }
        print("api_feedback_payload", payload)
        created = supa_insert_feedback(payload)
        print("api_feedback_out", created)
        if request.is_json:
            return jsonify({"ok": True, "message": "Sugestão enviada com sucesso", "data": created})
        else:
            return redirect(url_for("home") + "?sent=1")
    except Exception as e:
        print("api_feedback_error", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/feedback/demo")
def api_feedback_demo():
    try:
        payload = {
            "nome_completo": "Demo",
            "cpf": "00000000000",
            "hotzone": "Centro",
            "telefone": "00000000000",
            "email": "demo@example.com",
            "tipo": "sugestao",
            "mensagem": "Inserção de teste",
            "satisfacao": 5
        }
        print("api_feedback_demo_payload", payload)
        created = supa_insert_feedback(payload)
        print("api_feedback_demo_out", created)
        return jsonify({"ok": True, "data": created})
    except Exception as e:
        print("api_feedback_demo_error", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/admin/feedbacks")
def api_admin_feedbacks():
    if not session.get("user"):
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    hotzone = (request.args.get("hotzone") or "").strip()
    try:
        page = int(request.args.get("page") or "1")
        page_size = int(request.args.get("page_size") or "10")
    except:
        page, page_size = 1, 10
    try:
        result = supa_list_feedbacks(hotzone=hotzone or None, page=page, page_size=page_size)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
