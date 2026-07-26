import json
import os
import uuid
from datetime import datetime
from urllib.parse import quote

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import bcrypt
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

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

def simplify_text(value):
    return (
        (value or "").strip().lower()
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ç", "c")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
    )

def normalize_feedback_type(value, default="sugestao"):
    raw = (value or "").strip().lower()
    if not raw:
        raw = default
    simplified = simplify_text(raw)
    mapping = {
        "sugestao": "sugestao",
        "reclamacao": "reclamacao",
        "outro": "outro",
        "outros": "outro",
    }
    return mapping.get(simplified, "outro")

def normalize_feedback_filter_type(value):
    simplified = simplify_text(value)
    if not simplified:
        return ""
    if simplified in {"parceiro", "ser parceiro", "parceiro alx"}:
        return "parceiro"
    return normalize_feedback_type(simplified, default="")

SUPABASE_URL = normalize_env_value(os.environ.get("SUPABASE_URL")) or "https://ppewtznjwigjowgmhrge.supabase.co"
SUPABASE_URL = SUPABASE_URL.rstrip("/")
SUPABASE_KEY = normalize_env_value(os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY"))
SUPABASE_STORAGE_BUCKET = normalize_env_value(os.environ.get("SUPABASE_STORAGE_BUCKET")) or "feedback-anexos"
FEEDBACK_ATTACHMENT_MAX_MB = int(normalize_env_value(os.environ.get("FEEDBACK_ATTACHMENT_MAX_MB")) or "10")
FEEDBACK_ATTACHMENT_MAX_BYTES = FEEDBACK_ATTACHMENT_MAX_MB * 1024 * 1024
FEEDBACK_ATTACHMENT_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
FEEDBACK_ATTACHMENT_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
ATTACHMENT_MARKER_START = "[[ALX_ATTACHMENT]]"
ATTACHMENT_MARKER_END = "[[/ALX_ATTACHMENT]]"
TYPE_MARKER_START = "[[ALX_FEEDBACK_TYPE]]"
TYPE_MARKER_END = "[[/ALX_FEEDBACK_TYPE]]"

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


def expects_json_response():
    return request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"


def append_attachment_marker(message, attachment_meta):
    if not attachment_meta:
        return message or ""
    payload = {
        "name": attachment_meta.get("name"),
        "path": attachment_meta.get("path"),
        "mime": attachment_meta.get("mime"),
        "size": attachment_meta.get("size"),
    }
    return f"{(message or '').rstrip()}\n\n{ATTACHMENT_MARKER_START}{json.dumps(payload, ensure_ascii=True)}{ATTACHMENT_MARKER_END}"


def append_feedback_type_marker(message, original_type):
    normalized = normalize_feedback_type(original_type)
    if normalized != "outro":
        return message or ""
    payload = {"tipo_original": "outros"}
    return f"{(message or '').rstrip()}\n\n{TYPE_MARKER_START}{json.dumps(payload, ensure_ascii=True)}{TYPE_MARKER_END}"


def extract_feedback_type_marker(message):
    text = message or ""
    start = text.find(TYPE_MARKER_START)
    end = text.find(TYPE_MARKER_END)
    if start == -1 or end == -1 or end < start:
        return None
    raw_json = text[start + len(TYPE_MARKER_START):end]
    try:
        data = json.loads(raw_json)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return normalize_feedback_type(data.get("tipo_original"))


def extract_attachment_marker(message):
    text = message or ""
    start = text.find(ATTACHMENT_MARKER_START)
    end = text.find(ATTACHMENT_MARKER_END)
    if start == -1 or end == -1 or end < start:
        return None
    raw_json = text[start + len(ATTACHMENT_MARKER_START):end]
    try:
        data = json.loads(raw_json)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "name": data.get("name"),
        "path": data.get("path"),
        "mime": data.get("mime"),
        "size": data.get("size"),
    }


def strip_attachment_marker(message):
    text = message or ""
    start = text.find(ATTACHMENT_MARKER_START)
    end = text.find(ATTACHMENT_MARKER_END)
    if start == -1 or end == -1 or end < start:
        return text.strip()
    return (text[:start] + text[end + len(ATTACHMENT_MARKER_END):]).strip()


def strip_feedback_type_marker(message):
    text = message or ""
    start = text.find(TYPE_MARKER_START)
    end = text.find(TYPE_MARKER_END)
    if start == -1 or end == -1 or end < start:
        return text.strip()
    return (text[:start] + text[end + len(TYPE_MARKER_END):]).strip()


def attachment_column_error(response_text):
    text = (response_text or "").lower()
    return "could not find" in text and "anexo_" in text


def feedback_type_constraint_error(response_text):
    text = (response_text or "").lower()
    return "feedbacks_tipo_check" in text or ("check constraint" in text and "tipo" in text)


def candidate_feedback_types(value):
    normalized = normalize_feedback_type(value)
    if normalized == "sugestao":
        return ["sugestao"]
    if normalized == "reclamacao":
        return ["reclamacao"]
    return ["outro", "outros", "sugestao"]


def storage_headers(content_type="application/octet-stream"):
    return {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": content_type,
    }


def upload_feedback_attachment(file_storage):
    require_supabase_key()
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    original_name = file_storage.filename or ""
    safe_name = secure_filename(original_name)
    if not safe_name:
        raise ValueError("Arquivo invalido")

    extension = os.path.splitext(safe_name)[1].lower()
    mime_type = (file_storage.mimetype or "application/octet-stream").lower()
    if extension not in FEEDBACK_ATTACHMENT_ALLOWED_EXTENSIONS or mime_type not in FEEDBACK_ATTACHMENT_ALLOWED_MIME_TYPES:
        raise ValueError("Envie apenas PDF, JPG, JPEG, PNG ou WEBP")

    content = file_storage.read()
    file_storage.stream.seek(0)
    size = len(content)
    if size == 0:
        raise ValueError("O arquivo enviado esta vazio")
    if size > FEEDBACK_ATTACHMENT_MAX_BYTES:
        raise ValueError(f"O arquivo deve ter no maximo {FEEDBACK_ATTACHMENT_MAX_MB} MB")

    object_path = f"feedbacks/{datetime.utcnow():%Y/%m/%d}/{uuid.uuid4().hex}_{safe_name}"
    encoded_path = quote(object_path, safe="/")
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{encoded_path}"
    headers = {
        **storage_headers(mime_type),
        "x-upsert": "false",
    }
    response = requests.post(url, headers=headers, data=content)
    if response.status_code not in (200, 201):
        raise Exception(response.text)

    return {
        "name": original_name,
        "path": object_path,
        "mime": mime_type,
        "size": size,
    }


def create_signed_storage_url(object_path, expires_in=3600):
    require_supabase_key()
    if not object_path:
        return None
    encoded_path = quote(object_path, safe="/")
    url = f"{SUPABASE_URL}/storage/v1/object/sign/{SUPABASE_STORAGE_BUCKET}/{encoded_path}"
    response = requests.post(url, headers=build_supabase_headers(prefer_representation=False), json={"expiresIn": expires_in})
    if response.status_code != 200:
        return None
    data = response.json() or {}
    signed_url = data.get("signedURL") or data.get("signedUrl") or data.get("url")
    if not signed_url:
        return None
    if signed_url.startswith("http://") or signed_url.startswith("https://"):
        return signed_url
    if signed_url.startswith("/"):
        return f"{SUPABASE_URL}/storage/v1{signed_url}"
    return f"{SUPABASE_URL}/storage/v1/{signed_url}"


def normalize_feedback_row(row):
    marker_meta = extract_attachment_marker(row.get("mensagem"))
    marker_type = extract_feedback_type_marker(row.get("mensagem"))
    attachment_name = row.get("anexo_nome") or (marker_meta or {}).get("name")
    attachment_path = row.get("anexo_path") or (marker_meta or {}).get("path")
    attachment_type = row.get("anexo_tipo") or (marker_meta or {}).get("mime")
    attachment_size = row.get("anexo_tamanho") or (marker_meta or {}).get("size")
    attachment_url = row.get("anexo_url")
    if attachment_path:
        attachment_url = create_signed_storage_url(attachment_path) or attachment_url
    clean_message = strip_feedback_type_marker(strip_attachment_marker(row.get("mensagem")))
    resolved_type = marker_type or row.get("tipo")
    if not marker_type and (row.get("hotzone") or "").strip().upper() == "PARCEIRO ALX" and normalize_feedback_type(row.get("tipo")) == "sugestao":
        resolved_type = "parceiro"
    return {
        **row,
        "tipo": resolved_type,
        "mensagem": clean_message,
        "anexo_nome": attachment_name,
        "anexo_path": attachment_path,
        "anexo_tipo": attachment_type,
        "anexo_tamanho": attachment_size,
        "anexo_url": attachment_url,
        "tem_anexo": bool(attachment_name or attachment_path or attachment_url),
    }


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

@app.get("/parceiro-alx")
@app.get("/fale-conosco/parceiro")
def parceiro_alx():
    return render_template("partner.html", partner_mode=True, partner_hotzone="PARCEIRO ALX")

@app.get("/99food")
def page_99food():
    return render_template("99food.html")

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
    table = (found or {}).get("table") or get_admin_table_name()
    row = (found or {}).get("row") or {}
    fields = resolve_admin_field_names(table, row)
    email_field = (found or {}).get("email_field") or fields["email_field"]
    active_field = fields["active_field"]
    password_field = fields["password_field"]
    hierarchy_field = fields["hierarchy_field"]

    payload = {
        password_field: pw_hash,
        hierarchy_field: hierarchy,
    }
    if active_field:
        payload[active_field] = True

    if found:
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

def supa_insert_feedback(row, attachment_meta=None):
    require_supabase_key()
    url = f"{SUPABASE_URL}/rest/v1/feedbacks"
    headers = {
        **build_supabase_headers(prefer_representation=True),
        "Prefer": "return=representation"
    }
    base_payload = dict(row)
    original_type = base_payload.get("tipo")
    payload_variants = []
    for tipo in candidate_feedback_types(base_payload.get("tipo")):
        payload = dict(base_payload)
        payload["tipo"] = tipo
        payload["mensagem"] = base_payload.get("mensagem")
        if normalize_feedback_type(original_type) == "outro" and tipo == "sugestao":
            payload["mensagem"] = append_feedback_type_marker(payload.get("mensagem"), original_type)
        if attachment_meta:
            payload["mensagem"] = append_attachment_marker(payload.get("mensagem"), attachment_meta)
            payload["anexo_nome"] = attachment_meta.get("name")
            payload["anexo_path"] = attachment_meta.get("path")
            payload["anexo_tipo"] = attachment_meta.get("mime")
            payload["anexo_tamanho"] = attachment_meta.get("size")
        payload_variants.append(payload)

    last_error = None
    for payload in payload_variants:
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code in (200, 201):
            created_rows = r.json() or []
            return [normalize_feedback_row(item) for item in created_rows]

        if attachment_meta and attachment_column_error(r.text):
            fallback_payload = dict(payload)
            fallback_payload["mensagem"] = append_attachment_marker(payload.get("mensagem"), attachment_meta)
            for key in ("anexo_nome", "anexo_path", "anexo_tipo", "anexo_tamanho"):
                fallback_payload.pop(key, None)
            fallback_response = requests.post(url, headers=headers, json=fallback_payload)
            if fallback_response.status_code in (200, 201):
                created_rows = fallback_response.json() or []
                return [normalize_feedback_row(item) for item in created_rows]
            last_error = fallback_response.text
            if feedback_type_constraint_error(last_error):
                continue
            raise Exception(last_error)

        last_error = r.text
        if feedback_type_constraint_error(last_error):
            continue
        raise Exception(last_error)

    raise Exception(last_error or "Nao foi possivel inserir o feedback")


def supa_list_feedbacks(
    hotzone=None,
    tipo=None,
    busca=None,
    satisfacao_min=None,
    satisfacao_max=None,
    data_inicial=None,
    data_final=None,
    attachment_mode=None,
    order_by="created_at.desc",
    page=1,
    page_size=10
):
    require_supabase_key()
    url = f"{SUPABASE_URL}/rest/v1/feedbacks"
    headers = {
        **build_supabase_headers(prefer_representation=False),
        "Prefer": "count=exact"
    }
    params = [
        ("select", "*"),
        ("order", order_by or "created_at.desc"),
        ("limit", str(page_size)),
        ("offset", str(max(0, (page - 1) * page_size))),
    ]
    if hotzone:
        params.append(("hotzone", f"eq.{hotzone}"))
    if tipo:
        normalized_filter_type = normalize_feedback_filter_type(tipo)
        if normalized_filter_type == "parceiro":
            params.append(("hotzone", "eq.PARCEIRO ALX"))
            params.append(("tipo", "eq.sugestao"))
        elif normalized_filter_type == "outro":
            params.append(("tipo", "in.(outro,outros)"))
        else:
            params.append(("tipo", f"eq.{normalize_feedback_type(tipo)}"))
    if busca:
        busca_safe = busca.replace(",", " ").strip()
        search_terms = ",".join([
            f"nome_completo.ilike.*{busca_safe}*",
            f"email.ilike.*{busca_safe}*",
            f"cpf.ilike.*{busca_safe}*",
            f"telefone.ilike.*{busca_safe}*",
            f"mensagem.ilike.*{busca_safe}*",
        ])
        params.append(("or", f"({search_terms})"))
    if satisfacao_min is not None:
        params.append(("satisfacao", f"gte.{satisfacao_min}"))
    if satisfacao_max is not None:
        params.append(("satisfacao", f"lte.{satisfacao_max}"))
    if data_inicial:
        params.append(("created_at", f"gte.{data_inicial}T00:00:00"))
    if data_final:
        params.append(("created_at", f"lte.{data_final}T23:59:59"))
    if attachment_mode == "with":
        params.append(("mensagem", "ilike.*ALX_ATTACHMENT*"))
    elif attachment_mode == "without":
        params.append(("mensagem", "not.ilike.*ALX_ATTACHMENT*"))
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
    rows = [normalize_feedback_row(item) for item in (r.json() or [])]
    return {"data": rows, "total": total}
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
    attachment = request.files.get("anexo")
    nome = (data.get("nome_completo") or data.get("nome") or "").strip()
    cpf = "".join([c for c in (data.get("cpf") or "") if c.isdigit()])
    hotzone = (data.get("hotzone") or "").strip()
    allowed_hotzones = {"SANTO AMARO", "MOOCA", "PAULISTA", "NILÓPOLIS", "BANGU", "SANTA CRUZ", "OUTROS", "PARCEIRO ALX"}
    if hotzone and hotzone not in allowed_hotzones:
        hotzone = "OUTROS"
    telefone = (data.get("telefone") or "").strip()
    email = (data.get("email") or "").strip()
    tipo = normalize_feedback_type(data.get("tipo"))
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
        attachment_meta = None
        if attachment and getattr(attachment, "filename", ""):
            attachment_meta = upload_feedback_attachment(attachment)
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
        created = supa_insert_feedback(payload, attachment_meta=attachment_meta)
        if expects_json_response():
            return jsonify({"ok": True, "message": "Sugestão enviada com sucesso", "data": created})
        return redirect(url_for("home") + "?sent=1")
    except Exception as e:
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
    tipo = normalize_feedback_filter_type(request.args.get("tipo")) if (request.args.get("tipo") or "").strip() else ""
    busca = (request.args.get("busca") or "").strip()
    attachment_mode = (request.args.get("attachment_mode") or "").strip()
    sort = (request.args.get("sort") or "created_at.desc").strip() or "created_at.desc"
    data_inicial = (request.args.get("data_inicial") or "").strip()
    data_final = (request.args.get("data_final") or "").strip()
    try:
        page = int(request.args.get("page") or "1")
        page_size = int(request.args.get("page_size") or "10")
        satisfacao_min = request.args.get("satisfacao_min")
        satisfacao_max = request.args.get("satisfacao_max")
        satisfacao_min = int(satisfacao_min) if satisfacao_min not in (None, "") else None
        satisfacao_max = int(satisfacao_max) if satisfacao_max not in (None, "") else None
    except:
        page, page_size, satisfacao_min, satisfacao_max = 1, 10, None, None
    try:
        result = supa_list_feedbacks(
            hotzone=hotzone or None,
            tipo=tipo or None,
            busca=busca or None,
            satisfacao_min=satisfacao_min,
            satisfacao_max=satisfacao_max,
            data_inicial=data_inicial or None,
            data_final=data_final or None,
            attachment_mode=attachment_mode or None,
            order_by=sort,
            page=page,
            page_size=page_size
        )
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
