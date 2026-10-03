import os, sqlite3
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="/static")
DB_PATH = os.environ.get("GREENLEAF_DB_PATH", "/tmp/greenleaf.db")

def db():
    x = sqlite3.connect(DB_PATH)
    x.row_factory = sqlite3.Row
    return x

def init_db():
    x = db()
    x.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'TMT',
        description TEXT NOT NULL DEFAULT ''
    )""")
    if x.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        x.executemany(
            "INSERT INTO products(name,price,currency,description) VALUES(?,?,?,?)",
            [("Шуба",600,"TMT","Тестовый товар Greenleaf"),
             ("Пальто",450,"TMT","Тестовый товар Greenleaf"),
             ("Пиджак",350,"TMT","Тестовый товар Greenleaf")]
        )
    x.commit(); x.close()

def as_dict(row): return dict(row)

@app.route("/")
def home(): return send_from_directory(app.static_folder, "index.html")

@app.route("/health")
def health(): return jsonify(status="ok", app="greenleaf-catalog-persistence-v1")

@app.route("/api/test")
def api_test(): return jsonify(status="ok", message="Flask API is working")

@app.route("/api/products", methods=["GET"])
def products():
    x=db(); rows=x.execute("SELECT * FROM products ORDER BY id").fetchall(); x.close()
    return jsonify(products=[as_dict(r) for r in rows])

@app.route("/api/products", methods=["POST"])
def create():
    d=request.get_json(silent=True) or {}
    name=str(d.get("name","")).strip(); currency=str(d.get("currency","TMT")).strip() or "TMT"
    desc=str(d.get("description","")).strip()
    try: price=float(d.get("price"))
    except (TypeError,ValueError): return jsonify(error="price must be a number"),400
    if not name: return jsonify(error="name is required"),400
    if price < 0: return jsonify(error="price must be non-negative"),400
    x=db(); c=x.execute("INSERT INTO products(name,price,currency,description) VALUES(?,?,?,?)",(name,price,currency,desc)); x.commit()
    row=x.execute("SELECT * FROM products WHERE id=?",(c.lastrowid,)).fetchone(); x.close()
    return jsonify(product=as_dict(row)),201

@app.route("/api/products/<int:pid>", methods=["PUT"])
def update(pid):
    d=request.get_json(silent=True) or {}
    name=str(d.get("name","")).strip(); currency=str(d.get("currency","TMT")).strip() or "TMT"; desc=str(d.get("description","")).strip()
    try: price=float(d.get("price"))
    except (TypeError,ValueError): return jsonify(error="price must be a number"),400
    if not name: return jsonify(error="name is required"),400
    if price < 0: return jsonify(error="price must be non-negative"),400
    x=db(); c=x.execute("UPDATE products SET name=?,price=?,currency=?,description=? WHERE id=?",(name,price,currency,desc,pid))
    if c.rowcount==0: x.close(); return jsonify(error="product not found"),404
    x.commit(); row=x.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone(); x.close()
    return jsonify(product=as_dict(row))

@app.route("/api/products/<int:pid>", methods=["DELETE"])
def delete(pid):
    x=db(); c=x.execute("DELETE FROM products WHERE id=?",(pid,))
    if c.rowcount==0: x.close(); return jsonify(error="product not found"),404
    x.commit(); x.close(); return jsonify(status="ok", deleted_id=pid)

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
