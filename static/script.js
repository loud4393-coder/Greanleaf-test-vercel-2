let products = [];
let cart = [];

let currentLanguage =
  localStorage.getItem("greenleaf_language") || "ru";

let telegramInitData = "";

let isOwner = false;

let currentAdminTab = "orders";
let currentOrderView = "active";


// ---------------------------------------------------------
// TELEGRAM
// ---------------------------------------------------------

function setupTelegram() {
  if (
    window.Telegram &&
    window.Telegram.WebApp
  ) {
    const tg = window.Telegram.WebApp;

    tg.ready();
    tg.expand();

    telegramInitData =
      tg.initData || "";

    if (
      tg.initDataUnsafe &&
      tg.initDataUnsafe.user
    ) {
      const user =
        tg.initDataUnsafe.user;

      const fullName = [
        user.first_name,
        user.last_name
      ]
        .filter(Boolean)
        .join(" ");

      document.getElementById(
        "profileName"
      ).textContent =
        fullName ||
        user.username ||
        "Пользователь";
    }
  }
}


// ---------------------------------------------------------
// FETCH HELPER
// ---------------------------------------------------------

function requestHeaders() {
  const headers = {};

  if (telegramInitData) {
    headers["X-Telegram-Init-Data"] =
      telegramInitData;
  }

  return headers;
}


async function apiFetch(
  url,
  options = {}
) {
  options.headers = {
    ...(options.headers || {}),
    ...requestHeaders()
  };

  return fetch(
    url,
    options
  );
}


// ---------------------------------------------------------
// LANGUAGE
// ---------------------------------------------------------

function setLanguage(language) {
  currentLanguage = language;

  localStorage.setItem(
    "greenleaf_language",
    language
  );

  document
    .getElementById("langRu")
    .classList.toggle(
      "active",
      language === "ru"
    );

  document
    .getElementById("langTm")
    .classList.toggle(
      "active",
      language === "tm"
    );

  document
    .querySelectorAll("[data-ru][data-tm]")
    .forEach(element => {

      element.textContent =
        element.dataset[language];

    });

  updatePlaceholders();
}


function updatePlaceholders() {
  const ru = currentLanguage === "ru";

  const fields = {
    name: ru
      ? "Например, Alina"
      : "Mysal üçin, Alina",

    phone: ru
      ? "+993 ..."
      : "+993 ...",

    city: ru
      ? "Туркменбаши"
      : "Türkmenbaşy",

    address: ru
      ? "Адрес или пункт"
      : "Salgysy ýa-da nokady",

    comment: ru
      ? "Дополнительная информация"
      : "Goşmaça maglumat",

    productName: ru
      ? "Название товара"
      : "Önümiň ady",

    productCategory: ru
      ? "Например, уход"
      : "Mysal üçin, ideg",

    productPrice: ru
      ? "600"
      : "600",

    productDescription: ru
      ? "Описание товара"
      : "Önümiň düşündirişi"
  };

  Object.entries(fields)
    .forEach(([id, value]) => {

      const element =
        document.getElementById(id);

      if (element) {
        element.placeholder =
          value;
      }
    });
}


// ---------------------------------------------------------
// NAVIGATION
// ---------------------------------------------------------

function showPage(page) {

  document
    .querySelectorAll(".page")
    .forEach(element => {
      element.classList.remove("active");
    });

  document
    .getElementById(
      "page" +
      page.charAt(0).toUpperCase() +
      page.slice(1)
    )
    .classList.add("active");

  document
    .querySelectorAll(".nav-btn")
    .forEach(button => {
      button.classList.remove("active");
    });

  const nav =
    document.getElementById(
      "nav" +
      page.charAt(0).toUpperCase() +
      page.slice(1)
    );

  if (nav) {
    nav.classList.add("active");
  }

  window.scrollTo({
    top:0,
    behavior:"smooth"
  });

  if (
    page === "profile" &&
    isOwner
  ) {
    loadOrders(
      currentOrderView
    );
  }
}


// ---------------------------------------------------------
// MONEY
// ---------------------------------------------------------

function money(value) {
  return (
    Number(value)
      .toLocaleString(
        "ru-RU"
      ) +
    " TMT"
  );
}


// ---------------------------------------------------------
// ESCAPE
// ---------------------------------------------------------

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


// ---------------------------------------------------------
// PRODUCTS
// ---------------------------------------------------------

async function loadProducts() {

  try {

    const response =
      await apiFetch(
        "/api/products"
      );

    const data =
      await response.json();

    products =
      data.products || [];

    renderHomeProducts();
    renderCatalog();
    renderCart();
    renderAdminProducts();

    document.getElementById(
      "catalogStatus"
    ).textContent =
      currentLanguage === "ru"
        ? `Товаров: ${products.length}`
        : `Önümler: ${products.length}`;

  } catch (error) {

    document.getElementById(
      "catalogStatus"
    ).textContent =
      currentLanguage === "ru"
        ? "Не удалось загрузить каталог"
        : "Katalogy ýükläp bolmady";

  }
}


function productImage(product) {

  if (product.image_url) {

    return `
      <img
        class="product-image"
        src="${escapeHtml(product.image_url)}"
        alt="${escapeHtml(product.name)}"
      >
    `;

  }

  return `
    <div class="product-no-image">
      Greenleaf
    </div>
  `;
}


function productCard(product) {

  const addText =
    currentLanguage === "ru"
      ? "В корзину"
      : "Sebede goş";

  const description =
    product.description ||
    (
      currentLanguage === "ru"
        ? "Описание отсутствует."
        : "Düşündiriş ýok."
    );

  return `
    <article class="card">

      ${productImage(product)}

      <div class="product-body">

        ${
          product.category
            ? `
              <div class="product-category">
                ${escapeHtml(product.category)}
              </div>
            `
            : ""
        }

        <div class="product-name">
          ${escapeHtml(product.name)}
        </div>

        <div class="product-description">
          ${escapeHtml(description)}
        </div>

        <div class="product-bottom">

          <div class="price">
            ${money(product.price)}
          </div>

          <div style="
            display:flex;
            gap:6px;
          ">

            <button
              class="btn secondary"
              onclick="openProductModal(${product.id})"
            >
              ${currentLanguage === "ru"
                ? "Подробнее"
                : "Giňişleýin"}
            </button>

            <button
              class="btn"
              onclick="addToCart(${product.id})"
            >
              ${addText}
            </button>

          </div>

        </div>

      </div>

    </article>
  `;
}


function renderCatalog() {

  const root =
    document.getElementById(
      "catalog"
    );

  if (!products.length) {

    root.innerHTML = `
      <div class="empty">
        ${
          currentLanguage === "ru"
            ? "Каталог пока пуст."
            : "Katalog häzirlikçe boş."
        }
      </div>
    `;

    return;
  }

  root.innerHTML =
    products
      .map(productCard)
      .join("");
}


function renderHomeProducts() {

  const root =
    document.getElementById(
      "homeProducts"
    );

  const featured =
    products.slice(0, 3);

  if (!featured.length) {

    root.innerHTML = `
      <div class="empty">
        ${
          currentLanguage === "ru"
            ? "Товары появятся здесь после добавления владельцем."
            : "Eýesi önüm goşandan soň önümler şu ýerde görkeziler."
        }
      </div>
    `;

    return;
  }

  root.innerHTML =
    featured
      .map(productCard)
      .join("");
}


// ---------------------------------------------------------
// PRODUCT MODAL
// ---------------------------------------------------------

function openProductModal(id) {

  const product =
    products.find(
      item => item.id === id
    );

  if (!product) return;

  document.getElementById(
    "modalProductName"
  ).textContent =
    product.name;

  document.getElementById(
    "modalProductContent"
  ).innerHTML = `
    ${productImage(product)}

    <div style="
      padding-top:18px;
    ">

      ${
        product.category
          ? `
            <div class="product-category">
              ${escapeHtml(product.category)}
            </div>
          `
          : ""
      }

      <div style="
        color:#555b57;
        line-height:1.7;
        margin:12px 0 18px;
      ">
        ${escapeHtml(
          product.description || ""
        )}
      </div>

      <div class="price">
        ${money(product.price)}
      </div>

      <button
        class="btn full"
        style="margin-top:16px"
        onclick="
          addToCart(${product.id});
          closeProductModal();
        "
      >
        ${
          currentLanguage === "ru"
            ? "Добавить в корзину"
            : "Sebede goş"
        }
      </button>

    </div>
  `;

  document
    .getElementById(
      "productModal"
    )
    .classList.add("visible");
}


function closeProductModal(event) {

  if (
    event &&
    event.target !==
      document.getElementById(
        "productModal"
      )
  ) {
    return;
  }

  document
    .getElementById(
      "productModal"
    )
    .classList.remove("visible");
}


// ---------------------------------------------------------
// CART
// ---------------------------------------------------------

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
      quantity:1
    });
  }

  renderCart();

  showPage("cart");
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

  if (!cart.length) {

    root.innerHTML = `
      <div class="empty">
        ${
          currentLanguage === "ru"
            ? "Корзина пока пустая."
            : "Sebet häzirlikçe boş."
        }
      </div>
    `;

    document.getElementById(
      "cartTotal"
    ).textContent =
      "Итого: 0 TMT";

    document.getElementById(
      "checkoutBtn"
    ).disabled = true;

    return;
  }

  let total = 0;

  root.innerHTML =
    cart.map(item => {

      const product =
        products.find(
          p => p.id === item.id
        );

      if (!product) {
        return "";
      }

      const line =
        Number(product.price) *
        item.quantity;

      total += line;

      return `
        <div class="cart-item">

          <div class="cart-row">

            <div>
              <div style="
                font-weight:700;
                margin-bottom:5px;
              ">
                ${escapeHtml(
                  product.name
                )}
              </div>

              <div style="
                color:#747a76;
              ">
                ${money(line)}
              </div>
            </div>

            <div class="qty">

              <button
                onclick="
                  changeQty(
                    ${product.id},
                    -1
                  )
                "
              >
                −
              </button>

              <b>
                ${item.quantity}
              </b>

              <button
                onclick="
                  changeQty(
                    ${product.id},
                    1
                  )
                "
              >
                +
              </button>

            </div>

          </div>

        </div>
      `;

    }).join("");

  document.getElementById(
    "cartTotal"
  ).textContent =
    `${
      currentLanguage === "ru"
        ? "Итого"
        : "Jemi"
    }: ${money(total)}`;

  document.getElementById(
    "checkoutBtn"
  ).disabled = false;
}


// ---------------------------------------------------------
// CHECKOUT
// ---------------------------------------------------------

function showCheckout() {

  if (!cart.length) {
    return;
  }

  document
    .getElementById(
      "checkout"
    )
    .classList.remove(
      "hidden"
    );
}


function hideCheckout() {

  document
    .getElementById(
      "checkout"
    )
    .classList.add(
      "hidden"
    );
}


async function submitOrder() {

  if (!cart.length) {
    return;
  }

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

    items:cart
  };


  if (!payload.customer_name) {

    alert(
      currentLanguage === "ru"
        ? "Укажите имя."
        : "Adyňyzy ýazyň."
    );

    return;
  }


  const result =
    document.getElementById(
      "orderResult"
    );

  result.textContent =
    currentLanguage === "ru"
      ? "Отправляем заказ..."
      : "Sargyt ugradylyar...";


  try {

    const response =
      await apiFetch(
        "/api/orders",
        {
          method:"POST",
          headers:{
            "Content-Type":
              "application/json"
          },
          body:JSON.stringify(
            payload
          )
        }
      );

    const data =
      await response.json();


    if (!response.ok) {

      result.textContent =
        data.error ||
        (
          currentLanguage === "ru"
            ? "Не удалось создать заказ."
            : "Sargyt döredilmedi."
        );

      return;
    }


    result.innerHTML = `
      <div class="notice">
        ${
          currentLanguage === "ru"
            ? `Заказ №${data.order_id} оформлен. Сумма: ${money(data.total)}.`
            : `№${data.order_id} sargyt kabul edildi. Jemi: ${money(data.total)}.`
        }
      </div>
    `;


    if (!data.telegram_sent) {

      result.innerHTML += `
        <div class="notice">
          ${
            currentLanguage === "ru"
              ? "Заказ сохранён, но уведомление владельцу пока не отправлено."
              : "Sargyt saklandy, emma eýesine habar iberilmedi."
          }
        </div>
      `;
    }


    cart = [];

    renderCart();

    hideCheckout();

  } catch (error) {

    result.textContent =
      currentLanguage === "ru"
        ? "Ошибка соединения с сервером."
        : "Serwer bilen baglanyşykda säwlik.";
  }
}


// ---------------------------------------------------------
// ADMIN AUTH
// ---------------------------------------------------------

async function checkAdmin() {

  try {

    const response =
      await apiFetch(
        "/api/admin/check"
      );

    const data =
      await response.json();

    isOwner =
      Boolean(data.admin);


    if (data.user) {

      const user =
        data.user;

      const fullName = [
        user.first_name,
        user.last_name
      ]
        .filter(Boolean)
        .join(" ");

      document.getElementById(
        "profileName"
      ).textContent =
        fullName ||
        user.username ||
        "Пользователь";
    }


    if (isOwner) {

      document
        .getElementById(
          "adminPanel"
        )
        .classList.add(
          "visible"
        );

      document
        .getElementById(
          "adminBadge"
        )
        .classList.remove(
          "hidden"
        );

      document.getElementById(
        "profileStatus"
      ).textContent =
        currentLanguage === "ru"
          ? "Доступ владельца подтверждён."
          : "Eýe ygtyýary tassyklandy.";

      loadOrders("active");

    } else {

      document.getElementById(
        "profileStatus"
      ).textContent =
        currentLanguage === "ru"
          ? "Обычный пользователь."
          : "Adaty ulanyjy.";
    }

  } catch (error) {

    isOwner = false;

  }
}


// ---------------------------------------------------------
// ADMIN TABS
// ---------------------------------------------------------

function showAdminTab(tab) {

  if (!isOwner) return;

  currentAdminTab = tab;

  document
    .getElementById(
      "adminOrders"
    )
    .classList.toggle(
      "hidden",
      tab !== "orders"
    );

  document
    .getElementById(
      "adminProducts"
    )
    .classList.toggle(
      "hidden",
      tab !== "products"
    );

  document
    .getElementById(
      "ordersTab"
    )
    .classList.toggle(
      "active",
      tab === "orders"
    );

  document
    .getElementById(
      "productsTab"
    )
    .classList.toggle(
      "active",
      tab === "products"
    );

  if (tab === "products") {
    renderAdminProducts();
  }
}


// ---------------------------------------------------------
// ADMIN ORDERS
// ---------------------------------------------------------

async function loadOrders(
  view = "active"
) {

  if (!isOwner) return;

  currentOrderView = view;

  const root =
    document.getElementById(
      "ordersList"
    );

  root.innerHTML =
    currentLanguage === "ru"
      ? "Загрузка заказов..."
      : "Sargytlar ýüklenýär...";


  try {

    const response =
      await apiFetch(
        `/api/orders?view=${encodeURIComponent(view)}`
      );

    const data =
      await response.json();


    if (!response.ok) {

      root.innerHTML = `
        <div class="empty">
          ${escapeHtml(
            data.error ||
            "Ошибка"
          )}
        </div>
      `;

      return;
    }


    const orders =
      data.orders || [];


    if (!orders.length) {

      root.innerHTML = `
        <div class="empty">
          ${
            view === "archive"
              ? (
                  currentLanguage === "ru"
                    ? "Архив пока пуст."
                    : "Arhiw häzirlikçe boş."
                )
              : (
                  currentLanguage === "ru"
                    ? "Активных заказов нет."
                    : "Işjeň sargyt ýok."
                )
          }
        </div>
      `;

      return;
    }


    root.innerHTML =
      orders.map(renderOrder)
        .join("");

  } catch (error) {

    root.innerHTML = `
      <div class="empty">
        ${
          currentLanguage === "ru"
            ? "Не удалось загрузить заказы."
            : "Sargytlary ýükläp bolmady."
        }
      </div>
    `;
  }
}


function renderOrder(order) {

  const items =
    Array.isArray(order.items)
      ? order.items
      : [];


  const itemsHtml =
    items.map(item => `
      <div>
        ${escapeHtml(
          item.name
        )}
        × ${item.quantity}
        — ${money(
          item.line_total
        )}
      </div>
    `).join("");


  const statusText = {
    new:
      currentLanguage === "ru"
        ? "Новый"
        : "Täze",

    processing:
      currentLanguage === "ru"
        ? "В работе"
        : "Işlenýär",

    ready:
      currentLanguage === "ru"
        ? "Готов"
        : "Taýýar",

    completed:
      currentLanguage === "ru"
        ? "Завершён"
        : "Tamamlandy",

    cancelled:
      currentLanguage === "ru"
        ? "Отменён"
        : "Ýatyryldy"
  };


  return `
    <div class="order">

      <div class="order-top">

        <div>
          <div class="order-id">
            №${order.id}
          </div>

          <div style="
            color:#747a76;
            font-size:13px;
            margin-top:4px;
          ">
            ${escapeHtml(
              order.customer_name
            )}
          </div>
        </div>

        <div class="status">
          ${
            statusText[
              order.status
            ] ||
            order.status
          }
        </div>

      </div>


      <div style="
        line-height:1.7;
        font-size:14px;
      ">

        <div>
          ${
            escapeHtml(
              order.phone ||
              (
                currentLanguage === "ru"
                  ? "Телефон не указан"
                  : "Telefon görkezilmedi"
              )
            )
          }
        </div>

        <div>
          ${
            escapeHtml(
              order.city || ""
            )
          }
        </div>

        <div>
          ${
            escapeHtml(
              order.delivery_method
            )
          }
        </div>

        <div>
          ${
            escapeHtml(
              order.address || ""
            )
          }
        </div>

      </div>


      <div class="order-items">
        ${itemsHtml}
      </div>


      <div style="
        font-weight:700;
        font-size:19px;
        margin:12px 0;
      ">
        ${money(order.total)}
      </div>


      ${
        order.comment
          ? `
            <div style="
              color:#747a76;
              font-size:13px;
              margin-bottom:12px;
            ">
              ${escapeHtml(
                order.comment
              )}
            </div>
          `
          : ""
      }


      ${
        currentOrderView === "active"
          ? `
            <select
              onchange="
                changeOrderStatus(
                  ${order.id},
                  this.value
                )
              "
            >

              <option
                value="new"
                ${order.status === "new"
                  ? "selected"
                  : ""}
              >
                ${
                  currentLanguage === "ru"
                    ? "Новый"
                    : "Täze"
                }
              </option>

              <option
                value="processing"
                ${order.status === "processing"
                  ? "selected"
                  : ""}
              >
                ${
                  currentLanguage === "ru"
                    ? "В работе"
                    : "Işlenýär"
                }
              </option>

              <option
                value="ready"
                ${order.status === "ready"
                  ? "selected"
                  : ""}
              >
                ${
                  currentLanguage === "ru"
                    ? "Готов"
                    : "Taýýar"
                }
              </option>

              <option
                value="completed"
              >
                ${
                  currentLanguage === "ru"
                    ? "Завершён"
                    : "Tamamlandy"
                }
              </option>

              <option
                value="cancelled"
              >
                ${
                  currentLanguage === "ru"
                    ? "Отменён"
                    : "Ýatyryldy"
                }
              </option>

            </select>
          `
          : ""
      }

    </div>
  `;
}


async function changeOrderStatus(
  orderId,
  status
) {

  try {

    const response =
      await apiFetch(
        `/api/orders/${orderId}/status`,
        {
          method:"PATCH",
          headers:{
            "Content-Type":
              "application/json"
          },
          body:JSON.stringify({
            status
          })
        }
      );


    const data =
      await response.json();


    if (!response.ok) {

      alert(
        data.error ||
        "Ошибка"
      );

      return;
    }


    await loadOrders(
      currentOrderView
    );

  } catch (error) {

    alert(
      currentLanguage === "ru"
        ? "Ошибка соединения."
        : "Baglanyşyk säwligi."
    );
  }
}


// ---------------------------------------------------------
// ADMIN PRODUCTS
// ---------------------------------------------------------

function renderAdminProducts() {

  if (!isOwner) return;

  const root =
    document.getElementById(
      "adminProductList"
    );

  if (!products.length) {

    root.innerHTML = `
      <div class="empty">
        ${
          currentLanguage === "ru"
            ? "Товаров пока нет."
            : "Häzirlikçe önüm ýok."
        }
      </div>
    `;

    return;
  }


  root.innerHTML =
    products.map(product => `

      <div class="admin-box">

        <div class="admin-product">

          ${
            product.image_url
              ? `
                <img
                  class="admin-thumb"
                  src="${escapeHtml(
                    product.image_url
                  )}"
                >
              `
              : `
                <div class="admin-thumb"></div>
              `
          }

          <div>

            <div style="
              font-weight:700;
            ">
              ${escapeHtml(
                product.name
              )}
            </div>

            <div style="
              color:#747a76;
              margin-top:4px;
              font-size:13px;
            ">
              ${money(
                product.price
              )}
            </div>

          </div>

        </div>


        <div
          class="admin-actions"
          style="
            margin-top:10px;
          "
        >

          <button
            onclick="
              editProduct(
                ${product.id}
              )
            "
          >
            ${
              currentLanguage === "ru"
                ? "Изменить"
                : "Üýtget"
            }
          </button>

          <button
            onclick="
              deleteProduct(
                ${product.id}
              )
            "
            style="
              color:#9f3030;
            "
          >
            ${
              currentLanguage === "ru"
                ? "Удалить"
                : "Öçür"
            }
          </button>

        </div>

      </div>

    `).join("");
}


function resetProductForm() {

  document.getElementById(
    "editingProductId"
  ).value = "";

  document.getElementById(
    "productName"
  ).value = "";

  document.getElementById(
    "productCategory"
  ).value = "";

  document.getElementById(
    "productPrice"
  ).value = "";

  document.getElementById(
    "productDescription"
  ).value = "";

  document.getElementById(
    "productImage"
  ).value = "";

  document.getElementById(
    "productFormTitle"
  ).textContent =
    currentLanguage === "ru"
      ? "Добавить товар"
      : "Önüm goş";

  document.getElementById(
    "productFormResult"
  ).innerHTML = "";
}


function editProduct(id) {

  const product =
    products.find(
      p => p.id === id
    );

  if (!product) return;


  document.getElementById(
    "editingProductId"
  ).value =
    product.id;

  document.getElementById(
    "productName"
  ).value =
    product.name;

  document.getElementById(
    "productCategory"
  ).value =
    product.category || "";

  document.getElementById(
    "productPrice"
  ).value =
    product.price;

  document.getElementById(
    "productDescription"
  ).value =
    product.description || "";

  document.getElementById(
    "productImage"
  ).value = "";

  document.getElementById(
    "productFormTitle"
  ).textContent =
    currentLanguage === "ru"
      ? "Изменить товар"
      : "Önümi üýtget";


  window.scrollTo({
    top:0,
    behavior:"smooth"
  });
}


// ---------------------------------------------------------
// IMAGE COMPRESSION
// ---------------------------------------------------------

async function compressImage(
  file
) {

  if (!file) {
    return null;
  }

  if (
    !file.type.startsWith(
      "image/"
    )
  ) {
    throw new Error(
      currentLanguage === "ru"
        ? "Выберите изображение."
        : "Surat saýlaň."
    );
  }


  const image =
    await new Promise(
      (resolve, reject) => {

        const img =
          new Image();

        img.onload = () =>
          resolve(img);

        img.onerror = () =>
          reject(
            new Error(
              "IMAGE_ERROR"
            )
          );

        img.src =
          URL.createObjectURL(
            file
          );
      }
    );


  const maxSide = 1600;

  let width =
    image.naturalWidth;

  let height =
    image.naturalHeight;


  if (
    width > maxSide ||
    height > maxSide
  ) {

    const scale =
      Math.min(
        maxSide / width,
        maxSide / height
      );

    width =
      Math.round(
        width * scale
      );

    height =
      Math.round(
        height * scale
      );
  }


  const canvas =
    document.createElement(
      "canvas"
    );

  canvas.width = width;
  canvas.height = height;


  const context =
    canvas.getContext(
      "2d"
    );

  context.drawImage(
    image,
    0,
    0,
    width,
    height
  );


  const blob =
    await new Promise(
      resolve =>
        canvas.toBlob(
          resolve,
          "image/jpeg",
          0.82
        )
    );


  return new File(
    [blob],
    "product.jpg",
    {
      type:"image/jpeg"
    }
  );
}


// ---------------------------------------------------------
// SAVE PRODUCT
// ---------------------------------------------------------

async function saveProduct() {

  if (!isOwner) {
    return;
  }


  const name =
    document.getElementById(
      "productName"
    ).value.trim();

  const category =
    document.getElementById(
      "productCategory"
    ).value.trim();

  const price =
    document.getElementById(
      "productPrice"
    ).value;

  const description =
    document.getElementById(
      "productDescription"
    ).value.trim();

  const editingId =
    document.getElementById(
      "editingProductId"
    ).value;


  if (!name || !price) {

    alert(
      currentLanguage === "ru"
        ? "Заполните название и цену."
        : "Adyny we bahany dolduryň."
    );

    return;
  }


  const result =
    document.getElementById(
      "productFormResult"
    );

  result.textContent =
    currentLanguage === "ru"
      ? "Сохраняем..."
      : "Ýatda saklanýar...";


  try {

    const formData =
      new FormData();

    formData.append(
      "name",
      name
    );

    formData.append(
      "category",
      category
    );

    formData.append(
      "price",
      price
    );

    formData.append(
      "description",
      description
    );


    const file =
      document.getElementById(
        "productImage"
      ).files[0];


    if (file) {

      const compressed =
        await compressImage(
          file
        );

      formData.append(
        "image",
        compressed
      );
    }


    const url =
      editingId
        ? `/api/products/${editingId}`
        : "/api/products";


    const method =
      editingId
        ? "PUT"
        : "POST";


    const response =
      await apiFetch(
        url,
        {
          method,
          body:formData
        }
      );


    const data =
      await response.json();


    if (!response.ok) {

      result.textContent =
        data.error ||
        (
          currentLanguage === "ru"
            ? "Не удалось сохранить товар."
            : "Önümi saklap bolmady."
        );

      return;
    }


    result.innerHTML = `
      <div class="notice">
        ${
          currentLanguage === "ru"
            ? "Товар сохранён."
            : "Önüm saklandy."
        }
      </div>
    `;


    resetProductForm();

    await loadProducts();

  } catch (error) {

    result.textContent =
      error.message ||
      (
        currentLanguage === "ru"
          ? "Ошибка сохранения."
          : "Saklamakda säwlik."
      );
  }
}


// ---------------------------------------------------------
// DELETE PRODUCT
// ---------------------------------------------------------

async function deleteProduct(id) {

  if (!isOwner) return;


  const confirmed =
    confirm(
      currentLanguage === "ru"
        ? "Удалить этот товар?"
        : "Bu önümi öçürmelimi?"
    );


  if (!confirmed) {
    return;
  }


  try {

    const response =
      await apiFetch(
        `/api/products/${id}`,
        {
          method:"DELETE"
        }
      );


    const data =
      await response.json();


    if (!response.ok) {

      alert(
        data.error ||
        "Ошибка"
      );

      return;
    }


    await loadProducts();

  } catch (error) {

    alert(
      currentLanguage === "ru"
        ? "Ошибка соединения."
        : "Baglanyşyk säwligi."
    );
  }
}


// ---------------------------------------------------------
// INIT
// ---------------------------------------------------------

async function init() {

  setupTelegram();

  setLanguage(
    currentLanguage
  );

  await loadProducts();

  await checkAdmin();

  updatePlaceholders();
}


init();
