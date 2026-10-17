import os, json, hmac, hashlib, time, urllib.parse, secrets, math
from contextlib import contextmanager
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 4_000_000

DATABASE_URL = os.getenv('DATABASE_URL', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_ID = os.getenv('ADMIN_ID', '')
BLOB_TOKEN = os.getenv('BLOB_READ_WRITE_TOKEN', '')


def db():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL is not configured')
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require', connect_timeout=10)


@contextmanager
def connection():
    conn = db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    # Serialize first-request migrations/seeding across concurrent serverless instances.
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(724190631)')
        cur.execute('''CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT '',
            price NUMERIC(12,2) NOT NULL DEFAULT 0, description TEXT NOT NULL DEFAULT '',
            image_url TEXT NOT NULL DEFAULT '', active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        cur.execute('''CREATE TABLE IF NOT EXISTS orders (
            id BIGSERIAL PRIMARY KEY, customer_name TEXT NOT NULL, phone TEXT NOT NULL,
            city TEXT NOT NULL, delivery_method TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
            comment TEXT NOT NULL DEFAULT '', items JSONB NOT NULL DEFAULT '[]'::jsonb,
            total NUMERIC(12,2) NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'new',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        cur.execute('''CREATE TABLE IF NOT EXISTS banners (
            id BIGSERIAL PRIMARY KEY, image_url TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        cur.execute('''CREATE TABLE IF NOT EXISTS product_comments (
            id BIGSERIAL PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            author TEXT NOT NULL, body TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        cur.execute('''CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        cur.execute("SELECT value FROM app_meta WHERE key='cleanup_old_test_products_v1'")
        if not cur.fetchone():
            # Remove only the exact legacy demo name/price pairs requested by the owner.
            cur.execute("DELETE FROM products WHERE (name=%s AND price=%s) OR (name=%s AND price=%s) OR (name=%s AND price=%s)",
                ('Шуба',600,'Пальто',450,'Пиджак',350))
            cur.execute("INSERT INTO app_meta(key,value) VALUES('cleanup_old_test_products_v1','done') ON CONFLICT(key) DO NOTHING")
        cur.execute("SELECT value FROM app_meta WHERE key='test_products_seed_v1'")
        if not cur.fetchone():
            cur.execute('''INSERT INTO products(name,category,price,description,image_url) VALUES
                (%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s)''', (
                'Женское пальто','Одежда',650,'Классическое пальто для прохладной погоды. Тестовый товар.','',
                'Зимняя куртка','Одежда',520,'Тёплая куртка для повседневной носки. Тестовый товар.','',
                'Кожаная сумка','Аксессуары',390,'Лаконичная сумка на каждый день. Тестовый товар.',''))
            cur.execute("INSERT INTO app_meta(key,value) VALUES('test_products_seed_v1','done') ON CONFLICT(key) DO NOTHING")


def telegram_user_id(init_data):
    if not init_data or not BOT_TOKEN:
        return None
    try:
        params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        received_hash = params.pop('hash', '')
        auth_date = int(params.get('auth_date', '0'))
        now = int(time.time())
        # Reject stale or future-dated initData; allow at most 24 hours of age.
        if not received_hash or not auth_date or auth_date > now + 60 or now - auth_date > 86400:
            return None
        data_check = '\n'.join(f'{k}={v}' for k, v in sorted(params.items()))
        secret_key = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated, received_hash):
            return None
        user = json.loads(params.get('user', '{}'))
        return str(user.get('id')) if user.get('id') is not None else None
    except Exception:
        return None


def is_admin():
    user_id = telegram_user_id(request.headers.get('X-Telegram-Init-Data', ''))
    return bool(user_id and ADMIN_ID and secrets.compare_digest(user_id, str(ADMIN_ID)))


def admin_required():
    if not is_admin():
        return jsonify({'error': 'Доступ запрещён. Откройте приложение через Telegram.'}), 403
    return None


def product_dict(row):
    d = dict(row)
    d['price'] = float(d.get('price') or 0)
    return d


@app.get('/')
def index():
    return send_from_directory('static', 'index.html')

@app.get('/health')
def health():
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT 1')
        return jsonify({'ok': True, 'database': True})
    except Exception as e:
        app.logger.exception('Health check failed')
        return jsonify({'ok': False, 'error': 'Database connection failed'}), 503

@app.get('/api/products')
def get_products():
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT * FROM products WHERE active=TRUE ORDER BY id DESC')
            products = [product_dict(r) for r in cur.fetchall()]
        return jsonify({'products': products})
    except Exception:
        app.logger.exception('Could not load products')
        return jsonify({'error': 'Не удалось загрузить каталог'}), 500

@app.post('/api/products')
def create_product():
    denied = admin_required()
    if denied: return denied
    try:
        name = request.form.get('name','').strip()[:160]
        category = request.form.get('category','').strip()[:100]
        description = request.form.get('description','').strip()[:3000]
        price = float(request.form.get('price','0'))
        if not name or not math.isfinite(price) or price < 0: return jsonify({'error':'Укажите название и корректную цену'}), 400
        image_url = ''
        image = request.files.get('image')
        if image and image.filename:
            image_url, err = upload_blob(image)
            if err: return jsonify({'error':err}), 502
        with connection() as conn, conn.cursor() as cur:
            cur.execute('''INSERT INTO products(name,category,price,description,image_url)
                VALUES(%s,%s,%s,%s,%s) RETURNING *''',(name,category,price,description,image_url))
            row = product_dict(cur.fetchone())
        return jsonify({'product':row}), 201
    except ValueError:
        return jsonify({'error':'Цена должна быть числом'}), 400
    except Exception:
        app.logger.exception('Create product failed')
        return jsonify({'error':'Не удалось сохранить товар'}), 500

@app.put('/api/products/<int:product_id>')
def update_product(product_id):
    denied = admin_required()
    if denied: return denied
    try:
        name = request.form.get('name','').strip()[:160]
        category = request.form.get('category','').strip()[:100]
        description = request.form.get('description','').strip()[:3000]
        price = float(request.form.get('price','0'))
        if not name or not math.isfinite(price) or price < 0: return jsonify({'error':'Укажите название и корректную цену'}), 400
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT image_url FROM products WHERE id=%s AND active=TRUE',(product_id,))
            old = cur.fetchone()
            if not old: return jsonify({'error':'Товар не найден'}), 404
            image_url = old['image_url'] or ''
            image = request.files.get('image')
            if image and image.filename:
                image_url, err = upload_blob(image)
                if err: return jsonify({'error':err}), 502
            cur.execute('''UPDATE products SET name=%s,category=%s,price=%s,description=%s,image_url=%s
                WHERE id=%s RETURNING *''',(name,category,price,description,image_url,product_id))
            row = product_dict(cur.fetchone())
        return jsonify({'product':row})
    except ValueError:
        return jsonify({'error':'Цена должна быть числом'}), 400
    except Exception:
        app.logger.exception('Update product failed')
        return jsonify({'error':'Не удалось обновить товар'}), 500

@app.delete('/api/products/<int:product_id>')
def delete_product(product_id):
    denied = admin_required()
    if denied: return denied
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute('UPDATE products SET active=FALSE WHERE id=%s RETURNING id',(product_id,))
            if not cur.fetchone(): return jsonify({'error':'Товар не найден'}),404
        return jsonify({'ok':True})
    except Exception:
        app.logger.exception('Delete product failed')
        return jsonify({'error':'Не удалось удалить товар'}),500


@app.get('/api/banners')
def get_banners():
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT id,image_url,sort_order,active FROM banners WHERE active=TRUE ORDER BY sort_order ASC,id DESC')
            active_rows=[dict(r) for r in cur.fetchall()]
            if is_admin():
                cur.execute('SELECT id,image_url,sort_order,active FROM banners ORDER BY sort_order ASC,id DESC')
                all_rows=[dict(r) for r in cur.fetchall()]
            else:
                all_rows=[]
            return jsonify({'banners':active_rows,'admin_banners':all_rows})
    except Exception:
        app.logger.exception('Could not load banners')
        return jsonify({'error':'Не удалось загрузить баннеры'}),500

@app.post('/api/banners')
def create_banner():
    denied=admin_required()
    if denied: return denied
    image=request.files.get('image')
    if not image or not image.filename:
        return jsonify({'error':'Выберите изображение'}),400
    image_url,err=upload_blob(image, folder='banners')
    if err: return jsonify({'error':err}),502
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT COALESCE(MAX(sort_order),-1)+1 AS next_order FROM banners')
            order=cur.fetchone()['next_order']
            cur.execute('INSERT INTO banners(image_url,sort_order) VALUES(%s,%s) RETURNING id,image_url,sort_order,active',(image_url,order))
            return jsonify({'banner':dict(cur.fetchone())}),201
    except Exception:
        app.logger.exception('Could not save banner')
        return jsonify({'error':'Фото загружено, но не удалось сохранить баннер'}),500

@app.patch('/api/banners/<int:banner_id>')
def update_banner(banner_id):
    denied=admin_required()
    if denied: return denied
    data=request.get_json(silent=True) or {}
    if 'active' not in data: return jsonify({'error':'Не указано состояние баннера'}),400
    with connection() as conn, conn.cursor() as cur:
        cur.execute('UPDATE banners SET active=%s WHERE id=%s RETURNING id,active',(bool(data['active']),banner_id))
        row=cur.fetchone()
        if not row: return jsonify({'error':'Баннер не найден'}),404
        return jsonify({'banner':dict(row)})

@app.delete('/api/banners/<int:banner_id>')
def delete_banner(banner_id):
    denied=admin_required()
    if denied: return denied
    with connection() as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM banners WHERE id=%s RETURNING id',(banner_id,))
        if not cur.fetchone(): return jsonify({'error':'Баннер не найден'}),404
    return jsonify({'ok':True})

def upload_blob(file_storage, folder='products'):
    if not BLOB_TOKEN:
        return '', 'В Vercel не задана переменная BLOB_READ_WRITE_TOKEN'
    content = file_storage.read()
    if not content: return '', 'Файл пустой'
    if len(content) > 3_500_000: return '', 'Фото слишком большое. Выберите файл до 3,5 МБ.'
    mime = (file_storage.mimetype or '').lower()
    if mime not in ('image/jpeg','image/png','image/webp'):
        return '', 'Поддерживаются JPG, PNG и WEBP'
    ext = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp'}[mime]
    path = f'greenleaf/{folder}/{int(time.time())}-{secrets.token_hex(5)}.{ext}'
    try:
        response = requests.put('https://blob.vercel-storage.com/' + urllib.parse.quote(path, safe='/'),
            data=content, timeout=25, headers={
                'Authorization': f'Bearer {BLOB_TOKEN}', 'x-api-version':'7',
                'x-content-type':mime, 'x-add-random-suffix':'0', 'x-allow-overwrite':'0'})
        if response.status_code not in (200,201):
            app.logger.error('Blob upload failed: %s %s', response.status_code, response.text[:400])
            return '', 'Vercel Blob не принял фото. Проверьте подключение Blob к проекту.'
        data = response.json()
        url = data.get('url')
        if not url: return '', 'Blob не вернул URL фотографии'
        return url, None
    except Exception:
        app.logger.exception('Blob upload exception')
        return '', 'Не удалось загрузить фото в Blob'

@app.post('/api/products/<int:product_id>/comments')
def add_comment(product_id):
    data = request.get_json(silent=True) or {}
    author = str(data.get('author','')).strip()[:80]
    body = str(data.get('body','')).strip()[:1000]
    if not author or not body: return jsonify({'error':'Заполните имя и комментарий'}),400
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT id FROM products WHERE id=%s AND active=TRUE',(product_id,))
            if not cur.fetchone(): return jsonify({'error':'Товар не найден'}),404
            cur.execute('INSERT INTO product_comments(product_id,author,body) VALUES(%s,%s,%s) RETURNING id,product_id,author,body,created_at',(product_id,author,body))
            row = dict(cur.fetchone())
            row['created_at'] = row['created_at'].isoformat()
        return jsonify({'comment':row}),201
    except Exception:
        app.logger.exception('Add comment failed')
        return jsonify({'error':'Не удалось сохранить комментарий'}),500

@app.get('/api/products/<int:product_id>/comments')
def get_comments(product_id):
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT id,product_id,author,body,created_at FROM product_comments WHERE product_id=%s ORDER BY id DESC LIMIT 50',(product_id,))
            rows=[]
            for r in cur.fetchall():
                x=dict(r); x['created_at']=x['created_at'].isoformat(); rows.append(x)
        return jsonify({'comments':rows})
    except Exception:
        app.logger.exception('Get comments failed')
        return jsonify({'error':'Не удалось загрузить комментарии'}),500

@app.post('/api/orders')
def create_order():
    data = request.get_json(silent=True) or {}
    name = str(data.get('customer_name','')).strip()[:120]
    phone = str(data.get('phone','')).strip()[:80]
    city = str(data.get('city','')).strip()[:100]
    method = str(data.get('delivery_method','')).strip()[:80]
    address = str(data.get('address','')).strip()[:300]
    comment = str(data.get('comment','')).strip()[:1000]
    incoming = data.get('items', [])
    if not name or not phone or not city or not isinstance(incoming,list) or not incoming:
        return jsonify({'error':'Заполните имя, телефон, город и добавьте товары'}),400
    try:
        with connection() as conn, conn.cursor() as cur:
            ids=[]
            for item in incoming:
                try: ids.append((int(item.get('id')), max(1,min(99,int(item.get('quantity',1))))))
                except Exception: pass
            if not ids: return jsonify({'error':'В корзине нет корректных товаров'}),400
            product_ids=list({x[0] for x in ids})
            cur.execute('SELECT id,name,price FROM products WHERE active=TRUE AND id = ANY(%s)',(product_ids,))
            by_id={int(p['id']):p for p in cur.fetchall()}
            items=[]; total=0
            for pid,qty in ids:
                p=by_id.get(pid)
                if not p: continue
                line=round(float(p['price'])*qty,2); total+=line
                items.append({'id':pid,'name':p['name'],'quantity':qty,'price':float(p['price']),'line_total':line})
            if not items: return jsonify({'error':'Товары больше недоступны'}),400
            cur.execute('''INSERT INTO orders(customer_name,phone,city,delivery_method,address,comment,items,total)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING id''',
                (name,phone,city,method,address,comment,json.dumps(items,ensure_ascii=False),round(total,2)))
            order_id=cur.fetchone()['id']
        notify_owner(order_id,name,phone,city,method,address,comment,items,total)
        return jsonify({'ok':True,'order_id':order_id,'total':round(total,2)}),201
    except Exception:
        app.logger.exception('Create order failed')
        return jsonify({'error':'Не удалось оформить заказ. Попробуйте ещё раз.'}),500

@app.get('/api/orders')
def get_orders():
    denied=admin_required()
    if denied: return denied
    view=request.args.get('view','active')
    active_statuses=['new','processing','ready']
    try:
        with connection() as conn, conn.cursor() as cur:
            if view=='archive':
                cur.execute("SELECT * FROM orders WHERE status IN ('completed','cancelled') ORDER BY id DESC LIMIT 100")
            else:
                cur.execute("SELECT * FROM orders WHERE status NOT IN ('completed','cancelled') ORDER BY id DESC LIMIT 100")
            rows=[]
            for r in cur.fetchall():
                d=dict(r); d['total']=float(d.get('total') or 0)
                if isinstance(d.get('items'),str): d['items']=json.loads(d['items'])
                d['created_at']=d['created_at'].isoformat(); rows.append(d)
        return jsonify({'orders':rows})
    except Exception:
        app.logger.exception('Load orders failed')
        return jsonify({'error':'Не удалось загрузить заказы'}),500

@app.patch('/api/orders/<int:order_id>/status')
def update_order_status(order_id):
    denied=admin_required()
    if denied: return denied
    data=request.get_json(silent=True) or {}
    status=str(data.get('status',''))
    if status not in ('new','processing','ready','completed','cancelled'):
        return jsonify({'error':'Неизвестный статус'}),400
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute('UPDATE orders SET status=%s WHERE id=%s RETURNING id,status',(status,order_id))
            row=cur.fetchone()
            if not row: return jsonify({'error':'Заказ не найден'}),404
        return jsonify({'order':dict(row)})
    except Exception:
        app.logger.exception('Update status failed')
        return jsonify({'error':'Не удалось изменить статус'}),500

@app.get('/api/admin/check')
def admin_check():
    uid=telegram_user_id(request.headers.get('X-Telegram-Init-Data',''))
    return jsonify({'admin':bool(uid and ADMIN_ID and secrets.compare_digest(uid,str(ADMIN_ID)))})


def notify_owner(order_id,name,phone,city,method,address,comment,items,total):
    if not BOT_TOKEN or not ADMIN_ID: return
    lines=[f'Новый заказ #{order_id}',f'Покупатель: {name}',f'Телефон: {phone}',f'Город: {city}',f'Доставка: {method or "не указана"}']
    if address: lines.append(f'Адрес: {address}')
    lines += ['Товары:']+[f'• {i["name"]} × {i["quantity"]} — {i["line_total"]:.2f} TMT' for i in items]
    lines.append(f'Итого: {total:.2f} TMT')
    if comment: lines.append(f'Комментарий: {comment}')
    try:
        response = requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',json={'chat_id':ADMIN_ID,'text':'\n'.join(lines)},timeout=8)
        if not response.ok:
            app.logger.error('Telegram notification returned %s: %s', response.status_code, response.text[:300])
    except Exception: app.logger.exception('Telegram notification failed')

# Create tables lazily on the first request; suitable for serverless deployment.
_db_ready = False
@app.before_request
def ensure_db():
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True

if __name__ == '__main__':
    app.run(debug=True)
