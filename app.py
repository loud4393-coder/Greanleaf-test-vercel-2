import os
import json
import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl

import requests
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from flask import Flask, jsonify, request, send_from_directory


BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder="static")


DEFAULT_PRODUCTS = [
    {
        "id": 1,
        "name": "Шуба",
        "description": "Тестовый товар Greenleaf",
        "price": 600,
    },
    {
        "id": 2,
        "name": "Пальто",
        "description": "Тестовый товар Greenleaf",
        "price": 450,
    },
    {
        "id": 3,
        "name": "Пиджак",
        "description": "Тестовый товар Greenleaf",
        "price": 350,
    },
]


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
                    price NUMERIC(12,2) NOT NULL
                )
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

            cur.execute("SELECT COUNT(*) FROM products")
            count = cur.fetchone()[0]

            if count == 0:
                for product in DEFAULT_PRODUCTS:
                    cur.execute(
                        """
                        INSERT INTO products
                        (id, name, description, price)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            product["id"],
                            product["name"],
                            product["description"],
                            product["price"],
                        ),
                    )

                cur.execute("""
                    SELECT setval(
                        pg_get_serial_sequence('products', 'id'),
                        COALESCE((SELECT MAX(id) FROM products), 1)
                    )
                """)

        conn.commit()

    finally:
        conn.close()


def products():
    conn = db()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, description, price
                FROM products
                ORDER BY id
            """)

            rows = cur.fetchall()

            result = []

            for row in rows:
                item = dict(row)
                item["price"] = float(item["price"])
                result.append(item)

            return result

    finally:
        conn.close()


def send_telegram(text):
    token = os.environ.get("BOT_TOKEN", "").strip()
    admin_id = os.environ.get("ADMIN_ID", "").strip()

    if not token or not admin_id:
        return False, "BOT_TOKEN or ADMIN_ID is not configured"

    url = f"https://api.telegram.org/bot{token}/sendMessage"

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

        return bool(data.get("ok")), data.get("description", "")

    except Exception as exc:
        return False, str(exc)


def verify_admin_telegram():
    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        "",
    ).strip()

    if not init_data:
        return False

    bot_token = os.environ.get(
        "BOT_TOKEN",
        "",
    ).strip()

    admin_id = os.environ.get(
        "ADMIN_ID",
        "",
    ).strip()

    if not bot_token or not admin_id:
        return False

    try:
        data = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True,
            )
        )

        received_hash = data.pop(
            "hash",
            "",
        )

        if not received_hash:
            return False

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(data.items())
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
            return False

        user_data = data.get(
            "user",
            "",
        )

        if not user_data:
            return False

        telegram_user = json.loads(
            user_data
        )

        return (
            str(
                telegram_user.get(
                    "id",
                    "",
                )
            )
            == admin_id
        )

    except Exception:
        return False


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


@app.get("/api/products")
def api_products():
    return jsonify({
        "products": products(),
    })


@app.post("/api/products")
def add_product():
    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            "",
        )
    ).strip()

    description = str(
        data.get(
            "description",
            "",
        )
    ).strip()

    try:
        price = float(
            data.get("price")
        )

    except (
        TypeError,
        ValueError,
    ):
        return jsonify({
            "error": "Некорректная цена"
        }), 400

    if not name or price < 0:
        return jsonify({
            "error": "Нужно указать название и корректную цену"
        }), 400

    conn = db()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO products
                (name, description, price)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (
                    name,
                    description,
                    price,
                ),
            )

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
        },
    })


@app.put("/api/products/<int:product_id>")
def update_product(product_id):
    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            "",
        )
    ).strip()

    description = str(
        data.get(
            "description",
            "",
        )
    ).strip()

    try:
        price = float(
            data.get("price")
        )

    except (
        TypeError,
        ValueError,
    ):
        return jsonify({
            "error": "Некорректная цена"
        }), 400

    if not name or price < 0:
        return jsonify({
            "error": "Нужно указать название и корректную цену"
        }), 400

    conn = db()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE products
                SET name = %s,
                    description = %s,
                    price = %s
                WHERE id = %s
                """,
                (
                    name,
                    description,
                    price,
                    product_id,
                ),
            )

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


@app.delete("/api/products/<int:product_id>")
def delete_product(product_id):
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
        []
    )

    if (
        not name
        or not method
        or not isinstance(items, list)
        or not items
    ):
        return jsonify({
            "error": "Заполните имя, способ получения и корзину"
        }), 400

    catalog = {
        p["id"]: p
        for p in products()
    }

    normalized = []
    total = 0.0

    for item in items:
        try:
            pid = int(
                item.get("id")
            )

            qty = int(
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
                "error": "Некорректный товар в корзине"
            }), 400

        if qty < 1 or pid not in catalog:
            return jsonify({
                "error": "Некорректный товар в корзине"
            }), 400

        product = catalog[pid]

        line_total = (
            float(product["price"])
            * qty
        )

        normalized.append({
            "id": pid,
            "name": product["name"],
            "price": float(
                product["price"]
            ),
            "quantity": qty,
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
        "🛍 GREENLEAF — НОВЫЙ ЗАКАЗ",
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
            f"• {item['name']} × {item['quantity']} — "
            f"{item['line_total']:.0f} TMT"
        )

    lines += [
        "",
        f"ИТОГО: {total:.0f} TMT",
        f"Комментарий: {comment or 'нет'}",
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


@app.get("/api/orders")
def list_orders():

    if not verify_admin_telegram():
        return jsonify({
            "error": "Доступ запрещён"
        }), 403

    conn = db()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cur:

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
                    item["created_at"] = item[
                        "created_at"
                    ].isoformat()

                result.append(item)

            return jsonify({
                "orders": result
            })

    finally:
        conn.close()


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
