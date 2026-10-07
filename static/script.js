let products = [];
let cart = [];
let adminMode = false;

const ORDER_STATUSES = {
  new: "Новый",
  accepted: "Принят",
  packing: "Собирается",
  delivery: "Передан в доставку",
  completed: "Завершён",
  cancelled: "Отменён"
};

function telegramInitData() {
  if (
    window.Telegram &&
    window.Telegram.WebApp
  ) {
    return window.Telegram.WebApp.initData || "";
  }

  return "";
}

function adminHeaders() {
  const initData = telegramInitData();

  return {
    "Content-Type": "application/json",
    "X-Telegram-Init-Data": initData
  };
}


async function loadCatalog() {
  const res = await fetch("/api/products");
  const data = await res.json();

  products = data.products || [];

  document.getElementById(
    "catalogStatus"
  ).textContent =
    `Каталог загружен: ${products.length} товара`;

  renderCatalog();
  renderCart();
}


function money(v) {
  return Number(v).toLocaleString(
    "ru-RU"
  ) + " TMT";
}


function renderCatalog() {
  const root =
    document.getElementById(
      "catalog"
    );

  root.innerHTML = products.map(p => `
    <div class="card">
      <div class="row">
        <div>
          <h2>${escapeHtml(p.name)}</h2>
          <div class="muted">
            ${escapeHtml(p.description || "")}
          </div>
          <div class="price">
            ${money(p.price)}
          </div>
        </div>

        <button
          onclick="addToCart(${p.id})"
        >
          В корзину
        </button>
      </div>
    </div>
  `).join("");
}


function addToCart(id) {
  const item = cart.find(
    x => x.id === id
  );

  if (item) {
    item.quantity++;
  } else {
    cart.push({
      id,
      quantity: 1
    });
  }

  renderCart();
}


function changeQty(id, delta) {
  const item = cart.find(
    x => x.id === id
  );

  if (!item) return;

  item.quantity += delta;

  if (item.quantity <= 0) {
    cart = cart.filter(
      x => x.id !== id
    );
  }

  renderCart();
}


function renderCart() {
  const root =
    document.getElementById(
      "cart"
    );

  let total = 0;
  let count = 0;

  if (!cart.length) {
    root.innerHTML =
      '<div class="muted">Корзина пока пустая.</div>';
  } else {
    root.innerHTML = cart.map(item => {
      const p = products.find(
        x => x.id === item.id
      );

      if (!p) return "";

      const line =
        Number(p.price)
        * item.quantity;

      total += line;
      count += item.quantity;

      return `
        <div class="card">
          <div class="row">
            <div>
              <b>${escapeHtml(p.name)}</b>
              <br>
              ${money(line)}
            </div>

            <div class="qty">
              <button
                class="secondary"
                onclick="changeQty(${p.id},-1)"
              >
                −
              </button>

              <b>${item.quantity}</b>

              <button
                onclick="changeQty(${p.id},1)"
              >
                +
              </button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  document.getElementById(
    "cartCount"
  ).textContent = count;

  document.getElementById(
    "cartTotal"
  ).textContent =
    `Итого: ${money(total)}`;

  document.getElementById(
    "checkoutBtn"
  ).disabled = !cart.length;
}


function showCheckout() {
  if (!cart.length) return;

  document.getElementById(
    "checkout"
  ).classList.remove("hidden");

  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: "smooth"
  });
}


function hideCheckout() {
  document.getElementById(
    "checkout"
  ).classList.add("hidden");
}


async function submitOrder() {
  if (!cart.length) return;

  const payload = {
    customer_name:
      document.getElementById(
        "name"
      ).value.trim(),

    phone:
      document.getElementById(
        "phone"
      ).value.trim(),

    city:
      document.getElementById(
        "city"
      ).value.trim(),

    delivery_method:
      document.getElementById(
        "method"
      ).value,

    address:
      document.getElementById(
        "address"
      ).value.trim(),

    comment:
      document.getElementById(
        "comment"
      ).value.trim(),

    items: cart
  };

  if (!payload.customer_name) {
    alert("Укажи имя.");
    return;
  }

  const result =
    document.getElementById(
      "orderResult"
    );

  result.textContent =
    "Отправляем заказ…";

  try {
    const res = await fetch(
      "/api/orders",
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json"
        },
        body: JSON.stringify(
          payload
        )
      }
    );

    const data =
      await res.json();

    if (!res.ok) {
      result.textContent =
        data.error ||
        "Не удалось создать заказ.";

      return;
    }

    result.innerHTML =
      `<div class="notice">
        Заказ №${data.order_id}
        успешно оформлен.
        Сумма: ${money(data.total)}.
      </div>`;

    if (!data.telegram_sent) {
      result.innerHTML +=
        `<div class="notice">
          Заказ сохранён,
          но Telegram пока не настроен:
          ${escapeHtml(
            data.telegram_error || ""
          )}
        </div>`;
    }

    cart = [];

    renderCart();

  } catch (e) {
    result.textContent =
      "Ошибка соединения с сервером.";
  }
}


/* =========================
   ADMIN
========================= */


async function checkAdmin() {
  const initData =
    telegramInitData();

  if (!initData) {
    return;
  }

  try {
    const res = await fetch(
      "/api/admin/check",
      {
        headers: {
          "X-Telegram-Init-Data":
            initData
        }
      }
    );

    if (!res.ok) {
      return;
    }

    const data =
      await res.json();

    if (data.admin) {
      adminMode = true;

      document.getElementById(
        "adminPanel"
      ).classList.remove("hidden");

      await loadOrders();
    }

  } catch (e) {
    console.log(
      "Admin check failed"
    );
  }
}


async function loadOrders() {
  if (!adminMode) return;

  const root =
    document.getElementById(
      "orders"
    );

  root.innerHTML =
    '<div class="muted">Загрузка заказов…</div>';

  try {
    const res = await fetch(
      "/api/orders",
      {
        headers: {
          "X-Telegram-Init-Data":
            telegramInitData()
        }
      }
    );

    const data =
      await res.json();

    if (!res.ok) {
      root.innerHTML =
        `<div class="notice">
          ${escapeHtml(
            data.error ||
            "Не удалось загрузить заказы"
          )}
        </div>`;

      return;
    }

    renderOrders(
      data.orders || []
    );

  } catch (e) {
    root.innerHTML =
      `<div class="notice">
        Ошибка загрузки заказов.
      </div>`;
  }
}


function renderOrders(orders) {
  const root =
    document.getElementById(
      "orders"
    );

  if (!orders.length) {
    root.innerHTML =
      '<div class="muted">Заказов пока нет.</div>';

    return;
  }

  root.innerHTML =
    orders.map(order => {

      const itemsHtml =
        (order.items || [])
          .map(item => `
            <div class="order-item">
              ${escapeHtml(item.name)}
              × ${item.quantity}
              — ${money(item.line_total)}
            </div>
          `)
          .join("");

      const statusOptions =
        Object.entries(
          ORDER_STATUSES
        )
        .map(([value, label]) => `
          <option
            value="${value}"
            ${value === order.status
              ? "selected"
              : ""}
          >
            ${label}
          </option>
        `)
        .join("");

      const date =
        order.created_at
          ? new Date(
              order.created_at
            ).toLocaleString(
              "ru-RU"
            )
          : "";

      return `
        <div class="admin-order">

          <div class="row">
            <h3>
              Заказ №${order.id}
            </h3>

            <span class="status">
              ${escapeHtml(
                ORDER_STATUSES[
                  order.status
                ] ||
                order.status
              )}
            </span>
          </div>

          <div class="muted">
            ${escapeHtml(date)}
          </div>

          <hr>

          <div>
            <b>Клиент</b><br>
            ${escapeHtml(
              order.customer_name
            )}
          </div>

          <div>
            <b>Телефон</b><br>
            ${escapeHtml(
              order.phone ||
              "не указан"
            )}
          </div>

          <div>
            <b>Город</b><br>
            ${escapeHtml(
              order.city ||
              "не указан"
            )}
          </div>

          <div>
            <b>Получение</b><br>
            ${escapeHtml(
              order.delivery_method
            )}
          </div>

          <div>
            <b>Адрес / пункт</b><br>
            ${escapeHtml(
              order.address ||
              "не указан"
            )}
          </div>

          <hr>

          <b>Товары</b>

          <div class="order-items">
            ${itemsHtml}
          </div>

          <div class="order-total">
            Итого:
            ${money(order.total)}
          </div>

          <div>
            <b>Комментарий</b><br>
            ${escapeHtml(
              order.comment ||
              "нет"
            )}
          </div>

          <label>
            Статус
            <select
              onchange="changeOrderStatus(
                ${order.id},
                this.value
              )"
            >
              ${statusOptions}
            </select>
          </label>

        </div>
      `;
    })
    .join("");
}


async function changeOrderStatus(
  orderId,
  status
) {
  try {
    const res = await fetch(
      `/api/orders/${orderId}/status`,
      {
        method: "PATCH",
        headers: adminHeaders(),
        body: JSON.stringify({
          status
        })
      }
    );

    const data =
      await res.json();

    if (!res.ok) {
      alert(
        data.error ||
        "Не удалось изменить статус."
      );

      await loadOrders();

      return;
    }

    await loadOrders();

  } catch (e) {
    alert(
      "Ошибка соединения с сервером."
    );

    await loadOrders();
  }
}


function escapeHtml(value) {
  return String(value)
    .replaceAll(
      "&",
      "&amp;"
    )
    .replaceAll(
      "<",
      "&lt;"
    )
    .replaceAll(
      ">",
      "&gt;"
    )
    .replaceAll(
      '"',
      "&quot;"
    )
    .replaceAll(
      "'",
      "&#039;"
    );
}


/* =========================
   START
========================= */

async function startApp() {
  if (
    window.Telegram &&
    window.Telegram.WebApp
  ) {
    Telegram.WebApp.ready();
    Telegram.WebApp.expand();
  }

  try {
    await loadCatalog();
  } catch (e) {
    document.getElementById(
      "catalogStatus"
    ).textContent =
      "Не удалось загрузить каталог";
  }

  await checkAdmin();
}


startApp();
