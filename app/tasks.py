from datetime import datetime
from flask import current_app
from flask_mail import Message

from .extensions import db, mail
from .models import Product, LowStockAlert

def check_low_stock():
    """
    Nightly job: find low-stock active products, log an alert row for each,
    and send a single summary email to recipients.
    """
    # Flask-APScheduler provides app context; still safe-guard explicitly:
    app = current_app._get_current_object()

    threshold = app.config.get("LOW_STOCK_THRESHOLD", 10)
    recipients = app.config.get("LOW_STOCK_RECIPIENTS", [])

    # Fetch low stock items
    low_items = (
        Product.query
        .filter(Product.is_active.is_(True))
        .filter(Product.stock < threshold)
        .order_by(Product.stock.asc())
        .all()
    )

    if not low_items:
        return  # nothing to do

    # Persist audit rows
    now = datetime.utcnow()
    for p in low_items:
        db.session.add(
            LowStockAlert(
                product_name=p.name,
                stock=int(p.stock),
                timestamp=now
            )
        )
    db.session.commit()

    # Compose email body
    lines = [
        "The following products are below the threshold:\n",
        *(f"- {p.name}: {p.stock} {p.unit}" for p in low_items),
        f"\nThreshold: {threshold}",
        f"Timestamp (UTC): {now:%Y-%m-%d %H:%M:%S}",
    ]
    body = "\n".join(lines)

    if recipients:
        msg = Message(
            subject="⚠️ Low Stock Alert - Supermarket Inventory",
            recipients=recipients,
            body=body,
        )
        try:
            mail.send(msg)
        except Exception as e:
            # Log but don't crash the scheduler
            print(f"[LowStockEmail] send failed: {e}")
