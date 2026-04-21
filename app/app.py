import os
import time

import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "devsecret")

DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "name": os.getenv("DB_NAME", "appdb"),
    "user": os.getenv("DB_USER", "appuser"),
    "pass": os.getenv("DB_PASS", "changeme123"),
}


def get_conn():
    return psycopg2.connect(
        host=DB["host"],
        port=DB["port"],
        dbname=DB["name"],
        user=DB["user"],
        password=DB["pass"],
    )


def init_db(retries=10):
    for i in range(retries):
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS tasks(
                            id SERIAL PRIMARY KEY,
                            title TEXT NOT NULL,
                            done BOOLEAN NOT NULL DEFAULT FALSE,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW()
                        );
                        """
                    )
                conn.commit()
            return
        except Exception as e:
            print(f"[init_db] waiting for db... ({i + 1}/{retries}) {e}")
            time.sleep(2)
    raise RuntimeError("DB not ready after retries")


@app.get("/health")
def health():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return {"ok": True}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


@app.get("/tasks")
def list_tasks():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done, created_at FROM tasks ORDER BY id;")
            rows = cur.fetchall()
    return jsonify(
        [
            {
                "id": r[0],
                "title": r[1],
                "done": r[2],
                "created_at": r[3].isoformat(),
            }
            for r in rows
        ]
    )


@app.post("/tasks")
def add_task():
    data = request.get_json(silent=True)
    if data is None:
        return {"error": "invalid JSON body"}, 400

    title = data.get("title")
    if not title:
        return {"error": "title required"}, 400
    if len(title) > 500:
        return {"error": "title too long"}, 400

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tasks(title) VALUES (%s) RETURNING id;", (title,))
            new_id = cur.fetchone()[0]
        conn.commit()

    return {"id": new_id, "title": title, "done": False}, 201


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
