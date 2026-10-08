import os
import json
import time
import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl

import requests
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from flask import Flask, jsonify, request, send_from_directory
from vercel.blob import BlobClient


BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder="static")


# =========================================================
# DATABASE
# =========================================================

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
                CREATE TABLE IF NOT EXISTS reviews (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER NOT NULL
                        REFERENCES products(id)
                        ON DELETE CASCADE,
                    author TEXT NOT NULL,
                    rating INTEGER NOT NULL
                        CHECK (rating BETWEEN 1 AND 5),
                    text TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
            """)

        conn.commit()

    finally:
        conn.close()


# =========================================================
# TELEGRAM ADMIN AUTH
# =========================================================

def verify_telegram_init_data():
    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        "",
    ).strip()

    bot_token = os.environ.get(
        "BOT_TOKEN",
        "",
    ).strip()

    admin_id = os.environ.get(
        "ADMIN_ID",
        "",
    ).strip()

    if not init_data or not bot_token or not admin_id:
        return False, None

    try:
        parsed = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True,
            )
        )

        received_hash = parsed.pop(
            "hash",
            "",
        )

        if not received_hash:
            return False, None

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(parsed.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash,
        ):
            return False, None

        auth_date = int(
            parsed.get("auth_date", "0")
        )

        if not auth_date:
            return False, None

        if time.time() - auth_date > 86400:
            return False, None

        user = json.loads(
            parsed.get("user", "{}")
        )

        user_id = str(
            user.get("id", "")
        )

        if user_id != str(admin_id):
            return False, user

        return True, user

    except Exception:
        return False, None


def require_admin():
    ok, _ = verify_telegram_init_data()

    if not ok:
        return jsonify({
            "error": "Доступ разрешён только владельцу."
        }), 403

    return None


# =========================================================
# PRODUCTS
# =========================================================

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

            product_rows = cur.fetchall()

            cur.execute("""
                SELECT
                    id,
                    product_id,
                    author,
                    rating,
                    text,
                    created_at
                FROM reviews
                ORDER BY created_at DESC
            """)

            review_rows = cur.fetchall()

            reviews_by_product = {}

            for row in review_rows:
                review = dict(row)

                review["created_at"] = (
                    review["created_at"].isoformat()
                    if review["created_at"]
                    else ""
                )

                reviews_by_product.setdefault(
                    review["product_id"],
                    [],
                ).append(review)

            result = []

            for row in product_rows:
                product = dict(row)

                product["price"] = float(
                    product["price"]
                )

                reviews = reviews_by_product.get(
                    product["id"],
                    [],
                )

                product["reviews"] = reviews[:5]
                product["review_count"] = len(
                    reviews
                )

                if reviews:
                    product["rating"] = round(
                        sum(
                            r["rating"]
                            for r in reviews
                        ) / len(reviews),
                        1,
                    )
                else:
                    product["rating"] = 0

                result.append(product)

            return result

    finally:
        conn.close()


@app.get("/api/products")
def api_products():
    return jsonify({
        "products": get_products()
    })


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
            "Разрешены только JPG, PNG и WEBP."
        )

    raw = file.read()

    if len(raw) > 4 * 1024 * 1024:
        raise ValueError(
            "Фото слишком большое. "
            "Используй фото до 4 МБ."
        )

    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[content_type]

    pathname = (
        "greenleaf/products/"
        f"{uuid.uuid4().hex}.{extension}"
    )

    client = BlobClient()

    blob = client.put(
        pathname,
        raw,
        access="public",
        content_type=content_type,
        add_random_suffix=True,
    )

    return blob.url


@app.post("/api/products")
def add_product():
    denied = require_admin()

    if denied:
        return denied

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

    try:
        price = float(
            request.form.get(
                "price",
                "",
            )
        )
    except ValueError:
        return jsonify({
            "error": "Некорректная цена."
        }), 400

    if not name:
        return jsonify({
            "error": "Введите название товара."
        }), 400

    if price < 0:
        return jsonify({
            "error": "Цена не может быть отрицательной."
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
                "Ошибка загрузки фотографии: "
                f"{str(exc)}"
            )
        }), 500

    conn = db()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cur:

            cur.execute(
                """
                INSERT INTO products
                (
                    name,
                    description,
                    price,
                    category,
                    image_url
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING
                    id,
                    name,
                    description,
                    price,
                    category,
                    image_url
                """,
                (
                    name,
                    description,
                    price,
                    category,
                    image_url,
                ),
            )

            product = dict(
                cur.fetchone()
            )

        conn.commit()

    finally:
        conn.close()

    product["price"] = float(
        product["price"]
    )

    return jsonify({
        "ok": True,
        "product": product,
    })


@app.put("/api/products/<int:product_id>")
def update_product(product_id):
    denied = require_admin()

    if denied:
        return denied

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

    try:
        price = float(
            request.form.get(
                "price",
                "",
            )
        )
    except ValueError:
        return jsonify({
            "error": "Некорректная цена."
        }), 400

    if not name or price < 0:
        return jsonify({
            "error": "Проверьте название и цену."
        }), 400

    image_file = request.files.get(
        "image"
    )

    image_url = None

    if image_file and image_file.filename:
        try:
            image_url = upload_product_image(
                image_file
            )
        except ValueError as exc:
            return jsonify({
                "error": str(exc)
            }), 400
        except Exception as exc:
            return jsonify({
                "error": (
                    "Ошибка загрузки фотографии: "
                    f"{str(exc)}"
                )
            }), 500

    conn = db()

    try:
        with conn.cursor() as cur:

            if image_url:
                cur.execute(
                    """
                    UPDATE products
                    SET
                        name = %s,
                        description = %s,
                        price = %s,
                        category = %s,
                        image_url = %s
                    WHERE id = %s
                    """,
                    (
                        name,
                        description,
                        price,
                        category,
                        image_url,
                        product_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE products
                    SET
                        name = %s,
                        description = %s,
                        price = %s,
                        category = %s
                    WHERE id = %s
                    """,
                    (
                        name,
                        description,
                        price,
                        category,
                        product_id,
                    ),
                )

            updated = cur.rowcount

        conn.commit()

    finally:
        conn.close()

    if not updated:
        return jsonify({
            "error": "Товар не найден."
        }), 404

    return jsonify({
        "ok": True
    })


@app.delete("/api/products/<int:product_id>")
def delete_product(product_id):
    denied = require_admin()

    if denied:
        return denied

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

    if not deleted:
        return jsonify({
            "error": "Товар не найден."
        }), 404

    return jsonify({
        "ok": True
    })


# =========================================================
# REVIEWS
# =========================================================

@app.post("/api/reviews")
def add_review():
    denied = require_admin()

    if denied:
        return denied

    data = request.get_json(
        silent=True
    ) or {}

    try:
        product_id = int(
            data.get("product_id")
        )

        rating = int(
            data.get("rating")
        )

    except (
        TypeError,
        ValueError,
    ):
        return jsonify({
            "error": "Некорректные данные."
        }), 400

    author = str(
        data.get(
            "author",
            "",
        )
    ).strip()

    text = str(
        data.get(
            "text",
            "",
        )
    ).strip()

    if not author or not text:
        return jsonify({
            "error": "Заполните автора и текст."
        }), 400

    if rating < 1 or rating > 5:
        return jsonify({
            "error": (
                "Оценка должна быть "
                "от 1 до 5."
            )
        }), 400

    conn = db()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id
                FROM products
                WHERE id = %s
                """,
                (product_id,),
            )

            if not cur.fetchone():
                return jsonify({
                    "error": "Товар не найден."
                }), 404

            cur.execute(
                """
                INSERT INTO reviews
                (
                    product_id,
                    author,
                    rating,
                    text,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    product_id,
                    author,
                    rating,
                    text,
                    datetime.now(timezone.utc),
                ),
            )

        conn.commit()

    finally:
        conn.close()

    return jsonify({
        "ok": True
    })


@app.delete("/api/reviews/<int:review_id>")
def delete_review(review_id):
    denied = require_admin()

    if denied:
        return denied

    conn = db()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM reviews
                WHERE id = %s
                """,
                (review_id,),
            )

            deleted = cur.rowcount

        conn.commit()

    finally:
        conn.close()

    if not deleted:
        return jsonify({
            "error": "Отзыв не найден."
        }), 404

    return jsonify({
        "ok": True
    })


# =========================================================
# ORDERS
# =========================================================

def send_telegram(text):
    token = os.environ.get(
        "BOT_TOKEN",
        "",
    ).strip()

    admin_id = os.environ.get(
        "ADMIN_ID",
        "",
    ).strip()

    if not token or not admin_id:
        return (
            False,
            "BOT_TOKEN или ADMIN_ID "
            "не настроены.",
        )

    url = (
        "https://api.telegram.org/"
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
            data.get(
                "description",
                "",
            ),
        )

    except Exception as exc:
        return False, str(exc)


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
                "получения и корзину."
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
                    "в корзине."
                )
            }), 400

        if (
            quantity < 1
            or product_id not in catalog
        ):
            return jsonify({
                "error": (
                    "Некорректный товар "
                    "в корзине."
                )
            }), 400

        product = catalog[
            product_id
        ]

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

            cur.execute(
                """
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
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
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
                ),
            )

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

    lines.extend([
        "",
        f"ИТОГО: {total:.0f} TMT",
        f"Комментарий: {comment or 'нет'}",
    ])

    telegram_sent, telegram_error = send_telegram(
        "\n".join(lines)
    )

    return jsonify({
        "ok": True,
        "order_id": order_id,
        "total": total,
        "telegram_sent": telegram_sent,
        "telegram_error": (
            ""
            if telegram_sent
            else telegram_error
        ),
    })


@app.get("/api/orders")
def list_orders():
    denied = require_admin()

    if denied:
        return denied

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

                order = dict(row)

                order["items"] = order.pop(
                    "items_json"
                )

                order["total"] = float(
                    order["total"]
                )

                order["created_at"] = (
                    order["created_at"].isoformat()
                    if order["created_at"]
                    else ""
                )

                result.append(order)

            return jsonify({
                "orders": result
            })

    finally:
        conn.close()


@app.patch("/api/orders/<int:order_id>/status")
def change_order_status(order_id):
    denied = require_admin()

    if denied:
        return denied

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
            "error": "Недопустимый статус."
        }), 400

    conn = db()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE orders
                SET status = %s
                WHERE id = %s
                """,
                (
                    status,
                    order_id,
                ),
            )

            updated = cur.rowcount

        conn.commit()

    finally:
        conn.close()

    if not updated:
        return jsonify({
            "error": "Заказ не найден."
        }), 404

    return jsonify({
        "ok": True
    })


# =========================================================
# ADMIN CHECK
# =========================================================

@app.get("/api/admin/check")
def admin_check():
    ok, user = verify_telegram_init_data()

    return jsonify({
        "admin": ok,
        "user_id": (
            user.get("id")
            if user
            else None
        ),
    })


# =========================================================
# PAGES
# =========================================================

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


# =========================================================
# START
# =========================================================

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
