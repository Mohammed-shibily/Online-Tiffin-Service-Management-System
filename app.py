# app.py
import os
import hmac
import hashlib
import json
import requests
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template, redirect,
    url_for, session, flash
)
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, send_from_directory, render_template, redirect
import smtplib
from email.message import EmailMessage

# -----------------------
# Configuration
# -----------------------
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-here")

BASE = os.path.abspath(os.path.dirname(__file__))
STATIC = os.path.join(BASE, 'static')
DB_PATH = os.environ.get("SQLITE_PATH", os.path.join(BASE, "app.db"))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Razorpay: set these as env vars before running
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_xxxxxxxxxxxxx")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "your_test_secret_here")

# Admin credentials (simple for demo) - set env vars to override defaults
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")

# SMTP (optional) - if set, server will attempt to email admin on successful payment
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")  # where notifications go

# -----------------------
# Database models
# -----------------------
class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=True)
    email = db.Column(db.String(180), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship("Order", backref="customer", lazy=True)
    complaints = db.relationship("Complaint", backref="customer", lazy=True)

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Integer, nullable=False)  # stored in paise (integer)
    currency = db.Column(db.String(10), nullable=False, default="INR")
    razorpay_order_id = db.Column(db.String(120), nullable=True, unique=True)
    razorpay_payment_id = db.Column(db.String(120), nullable=True, unique=True)
    razorpay_signature = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(40), nullable=False, default="created") # created, paid, failed, fulfilled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)

class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    place = db.Column(db.String(180), nullable=True)
    category = db.Column(db.String(50), nullable=True)  # Breakfast, Lunch, Dinner
    complaint_type = db.Column(db.String(50), nullable=True)  # Delivery, Food, Other
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="New")  # New, In Progress, Resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)

# -----------------------
# Helper functions
# -----------------------
def init_db():
    db.create_all()

def send_admin_email(subject: str, content: str):
    """Send email to ADMIN_EMAIL if SMTP settings provided. Silent fail otherwise."""
    if not ADMIN_EMAIL or not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        app.logger.info("SMTP or ADMIN_EMAIL not configured — skipping email")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = ADMIN_EMAIL
        msg.set_content(content)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        app.logger.info("Admin email sent")
        return True
    except Exception as e:
        app.logger.exception("Failed to send admin email: %s", e)
        return False

# -----------------------
# Routes: frontend pages
# -----------------------
@app.route("/")
def home():
    return send_from_directory(STATIC, "index.html")

@app.route("/plans")
def plans():
    return send_from_directory(STATIC, "plans.html")

# -----------------------
# API: Submit Complaint
# -----------------------
@app.route("/submit_complaint", methods=["POST"])
def submit_complaint():
    """
    Handle complaint submission from the frontend form
    """
    data = request.get_json() or request.form.to_dict()
    
    name = data.get("Name")
    phone = data.get("Phone")
    place = data.get("Place")
    category = data.get("Category")  # Breakfast, Lunch, Dinner
    complaint_type = data.get("Complaint")  # Delivery, Food, Other
    description = data.get("Description")
    
    if not name or not phone:
        return jsonify({"error": "Name and phone are required"}), 400
    
    # Find or create customer
    customer = Customer.query.filter_by(phone=phone).first()
    if not customer:
        customer = Customer(name=name, phone=phone)
        db.session.add(customer)
        db.session.commit()
    
    # Create complaint
    complaint = Complaint(
        name=name,
        phone=phone,
        place=place,
        category=category,
        complaint_type=complaint_type,
        description=description,
        customer_id=customer.id
    )
    
    db.session.add(complaint)
    db.session.commit()
    
    # Send notification email
    subject = f"New Complaint Received - {complaint_type}"
    content = f"""
New complaint received:

Name: {name}
Phone: {phone}
Place: {place}
Category: {category}
Type: {complaint_type}
Description: {description}

Complaint ID: {complaint.id}
Time: {complaint.created_at}

Please check the admin dashboard: /admin
"""
    send_admin_email(subject, content)
    
    return jsonify({"success": True, "message": "Complaint registered successfully"})

# -----------------------
# API: Create Razorpay order (server-side)
# -----------------------
@app.route("/create_order", methods=["POST"])
def create_order():
    """
    Expects JSON:
    { plan_id, amount (int paise), currency, description, customer: {name, email, phone} }
    """
    data = request.get_json() or {}
    plan_id = data.get("plan_id")
    amount = data.get("amount")
    currency = data.get("currency", "INR")
    description = data.get("description", "")
    customer_info = data.get("customer", {})

    if not plan_id or not amount:
        return jsonify({"error": "plan_id and amount are required"}), 400

    receipt = f"rcpt_{plan_id}_{os.urandom(4).hex()}"

    payload = {
        "amount": int(amount),
        "currency": currency,
        "receipt": receipt,
        "payment_capture": 1
    }

    url = "https://api.razorpay.com/v1/orders"
    resp = requests.post(url, auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET), json=payload)

    if resp.status_code not in (200, 201):
        app.logger.error("Razorpay order creation failed: %s", resp.text)
        return jsonify({"error": "Failed to create order with payment provider", "details": resp.text}), 500

    order_data = resp.json()
    razorpay_order_id = order_data.get("id")

    # Save customer (or find existing by phone/email)
    cust = None
    phone = customer_info.get("phone")
    email = customer_info.get("email")
    if phone:
        cust = Customer.query.filter_by(phone=phone).first()
    if not cust and email:
        cust = Customer.query.filter_by(email=email).first()
    if not cust:
        cust = Customer(name=customer_info.get("name"), email=email, phone=phone)
        db.session.add(cust)
        db.session.commit()

    # Save order row
    order_row = Order(
        plan_id=plan_id,
        description=description,
        amount=int(amount),
        currency=currency,
        razorpay_order_id=razorpay_order_id,
        status="created",
        customer_id=cust.id
    )
    db.session.add(order_row)
    db.session.commit()

    return jsonify({
        "order_id": razorpay_order_id,
        "amount": order_data.get("amount"),
        "currency": order_data.get("currency"),
        "key": RAZORPAY_KEY_ID
    })

# -----------------------
# API: Verify payment (front-end sends Razorpay response)
# -----------------------
@app.route("/verify_payment", methods=["POST"])
def verify_payment():
    """
    Expected JSON from frontend after checkout:
    { razorpay_payment_id, razorpay_order_id, razorpay_signature, plan_id, customer: {...} }
    """
    data = request.get_json() or {}
    pay_id = data.get("razorpay_payment_id")
    order_id = data.get("razorpay_order_id")
    signature = data.get("razorpay_signature")
    plan_id = data.get("plan_id")
    customer_info = data.get("customer", {})

    if not (pay_id and order_id and signature):
        return jsonify({"success": False, "error": "Missing payment parameters"}), 400

    # compute signature server-side
    payload = f"{order_id}|{pay_id}"
    expected_signature = hmac.new(
        bytes(RAZORPAY_KEY_SECRET, "utf-8"),
        bytes(payload, "utf-8"),
        hashlib.sha256
    ).hexdigest()

    if expected_signature != signature:
        app.logger.warning("Signature mismatch: expected=%s received=%s", expected_signature, signature)
        # Update DB order to failed if exists
        o = Order.query.filter_by(razorpay_order_id=order_id).first()
        if o:
            o.status = "failed"
            o.razorpay_payment_id = pay_id
            o.razorpay_signature = signature
            db.session.commit()
        return jsonify({"success": False, "error": "Invalid signature"}), 400

    # signature OK -> mark order as paid
    o = Order.query.filter_by(razorpay_order_id=order_id).first()
    if not o:
        # fallback: create an order row if missing (rare)
        cust = None
        phone = customer_info.get("phone")
        email = customer_info.get("email")
        if phone:
            cust = Customer.query.filter_by(phone=phone).first()
        if not cust and email:
            cust = Customer.query.filter_by(email=email).first()
        if not cust:
            cust = Customer(name=customer_info.get("name"), email=email, phone=phone)
            db.session.add(cust)
            db.session.commit()

        o = Order(
            plan_id=plan_id or "unknown",
            description="(created after payment)",
            amount=0,
            currency="INR",
            razorpay_order_id=order_id,
            razorpay_payment_id=pay_id,
            razorpay_signature=signature,
            status="paid",
            customer_id=cust.id
        )
        db.session.add(o)
        db.session.commit()
    else:
        o.status = "paid"
        o.razorpay_payment_id = pay_id
        o.razorpay_signature = signature
        db.session.commit()

    # Notify admin (optional email)
    subject = f"New subscription paid — {o.plan_id} — ₹{o.amount/100:.2f} {o.currency}"
    content = f"""
A new payment has been received.

Order DB id: {o.id}
Plan: {o.plan_id}
Amount: ₹{o.amount/100:.2f} {o.currency}
Customer: {o.customer.name if o.customer else 'N/A'} ({o.customer.phone if o.customer else 'N/A'}, {o.customer.email if o.customer else 'N/A'})
Razorpay Order ID: {order_id}
Razorpay Payment ID: {pay_id}

Please check the admin dashboard: /admin
"""
    send_admin_email(subject, content)

    return jsonify({"success": True})

# -----------------------
# Admin: Authentication & Dashboard
# -----------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/admin")
@admin_required
def admin_dashboard():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template("admin_dashboard.html", orders=orders, complaints=complaints)

@app.route("/admin/order/<int:order_id>/fulfill", methods=["POST"])
@admin_required
def fulfill_order(order_id):
    o = Order.query.get_or_404(order_id)
    o.status = "fulfilled"
    db.session.commit()
    flash("Order marked fulfilled", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/complaint/<int:complaint_id>/resolve", methods=["POST"])
@admin_required
def resolve_complaint(complaint_id):
    c = Complaint.query.get_or_404(complaint_id)
    c.status = "Resolved"
    db.session.commit()
    flash("Complaint marked as resolved", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/complaint/<int:complaint_id>/progress", methods=["POST"])
@admin_required
def progress_complaint(complaint_id):
    c = Complaint.query.get_or_404(complaint_id)
    c.status = "In Progress"
    db.session.commit()
    flash("Complaint marked as in progress", "success")
    return redirect(url_for("admin_dashboard"))

# -----------------------
# Utility: create DB quickly
# -----------------------
@app.cli.command("initdb")
def initdb_cmd():
    """Initialize the database."""
    init_db()
    print("Initialized the database.")

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    init_db()  # create DB on first run
    app.run(debug=True, host="0.0.0.0", port=5000)