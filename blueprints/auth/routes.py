# app/blueprints/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, send to correct dashboard
    if current_user.is_authenticated:
        if current_user.role == "manager":
            return redirect(url_for("manager.dashboard"))
        elif current_user.role == "staff":
            return redirect(url_for("main.staff_dashboard"))
        else:
            return redirect(url_for("main.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash("Invalid username or password", "danger")
            return render_template("login.html")

        # Login OK
        login_user(user)
        flash("Login successful!", "success")

        # Redirect based on role
        if user.role == "manager":
            return redirect(url_for("manager.dashboard"))
        elif user.role == "staff":
            # NOTE: staff dashboard endpoint is in main blueprint
            return redirect(url_for("main.staff_dashboard"))
        else:
            return redirect(url_for("main.login"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))