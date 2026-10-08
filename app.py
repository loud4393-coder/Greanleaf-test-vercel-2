import os
import json
import hashlib
import hmac
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qsl

import requests
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from flask import Flask, jsonify, request, send_from_directory

try:
    from vercel.blob import BlobClient
except Exception:
    BlobClient = None


app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()


# =========================================================
# DATABASE
# =========================================================

def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price NUMERIC(12,2) NOT NULL,
            category TEXT DEFAULT '',
            image_url TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS category TEXT DEFAULT ''
    """)

    cur.execute("""
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT ''
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            customer_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            total NUMERIC(12,2) NOT NULL,
            items JSONB NOT NULL,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Одноразово удаляем старые тестовые товары.
    cur.execute("""
        SELECT 1
        FROM app_meta
        WHERE key = 'test_seed_cleanup_v1'
    """)

    if cur.fetchone() is None:
        cur.execute("""
            DELETE FROM products
            WHERE (name = 'Шуба' AND price = 600)
               OR (name = 'Пальто' AND price = 450)
               OR (name = 'Пиджак' AND price = 350)
        """)

        cur.execute("""
            INSERT INTO app_meta (key, value)
            VALUES ('test_seed_cleanup_v1', 'done')
        """)

    conn.commit()
    cur.close()
    conn.close()


try:
    init_db()
except Exception as e:
    print("DATABASE_INIT_ERROR:", repr(e))


# =========================================================
# TELEGRAM AUTH
# =========================================================

def get_init_data():
    return request.headers.get("X-Telegram-Init-Data", "")


def telegram_user():
    init_data = get_init_data()

    if not init_data or not BOT_TOKEN:
        return None

    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))

        received_hash = data.pop("hash", None)

        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(data.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):
            return None

        auth_date = int(data.get("auth_date", "0"))

        if time.time() - auth_date > 86400:
            return None

        user_json = data.get("user")

        if not user_json:
            return None

        return json.loads(user_json)

    except Exception as e:
        print("TELEGRAM_AUTH_ERROR:", repr(e))
        return None


def is_admin():
    user = telegram_user()

    if not user:
        return False

    return str(user.get("id")) == ADMIN_ID


def require_admin():
    if not is_admin():
        return jsonify({
            "error": "ADMIN_REQUIRED"
        }), 403

    return None


# =========================================================
# VERCEL BLOB
# =========================================================

def upload_image(file):
    if not file:
        return ""

    if BlobClient is None:
        raise RuntimeError(
            "Vercel Blob SDK is not installed"
        )

    content_type = file.content_type or ""

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp"
    }

    if content_type not in allowed_types:
        raise RuntimeError(
            f"Unsupported image type: {content_type}"
        )

    raw = file.read()

    if not raw:
        raise RuntimeError(
            "Uploaded image is empty"
        )

    # Защита от слишком большого файла.
    if len(raw) > 4 * 1024 * 1024:
        raise RuntimeError(
            "Image is larger than 4 MB"
        )

    extension = allowed_types[content_type]

    filename = (
        "greenleaf/products/"
        + uuid.uuid4().hex
        + extension
    )

    print(
        "BLOB_UPLOAD:",
        filename,
        content_type,
        len(raw)
    )

    try:
        with BlobClient() as client:
            blob = client.put(
                filename,
                raw,
                access="public",
                content_type=content_type,
                add_random_suffix=True
            )

        print(
            "BLOB_UPLOAD_SUCCESS:",
            getattr(blob, "url", None)
        )

        return blob.url

    except Exception as e:
        print(
            "BLOB_UPLOAD_ERROR:",
            repr(e)
        )

        raise RuntimeError(
            f"Blob upload failed: {e}"
        )


# =========================================================
# PRODUCTS
# =========================================================

@app.get("/api/products")
def get_products():
    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            id,
            name,
            description,
            price,
            category,
            image_url
        FROM products
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row["id"],
            "name": row["name"],
            "description": row["description"] or "",
            "price": float(row["price"]),
            "category": row["category"] or "",
            "image_url": row["image_url"] or ""
        })

    return jsonify(result)


@app.post("/api/products")
def create_product():
    admin_error = require_admin()

    if admin_error:
        return admin_error

    try:
        name = request.form.get("name", "").strip()
        description = request.form.get(
            "description", ""
        ).strip()
        category = request.form.get(
            "category", ""
        ).strip()
        price = request.form.get(
            "price", ""
        ).strip()

        if not name:
            return jsonify({
                "error": "NAME_REQUIRED"
            }), 400

        if not price:
            return jsonify({
                "error": "PRICE_REQUIRED"
            }), 400

        try:
            price_value = float(price)
        except ValueError:
            return jsonify({
                "error": "INVALID_PRICE"
            }), 400

        image_url = ""

        image = request.files.get("image")

        if image:
            try:
                image_url = upload_image(image)

            except Exception as e:
                print(
                    "CREATE_PRODUCT_IMAGE_ERROR:",
                    repr(e)
                )

                return jsonify({
                    "error": "IMAGE_ERROR",
                    "details": str(e)
                }), 500

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO products
            (name, description, price, category, image_url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            name,
            description,
            price_value,
            category,
            image_url
        ))

        product_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "id": product_id,
            "image_url": image_url
        })

    except Exception as e:
        print(
            "CREATE_PRODUCT_ERROR:",
            repr(e)
        )

        return jsonify({
            "error": "PRODUCT_CREATE_ERROR",
            "details": str(e)
        }), 500


@app.put("/api/products/<int:product_id>")
def update_product(product_id):
    admin_error = require_admin()

    if admin_error:
        return admin_error

    try:
        name = request.form.get("name", "").strip()
        description = request.form.get(
            "description", ""
        ).strip()
        category = request.form.get(
            "category", ""
        ).strip()
        price = request.form.get(
            "price", ""
        ).strip()

        if not name or not price:
            return jsonify({
                "error": "NAME_AND_PRICE_REQUIRED"
            }), 400

        try:
            price_value = float(price)
        except ValueError:
            return jsonify({
                "error": "INVALID_PRICE"
            }), 400

        conn = db()
        cur = conn.cursor(
            cursor_factory=RealDictCursor
        )

        cur.execute("""
            SELECT image_url
            FROM products
            WHERE id = %s
        """, (product_id,))

        existing = cur.fetchone()

        if not existing:
            cur.close()
            conn.close()

            return jsonify({
                "error": "PRODUCT_NOT_FOUND"
            }), 404

        image_url = existing["image_url"] or ""

        image = request.files.get("image")

        if image:
            try:
                image_url = upload_image(image)

            except Exception as e:
                print(
                    "UPDATE_PRODUCT_IMAGE_ERROR:",
                    repr(e)
                )

                cur.close()
                conn.close()

                return jsonify({
                    "error": "IMAGE_ERROR",
                    "details": str(e)
                }), 500

        cur.execute("""
            UPDATE products
            SET
                name = %s,
                description = %s,
                price = %s,
                category = %s,
                image_url = %s
            WHERE id = %s
        """, (
            name,
            description,
            price_value,
            category,
            image_url,
            product_id
        ))

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:
        print(
            "UPDATE_PRODUCT_ERROR:",
            repr(e)
        )

        return jsonify({
            "error": "PRODUCT_UPDATE_ERROR",
            "details": str(e)
        }), 500


@app.delete("/api/products/<int:product_id>")
def delete_product(product_id):
    admin_error = require_admin()

    if admin_error:
        return admin_error

    try:
        conn = db()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM products
            WHERE id = %s
        """, (product_id,))

        deleted = cur.rowcount

        conn.commit()

        cur.close()
        conn.close()

        if deleted == 0:
            return jsonify({
                "error": "PRODUCT_NOT_FOUND"
            }), 404

        return jsonify({
            "success": True
        })

    except Exception as e:
        print(
            "DELETE_PRODUCT_ERROR:",
            repr(e)
        )

        return jsonify({
            "error": "PRODUCT_DELETE_ERROR",
            "details": str(e)
        }), 500


# =========================================================
# ADMIN CHECK
# =========================================================

@app.get("/api/admin/check")
def admin_check():
    user = telegram_user()

    return jsonify({
        "admin": is_admin(),
        "user": {
            "id": user.get("id"),
            "first_name": user.get("first_name"),
            "username": user.get("username")
        } if user else None
    })


# =========================================================
# ORDERS
# =========================================================

@app.post("/api/orders")
def create_order():
    try:
        data = request.get_json(
            silent=True
        ) or {}

        customer_name = str(
            data.get("customer_name", "")
        ).strip()

        phone = str(
            data.get("phone", "")
        ).strip()

        address = str(
            data.get("address", "")
        ).strip()

        city = str(
            data.get("city", "")
        ).strip()

        items = data.get("items", [])

        total = float(
            data.get("total", 0)
        )

        if not items:
            return jsonify({
                "error": "CART_EMPTY"
            }), 400

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO orders
            (
                customer_name,
                phone,
                address,
                city,
                total,
                items,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'new')
            RETURNING id, created_at
        """, (
            customer_name,
            phone,
            address,
            city,
            total,
            Json(items)
        ))

        order_id, created_at = cur.fetchone()

        conn.commit()

        cur.close()
        conn.close()

        send_order_to_telegram(
            order_id,
            customer_name,
            phone,
            address,
            city,
            total,
            items
        )

        return jsonify({
            "success": True,
            "order_id": order_id,
            "created_at": created_at.isoformat()
        })

    except Exception as e:
        print(
            "CREATE_ORDER_ERROR:",
            repr(e)
        )

        return jsonify({
            "error": "ORDER_ERROR",
            "details": str(e)
        }), 500


@app.get("/api/orders")
def get_orders():
    admin_error = require_admin()

    if admin_error:
        return admin_error

    view = request.args.get(
        "view",
        "active"
    )

    conn = db()
    cur = conn.cursor(
        cursor_factory=RealDictCursor
    )

    if view == "archive":
        cur.execute("""
            SELECT *
            FROM orders
            WHERE status IN ('completed', 'cancelled')
            ORDER BY id DESC
        """)
    else:
        cur.execute("""
            SELECT *
            FROM orders
            WHERE status NOT IN ('completed', 'cancelled')
            ORDER BY id DESC
        """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row["id"],
            "customer_name": row["customer_name"] or "",
            "phone": row["phone"] or "",
            "address": row["address"] or "",
            "city": row["city"] or "",
            "total": float(row["total"]),
            "items": row["items"],
            "status": row["status"],
            "created_at": (
                row["created_at"].isoformat()
                if row["created_at"]
                else None
            )
        })

    return jsonify(result)


@app.patch("/api/orders/<int:order_id>/status")
def change_order_status(order_id):
    admin_error = require_admin()

    if admin_error:
        return admin_error

    data = request.get_json(
        silent=True
    ) or {}

    status = str(
        data.get("status", "")
    ).strip()

    allowed = {
        "new",
        "confirmed",
        "shipping",
        "completed",
        "cancelled"
    }

    if status not in allowed:
        return jsonify({
            "error": "INVALID_STATUS"
        }), 400

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE orders
        SET status = %s
        WHERE id = %s
    """, (
        status,
        order_id
    ))

    updated = cur.rowcount

    conn.commit()

    cur.close()
    conn.close()

    if updated == 0:
        return jsonify({
            "error": "ORDER_NOT_FOUND"
        }), 404

    return jsonify({
        "success": True
    })


# =========================================================
# TELEGRAM ORDER MESSAGE
# =========================================================

def send_order_to_telegram(
    order_id,
    customer_name,
    phone,
    address,
    city,
    total,
    items
):
    if not BOT_TOKEN or not ADMIN_ID:
        print(
            "Telegram notification skipped: "
            "BOT_TOKEN or ADMIN_ID missing"
        )
        return

    lines = []

    for item in items:
        name = item.get("name", "")
        qty = item.get("qty", 1)
        price = item.get("price", 0)

        lines.append(
            f"{name} × {qty} — {price} TMT"
        )

    message = (
        f"Новый заказ #{order_id}\n\n"
        f"Клиент: {customer_name}\n"
        f"Телефон: {phone}\n"
        f"Город: {city}\n"
        f"Адрес: {address}\n\n"
        f"Товары:\n"
        + "\n".join(lines)
        + f"\n\nИтого: {total} TMT"
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": ADMIN_ID,
                "text": message
            },
            timeout=10
        )

    except Exception as e:
        print(
            "TELEGRAM_MESSAGE_ERROR:",
            repr(e)
        )


# =========================================================
# FRONTEND
# =========================================================

@app.get("/")
def index():
    return send_from_directory(
        "static",
        "index.html"
    )


@app.get("/<path:path>")
def static_files(path):
    return send_from_directory(
        "static",
        path
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv("PORT", "5000")
        ),
        debug=False
    )
