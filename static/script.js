let products = [];
let cart = [];

async function loadCatalog() {
  const res = await fetch("/api/products");
  const data = await res.json();
  products = data.products || [];
  document.getElementById("catalogStatus").textContent =
    `Каталог загружен: ${products.length} товара`;
  renderCatalog();
  renderCart();
}

function money(v) {
  return Number(v).toLocaleString("ru-RU") + " TMT";
}

function renderCatalog() {
  const root = document.getElementById("catalog");
  root.innerHTML = products.map(p => `
    <div class="card">
      <div class="row">
        <div>
          <h2>${escapeHtml(p.name)}</h2>
          <div class="muted">${escapeHtml(p.description || "")}</div>
          <div class="price">${money(p.price)}</div>
        </div>
        <button onclick="addToCart(${p.id})">В корзину</button>
      </div>
    </div>
  `).join("");
}

function addToCart(id) {
  const item = cart.find(x => x.id === id);
  if (item) item.quantity++;
  else cart.push({id, quantity: 1});
  renderCart();
}

function changeQty(id, delta) {
  const item = cart.find(x => x.id === id);
  if (!item) return;
  item.quantity += delta;
  if (item.quantity <= 0) cart = cart.filter(x => x.id !== id);
  renderCart();
}

function renderCart() {
  const root = document.getElementById("cart");
  let total = 0, count = 0;

  if (!cart.length) {
    root.innerHTML = '<div class="muted">Корзина пока пустая.</div>';
  } else {
    root.innerHTML = cart.map(item => {
      const p = products.find(x => x.id === item.id);
      const line = Number(p.price) * item.quantity;
      total += line;
      count += item.quantity;
      return `
        <div class="card">
          <div class="row">
            <div><b>${escapeHtml(p.name)}</b><br>${money(line)}</div>
            <div class="qty">
              <button class="secondary" onclick="changeQty(${p.id},-1)">−</button>
              <b>${item.quantity}</b>
              <button onclick="changeQty(${p.id},1)">+</button>
            </div>
          </div>
        </div>`;
    }).join("");
  }

  document.getElementById("cartCount").textContent = count;
  document.getElementById("cartTotal").textContent = `Итого: ${money(total)}`;
  document.getElementById("checkoutBtn").disabled = !cart.length;
}

function showCheckout() {
  if (!cart.length) return;
  document.getElementById("checkout").classList.remove("hidden");
  window.scrollTo({top: document.body.scrollHeight, behavior: "smooth"});
}

function hideCheckout() {
  document.getElementById("checkout").classList.add("hidden");
}

async function submitOrder() {
  if (!cart.length) return;

  const payload = {
    customer_name: document.getElementById("name").value.trim(),
    phone: document.getElementById("phone").value.trim(),
    city: document.getElementById("city").value.trim(),
    delivery_method: document.getElementById("method").value,
    address: document.getElementById("address").value.trim(),
    comment: document.getElementById("comment").value.trim(),
    items: cart
  };

  if (!payload.customer_name) {
    alert("Укажи имя.");
    return;
  }

  const result = document.getElementById("orderResult");
  result.textContent = "Отправляем заказ…";

  try {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (!res.ok) {
      result.textContent = data.error || "Не удалось создать заказ.";
      return;
    }

    result.innerHTML =
  `<div class="notice">Заказ успешно оформлен. Сумма: ${money(data.total)}.</div>`;

    if (!data.telegram_sent) {
      result.innerHTML +=
        `<div class="notice">Заказ сохранён, но Telegram пока не настроен: ${escapeHtml(data.telegram_error || "")}</div>`;
    }

    cart = [];
    renderCart();
  } catch (e) {
    result.textContent = "Ошибка соединения с сервером.";
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

loadCatalog().catch(() => {
  document.getElementById("catalogStatus").textContent = "Не удалось загрузить каталог";
});
