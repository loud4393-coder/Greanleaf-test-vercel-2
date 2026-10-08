import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl

import psycopg2
import requests
from psycopg2.extras import Json, RealDictCursor
from flask import Flask, jsonify, request, send_from_directory
from vercel.blob import BlobClient


BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder="static")


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def db():
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg2.connect(
        database_url,
        sslmode="require",
    )


def init_db():
    conn = db()

    try:
        with conn.cursor() as cur:

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
                    customer_name TEXT NOT NULL,
                    phone TEXT DEFAULT '',
                    city TEXT DEFAULT '',
                    delivery_method TEXT NOT NULL,
                    address TEXT DEFAULT '',
                    comment TEXT DEFAULT '',
                    items_json JSONB NOT NULL,
                    total NUMERIC(12,2) NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TIMESTAMPTZ NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT DEFAULT ''
                )
            """)

            # -------------------------------------------------
            # ONE-TIME CLEANUP OF OLD TEST PRODUCTS
            #
            # This is deliberately protected by app_meta.
            # Therefore these rows are removed only once.
            # -------------------------------------------------

            cur.execute("""
                SELECT 1
                FROM app_meta
                WHERE key = 'remove_old_demo_products_v1'
            """)

            already_cleaned = cur.fetchone()

            if not already_cleaned:
                cur.execute("""
                    DELETE FROM products
                    WHERE
                        (name = 'Шуба' AND price = 600)
                        OR
                        (name = 'Пальто' AND price = 450)
                        OR
                        (name = 'Пиджак' AND price = 350)
                """)

                cur.execute("""
                    INSERT INTO app_meta (key, value)
                    VALUES ('remove_old_demo_products_v1', 'done')
                    ON CONFLICT (key) DO NOTHING
                """)

        conn.commit()

    finally:
        conn.close()


# ---------------------------------------------------------
# TELEGRAM OWNER AUTH
# ---------------------------------------------------------

def get_admin_id():
    return os.environ.get("ADMIN_ID", "").strip()


def get_bot_token():
    return os.environ.get("BOT_TOKEN", "").strip()


def telegram_user_from_init_data(init_data):
    bot_token = get_bot_token()

    if not bot_token or not init_data:
        return None

    try:
        pairs = dict(parse_qsl(
            init_data,
            keep_blank_values=True,
        ))

        received_hash = pairs.pop("hash", "")

        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(pairs.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash,
        ):
            return None

        auth_date = int(pairs.get("auth_date", "0"))

        # Don't accept extremely old Telegram sessions.
        if not auth_date:
            return None

        if time.time() - auth_date > 86400:
            return None

        user_raw = pairs.get("user", "")

        if not user_raw:
            return None

        user = json.loads(user_raw)

        return user

    except Exception:
        return None


def current_telegram_user():
    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        "",
    )

    return telegram_user_from_init_data(init_data)


def is_admin():
    user = current_telegram_user()

    if not user:
        return False

    admin_id = get_admin_id()

    if not admin_id:
        return False

    return str(user.get("id")) == str(admin_id)


def require_admin():
    if not is_admin():
        return jsonify({
            "error": "Доступ владельца не подтверждён"
        }), 403

    return None


# ---------------------------------------------------------
# PRODUCTS
# ---------------------------------------------------------

def get_products():
    conn = db()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cur:

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

            result = []

            for row in rows:
                item = dict(row)

                item["price"] = float(
                    item["price"]
                )

                result.append(item)

            return result

    finally:
        conn.close()


def upload_product_image(file):
    if not file or not file.filename:
        return ""

    allowed = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    content_type = (
        file.mimetype or ""
    ).lower()

    if content_type not in allowed:
        raise ValueError(
            "Разрешены только JPG, PNG и WEBP"
        )

    raw = file.read()

    # Vercel Functions have a 4.5 MB request-body limit.
    # Frontend compression should keep normal uploads well below it.
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError(
            "Фотография слишком большая. "
            "Выберите изображение до 4 МБ."
        )

    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[content_type]

    pathname = (
        f"greenleaf/products/"
        f"{uuid.uuid4().hex}.{extension}"
    )

    with BlobClient() as client:
        blob = client.put(
            pathname,
            raw,
            access="public",
            content_type=content_type,
            add_random_suffix=True,
        )

    return blob.url


# ---------------------------------------------------------
# TELEGRAM
# ---------------------------------------------------------

def send_telegram(text):
    token = get_bot_token()
    admin_id = get_admin_id()

    if not token or not admin_id:
        return False, (
            "BOT_TOKEN или ADMIN_ID "
            "не настроены"
        )

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    try:
        response = requests.post(
            url,
            json={
                "chat_id": admin_id,
                "text": text,
            },
            timeout=12,
        )

        response.raise_for_status()

        data = response.json()

        return (
            bool(data.get("ok")),
            data.get("description", ""),
        )

    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------
# PAGES
# ---------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(
        BASE_DIR / "static",
        "index.html",
    )


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "greenleaf",
    })


# ---------------------------------------------------------
# ADMIN CHECK
# ---------------------------------------------------------

@app.get("/api/admin/check")
def admin_check():
    user = current_telegram_user()

    return jsonify({
        "admin": is_admin(),
        "user": {
            "id": user.get("id"),
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "username": user.get("username", ""),
        } if user else None,
    })


# ---------------------------------------------------------
# PUBLIC PRODUCTS
# ---------------------------------------------------------

@app.get("/api/products")
def api_products():
    return jsonify({
        "products": get_products(),
    })


# ---------------------------------------------------------
# ADMIN: CREATE PRODUCT
# ---------------------------------------------------------

@app.post("/api/products")
def add_product():
    auth_error = require_admin()

    if auth_error:
        return auth_error

    name = request.form.get(
        "name",
        "",
    ).strip()

    description = request.form.get(
        "description",
        "",
    ).strip()

    category = request.form.get(
        "category",
        "",
    ).strip()

    price_raw = request.form.get(
        "price",
        "",
    ).strip()

    if not name:
        return jsonify({
            "error": "Укажите название товара"
        }), 400

    try:
        price = float(price_raw)

    except (TypeError, ValueError):
        return jsonify({
            "error": "Некорректная цена"
        }), 400

    if price < 0:
        return jsonify({
            "error": "Цена не может быть отрицательной"
        }), 400

    try:
        image_url = upload_product_image(
            request.files.get("image")
        )

    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    except Exception as exc:
        return jsonify({
            "error": (
                "Не удалось загрузить фотографию: "
                f"{exc}"
            )
        }), 500

    conn = db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO products
                (
                    name,
                    description,
                    price,
                    category,
                    image_url
                )
                VALUES
                (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                name,
                description,
                price,
                category,
                image_url,
            ))

            product_id = cur.fetchone()[0]

        conn.commit()

    finally:
        conn.close()

    return jsonify({
        "ok": True,
        "product": {
            "id": product_id,
            "name": name,
            "description": description,
            "price": price,
            "category": category,
            "image_url": image_url,
        },
    })


# ---------------------------------------------------------
# ADMIN: UPDATE PRODUCT
# ---------------------------------------------------------

@app.put("/api/products/<int:product_id>")
def update_product(product_id):
    auth_error = require_admin()

    if auth_error:
        return auth_error

    name = request.form.get(
        "name",
        "",
    ).strip()

    description = request.form.get(
        "description",
        "",
    ).strip()

    category = request.form.get(
        "category",
        "",
    ).strip()

    price_raw = request.form.get(
        "price",
        "",
    ).strip()

    if not name:
        return jsonify({
            "error": "Укажите название товара"
        }), 400

    try:
        price = float(price_raw)

    except (TypeError, ValueError):
        return jsonify({
            "error": "Некорректная цена"
        }), 400

    if price < 0:
        return jsonify({
            "error": "Цена не может быть отрицательной"
        }), 400

    new_image_url = ""

    image = request.files.get("image")

    if image and image.filename:
        try:
            new_image_url = upload_product_image(
                image
            )

        except ValueError as exc:
            return jsonify({
                "error": str(exc)
            }), 400

        except Exception as exc:
            return jsonify({
                "error": (
                    "Не удалось загрузить "
                    f"фотографию: {exc}"
                )
            }), 500

    conn = db()

    try:
        with conn.cursor() as cur:

            if new_image_url:
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
                    price,
                    category,
                    new_image_url,
                    product_id,
                ))

            else:
                cur.execute("""
                    UPDATE products
                    SET
                        name = %s,
                        description = %s,
                        price = %s,
                        category = %s
                    WHERE id = %s
                """, (
                    name,
                    description,
                    price,
                    category,
                    product_id,
                ))

            updated = cur.rowcount

        conn.commit()

    finally:
        conn.close()

    if updated == 0:
        return jsonify({
            "error": "Товар не найден"
        }), 404

    return jsonify({
        "ok": True
    })


# ---------------------------------------------------------
# ADMIN: DELETE PRODUCT
# ---------------------------------------------------------

@app.delete("/api/products/<int:product_id>")
def delete_product(product_id):
    auth_error = require_admin()

    if auth_error:
        return auth_error

    conn = db()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM products
                WHERE id = %s
                """,
                (product_id,),
            )

            deleted = cur.rowcount

        conn.commit()

    finally:
        conn.close()

    if deleted == 0:
        return jsonify({
            "error": "Товар не найден"
        }), 404

    return jsonify({
        "ok": True
    })


# ---------------------------------------------------------
# CREATE ORDER
# ---------------------------------------------------------

@app.post("/api/orders")
def create_order():
    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "customer_name",
            "",
        )
    ).strip()

    phone = str(
        data.get(
            "phone",
            "",
        )
    ).strip()

    city = str(
        data.get(
            "city",
            "",
        )
    ).strip()

    method = str(
        data.get(
            "delivery_method",
            "",
        )
    ).strip()

    address = str(
        data.get(
            "address",
            "",
        )
    ).strip()

    comment = str(
        data.get(
            "comment",
            "",
        )
    ).strip()

    items = data.get(
        "items",
        [],
    )

    if (
        not name
        or not method
        or not isinstance(items, list)
        or not items
    ):
        return jsonify({
            "error": (
                "Заполните имя, способ "
                "получения и корзину"
            )
        }), 400

    catalog = {
        p["id"]: p
        for p in get_products()
    }

    normalized = []
    total = 0.0

    for item in items:

        try:
            product_id = int(
                item.get("id")
            )

            quantity = int(
                item.get(
                    "quantity",
                    1,
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ):
            return jsonify({
                "error": (
                    "Некорректный товар "
                    "в корзине"
                )
            }), 400

        if (
            quantity < 1
            or product_id not in catalog
        ):
            return jsonify({
                "error": (
                    "Некорректный товар "
                    "в корзине"
                )
            }), 400

        product = catalog[product_id]

        line_total = (
            float(product["price"])
            * quantity
        )

        normalized.append({
            "id": product_id,
            "name": product["name"],
            "price": float(
                product["price"]
            ),
            "quantity": quantity,
            "line_total": line_total,
        })

        total += line_total

    created_at = datetime.now(
        timezone.utc
    )

    conn = db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO orders
                (
                    customer_name,
                    phone,
                    city,
                    delivery_method,
                    address,
                    comment,
                    items_json,
                    total,
                    status,
                    created_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id
            """, (
                name,
                phone,
                city,
                method,
                address,
                comment,
                Json(normalized),
                total,
                "new",
                created_at,
            ))

            order_id = cur.fetchone()[0]

        conn.commit()

    finally:
        conn.close()

    lines = [
        "GREENLEAF — НОВЫЙ ЗАКАЗ",
        f"Заказ №{order_id}",
        "",
        f"Клиент: {name}",
        f"Телефон: {phone or 'не указан'}",
        f"Город: {city or 'не указан'}",
        f"Получение: {method}",
        f"Адрес/пункт: {address or 'не указан'}",
        "",
        "Товары:",
    ]

    for item in normalized:
        lines.append(
            f"• {item['name']} × "
            f"{item['quantity']} — "
            f"{item['line_total']:.0f} TMT"
        )

    lines += [
        "",
        f"ИТОГО: {total:.0f} TMT",
        f"Комментарий: "
        f"{comment or 'нет'}",
    ]

    sent, telegram_error = send_telegram(
        "\n".join(lines)
    )

    return jsonify({
        "ok": True,
        "order_id": order_id,
        "total": total,
        "telegram_sent": sent,
        "telegram_error": (
            ""
            if sent
            else telegram_error
        ),
    })


# ---------------------------------------------------------
# ADMIN: ORDERS
# ---------------------------------------------------------

@app.get("/api/orders")
def list_orders():
    auth_error = require_admin()

    if auth_error:
        return auth_error

    view = request.args.get(
        "view",
        "active",
    )

    conn = db()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cur:

            if view == "archive":
                cur.execute("""
                    SELECT
                        id,
                        customer_name,
                        phone,
                        city,
                        delivery_method,
                        address,
                        comment,
                        items_json,
                        total,
                        status,
                        created_at
                    FROM orders
                    WHERE status IN (
                        'completed',
                        'cancelled'
                    )
                    ORDER BY id DESC
                """)

            else:
                cur.execute("""
                    SELECT
                        id,
                        customer_name,
                        phone,
                        city,
                        delivery_method,
                        address,
                        comment,
                        items_json,
                        total,
                        status,
                        created_at
                    FROM orders
                    WHERE status NOT IN (
                        'completed',
                        'cancelled'
                    )
                    ORDER BY id DESC
                """)

            rows = cur.fetchall()

            result = []

            for row in rows:
                item = dict(row)

                item["items"] = item.pop(
                    "items_json"
                )

                item["total"] = float(
                    item["total"]
                )

                if item["created_at"]:
                    item["created_at"] = (
                        item["created_at"]
                        .isoformat()
                    )

                result.append(item)

            return jsonify({
                "orders": result,
            })

    finally:
        conn.close()


# ---------------------------------------------------------
# ADMIN: CHANGE ORDER STATUS
# ---------------------------------------------------------

@app.patch("/api/orders/<int:order_id>/status")
def update_order_status(order_id):
    auth_error = require_admin()

    if auth_error:
        return auth_error

    data = request.get_json(
        silent=True
    ) or {}

    status = str(
        data.get(
            "status",
            "",
        )
    ).strip()

    allowed = {
        "new",
        "processing",
        "ready",
        "completed",
        "cancelled",
    }

    if status not in allowed:
        return jsonify({
            "error": "Недопустимый статус"
        }), 400

    conn = db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE orders
                SET status = %s
                WHERE id = %s
            """, (
                status,
                order_id,
            ))

            updated = cur.rowcount

        conn.commit()

    finally:
        conn.close()

    if updated == 0:
        return jsonify({
            "error": "Заказ не найден"
        }), 404

    return jsonify({
        "ok": True,
    })


# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                "5000",
            )
        ),
    )
