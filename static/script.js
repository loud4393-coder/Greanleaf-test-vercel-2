let products = [];
let cart = [];
let currentCategory = "Все";
let currentLanguage = "ru";
let adminMode = false;
let currentAdminSection = "orders";
let currentOrderView = "active";
let editingProductId = null;
let modalProductId = null;


/* =========================================================
   TELEGRAM
========================================================= */

const tg =
  window.Telegram &&
  window.Telegram.WebApp
    ? window.Telegram.WebApp
    : null;

if (tg) {
  tg.ready();
  tg.expand();
}


/* =========================================================
   INIT DATA
========================================================= */

async function init() {
  await loadProducts();
  await checkAdmin();

  renderCart();
}

init().catch(() => {
  showToast("Не удалось загрузить приложение");
});


/* =========================================================
   NAVIGATION
========================================================= */

function showPage(page) {
  document
    .querySelectorAll(".page")
    .forEach(el => {
      el.classList.remove("active");
    });

  const target = document.getElementById(
    `page-${page}`
  );

  if (target) {
    target.classList.add("active");
  }

  document
    .querySelectorAll(".nav-btn")
    .forEach(btn => {
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


/* =========================================================
   LANGUAGE
========================================================= */

function setLanguage(language) {
  currentLanguage = language;

  document
    .getElementById("langRU")
    .classList.toggle(
      "active",
      language === "ru"
    );

  document
    .getElementById("langTM")
    .classList.toggle(
      "active",
      language === "tm"
    );

  /*
    Сейчас структура приложения остаётся
    одинаковой. Переключатель уже готов
    для следующего слоя локализации.
  */

  showToast(
    language === "ru"
      ? "Русский язык"
      : "Türkmen dili"
  );
}


/* =========================================================
   PRODUCTS
========================================================= */

async function loadProducts() {
  const response = await fetch(
    "/api/products"
  );

  if (!response.ok) {
    throw new Error(
      "Products request failed"
    );
  }

  const data = await response.json();

  products = data.products || [];

  renderCategories();
  renderCatalog();
  renderHomeProducts();
  renderReviewProductSelect();
  renderAdminProducts();
  renderAdminReviews();
}


function renderCategories() {
  const root = document.getElementById(
    "categories"
  );

  const categories = [
    "Все",
    ...new Set(
      products
        .map(p => p.category)
        .filter(Boolean)
    )
  ];

  if (
    currentCategory !== "Все" &&
    !categories.includes(
      currentCategory
    )
  ) {
    currentCategory = "Все";
  }

  root.innerHTML = categories
    .map(category => `
      <button
        class="category ${
          category === currentCategory
            ? "active"
            : ""
        }"
        onclick="selectCategory('${escapeJs(category)}')"
      >
        ${escapeHtml(category)}
      </button>
    `)
    .join("");
}


function selectCategory(category) {
  currentCategory = category;

  renderCategories();
  renderCatalog();
}


function filteredProducts() {
  if (currentCategory === "Все") {
    return products;
  }

  return products.filter(
    product =>
      product.category ===
      currentCategory
  );
}


function renderCatalog() {
  const root = document.getElementById(
    "catalogProducts"
  );

  const list = filteredProducts();

  document.getElementById(
    "catalogCount"
  ).textContent =
    `${list.length} товар${plural(
      list.length
    )}`;

  if (!list.length) {
    root.innerHTML = `
      <div
        class="empty"
        style="grid-column:1/-1"
      >
        Каталог пока пуст.
      </div>
    `;

    return;
  }

  root.innerHTML = list
    .map(renderProductCard)
    .join("");
}


function renderHomeProducts() {
  const root = document.getElementById(
    "homeProducts"
  );

  const list = products.slice(0, 4);

  document.getElementById(
    "homeCount"
  ).textContent =
    `${products.length} товар${plural(
      products.length
    )}`;

  if (!list.length) {
    root.innerHTML = `
      <div class="empty">
        Каталог пока пуст.
      </div>
    `;

    return;
  }

  root.innerHTML = `
    <div class="products">
      ${list.map(renderProductCard).join("")}
    </div>
  `;
}


function renderProductCard(product) {
  const image = product.image_url
    ? `
      <img
        src="${escapeHtml(product.image_url)}"
        alt="${escapeHtml(product.name)}"
        loading="lazy"
      >
    `
    : `
      <div class="product-placeholder">
        GREENLEAF
      </div>
    `;

  const rating =
    product.review_count > 0
      ? `
        <div class="rating">
          ${Number(product.rating).toFixed(1)}
          · ${product.review_count} отзыв${plural(
            product.review_count
          )}
        </div>
      `
      : "";

  return `
    <article
      class="product"
      onclick="openProduct(${product.id})"
    >

      <div class="product-image">
        ${image}
      </div>

      <div class="product-body">

        <div class="product-category">
          ${escapeHtml(
            product.category ||
            "Greenleaf"
          )}
        </div>

        <div class="product-name">
          ${escapeHtml(product.name)}
        </div>

        <div class="product-description">
          ${escapeHtml(
            product.description || ""
          )}
        </div>

        ${rating}

        <div class="product-bottom">

          <div class="product-price">
            ${money(product.price)}
          </div>

          <button
            class="small-button"
            onclick="event.stopPropagation();addToCart(${product.id})"
          >
            В корзину
          </button>

        </div>

      </div>

    </article>
  `;
}


/* =========================================================
   PRODUCT MODAL
========================================================= */

function openProduct(productId) {
  const product = products.find(
    p => p.id === productId
  );

  if (!product) {
    return;
  }

  modalProductId = productId;

  document.getElementById(
    "modalProductName"
  ).textContent = product.name;

  const imageRoot = document.getElementById(
    "modalProductImage"
  );

  imageRoot.innerHTML =
    product.image_url
      ? `
        <img
          src="${escapeHtml(
            product.image_url
          )}"
          alt="${escapeHtml(
            product.name
          )}"
        >
      `
      : `
        <div class="product-placeholder">
          GREENLEAF
        </div>
      `;

  document.getElementById(
    "modalProductInfo"
  ).innerHTML = `
    <div class="product-category">
      ${escapeHtml(
        product.category || "Greenleaf"
      )}
    </div>

    <p
      style="
        color:#777d79;
        line-height:1.6;
        font-size:14px
      "
    >
      ${escapeHtml(
        product.description || ""
      )}
    </p>

    <div
      style="
        font-size:22px;
        font-weight:700;
        margin:14px 0 18px
      "
    >
      ${money(product.price)}
    </div>
  `;

  renderModalReviews(product);

  document
    .getElementById("productModal")
    .classList.add("open");
}


function closeProductModal() {
  document
    .getElementById("productModal")
    .classList.remove("open");
}


function closeModal(event) {
  if (
    event.target.id ===
    "productModal"
  ) {
    closeProductModal();
  }
}


function addModalProductToCart() {
  if (!modalProductId) {
    return;
  }

  addToCart(modalProductId);
  closeProductModal();
}


function renderModalReviews(product) {
  const root = document.getElementById(
    "modalReviews"
  );

  const reviews =
    product.reviews || [];

  if (!reviews.length) {
    root.innerHTML = `
      <div class="muted">
        Отзывов пока нет.
      </div>
    `;

    return;
  }

  root.innerHTML = reviews
    .map(review => `
      <div class="review">

        <div class="review-author">
          ${escapeHtml(review.author)}
        </div>

        <div class="review-stars">
          ${"•".repeat(
            Number(review.rating)
          )}
        </div>

        <div class="review-text">
          ${escapeHtml(review.text)}
        </div>

      </div>
    `)
    .join("");
}


/* =========================================================
   CART
========================================================= */

function addToCart(productId) {
  const existing = cart.find(
    item => item.id === productId
  );

  if (existing) {
    existing.quantity += 1;
  } else {
    cart.push({
      id: productId,
      quantity: 1,
    });
  }

  renderCart();
  showToast("Товар добавлен");
}


function changeQty(
  productId,
  delta
) {
  const item = cart.find(
    x => x.id === productId
  );

  if (!item) {
    return;
  }

  item.quantity += delta;

  if (item.quantity <= 0) {
    cart = cart.filter(
      x => x.id !== productId
    );
  }

  renderCart();
}


function getCartTotal() {
  return cart.reduce(
    (sum, item) => {
      const product = products.find(
        p => p.id === item.id
      );

      if (!product) {
        return sum;
      }

      return (
        sum +
        Number(product.price) *
        item.quantity
      );
    },
    0
  );
}


function renderCart() {
  const root = document.getElementById(
    "cartPanel"
  );

  const count = cart.reduce(
    (sum, item) =>
      sum + item.quantity,
    0
  );

  document.getElementById(
    "cartHeaderCount"
  ).textContent =
    count
      ? `${count} шт.`
      : "Пусто";

  const badge =
    document.getElementById(
      "navCartBadge"
    );

  if (count) {
    badge.textContent = count;
    badge.classList.remove(
      "hidden"
    );
  } else {
    badge.classList.add(
      "hidden"
    );
  }

  if (!cart.length) {
    root.innerHTML = `
      <div class="empty">
        В корзине пока ничего нет.
      </div>
    `;

    document
      .getElementById("checkoutPanel")
      .classList.add("hidden");

    return;
  }

  let total = 0;

  root.innerHTML = cart
    .map(item => {

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

          <div class="row">

            <div>
              <strong>
                ${escapeHtml(
                  product.name
                )}
              </strong>

              <div
                class="muted"
                style="font-size:11px;margin-top:4px"
              >
                ${money(line)}
              </div>
            </div>

            <div class="qty">

              <button
                onclick="changeQty(${product.id},-1)"
              >
                −
              </button>

              <strong>
                ${item.quantity}
              </strong>

              <button
                onclick="changeQty(${product.id},1)"
              >
                +
              </button>

            </div>

          </div>

        </div>
      `;
    })
    .join("");

  root.innerHTML += `
    <div class="total">
      <span>Итого</span>
      <span>${money(total)}</span>
    </div>

    <div style="height:12px"></div>

    <button
      class="primary"
      onclick="showCheckout()"
    >
      Оформить заказ
    </button>
  `;
}


function showCheckout() {
  if (!cart.length) {
    return;
  }

  document
    .getElementById(
      "checkoutPanel"
    )
    .classList.remove(
      "hidden"
    );

  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: "smooth"
  });
}


/* =========================================================
   ORDER
========================================================= */

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

    items: cart,
  };

  if (!payload.customer_name) {
    showToast(
      "Укажите имя"
    );

    return;
  }

  const result =
    document.getElementById(
      "orderResult"
    );

  result.innerHTML = `
    <div class="notice">
      Заказ отправляется...
    </div>
  `;

  try {

    const response =
      await fetch(
        "/api/orders",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json"
          },
          body:
            JSON.stringify(payload)
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      result.innerHTML = `
        <div class="notice">
          ${escapeHtml(
            data.error ||
            "Не удалось создать заказ."
          )}
        </div>
      `;

      return;
    }

    result.innerHTML = `
      <div class="notice">
        Заказ №${data.order_id}
        успешно оформлен.
        Сумма:
        ${money(data.total)}.
      </div>
    `;

    if (!data.telegram_sent) {
      result.innerHTML += `
        <div
          class="notice"
          style="background:#faf3e8"
        >
          Заказ сохранён, но уведомление
          Telegram пока не отправлено.
        </div>
      `;
    }

    cart = [];

    renderCart();

    showToast(
      `Заказ №${data.order_id} создан`
    );

  } catch (error) {

    result.innerHTML = `
      <div class="notice">
        Ошибка соединения с сервером.
      </div>
    `;
  }
}


/* =========================================================
   ADMIN
========================================================= */

async function checkAdmin() {
  if (!tg) {
    return;
  }

  const initData =
    tg.initData || "";

  if (!initData) {
    return;
  }

  try {

    const response =
      await fetch(
        "/api/admin/check",
        {
          headers: {
            "X-Telegram-Init-Data":
              initData
          }
        }
      );

    const data =
      await response.json();

    adminMode =
      Boolean(data.admin);

    if (adminMode) {
      document
        .getElementById(
          "adminPanel"
        )
        .classList.remove(
          "hidden"
        );

      const user =
        tg.initDataUnsafe &&
        tg.initDataUnsafe.user;

      if (user) {
        document.getElementById(
          "profileInfo"
        ).innerHTML = `
          <h2>
            ${escapeHtml(
              user.first_name ||
              "Владелец"
            )}
          </h2>

          <div class="muted">
            Панель владельца Greenleaf
          </div>
        `;
      }

      await loadOrders(
        "active"
      );
    }

  } catch (error) {
    adminMode = false;
  }
}


function adminHeaders() {
  const headers = {};

  if (tg && tg.initData) {
    headers[
      "X-Telegram-Init-Data"
    ] = tg.initData;
  }

  return headers;
}


function showAdminSection(section) {
  if (!adminMode) {
    return;
  }

  currentAdminSection =
    section;

  document
    .getElementById(
      "adminOrdersSection"
    )
    .classList.toggle(
      "hidden",
      section !== "orders"
    );

  document
    .getElementById(
      "adminProductsSection"
    )
    .classList.toggle(
      "hidden",
      section !== "products"
    );

  document
    .getElementById(
      "adminReviewsSection"
    )
    .classList.toggle(
      "hidden",
      section !== "reviews"
    );

  document
    .getElementById(
      "adminOrdersTab"
    )
    .classList.toggle(
      "active",
      section === "orders"
    );

  document
    .getElementById(
      "adminProductsTab"
    )
    .classList.toggle(
      "active",
      section === "products"
    );

  document
    .getElementById(
      "adminReviewsTab"
    )
    .classList.toggle(
      "active",
      section === "reviews"
    );

  if (section === "orders") {
    loadOrders(
      currentOrderView
    );
  }

  if (section === "products") {
    renderAdminProducts();
  }

  if (section === "reviews") {
    renderAdminReviews();
  }
}


/* =========================================================
   ADMIN ORDERS
========================================================= */

async function loadOrders(view) {
  if (!adminMode) {
    return;
  }

  currentOrderView = view;

  document
    .getElementById(
      "activeOrdersTab"
    )
    .classList.toggle(
      "active",
      view === "active"
    );

  document
    .getElementById(
      "archiveOrdersTab"
    )
    .classList.toggle(
      "active",
      view === "archive"
    );

  const root =
    document.getElementById(
      "ordersList"
    );

  root.innerHTML = `
    <div class="empty">
      Загрузка...
    </div>
  `;

  try {

    const response =
      await fetch(
        `/api/orders?view=${view}`,
        {
          headers:
            adminHeaders()
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.error ||
        "Ошибка"
      );
    }

    renderOrders(
      data.orders || []
    );

  } catch (error) {

    root.innerHTML = `
      <div class="empty">
        ${escapeHtml(
          error.message ||
          "Не удалось загрузить заказы."
        )}
      </div>
    `;
  }
}


function renderOrders(orders) {
  const root =
    document.getElementById(
      "ordersList"
    );

  if (!orders.length) {
    root.innerHTML = `
      <div class="empty">
        ${
          currentOrderView === "archive"
            ? "Архив пока пуст."
            : "Активных заказов нет."
        }
      </div>
    `;

    return;
  }

  root.innerHTML = orders
    .map(order => {

      const items =
        Array.isArray(
          order.items
        )
          ? order.items
          : [];

      return `
        <div class="order">

          <div class="row">

            <div>
              <div class="order-number">
                Заказ №${order.id}
              </div>

              <div class="order-meta">
                ${escapeHtml(
                  order.customer_name
                )}
                ·
                ${escapeHtml(
                  order.phone || ""
                )}
              </div>
            </div>

            <strong>
              ${money(order.total)}
            </strong>

          </div>

          <div class="order-meta">
            Город:
            ${escapeHtml(
              order.city || "—"
            )}
            <br>

            Получение:
            ${escapeHtml(
              order.delivery_method || "—"
            )}
            <br>

            Адрес:
            ${escapeHtml(
              order.address || "—"
            )}
          </div>

          <div class="order-items">

            ${items
              .map(item => `
                <div>
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
              .join("")}

          </div>

          <div class="order-meta">
            Комментарий:
            ${escapeHtml(
              order.comment || "нет"
            )}
          </div>

          <div
            class="order-actions"
            style="margin-top:12px"
          >

            <select
              onchange="changeOrderStatus(
                ${order.id},
                this.value
              )"
            >

              ${statusOption(
                "new",
                order.status,
                "Новый"
              )}

              ${statusOption(
                "processing",
                order.status,
                "В обработке"
              )}

              ${statusOption(
                "ready",
                order.status,
                "Готов"
              )}

              ${statusOption(
                "completed",
                order.status,
                "Завершён"
              )}

              ${statusOption(
                "cancelled",
                order.status,
                "Отменён"
              )}

            </select>

          </div>

        </div>
      `;
    })
    .join("");
}


function statusOption(
  value,
  current,
  label
) {
  return `
    <option
      value="${value}"
      ${value === current ? "selected" : ""}
    >
      ${label}
    </option>
  `;
}


async function changeOrderStatus(
  orderId,
  status
) {
  try {

    const response =
      await fetch(
        `/api/orders/${orderId}/status`,
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
            ...adminHeaders()
          },
          body:
            JSON.stringify({
              status
            })
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.error ||
        "Не удалось изменить статус."
      );
    }

    showToast(
      "Статус заказа обновлён"
    );

    await loadOrders(
      currentOrderView
    );

  } catch (error) {

    showToast(
      error.message
    );
  }
}


/* =========================================================
   ADMIN PRODUCTS
========================================================= */

function renderAdminProducts() {
  const root =
    document.getElementById(
      "adminProductsList"
    );

  if (!root) {
    return;
  }

  if (!products.length) {
    root.innerHTML = `
      <div class="empty">
        Товаров пока нет.
      </div>
    `;

    return;
  }

  root.innerHTML = `
    <h3>
      Каталог
    </h3>

    ${products.map(product => `
      <div class="admin-product">

        <div class="admin-thumb">

          ${
            product.image_url
              ? `
                <img
                  src="${escapeHtml(
                    product.image_url
                  )}"
                  alt=""
                >
              `
              : ""
          }

        </div>

        <div class="admin-product-main">

          <div class="admin-product-name">
            ${escapeHtml(
              product.name
            )}
          </div>

          <div class="admin-product-price">
            ${money(product.price)}
            ${
              product.category
                ? " · " +
                  escapeHtml(
                    product.category
                  )
                : ""
            }
          </div>

          <div
            class="admin-product-actions"
          >

            <button
              class="secondary"
              onclick="editProduct(
                ${product.id}
              )"
            >
              Изменить
            </button>

            <button
              class="danger"
              onclick="removeProduct(
                ${product.id}
              )"
            >
              Удалить
            </button>

          </div>

        </div>

      </div>
    `).join("")}
  `;
}


function resetProductForm() {
  editingProductId = null;

  document.getElementById(
    "editProductId"
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
    "Новый товар";

  document.getElementById(
    "productFormResult"
  ).textContent = "";
}


function editProduct(productId) {
  const product =
    products.find(
      p => p.id === productId
    );

  if (!product) {
    return;
  }

  editingProductId =
    productId;

  document.getElementById(
    "editProductId"
  ).value =
    productId;

  document.getElementById(
    "productName"
  ).value =
    product.name || "";

  document.getElementById(
    "productCategory"
  ).value =
    product.category || "";

  document.getElementById(
    "productPrice"
  ).value =
    product.price || "";

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
    "Редактирование товара";

  document
    .getElementById(
      "adminProductsSection"
    )
    .scrollIntoView({
      behavior: "smooth"
    });
}


async function compressImage(
  file
) {
  if (!file) {
    return null;
  }

  const image =
    await new Promise(
      (resolve, reject) => {

        const img =
          new Image();

        img.onload =
          () => resolve(img);

        img.onerror =
          reject;

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

    const ratio =
      Math.min(
        maxSide / width,
        maxSide / height
      );

    width =
      Math.round(
        width * ratio
      );

    height =
      Math.round(
        height * ratio
      );
  }

  const canvas =
    document.createElement(
      "canvas"
    );

  canvas.width =
    width;

  canvas.height =
    height;

  const ctx =
    canvas.getContext(
      "2d"
    );

  ctx.drawImage(
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
      type:
        "image/jpeg"
    }
  );
}


async function saveProduct() {
  if (!adminMode) {
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

  const imageInput =
    document.getElementById(
      "productImage"
    );

  if (!name || price === "") {
    showToast(
      "Введите название и цену"
    );

    return;
  }

  const form =
    new FormData();

  form.append(
    "name",
    name
  );

  form.append(
    "category",
    category
  );

  form.append(
    "price",
    price
  );

  form.append(
    "description",
    description
  );

  if (
    imageInput.files &&
    imageInput.files[0]
  ) {

    const compressed =
      await compressImage(
        imageInput.files[0]
      );

    if (compressed) {
      form.append(
        "image",
        compressed
      );
    }
  }

  const method =
    editingProductId
      ? "PUT"
      : "POST";

  const url =
    editingProductId
      ? `/api/products/${editingProductId}`
      : "/api/products";

  const result =
    document.getElementById(
      "productFormResult"
    );

  result.textContent =
    "Сохраняем...";

  try {

    const response =
      await fetch(
        url,
        {
          method,
          headers:
            adminHeaders(),
          body: form
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.error ||
        "Не удалось сохранить товар."
      );
    }

    result.textContent =
      "Товар сохранён.";

    resetProductForm();

    await loadProducts();

    showToast(
      "Товар сохранён"
    );

  } catch (error) {

    result.textContent =
      error.message;
  }
}


async function removeProduct(
  productId
) {
  if (!adminMode) {
    return;
  }

  const product =
    products.find(
      p => p.id === productId
    );

  if (!product) {
    return;
  }

  const confirmed =
    confirm(
      `Удалить товар «${product.name}»?`
    );

  if (!confirmed) {
    return;
  }

  try {

    const response =
      await fetch(
        `/api/products/${productId}`,
        {
          method: "DELETE",
          headers:
            adminHeaders()
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.error ||
        "Не удалось удалить товар."
      );
    }

    cart =
      cart.filter(
        item =>
          item.id !== productId
      );

    await loadProducts();

    renderCart();

    showToast(
      "Товар удалён"
    );

  } catch (error) {

    showToast(
      error.message
    );
  }
}


/* =========================================================
   ADMIN REVIEWS
========================================================= */

function renderReviewProductSelect() {
  const select =
    document.getElementById(
      "reviewProduct"
    );

  if (!select) {
    return;
  }

  select.innerHTML =
    products.map(product => `
      <option value="${product.id}">
        ${escapeHtml(
          product.name
        )}
      </option>
    `).join("");
}


function renderAdminReviews() {
  const root =
    document.getElementById(
      "adminReviewsList"
    );

  if (!root) {
    return;
  }

  const reviews =
    products.flatMap(
      product =>
        (product.reviews || [])
          .map(review => ({
            ...review,
            productName:
              product.name
          }))
    );

  if (!reviews.length) {
    root.innerHTML = `
      <div class="empty">
        Отзывов пока нет.
      </div>
    `;

    return;
  }

  root.innerHTML = `
    <h3>
      Отзывы
    </h3>

    ${reviews.map(review => `
      <div class="review">

        <div class="row">

          <div>
            <div class="review-author">
              ${escapeHtml(
                review.author
              )}
            </div>

            <div class="muted">
              ${escapeHtml(
                review.productName
              )}
            </div>
          </div>

          <button
            class="danger"
            onclick="removeReview(
              ${review.id}
            )"
          >
            Удалить
          </button>

        </div>

        <div class="review-stars">
          ${"•".repeat(
            Number(review.rating)
          )}
        </div>

        <div class="review-text">
          ${escapeHtml(
            review.text
          )}
        </div>

      </div>
    `).join("")}
  `;
}


async function saveReview() {
  const productId =
    document.getElementById(
      "reviewProduct"
    ).value;

  const author =
    document.getElementById(
      "reviewAuthor"
    ).value.trim();

  const rating =
    document.getElementById(
      "reviewRating"
    ).value;

  const text =
    document.getElementById(
      "reviewText"
    ).value.trim();

  if (!author || !text) {
    showToast(
      "Заполните автора и текст"
    );

    return;
  }

  try {

    const response =
      await fetch(
        "/api/reviews",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
            ...adminHeaders()
          },
          body:
            JSON.stringify({
              product_id:
                Number(productId),
              author,
              rating:
                Number(rating),
              text
            })
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.error ||
        "Не удалось добавить отзыв."
      );
    }

    document.getElementById(
      "reviewAuthor"
    ).value = "";

    document.getElementById(
      "reviewText"
    ).value = "";

    await loadProducts();

    showToast(
      "Отзыв добавлен"
    );

  } catch (error) {

    showToast(
      error.message
    );
  }
}


async function removeReview(
  reviewId
) {
  if (!adminMode) {
    return;
  }

  if (
    !confirm(
      "Удалить этот отзыв?"
    )
  ) {
    return;
  }

  try {

    const response =
      await fetch(
        `/api/reviews/${reviewId}`,
        {
          method: "DELETE",
          headers:
            adminHeaders()
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.error ||
        "Не удалось удалить отзыв."
      );
    }

    await loadProducts();

    showToast(
      "Отзыв удалён"
    );

  } catch (error) {

    showToast(
      error.message
    );
  }
}


/* =========================================================
   HELPERS
========================================================= */

function money(value) {
  return (
    Number(value)
      .toLocaleString("ru-RU") +
    " TMT"
  );
}


function plural(number) {
  const n =
    Math.abs(number) % 100;

  const n1 =
    n % 10;

  if (
    n > 10 &&
    n < 20
  ) {
    return "ов";
  }

  if (n1 === 1) {
    return "";
  }

  if (
    n1 >= 2 &&
    n1 <= 4
  ) {
    return "а";
  }

  return "ов";
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


function escapeJs(value) {
  return String(value)
    .replaceAll(
      "\\",
      "\\\\"
    )
    .replaceAll(
      "'",
      "\\'"
    );
}


function showToast(message) {
  const toast =
    document.getElementById(
      "toast"
    );

  toast.textContent =
    message;

  toast.classList.add(
    "show"
  );

  clearTimeout(
    window.toastTimer
  );

  window.toastTimer =
    setTimeout(
      () => {
        toast.classList.remove(
          "show"
        );
      },
      2200
    );
}
