let products = [];
let cart = [];
let adminMode = false;

let currentLanguage =
  localStorage.getItem("greenleaf_language") || "ru";


const TRANSLATIONS = {

  ru: {
    heroLabel: "GREENLEAF",
    heroTitle: "Добро пожаловать в Greenleaf",
    heroText:
      "Выбирайте понравившиеся товары и оформляйте заказ быстро и удобно.",
    viewCatalog: "Смотреть каталог",
    popular: "Каталог",
    allProducts: "Все товары",

    home: "Главная",
    catalog: "Каталог",
    cart: "Корзина",
    profile: "Профиль",

    loading: "Загрузка каталога…",
    cartSubtitle:
      "Проверьте товары перед оформлением.",
    total: "Итого",
    checkout: "Оформить заказ",
    order: "Оформление заказа",

    name: "Имя",
    namePlaceholder: "Например, Alina",
    phone: "Телефон",
    city: "Город",
    cityPlaceholder: "Туркменбаши",
    method: "Способ получения",
    pickup: "Самовывоз",
    delivery: "Доставка",
    address: "Адрес / пункт выдачи",
    addressPlaceholder:
      "Адрес или название пункта",
    comment: "Комментарий",
    commentPlaceholder:
      "Дополнительная информация",

    back: "Назад",
    sendOrder: "Отправить заказ",

    profileSubtitle:
      "Ваша информация в Greenleaf.",
    guest: "Гость",

    adminTitle: "Панель владельца",
    adminDescription:
      "Управление заказами Greenleaf.",
    openAdmin: "Открыть панель",
    orders: "Заказы",
    refresh: "Обновить",

    emptyCart: "Корзина пока пустая.",
    emptyCartIcon: "🛍",

    catalogLoaded: "Каталог загружен",
    catalogError:
      "Не удалось загрузить каталог",

    enterName: "Укажи имя.",
    sending: "Отправляем заказ…",
    orderSuccess:
      "Заказ успешно оформлен.",
    orderSavedTelegram:
      "Заказ сохранён, но Telegram пока не настроен:",
    connectionError:
      "Ошибка соединения с сервером.",
    orderLoadError:
      "Не удалось загрузить заказы.",
    noOrders: "Заказов пока нет.",
    accessDenied: "Доступ запрещён",

    new: "Новый",
    accepted: "Принят",
    packing: "Собирается",
    deliveryStatus: "Передан в доставку",
    completed: "Завершён",
    cancelled: "Отменён",

    client: "Клиент",
    phoneLabel: "Телефон",
    cityLabel: "Город",
    receiving: "Получение",
    addressLabel: "Адрес / пункт",
    products: "Товары",
    commentLabel: "Комментарий",
    none: "нет",
    notSpecified: "не указан"
  },


  tm: {
    heroLabel: "GREENLEAF",
    heroTitle: "Greenleaf-e hoş geldiňiz",
    heroText:
      "Özüňize göwnüňizden turan harytlary saýlaň we sargydyňyzy çalt hem amatly resmileşdiriň.",
    viewCatalog: "Katalogy gör",
    popular: "Katalog",
    allProducts: "Ähli harytlar",

    home: "Baş sahypa",
    catalog: "Katalog",
    cart: "Sebet",
    profile: "Profil",

    loading: "Katalog ýüklenýär…",
    cartSubtitle:
      "Resmileşdirmezden öň harytlaryňyzy barlaň.",
    total: "Jemi",
    checkout: "Sargydy resmileşdirmek",
    order: "Sargyt resmileşdirmek",

    name: "Ady",
    namePlaceholder: "Mysal üçin, Alina",
    phone: "Telefon",
    city: "Şäher",
    cityPlaceholder: "Türkmenbaşy",
    method: "Almak usuly",
    pickup: "Özi alyp gitmek",
    delivery: "Eltip bermek",
    address: "Salgy / almak nokady",
    addressPlaceholder:
      "Salgysy ýa-da almak nokadynyň ady",
    comment: "Teswir",
    commentPlaceholder:
      "Goşmaça maglumat",

    back: "Yza",
    sendOrder: "Sargydy ibermek",

    profileSubtitle:
      "Greenleaf-däki maglumatlaryňyz.",
    guest: "Myhman",

    adminTitle: "Eýe üçin dolandyryş paneli",
    adminDescription:
      "Greenleaf sargytlaryny dolandyryň.",
    openAdmin: "Dolandyryş panelini aç",
    orders: "Sargytlar",
    refresh: "Täzele",

    emptyCart: "Sebet häzirlikçe boş.",
    emptyCartIcon: "🛍",

    catalogLoaded: "Katalog ýüklenildi",
    catalogError:
      "Katalogy ýüklemek başartmady",

    enterName: "Adyňyzy ýazyň.",
    sending: "Sargyt iberilýär…",
    orderSuccess:
      "Sargyt üstünlikli kabul edildi.",
    orderSavedTelegram:
      "Sargyt saklandy, ýöne Telegram häzir sazlanmady:",
    connectionError:
      "Serwer bilen birikme ýalňyşlygy.",
    orderLoadError:
      "Sargytlary ýüklemek başartmady.",
    noOrders: "Häzirlikçe sargyt ýok.",
    accessDenied: "Giriş gadagan",

    new: "Täze",
    accepted: "Kabul edildi",
    packing: "Taýýarlanylýar",
    deliveryStatus: "Eltip bermäge berildi",
    completed: "Tamamlandy",
    cancelled: "Ýatyryldy",

    client: "Müşderi",
    phoneLabel: "Telefon",
    cityLabel: "Şäher",
    receiving: "Almak usuly",
    addressLabel: "Salgy / nokat",
    products: "Harytlar",
    commentLabel: "Teswir",
    none: "ýok",
    notSpecified: "görkezilmedi"
  }

};


const ORDER_STATUSES = {
  new: "new",
  accepted: "accepted",
  packing: "packing",
  delivery: "delivery",
  completed: "completed",
  cancelled: "cancelled"
};


/* =========================
   LANGUAGE
========================= */

function t(key) {
  return (
    TRANSLATIONS[currentLanguage]?.[key]
    ||
    TRANSLATIONS.ru[key]
    ||
    key
  );
}


function applyLanguage() {

  document.documentElement.lang =
    currentLanguage === "ru"
      ? "ru"
      : "tk";

  document.querySelectorAll(
    "[data-i18n]"
  ).forEach(el => {
    const key =
      el.dataset.i18n;

    el.textContent = t(key);
  });


  document.querySelectorAll(
    "[data-i18n-placeholder]"
  ).forEach(el => {

    const key =
      el.dataset.i18nPlaceholder;

    el.placeholder = t(key);
  });


  const languageButton =
    document.getElementById(
      "languageBtn"
    );

  if (languageButton) {
    languageButton.textContent =
      currentLanguage === "ru"
        ? "TM"
        : "RU";
  }


  renderCatalog();
  renderHomeProducts();
  renderCart();

  if (adminMode) {
    loadOrders();
  }
}


function toggleLanguage() {

  currentLanguage =
    currentLanguage === "ru"
      ? "tm"
      : "ru";

  localStorage.setItem(
    "greenleaf_language",
    currentLanguage
  );

  applyLanguage();
}


/* =========================
   TELEGRAM
========================= */

function telegramInitData() {

  if (
    window.Telegram &&
    window.Telegram.WebApp
  ) {
    return (
      window.Telegram.WebApp.initData
      || ""
    );
  }

  return "";
}


function telegramUser() {

  if (
    window.Telegram &&
    window.Telegram.WebApp &&
    window.Telegram.WebApp
      .initDataUnsafe &&
    window.Telegram.WebApp
      .initDataUnsafe.user
  ) {
    return window.Telegram.WebApp
      .initDataUnsafe.user;
  }

  return null;
}


function adminHeaders() {

  return {
    "Content-Type":
      "application/json",

    "X-Telegram-Init-Data":
      telegramInitData()
  };
}


/* =========================
   NAVIGATION
========================= */

function openPage(page) {

  document.querySelectorAll(
    ".page"
  ).forEach(el => {
    el.classList.remove("active");
  });


  const target =
    document.getElementById(
      `page-${page}`
    );

  if (target) {
    target.classList.add("active");
  }


  document.querySelectorAll(
    ".nav-btn"
  ).forEach(btn => {

    btn.classList.toggle(
      "active",
      btn.dataset.page === page
    );

  });


  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}


/* =========================
   CATALOG
========================= */

async function loadCatalog() {

  const res =
    await fetch(
      "/api/products"
    );

  const data =
    await res.json();

  products =
    data.products || [];

  document.getElementById(
    "catalogStatus"
  ).textContent =
    `${t("catalogLoaded")}: ${products.length}`;

  renderCatalog();
  renderHomeProducts();
  renderCart();
}


function money(value) {

  return (
    Number(value)
      .toLocaleString("ru-RU")
    + " TMT"
  );
}


function renderCatalog() {

  const root =
    document.getElementById(
      "catalog"
    );

  if (!root) return;


  root.innerHTML =
    products.map(p => `

      <div class="product-card">

        <div class="product-info">

          <div class="product-name">
            ${escapeHtml(p.name)}
          </div>

          <div class="product-description">
            ${escapeHtml(
              p.description || ""
            )}
          </div>

          <div class="product-bottom">

            <div class="product-price">
              ${money(p.price)}
            </div>

            <button
              class="add-btn"
              onclick="addToCart(${p.id})"
            >
              +
            </button>

          </div>

        </div>

      </div>

    `).join("");
}


function renderHomeProducts() {

  const root =
    document.getElementById(
      "homeProducts"
    );

  if (!root) return;


  const preview =
    products.slice(0, 3);


  root.innerHTML =
    preview.map(p => `

      <div class="product-card">

        <div class="product-name">
          ${escapeHtml(p.name)}
        </div>

        <div class="product-description">
          ${escapeHtml(
            p.description || ""
          )}
        </div>

        <div class="product-bottom">

          <div class="product-price">
            ${money(p.price)}
          </div>

          <button
            class="add-btn"
            onclick="addToCart(${p.id})"
          >
            +
          </button>

        </div>

      </div>

    `).join("");
}


/* =========================
   CART
========================= */

function addToCart(id) {

  const item =
    cart.find(
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

  openPage("cart");
}


function changeQty(
  id,
  delta
) {

  const item =
    cart.find(
      x => x.id === id
    );

  if (!item) return;


  item.quantity += delta;


  if (item.quantity <= 0) {

    cart =
      cart.filter(
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

  if (!root) return;


  let total = 0;
  let count = 0;


  if (!cart.length) {

    root.innerHTML = `

      <div class="empty">

        <div class="empty-icon">
          ${t("emptyCartIcon")}
        </div>

        <div>
          ${t("emptyCart")}
        </div>

      </div>

    `;

  } else {

    root.innerHTML =
      cart.map(item => {

        const p =
          products.find(
            x => x.id === item.id
          );


        if (!p) return "";


        const line =
          Number(p.price)
          * item.quantity;


        total += line;
        count += item.quantity;


        return `

          <div class="cart-card">

            <div class="row">

              <div>

                <div class="cart-name">
                  ${escapeHtml(
                    p.name
                  )}
                </div>

                <div class="cart-price">
                  ${money(line)}
                </div>

              </div>


              <div class="qty">

                <button
                  onclick="changeQty(
                    ${p.id},
                    -1
                  )"
                >
                  −
                </button>

                <b>
                  ${item.quantity}
                </b>

                <button
                  onclick="changeQty(
                    ${p.id},
                    1
                  )"
                >
                  +
                </button>

              </div>

            </div>

          </div>

        `;

      }).join("");

  }


  const totalElement =
    document.getElementById(
      "cartTotal"
    );

  if (totalElement) {
    totalElement.textContent =
      money(total);
  }


  const button =
    document.getElementById(
      "checkoutBtn"
    );

  if (button) {
    button.disabled =
      !cart.length;
  }


  const badge =
    document.getElementById(
      "cartBadge"
    );

  if (badge) {

    badge.textContent =
      count;

    badge.classList.toggle(
      "visible",
      count > 0
    );

  }


  const summary =
    document.getElementById(
      "cartSummary"
    );

  if (summary) {
    summary.classList.toggle(
      "hidden",
      !cart.length
    );
  }
}


/* =========================
   CHECKOUT
========================= */

function showCheckout() {

  if (!cart.length) return;


  document.getElementById(
    "checkout"
  ).classList.remove(
    "hidden"
  );


  window.scrollTo({
    top:
      document.body
        .scrollHeight,
    behavior: "smooth"
  });
}


function hideCheckout() {

  document.getElementById(
    "checkout"
  ).classList.add(
    "hidden"
  );
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

    alert(
      t("enterName")
    );

    return;
  }


  const result =
    document.getElementById(
      "orderResult"
    );


  result.textContent =
    t("sending");


  try {

    const res =
      await fetch(
        "/api/orders",
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify(
              payload
            )
        }
      );


    const data =
      await res.json();


    if (!res.ok) {

      result.textContent =
        data.error ||
        t("connectionError");

      return;
    }


    result.innerHTML = `

      <div class="notice">

        ${t("orderSuccess")}

        №${data.order_id}.

        ${money(data.total)}.

      </div>

    `;


    if (!data.telegram_sent) {

      result.innerHTML += `

        <div class="notice">

          ${t(
            "orderSavedTelegram"
          )}

          ${escapeHtml(
            data.telegram_error || ""
          )}

        </div>

      `;

    }


    cart = [];

    renderCart();

  } catch (e) {

    result.textContent =
      t("connectionError");

  }
}


/* =========================
   PROFILE
========================= */

function renderProfile() {

  const user =
    telegramUser();


  const nameElement =
    document.getElementById(
      "profileName"
    );

  const usernameElement =
    document.getElementById(
      "profileUsername"
    );


  if (!user) {

    nameElement.textContent =
      t("guest");

    usernameElement.textContent =
      "";

    return;
  }


  const fullName =
    [
      user.first_name,
      user.last_name
    ]
      .filter(Boolean)
      .join(" ");


  nameElement.textContent =
    fullName ||
    t("guest");


  usernameElement.textContent =
    user.username
      ? "@" + user.username
      : "";
}


function openAdminOrders() {

  document.getElementById(
    "adminOrders"
  ).classList.remove(
    "hidden"
  );

  loadOrders();
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

    const res =
      await fetch(
        "/api/admin/check",
        {
          headers: {
            "X-Telegram-Init-Data":
              initData
          }
        }
      );


    if (!res.ok) return;


    const data =
      await res.json();


    if (data.admin) {

      adminMode = true;

      document.getElementById(
        "adminEntry"
      ).classList.remove(
        "hidden"
      );

    }

  } catch (e) {

    console.log(
      "Admin check failed"
    );

  }
}


function statusLabel(status) {

  const map = {

    new: "new",
    accepted: "accepted",
    packing: "packing",
    delivery: "deliveryStatus",
    completed: "completed",
    cancelled: "cancelled"

  };


  return t(
    map[status] || status
  );
}


async function loadOrders() {

  if (!adminMode) return;


  const root =
    document.getElementById(
      "orders"
    );


  root.innerHTML =
    `<div class="muted">
      ${t("loading")}
    </div>`;


  try {

    const res =
      await fetch(
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
            t("orderLoadError")
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
        ${t("orderLoadError")}
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
      `<div class="empty">
        ${t("noOrders")}
      </div>`;

    return;
  }


  root.innerHTML =
    orders.map(order => {

      const itemsHtml =
        (order.items || [])
          .map(item => `

            <div class="order-line">

              ${escapeHtml(
                item.name
              )}

              × ${item.quantity}

              —

              ${money(
                item.line_total
              )}

            </div>

          `)
          .join("");


      const statusOptions =
        Object.keys(
          ORDER_STATUSES
        )
        .map(status => `

          <option
            value="${status}"
            ${
              status ===
              order.status
                ? "selected"
                : ""
            }
          >
            ${statusLabel(
              status
            )}
          </option>

        `)
        .join("");


      const date =
        order.created_at
          ? new Date(
              order.created_at
            ).toLocaleString(
              currentLanguage === "ru"
                ? "ru-RU"
                : "tk-TM"
            )
          : "";


      return `

        <div class="admin-order">

          <div class="row">

            <h3>
              №${order.id}
            </h3>

            <span class="order-status">
              ${escapeHtml(
                statusLabel(
                  order.status
                )
              )}
            </span>

          </div>


          <div class="order-meta">
            ${escapeHtml(date)}
          </div>


          <div class="order-separator"></div>


          <div>

            <b>${t("client")}</b><br>

            ${escapeHtml(
              order.customer_name
            )}

          </div>


          <br>


          <div>

            <b>${t("phoneLabel")}</b><br>

            ${escapeHtml(
              order.phone ||
              t("notSpecified")
            )}

          </div>


          <br>


          <div>

            <b>${t("cityLabel")}</b><br>

            ${escapeHtml(
              order.city ||
              t("notSpecified")
            )}

          </div>


          <br>


          <div>

            <b>${t("receiving")}</b><br>

            ${escapeHtml(
              order.delivery_method
            )}

          </div>


          <br>


          <div>

            <b>${t(
              "addressLabel"
            )}</b><br>

            ${escapeHtml(
              order.address ||
              t("notSpecified")
            )}

          </div>


          <div class="order-separator"></div>


          <b>
            ${t("products")}
          </b>


          <div>
            ${itemsHtml}
          </div>


          <div class="order-total">

            ${t("total")}:

            ${money(order.total)}

          </div>


          <div>

            <b>
              ${t("commentLabel")}
            </b><br>

            ${escapeHtml(
              order.comment ||
              t("none")
            )}

          </div>


          <br>


          <label>

            ${t("orders")}

            <select
              onchange="
                changeOrderStatus(
                  ${order.id},
                  this.value
                )
              "
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

    const res =
      await fetch(
        `/api/orders/${orderId}/status`,
        {
          method: "PATCH",
          headers:
            adminHeaders(),

          body:
            JSON.stringify({
              status
            })
        }
      );


    const data =
      await res.json();


    if (!res.ok) {

      alert(
        data.error ||
        t("orderLoadError")
      );

      await loadOrders();

      return;
    }


    await loadOrders();

  } catch (e) {

    alert(
      t("connectionError")
    );

    await loadOrders();

  }
}


/* =========================
   HELPERS
========================= */

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


  applyLanguage();

  renderProfile();


  try {

    await loadCatalog();

  } catch (e) {

    const status =
      document.getElementById(
        "catalogStatus"
      );

    if (status) {

      status.textContent =
        t("catalogError");

    }

  }


  renderProfile();

  await checkAdmin();

}


startApp();
