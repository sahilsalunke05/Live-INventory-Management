from .extensions import login_manager
from datetime import datetime
from .extensions import db
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True, index=True)
    email = db.Column(db.String(150), nullable=True, unique=True, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, index=True)  # 'staff' or 'manager'

    # Relationship: user.bills -> list[Bill] (via backref on Bill.staff)
    def __repr__(self):
        return f"<User {self.username}>"

class Product(db.Model):
    __tablename__ = "product"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    stock = db.Column(db.Integer, nullable=False)                     # quantity available
    price = db.Column(db.Float, nullable=False)                     # consider DECIMAL(10,2) later
    unit = db.Column(db.String(20), nullable=False, default="pcs")  # e.g. "kg", "litre", "pcs"
    # is_active = db.Column(db.Boolean, default=True, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    @property
    def is_active(self):
        return self.deleted_at is None
    def soft_delete(self):
        self.deleted_at = datetime.utcnow() 
    def restore(self):
        self.deleted_at = None

    bill_items = db.relationship("BillItem", back_populates="product")

    def __repr__(self):
        return f"<Product {self.name}>"

class Bill(db.Model):
    __tablename__ = "bill"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)

    subtotal       = db.Column(db.Float, nullable=False, default=0.0)
    discount_percent = db.Column(db.Float, nullable=False, default=0.0)  # ✅ you added in DB
    discount       = db.Column(db.Float, nullable=False, default=0.0)
    taxable_amount = db.Column(db.Float, nullable=False, default=0.0)
    cgst           = db.Column(db.Float, nullable=False, default=0.0)
    sgst           = db.Column(db.Float, nullable=False, default=0.0)
    total          = db.Column(db.Float, nullable=False, default=0.0)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="PAID",   # PAID / PARTIAL / RETURNED / CREDIT
    )

    payment_mode = db.Column(db.String(20), nullable=False, default="CASH")  


    staff_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    staff = db.relationship("User", backref="bills")

    items = db.relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")

    def calculate_total(self, discount_percent=0.0, gst_percent=18.0):
        """Already implemented by you – just make sure it updates subtotal, discount, etc."""
        self.subtotal = sum((item.price or 0) * (item.quantity or 0) for item in self.items)

        self.discount_percent = float(discount_percent or 0.0)
        if self.discount_percent < 0:
            self.discount_percent = 0.0
        if self.discount_percent > 100:
            self.discount_percent = 100.0

        self.discount = self.subtotal * (self.discount_percent / 100.0)
        self.taxable_amount = max(self.subtotal - self.discount, 0.0)

        gst_total = self.taxable_amount * (gst_percent / 100.0)
        self.cgst = gst_total / 2.0
        self.sgst = gst_total / 2.0

        self.total = self.taxable_amount + self.cgst + self.sgst

class BillItem(db.Model):
    __tablename__ = "bill_item"

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bill.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)  # price captured at time of billing

    bill = db.relationship("Bill", back_populates="items")
    product = db.relationship("Product", back_populates="bill_items")

    def __repr__(self):
        return f"<BillItem Bill={self.bill_id}, Product={self.product_id}, Qty={self.quantity}>"

class LowStockAlert(db.Model):
    __tablename__ = "low_stock_alert"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False,
        unique=True,        # no DUPLICATES
        index=True
    )
    product_name = db.Column(db.String(100), nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    product = db.relationship("Product")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
