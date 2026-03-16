// app/static/js/pos.js
document.addEventListener("DOMContentLoaded", () => {
  const productsTbody = document.getElementById("products-tbody");
  const productSearch = document.getElementById("product-search");

  const cartBody = document.getElementById("cart-body");
  const cartTable = document.getElementById("cart-table");
  const cartEmpty = document.getElementById("cart-empty");
  const cartTotal = document.getElementById("cart-total");
  const checkoutBtn = document.getElementById("checkout-btn");

  const discountInput = document.getElementById("discount-input");
  const subtotalSpan = document.getElementById("summary-subtotal");
  const discountAmtSpan = document.getElementById("summary-discount-amount");
  const taxableSpan = document.getElementById("summary-taxable");
  const gstSpan = document.getElementById("summary-gst");

  // 🔹 payment fields
  const paymentModeSelect = document.getElementById("payment-mode");
  const paymentRefInput = document.getElementById("payment-ref");

  // 🔊 SUCCESS SOUND
  

  function playSuccessSound() {
    const sound = document.getElementById("success-sound");
    if (!sound) return;

    sound.currentTime = 0;
    sound.play().catch(() => {});
  }
  

  // local mirror of server cart (keyed by product id string)
  let cart = {};

  const GST_PERCENT = 18.0; // should match backend

  /*  helpers  */
  async function fetchJSON(url, opts = {}) {
    try {
      const res = await fetch(url, opts);
      if (!res.ok) {
        let errText = await res.text().catch(() => "");
        throw new Error(errText || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (e) {
      return { error: e.message || String(e) };
    }
  }

  function formatCurrency(n) {
    return `₹ ${Number(n || 0).toFixed(2)}`;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function showToast(message, type = "success") {
    const toast = document.getElementById("toast-message");
    if (!toast) return;

    toast.innerText = message;

    // Change color depending on type
    if (type === "success") {
      toast.style.background = "#28a745";
    } else if (type === "error") {
      toast.style.background = "#dc3545";
    } else {
      toast.style.background = "#007bff";
    }

    toast.style.display = "block";
    toast.style.opacity = "1";

    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => {
       toast.style.display = "none";
      }, 300);
    }, 2500);
  }

  /*  cart rendering & summary  */
  function renderCartFromServer(serverCart) {
    cart = serverCart || {};
    updateCartUI();
  }

  function computeSummary() {
    let subtotal = 0;
    Object.keys(cart).forEach((pid) => {
      const item = cart[pid];
      subtotal += (item.price || 0) * (item.qty || 0);
    });

    let discountPercent = parseFloat(discountInput?.value || "0");
    if (isNaN(discountPercent) || discountPercent < 0) discountPercent = 0;
    if (discountPercent > 100) discountPercent = 100;

    const discountAmt = subtotal * (discountPercent / 100.0);
    let taxable = subtotal - discountAmt;
    if (taxable < 0) taxable = 0;

    const gstTotal = taxable * (GST_PERCENT / 100.0);
    const total = taxable + gstTotal;

    if (subtotalSpan) subtotalSpan.innerText = formatCurrency(subtotal);
    if (discountAmtSpan) discountAmtSpan.innerText = `- ${formatCurrency(discountAmt).replace("₹ ", "₹ ")}`;
    if (taxableSpan) taxableSpan.innerText = formatCurrency(taxable);
    if (gstSpan) gstSpan.innerText = formatCurrency(gstTotal);
    if (cartTotal) cartTotal.innerText = formatCurrency(total);
  }

  function updateCartUI() {
    cartBody.innerHTML = "";
    const keys = Object.keys(cart);

    if (!keys.length) {
      cartTable.style.display = "none";
      cartEmpty.style.display = "block";
      checkoutBtn.disabled = true;
      computeSummary();
      return;
    }

    cartTable.style.display = "table";
    cartEmpty.style.display = "none";
    checkoutBtn.disabled = false;

    keys.forEach((pid) => {
      const item = cart[pid];
      const subtotal = (item.price || 0) * (item.qty || 0);

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(item.name)}</td>
        <td>
          <input type="number"
                 class="cart-qty"
                 data-id="${pid}"
                 min="0"
                 step="1"
                 value="${item.qty}"
                 style="width:80px;">
        </td>
        <td>${formatCurrency(item.price)}</td>
        <td>${formatCurrency(subtotal)}</td>
        <td><button class="btn btn-sm btn-danger remove-item" data-id="${pid}">X</button></td>
      `;
      cartBody.appendChild(tr);
    });

    // attach listeners
    cartBody.querySelectorAll(".cart-qty").forEach((input) => {
      input.addEventListener("change", onCartQtyChange);
    });
    cartBody.querySelectorAll(".remove-item").forEach((btn) => {
      btn.addEventListener("click", onRemoveItem);
    });

    // update summary
    computeSummary();
  }

  /*  server sync helpers  */
  async function loadServerCart() {
    // Server cart disabled — using client-side cart only
    cart = {};
    updateCartUI();
  }

  async function serverAddItem(product_id, quantity = 1) {
    const res = await fetchJSON("/staff/pos/cart/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: product_id, quantity: quantity }),
    });
    if (res.error) throw new Error(res.error);
    if (res.cart) renderCartFromServer(res.cart);
    return res;
  }

  async function serverUpdateItem(product_id, quantity) {
    const res = await fetchJSON("/staff/pos/cart/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: product_id, quantity: quantity }),
    });
    if (res.error) throw new Error(res.error);
    if (res.cart) renderCartFromServer(res.cart);
    return res;
  }

  async function serverRemoveItem(product_id) {
    const res = await fetchJSON("/staff/pos/cart/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: product_id }),
    });
    if (res.error) throw new Error(res.error);
    if (res.cart) renderCartFromServer(res.cart);
    return res;
  }

  /*  DOM event handlers  */
  // Add product from list
  productsTbody &&
    productsTbody.addEventListener("click", async (e) => {
      if (!e.target.classList.contains("add-to-cart")) return;
      const tr = e.target.closest("tr");
      const pid = tr.dataset.id;
      const name = tr.dataset.name;
      const price = parseFloat(tr.dataset.price || "0");
      const stock = parseInt(tr.dataset.stock || "0");
      const unit = tr.dataset.unit || "";

      try {
        await serverAddItem(parseInt(pid), 1);
      } catch (err) {
        // fallback to purely client-side if server not available
        const existing = cart[pid];
        let qty = existing ? existing.qty + 1 : 1;
        if (qty > stock) {
          showToast("Not enough stock available");
          return;
        }
        cart[pid] = { product_id: pid, name, price, qty, unit };
        updateCartUI();
      }
    });

  function onRemoveItem(e) {
    const id = e.currentTarget.dataset.id;
    serverRemoveItem(parseInt(id))
      .catch(() => {
        delete cart[id];
        updateCartUI();
      });
  }

  function onCartQtyChange(e) {
    const input = e.currentTarget;
    const id = input.dataset.id;
    let q = parseInt(input.value || "0");
    if (isNaN(q) || q < 0) q = 0;

    const prodRow = document.querySelector(`tr[data-id="${id}"]`);
    const stock = prodRow ? parseInt(prodRow.dataset.stock || "0") : Infinity;
    if (q > stock) {
      showToast("Quantity exceeds available stock");
      q = stock;
      input.value = stock;
    }

    if (q === 0) {
      serverRemoveItem(parseInt(id))
        .catch(() => {
          delete cart[id];
          updateCartUI();
        });
      return;
    }

    serverUpdateItem(parseInt(id), q)
      .catch(() => {
        if (cart[id]) {
          cart[id].qty = q;
          updateCartUI();
        }
      });
  }

  // Search filter
  productSearch &&
    productSearch.addEventListener("input", () => {
      const q = (productSearch.value || "").trim().toLowerCase();
      document.querySelectorAll("#products-tbody tr").forEach((r) => {
        const name = (r.dataset.name || "").toLowerCase();
        r.style.display = name.includes(q) ? "" : "none";
      });
    });

  // Recalculate summary when discount changes
  if (discountInput) {
    discountInput.addEventListener("input", () => {
      computeSummary();
    });
  }

  

  // Checkout
checkoutBtn &&
  checkoutBtn.addEventListener("click", async () => {

    if (!Object.keys(cart).length) {
      showToast("Cart is empty");
      return;
    }

    if (!confirm("Proceed to checkout?")) return;

    let discountPercent = parseFloat(discountInput?.value || "0");
    if (isNaN(discountPercent) || discountPercent < 0) discountPercent = 0;
    if (discountPercent > 100) discountPercent = 100;

    const paymentMode = paymentModeSelect ? paymentModeSelect.value : "cash";
    const paymentRef = paymentRefInput ? paymentRefInput.value.trim() : "";

    // ✅ GET FINAL TOTAL (GST + Discount INCLUDED)
    const totalText = cartTotal.innerText.replace("₹", "").trim();
    const totalAmount = parseFloat(totalText);

    // 🔵 FREE UPI QR ONLY FOR ONLINE
    if (paymentMode === "online") {

      const upiId = "sahil.salunke999@okaxis";  
      const businessName = "SmartSupermarketPOS";

      const upiLink = `upi://pay?pa=${upiId}&pn=${businessName}&am=${totalAmount}&cu=INR`;

      const qrContainer = document.getElementById("upi-qr-container");
      const qrDiv = document.getElementById("upi-qr-code");
      const amountText = document.getElementById("upi-amount-text");

      if (!qrContainer || !qrDiv || !amountText) return;

      qrContainer.style.display = "block";
      amountText.innerText = "₹ " + totalAmount.toFixed(2);

      qrDiv.innerHTML = "";

      new QRCode(qrDiv, {
        text: upiLink,
        width: 220,
        height: 220
      });

      // 🔥 CHANGE BUTTON TEXT
      checkoutBtn.innerText = "💰 Payment Received";
      checkoutBtn.classList.remove("btn-success");
      checkoutBtn.classList.add("btn-primary");

      // Remove old click listeners by cloning button
      const newBtn = checkoutBtn.cloneNode(true);
      checkoutBtn.parentNode.replaceChild(newBtn, checkoutBtn);

      newBtn.addEventListener("click", async () => {

        const res = await fetchJSON("/staff/pos/checkout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            discount_percent: discountPercent,
            payment_mode: "online",
            payment_ref: "UPI_MANUAL"
          }),
        });

        if (res.success) {
          qrContainer.style.display = "none";
          checkoutBtn.innerText = "Checkout";
          checkoutBtn.classList.remove("btn-primary");
          checkoutBtn.classList.add("btn-success");
          playSuccessSound();
          showToast("Payment successful!","success");
          cart = {};
          updateCartUI();
          window.location.href = res.receipt_url;
        } else {
          showToast("Checkout failed");
        }
      });

      return;
    }   

    // 🟢 NORMAL CASH FLOW (UNCHANGED)
    const res = await fetchJSON("/staff/pos/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        discount_percent: discountPercent,
        payment_mode: paymentMode,
        payment_ref: paymentRef
      }),
    });

    if (res.success) {
      cart = {};
      updateCartUI();
      showToast("Payment successful!","success");
      playSuccessSound();
      window.location.href = res.receipt_url;
    } else {
      showToast("Checkout failed");
    }

  });

  /* -------------------- initial load -------------------- */
  (async function init() {
    await loadServerCart();
  })();
});