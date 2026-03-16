# app/utils/stock.py
from datetime import datetime
from app.extensions import db
from app.models import Product, LowStockAlert
from flask import current_app


def sync_low_stock_alerts():
    """
    Keep low_stock_alert table in sync with current product stock.
    - No duplicates
    - Removes alerts when stock is healthy
    - Uses soft-delete logic (deleted_at)
    """

    threshold = current_app.config.get("LOW_STOCK_THRESHOLD", 10)

    # ✅ Only non-deleted products
    low_products = (
        Product.query
        .filter(Product.deleted_at.is_(None))
        .filter(Product.stock < threshold)
        .all()
    )

    # Existing alerts mapped by product_id
    existing_alerts = {
        a.product_id: a for a in LowStockAlert.query.all()
    }

    now = datetime.utcnow()

    seen_product_ids = set()

    # 🔹 Create or update alerts
    for product in low_products:
        seen_product_ids.add(product.id)

        if product.id in existing_alerts:
            alert = existing_alerts[product.id]
            alert.stock = product.stock
            alert.timestamp = now
        else:
            db.session.add(
                LowStockAlert(
                    product_id=product.id,
                    product_name=product.name,
                    stock=product.stock,
                    timestamp=now
                )
            )

    # 🔹 Remove alerts if product is no longer low-stock
    for product_id, alert in existing_alerts.items():
        if product_id not in seen_product_ids:
            db.session.delete(alert)

    db.session.commit()