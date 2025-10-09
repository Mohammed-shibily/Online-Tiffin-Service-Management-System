import os
import json
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template, redirect,
    url_for, session, flash, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.message import EmailMessage
import stripe
from dotenv import load_dotenv
load_dotenv()

# -----------------------
# Configuration
# -----------------------
# -----------------------
# Configuration
# -----------------------
app = Flask(__name__, static_folder='static', template_folder='templates')

# Use a writable local folder instead of OneDrive
local_instance = os.path.join(os.environ["LOCALAPPDATA"], "mini_project_instance")
os.makedirs(local_instance, exist_ok=True)

db_path = os.path.join(local_instance, "app.db")
print(f"🔥 Using database at: {db_path}")

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# Stripe Configuration
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_xxxxxxxxxxxxx")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_xxxxxxxxxxxxx")
stripe.api_key = STRIPE_SECRET_KEY

# Admin credentials
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "secure_admin_password_123")

# SMTP Configuration (optional)
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")

# -----------------------
# Database Models
# -----------------------
class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=True)
    email = db.Column(db.String(180), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    stripe_customer_id = db.Column(db.String(120), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship("Order", backref="customer", lazy=True)
    complaints = db.relationship("Complaint", backref="customer", lazy=True)

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default="INR")
    stripe_payment_intent_id = db.Column(db.String(120), nullable=True, unique=True)
    stripe_charge_id = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(40), nullable=False, default="created")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)

class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    place = db.Column(db.String(180), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    complaint_type = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="New")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)

# -----------------------
# Helper Functions
# -----------------------
def send_admin_email(subject: str, content: str):
    """Send email to ADMIN_EMAIL if SMTP settings provided."""
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
        app.logger.info("Admin email sent successfully")
        return True
    except Exception as e:
        app.logger.exception("Failed to send admin email: %s", e)
        return False

def admin_required(f):
    """Decorator to require admin login"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# -----------------------
# Frontend Routes
# -----------------------
@app.route("/")
def home():
    return render_template('index.html')

@app.route("/plans")
def plans():
    return render_template('plans.html')

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/features")
def features():
    return render_template('features.html')

# -----------------------
# API Routes - STRIPE
# -----------------------
@app.route("/api/get_stripe_config", methods=["GET"])
def get_stripe_config():
    """Return Stripe publishable key for frontend"""
    print("DEBUG: get_stripe_config called")
    return jsonify({"publishableKey": STRIPE_PUBLISHABLE_KEY})

@app.route("/api/create_payment_intent", methods=["POST"])
def create_payment_intent():
    """Create Stripe Payment Intent"""
    print("DEBUG: create_payment_intent called")
    try:
        data = request.get_json() or {}
        print(f"DEBUG: Received data: {data}")
        
        plan_id = data.get("plan_id")
        amount = data.get("amount")
        currency = data.get("currency", "inr")
        description = data.get("description", "")
        customer_info = data.get("customer", {})

        if not plan_id or not amount:
            return jsonify({"error": "plan_id and amount are required"}), 400

        # Find or create customer
        phone = customer_info.get("phone")
        email = customer_info.get("email")
        cust = None
        
        if phone:
            cust = Customer.query.filter_by(phone=phone).first()
        if not cust and email:
            cust = Customer.query.filter_by(email=email).first()
        
        # Create Stripe customer if needed
        stripe_customer_id = None
        if cust and cust.stripe_customer_id:
            stripe_customer_id = cust.stripe_customer_id
        else:
            stripe_customer = stripe.Customer.create(
                name=customer_info.get("name"),
                email=email,
                phone=phone,
                metadata={"plan_id": plan_id}
            )
            stripe_customer_id = stripe_customer.id
            
            if not cust:
                cust = Customer(
                    name=customer_info.get("name"),
                    email=email,
                    phone=phone,
                    stripe_customer_id=stripe_customer_id
                )
                db.session.add(cust)
            else:
                cust.stripe_customer_id = stripe_customer_id
            
            db.session.commit()

        # Create Stripe Payment Intent
        payment_intent = stripe.PaymentIntent.create(
            amount=int(amount),
            currency=currency.lower(),
            customer=stripe_customer_id,
            description=description,
            metadata={
                "plan_id": plan_id,
                "customer_id": str(cust.id)
            }
        )

        # Save order
        order_row = Order(
            plan_id=plan_id,
            description=description,
            amount=int(amount),
            currency=currency.upper(),
            stripe_payment_intent_id=payment_intent.id,
            status="created",
            customer_id=cust.id
        )
        db.session.add(order_row)
        db.session.commit()

        print(f"DEBUG: Payment intent created: {payment_intent.id}")
        
        return jsonify({
            "clientSecret": payment_intent.client_secret,
            "paymentIntentId": payment_intent.id
        })

    except Exception as e:
        print(f"DEBUG: Error in create_payment_intent: {str(e)}")
        app.logger.error("Error creating payment intent: %s", str(e))
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/api/confirm_payment", methods=["POST"])
def confirm_payment():
    """Confirm payment success"""
    print("DEBUG: confirm_payment called")
    try:
        data = request.get_json() or {}
        payment_intent_id = data.get("payment_intent_id")

        if not payment_intent_id:
            return jsonify({"success": False, "error": "Missing payment_intent_id"}), 400

        # Retrieve payment intent from Stripe, expand charges safely
        payment_intent = stripe.PaymentIntent.retrieve(
            payment_intent_id,
            expand=["latest_charge", "charges"]
        )

        # Find order in database
        order = Order.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
        if not order:
            return jsonify({"success": False, "error": "Order not found"}), 404

        # Update order status safely
        if payment_intent.status == "succeeded":
            # Safely handle charge ID
            charge_id = None
            try:
                # Prefer latest_charge (new API field)
                if getattr(payment_intent, "latest_charge", None):
                    charge_id = payment_intent.latest_charge.id
                # Fallback for older API structure
                elif getattr(payment_intent, "charges", None):
                    charges_data = payment_intent.charges.get("data", [])
                    if charges_data:
                        charge_id = charges_data[0].id
            except Exception as e:
                print(f"DEBUG: Couldn't extract charge ID safely: {e}")

            order.status = "paid"
            order.stripe_charge_id = charge_id
            db.session.commit()

            # Send admin notification
            subject = f"New subscription paid — {order.plan_id} — ₹{order.amount/100:.2f}"
            content = f"""
A new payment has been received.

Order ID: {order.id}
Plan: {order.plan_id}
Amount: ₹{order.amount/100:.2f} {order.currency}
Customer: {order.customer.name if order.customer else 'N/A'} 
Phone: {order.customer.phone if order.customer else 'N/A'}
Email: {order.customer.email if order.customer else 'N/A'}
Stripe Payment Intent: {payment_intent_id}

Please check the admin dashboard: /admin
"""
            send_admin_email(subject, content)

            print(f"✅ Payment confirmed for order {order.id}")
            return jsonify({"success": True, "status": "paid"}), 200

        else:
            order.status = payment_intent.status
            db.session.commit()
            print(f"⚠️ Payment not succeeded, status: {payment_intent.status}")
            return jsonify({"success": False, "status": payment_intent.status}), 400

    except Exception as e:
        print(f"❌ DEBUG: Error in confirm_payment: {str(e)}")
        app.logger.error("Error confirming payment: %s", str(e))
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# -----------------------
# API Routes - COMPLAINTS
# -----------------------
@app.route("/api/submit_complaint", methods=["POST"])
def submit_complaint():
    """Handle complaint submission from the frontend form"""
    try:
        data = request.get_json() or request.form.to_dict()
        
        name = data.get("Name")
        phone = data.get("Phone")
        place = data.get("Place")
        category = data.get("Category")
        complaint_type = data.get("Complaint")
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
    
    except Exception as e:
        app.logger.error("Error submitting complaint: %s", str(e))
        db.session.rollback()
        return jsonify({"error": "Failed to submit complaint"}), 500

# -----------------------
# Stripe Webhook
# -----------------------
@app.route("/api/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        app.logger.warning("Webhook secret not configured")
        return jsonify({"status": "webhook secret not configured"}), 400

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    # Handle events
    if event.type == "payment_intent.succeeded":
        payment_intent = event.data.object
        payment_intent_id = payment_intent.id
        
        order = Order.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
        if order and order.status != "paid":
            order.status = "paid"
            order.stripe_charge_id = payment_intent.charges.data[0].id if payment_intent.charges.data else None
            db.session.commit()
            app.logger.info(f"Order {order.id} marked as paid via webhook")

    elif event.type == "payment_intent.payment_failed":
        payment_intent = event.data.object
        payment_intent_id = payment_intent.id
        
        order = Order.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
        if order:
            order.status = "failed"
            db.session.commit()
            app.logger.info(f"Order {order.id} marked as failed via webhook")

    return jsonify({"status": "success"})

# -----------------------
# Admin Routes
# -----------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            flash("Login successful!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out successfully", "success")
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    
    # Calculate statistics
    total_orders = len(orders)
    paid_orders = len([o for o in orders if o.status == "paid"])
    total_revenue = sum([o.amount for o in orders if o.status == "paid"])
    pending_complaints = len([c for c in complaints if c.status == "New"])
    
    stats = {
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "total_revenue": total_revenue / 100,
        "pending_complaints": pending_complaints
    }
    
    return render_template("admin_dashboard.html", 
                         orders=orders, 
                         complaints=complaints,
                         stats=stats)

@app.route("/admin/order/<int:order_id>/fulfill", methods=["POST"])
@admin_required
def fulfill_order(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = "fulfilled"
    db.session.commit()
    flash("Order marked as fulfilled", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/complaint/<int:complaint_id>/resolve", methods=["POST"])
@admin_required
def resolve_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    complaint.status = "Resolved"
    db.session.commit()
    flash("Complaint marked as resolved", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/complaint/<int:complaint_id>/progress", methods=["POST"])
@admin_required
def progress_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    complaint.status = "In Progress"
    db.session.commit()
    flash("Complaint marked as in progress", "success")
    return redirect(url_for("admin_dashboard"))

# -----------------------
# Error Handlers
# -----------------------
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": f"Endpoint {request.path} not found"}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Server error: {str(e)}")
    if request.path.startswith('/api/'):
        return jsonify({"error": "Internal server error"}), 500
    return render_template('500.html'), 500

# -----------------------
# Debug Route (Remove in production)
# -----------------------
@app.route("/api/test")
def test_api():
    """Test route to verify API is working"""
    return jsonify({
        "status": "success",
        "message": "API is working!",
        "routes": [str(rule) for rule in app.url_map.iter_rules() if rule.rule.startswith('/api')]
    })

# -----------------------
# CLI Commands
# -----------------------
@app.cli.command("initdb")
def initdb_cmd():
    """Initialize the database."""
    with app.app_context():
        db.create_all()
    print("✓ Database initialized successfully!")

@app.cli.command("resetdb")
def resetdb_cmd():
    """Reset the database (drop all tables and recreate)."""
    with app.app_context():
        db.drop_all()
        db.create_all()
    print("✓ Database reset successfully!")

@app.cli.command("routes")
def routes_cmd():
    """List all registered routes."""
    print("\nRegistered Routes:")
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        print(f"  {rule.rule:50s} {methods:20s} {rule.endpoint}")
    print()

# -----------------------
# Application Entry Point
# -----------------------
if __name__ == "__main__":
    # Initialize database
    with app.app_context():
        db.create_all()
        print("=" * 60)
        print("✓ Database initialized!")
        print(f"✓ Server starting on http://localhost:5000")
        print(f"✓ Admin login: http://localhost:5000/admin/login")
        print(f"  Username: {ADMIN_USERNAME}")
        print(f"  Password: {ADMIN_PASSWORD}")
        print("=" * 60)
        
        # List API routes
        print("\nAPI Routes Available:")
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith('/api'):
                methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
                print(f"  {rule.rule:40s} [{methods}]")
        print("=" * 60)
    
    # Run application
    app.run(debug=True, host="0.0.0.0", port=5000)