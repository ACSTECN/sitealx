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
    hierarchy = (
        row.get("hierarquia")
        or row.get("hierarchy")
        or row.get("role")
        or row.get("nivel")
        or row.get("hier")
    )
    return {"email": email, "password_hash": password_hash, "active": active, "hierarchy": hierarchy}


def get_admin_table_name():
    return normalize_env_value(os.environ.get("ADMIN_TABLE")) or "admins"


def resolve_admin_field_names(table, row=None):
    row = row or {}

    if "email" in row:
        email_field = "email"
    elif "e-mail" in row:
        email_field = "e-mail"
    elif "E-mail" in row:
        email_field = "E-mail"
    else:
        email_field = "email"

    if "active" in row:
        active_field = "active"
    elif "ativo" in row:
        active_field = "ativo"
    elif "Ativo" in row:
        active_field = "Ativo"
    elif str(table).lower() in ("administradores", "administrador"):
        active_field = "Ativo"
    else:
        active_field = "active"

    if "password_hash" in row:
        password_field = "password_hash"
    elif "password" in row:
        password_field = "password"
    elif "senha" in row:
        password_field = "senha"
    else:
        password_field = "password_hash"

    hierarchy_candidates = [
        normalize_env_value(os.environ.get("ADMIN_HIERARCHY_FIELD")),
        "hierarchy",
        "hierarquia",
        "role",
        "nivel",
        "hier",
    ]
    hierarchy_field = next((field for field in hierarchy_candidates if field and field in row), None)
    if not hierarchy_field:
        hierarchy_field = next((field for field in hierarchy_candidates if field), "hierarquia")

    return {
        "email_field": email_field,
        "active_field": active_field,
        "password_field": password_field,
        "hierarchy_field": hierarchy_field,
    }


def build_supabase_headers(prefer_representation=True):
    headers = {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json",
    }
    if prefer_representation:
        headers["Prefer"] = "return=representation"
    return headers


def candidate_hierarchy_fields(row=None):
    row = row or {}
    candidates = [
        normalize_env_value(os.environ.get("ADMIN_HIERARCHY_FIELD")),
        "hierarchy",
        "hierarquia",
        "role",
        "nivel",
        "hier",
    ]
    ordered = []
    for field in candidates:
        if not field:
            continue
        if field in row and field not in ordered:
            ordered.append(field)
    for field in candidates:
        if field and field not in ordered:
            ordered.append(field)
    return ordered


def is_missing_column_error(response_text, field_name):
    text = (response_text or "").lower()
    return "could not find" in text and str(field_name or "").lower() in text


def supa_write_admin_payload(table, email_field, email_filter, payload, method="PATCH"):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = build_supabase_headers(prefer_representation=True)
    params = {email_field: f"eq.{email_filter}"} if email_filter else None

    if method == "PATCH":
        request_fn = lambda body: requests.patch(url, headers=headers, params=params, json=body)
    else:
        request_fn = lambda body: requests.post(url, headers=headers, json=body)

    hierarchy_fields = candidate_hierarchy_fields()
    hierarchy_field = next((field for field in hierarchy_fields if field in payload), None)

    attempt_payloads = []
    if hierarchy_field:
        for field in hierarchy_fields:
            body = dict(payload)
            value = body.pop(hierarchy_field)
            body[field] = value
            attempt_payloads.append((field, body))
    else:
        attempt_payloads.append((None, dict(payload)))

    last_error = None
    for field_name, body in attempt_payloads:
        r = request_fn(body)
        if r.status_code in (200, 201, 204):
            rows = r.json() if r.text.strip() else []
            return {"rows": rows, "hierarchy_field": field_name}
        if field_name and is_missing_column_error(r.text, field_name):
            last_error = r.text
            continue
        raise Exception(r.text)

    raise Exception(last_error or "Nao foi possivel gravar a hierarquia na tabela admins")

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
    row = (found or {}).get("row") or {}
    fields = resolve_admin_field_names(table, row)
    email_field = (found or {}).get("email_field") or fields["email_field"]
    active_field = fields["active_field"]
    password_field = fields["password_field"]
    if found:
        patch_payload = {password_field: pw_hash}
        if active_field:
            patch_payload[active_field] = True
        supa_write_admin_payload(table, email_field, email, patch_payload, method="PATCH")
        return True
    else:
        insert_payload = {email_field: email, password_field: pw_hash}
        if active_field:
            insert_payload[active_field] = True
        supa_write_admin_payload(table, email_field, None, insert_payload, method="POST")
        return True


def supa_upsert_admin_user(email, password, hierarchy):
    require_supabase_key()
    email = (email or "").strip().lower()
    hierarchy = (hierarchy or "").strip()
    if not email or not password or not hierarchy:
        raise ValueError("Email, senha e hierarquia são obrigatórios")

    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(password.encode(), salt).decode()
    found = supa_find_admin(email)
    table = (found or {}).get("table") or normalize_env_value(os.environ.get("ADMIN_TABLE")) or "admins"
    row = (found or {}).get("row") or {}
    fields = resolve_admin_field_names(table, row)
    email_field = (found or {}).get("email_field") or fields["email_field"]
    active_field = fields["active_field"]
    password_field = fields["password_field"]
    hierarchy_field = fields["hierarchy_field"]

    payload = {
        password_field: pw_hash,
        hierarchy_field: hierarchy,
        write_result = supa_write_admin_payload(table, email_field, email, payload, method="PATCH")
        resolved_hierarchy_field = write_result["hierarchy_field"] or hierarchy_field
        response_rows = write_result["rows"] or [dict(row, **payload)]
        result_row = response_rows[0] if response_rows else dict(row, **payload)
        return {
            "created": False,
            "email": result_row.get(email_field, email),
            "hierarchy": result_row.get(resolved_hierarchy_field, hierarchy),
            "active": normalize_bool(result_row.get(active_field)) if active_field else True,
        }

    insert_payload = {
        email_field: email,
        **payload,
    }
    write_result = supa_write_admin_payload(table, email_field, None, insert_payload, method="POST")
    resolved_hierarchy_field = write_result["hierarchy_field"] or hierarchy_field
    response_rows = write_result["rows"] or [insert_payload]
    result_row = response_rows[0] if response_rows else insert_payload
    return {
        "created": True,
        "email": result_row.get(email_field, email),
        "hierarchy": result_row.get(resolved_hierarchy_field, hierarchy),
        "active": normalize_bool(result_row.get(active_field)) if active_field else True,
    }


def supa_list_admin_users():
    require_supabase_key()
    table = get_admin_table_name()
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = build_supabase_headers(prefer_representation=False)
    params = {
        "select": "*",
        "order": "created_at.desc",
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        raise Exception(r.text)

    rows = r.json() or []
    result = []
    for row in rows:
        fields = resolve_admin_field_names(table, row)
        result.append({
            "email": row.get(fields["email_field"]),
            "hierarchy": row.get(fields["hierarchy_field"]),
            "active": normalize_bool(row.get(fields["active_field"])) if fields["active_field"] else True,
            "created_at": row.get("created_at"),
        })
    return result


def supa_update_admin_user(original_email, email, hierarchy, password=None):
    require_supabase_key()
    original_email = (original_email or "").strip().lower()
    email = (email or "").strip().lower()
    hierarchy = (hierarchy or "").strip()
    password = password or ""
    if not original_email or not email or not hierarchy:
        raise ValueError("Email original, email e hierarquia são obrigatórios")

    found = supa_find_admin(original_email)
    if not found:
        raise ValueError("Login não encontrado")

    table = found["table"]
    row = found["row"] or {}
    fields = resolve_admin_field_names(table, row)
    email_field = found.get("email_field") or fields["email_field"]
    hierarchy_field = fields["hierarchy_field"]
    password_field = fields["password_field"]
    active_field = fields["active_field"]

    payload = {
        email_field: email,
        hierarchy_field: hierarchy,
    }
    if password:
        salt = bcrypt.gensalt()
        payload[password_field] = bcrypt.hashpw(password.encode(), salt).decode()
    if active_field and active_field not in payload and active_field in row:
        payload[active_field] = normalize_bool(row.get(active_field))

    write_result = supa_write_admin_payload(table, email_field, original_email, payload, method="PATCH")
    resolved_hierarchy_field = write_result["hierarchy_field"] or hierarchy_field
    response_rows = write_result["rows"] or [dict(row, **payload)]
    result_row = response_rows[0] if response_rows else dict(row, **payload)
    return {
        "email": result_row.get(email_field, email),
        "hierarchy": result_row.get(resolved_hierarchy_field, hierarchy),
        "active": normalize_bool(result_row.get(active_field)) if active_field else True,
        "created_at": result_row.get("created_at"),
    }


def supa_set_admin_active(email, active):
    require_supabase_key()
    email = (email or "").strip().lower()
    found = supa_find_admin(email)
    if not found:
        raise ValueError("Login não encontrado")

    table = found["table"]
    row = found["row"] or {}
    fields = resolve_admin_field_names(table, row)
    email_field = found.get("email_field") or fields["email_field"]
    active_field = fields["active_field"]
    if not active_field:
        raise ValueError("Campo de status não encontrado na tabela de admins")

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = build_supabase_headers(prefer_representation=True)
    r = requests.patch(url, headers=headers, params={email_field: f"eq.{email}"}, json={active_field: bool(active)})
    if r.status_code not in (200, 204):
        raise Exception(r.text)
    response_rows = r.json() if r.text.strip() else [dict(row, **{active_field: bool(active)})]
    result_row = response_rows[0] if response_rows else dict(row, **{active_field: bool(active)})
    return {
        "email": result_row.get(email_field, email),
        "hierarchy": result_row.get(fields["hierarchy_field"]),
        "active": normalize_bool(result_row.get(active_field)),
        "created_at": result_row.get("created_at"),
    }


def supa_delete_admin_user(email):
    require_supabase_key()
    email = (email or "").strip().lower()
    found = supa_find_admin(email)
    if not found:
        raise ValueError("Login não encontrado")

    table = found["table"]
    row = found["row"] or {}
    fields = resolve_admin_field_names(table, row)
    email_field = found.get("email_field") or fields["email_field"]
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = build_supabase_headers(prefer_representation=True)
    r = requests.delete(url, headers=headers, params={email_field: f"eq.{email}"})
    if r.status_code not in (200, 204):
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
        **build_supabase_headers(prefer_representation=False),
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


@app.post("/api/admin/users")
def api_admin_users_create():
    if not session.get("user"):
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    hierarchy = (data.get("hierarquia") or data.get("hierarchy") or "").strip()

    if not email or not password or not hierarchy:
        return jsonify({"ok": False, "error": "Informe email, senha e hierarquia"}), 400
    if "@" not in email:
        return jsonify({"ok": False, "error": "Email inválido"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "A senha deve ter pelo menos 6 caracteres"}), 400

    try:
        result = supa_upsert_admin_user(email, password, hierarchy)
        action = "criado" if result["created"] else "atualizado"
        return jsonify({
            "ok": True,
            "message": f"Login {action} com sucesso",
            "data": result
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/admin/users")
def api_admin_users_list():
    if not session.get("user"):
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    try:
        return jsonify({"ok": True, "data": supa_list_admin_users()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.put("/api/admin/users")
def api_admin_users_update():
    if not session.get("user"):
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    data = request.get_json(silent=True) or {}
    original_email = (data.get("original_email") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()
    hierarchy = (data.get("hierarquia") or data.get("hierarchy") or "").strip()
    password = data.get("password") or ""

    if not original_email or not email or not hierarchy:
        return jsonify({"ok": False, "error": "Informe email original, email e hierarquia"}), 400
    if "@" not in email:
        return jsonify({"ok": False, "error": "Email inválido"}), 400
    if password and len(password) < 6:
        return jsonify({"ok": False, "error": "A senha deve ter pelo menos 6 caracteres"}), 400

    try:
        result = supa_update_admin_user(original_email, email, hierarchy, password=password)
        return jsonify({"ok": True, "message": "Login atualizado com sucesso", "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.patch("/api/admin/users/status")
def api_admin_users_status():
    if not session.get("user"):
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    active = normalize_bool(data.get("active"))
    if not email or active is None:
        return jsonify({"ok": False, "error": "Informe email e status"}), 400

    try:
        result = supa_set_admin_active(email, active)
        return jsonify({"ok": True, "message": "Status atualizado com sucesso", "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.delete("/api/admin/users")
def api_admin_users_delete():
    if not session.get("user"):
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "Informe o email"}), 400

    try:
        supa_delete_admin_user(email)
        return jsonify({"ok": True, "message": "Login excluído com sucesso"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
