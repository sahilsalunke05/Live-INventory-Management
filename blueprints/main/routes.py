# app/blueprints/main/routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import User

main_bp = Blueprint("main", __name__)

# ---------------- Public Home ----------------
@main_bp.route("/")
def index():
    return render_template("index.html")


#  Manager Dashboard (redirect to manager blueprint) 
@main_bp.route("/manager/dashboard", methods=["GET", "POST"])
@login_required
def manager_dashboard():
    # Only managers allowed - keep check, but redirect to manager blueprint's dashboard,
    # which has full manager functionality.
    if current_user.role != "manager":
        return "🚫 Unauthorized: Managers only", 403

    # If the manager page has staff-creation form on a separate URL, you can keep POST logic here.
    # But to keep concerns separated, we'll redirect to the manager blueprint. If you want "add staff"
    # handled here, we could implement it — for now redirect.
    return redirect(url_for("manager.dashboard"))


#  Staff Dashboard 
@main_bp.route("/staff/dashboard")
@login_required
def staff_dashboard():
    if current_user.role != "staff":
        return "🚫 Unauthorized: Staff only", 403
    return render_template("staff/staff_dashboard.html")