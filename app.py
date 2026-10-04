import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(os.environ.get("DB_PATH", "/tmp/greenleaf.db"))
app = Flask(__name__, static_folder="static")

DEFAULT_PRODUCTS = [
    {"id": 1, "name": "Шуба", "description": "Тестовый товар Greenleaf", "price": 600},
    {"id": 2, "name": "Пальто", "description": "Тестовый товар Greenleaf", "price": 450},
    {"id": 3, "name": "Пиджак", "description": "Тестовый товар Greenleaf", "price": 350},
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            city TEXT DEFAULT '',
            delivery_method TEXT NOT NULL,
            address TEXT DEFAULT '',
            comment TEXT DEFAULT '',
            items_json TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL
        )
    """)
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO products (id,name,description,price) VALUES (?,?,?,?)",
            [(p["id"], p["name"], p["description"], p["price"]) for p in DEFAULT_PRODUCTS],
        )
    conn.commit()
    conn.close()


def products():
    conn = db()
    rows = conn.execute("SELECT id,name,description,price FROM products ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def send_telegram(text):
    token = os.environ.get("BOT_TOKEN", "").strip()
    admin_id = os.environ.get("ADMIN_ID", "").strip()
    if not token or not admin_id:
        return False, "BOT_TOKEN or ADMIN_ID is not configured"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": admin_id, "text": text},
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        return bool(data.get("ok")), data.get("description", "")
    except Exception as exc:
        return False, str(exc)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "greenleaf"})


@app.get("/api/products")
def api_products():
    return jsonify({"products": products()})


@app.post("/api/products")
def add_product():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    try:
        price = float(data.get("price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректная цена"}), 400

    if not name or price < 0:
        return jsonify({"error": "Нужно указать название и корректную цену"}), 400

    conn = db()
    cur = conn.execute(
        "INSERT INTO products (name,description,price) VALUES (?,?,?)",
        (name, description, price),
    )
    conn.commit()
    product_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "product": {"id": product_id, "name": name, "description": description, "price": price}})


@app.put("/api/products/<int:product_id>")
def update_product(product_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    try:
        price = float(data.get("price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректная цена"}), 400

    if not name or price < 0:
        return jsonify({"error": "Нужно указать название и корректную цену"}), 400

    conn = db()
    cur = conn.execute(
        "UPDATE products SET name=?,description=?,price=? WHERE id=?",
        (name, description, price, product_id),
    )
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        return jsonify({"error": "Товар не найден"}), 404
    return jsonify({"ok": True})


@app.delete("/api/products/<int:product_id>")
def delete_product(product_id):
    conn = db()
    cur = conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "Товар не найден"}), 404
    return jsonify({"ok": True})


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}

    name = str(data.get("customer_name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    city = str(data.get("city", "")).strip()
    method = str(data.get("delivery_method", "")).strip()
    address = str(data.get("address", "")).strip()
    comment = str(data.get("comment", "")).strip()
    items = data.get("items", [])

    if not name or not method or not isinstance(items, list) or not items:
        return jsonify({"error": "Заполните имя, способ получения и корзину"}), 400

    catalog = {p["id"]: p for p in products()}
    normalized = []
    total = 0.0

    for item in items:
        try:
            pid = int(item.get("id"))
            qty = int(item.get("quantity", 1))
        except (TypeError, ValueError, AttributeError):
            return jsonify({"error": "Некорректный товар в корзине"}), 400

        if qty < 1 or pid not in catalog:
            return jsonify({"error": "Некорректный товар в корзине"}), 400

        p = catalog[pid]
        line_total = float(p["price"]) * qty
        normalized.append({
            "id": pid,
            "name": p["name"],
            "price": float(p["price"]),
            "quantity": qty,
            "line_total": line_total,
        })
        total += line_total

    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    conn = db()
    cur = conn.execute(
        """INSERT INTO orders
           (customer_name,phone,city,delivery_method,address,comment,items_json,total,status,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (name, phone, city, method, address, comment,
         json.dumps(normalized, ensure_ascii=False), total, "new", created_at),
    )
    order_id = cur.lastrowid
    conn.commit()
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
        lines.append(f"• {item['name']} × {item['quantity']} — {item['line_total']:.0f} TMT")
    lines += [
        "",
        f"ИТОГО: {total:.0f} TMT",
        f"Комментарий: {comment or 'нет'}",
    ]

    sent, telegram_error = send_telegram("\n".join(lines))
    return jsonify({
        "ok": True,
        "order_id": order_id,
        "total": total,
        "telegram_sent": sent,
        "telegram_error": "" if sent else telegram_error,
    })


@app.get("/api/orders")
def list_orders():
    # For the test stage. Later we will protect this route with Telegram admin auth.
    conn = db()
    rows = conn.execute(
        "SELECT id,customer_name,phone,city,delivery_method,address,comment,items_json,total,status,created_at "
        "FROM orders ORDER BY id DESC"
    ).fetchall()
    conn.close()

    result = []
    for row in rows:
        item = dict(row)
        item["items"] = json.loads(item.pop("items_json"))
        result.append(item)
    return jsonify({"orders": result})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
