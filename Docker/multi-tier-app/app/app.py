import os
import time

import psycopg2
import redis
from flask import Flask, render_template, request, redirect, jsonify

app = Flask(__name__)

# --- Config from environment variables (never hardcode secrets) ---
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("POSTGRES_DB", "notesdb")
DB_USER = os.environ.get("POSTGRES_USER", "notesuser")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "notespass")

CACHE_HOST = os.environ.get("CACHE_HOST", "cache")
CACHE_PORT = int(os.environ.get("CACHE_PORT", 6379))


def get_db_connection(retries=5, delay=2):
    """Retry connecting to Postgres — the container can be 'up' before
    the DB inside it is actually ready to accept connections."""
    last_err = None
    for attempt in range(retries):
        try:
            conn = psycopg2.connect(
                host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
            )
            return conn
        except psycopg2.OperationalError as e:
            last_err = e
            time.sleep(delay)
    raise last_err


def get_cache():
    return redis.Redis(host=CACHE_HOST, port=CACHE_PORT, decode_responses=True)


@app.route("/health")
def health():
    """Used by Docker HEALTHCHECK and Compose depends_on: condition: service_healthy."""
    try:
        conn = get_db_connection(retries=1)
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    try:
        get_cache().ping()
        cache_ok = True
    except Exception:
        cache_ok = False

    status = 200 if (db_ok and cache_ok) else 503
    return jsonify({"db": db_ok, "cache": cache_ok}), status


@app.route("/", methods=["GET"])
def index():
    cache = get_cache()
    visits = cache.incr("visit_count")  # Redis: fast, ephemeral counter

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, content, created_at FROM notes ORDER BY id DESC;")
    notes = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("index.html", visits=visits, notes=notes)


@app.route("/notes", methods=["POST"])
def add_note():
    content = request.form.get("content", "").strip()
    if content:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO notes (content) VALUES (%s);", (content,))
        conn.commit()
        cur.close()
        conn.close()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
