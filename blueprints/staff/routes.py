# app/blueprints/staff/routes.py

import razorpay
from flask import current_app, jsonify, request
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash,
    current_app,
)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Product, Bill, BillItem, LowStockAlert
from datetime import datetime, date, timedelta
from sqlalchemy import func
from pytz import timezone

from app.utils.stock import sync_low_stock_alerts

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


def staff_required():
    """Return True if current_user is authenticated as staff."""
    return current_user.is_authenticated and current_user.role == "staff"


def staff_or_manager():
    """Helper to allow either staff or manager to access POS."""
    return current_user.is_authenticated and current_user.role in ("staff", "manager")


# ---------------- POS UI ----------------
@staff_bp.route("/pos")
@login_required
def pos():
    # allow staff and manager to use POS
    if not staff_or_manager():
        return "Unauthorized", 403

    products = (
        Product.query.filter(Product.deleted_at.is_(None))  # noqa: E712 
        .order_by(Product.name)
        .limit(500)
        .all()
    )
    session.setdefault("pos_cart", {})
    return render_template("staff/pos.html", products=products)


# ---------------- API: search products (ajax) ----------------
@staff_bp.route("/pos/search")
@login_required
def pos_search():
    if not staff_or_manager():
        return jsonify({"error": "Unauthorized"}), 403

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})

    results = (
        Product.query.filter(
            Product.name.ilike(f"%{q}%"),
            Product.deleted_at.is_(None)  # noqa: E712
        )
        .limit(50)
        .all()
    )
    out = [
        {
            "id": p.id,
            "name": p.name,
            "price": float(p.price),
            "stock": int(p.stock),
            "unit": p.unit,
        }
        for p in results
    ]
    return jsonify({"results": out})


# ---------------- API: add item to cart ----------------
@staff_bp.route("/pos/cart/add", methods=["POST"])
@login_required
def pos_cart_add():
    if not staff_or_manager():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    product_id = data.get("product_id")
    qty = data.get("quantity", 1)
    try:
        qty = float(qty)
    except Exception:
        return jsonify({"error": "Invalid quantity"}), 400

    if not product_id:
        return jsonify({"error": "product_id required"}), 400

    product = Product.query.get(product_id)
    if not product or not product.is_active:
        return jsonify({"error": "Product not found"}), 404

    if qty <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    cart = session.get("pos_cart", {})
    pid_str = str(product.id)
    existing = cart.get(pid_str)
    existing_qty = float(existing.get("qty", 0)) if existing else 0.0
    new_qty = existing_qty + qty
    if new_qty > float(product.stock):
        return jsonify({"error": f"Not enough stock. Available: {product.stock}"}), 400

    cart[pid_str] = {
        "product_id": product.id,
        "name": product.name,
        "price": float(product.price),
        "qty": new_qty,
        "unit": product.unit,
    }
    session["pos_cart"] = cart
    session.modified = True
    return jsonify({"success": True, "cart": cart})


# ---------------- API: update cart item qty ----------------
@staff_bp.route("/pos/cart/update", methods=["POST"])
@login_required
def pos_cart_update():
    if not staff_or_manager():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    product_id = data.get("product_id")
    qty = data.get("quantity")
    try:
        qty = float(qty)
    except Exception:
        return jsonify({"error": "Invalid quantity"}), 400

    if product_id is None:
        return jsonify({"error": "product_id required"}), 400

    if qty < 0:
        return jsonify({"error": "Invalid quantity"}), 400

    cart = session.get("pos_cart", {})
    pid_str = str(product_id)
    if pid_str not in cart:
        return jsonify({"error": "Item not in cart"}), 404

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if qty > float(product.stock):
        return jsonify({"error": f"Not enough stock. Available: {product.stock}"}), 400

    if qty == 0:
        cart.pop(pid_str, None)
    else:
        cart[pid_str]["qty"] = qty

    session["pos_cart"] = cart
    session.modified = True
    return jsonify({"success": True, "cart": cart})


# ---------------- API: remove item ----------------
@staff_bp.route("/pos/cart/remove", methods=["POST"])
@login_required
def pos_cart_remove():
    if not staff_or_manager():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    product_id = data.get("product_id")
    if product_id is None:
        return jsonify({"error": "product_id required"}), 400

    cart = session.get("pos_cart", {})
    pid_str = str(product_id)
    if pid_str in cart:
        cart.pop(pid_str, None)
        session["pos_cart"] = cart
        session.modified = True

    return jsonify({"success": True, "cart": cart})

# ---------------- API: checkout ----------------
@staff_bp.route("/pos/checkout", methods=["POST"])
@login_required
def pos_checkout():
    # allow staff OR manager to use POS
    if not staff_or_manager():
        return jsonify({"error": "Unauthorized"}), 403

    cart = session.get("pos_cart", {})
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    data = request.get_json(silent=True) or {}

    # Discount %
    try:
        discount_percent = float(data.get("discount_percent", 0.0))
    except Exception:
        discount_percent = 0.0

    discount_percent = max(0.0, min(discount_percent, 100.0))

    # Payment mode
    payment_mode = (data.get("payment_mode") or "cash").lower()
    if payment_mode not in ("cash", "online", "card", "upi"):
        payment_mode = "cash"
    payment_mode = payment_mode.upper()

    GST_PERCENT = 18.0

    product_ids = [int(k) for k in cart.keys()]
    products = Product.query.filter(Product.id.in_(product_ids),Product.deleted_at.is_(None)).all()
    products_map = {p.id: p for p in products}

    # Validate stock
    for pid_str, item in cart.items():
        pid = int(pid_str)
        p = products_map.get(pid)
        if not p:
            return jsonify({"error": f"Product {item.get('name')} not found"}), 404

        qty = float(item.get("qty", 0))
        if qty <= 0:
            return jsonify({"error": f"Invalid quantity for {p.name}"}), 400

        if qty > int(p.stock):
            return jsonify({"error": f"Not enough stock for {p.name}. Available: {p.stock}"}), 400

    try:
        # Create bill
        bill = Bill(
            staff_id=current_user.id,
            created_at=datetime.now(timezone("Asia/Kolkata")),
            payment_mode=payment_mode,
        )
        db.session.add(bill)

        # Create bill items + update stock
        for pid_str, item in cart.items():
            pid = int(pid_str)
            p = products_map[pid]
            qty = float(item["qty"])
            price = float(item["price"])

            bill_item = BillItem(
                product_id=pid,
                quantity=qty,
                price=price
            )
            bill.items.append(bill_item)

            # update stock ONLY
            p.stock = int(p.stock) - int(qty)
            if p.stock < 0:
                raise Exception("Stock went negative")

        # Calculate totals
        bill.calculate_total(
            discount_percent=discount_percent,
            gst_percent=GST_PERCENT
        )

        db.session.commit()

        # ✅ SINGLE SOURCE OF TRUTH for alerts
        from app.utils.stock import sync_low_stock_alerts
        sync_low_stock_alerts()

    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Checkout failed")
        return jsonify({"error": "Checkout failed", "detail": str(exc)}), 500

    # clear cart
    session["pos_cart"] = {}
    session.modified = True

    receipt_url = url_for("staff.pos_receipt", bill_id=bill.id)

    return jsonify({
        "success": True,
        "bill_id": bill.id,
        "subtotal": float(bill.subtotal or 0),
        "discount_percent": float(discount_percent),
        "discount": float(bill.discount or 0),
        "taxable_amount": float(bill.taxable_amount or 0),
        "cgst": float(bill.cgst or 0),
        "sgst": float(bill.sgst or 0),
        "total": float(bill.total or 0),
        "receipt_url": receipt_url
    })


#  View / Print bill 
@staff_bp.route("/pos/receipt/<int:bill_id>")
@login_required
def pos_receipt(bill_id):
    if not staff_or_manager():
        return "Unauthorized", 403

    bill = Bill.query.get_or_404(bill_id)
    items = BillItem.query.filter_by(bill_id=bill.id).all()

    # Use stored values (set by calculate_total)
    subtotal = float(bill.subtotal or 0.0)
    discount = float(bill.discount or 0.0)
    taxable_amount = float(bill.taxable_amount or 0.0)
    cgst = float(bill.cgst or 0.0)
    sgst = float(bill.sgst or 0.0)
    grand_total = float(bill.total or 0.0)

    # You can also pass payment info to the template if columns exist in the model
    payment_mode = getattr(bill, "payment_mode", None)
    payment_reference = getattr(bill, "payment_reference", None)

    return render_template(
        "staff/receipt.html",
        bill=bill,
        items=items,
        subtotal=subtotal,
        discount=discount,
        taxable_amount=taxable_amount,
        cgst=cgst,
        sgst=sgst,
        grand_total=grand_total,
        payment_mode=payment_mode,
        payment_reference=payment_reference,
    )

@staff_bp.route("/create-razorpay-order", methods=["POST"])
@login_required
def create_razorpay_order():
    try:
        data = request.get_json()
        amount = int(data.get("amount"))  # in rupees

        # convert to paise (important)
        amount_paise = amount * 100

        client = razorpay.Client(auth=(
            current_app.config["RAZORPAY_KEY_ID"],
            current_app.config["RAZORPAY_KEY_SECRET"]
        ))

        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1
        })

        return jsonify({
            "success": True,
            "order_id": order["id"],
            "key": current_app.config["RAZORPAY_KEY_ID"]
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


#  Staff: view own bills 
@staff_bp.route("/my_bills")
@login_required
def my_bills():
    # only staff should see their own bills
    if not staff_required():
        return "Unauthorized", 403

    #  Filters from query string 
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    min_total = request.args.get("min_total", "").strip()
    max_total = request.args.get("max_total", "").strip()

    q = Bill.query.filter(Bill.staff_id == current_user.id)

    # Date from
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            q = q.filter(Bill.created_at >= dt_from)
        except ValueError:
            pass

    # Date to (add 1 day so it's inclusive)
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            q = q.filter(Bill.created_at < dt_to)
        except ValueError:
            pass

    # Min / max total
    if min_total:
        try:
            q = q.filter(Bill.total >= float(min_total))
        except ValueError:
            pass

    if max_total:
        try:
            q = q.filter(Bill.total <= float(max_total))
        except ValueError:
            pass

    bills = q.order_by(Bill.created_at.desc()).all()

    #  Quick stats for dashboard feel 
    today = date.today()
    today_q = Bill.query.filter(
        Bill.staff_id == current_user.id,
        func.date(Bill.created_at) == today
    )
    today_count = today_q.count()
    today_sales = today_q.with_entities(func.sum(Bill.total)).scalar() or 0.0

    last_bill = (
        Bill.query
        .filter_by(staff_id=current_user.id)
        .order_by(Bill.created_at.desc())
        .first()
    )

    return render_template(
        "staff/my_bills.html",
        bills=bills,
        today_count=today_count,
        today_sales=float(today_sales),
        last_bill=last_bill,
        date_from=date_from,
        date_to=date_to,
        min_total=min_total,
        max_total=max_total,
    )