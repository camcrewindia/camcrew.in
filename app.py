import os
import json as _json
import secrets
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
import psycopg2.errors

from flask import (
    Flask, request, session, jsonify,
    send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-change-me")

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_ROOT = os.path.join(ROOT_DIR, "uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# Only these extensions may be served as static files.
ALLOWED_EXTENSIONS = {
    ".html", ".css", ".js", ".ico", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".webp", ".mp4", ".mov", ".webm",
    ".woff", ".woff2", ".ttf", ".otf",
    ".json", ".map", ".txt",
}

DEFAULT_DATABASE_URL = "postgresql://camcrewindia_user:OtYug8HJmROYnDqpCTF7v0bBGxwZeof3@dpg-d9k4lfbm8hqs73bl2jq0-a.oregon-postgres.render.com/camcrewindia?sslmode=require"
DATABASE_URL = os.environ.get("RENDER_DATABASE_URL", DEFAULT_DATABASE_URL)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

class _DBCursor:
    """Wraps a psycopg2 cursor so callers can chain .fetchone() / .fetchall()."""
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


import sqlite3
import re

class _DBConn:
    """
    Dual DB connection supporting PostgreSQL and automatic local SQLite fallback.
    Supports: conn.execute(sql, params), conn.commit(), context-manager.
    """
    def __init__(self):
        url = os.environ.get("RENDER_DATABASE_URL") or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
        if url and "sslmode" not in url and ("postgres.render.com" in url or "render.com" in url):
            url += "?sslmode=require" if "?" not in url else "&sslmode=require"
        self._is_sqlite = False
        if url:
            try:
                self._conn = psycopg2.connect(
                    url,
                    connect_timeout=3,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
                return
            except Exception as e:
                print(f"[DB] PostgreSQL connection to Render failed ({e}). Falling back to local SQLite.")

        # Local SQLite fallback when PostgreSQL server is unreachable
        self._is_sqlite = True
        db_path = os.path.join(ROOT_DIR, "camcrew_local.db")
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row

    def execute(self, sql, params=None):
        if self._is_sqlite:
            adapted_sql = sql
            # Adapt PostgreSQL DDL/DML for SQLite compatibility
            adapted_sql = adapted_sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
            adapted_sql = adapted_sql.replace("TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')", "datetime('now', 'localtime')")
            adapted_sql = adapted_sql.replace("TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS')", "datetime('now', 'localtime')")
            adapted_sql = adapted_sql.replace("ILIKE", "LIKE")
            adapted_sql = adapted_sql.replace("TRUE", "1").replace("FALSE", "0")

            # Handle RETURNING clause emulation for SQLite
            ret_match = re.search(r"\s+RETURNING\s+(\*|[a-zA-Z0-9_,\s]+)$", adapted_sql, re.IGNORECASE)
            returning_cols = None
            if ret_match:
                returning_cols = ret_match.group(1).strip()
                adapted_sql = adapted_sql[:ret_match.start()]

            # Replace PostgreSQL %s placeholder with SQLite ?
            adapted_sql = adapted_sql.replace("%s", "?")
            cur = self._conn.cursor()
            cur.execute(adapted_sql, params or ())

            if returning_cols:
                last_id = cur.lastrowid
                tbl_match = re.search(r"INSERT\s+INTO\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
                if tbl_match:
                    tbl_name = tbl_match.group(1)
                    if returning_cols == "id":
                        cur.execute(f"SELECT id FROM {tbl_name} WHERE rowid=?", (last_id,))
                    else:
                        cur.execute(f"SELECT * FROM {tbl_name} WHERE rowid=?", (last_id,))
            return _DBCursor(cur)
        else:
            cur = self._conn.cursor()
            cur.execute(sql, params or ())
            return _DBCursor(cur)

    def commit(self):
        try:
            self._conn.commit()
        except Exception:
            pass

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            try:
                self._conn.rollback()
            except Exception:
                pass
        else:
            try:
                self._conn.commit()
            except Exception:
                pass
        try:
            self._conn.close()
        except Exception:
            pass
        return False


def get_db():
    return _DBConn()


def _save_uploaded_file(file, subdir):
    filename = getattr(file, 'filename', '') or ''
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    safe_name = secrets.token_hex(10) + ext
    rel_dir = os.path.join("uploads", subdir)
    abs_dir = os.path.join(ROOT_DIR, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(abs_dir, safe_name)
    file.save(abs_path)
    return '/' + os.path.join(rel_dir, safe_name).replace('\\', '/')


def _file_to_data_url(file):
    """Convert an uploaded image file into a persistent Base64 Data URL for PostgreSQL storage."""
    try:
        if hasattr(file, 'seek'):
            file.seek(0)
        data = file.read() if hasattr(file, 'read') else None
        if hasattr(file, 'seek'):
            file.seek(0)
        if not data or len(data) > 15 * 1024 * 1024:
            return None
        filename = getattr(file, 'filename', '') or ''
        _, ext = os.path.splitext(filename)
        ext = ext.lower().replace('.', '')
        if ext in ('jpg', 'jpeg'):
            mime = 'image/jpeg'
        elif ext == 'png':
            mime = 'image/png'
        elif ext == 'webp':
            mime = 'image/webp'
        elif ext == 'gif':
            mime = 'image/gif'
        elif ext == 'svg':
            mime = 'image/svg+xml'
        elif ext in ('mp4', 'mov', 'webm'):
            mime = f'video/{ext}'
        else:
            mime = 'image/png'
        encoded = base64.b64encode(data).decode('utf-8')
        return f"data:{mime};base64,{encoded}"
    except Exception as e:
        print(f"[AVATAR] Error encoding data url: {e}")
        return None


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           SERIAL PRIMARY KEY,
                email        TEXT    NOT NULL UNIQUE,
                password     TEXT    NOT NULL,
                role         TEXT    NOT NULL DEFAULT 'customer',
                display_name TEXT,
                created_at   TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
            )
        """)
        # Migrate: add display_name if it doesn't exist yet
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                token      TEXT    NOT NULL UNIQUE,
                expires_at TEXT    NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id               SERIAL PRIMARY KEY,
                user_id          INTEGER NOT NULL,
                order_ref        TEXT    NOT NULL,
                status           TEXT    NOT NULL DEFAULT 'processing',
                items_json       TEXT    NOT NULL DEFAULT '[]',
                total_amount     REAL    NOT NULL DEFAULT 0,
                tracking_number  TEXT,
                tracking_status  TEXT,
                checkout_payload_json TEXT,
                created_at       TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS checkout_payload_json TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id                SERIAL PRIMARY KEY,
                user_id           INTEGER NOT NULL,
                professional_name TEXT    NOT NULL,
                service           TEXT    NOT NULL,
                booking_date      TEXT    NOT NULL,
                status            TEXT    NOT NULL DEFAULT 'pending',
                amount            REAL    NOT NULL DEFAULT 0,
                note              TEXT,
                created_at        TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_methods (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                type       TEXT    NOT NULL DEFAULT 'card',
                label      TEXT    NOT NULL,
                last4      TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS addresses (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                label      TEXT    NOT NULL DEFAULT 'Home',
                full_name  TEXT    NOT NULL,
                line1      TEXT    NOT NULL,
                line2      TEXT,
                city       TEXT    NOT NULL,
                state      TEXT    NOT NULL,
                pincode    TEXT    NOT NULL,
                phone      TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rewards (
                id      SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                points  INTEGER NOT NULL DEFAULT 0,
                tier    TEXT    NOT NULL DEFAULT 'Bronze',
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                id             SERIAL PRIMARY KEY,
                user_id        INTEGER NOT NULL,
                code           TEXT    NOT NULL,
                discount_value REAL    NOT NULL,
                discount_type  TEXT    NOT NULL DEFAULT 'percent',
                min_order      REAL    NOT NULL DEFAULT 0,
                expires_at     TEXT,
                used           INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refunds (
                id         SERIAL PRIMARY KEY,
                order_id   INTEGER,
                user_id    INTEGER NOT NULL,
                amount     REAL    NOT NULL,
                reason     TEXT,
                status     TEXT    NOT NULL DEFAULT 'pending',
                created_at TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_items (
                id              SERIAL PRIMARY KEY,
                professional_id INTEGER NOT NULL,
                title           TEXT,
                description     TEXT,
                file_url        TEXT,
                file_type       TEXT,
                share_id        TEXT UNIQUE,
                is_public       BOOLEAN NOT NULL DEFAULT TRUE,
                created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (professional_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS professional_profiles (
                user_id      INTEGER PRIMARY KEY,
                username     TEXT UNIQUE NOT NULL,
                title        TEXT,
                bio          TEXT,
                phone        TEXT,
                website      TEXT,
                avatar_url   TEXT,
                categories   TEXT NOT NULL DEFAULT '[]',
                services     TEXT NOT NULL DEFAULT '[]',
                locations    TEXT NOT NULL DEFAULT '[]',
                socials      TEXT NOT NULL DEFAULT '{}',
                travel_intl  BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at   TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("ALTER TABLE professional_profiles ADD COLUMN IF NOT EXISTS avatar_url TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id           SERIAL PRIMARY KEY,
                name         TEXT    NOT NULL,
                sku          TEXT,
                category     TEXT    NOT NULL DEFAULT 'Other',
                price        REAL    NOT NULL DEFAULT 0,
                stock        INTEGER NOT NULL DEFAULT 0,
                description  TEXT,
                image_url    TEXT,
                badge        TEXT,
                rating       REAL    NOT NULL DEFAULT 5.0,
                review_count INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
            )
        """)
        # Migrate: add seller_id to products for professional-listed items
        conn.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS seller_id INTEGER")


def seed_demo_data(user_id):
    """Populate sample orders/bookings/rewards for a user that has none yet."""
    import json, random, string as _string
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) AS c FROM orders WHERE user_id=%s", (user_id,)).fetchone()['c']:
            return  # already seeded


        conn.execute(
            "INSERT INTO rewards (user_id,points,tier) VALUES (%s,1250,'Silver') ON CONFLICT (user_id) DO NOTHING",
            (user_id,)
        )
        for code, val, dtype, minord, exp in [
            ("CAMCREW10", 10, "percent", 1000, "2026-12-31"),
            ("SAVE500",  500, "flat",    5000, "2026-09-30"),
        ]:
            if not conn.execute("SELECT id FROM coupons WHERE user_id=%s AND code=%s", (user_id, code)).fetchone():
                conn.execute(
                    "INSERT INTO coupons (user_id,code,discount_value,discount_type,min_order,expires_at) VALUES (%s,%s,%s,%s,%s,%s)",
                    (user_id, code, val, dtype, minord, exp),
                )


def init_cart_table():
    """Create cart_items table if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                product_id  INTEGER,
                name        TEXT    NOT NULL,
                price       REAL    NOT NULL DEFAULT 0,
                quantity    INTEGER NOT NULL DEFAULT 1,
                image_url   TEXT,
                category    TEXT,
                created_at  TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (user_id)    REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        """)


def init_admin_tables():
    """Create admin-specific tables if they don't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verification_requests (
                id           SERIAL PRIMARY KEY,
                user_id      INTEGER,
                studio_name  TEXT    NOT NULL,
                rep_name     TEXT    NOT NULL,
                rep_title    TEXT,
                studio_type  TEXT,
                location     TEXT,
                website      TEXT,
                notes        TEXT,
                status       TEXT    NOT NULL DEFAULT 'pending',
                reviewed_by  INTEGER,
                reviewed_at  TEXT,
                created_at   TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)


def init_rental_tables():
    """Create rental_equipment and rental_orders tables if they don't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rental_equipment (
                id              SERIAL PRIMARY KEY,
                professional_id INTEGER NOT NULL,
                name            TEXT    NOT NULL,
                category        TEXT    NOT NULL DEFAULT 'Camera',
                description     TEXT,
                price_per_day   REAL    NOT NULL DEFAULT 0,
                available       BOOLEAN NOT NULL DEFAULT TRUE,
                image_url       TEXT,
                created_at      TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (professional_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rental_orders (
                id              SERIAL PRIMARY KEY,
                equipment_id    INTEGER NOT NULL,
                professional_id INTEGER NOT NULL,
                customer_id     INTEGER,
                customer_name   TEXT    NOT NULL,
                customer_email  TEXT    NOT NULL,
                from_date       TEXT    NOT NULL,
                to_date         TEXT    NOT NULL,
                days            INTEGER NOT NULL DEFAULT 1,
                total_cost      REAL    NOT NULL DEFAULT 0,
                notes           TEXT,
                status          TEXT    NOT NULL DEFAULT 'pending',
                created_at      TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (equipment_id)    REFERENCES rental_equipment(id),
                FOREIGN KEY (professional_id) REFERENCES users(id)
            )
        """)

def init_professional_tables():
    """Create professional_requests, professional_jobs, vault_folders, vault_files tables."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS professional_requests (
                id              SERIAL PRIMARY KEY,
                professional_id INTEGER NOT NULL,
                client_name     TEXT NOT NULL,
                client_email    TEXT,
                service         TEXT NOT NULL,
                booking_date    TEXT NOT NULL,
                amount          REAL NOT NULL DEFAULT 0,
                note            TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (professional_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS professional_jobs (
                id              SERIAL PRIMARY KEY,
                professional_id INTEGER NOT NULL,
                client          TEXT NOT NULL,
                service         TEXT NOT NULL,
                booking_date    TEXT NOT NULL,
                amount          REAL NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'pending',
                notes           TEXT,
                created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (professional_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vault_folders (
                id              SERIAL PRIMARY KEY,
                professional_id INTEGER NOT NULL,
                name            TEXT NOT NULL,
                color           TEXT DEFAULT '#00dbe9',
                created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (professional_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vault_files (
                id              SERIAL PRIMARY KEY,
                professional_id INTEGER NOT NULL,
                folder_id       INTEGER,
                name            TEXT NOT NULL,
                file_type       TEXT NOT NULL DEFAULT 'other',
                file_size       BIGINT NOT NULL DEFAULT 0,
                file_url        TEXT,
                share_id        TEXT UNIQUE,
                created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (professional_id) REFERENCES users(id)
            )
        """)
        # Migrate: link bookings to a professional user account
        conn.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS professional_id INTEGER")
        # Migrate: link professional_requests back to the originating customer booking
        conn.execute("ALTER TABLE professional_requests ADD COLUMN IF NOT EXISTS booking_id INTEGER")


def seed_professional_data(uid):
    """Populate sample requests/jobs/vault for a professional that has none yet."""
    with get_db() as conn:
        if conn.execute(
            "SELECT COUNT(*) AS c FROM professional_requests WHERE professional_id=%s", (uid,)
        ).fetchone()['c']:
            return  # already seeded
        # Seed requests
        for client, email, service, date, amount, note, status in [
            ('Sarah Johnson', 'sarah@example.com',  'Wedding Videography',          '2026-08-15', 2800, 'Full day coverage, church + reception',       'pending'),
            ('Bright Agency', 'agency@brightco.com','Corporate Video — Q3 Launch',  '2026-08-22', 3500, 'Half-day shoot, 3 testimonials + b-roll',     'pending'),
            ('Marcus Lee',    'marcus@example.com', 'Portrait Photography',         '2026-07-30',  450, 'Outdoor session, 2 outfits',                  'confirmed'),
            ('TechConf 2026', 'events@techconf.com','Event Photography',            '2026-07-28', 1200, 'Full day conference coverage',                'completed'),
        ]:
            conn.execute(
                "INSERT INTO professional_requests (professional_id,client_name,client_email,service,booking_date,amount,note,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (uid, client, email, service, date, amount, note, status)
            )
        # Seed jobs
        for client, service, date, amount, status, notes in [
            ('Marcus Lee',    'Portrait Photography',     '2026-07-30',  450, 'confirmed', 'Outdoor session'),
            ('TechConf 2026', 'Event Photography',        '2026-07-28', 1200, 'completed', 'Full day conference'),
            ('Nova Films',    'Cinematic Brand Video',    '2026-08-10', 5000, 'active',    '3-day shoot, downtown LA'),
        ]:
            conn.execute(
                "INSERT INTO professional_jobs (professional_id,client,service,booking_date,amount,status,notes) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (uid, client, service, date, amount, status, notes)
            )
        # Seed vault folders
        f1 = conn.execute(
            "INSERT INTO vault_folders (professional_id,name,color) VALUES (%s,%s,%s) RETURNING id",
            (uid, 'Wedding – Smith 2026', '#00dbe9')
        ).fetchone()['id']
        f2 = conn.execute(
            "INSERT INTO vault_folders (professional_id,name,color) VALUES (%s,%s,%s) RETURNING id",
            (uid, 'TechConf 2026', '#ebb2ff')
        ).fetchone()['id']
        # Seed vault files
        for name, ftype, size, folder_id in [
            ('smith_wedding_highlight.mp4', 'video', 284000000, f1),
            ('smith_wedding_photos.zip',    'zip',   912000000, f1),
            ('techconf_gallery.zip',        'zip',   450000000, f2),
            ('contract_nova_films.pdf',     'pdf',      540000, None),
        ]:
            share_id = 'shr_' + secrets.token_hex(4)
            conn.execute(
                "INSERT INTO vault_files (professional_id,folder_id,name,file_type,file_size,share_id) VALUES (%s,%s,%s,%s,%s,%s)",
                (uid, folder_id, name, ftype, size, share_id)
            )


def init_pro_sales_table():
    """Create pro_sale_items table for tracking professional product sales."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pro_sale_items (
                id           SERIAL PRIMARY KEY,
                seller_id    INTEGER NOT NULL,
                order_id     INTEGER NOT NULL,
                product_id   INTEGER,
                product_name TEXT    NOT NULL,
                quantity     INTEGER NOT NULL DEFAULT 1,
                unit_price   REAL    NOT NULL DEFAULT 0,
                total_price  REAL    NOT NULL DEFAULT 0,
                created_at   TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (seller_id)  REFERENCES users(id),
                FOREIGN KEY (order_id)   REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        """)


init_db()
init_cart_table()
init_rental_tables()
init_admin_tables()
init_professional_tables()
init_pro_sales_table()


def init_phase1_tables():
    """Create escrow_payments and chat_messages tables."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS escrow_payments (
                id              SERIAL PRIMARY KEY,
                booking_id      INTEGER,
                client_id       INTEGER NOT NULL,
                professional_id INTEGER NOT NULL,
                amount          REAL NOT NULL,
                payment_method  TEXT NOT NULL DEFAULT 'upi_razorpay',
                escrow_status   TEXT NOT NULL DEFAULT 'held_in_escrow',
                transaction_ref TEXT UNIQUE,
                created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                released_at     TEXT,
                FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (professional_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id              SERIAL PRIMARY KEY,
                sender_id       INTEGER NOT NULL,
                receiver_id     INTEGER NOT NULL,
                booking_id      INTEGER,
                message         TEXT NOT NULL,
                is_read         BOOLEAN NOT NULL DEFAULT FALSE,
                created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)


def init_notifications_table():
    """Create notifications table if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                title       TEXT    NOT NULL,
                message     TEXT    NOT NULL,
                type        TEXT    NOT NULL DEFAULT 'info',
                link        TEXT,
                is_read     BOOLEAN NOT NULL DEFAULT FALSE,
                created_at  TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)


def create_notification(user_id, title, message, ntype='info', link=None, conn=None):
    """Insert a notification record for target user_id."""
    if not user_id:
        return
    sql = """INSERT INTO notifications (user_id, title, message, type, link)
             VALUES (%s, %s, %s, %s, %s)"""
    params = (user_id, title, message, ntype, link)
    try:
        if conn:
            conn.execute(sql, params)
        else:
            with get_db() as c:
                c.execute(sql, params)
    except Exception as exc:
        print(f"Failed to create notification: {exc}")


init_notifications_table()
init_phase1_tables()


# ---------------------------------------------------------------------------
# Notifications API
# ---------------------------------------------------------------------------

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401

    limit = max(1, min(100, int(request.args.get("limit", 20))))
    with get_db() as conn:
        unread_count = conn.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=FALSE", (uid,)
        ).fetchone()["c"]
        rows = conn.execute(
            "SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
            (uid, limit)
        ).fetchall()

    return jsonify({
        "ok": True,
        "unread_count": unread_count,
        "notifications": [dict(r) for r in rows]
    })


@app.route("/api/notifications/<int:notif_id>/read", methods=["PATCH"])
def mark_notification_read(notif_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        conn.execute(
            "UPDATE notifications SET is_read=TRUE WHERE id=%s AND user_id=%s",
            (notif_id, uid)
        )
    return jsonify({"ok": True})


@app.route("/api/notifications/mark-all-read", methods=["POST"])
def mark_all_notifications_read():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        conn.execute(
            "UPDATE notifications SET is_read=TRUE WHERE user_id=%s AND is_read=FALSE",
            (uid,)
        )
    return jsonify({"ok": True})


@app.route("/api/notifications/<int:notif_id>", methods=["DELETE"])
def delete_notification(notif_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        conn.execute("DELETE FROM notifications WHERE id=%s AND user_id=%s", (notif_id, uid))
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Public portfolio sharing
# ---------------------------------------------------------------------------


import re as _re

_SHARE_ID_RE  = _re.compile(r'^[A-Za-z0-9_\-]{4,64}$')
_USERNAME_RE  = _re.compile(r'^[a-z0-9][a-z0-9._]{2,29}$')

def _make_username(display_name, conn):
    """Derive a unique URL-safe username from a display name."""
    base = _re.sub(r'[^a-z0-9]', '_', (display_name or 'pro').lower())
    base = _re.sub(r'_+', '_', base).strip('_') or 'pro'
    base = base[:24]
    candidate = base
    i = 2
    while True:
        if not conn.execute(
            "SELECT user_id FROM professional_profiles WHERE username=%s",
            (candidate,)
        ).fetchone():
            return candidate
        candidate = f"{base}_{i}"
        i += 1
        if i > 99:
            return base + '_' + secrets.token_hex(3)


@app.route("/@<username>")
def at_profile_page(username):
    """Serve the public Instagram-style profile page for a professional."""
    return send_from_directory("templates/user", "public-profile.html")


@app.route("/api/profile/@<username>", methods=["GET"])
def get_public_profile(username):
    """Return public profile JSON for /@username — no auth required."""
    username_clean = (username or "").lstrip("@").strip()
    if not username_clean:
        return jsonify({"ok": False, "error": "Invalid username."}), 400

    with get_db() as conn:
        row = conn.execute("""
            SELECT pp.*, u.display_name, u.created_at AS joined_at
            FROM professional_profiles pp
            LEFT JOIN users u ON u.id = pp.user_id
            WHERE LOWER(pp.username) = LOWER(%s) OR LOWER(u.display_name) = LOWER(%s)
        """, (username_clean, username_clean)).fetchone()

        if not row:
            u_row = conn.execute("""
                SELECT id, display_name, email, created_at AS joined_at
                FROM users WHERE LOWER(display_name) = LOWER(%s) OR LOWER(email) = LOWER(%s) OR LOWER(role) = LOWER(%s)
            """, (username_clean, username_clean, username_clean)).fetchone()
            if u_row:
                dn = u_row["display_name"] or username_clean
                return jsonify({"ok": True, "profile": {
                    "username":     username_clean,
                    "display_name": dn,
                    "title":        "Professional",
                    "bio":          "",
                    "website":      "",
                    "avatar_url":   "",
                    "avatarUrl":    "",
                    "categories":   ["Photography", "Videography"],
                    "services":     [{"name": "Standard Session", "price": 2000, "unit": "per day", "category": "General"}],
                    "locations":    [],
                    "socials":      {},
                    "joined_at":    u_row["joined_at"],
                    "portfolio":    [],
                }})
            return jsonify({"ok": False, "error": "Profile not found."}), 404

        portfolio = conn.execute("""
            SELECT id, title, file_url, file_type, created_at
            FROM portfolio_items
            WHERE professional_id = %s AND is_public = TRUE
            ORDER BY created_at DESC LIMIT 30
        """, (row["user_id"],)).fetchall()

    avatar = row["avatar_url"] or ""
    return jsonify({"ok": True, "profile": {
        "username":     row["username"],
        "display_name": row["display_name"] or username,
        "title":        row["title"],
        "bio":          row["bio"],
        "website":      row["website"],
        "avatar_url":   avatar,
        "avatarUrl":    avatar,
        "categories":   _json.loads(row["categories"] or "[]"),
        "services":     _json.loads(row["services"]   or "[]"),
        "locations":    _json.loads(row["locations"]  or "[]"),
        "socials":      _json.loads(row["socials"]    or "{}"),
        "joined_at":    row["joined_at"],
        "portfolio":    [dict(p) for p in portfolio],
    }})


@app.route("/api/professionals", methods=["GET"])
def list_professionals():
    """Return professionals filtered by service category (case-insensitive). Compatible with PostgreSQL & SQLite."""
    category   = (request.args.get("category") or "").strip().lower()
    limit      = min(int(request.args.get("limit", 20)), 50)
    offset     = max(int(request.args.get("offset", 0)), 0)
    location_q = (request.args.get("location") or "").strip().lower()
    min_price_raw = (request.args.get("min_price") or "").strip()

    if not category:
        return jsonify({"ok": False, "error": "category parameter required."}), 400

    try:
        min_price_val = float(min_price_raw) if min_price_raw else None
    except ValueError:
        min_price_val = None

    # Derive category keyword root (e.g. "photographers" -> "photo")
    cat_root = category.rstrip("s")
    if cat_root.startswith("photographer") or cat_root.startswith("photography"):
        cat_root = "photo"
    elif cat_root.startswith("videographer") or cat_root.startswith("videography"):
        cat_root = "video"
    elif cat_root.startswith("designer"):
        cat_root = "design"
    elif cat_root.startswith("developer"):
        cat_root = "dev"
    elif cat_root.startswith("caterer") or cat_root.startswith("catering"):
        cat_root = "cater"
    elif cat_root.startswith("organiser") or cat_root.startswith("organizer"):
        cat_root = "organi"

    with get_db() as conn:
        rows = conn.execute("""
            SELECT pp.username, pp.title, pp.bio, pp.categories, pp.services,
                   pp.locations, pp.travel_intl, pp.avatar_url,
                   u.display_name
            FROM professional_profiles pp
            LEFT JOIN users u ON u.id = pp.user_id
            ORDER BY pp.updated_at DESC
        """).fetchall()

    professionals = []
    for r in rows:
        all_services   = _json.loads(r["services"] or "[]")
        all_categories = _json.loads(r["categories"] or "[]")
        locations      = _json.loads(r["locations"] or "[]")
        title          = (r["title"] or "").lower()

        cat_match = False
        cat_services = []

        # Check inside categories array or title
        for cat in all_categories:
            c_str = (cat or "").lower()
            if cat_root in c_str or c_str in category:
                cat_match = True
                break
        if cat_root in title or category in title:
            cat_match = True

        # Check inside services array
        for s in all_services:
            svc_cat  = (s.get("category") or "").lower()
            svc_name = (s.get("name") or "").lower()
            if not svc_cat or cat_root in svc_cat or cat_root in svc_name or svc_cat in category:
                cat_services.append(s)
                cat_match = True

        if not cat_services:
            cat_services = all_services

        # If categories/services are unpopulated, allow matching so profiles are visible
        if not cat_match and (not all_categories and not all_services):
            cat_match = True

        if not cat_match:
            continue

        # Location filter
        if location_q and not any(location_q in loc.lower() for loc in locations):
            continue

        # Min price filter
        if min_price_val is not None:
            if not any(float(s.get("price") or 0) >= min_price_val for s in cat_services):
                continue

        # Derive display rate from cheapest matching service
        rate = None
        priced = [s for s in cat_services if s.get("price")]
        if priced:
            cheapest = min(priced, key=lambda s: float(s.get("price") or 0))
            rate = f"₹{cheapest['price']}/{cheapest.get('unit', 'per day')}"

        avatar = r["avatar_url"] or ""

        professionals.append({
            "username":     r["username"],
            "display_name": r["display_name"] or r["username"],
            "title":        r["title"],
            "bio":          r["bio"],
            "avatar_url":   avatar,
            "avatarUrl":    avatar,
            "locations":    locations,
            "location":     locations[0] if locations else None,
            "rate":         rate,
            "services":     cat_services,
            "categories":   all_categories,
            "travel_intl":  r["travel_intl"],
        })

    paginated = professionals[offset:offset + limit]

    return jsonify({"ok": True, "professionals": paginated})


@app.route("/shared/<share_id>")
def shared_portfolio_page(share_id):
    """Serve the public portfolio viewer for a given share_id."""
    return send_from_directory("templates/public", "shared.html")


@app.route("/api/shared/<share_id>", methods=["GET"])
def shared_portfolio_data(share_id):
    """Return JSON data for a public portfolio item — no auth required."""
    if not _SHARE_ID_RE.match(share_id):
        return jsonify({"ok": False, "error": "Invalid share link."}), 400

    with get_db() as conn:
        row = conn.execute(
            """SELECT pi.*, u.display_name
               FROM portfolio_items pi
               JOIN users u ON u.id = pi.professional_id
               WHERE pi.share_id = %s""",
            (share_id,),
        ).fetchone()

    if not row:
        return jsonify({"ok": False, "error": "Portfolio not found."}), 404
    if not row["is_public"]:
        return jsonify({"ok": False, "error": "This portfolio is no longer publicly available."}), 404

    return jsonify({"ok": True, "item": {
        "title":        row["title"],
        "description":  row["description"],
        "file_url":     row["file_url"],
        "file_type":    row["file_type"],
        "created_at":   row["created_at"],
    }, "professional": {
        "display_name": row["display_name"] or "CamCrew Professional",
    }})


@app.route("/api/portfolio/share", methods=["POST"])
def portfolio_share():
    """Create or retrieve a share_id for a vault file. Requires auth."""
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401

    data        = request.get_json(force=True)
    title       = (data.get("title")       or "").strip() or None
    description = (data.get("description") or "").strip() or None
    file_url    = (data.get("file_url")    or "").strip() or None
    file_type   = (data.get("file_type")   or "").strip() or None
    hint_id     = (data.get("shareId")     or "").strip()

    # If the caller supplies its existing share_id, honour it if already in DB
    if hint_id and _SHARE_ID_RE.match(hint_id):
        with get_db() as conn:
            existing = conn.execute(
                "SELECT share_id FROM portfolio_items WHERE share_id=%s AND professional_id=%s",
                (hint_id, uid),
            ).fetchone()
        if existing:
            url = f"{request.host_url.rstrip('/')}shared/{hint_id}"
            return jsonify({"ok": True, "shareId": hint_id, "url": url})

    # Generate a fresh URL-safe share_id
    new_id = secrets.token_hex(8)          # 16 hex chars, e.g. 3f9d8ab712ce4a01
    with get_db() as conn:
        conn.execute(
            """INSERT INTO portfolio_items
               (professional_id, title, description, file_url, file_type, share_id, is_public)
               VALUES (%s, %s, %s, %s, %s, %s, TRUE)
               ON CONFLICT (share_id) DO NOTHING""",
            (uid, title, description, file_url, file_type, new_id),
        )

    url = f"{request.host_url.rstrip('/')}shared/{new_id}"
    return jsonify({"ok": True, "shareId": new_id, "url": url})


# ---------------------------------------------------------------------------
# Static page routes
# ---------------------------------------------------------------------------

# Maps each HTML filename to the subdirectory it lives in after restructure.
_TEMPLATE_MAP = {
    # partials
    "header.html":               "templates/partials",
    "footer.html":               "templates/partials",
    "dashboard-sidebar.html":    "templates/partials",
    "dashboard-footer.html":     "templates/partials",
    # public
    "index.html":                "templates/public",
    "About.html":                "templates/public",
    "about.html":                "templates/public",
    "services.html":             "templates/public",
    "rentals.html":              "templates/public",
    "book.html":                 "templates/public",
    "scroll-animation.html":     "templates/public",
    "photographers.html":        "templates/public",
    "videographers.html":        "templates/public",
    "designers.html":            "templates/public",
    "developers.html":           "templates/public",
    "caterers.html":             "templates/public",
    "organisers.html":           "templates/public",
    "sales.html":                "templates/public",
    "shared.html":               "templates/public",
    # auth
    "signin.html":               "templates/auth",
    "signup.html":               "templates/auth",
    "customersignup.html":       "templates/auth",
    "studiosignup.html":         "templates/auth",
    "professionalsetup.html":    "templates/auth",
    "studioreq.html":            "templates/auth",
    "forgot-password.html":      "templates/auth",
    "reset-password.html":       "templates/auth",
    # user
    "profile.html":              "templates/user",
    "customer-profile.html":     "templates/user",
    "public-profile.html":       "templates/user",
    "settings.html":             "templates/user",
    "cart.html":                 "templates/user",
    "checkout.html":             "templates/user",
    "orders.html":               "templates/user",
    "notifications.html":        "templates/user",
    # professional
    "professional-dashboard.html": "templates/professional",
    "professional-edit.html":      "templates/professional",
    "professional-profile.html":   "templates/professional",
    # admin
    "admindashboard.html":         "templates/admin",
    "adminlogin.html":             "templates/admin",
    "inventory.html":              "templates/admin",
    "subscriptionmanagement.html": "templates/admin",
    "verificationrequest.html":    "templates/admin",
}


def _serve_template(filename):
    """Look up filename in _TEMPLATE_MAP and serve it from the right subdir using ROOT_DIR."""
    subdir = _TEMPLATE_MAP.get(filename)
    if subdir:
        return send_from_directory(os.path.join(ROOT_DIR, subdir), filename)
    abort(404)


@app.route("/uploads/<path:filename>")
def serve_uploads(filename):
    abs_path = os.path.join(ROOT_DIR, "uploads", filename)
    if os.path.exists(abs_path):
        return send_from_directory(os.path.join(ROOT_DIR, "uploads"), filename)

    initial = "CC"
    parts = [p for p in filename.split("/") if p]
    if len(parts) >= 2:
        initial = parts[1][:2].upper()

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#00f0ff"/>
          <stop offset="100%" stop-color="#8b5cf6"/>
        </linearGradient>
      </defs>
      <rect width="200" height="200" rx="100" fill="url(#g)"/>
      <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle" fill="#0b0c10" font-family="sans-serif" font-size="72" font-weight="900">{initial}</text>
    </svg>"""
    return Response(svg, mimetype="image/svg+xml")


@app.route("/")
def index():
    return send_from_directory(os.path.join(ROOT_DIR, "templates", "public"), "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    # Block any path that escapes the root or targets hidden/sensitive files
    if ".." in filename or filename.startswith("."):
        abort(403)

    ext = os.path.splitext(filename)[1].lower()

    # If no extension is provided (e.g. /services, /about, /signin), default to .html
    if not ext:
        filename = filename + ".html"
        ext = ".html"

    # HTML files → look up in the template map or subdirs
    if ext == ".html":
        basename = os.path.basename(filename)
        subdir = _TEMPLATE_MAP.get(basename)
        if subdir and os.path.exists(os.path.join(ROOT_DIR, subdir, basename)):
            return send_from_directory(os.path.join(ROOT_DIR, subdir), basename)
        for sub in ("templates/public", "templates/auth", "templates/user", "templates/professional", "templates/admin"):
            if os.path.exists(os.path.join(ROOT_DIR, sub, basename)):
                return send_from_directory(os.path.join(ROOT_DIR, sub), basename)
        abort(404)

    if ext not in ALLOWED_EXTENSIONS:
        abort(403)

    # Everything else (images, fonts, attached_assets, etc.) → serve from ROOT_DIR
    if os.path.exists(os.path.join(ROOT_DIR, filename)):
        return send_from_directory(ROOT_DIR, filename)

    abort(404)

# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "").strip()
    role     = (data.get("role")     or "customer").strip().lower()

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password are required."}), 400

    if len(password) < 6:
        return jsonify({"ok": False, "error": "Password must be at least 6 characters."}), 400

    if role not in ("customer", "professional", "studio"):
        role = "customer"

    hashed = generate_password_hash(password)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (email, password, role) VALUES (%s, %s, %s)",
                (email, hashed, role),
            )
    except psycopg2.IntegrityError:
        return jsonify({"ok": False, "error": "An account with that email already exists."}), 409

    # Log the user in immediately after registration
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()

    session["user_id"] = row["id"]
    session["email"]   = row["email"]
    session["role"]    = row["role"]

    return jsonify({"ok": True, "user": {"email": row["email"], "role": row["role"]}})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password are required."}), 400

    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()

    if not row or not check_password_hash(row["password"], password):
        return jsonify({"ok": False, "error": "Invalid email or password."}), 401
        
    if row["role"] == "admin":
        return jsonify({"ok": False, "error": "Admins must log in through the admin portal."}), 403

    session["user_id"] = row["id"]
    session["email"]   = row["email"]
    session["role"]    = row["role"]

    return jsonify({"ok": True, "user": {"email": row["email"], "role": row["role"]}})


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(force=True)
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password are required."}), 400

    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()

    if not row or not check_password_hash(row["password"], password):
        return jsonify({"ok": False, "error": "Invalid email or password."}), 401

    if row["role"] != "admin":
        return jsonify({"ok": False, "error": "Access denied. Admin accounts only."}), 403

    session["user_id"] = row["id"]
    session["email"]   = row["email"]
    session["role"]    = row["role"]

    return jsonify({"ok": True, "user": {"email": row["email"], "role": row["role"]}})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data  = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"ok": False, "error": "Email is required."}), 400

    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()

    # Always return success to avoid leaking whether an account exists
    if not row:
        return jsonify({"ok": True, "message": "If that email is registered, a reset link has been sent."})

    token      = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

    with get_db() as conn:
        # Invalidate any previous unused tokens for this user
        conn.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE user_id = %s AND used = 0",
            (row["id"],)
        )
        conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
            (row["id"], token, expires_at),
        )

    # In production, send token via email. Here we return it so the UI can
    # construct the reset link (dev/demo mode — replace with email delivery).
    return jsonify({
        "ok": True,
        "message": "If that email is registered, a reset link has been sent.",
    })


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data     = request.get_json(force=True)
    token    = (data.get("token")    or "").strip()
    password = (data.get("password") or "").strip()

    if not token or not password:
        return jsonify({"ok": False, "error": "Token and new password are required."}), 400

    if len(password) < 6:
        return jsonify({"ok": False, "error": "Password must be at least 6 characters."}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token = %s AND used = 0",
            (token,)
        ).fetchone()

    if not row:
        return jsonify({"ok": False, "error": "This reset link is invalid or has already been used."}), 400

    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
        return jsonify({"ok": False, "error": "This reset link has expired. Please request a new one."}), 400

    hashed = generate_password_hash(password)
    with get_db() as conn:
        conn.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, row["user_id"]))
        conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = %s", (row["id"],))

    return jsonify({"ok": True, "message": "Password updated successfully. You can now sign in."})


@app.route("/api/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        row = conn.execute(
            "SELECT email, role, display_name FROM users WHERE id=%s",
            (session["user_id"],)
        ).fetchone()
    return jsonify({
        "ok": True,
        "user": {
            "id":           session["user_id"],
            "email":        session["email"],
            "role":         session["role"],
            "display_name": row["display_name"] if row else None,
        }
    })


@app.route("/api/profile", methods=["GET"])
def get_profile():
    if "user_id" not in session:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    uid = session["user_id"]

    with get_db() as conn:
        row = conn.execute(
            "SELECT email, role, display_name, created_at FROM users WHERE id = %s",
            (uid,)
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "User not found."}), 404

        profile = {
            "name":         row["display_name"] or "",
            "email":        row["email"],
            "role":         row["role"],
            "display_name": row["display_name"] or "",
            "created_at":   row["created_at"],
        }

        if row["role"] in ("professional", "studio"):
            pro = conn.execute(
                "SELECT * FROM professional_profiles WHERE user_id=%s",
                (uid,)
            ).fetchone()
            if pro:
                profile.update({
                    "username":             pro["username"],
                    "title":                pro["title"] or "",
                    "bio":                  pro["bio"] or "",
                    "phone":                pro["phone"] or "",
                    "website":              pro["website"] or "",
                    "avatarUrl":           pro["avatar_url"] or "",
                    "avatar_url":          pro["avatar_url"] or "",
                    "categories":           _json.loads(pro["categories"] or "[]"),
                    "services":             _json.loads(pro["services"] or "[]"),
                    "locations":            _json.loads(pro["locations"] or "[]"),
                    "socials":              _json.loads(pro["socials"] or "{}"),
                    "travelIntl":           bool(pro["travel_intl"]),
                })
            else:
                profile.update({
                    "username":             "",
                    "title":                "",
                    "bio":                  "",
                    "phone":                "",
                    "website":              "",
                    "avatarUrl":           "",
                    "categories":           [],
                    "services":             [],
                    "locations":            [],
                    "socials":              {},
                    "travelIntl":           False,
                })

            portfolio = conn.execute(
                """SELECT id, title, description, file_url, file_type, created_at
                   FROM portfolio_items
                   WHERE professional_id = %s AND is_public = TRUE
                   ORDER BY created_at DESC LIMIT 30""",
                (uid,)
            ).fetchall()
            profile["portfolio"] = [dict(p) for p in portfolio]

    return jsonify({"ok": True, "profile": profile})


@app.route("/api/profile", methods=["PATCH"])
def update_profile():
    if "user_id" not in session:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401

    uid = session["user_id"]
    is_form = bool(request.files)
    data = request.form.to_dict() if is_form else request.get_json(force=True)

    avatar_file = request.files.get("avatar") if is_form else None
    portfolio_files = [request.files[k] for k in request.files if k.startswith("portfolio_file_")] if is_form else []
    removed_portfolio_ids = []
    if data.get("remove_portfolio_ids"):
        try:
            removed_portfolio_ids = _json.loads(data.get("remove_portfolio_ids") or "[]")
        except ValueError:
            removed_portfolio_ids = []
    elif not is_form:
        removed_portfolio_ids = data.get("remove_portfolio_ids") or []

    display_name = (data.get("display_name") or "").strip()
    if display_name and len(display_name) > 60:
        return jsonify({"ok": False, "error": "Display name must be 60 characters or fewer."}), 400

    avatar_url = (data.get("avatar_url") or "").strip() or None
    if avatar_file:
        try:
            data_url = _file_to_data_url(avatar_file)
            disk_url = _save_uploaded_file(avatar_file, f"profiles/{uid}/avatar")
            avatar_url = data_url or disk_url
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    if avatar_url and not (avatar_url.startswith("/") or avatar_url.startswith("http") or avatar_url.startswith("data:")):
        avatar_url = None

    username = None
    with get_db() as conn:
        if display_name:
            conn.execute("UPDATE users SET display_name=%s WHERE id=%s", (display_name, uid))

        role_row = conn.execute("SELECT role, display_name FROM users WHERE id=%s", (uid,)).fetchone()

        if role_row and role_row["role"] in ("professional", "studio"):
            title       = (data.get("title")   or "").strip() or None
            bio         = (data.get("bio")      or "").strip() or None
            phone       = (data.get("phone")    or "").strip() or None
            website     = (data.get("website")  or "").strip() or None

            def _parse_json_field(value, default):
                if isinstance(value, str):
                    try:
                        return _json.loads(value)
                    except ValueError:
                        return default
                return value if value is not None else default

            categories  = _json.dumps(_parse_json_field(data.get("categories"), []))
            services    = _json.dumps(_parse_json_field(data.get("services"), []))
            locations   = _json.dumps(_parse_json_field(data.get("locations"), []))
            socials     = _json.dumps(_parse_json_field(data.get("socials"), {}))
            travel_intl = bool(_parse_json_field(data.get("travel_international"), False))

            existing = conn.execute(
                "SELECT username FROM professional_profiles WHERE user_id=%s", (uid,)
            ).fetchone()

            if existing:
                update_fields = [
                    "title=%s", "bio=%s", "phone=%s", "website=%s",
                    "categories=%s", "services=%s", "locations=%s",
                    "socials=%s", "travel_intl=%s",
                ]
                params = [title, bio, phone, website, categories, services, locations, socials, travel_intl]
                if avatar_url is not None:
                    update_fields.append("avatar_url=%s")
                    params.append(avatar_url)
                update_fields.append("updated_at=TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS')")
                params.append(uid)
                conn.execute(f"UPDATE professional_profiles SET {', '.join(update_fields)} WHERE user_id=%s", tuple(params))
                username = existing["username"]
            else:
                dn = display_name or (role_row["display_name"] or "")
                username = _make_username(dn or "pro", conn)
                conn.execute("""
                    INSERT INTO professional_profiles
                    (user_id, username, title, bio, phone, website, avatar_url,
                     categories, services, locations, socials, travel_intl)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    uid, username, title, bio, phone, website, avatar_url,
                    categories, services, locations, socials, travel_intl,
                ))

            if removed_portfolio_ids:
                try:
                    clean_ids = [int(x) for x in removed_portfolio_ids if str(x).isdigit()]
                    if clean_ids:
                        placeholders = ','.join(['%s'] * len(clean_ids))
                        conn.execute(
                            f"DELETE FROM portfolio_items WHERE professional_id=%s AND id IN ({placeholders})",
                            (uid, *clean_ids)
                        )
                except Exception as err:
                    print(f"[PORTFOLIO] Error deleting portfolio items: {err}")

            for file in portfolio_files:
                try:
                    data_url = _file_to_data_url(file)
                    disk_url = _save_uploaded_file(file, f"profiles/{uid}/portfolio")
                    file_url = data_url or disk_url
                except ValueError as exc:
                    return jsonify({"ok": False, "error": str(exc)}), 400
                _, ext = os.path.splitext(file.filename or "")
                file_type = "video" if ext.lower() in {".mp4", ".mov", ".webm"} else "image"
                conn.execute(
                    "INSERT INTO portfolio_items (professional_id, title, description, file_url, file_type, share_id, is_public) VALUES (%s,%s,%s,%s,%s,NULL,TRUE)",
                    (uid, file.filename or None, None, file_url, file_type)
                )

    return jsonify({"ok": True, "display_name": display_name, "username": username, "avatarUrl": avatar_url})


@app.route("/api/portfolio", methods=["DELETE"])
def delete_portfolio_generic():
    """Delete a portfolio item by id or file_url for the authenticated professional."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data = request.get_json(force=True, silent=True) or {}
    item_id = data.get("id") or request.args.get("id")
    file_url = data.get("file_url") or request.args.get("file_url")

    with get_db() as conn:
        if item_id and str(item_id).isdigit():
            conn.execute("DELETE FROM portfolio_items WHERE id=%s AND professional_id=%s", (int(item_id), uid))
        elif file_url:
            conn.execute("DELETE FROM portfolio_items WHERE file_url=%s AND professional_id=%s", (file_url, uid))
        else:
            return jsonify({"ok": False, "error": "Missing item identifier."}), 400

    return jsonify({"ok": True, "message": "Portfolio item deleted."})


@app.route("/api/portfolio/<int:item_id>", methods=["DELETE"])
def delete_portfolio_item(item_id):
    """Delete a single portfolio item directly for the authenticated professional."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        conn.execute("DELETE FROM portfolio_items WHERE id=%s AND professional_id=%s", (item_id, uid))
    return jsonify({"ok": True, "message": "Portfolio item deleted."})


@app.route("/api/portfolio/<int:item_id>", methods=["PATCH"])
def update_portfolio_item_title(item_id):
    """Update title/name of a single portfolio item for the authenticated professional."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data = request.get_json(force=True) or {}
    new_title = (data.get("title") or "").strip()
    if not new_title:
        return jsonify({"ok": False, "error": "Title cannot be empty."}), 400

    with get_db() as conn:
        conn.execute("UPDATE portfolio_items SET title=%s WHERE id=%s AND professional_id=%s", (new_title, item_id, uid))
    return jsonify({"ok": True, "message": "Title updated.", "title": new_title})


# ---------------------------------------------------------------------------
# Phase 1: Escrow Payments API
# ---------------------------------------------------------------------------

@app.route("/api/payments/checkout", methods=["POST"])
def payment_checkout():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data = request.get_json(force=True, silent=True) or {}
    booking_id = data.get("booking_id")
    pro_id = data.get("professional_id")
    amount = float(data.get("amount") or 0)
    method = data.get("payment_method") or "upi_razorpay"

    if amount <= 0 or not pro_id:
        return jsonify({"ok": False, "error": "Invalid checkout details."}), 400

    tx_ref = f"CC-ESC-{secrets.token_hex(6).upper()}"
    with get_db() as conn:
        row = conn.execute("""
            INSERT INTO escrow_payments
            (booking_id, client_id, professional_id, amount, payment_method, escrow_status, transaction_ref)
            VALUES (%s, %s, %s, %s, %s, 'held_in_escrow', %s)
            RETURNING id
        """, (booking_id, uid, pro_id, amount, method, tx_ref)).fetchone()
        
        escrow_id = row["id"] if row else None
        if booking_id:
            conn.execute("UPDATE bookings SET status='escrow_held' WHERE id=%s", (booking_id,))

    create_notification(
        pro_id,
        "Escrow Payment Received!",
        f"₹{amount:,.0f} has been locked in Escrow Protection for your upcoming shoot! Ref: {tx_ref}",
        ntype="success",
        link="/professional-dashboard.html"
    )
    create_notification(
        uid,
        "Payment Secured in Escrow",
        f"Your payment of ₹{amount:,.0f} is locked safely in Camcrew Escrow Protection.",
        ntype="info",
        link="/customer-profile.html"
    )

    return jsonify({
        "ok": True,
        "escrow_id": escrow_id,
        "transaction_ref": tx_ref,
        "status": "held_in_escrow",
        "message": "Payment locked in Escrow Protection."
    })


@app.route("/api/payments/release", methods=["POST"])
def payment_release():
    uid = session.get("user_id")
    role = session.get("role")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data = request.get_json(force=True, silent=True) or {}
    escrow_id = data.get("escrow_id")
    booking_id = data.get("booking_id")

    with get_db() as conn:
        if escrow_id:
            pay = conn.execute("SELECT * FROM escrow_payments WHERE id=%s", (escrow_id,)).fetchone()
        elif booking_id:
            pay = conn.execute("SELECT * FROM escrow_payments WHERE booking_id=%s ORDER BY id DESC LIMIT 1", (booking_id,)).fetchone()
        else:
            return jsonify({"ok": False, "error": "Missing escrow or booking ID."}), 400

        if not pay:
            return jsonify({"ok": False, "error": "Escrow transaction not found."}), 404

        if role != "admin" and pay["client_id"] != uid:
            return jsonify({"ok": False, "error": "Only client or admin can release escrow funds."}), 403

        conn.execute("""
            UPDATE escrow_payments
            SET escrow_status='released_to_pro', released_at=TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
            WHERE id=%s
        """, (pay["id"],))

        if pay["booking_id"]:
            conn.execute("UPDATE bookings SET status='completed' WHERE id=%s", (pay["booking_id"],))

    create_notification(
        pay["professional_id"],
        "Escrow Payment Released!",
        f"₹{pay['amount']:,.0f} has been released from Escrow into your earnings!",
        ntype="success",
        link="/professional-dashboard.html"
    )
    return jsonify({"ok": True, "message": "Escrow funds released to professional."})


@app.route("/api/payments/escrow-summary", methods=["GET"])
def payment_escrow_summary():
    uid = session.get("user_id")
    role = session.get("role")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401

    with get_db() as conn:
        if role in ("professional", "studio"):
            items = conn.execute("""
                SELECT ep.*, u.display_name as client_name
                FROM escrow_payments ep
                JOIN users u ON u.id = ep.client_id
                WHERE ep.professional_id=%s
                ORDER BY ep.id DESC LIMIT 50
            """, (uid,)).fetchall()
        elif role == "admin":
            items = conn.execute("""
                SELECT ep.*, c.display_name as client_name, p.display_name as pro_name
                FROM escrow_payments ep
                JOIN users c ON c.id = ep.client_id
                JOIN users p ON p.id = ep.professional_id
                ORDER BY ep.id DESC LIMIT 50
            """).fetchall()
        else:
            items = conn.execute("""
                SELECT ep.*, u.display_name as pro_name
                FROM escrow_payments ep
                JOIN users u ON u.id = ep.professional_id
                WHERE ep.client_id=%s
                ORDER BY ep.id DESC LIMIT 50
            """, (uid,)).fetchall()

    return jsonify({"ok": True, "items": [dict(i) for i in items]})


# ---------------------------------------------------------------------------
# Phase 1: Real-Time Chat & Direct Messaging API
# ---------------------------------------------------------------------------

@app.route("/api/chat/send", methods=["POST"])
def chat_send():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data = request.get_json(force=True, silent=True) or {}
    receiver_id = data.get("receiver_id")
    booking_id = data.get("booking_id")
    message = (data.get("message") or "").strip()

    if not receiver_id or not message:
        return jsonify({"ok": False, "error": "Receiver and message content required."}), 400

    with get_db() as conn:
        row = conn.execute("""
            INSERT INTO chat_messages (sender_id, receiver_id, booking_id, message)
            VALUES (%s, %s, %s, %s)
            RETURNING id, created_at
        """, (uid, receiver_id, booking_id, message)).fetchone()
        
        sender_name = conn.execute("SELECT display_name FROM users WHERE id=%s", (uid,)).fetchone()
        sname = sender_name["display_name"] if sender_name else "Someone"

    create_notification(
        receiver_id,
        f"New message from {sname}",
        message[:80] + ("..." if len(message) > 80 else ""),
        ntype="info",
        link=f"/professional-dashboard.html?chat={uid}"
    )

    return jsonify({"ok": True, "message_id": row["id"], "created_at": row["created_at"]})


@app.route("/api/chat/messages/<int:target_id>", methods=["GET"])
def chat_messages_with_user(target_id):
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401

    with get_db() as conn:
        conn.execute("""
            UPDATE chat_messages SET is_read=TRUE
            WHERE sender_id=%s AND receiver_id=%s AND is_read=FALSE
        """, (target_id, uid))
        
        msgs = conn.execute("""
            SELECT id, sender_id, receiver_id, booking_id, message, is_read, created_at
            FROM chat_messages
            WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)
            ORDER BY id ASC LIMIT 200
        """, (uid, target_id, target_id, uid)).fetchall()

        target_user = conn.execute(
            "SELECT id, display_name, email, role FROM users WHERE id=%s",
            (target_id,)
        ).fetchone()

    return jsonify({
        "ok": True,
        "target_user": dict(target_user) if target_user else None,
        "messages": [dict(m) for m in msgs]
    })


@app.route("/api/chat/conversations", methods=["GET"])
def chat_conversations():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401

    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                CASE WHEN sender_id = %s THEN receiver_id ELSE sender_id END AS other_id,
                MAX(id) as last_msg_id,
                COUNT(CASE WHEN receiver_id = %s AND is_read = FALSE THEN 1 END) as unread_count
            FROM chat_messages
            WHERE sender_id = %s OR receiver_id = %s
            GROUP BY other_id
            ORDER BY last_msg_id DESC
        """, (uid, uid, uid, uid)).fetchall()

        convos = []
        for r in rows:
            other_id = r["other_id"]
            user_info = conn.execute(
                "SELECT id, display_name, role FROM users WHERE id=%s",
                (other_id,)
            ).fetchone()
            last_msg = conn.execute(
                "SELECT message, created_at FROM chat_messages WHERE id=%s",
                (r["last_msg_id"],)
            ).fetchone()
            if user_info and last_msg:
                convos.append({
                    "user_id": user_info["id"],
                    "display_name": user_info["display_name"] or "User",
                    "role": user_info["role"],
                    "last_message": last_msg["message"],
                    "last_time": last_msg["created_at"],
                    "unread_count": r["unread_count"]
                })

    return jsonify({"ok": True, "conversations": convos})


# ---------------------------------------------------------------------------
# Customer dashboard API
# ---------------------------------------------------------------------------

def require_auth():
    """Return user_id from session or None."""
    return session.get("user_id")


@app.route("/api/customer/seed", methods=["POST"])
def customer_seed():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    seed_demo_data(uid)
    return jsonify({"ok": True})


@app.route("/api/customer/overview", methods=["GET"])
def customer_overview():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        orders_count   = conn.execute("SELECT COUNT(*) AS c FROM orders   WHERE user_id=%s", (uid,)).fetchone()['c']
        bookings_count = conn.execute("SELECT COUNT(*) AS c FROM bookings WHERE user_id=%s AND status IN ('pending','confirmed')", (uid,)).fetchone()['c']
        addr_count     = conn.execute("SELECT COUNT(*) AS c FROM addresses WHERE user_id=%s", (uid,)).fetchone()['c']
        row            = conn.execute("SELECT points, tier FROM rewards WHERE user_id=%s", (uid,)).fetchone()
        points = row["points"] if row else 0
        tier   = row["tier"]   if row else "Bronze"
    return jsonify({"ok": True, "overview": {
        "orders": orders_count, "active_bookings": bookings_count,
        "addresses": addr_count, "points": points, "tier": tier,
    }})


# ── Orders ─────────────────────────────────────────────────────────────────

@app.route("/api/customer/orders", methods=["GET"])
def customer_orders():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    import json as _json
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC", (uid,)
        ).fetchall()
    orders = []
    for r in rows:
        orders.append({
            "id": r["id"], "order_ref": r["order_ref"], "status": r["status"],
            "items": _json.loads(r["items_json"]), "total_amount": r["total_amount"],
            "tracking_number": r["tracking_number"], "tracking_status": r["tracking_status"],
            "created_at": r["created_at"],
        })
    return jsonify({"ok": True, "orders": orders})


@app.route("/api/customer/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=%s AND user_id=%s", (order_id, uid)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Order not found."}), 404
        if row["status"] not in ("processing", "confirmed"):
            return jsonify({"ok": False, "error": f"Cannot cancel an order with status '{row['status']}'."}), 400
        conn.execute("UPDATE orders SET status='cancelled', tracking_status=NULL WHERE id=%s", (order_id,))
    return jsonify({"ok": True, "message": "Order cancelled."})


@app.route("/api/customer/orders/<int:order_id>/track", methods=["GET"])
def track_order(order_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=%s AND user_id=%s", (order_id, uid)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Order not found."}), 404
    return jsonify({"ok": True, "tracking": {
        "order_ref": row["order_ref"], "tracking_number": row["tracking_number"],
        "tracking_status": row["tracking_status"], "order_status": row["status"],
    }})


# ── Bookings ────────────────────────────────────────────────────────────────

@app.route("/api/customer/bookings", methods=["POST"])
def create_booking():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data = request.get_json(force=True)
    professional_name     = (data.get("professional_name")     or "").strip()
    professional_username = (data.get("professional_username") or "").strip()
    service      = (data.get("service")      or "").strip()
    booking_date = (data.get("booking_date") or "").strip()
    amount       = float(data.get("amount") or 0)
    note         = (data.get("note") or "").strip() or None
    if not professional_name or not service or not booking_date:
        return jsonify({"ok": False, "error": "professional_name, service, and booking_date are required."}), 400

    # Resolve professional user_id for dashboard cross-posting
    professional_id = None
    with get_db() as conn:
        if professional_username:
            row = conn.execute(
                "SELECT user_id FROM professional_profiles WHERE username=%s",
                (professional_username,)
            ).fetchone()
            if row:
                professional_id = row["user_id"]
        if not professional_id and professional_name:
            row = conn.execute(
                "SELECT id FROM users WHERE LOWER(display_name)=LOWER(%s) AND role IN ('professional', 'studio') LIMIT 1",
                (professional_name,)
            ).fetchone()
            if row:
                professional_id = row["id"]

    with get_db() as conn:
        # Get customer display info for the professional's request card
        cust = conn.execute(
            "SELECT email, display_name FROM users WHERE id=%s", (uid,)
        ).fetchone()
        client_name  = (cust["display_name"] or cust["email"]) if cust else "Customer"
        client_email = cust["email"] if cust else None

        cur = conn.execute(
            """INSERT INTO bookings
               (user_id, professional_name, service, booking_date, status, amount, note, professional_id)
               VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s) RETURNING id""",
            (uid, professional_name, service, booking_date, amount, note, professional_id),
        )
        booking_id = cur.fetchone()["id"]

        # Cross-post to professional_requests so it appears on the pro's dashboard
        if professional_id:
            conn.execute(
                """INSERT INTO professional_requests
                   (professional_id, client_name, client_email, service, booking_date, amount, note, status, booking_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                (professional_id, client_name, client_email, service, booking_date, amount, note, booking_id),
            )
            create_notification(professional_id, "New Booking Request", f"{client_name} requested a booking for {service} on {booking_date}.", ntype="booking", link="professional-dashboard.html", conn=conn)

        create_notification(uid, "Booking Submitted", f"Your booking request for {service} has been submitted.", ntype="booking", link="orders.html", conn=conn)

    return jsonify({"ok": True, "booking_id": booking_id, "status": "pending"})


@app.route("/api/customer/bookings", methods=["GET"])
def customer_bookings():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE user_id=%s ORDER BY booking_date DESC", (uid,)
        ).fetchall()
    return jsonify({"ok": True, "bookings": [dict(r) for r in rows]})


@app.route("/api/customer/bookings/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id=%s AND user_id=%s", (booking_id, uid)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Booking not found."}), 404
        if row["status"] in ("cancelled", "completed"):
            return jsonify({"ok": False, "error": f"Cannot cancel a booking with status '{row['status']}'."}), 400
        conn.execute("UPDATE bookings SET status='cancelled' WHERE id=%s", (booking_id,))
    return jsonify({"ok": True, "message": "Booking cancelled."})


# ── Refunds ─────────────────────────────────────────────────────────────────

@app.route("/api/customer/refunds", methods=["GET"])
def customer_refunds():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT r.*, o.order_ref FROM refunds r LEFT JOIN orders o ON r.order_id=o.id WHERE r.user_id=%s ORDER BY r.created_at DESC",
            (uid,)
        ).fetchall()
    return jsonify({"ok": True, "refunds": [dict(r) for r in rows]})


@app.route("/api/customer/refunds", methods=["POST"])
def request_refund():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data     = request.get_json(force=True)
    order_id = data.get("order_id")
    reason   = (data.get("reason") or "").strip()
    if not order_id:
        return jsonify({"ok": False, "error": "order_id is required."}), 400
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=%s AND user_id=%s", (order_id, uid)).fetchone()
        if not order:
            return jsonify({"ok": False, "error": "Order not found."}), 404
        if order["status"] not in ("cancelled", "delivered"):
            return jsonify({"ok": False, "error": "Refunds can only be requested for delivered or cancelled orders."}), 400
        existing = conn.execute("SELECT id FROM refunds WHERE order_id=%s AND user_id=%s AND status!='rejected'", (order_id, uid)).fetchone()
        if existing:
            return jsonify({"ok": False, "error": "A refund request already exists for this order."}), 409
        conn.execute(
            "INSERT INTO refunds (order_id,user_id,amount,reason,status) VALUES (%s,%s,%s,%s,'pending')",
            (order_id, uid, order["total_amount"], reason),
        )
    return jsonify({"ok": True, "message": "Refund request submitted."})


# ── Payment Methods ─────────────────────────────────────────────────────────

@app.route("/api/customer/payment-methods", methods=["GET"])
def get_payment_methods():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM payment_methods WHERE user_id=%s ORDER BY is_default DESC, created_at DESC", (uid,)).fetchall()
    return jsonify({"ok": True, "methods": [dict(r) for r in rows]})


@app.route("/api/customer/payment-methods", methods=["POST"])
def add_payment_method():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data  = request.get_json(force=True)
    mtype = (data.get("type")  or "card").strip().lower()
    label = (data.get("label") or "").strip()
    last4 = (data.get("last4") or "").strip()
    if not label:
        return jsonify({"ok": False, "error": "Label is required."}), 400
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM payment_methods WHERE user_id=%s", (uid,)).fetchone()['c']
        is_default = 1 if count == 0 else 0
        conn.execute(
            "INSERT INTO payment_methods (user_id,type,label,last4,is_default) VALUES (%s,%s,%s,%s,%s)",
            (uid, mtype, label, last4, is_default),
        )
    return jsonify({"ok": True, "message": "Payment method added."})


@app.route("/api/customer/payment-methods/<int:method_id>", methods=["DELETE"])
def delete_payment_method(method_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        row = conn.execute("SELECT * FROM payment_methods WHERE id=%s AND user_id=%s", (method_id, uid)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Payment method not found."}), 404
        conn.execute("DELETE FROM payment_methods WHERE id=%s", (method_id,))
        if row["is_default"]:
            # PostgreSQL doesn't support ORDER BY/LIMIT in UPDATE directly — use a subquery
            conn.execute("""
                UPDATE payment_methods SET is_default=1
                WHERE id = (
                    SELECT id FROM payment_methods
                    WHERE user_id=%s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
            """, (uid,))
    return jsonify({"ok": True, "message": "Payment method removed."})


@app.route("/api/customer/payment-methods/<int:method_id>/default", methods=["PATCH"])
def set_default_payment(method_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        if not conn.execute("SELECT id FROM payment_methods WHERE id=%s AND user_id=%s", (method_id, uid)).fetchone():
            return jsonify({"ok": False, "error": "Payment method not found."}), 404
        conn.execute("UPDATE payment_methods SET is_default=0 WHERE user_id=%s", (uid,))
        conn.execute("UPDATE payment_methods SET is_default=1 WHERE id=%s", (method_id,))
    return jsonify({"ok": True})


# ── Addresses ───────────────────────────────────────────────────────────────

@app.route("/api/customer/addresses", methods=["GET"])
def get_addresses():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM addresses WHERE user_id=%s ORDER BY is_default DESC, id DESC", (uid,)).fetchall()
    return jsonify({"ok": True, "addresses": [dict(r) for r in rows]})


@app.route("/api/customer/addresses", methods=["POST"])
def add_address():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    d = request.get_json(force=True)
    required = ["full_name", "line1", "city", "state", "pincode"]
    for f in required:
        if not (d.get(f) or "").strip():
            return jsonify({"ok": False, "error": f"'{f}' is required."}), 400
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM addresses WHERE user_id=%s", (uid,)).fetchone()['c']
        is_default = 1 if count == 0 else int(bool(d.get("is_default")))
        if is_default:
            conn.execute("UPDATE addresses SET is_default=0 WHERE user_id=%s", (uid,))
        conn.execute(
            "INSERT INTO addresses (user_id,label,full_name,line1,line2,city,state,pincode,phone,is_default) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (uid, (d.get("label") or "Home").strip(), d["full_name"].strip(),
             d["line1"].strip(), (d.get("line2") or "").strip(),
             d["city"].strip(), d["state"].strip(), d["pincode"].strip(),
             (d.get("phone") or "").strip(), is_default),
        )
    return jsonify({"ok": True, "message": "Address added."})


@app.route("/api/customer/addresses/<int:addr_id>", methods=["PATCH"])
def update_address(addr_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    d = request.get_json(force=True)
    with get_db() as conn:
        if not conn.execute("SELECT id FROM addresses WHERE id=%s AND user_id=%s", (addr_id, uid)).fetchone():
            return jsonify({"ok": False, "error": "Address not found."}), 404
        conn.execute("""UPDATE addresses SET label=%s,full_name=%s,line1=%s,line2=%s,city=%s,state=%s,pincode=%s,phone=%s WHERE id=%s""",
            ((d.get("label") or "Home").strip(), (d.get("full_name") or "").strip(),
             (d.get("line1") or "").strip(), (d.get("line2") or "").strip(),
             (d.get("city") or "").strip(), (d.get("state") or "").strip(),
             (d.get("pincode") or "").strip(), (d.get("phone") or "").strip(), addr_id))
    return jsonify({"ok": True, "message": "Address updated."})


@app.route("/api/customer/addresses/<int:addr_id>", methods=["DELETE"])
def delete_address(addr_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        if not conn.execute("SELECT id FROM addresses WHERE id=%s AND user_id=%s", (addr_id, uid)).fetchone():
            return jsonify({"ok": False, "error": "Address not found."}), 404
        conn.execute("DELETE FROM addresses WHERE id=%s", (addr_id,))
    return jsonify({"ok": True, "message": "Address deleted."})


@app.route("/api/customer/addresses/<int:addr_id>/default", methods=["PATCH"])
def set_default_address(addr_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        if not conn.execute("SELECT id FROM addresses WHERE id=%s AND user_id=%s", (addr_id, uid)).fetchone():
            return jsonify({"ok": False, "error": "Address not found."}), 404
        conn.execute("UPDATE addresses SET is_default=0 WHERE user_id=%s", (uid,))
        conn.execute("UPDATE addresses SET is_default=1 WHERE id=%s", (addr_id,))
    return jsonify({"ok": True})


# ── Aadhaar Verification ────────────────────────────────────────────────────

def _verify_aadhaar_with_provider(aadhaar: str) -> dict:
    """
    Verification logic isolated here so it can be swapped for a real
    KYC provider (e.g. UIDAI / Sandbox.co.in) without touching the route.

    Returns a dict with keys: verified (bool), name (str), message (str).
    Raises an exception if the provider call fails.
    """
    # Demo-safe: accept any valid 12-digit number
    return {
        "verified": True,
        "name":     "Demo User",
        "message":  "Aadhaar verified successfully.",
    }


@app.route("/api/verify-aadhar", methods=["POST"])
def verify_aadhar():
    data    = request.get_json(force=True, silent=True) or {}
    aadhaar = data.get("aadhaar")

    # Validate format
    if not aadhaar or not isinstance(aadhaar, str):
        return jsonify({"error": "Invalid Aadhaar number."}), 400

    aadhaar = aadhaar.strip()
    if not aadhaar.isdigit() or len(aadhaar) != 12:
        return jsonify({"error": "Invalid Aadhaar number."}), 400

    try:
        result = _verify_aadhaar_with_provider(aadhaar)
    except Exception:
        return jsonify({"error": "Unable to verify Aadhaar."}), 500

    return jsonify(result), 200


# ── Rewards & Coupons ───────────────────────────────────────────────────────

@app.route("/api/customer/rewards", methods=["GET"])
def customer_rewards():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        rw  = conn.execute("SELECT * FROM rewards WHERE user_id=%s", (uid,)).fetchone()
        cps = conn.execute("SELECT * FROM coupons WHERE user_id=%s AND used=0 ORDER BY expires_at ASC", (uid,)).fetchall()
    points = rw["points"] if rw else 0
    tier   = rw["tier"]   if rw else "Bronze"
    tier_thresholds = {"Bronze": 0, "Silver": 1000, "Gold": 5000}
    next_tier = {"Bronze": ("Silver", 1000), "Silver": ("Gold", 5000), "Gold": (None, None)}
    nt_name, nt_pts = next_tier[tier]
    progress = 0
    if nt_pts:
        cur_floor = tier_thresholds[tier]
        progress = min(100, int((points - cur_floor) / (nt_pts - cur_floor) * 100))
    return jsonify({"ok": True, "rewards": {
        "points": points, "tier": tier,
        "next_tier": nt_name, "next_tier_points": nt_pts, "progress": progress,
        "coupons": [dict(c) for c in cps],
    }})


# ── Products (Sales catalogue) ──────────────────────────────────────────────

@app.route("/api/products", methods=["GET"])
def list_products():
    category = request.args.get("category", "")
    with get_db() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM products WHERE category=%s ORDER BY created_at DESC",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM products ORDER BY created_at DESC"
            ).fetchall()
    return jsonify({"ok": True, "products": [dict(r) for r in rows]})


@app.route("/api/products", methods=["POST"])
def create_product():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        user = conn.execute("SELECT role FROM users WHERE id=%s", (uid,)).fetchone()
    if not user or user["role"] != "admin":
        return jsonify({"ok": False, "error": "Admin only."}), 403

    data = request.get_json(force=True, silent=True) or {}
    name     = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Product name is required."}), 400

    sku         = (data.get("sku") or "").strip() or None
    category    = (data.get("category") or "Other").strip()
    price       = float(data.get("price") or 0)
    stock       = int(data.get("stock") or 0)
    description = (data.get("description") or "").strip() or None
    image_url   = (data.get("image_url") or "").strip() or None
    badge       = (data.get("badge") or "").strip() or None

    with get_db() as conn:
        conn.execute(
            """INSERT INTO products (name, sku, category, price, stock, description, image_url, badge)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (name, sku, category, price, stock, description, image_url, badge)
        )
        conn.commit()
        product = conn.execute(
            "SELECT * FROM products WHERE name=%s ORDER BY created_at DESC LIMIT 1",
            (name,)
        ).fetchone()
    return jsonify({"ok": True, "product": dict(product)}), 201


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        user = conn.execute("SELECT role FROM users WHERE id=%s", (uid,)).fetchone()
    if not user or user["role"] != "admin":
        return jsonify({"ok": False, "error": "Admin only."}), 403

    with get_db() as conn:
        conn.execute("DELETE FROM products WHERE id=%s", (product_id,))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/products/<int:product_id>", methods=["PATCH"])
def update_product(product_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        user = conn.execute("SELECT role FROM users WHERE id=%s", (uid,)).fetchone()
    if not user or user["role"] != "admin":
        return jsonify({"ok": False, "error": "Admin only."}), 403

    data    = request.get_json(force=True, silent=True) or {}
    allowed = ["name", "sku", "category", "price", "stock", "description", "image_url", "badge"]
    sets    = []
    vals    = []
    for key in allowed:
        if key in data:
            sets.append(f"{key}=%s")
            vals.append(data[key])
    if not sets:
        return jsonify({"ok": False, "error": "Nothing to update."}), 400
    vals.append(product_id)
    with get_db() as conn:
        conn.execute(f"UPDATE products SET {', '.join(sets)} WHERE id=%s", vals)
        conn.commit()
        product = conn.execute("SELECT * FROM products WHERE id=%s", (product_id,)).fetchone()
    if not product:
        return jsonify({"ok": False, "error": "Not found."}), 404
    return jsonify({"ok": True, "product": dict(product)})


# ---------------------------------------------------------------------------
# Cart — per-user, DB-backed
# ---------------------------------------------------------------------------

@app.route("/api/cart", methods=["GET"])
def get_cart():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM cart_items WHERE user_id=%s ORDER BY created_at ASC",
            (uid,)
        ).fetchall()
    items = [dict(r) for r in rows]
    subtotal = sum(r["price"] * r["quantity"] for r in items)
    return jsonify({"ok": True, "items": items, "subtotal": round(subtotal, 2), "count": sum(r["quantity"] for r in items)})


@app.route("/api/cart", methods=["POST"])
def add_to_cart():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data       = request.get_json(force=True, silent=True) or {}
    product_id = data.get("product_id")
    name       = (data.get("name") or "").strip()
    price      = float(data.get("price") or 0)
    quantity   = max(1, int(data.get("quantity") or 1))
    image_url  = (data.get("image_url") or "").strip() or None
    category   = (data.get("category") or "").strip() or None

    # If product_id given, resolve name/price/image from DB
    if product_id:
        with get_db() as conn:
            prod = conn.execute("SELECT * FROM products WHERE id=%s", (product_id,)).fetchone()
        if not prod:
            return jsonify({"ok": False, "error": "Product not found."}), 404
        name      = prod["name"]
        price     = prod["price"]
        image_url = prod["image_url"]
        category  = prod["category"]
    elif not name or price <= 0:
        return jsonify({"ok": False, "error": "name and price are required when product_id is not given."}), 400

    with get_db() as conn:
        # If same product already in cart, increment quantity
        if product_id:
            existing = conn.execute(
                "SELECT id, quantity FROM cart_items WHERE user_id=%s AND product_id=%s",
                (uid, product_id)
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id, quantity FROM cart_items WHERE user_id=%s AND name=%s AND product_id IS NULL",
                (uid, name)
            ).fetchone()

        if existing:
            new_qty = existing["quantity"] + quantity
            conn.execute("UPDATE cart_items SET quantity=%s WHERE id=%s", (new_qty, existing["id"]))
            row = conn.execute("SELECT * FROM cart_items WHERE id=%s", (existing["id"],)).fetchone()
        else:
            row = conn.execute(
                """INSERT INTO cart_items (user_id, product_id, name, price, quantity, image_url, category)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (uid, product_id, name, price, quantity, image_url, category)
            ).fetchone()
    return jsonify({"ok": True, "item": dict(row)}), 201


@app.route("/api/cart/<int:item_id>", methods=["PATCH"])
def update_cart_item(item_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    data     = request.get_json(force=True, silent=True) or {}
    quantity = int(data.get("quantity") or 0)
    if quantity <= 0:
        return jsonify({"ok": False, "error": "quantity must be >= 1."}), 400
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM cart_items WHERE id=%s AND user_id=%s", (item_id, uid)).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("UPDATE cart_items SET quantity=%s WHERE id=%s", (quantity, item_id))
        row = conn.execute("SELECT * FROM cart_items WHERE id=%s", (item_id,)).fetchone()
    return jsonify({"ok": True, "item": dict(row)})


@app.route("/api/cart/<int:item_id>", methods=["DELETE"])
def remove_cart_item(item_id):
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM cart_items WHERE id=%s AND user_id=%s", (item_id, uid)).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("DELETE FROM cart_items WHERE id=%s", (item_id,))
    return jsonify({"ok": True})


@app.route("/api/cart", methods=["DELETE"])
def clear_cart():
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        conn.execute("DELETE FROM cart_items WHERE user_id=%s", (uid,))
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Rental Equipment — public listing
# ---------------------------------------------------------------------------

@app.route("/api/rental-equipment", methods=["GET"])
def list_rental_equipment():
    """Public: list all available rental equipment (optionally filter by category)."""
    category = request.args.get("category", "").strip()
    with get_db() as conn:
        if category and category.lower() != "all":
            rows = conn.execute(
                """SELECT re.*, u.display_name AS professional_name
                   FROM rental_equipment re
                   JOIN users u ON u.id = re.professional_id
                   WHERE re.available = TRUE AND LOWER(re.category) = LOWER(%s)
                   ORDER BY re.created_at DESC""",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT re.*, u.display_name AS professional_name
                   FROM rental_equipment re
                   JOIN users u ON u.id = re.professional_id
                   WHERE re.available = TRUE
                   ORDER BY re.created_at DESC"""
            ).fetchall()
    return jsonify({"ok": True, "equipment": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# Rental Equipment — professional management
# ---------------------------------------------------------------------------

def _require_professional():
    """Return user_id if session user is a professional/studio/admin, else None."""
    uid = require_auth()
    if not uid:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT role FROM users WHERE id=%s", (uid,)).fetchone()
    if row and row["role"] in ("professional", "studio", "admin"):
        return uid
    return None


@app.route("/api/professional/rental-equipment", methods=["GET"])
def pro_list_rental_equipment():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM rental_equipment WHERE professional_id=%s ORDER BY created_at DESC",
            (uid,)
        ).fetchall()
    return jsonify({"ok": True, "equipment": [dict(r) for r in rows]})


@app.route("/api/professional/rental-equipment", methods=["POST"])
def pro_add_rental_equipment():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data = request.get_json(force=True, silent=True) or {}
    name          = (data.get("name") or "").strip()
    category      = (data.get("category") or "Camera").strip()
    description   = (data.get("description") or "").strip()
    price_per_day = float(data.get("price_per_day") or 0)
    available     = bool(data.get("available", True))
    image_url     = (data.get("image_url") or "").strip() or None
    if not name:
        return jsonify({"ok": False, "error": "Equipment name is required."}), 400
    if price_per_day <= 0:
        return jsonify({"ok": False, "error": "Price per day must be greater than 0."}), 400
    with get_db() as conn:
        row = conn.execute(
            """INSERT INTO rental_equipment
               (professional_id, name, category, description, price_per_day, available, image_url)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uid, name, category, description, price_per_day, available, image_url)
        ).fetchone()
    return jsonify({"ok": True, "equipment": dict(row)}), 201


@app.route("/api/professional/rental-equipment/<int:equip_id>", methods=["PUT"])
def pro_edit_rental_equipment(equip_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data = request.get_json(force=True, silent=True) or {}
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM rental_equipment WHERE id=%s AND professional_id=%s",
            (equip_id, uid)
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        name          = (data.get("name") or existing["name"]).strip()
        category      = (data.get("category") or existing["category"]).strip()
        description   = (data.get("description") or existing["description"] or "").strip()
        price_per_day = float(data.get("price_per_day") or existing["price_per_day"])
        available     = data.get("available", existing["available"])
        image_url     = data.get("image_url", existing["image_url"])
        conn.execute(
            """UPDATE rental_equipment
               SET name=%s, category=%s, description=%s, price_per_day=%s, available=%s, image_url=%s
               WHERE id=%s AND professional_id=%s""",
            (name, category, description, price_per_day, available, image_url, equip_id, uid)
        )
        row = conn.execute("SELECT * FROM rental_equipment WHERE id=%s", (equip_id,)).fetchone()
    return jsonify({"ok": True, "equipment": dict(row)})


@app.route("/api/professional/rental-equipment/<int:equip_id>", methods=["DELETE"])
def pro_delete_rental_equipment(equip_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM rental_equipment WHERE id=%s AND professional_id=%s",
            (equip_id, uid)
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("DELETE FROM rental_equipment WHERE id=%s", (equip_id,))
    return jsonify({"ok": True})


@app.route("/api/professional/rental-equipment/<int:equip_id>/availability", methods=["PATCH"])
def pro_toggle_rental_availability(equip_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data = request.get_json(force=True, silent=True) or {}
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM rental_equipment WHERE id=%s AND professional_id=%s",
            (equip_id, uid)
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        new_val = data.get("available", not existing["available"])
        conn.execute(
            "UPDATE rental_equipment SET available=%s WHERE id=%s",
            (new_val, equip_id)
        )
        row = conn.execute("SELECT * FROM rental_equipment WHERE id=%s", (equip_id,)).fetchone()
    return jsonify({"ok": True, "equipment": dict(row)})


# ---------------------------------------------------------------------------
# Rental Orders — customers place requests, professionals manage them
# ---------------------------------------------------------------------------

@app.route("/api/rental-orders", methods=["POST"])
def place_rental_order():
    """Customer places a rental request. Auth optional — name/email required in body."""
    data           = request.get_json(force=True, silent=True) or {}
    equipment_id   = data.get("equipment_id")
    customer_name  = (data.get("customer_name") or "").strip()
    customer_email = (data.get("customer_email") or "").strip()
    from_date      = (data.get("from_date") or "").strip()
    to_date        = (data.get("to_date") or "").strip()
    notes          = (data.get("notes") or "").strip()
    customer_id    = require_auth()

    if not equipment_id or not customer_name or not customer_email or not from_date or not to_date:
        return jsonify({"ok": False, "error": "equipment_id, customer_name, customer_email, from_date, and to_date are required."}), 400

    try:
        from datetime import date as _date
        d1 = _date.fromisoformat(from_date)
        d2 = _date.fromisoformat(to_date)
        if d1 < _date.today():
            return jsonify({"ok": False, "error": "Rental start date cannot be in the past."}), 400
        if d2 <= d1:
            return jsonify({"ok": False, "error": "to_date must be after from_date."}), 400
        days = (d2 - d1).days
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400

    with get_db() as conn:
        equip = conn.execute(
            "SELECT * FROM rental_equipment WHERE id=%s AND available=TRUE",
            (equipment_id,)
        ).fetchone()
        if not equip:
            return jsonify({"ok": False, "error": "Equipment not found or not available."}), 404

        overlap = conn.execute(
            """SELECT id FROM rental_orders
               WHERE equipment_id=%s AND status IN ('accepted', 'active')
               AND NOT (to_date <= %s OR from_date >= %s) LIMIT 1""",
            (equipment_id, from_date, to_date)
        ).fetchone()
        if overlap:
            return jsonify({"ok": False, "error": "Equipment is already booked for the selected date range."}), 400
        total_cost = round(equip["price_per_day"] * days, 2)
        row = conn.execute(
            """INSERT INTO rental_orders
               (equipment_id, professional_id, customer_id, customer_name, customer_email,
                from_date, to_date, days, total_cost, notes, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending') RETURNING *""",
            (equipment_id, equip["professional_id"], customer_id,
             customer_name, customer_email, from_date, to_date, days, total_cost, notes)
        ).fetchone()

        create_notification(equip["professional_id"], "New Rental Request", f"{customer_name} requested to rent '{equip['name']}' ({from_date} to {to_date}).", ntype="rental", link="professional-dashboard.html", conn=conn)
        if customer_id:
            create_notification(customer_id, "Rental Request Submitted", f"Your rental request for '{equip['name']}' has been submitted.", ntype="rental", link="orders.html", conn=conn)
    return jsonify({"ok": True, "order": dict(row)}), 201


@app.route("/api/professional/rental-orders", methods=["GET"])
def pro_list_rental_orders():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ro.*, re.name AS equipment_name
               FROM rental_orders ro
               JOIN rental_equipment re ON re.id = ro.equipment_id
               WHERE ro.professional_id=%s
               ORDER BY ro.created_at DESC""",
            (uid,)
        ).fetchall()
    return jsonify({"ok": True, "orders": [dict(r) for r in rows]})


@app.route("/api/professional/rental-orders/<int:order_id>", methods=["PATCH"])
def pro_update_rental_order(order_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data       = request.get_json(force=True, silent=True) or {}
    new_status = (data.get("status") or "").strip()
    allowed    = ("pending", "accepted", "active", "completed", "declined")
    if new_status not in allowed:
        return jsonify({"ok": False, "error": f"status must be one of {allowed}"}), 400
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM rental_orders WHERE id=%s AND professional_id=%s",
            (order_id, uid)
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute(
            "UPDATE rental_orders SET status=%s WHERE id=%s",
            (new_status, order_id)
        )
        row = conn.execute(
            """SELECT ro.*, re.name AS equipment_name
               FROM rental_orders ro
               JOIN rental_equipment re ON re.id = ro.equipment_id
               WHERE ro.id=%s""",
            (order_id,)
        ).fetchone()
        if existing.get("customer_id"):
            create_notification(existing["customer_id"], "Rental Request Updated", f"Your rental request for equipment has been updated to '{new_status}'.", ntype="rental", link="orders.html", conn=conn)
    return jsonify({"ok": True, "order": dict(row)})


# ---------------------------------------------------------------------------
# Professional Dashboard — Requests, Jobs, Vault, Overview, Earnings
# ---------------------------------------------------------------------------

@app.route("/api/professional/seed", methods=["POST"])
def professional_seed():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    seed_professional_data(uid)
    return jsonify({"ok": True})


@app.route("/api/professional/overview", methods=["GET"])
def professional_overview():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        pending_requests = conn.execute(
            "SELECT COUNT(*) AS c FROM professional_requests WHERE professional_id=%s AND status='pending'", (uid,)
        ).fetchone()['c']
        active_jobs = conn.execute(
            "SELECT COUNT(*) AS c FROM professional_jobs WHERE professional_id=%s AND status IN ('active','confirmed')", (uid,)
        ).fetchone()['c']
        total_earnings = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS s FROM professional_jobs WHERE professional_id=%s AND status='completed'", (uid,)
        ).fetchone()['s']
        vault_files_count = conn.execute(
            "SELECT COUNT(*) AS c FROM vault_files WHERE professional_id=%s", (uid,)
        ).fetchone()['c']
        recent_requests = conn.execute(
            "SELECT * FROM professional_requests WHERE professional_id=%s ORDER BY created_at DESC LIMIT 5", (uid,)
        ).fetchall()
        # Rentals stats
        rental_income = conn.execute(
            "SELECT COALESCE(SUM(total_cost),0) AS s FROM rental_orders WHERE professional_id=%s AND status='completed'", (uid,)
        ).fetchone()['s']
        pending_rentals = conn.execute(
            "SELECT COUNT(*) AS c FROM rental_orders WHERE professional_id=%s AND status='pending'", (uid,)
        ).fetchone()['c']
        active_rentals = conn.execute(
            "SELECT COUNT(*) AS c FROM rental_orders WHERE professional_id=%s AND status IN ('accepted','active')", (uid,)
        ).fetchone()['c']
        # Sales stats
        sales_revenue = conn.execute(
            "SELECT COALESCE(SUM(total_price),0) AS s FROM pro_sale_items WHERE seller_id=%s", (uid,)
        ).fetchone()['s']
        product_count = conn.execute(
            "SELECT COUNT(*) AS c FROM products WHERE seller_id=%s", (uid,)
        ).fetchone()['c']
    return jsonify({"ok": True, "overview": {
        "pending_requests": pending_requests,
        "active_jobs":      active_jobs,
        "total_earnings":   float(total_earnings),
        "vault_files":      vault_files_count,
        "recent_requests":  [dict(r) for r in recent_requests],
        "rental_income":    float(rental_income),
        "pending_rentals":  pending_rentals,
        "active_rentals":   active_rentals,
        "sales_revenue":    float(sales_revenue),
        "product_count":    product_count,
    }})


# ── Requests ──────────────────────────────────────────────────────────────

@app.route("/api/professional/requests", methods=["GET"])
def pro_list_requests():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM professional_requests WHERE professional_id=%s ORDER BY created_at DESC", (uid,)
        ).fetchall()
    return jsonify({"ok": True, "requests": [dict(r) for r in rows]})


@app.route("/api/professional/requests", methods=["POST"])
def pro_create_request():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data         = request.get_json(force=True, silent=True) or {}
    client_name  = (data.get("client_name")  or "").strip()
    service      = (data.get("service")      or "").strip()
    booking_date = (data.get("booking_date") or "").strip()
    if not client_name or not service or not booking_date:
        return jsonify({"ok": False, "error": "client_name, service, and booking_date are required."}), 400
    client_email = (data.get("client_email") or "").strip() or None
    amount       = float(data.get("amount") or 0)
    note         = (data.get("note") or "").strip() or None
    with get_db() as conn:
        row = conn.execute(
            """INSERT INTO professional_requests
               (professional_id,client_name,client_email,service,booking_date,amount,note,status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'pending') RETURNING *""",
            (uid, client_name, client_email, service, booking_date, amount, note)
        ).fetchone()
    return jsonify({"ok": True, "request": dict(row)}), 201


@app.route("/api/professional/requests/<int:req_id>", methods=["PATCH"])
def pro_update_request(req_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data       = request.get_json(force=True, silent=True) or {}
    new_status = (data.get("status") or "").strip()
    allowed    = ("pending", "confirmed", "declined", "completed")
    if new_status not in allowed:
        return jsonify({"ok": False, "error": f"status must be one of {allowed}"}), 400
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM professional_requests WHERE id=%s AND professional_id=%s", (req_id, uid)
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("UPDATE professional_requests SET status=%s WHERE id=%s", (new_status, req_id))
        row = conn.execute("SELECT * FROM professional_requests WHERE id=%s", (req_id,)).fetchone()
        # Sync status back to the originating customer booking
        if existing.get("booking_id"):
            booking_status = {
                "confirmed": "confirmed",
                "declined":  "cancelled",
                "completed": "completed",
                "pending":   "pending",
            }.get(new_status, new_status)
            conn.execute(
                "UPDATE bookings SET status=%s WHERE id=%s",
                (booking_status, existing["booking_id"])
            )
        if new_status in ("confirmed", "completed"):
            job_exists = conn.execute(
                "SELECT id FROM professional_jobs WHERE professional_id=%s AND client=%s AND service=%s AND booking_date=%s",
                (uid, existing["client_name"], existing["service"], existing["booking_date"])
            ).fetchone()
            if not job_exists:
                conn.execute(
                    """INSERT INTO professional_jobs (professional_id, client, service, booking_date, amount, status, notes)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (uid, existing["client_name"], existing["service"], existing["booking_date"], existing["amount"], new_status, existing["note"])
                )
            else:
                conn.execute(
                    "UPDATE professional_jobs SET status=%s WHERE id=%s",
                    (new_status, job_exists["id"])
                )
            b_row = conn.execute("SELECT user_id, service FROM bookings WHERE id=%s", (existing["booking_id"],)).fetchone()
            if b_row:
                create_notification(b_row["user_id"], "Booking Status Updated", f"Your booking request for '{b_row['service']}' status is now '{booking_status}'.", ntype="booking", link="orders.html", conn=conn)
    return jsonify({"ok": True, "request": dict(row)})


# ── Jobs ──────────────────────────────────────────────────────────────────

@app.route("/api/professional/jobs", methods=["GET"])
def pro_list_jobs():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM professional_jobs WHERE professional_id=%s ORDER BY created_at DESC", (uid,)
        ).fetchall()
    return jsonify({"ok": True, "jobs": [dict(r) for r in rows]})


@app.route("/api/professional/jobs", methods=["POST"])
def pro_create_job():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data         = request.get_json(force=True, silent=True) or {}
    client       = (data.get("client")       or "").strip()
    service      = (data.get("service")      or "").strip()
    booking_date = (data.get("booking_date") or data.get("date") or "").strip()
    if not client or not service or not booking_date:
        return jsonify({"ok": False, "error": "client, service, and booking_date are required."}), 400
    amount = float(data.get("amount") or 0)
    status = (data.get("status") or "pending").strip()
    notes  = (data.get("notes") or "").strip() or None
    with get_db() as conn:
        row = conn.execute(
            """INSERT INTO professional_jobs
               (professional_id,client,service,booking_date,amount,status,notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uid, client, service, booking_date, amount, status, notes)
        ).fetchone()
    return jsonify({"ok": True, "job": dict(row)}), 201


@app.route("/api/professional/jobs/<int:job_id>", methods=["PATCH"])
def pro_update_job(job_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data = request.get_json(force=True, silent=True) or {}
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM professional_jobs WHERE id=%s AND professional_id=%s", (job_id, uid)
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        allowed_statuses = ("pending", "confirmed", "active", "completed", "cancelled")
        new_status = (data.get("status") or existing["status"]).strip()
        if new_status not in allowed_statuses:
            return jsonify({"ok": False, "error": f"status must be one of {allowed_statuses}"}), 400
        conn.execute("UPDATE professional_jobs SET status=%s WHERE id=%s", (new_status, job_id))
        row = conn.execute("SELECT * FROM professional_jobs WHERE id=%s", (job_id,)).fetchone()
    return jsonify({"ok": True, "job": dict(row)})


@app.route("/api/professional/jobs/<int:job_id>", methods=["DELETE"])
def pro_delete_job(job_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM professional_jobs WHERE id=%s AND professional_id=%s", (job_id, uid)
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("DELETE FROM professional_jobs WHERE id=%s", (job_id,))
    return jsonify({"ok": True})


# ── Vault Folders ─────────────────────────────────────────────────────────

@app.route("/api/professional/vault/folders", methods=["GET"])
def pro_list_vault_folders():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM vault_folders WHERE professional_id=%s ORDER BY created_at ASC", (uid,)
        ).fetchall()
    return jsonify({"ok": True, "folders": [dict(r) for r in rows]})


@app.route("/api/professional/vault/folders", methods=["POST"])
def pro_create_vault_folder():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data  = request.get_json(force=True, silent=True) or {}
    name  = (data.get("name") or "").strip()
    color = (data.get("color") or "#00dbe9").strip()
    if not name:
        return jsonify({"ok": False, "error": "Folder name is required."}), 400
    with get_db() as conn:
        row = conn.execute(
            "INSERT INTO vault_folders (professional_id,name,color) VALUES (%s,%s,%s) RETURNING *",
            (uid, name, color)
        ).fetchone()
    return jsonify({"ok": True, "folder": dict(row)}), 201


@app.route("/api/professional/vault/folders/<int:folder_id>", methods=["DELETE"])
def pro_delete_vault_folder(folder_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        if not conn.execute(
            "SELECT id FROM vault_folders WHERE id=%s AND professional_id=%s", (folder_id, uid)
        ).fetchone():
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("DELETE FROM vault_files WHERE folder_id=%s AND professional_id=%s", (folder_id, uid))
        conn.execute("DELETE FROM vault_folders WHERE id=%s", (folder_id,))
    return jsonify({"ok": True})


# ── Vault Files ──────────────────────────────────────────────────────────

@app.route("/api/professional/vault/files", methods=["GET"])
def pro_list_vault_files():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    folder_id = request.args.get("folder_id")
    with get_db() as conn:
        if folder_id:
            rows = conn.execute(
                "SELECT * FROM vault_files WHERE professional_id=%s AND folder_id=%s ORDER BY created_at DESC",
                (uid, int(folder_id))
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM vault_files WHERE professional_id=%s ORDER BY created_at DESC", (uid,)
            ).fetchall()
    return jsonify({"ok": True, "files": [dict(r) for r in rows]})


@app.route("/api/professional/vault/files", methods=["POST"])
def pro_add_vault_file():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data      = request.get_json(force=True, silent=True) or {}
    name      = (data.get("name") or "").strip()
    file_type = (data.get("file_type") or "other").strip()
    file_size = int(data.get("file_size") or 0)
    folder_id = data.get("folder_id")
    file_url  = (data.get("file_url") or "").strip() or None
    if not name:
        return jsonify({"ok": False, "error": "File name is required."}), 400
    if folder_id:
        with get_db() as conn:
            if not conn.execute(
                "SELECT id FROM vault_folders WHERE id=%s AND professional_id=%s", (folder_id, uid)
            ).fetchone():
                return jsonify({"ok": False, "error": "Folder not found."}), 404
    share_id = 'shr_' + secrets.token_hex(6)
    with get_db() as conn:
        row = conn.execute(
            """INSERT INTO vault_files (professional_id,folder_id,name,file_type,file_size,file_url,share_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uid, folder_id, name, file_type, file_size, file_url, share_id)
        ).fetchone()
    return jsonify({"ok": True, "file": dict(row)}), 201


@app.route("/api/professional/vault/files/<int:file_id>", methods=["DELETE"])
def pro_delete_vault_file(file_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        if not conn.execute(
            "SELECT id FROM vault_files WHERE id=%s AND professional_id=%s", (file_id, uid)
        ).fetchone():
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("DELETE FROM vault_files WHERE id=%s", (file_id,))
    return jsonify({"ok": True})


@app.route("/api/professional/vault/files/<int:file_id>/move", methods=["PATCH"])
def pro_move_vault_file(file_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data      = request.get_json(force=True, silent=True) or {}
    folder_id = data.get("folder_id")  # None = root
    with get_db() as conn:
        if not conn.execute(
            "SELECT id FROM vault_files WHERE id=%s AND professional_id=%s", (file_id, uid)
        ).fetchone():
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("UPDATE vault_files SET folder_id=%s WHERE id=%s", (folder_id, file_id))
        row = conn.execute("SELECT * FROM vault_files WHERE id=%s", (file_id,)).fetchone()
    return jsonify({"ok": True, "file": dict(row)})


# ── Professional Products (Sales catalogue) ───────────────────────────────────

@app.route("/api/professional/products", methods=["GET"])
def pro_list_products():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM products WHERE seller_id=%s ORDER BY created_at DESC", (uid,)
        ).fetchall()
    return jsonify({"ok": True, "products": [dict(r) for r in rows]})


@app.route("/api/professional/products", methods=["POST"])
def pro_create_product():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data        = request.get_json(force=True, silent=True) or {}
    name        = (data.get("name")        or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Product name is required."}), 400
    sku         = (data.get("sku")         or "").strip() or None
    category    = (data.get("category")    or "Other").strip()
    price       = float(data.get("price")  or 0)
    stock       = int(data.get("stock")    or 0)
    description = (data.get("description") or "").strip() or None
    image_url   = (data.get("image_url")   or "").strip() or None
    badge_val   = (data.get("badge")       or "").strip() or None
    with get_db() as conn:
        row = conn.execute(
            """INSERT INTO products (name,sku,category,price,stock,description,image_url,badge,seller_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (name, sku, category, price, stock, description, image_url, badge_val, uid)
        ).fetchone()
    return jsonify({"ok": True, "product": dict(row)}), 201


@app.route("/api/professional/products/<int:product_id>", methods=["PATCH"])
def pro_update_product(product_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        if not conn.execute(
            "SELECT id FROM products WHERE id=%s AND seller_id=%s", (product_id, uid)
        ).fetchone():
            return jsonify({"ok": False, "error": "Not found."}), 404
        data    = request.get_json(force=True, silent=True) or {}
        allowed = ["name", "sku", "category", "price", "stock", "description", "image_url", "badge"]
        sets, vals = [], []
        for key in allowed:
            if key in data:
                sets.append(f"{key}=%s")
                vals.append(data[key])
        if not sets:
            return jsonify({"ok": False, "error": "Nothing to update."}), 400
        vals.append(product_id)
        conn.execute(f"UPDATE products SET {', '.join(sets)} WHERE id=%s", vals)
        row = conn.execute("SELECT * FROM products WHERE id=%s", (product_id,)).fetchone()
    return jsonify({"ok": True, "product": dict(row)})


@app.route("/api/professional/products/<int:product_id>", methods=["DELETE"])
def pro_delete_product(product_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        if not conn.execute(
            "SELECT id FROM products WHERE id=%s AND seller_id=%s", (product_id, uid)
        ).fetchone():
            return jsonify({"ok": False, "error": "Not found."}), 404
        conn.execute("DELETE FROM products WHERE id=%s", (product_id,))
    return jsonify({"ok": True})


# ── Professional Sales Orders ──────────────────────────────────────────────────

@app.route("/api/professional/sales", methods=["GET"])
def pro_sales():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        rows = conn.execute(
            """SELECT psi.*, o.order_ref, o.status AS order_status, o.checkout_payload_json,
                      u.email AS customer_email, u.display_name AS customer_name
               FROM pro_sale_items psi
               JOIN orders o ON o.id = psi.order_id
               JOIN users  u ON u.id = o.user_id
               WHERE psi.seller_id=%s
               ORDER BY psi.created_at DESC""",
            (uid,)
        ).fetchall()
    sales = []
    for r in rows:
        payload = _json.loads(r["checkout_payload_json"] or "{}") if r["checkout_payload_json"] else {}
        customer_name = (payload.get("customer_name") or payload.get("full_name") or "").strip() or r["customer_name"] or r["customer_email"]
        customer_email = (payload.get("customer_email") or "").strip() or r["customer_email"]
        sales.append({
            "id": r["id"],
            "seller_id": r["seller_id"],
            "order_id": r["order_id"],
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "quantity": r["quantity"],
            "unit_price": float(r["unit_price"] or 0),
            "total_price": float(r["total_price"] or 0),
            "created_at": r["created_at"],
            "order_ref": r["order_ref"],
            "order_status": r["order_status"],
            "customer_email": customer_email,
            "customer_name": customer_name,
            "checkout_payload": payload,
        })
    total_revenue = sum(float(item["total_price"]) for item in sales)
    return jsonify({"ok": True, "sales": sales, "total_revenue": total_revenue})


@app.route("/api/seller/sales", methods=["GET"])
def seller_sales():
    """Return sale items for the logged-in seller (works for professionals, studios, etc.)."""
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    with get_db() as conn:
        rows = conn.execute(
            """SELECT psi.*, o.order_ref, o.status AS order_status, o.checkout_payload_json,
                      u.email AS customer_email, u.display_name AS customer_name
               FROM pro_sale_items psi
               JOIN orders o ON o.id = psi.order_id
               JOIN users  u ON u.id = o.user_id
               WHERE psi.seller_id=%s
               ORDER BY psi.created_at DESC""",
            (uid,)
        ).fetchall()
    sales = []
    for r in rows:
        payload = _json.loads(r["checkout_payload_json"] or "{}") if r["checkout_payload_json"] else {}
        customer_name = (payload.get("customer_name") or payload.get("full_name") or "").strip() or r["customer_name"] or r["customer_email"]
        customer_email = (payload.get("customer_email") or "").strip() or r["customer_email"]
        sales.append({
            "id": r["id"],
            "seller_id": r["seller_id"],
            "order_id": r["order_id"],
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "quantity": r["quantity"],
            "unit_price": float(r["unit_price"] or 0),
            "total_price": float(r["total_price"] or 0),
            "created_at": r["created_at"],
            "order_ref": r["order_ref"],
            "order_status": r["order_status"],
            "customer_email": customer_email,
            "customer_name": customer_name,
            "checkout_payload": payload,
        })
    total_revenue = sum(float(item["total_price"]) for item in sales)
    return jsonify({"ok": True, "sales": sales, "total_revenue": total_revenue})


# ── Checkout / Place Order ─────────────────────────────────────────────────────

@app.route("/api/orders", methods=["POST"])
def place_order():
    """Create an order from the user's current cart and record professional sale items."""
    uid = require_auth()
    if not uid:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    import random, string as _str

    data = request.get_json(force=True, silent=True) or {}
    full_name = (data.get("customer_name") or data.get("full_name") or "").strip()
    email = (data.get("customer_email") or "").strip()
    phone = (data.get("customer_phone") or "").strip()
    shipping_address = data.get("shipping_address") or {}
    shipping_method = (data.get("shipping_method") or "").strip()
    payment_method = (data.get("payment_method") or "").strip()
    payment_details = data.get("payment_details") or {}
    notes = (data.get("notes") or "").strip()

    checkout_payload = {
        "customer_name": full_name,
        "customer_email": email,
        "customer_phone": phone,
        "shipping_address": shipping_address,
        "shipping_method": shipping_method,
        "payment_method": payment_method,
        "payment_details": payment_details,
        "notes": notes,
    }

    coupon_code = (data.get("coupon_code") or "").strip().upper()
    discount_amount = 0

    with get_db() as conn:
        cart_items = conn.execute(
            "SELECT * FROM cart_items WHERE user_id=%s", (uid,)
        ).fetchall()
        if not cart_items:
            return jsonify({"ok": False, "error": "Cart is empty."}), 400

        for ci in cart_items:
            if ci["product_id"]:
                prod = conn.execute("SELECT stock, name FROM products WHERE id=%s", (ci["product_id"],)).fetchone()
                if prod and prod["stock"] < ci["quantity"]:
                    return jsonify({"ok": False, "error": f"Product '{prod['name']}' has only {prod['stock']} items left in stock."}), 400

        subtotal = sum(ci["price"] * ci["quantity"] for ci in cart_items)
        total = subtotal

        if coupon_code:
            coupon = conn.execute(
                "SELECT * FROM coupons WHERE (user_id=%s OR user_id IS NULL) AND UPPER(code)=%s AND used=0",
                (uid, coupon_code)
            ).fetchone()
            if coupon:
                if subtotal >= float(coupon["min_order"] or 0):
                    if coupon["discount_type"] == "percent":
                        discount_amount = round(subtotal * (float(coupon["discount_value"]) / 100.0), 2)
                    else:
                        discount_amount = float(coupon["discount_value"])
                    discount_amount = min(discount_amount, subtotal)
                    total = round(subtotal - discount_amount, 2)
                    conn.execute("UPDATE coupons SET used=1 WHERE id=%s", (coupon["id"],))

        for _ in range(10):
            order_ref = 'CC-' + ''.join(random.choices(_str.digits, k=6))
            if not conn.execute("SELECT id FROM orders WHERE order_ref=%s", (order_ref,)).fetchone():
                break

        checkout_payload["subtotal"] = subtotal
        checkout_payload["discount_amount"] = discount_amount
        checkout_payload["coupon_code"] = coupon_code if discount_amount > 0 else None

        items_json_val = _json.dumps([{
            "name": ci["name"], "qty": ci["quantity"],
            "price": ci["price"], "product_id": ci["product_id"],
        } for ci in cart_items])
        order_row = conn.execute(
            """INSERT INTO orders (user_id,order_ref,status,items_json,total_amount,checkout_payload_json)
               VALUES (%s,%s,'processing',%s,%s,%s) RETURNING id""",
            (uid, order_ref, items_json_val, total, _json.dumps(checkout_payload))
        ).fetchone()
        order_id = order_row["id"]

        for ci in cart_items:
            if ci["product_id"]:
                conn.execute(
                    "UPDATE products SET stock = GREATEST(0, stock - %s) WHERE id=%s",
                    (ci["quantity"], ci["product_id"])
                )
                prod = conn.execute(
                    "SELECT seller_id FROM products WHERE id=%s", (ci["product_id"],)
                ).fetchone()
                if prod and prod["seller_id"]:
                    conn.execute(
                        """INSERT INTO pro_sale_items
                           (seller_id,order_id,product_id,product_name,quantity,unit_price,total_price)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (prod["seller_id"], order_id, ci["product_id"], ci["name"],
                         ci["quantity"], ci["price"], ci["price"] * ci["quantity"])
                    )
        conn.execute("DELETE FROM cart_items WHERE user_id=%s", (uid,))
        create_notification(uid, "Order Placed", f"Your order #{order_ref} total ₹{round(total, 2)} has been placed successfully.", ntype="order", link="orders.html", conn=conn)
        for ci in cart_items:
            if ci["product_id"]:
                prod = conn.execute("SELECT seller_id FROM products WHERE id=%s", (ci["product_id"],)).fetchone()
                if prod and prod["seller_id"]:
                    create_notification(prod["seller_id"], "New Sale Item", f"Your product '{ci['name']}' was ordered in order #{order_ref}.", ntype="order", link="professional-dashboard.html", conn=conn)
    return jsonify({"ok": True, "order_id": order_id, "order_ref": order_ref,
                    "status": "processing", "total": round(total, 2)})


# ── Earnings ─────────────────────────────────────────────────────────────

@app.route("/api/professional/earnings", methods=["GET"])
def professional_earnings():
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    with get_db() as conn:
        jobs = conn.execute(
            "SELECT * FROM professional_jobs WHERE professional_id=%s ORDER BY booking_date DESC", (uid,)
        ).fetchall()
        rental_income = conn.execute(
            "SELECT COALESCE(SUM(total_cost),0) AS s FROM rental_orders WHERE professional_id=%s AND status='completed'", (uid,)
        ).fetchone()['s']
        sales_revenue = conn.execute(
            "SELECT COALESCE(SUM(total_price),0) AS s FROM pro_sale_items WHERE seller_id=%s", (uid,)
        ).fetchone()['s']
    jobs_list  = [dict(j) for j in jobs]
    completed  = [j for j in jobs_list if j['status'] == 'completed']
    pending_js = [j for j in jobs_list if j['status'] in ('active', 'confirmed')]
    services_total = sum(float(j['amount'] or 0) for j in completed)
    pending    = sum(float(j['amount'] or 0) for j in pending_js)
    total      = services_total + float(rental_income or 0) + float(sales_revenue or 0)
    from datetime import date as _date
    today = _date.today()
    month = sum(
        float(j['amount'] or 0) for j in completed
        if j.get('booking_date') and j['booking_date'][:7] == today.strftime('%Y-%m')
    )
    return jsonify({"ok": True, "earnings": {
        "total":          round(total, 2),
        "services_total": round(services_total, 2),
        "rental_income":   round(float(rental_income or 0), 2),
        "sales_revenue":   round(float(sales_revenue or 0), 2),
        "pending":        round(pending, 2),
        "month":          round(month, 2),
        "jobs":           jobs_list,
    }})


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------

def require_admin():
    """Return user_id if session user is admin, else None."""
    uid = session.get("user_id")
    if not uid:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT role FROM users WHERE id=%s", (uid,)).fetchone()
    if row and row["role"] == "admin":
        return uid
    return None


@app.route("/api/admin/stats", methods=["GET"])
def admin_stats():
    uid = require_admin()
    if not uid:
        return jsonify({"ok": False, "error": "Admin only."}), 403
    with get_db() as conn:
        total_users       = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        customers         = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='customer'").fetchone()["c"]
        professionals     = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='professional'").fetchone()["c"]
        studios           = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='studio'").fetchone()["c"]
        total_orders      = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
        total_revenue     = conn.execute("SELECT COALESCE(SUM(total_amount),0) AS s FROM orders WHERE status!='cancelled'").fetchone()["s"]
        pending_verif     = conn.execute("SELECT COUNT(*) AS c FROM verification_requests WHERE status='pending'").fetchone()["c"]
        approved_verif    = conn.execute("SELECT COUNT(*) AS c FROM verification_requests WHERE status='approved'").fetchone()["c"]
        total_products    = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        low_stock         = conn.execute("SELECT COUNT(*) AS c FROM products WHERE stock <= 3").fetchone()["c"]
    return jsonify({"ok": True, "stats": {
        "total_users": total_users,
        "customers": customers,
        "professionals": professionals,
        "studios": studios,
        "total_orders": total_orders,
        "total_revenue": round(float(total_revenue), 2),
        "pending_verifications": pending_verif,
        "approved_verifications": approved_verif,
        "total_products": total_products,
        "low_stock_products": low_stock,
    }})


@app.route("/api/admin/orders", methods=["GET"])
def admin_list_orders():
    uid = require_admin()
    if not uid:
        return jsonify({"ok": False, "error": "Admin only."}), 403
    status_filter = request.args.get("status", "").strip()
    search        = request.args.get("q", "").strip()
    page          = max(1, int(request.args.get("page", 1)))
    per_page      = 20
    offset        = (page - 1) * per_page

    with get_db() as conn:
        base_sql = """
            SELECT o.*, u.email AS customer_email, u.display_name AS customer_name
            FROM orders o
            JOIN users u ON u.id = o.user_id
        """
        wheres, params = [], []
        if status_filter:
            wheres.append("o.status = %s"); params.append(status_filter)
        if search:
            wheres.append("(u.email ILIKE %s OR o.order_ref ILIKE %s)")
            params += [f"%{search}%", f"%{search}%"]
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""

        count_sql = f"SELECT COUNT(*) AS c FROM orders o JOIN users u ON u.id=o.user_id {where_clause}"
        total = conn.execute(count_sql, params).fetchone()["c"]

        rows = conn.execute(
            f"{base_sql} {where_clause} ORDER BY o.created_at DESC LIMIT %s OFFSET %s",
            params + [per_page, offset]
        ).fetchall()

    orders = []
    for r in rows:
        checkout_payload = _json.loads(r["checkout_payload_json"] or "{}") if r["checkout_payload_json"] else {}
        orders.append({
            "id": r["id"], "order_ref": r["order_ref"], "status": r["status"],
            "items": _json.loads(r["items_json"]), "total_amount": r["total_amount"],
            "tracking_number": r["tracking_number"], "tracking_status": r["tracking_status"],
            "created_at": r["created_at"],
            "customer_email": r["customer_email"],
            "customer_name": checkout_payload.get("customer_name") or r["customer_name"] or r["customer_email"],
            "checkout_payload": checkout_payload,
        })
    return jsonify({"ok": True, "orders": orders, "total": total, "page": page, "per_page": per_page})


@app.route("/api/admin/orders/<int:order_id>", methods=["PATCH"])
def admin_update_order(order_id):
    uid = require_admin()
    if not uid:
        return jsonify({"ok": False, "error": "Admin only."}), 403
    data       = request.get_json(force=True, silent=True) or {}
    new_status = (data.get("status") or "").strip()
    allowed    = ("pending", "processing", "confirmed", "shipped", "delivered", "cancelled")
    if new_status not in allowed:
        return jsonify({"ok": False, "error": f"status must be one of {allowed}"}), 400
    tracking_number = data.get("tracking_number")
    tracking_status = data.get("tracking_status")
    with get_db() as conn:
        row = conn.execute("SELECT id FROM orders WHERE id=%s", (order_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Order not found."}), 404
        sets, vals = ["status=%s"], [new_status]
        if tracking_number is not None:
            sets.append("tracking_number=%s"); vals.append(tracking_number)
        if tracking_status is not None:
            sets.append("tracking_status=%s"); vals.append(tracking_status)
        vals.append(order_id)
        conn.execute(f"UPDATE orders SET {', '.join(sets)} WHERE id=%s", vals)
        ord_row = conn.execute("SELECT user_id, order_ref FROM orders WHERE id=%s", (order_id,)).fetchone()
        if ord_row:
            create_notification(ord_row["user_id"], "Order Status Updated", f"Order #{ord_row['order_ref']} status has been updated to '{new_status}'.", ntype="order", link="orders.html", conn=conn)
    return jsonify({"ok": True})


@app.route("/api/professional/orders/<int:order_id>", methods=["PATCH"])
def pro_update_order(order_id):
    uid = _require_professional()
    if not uid:
        return jsonify({"ok": False, "error": "Professional account required."}), 401
    data = request.get_json(force=True, silent=True) or {}
    new_status = (data.get("status") or "").strip()
    allowed = ("processing", "confirmed", "shipped", "delivered", "cancelled")
    if new_status not in allowed:
        return jsonify({"ok": False, "error": f"status must be one of {allowed}"}), 400
    with get_db() as conn:
        if not conn.execute(
            "SELECT 1 FROM pro_sale_items WHERE seller_id=%s AND order_id=%s LIMIT 1",
            (uid, order_id)
        ).fetchone():
            return jsonify({"ok": False, "error": "Order not found."}), 404
        conn.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
        row = conn.execute(
            "SELECT id, order_ref, status, items_json, total_amount, tracking_number, tracking_status, created_at, checkout_payload_json FROM orders WHERE id=%s",
            (order_id,)
        ).fetchone()
    checkout_payload = _json.loads(row["checkout_payload_json"] or "{}") if row["checkout_payload_json"] else {}
    return jsonify({"ok": True, "order": {
        "id": row["id"],
        "order_ref": row["order_ref"],
        "status": row["status"],
        "items": _json.loads(row["items_json"]),
        "total_amount": row["total_amount"],
        "tracking_number": row["tracking_number"],
        "tracking_status": row["tracking_status"],
        "created_at": row["created_at"],
        "checkout_payload": checkout_payload,
    }})


@app.route("/api/admin/verification-requests", methods=["GET"])
def admin_list_verifications():
    uid = require_admin()
    if not uid:
        return jsonify({"ok": False, "error": "Admin only."}), 403
    status_filter = request.args.get("status", "pending").strip()
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 20
    offset   = (page - 1) * per_page

    with get_db() as conn:
        if status_filter == "all":
            total = conn.execute("SELECT COUNT(*) AS c FROM verification_requests").fetchone()["c"]
            rows  = conn.execute(
                "SELECT * FROM verification_requests ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (per_page, offset)
            ).fetchall()
        else:
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM verification_requests WHERE status=%s", (status_filter,)
            ).fetchone()["c"]
            rows  = conn.execute(
                "SELECT * FROM verification_requests WHERE status=%s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (status_filter, per_page, offset)
            ).fetchall()

    return jsonify({"ok": True, "requests": [dict(r) for r in rows], "total": total, "page": page, "per_page": per_page})


@app.route("/api/admin/verification-requests", methods=["POST"])
def admin_submit_verification():
    """Anyone (or admin) can submit a studio verification request."""
    data        = request.get_json(force=True, silent=True) or {}
    studio_name = (data.get("studio_name") or "").strip()
    rep_name    = (data.get("rep_name")    or "").strip()
    if not studio_name or not rep_name:
        return jsonify({"ok": False, "error": "studio_name and rep_name are required."}), 400
    uid = require_auth()
    with get_db() as conn:
        row = conn.execute(
            """INSERT INTO verification_requests
               (user_id, studio_name, rep_name, rep_title, studio_type, location, website, notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (uid,
             studio_name, rep_name,
             (data.get("rep_title")  or "").strip() or None,
             (data.get("studio_type")or "").strip() or None,
             (data.get("location")   or "").strip() or None,
             (data.get("website")    or "").strip() or None,
             (data.get("notes")      or "").strip() or None,
            )
        ).fetchone()
        admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
        for a in admins:
            create_notification(a["id"], "New Studio Verification Request", f"Verification request submitted for '{studio_name}'.", ntype="verification", link="verificationrequest.html", conn=conn)
    return jsonify({"ok": True, "id": row["id"]}), 201


@app.route("/api/admin/verification-requests/<int:req_id>", methods=["PATCH"])
def admin_review_verification(req_id):
    uid = require_admin()
    if not uid:
        return jsonify({"ok": False, "error": "Admin only."}), 403
    data   = request.get_json(force=True, silent=True) or {}
    action = (data.get("status") or "").strip()
    if action not in ("approved", "rejected"):
        return jsonify({"ok": False, "error": "status must be 'approved' or 'rejected'."}), 400
    with get_db() as conn:
        row = conn.execute("SELECT * FROM verification_requests WHERE id=%s", (req_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Request not found."}), 404
        conn.execute(
            "UPDATE verification_requests SET status=%s, reviewed_by=%s, reviewed_at=TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS') WHERE id=%s",
            (action, uid, req_id)
        )
        # If approved and linked to a user, upgrade their role to 'studio'
        if action == "approved" and row["user_id"]:
            conn.execute("UPDATE users SET role='studio' WHERE id=%s AND role IN ('customer', 'professional')", (row["user_id"],))
        if row["user_id"]:
            create_notification(row["user_id"], "Studio Verification Updated", f"Your studio verification request has been '{action}'.", ntype="verification", link="profile.html", conn=conn)
    return jsonify({"ok": True, "status": action})


@app.route("/api/admin/users", methods=["GET"])
def admin_list_users():
    uid = require_admin()
    if not uid:
        return jsonify({"ok": False, "error": "Admin only."}), 403
    role_filter = request.args.get("role", "").strip()
    search      = request.args.get("q", "").strip()
    page        = max(1, int(request.args.get("page", 1)))
    per_page    = 20
    offset      = (page - 1) * per_page

    wheres, params = [], []
    if role_filter:
        wheres.append("role=%s"); params.append(role_filter)
    if search:
        wheres.append("(email ILIKE %s OR display_name ILIKE %s)")
        params += [f"%{search}%", f"%{search}%"]
    where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""

    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM users {where_clause}", params).fetchone()["c"]
        rows  = conn.execute(
            f"SELECT id,email,role,display_name,created_at FROM users {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params + [per_page, offset]
        ).fetchall()
    return jsonify({"ok": True, "users": [dict(r) for r in rows], "total": total, "page": page, "per_page": per_page})


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug)
