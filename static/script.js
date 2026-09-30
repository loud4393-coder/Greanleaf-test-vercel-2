async function loadProducts() {
  const status = document.getElementById("status");
  const container = document.getElementById("products");
  try {
    const response = await fetch("/api/products");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const products = Array.isArray(data.products) ? data.products : [];
    container.innerHTML = "";
    if (!products.length) {
      status.textContent = "Каталог пуст";
      return;
    }
    for (const product of products) {
      const card = document.createElement("article");
      card.className = "product";
      const name = document.createElement("h2");
      name.textContent = product.name;
      const description = document.createElement("div");
      description.textContent = product.description || "";
      const price = document.createElement("div");
      price.className = "price";
      price.textContent = `${product.price} ${product.currency || "TMT"}`;
      card.append(name, description, price);
      container.appendChild(card);
    }
    status.textContent = `Каталог загружен: ${products.length} товара`;
  } catch (error) {
    status.className = "error";
    status.textContent = `Не удалось загрузить каталог: ${error.message}`;
  }
}
loadProducts();
