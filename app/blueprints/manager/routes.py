# app/blueprints/manager/routes.py
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Product, Bill, BillItem, User, LowStockAlert
from sqlalchemy import func
from datetime import date, datetime, timedelta

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")


def manager_required():
    return current_user.is_authenticated and current_user.role == "manager"


# ================= MANAGER DASHBOARD =================
@manager_bp.route("/manager_dashboard")
@login_required
def dashboard():
    if not manager_required():
        return "Unauthorized", 403

    from app.utils.stock import sync_low_stock_alerts
    sync_low_stock_alerts()

    total_products = Product.query.filter(Product.deleted_at.is_(None)).count()
    total_bills = Bill.query.count()
    total_sales = db.session.query(func.sum(Bill.total)).scalar() or 0.0
    total_staff = User.query.filter_by(role="staff").count()
    recent_bills = Bill.query.order_by(Bill.created_at.desc()).limit(5).all()

    low_stock = (
        LowStockAlert.query
        .order_by(LowStockAlert.stock.asc())
        .limit(3)
        .all()
    )

    return render_template(
        "manager/manager_dashboard.html",
        total_products=total_products,
        total_bills=total_bills,
        total_sales=total_sales,
        total_staff=total_staff,
        recent_bills=recent_bills,
        low_stock=low_stock,
    )


# ================= ADD PRODUCT =================
@manager_bp.route("/add_product", methods=["GET", "POST"])
@login_required
def add_product():
    if not manager_required():
        return "Unauthorized", 403

    if "manual_submit" in request.form:
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "0")
        stock = request.form.get("stock", "0")
        unit = request.form.get("unit", "pcs")

        try:
            product = Product(
                name=name,
                price=float(price),
                stock=int(stock),
                unit=unit,
                deleted_at=None
            )
        except ValueError:
            flash("Invalid price or stock value.", "danger")
            return redirect(url_for("manager.add_product"))

        db.session.add(product)
        db.session.commit()
        flash("Product added successfully!", "success")
        return redirect(url_for("manager.view_products"))

    return render_template("manager/add_product.html")


# VIEW PRODUCTS 

@manager_bp.route("/view_products")
@login_required
def view_products():
    if not manager_required():
        return "Unauthorized", 403

    search = request.args.get("search", "")
    sort = request.args.get("sort", "")
    status = request.args.get("status", "all")

    # ✅ DO NOT pre-filter here
    query = Product.query

    # 🔍 Search
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    # 🔹 Status filter
    if status == "active":
        query = query.filter(Product.deleted_at.is_(None))
    elif status == "inactive":
        query = query.filter(Product.deleted_at.is_not(None))
    # else: all (no filter)

    # 🔃 Sorting
    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "stock_asc":
        query = query.order_by(Product.stock.asc())
    elif sort == "stock_desc":
        query = query.order_by(Product.stock.desc())

    products = query.all()

    return render_template(
        "manager/view_products.html",
        products=products,
        current_status=status
    )
# ================= EDIT PRODUCT (BUG FIXED HERE) =================
@manager_bp.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    if not manager_required():
        return "Unauthorized", 403

    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        product.name = request.form.get("name", product.name).strip()

        try:
            product.price = float(request.form.get("price", product.price))

            # 🔹 ADD STOCK (not replace)
            added_stock_raw = request.form.get("stock", "").strip()
            added_stock = int(added_stock_raw) if added_stock_raw else 0
            if added_stock < 0:
                raise ValueError

        except ValueError:
            flash("Invalid numeric value for price or stock.", "danger")
            return redirect(url_for("manager.edit_product", product_id=product_id))

        product.stock += added_stock
        product.unit = request.form.get("unit", product.unit)

        # 🚨 DO NOT TOUCH ACTIVE STATUS HERE
        db.session.commit()

        flash("Product updated successfully.", "success")
        return redirect(url_for("manager.view_products"))

    return render_template("manager/edit_product.html", product=product)

# ================= DELETE PRODUCT =================
@manager_bp.route("/delete_product/<int:product_id>", methods=["POST"])
@login_required
def delete_product(product_id):
    if not manager_required():
        return "Unauthorized", 403

    product = Product.query.get_or_404(product_id)

    # Always soft delete
    product.soft_delete()
    product.stock = 0

    db.session.commit()
    flash("Product marked inactive.", "warning")
    return redirect(url_for("manager.view_products"))

# ================= REACTIVATE PRODUCT =================
@manager_bp.route("/reactivate_product/<int:product_id>", methods=["GET", "POST"])
@login_required
def reactivate_product(product_id):
    if not manager_required():
        return "Unauthorized", 403

    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        try:
            added_stock = int(request.form.get("stock", "").strip())
            if added_stock <= 0:
                raise ValueError
        except ValueError:
            flash("Enter valid stock.", "danger")
            return redirect(url_for("manager.reactivate_product", product_id=product_id))

        product.restore()              # bring back from soft delete
        product.stock += added_stock   # 🔹 ADD, not replace
        db.session.commit()

        flash("Product reactivated successfully.", "success")
        return redirect(url_for("manager.view_products"))

    return render_template("manager/reactivate_product.html", product=product)

# ================= ALERTS =================
@manager_bp.route("/alerts")
@login_required
def alerts():
    if not manager_required():
        return "Unauthorized", 403

    from app.utils.stock import sync_low_stock_alerts
    sync_low_stock_alerts()

    range_param = request.args.get("range", "all")
    query = LowStockAlert.query
    now = datetime.utcnow()

    if range_param == "today":
        start = datetime.combine(date.today(), datetime.min.time())
        query = query.filter(LowStockAlert.timestamp >= start)
    elif range_param == "week":
        query = query.filter(LowStockAlert.timestamp >= now - timedelta(days=7))

    alerts = query.order_by(
        LowStockAlert.stock.asc(),
        LowStockAlert.timestamp.desc()
    ).all()

    return render_template(
        "manager/alerts.html",
        alerts=alerts,
        current_range=range_param
    )


#  Billing History 
@manager_bp.route("/billing_history")
@login_required
def billing_history():
    if not manager_required():
        return "Unauthorized", 403

    #  Filters from query string 
    start_date_str = request.args.get("start_date", "").strip()
    end_date_str = request.args.get("end_date", "").strip()
    staff_id_str = request.args.get("staff_id", "").strip()
    payment_mode_str = request.args.get("payment_mode", "").strip().upper()  # NEW

    bills_query = Bill.query

    # Parse dates safely
    start_date = None
    end_date = None
    from datetime import datetime as dtmod, time

    if start_date_str:
        try:
            d = dtmod.strptime(start_date_str, "%Y-%m-%d").date()
            start_date = dtmod.combine(d, time.min)
            bills_query = bills_query.filter(Bill.created_at >= start_date)
        except ValueError:
            start_date_str = ""  # invalid date -> ignore

    if end_date_str:
        try:
            d = dtmod.strptime(end_date_str, "%Y-%m-%d").date()
            end_date = dtmod.combine(d, time.max)
            bills_query = bills_query.filter(Bill.created_at <= end_date)
        except ValueError:
            end_date_str = ""

    # Staff filter
    selected_staff_id = None
    if staff_id_str:
        try:
            selected_staff_id = int(staff_id_str)
            bills_query = bills_query.filter(Bill.staff_id == selected_staff_id)
        except ValueError:
            selected_staff_id = None

    #  Payment mode filter (CASH / ONLINE / CARD)
    selected_payment_mode = ""
    if payment_mode_str in ("CASH", "ONLINE", "CARD"):
        bills_query = bills_query.filter(Bill.payment_mode == payment_mode_str)
        selected_payment_mode = payment_mode_str

    # Final ordered bills
    bills = bills_query.order_by(Bill.created_at.desc()).all()

    # Summary for visible (filtered) bills
    total_bills = len(bills)
    total_sales = sum((b.total or 0) for b in bills)

    # Staff list for dropdown
    staffs = User.query.filter_by(role="staff").all()

    return render_template(
        "manager/billing_history.html",
        bills=bills,
        total_bills=total_bills,
        total_sales=total_sales,
        staffs=staffs,
        start_date=start_date_str,
        end_date=end_date_str,
        selected_staff_id=selected_staff_id,
        selected_payment_mode=selected_payment_mode,  # NEW
    )


@manager_bp.route("/bill/<int:bill_id>/update_status", methods=["POST"])
@login_required
def update_bill_status(bill_id):
    if not manager_required():
        return "Unauthorized", 403

    bill = Bill.query.get_or_404(bill_id)
    new_status = (request.form.get("status") or "").upper()

    allowed_statuses = {"PAID", "PARTIAL", "RETURNED", "CREDIT"}
    if new_status not in allowed_statuses:
        flash("Invalid status selected.", "danger")
        return redirect(url_for("manager.billing_history"))

    bill.status = new_status
    db.session.commit()
    flash(f"Bill #{bill.id} marked as {new_status}.", "success")
    return redirect(url_for("manager.billing_history"))


# ---------------- Reports ----------------
@manager_bp.route("/reports")
@login_required
def reports():
    if not manager_required():
        return "Unauthorized", 403

    # ----- Top–selling products -----
    most_selling_rows = (
        db.session.query(Product.name, func.sum(BillItem.quantity).label("total_sold"))
        .join(BillItem, Product.id == BillItem.product_id)
        .filter(Product.deleted_at.is_(None))  # ✅ only consider active products
        .group_by(Product.id)
        .order_by(func.sum(BillItem.quantity).desc())
        .limit(10)
        .all()
    )
    most_selling = [(r[0], float(r[1] or 0)) for r in most_selling_rows]

    # ----- Monthly sales (YYYY-MM -> total) -----
    monthly_rows = (
        db.session.query(
            func.date_format(Bill.created_at, "%Y-%m").label("month"),
            func.sum(Bill.total).label("total_sales"),
        )
        .group_by("month")
        .order_by("month")
        .all()
    )
    monthly_sales = [(r[0], float(r[1] or 0)) for r in monthly_rows]

    # ----- Staff performance (username -> total billed) -----
    staff_rows = (
        db.session.query(User.username, func.sum(Bill.total).label("total_billed"))
        .join(Bill, User.id == Bill.staff_id)
        .filter(User.role == "staff")
        .group_by(User.id)
        .order_by(func.sum(Bill.total).desc())
        .all()
    )
    staff_stats = [(r[0], float(r[1] or 0)) for r in staff_rows]

    # lists for Chart.js
    staff_labels = [s[0] for s in staff_stats]
    staff_totals = [s[1] for s in staff_stats]

    # ----- Low stock -----
    low_stock = Product.query.filter(Product.stock < 10,Product.deleted_at.is_(None)).all()

    return render_template(
        "manager/reports.html",
        top_products=most_selling,
        monthly_sales=monthly_sales,
        low_stock=low_stock,
        staff_stats=staff_stats,
        staff_labels=staff_labels,   # ✅ used by staffPerformanceChart
        staff_totals=staff_totals,   # ✅ used by staffPerformanceChart
    )


# ---------------- Staff Management ----------------
@manager_bp.route("/staffs", methods=["GET"])
@login_required
def staff_list():
    if not manager_required():
        return "Unauthorized", 403

    # right now we only list staff users (not managers) on this screen
    staffs = User.query.filter(User.role.in_(["staff","manager"])).all()

    # Attach computed stats as attributes on user objects so templates can access s.total_billed etc.
    for s in staffs:
        bills_count = Bill.query.filter_by(staff_id=s.id).count()
        total_billed = (
            db.session.query(func.sum(Bill.total))
            .filter(Bill.staff_id == s.id)
            .scalar()
            or 0.0
        )
        setattr(s, "bills_count", bills_count)
        setattr(s, "total_billed", float(total_billed))

    return render_template("manager/staffs.html", staffs=staffs)


@manager_bp.route("/staffs/<int:staff_id>/profile")
@login_required
def view_staff_profile(staff_id):
    if not manager_required():
        return "Unauthorized", 403

    staff_user = User.query.get_or_404(staff_id)

    bills = (
        Bill.query.filter_by(staff_id=staff_user.id)
        .order_by(Bill.created_at.desc())
        .all()
    )
    bills_count = len(bills)
    total_billed = (
        db.session.query(func.sum(Bill.total))
        .filter(Bill.staff_id == staff_user.id)
        .scalar()
        or 0.0
    )

    last_bill = bills[0] if bills else None
    avg_bill = (float(total_billed) / bills_count) if bills_count > 0 else 0.0

    return render_template(
        "manager/staff_profile.html",
        staff=staff_user,
        bills=bills,
        bills_count=bills_count,
        total_billed=float(total_billed),
        last_bill=last_bill,
        avg_bill=avg_bill,
    )


@manager_bp.route("/staffs/add", methods=["GET", "POST"])
@login_required
def add_staff():
    if not manager_required():
        return "Unauthorized", 403

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        role = (request.form.get("role") or "staff").strip().lower()   # 🔹 NEW

        if not username or not password:
            flash("Username and password required.", "danger")
            return redirect(url_for("manager.add_staff"))

        # keep only valid roles
        if role not in ("staff", "manager"):
            role = "staff"

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("manager.add_staff"))

        hashed = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash(f"{role.capitalize()} added successfully.", "success")
        return redirect(url_for("manager.staff_list"))

    return render_template("manager/add_staff.html")


@manager_bp.route("/staffs/delete/<int:staff_id>", methods=["POST"])
@login_required
def delete_staff(staff_id):
    if not manager_required():
        return "Unauthorized", 403

    staff = User.query.get_or_404(staff_id)
    if staff.role == "manager":
        flash("Cannot remove a manager account.", "danger")
        return redirect(url_for("manager.staff_list"))

    db.session.delete(staff)
    db.session.commit()
    flash("Staff removed.", "info")
    return redirect(url_for("manager.staff_list"))


# ---------------- Alerts ----------------
# @manager_bp.route("/alerts")
# @login_required
# def alerts():
#     if not manager_required():
#         return "Unauthorized", 403

#     # 🔹 Sync alerts before showing page
#     from app.utils.stock import sync_low_stock_alerts
#     sync_low_stock_alerts()

#     range_param = request.args.get("range", "all")

#     query = LowStockAlert.query
#     now = datetime.utcnow()

#     if range_param == "today":
#         start = datetime.combine(date.today(), datetime.min.time())
#         query = query.filter(LowStockAlert.timestamp >= start)

#     elif range_param == "week":
#         start = now - timedelta(days=7)
#         query = query.filter(LowStockAlert.timestamp >= start)

#     alerts = query.order_by(
#         LowStockAlert.stock.asc(),
#         LowStockAlert.timestamp.desc()
#     ).all()

#     return render_template(
#         "manager/alerts.html",
#         alerts=alerts,
#         current_range=range_param
#     )

@manager_bp.route("/test-mail")
def test_mail():
    from flask_mail import Message
    from app.extensions import mail

    msg = Message(
        subject="Test Email – Smart Supermarket",
        recipients=["sahil.salunke816@gmail.com"],
        body="Email system is working correctly ✅"
    )
    mail.send(msg)
    return "Mail sent successfully"