from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import socket
import datetime
import time

app = Flask(__name__)

APP_VERSION = "2.0.0"

# --- Database connection -------------------------------------------------
# DATABASE_URL wins if set (handy for tests / local override). Otherwise the
# connection is built from the individual DB_* pieces, which come from the
# ConfigMap (host/port/name) and Secret (user/password) in Kubernetes.
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    db_user = os.environ.get("DB_USER", "postgres")
    db_password = os.environ.get("DB_PASSWORD", "postgres")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "appdb")
    DATABASE_URL = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def wait_for_db(max_retries=15, delay_seconds=2):
    """Postgres may still be starting when this pod boots, so retry briefly
    instead of crash-looping the container on the first failed connection."""
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            print(f"[startup] DB not ready (attempt {attempt}/{max_retries}): {exc}")
            time.sleep(delay_seconds)
    return False


def init_db():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()


if os.environ.get("SKIP_DB_INIT") != "true":
    if wait_for_db():
        init_db()
    else:
        print("[startup] WARNING: could not reach the database; /api/items will fail until it's up")


def mask_secret(value):
    if not value:
        return None
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


# --- Health / info ---------------------------------------------------------

@app.route("/health")
def health():
    # Used by Kubernetes liveness/readiness probes
    return jsonify({"status": "healthy"}), 200


@app.route("/info")
def info():
    config = {
        "app_name": os.environ.get("APP_NAME", "python-k8s-app"),
        "env": os.environ.get("APP_ENV", "development"),
        "log_level": os.environ.get("LOG_LEVEL", "info"),
        "db_host": os.environ.get("DB_HOST", "localhost"),
    }
    secrets_status = {
        "api_key_loaded": bool(os.environ.get("API_KEY")),
        "api_key_preview": mask_secret(os.environ.get("API_KEY")),
        "db_password_loaded": bool(os.environ.get("DB_PASSWORD")),
    }
    db_status = "unknown"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unreachable"

    return jsonify({
        "hostname": socket.gethostname(),
        "version": APP_VERSION,
        "config": config,
        "secrets_status": secrets_status,
        "db_status": db_status
    })


# --- Items API (backed by PostgreSQL) --------------------------------------

@app.route("/api/items", methods=["GET"])
def list_items():
    with SessionLocal() as session:
        rows = session.execute(
            text("SELECT id, name, description, created_at FROM items ORDER BY id DESC")
        ).mappings().all()
        items = [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    return jsonify(items)


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400

    with SessionLocal() as session:
        result = session.execute(
            text("INSERT INTO items (name, description) VALUES (:name, :description) "
                 "RETURNING id, name, description, created_at"),
            {"name": name, "description": description}
        )
        row = result.mappings().first()
        session.commit()

    return jsonify({
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }), 201


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    with SessionLocal() as session:
        result = session.execute(text("DELETE FROM items WHERE id = :id"), {"id": item_id})
        session.commit()
        if result.rowcount == 0:
            return jsonify({"error": "item not found"}), 404
    return jsonify({"deleted": item_id}), 200


# --- Root --------------------------------------------------------------

@app.route("/")
def home():
    app_name = os.environ.get("APP_NAME", "python-k8s-app")
    return jsonify({
        "message": f"{app_name} backend API is running.",
        "hostname": socket.gethostname(),
        "version": APP_VERSION,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "endpoints": ["/health", "/info", "/api/items"]
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
