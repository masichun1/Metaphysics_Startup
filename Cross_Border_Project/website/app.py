"""Mystic Sanctuary — Metaphysical E-Commerce Website"""
import json
import hashlib
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, jsonify, session

app = Flask(__name__)
app.secret_key = "mystic-sanctuary-secret-key-change-in-production"
DATA_DIR = Path(__file__).parent / "data"

# Admin password (SHA256 hash of "mystic2026")
ADMIN_PASSWORD_HASH = "a1b2c3d4e5f6"  # Change this in production!


def load_json(filename: str):
    path = DATA_DIR / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {} if filename.endswith("settings") else []


def save_json(filename: str, data):
    (DATA_DIR / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via SMTP."""
    try:
        settings = load_json("settings.json")
        smtp = settings.get("smtp", {})
        if not smtp.get("host"):
            return False
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{smtp.get('from_name', 'Mystic Sanctuary')} <{smtp.get('from_email', '')}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP(smtp["host"], smtp.get("port", 587), timeout=15) as server:
            server.starttls()
            server.login(smtp.get("user", ""), smtp.get("password", ""))
            server.sendmail(smtp["from_email"], to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


# ============================================================
# Frontend Routes
# ============================================================

@app.route("/")
def index():
    products = load_json("products.json")
    posts = load_json("blog_posts.json")
    settings = load_json("settings.json")
    return render_template("index.html", products=products[:6], posts=posts[:3], settings=settings)


@app.route("/products")
def products():
    products = load_json("products.json")
    settings = load_json("settings.json")
    category = request.args.get("category", "")
    if category:
        products = [p for p in products if p.get("category", "").lower() == category.lower()]
    return render_template("products.html", products=products, category=category, settings=settings)


@app.route("/product/<sku>")
def product_detail(sku: str):
    products = load_json("products.json")
    product = next((p for p in products if p.get("sku") == sku), None)
    if not product:
        return render_template("404.html"), 404
    settings = load_json("settings.json")
    related = [p for p in products if p.get("sku") != sku][:4]
    return render_template("product.html", product=product, related=related, settings=settings)


@app.route("/blog")
def blog():
    posts = load_json("blog_posts.json")
    settings = load_json("settings.json")
    return render_template("blog.html", posts=posts, settings=settings)


@app.route("/blog/<slug>")
def blog_post(slug: str):
    posts = load_json("blog_posts.json")
    post = next((p for p in posts if p.get("slug") == slug), None)
    if not post:
        return render_template("404.html"), 404
    settings = load_json("settings.json")
    return render_template("blog_post.html", post=post, settings=settings)


@app.route("/cart")
def cart():
    settings = load_json("settings.json")
    return render_template("cart.html", settings=settings)


@app.route("/checkout")
def checkout():
    settings = load_json("settings.json")
    return render_template("checkout.html", settings=settings)


@app.route("/checkout/submit", methods=["POST"])
def checkout_submit():
    """Handle checkout form submission — save order and send email."""
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    orders = load_json("orders.json")
    order = {
        "id": f"MS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{len(orders)+1:04d}",
        "customer": {
            "first_name": data.get("first_name", ""),
            "last_name": data.get("last_name", ""),
            "email": data.get("email", ""),
            "address": data.get("address", ""),
            "city": data.get("city", ""),
            "state": data.get("state", ""),
            "zip": data.get("zip", ""),
            "country": data.get("country", "United States"),
        },
        "items": data.get("items", []),
        "subtotal": float(data.get("subtotal", 0)),
        "shipping": float(data.get("shipping", 0)),
        "total": float(data.get("total", 0)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    orders.append(order)
    save_json("orders.json", orders)

    # Send confirmation email to customer
    customer_email = order["customer"]["email"]
    if customer_email:
        items_html = "".join(
            f'<li>{item.get("title", "")} x{item.get("quantity", 1)} — ${item.get("price", 0):.2f}</li>'
            for item in order["items"]
        )
        send_email(
            to_email=customer_email,
            subject=f"Order {order['id']} Confirmed — Mystic Sanctuary",
            html_body=f"""<h2>Thank you for your order, {order['customer']['first_name']}!</h2>
<p>Your order <strong>#{order['id']}</strong> has been received.</p>
<h3>Order Summary</h3><ul>{items_html}</ul>
<p><strong>Subtotal:</strong> ${order['subtotal']:.2f}</p>
<p><strong>Shipping:</strong> ${order['shipping']:.2f}</p>
<p><strong>Total:</strong> ${order['total']:.2f}</p>
<p>We'll send you a shipping confirmation once your order is on the way.</p>
<p style='margin-top:20px;color:#6b4e7e;'><em>May these tools bring light to your journey.</em></p>
<p>— Mystic Sanctuary</p>""",
        )

    return jsonify({"success": True, "order_id": order["id"]})


# ============================================================
# Admin Routes
# ============================================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    products = load_json("products.json")
    posts = load_json("blog_posts.json")
    orders = load_json("orders.json")
    pending = sum(1 for o in orders if o.get("status") == "pending")
    revenue = sum(o.get("total", 0) for o in orders)
    return render_template("admin/dashboard.html",
        product_count=len(products), post_count=len(posts),
        order_count=len(orders), pending_orders=pending, revenue=revenue)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == "mystic2026":  # Change this in production!
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        return render_template("admin/login.html", error="Wrong password")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/products")
@admin_required
def admin_products():
    products = load_json("products.json")
    return render_template("admin/products.html", products=products)


@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    if request.method == "POST":
        products = load_json("products.json")
        products.append({
            "sku": request.form.get("sku", ""),
            "title": request.form.get("title", ""),
            "category": request.form.get("category", ""),
            "price": float(request.form.get("price", 0)),
            "compare_at_price": float(request.form.get("compare_at_price", 0) or 0),
            "vendor": request.form.get("vendor", "Mystic Sanctuary"),
            "tags": [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
            "body_html": request.form.get("body_html", ""),
            "meta_description": request.form.get("meta_description", ""),
            "seo_keywords": request.form.get("seo_keywords", ""),
            "inventory": int(request.form.get("inventory", 100)),
            "image": f"/static/images/{request.form.get('sku', '').lower()}.jpg",
        })
        save_json("products.json", products)
        return redirect(url_for("admin_products"))
    return render_template("admin/product_edit.html", product=None)


@app.route("/admin/products/<sku>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(sku: str):
    products = load_json("products.json")
    idx = next((i for i, p in enumerate(products) if p.get("sku") == sku), None)
    if idx is None:
        return "Not found", 404
    if request.method == "POST":
        products[idx].update({
            "title": request.form.get("title", products[idx]["title"]),
            "category": request.form.get("category", products[idx].get("category", "")),
            "price": float(request.form.get("price", products[idx]["price"])),
            "compare_at_price": float(request.form.get("compare_at_price", 0) or 0),
            "body_html": request.form.get("body_html", products[idx].get("body_html", "")),
            "meta_description": request.form.get("meta_description", products[idx].get("meta_description", "")),
            "seo_keywords": request.form.get("seo_keywords", products[idx].get("seo_keywords", "")),
            "tags": [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
            "inventory": int(request.form.get("inventory", products[idx].get("inventory", 100))),
        })
        save_json("products.json", products)
        return redirect(url_for("admin_products"))
    return render_template("admin/product_edit.html", product=products[idx])


@app.route("/admin/products/<sku>/delete", methods=["POST"])
@admin_required
def admin_product_delete(sku: str):
    products = load_json("products.json")
    products = [p for p in products if p.get("sku") != sku]
    save_json("products.json", products)
    return redirect(url_for("admin_products"))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = load_json("orders.json")
    settings = load_json("settings.json")
    return render_template("admin/orders.html", orders=orders, settings=settings)


@app.route("/admin/orders/<order_id>/status", methods=["POST"])
@admin_required
def admin_order_status(order_id: str):
    orders = load_json("orders.json")
    for o in orders:
        if o.get("id") == order_id:
            o["status"] = request.form.get("status", "pending")
            save_json("orders.json", orders)
            break
    return redirect(url_for("admin_orders"))


@app.route("/admin/blog")
@admin_required
def admin_blog():
    posts = load_json("blog_posts.json")
    return render_template("admin/blog.html", posts=posts)


@app.route("/admin/blog/new", methods=["GET", "POST"])
@admin_required
def admin_blog_new():
    if request.method == "POST":
        posts = load_json("blog_posts.json")
        posts.append({
            "slug": request.form.get("slug", ""),
            "title": request.form.get("title", ""),
            "category": request.form.get("category", ""),
            "date": request.form.get("date", ""),
            "read_time": int(request.form.get("read_time", 5)),
            "excerpt": request.form.get("excerpt", ""),
            "body_html": request.form.get("body_html", ""),
        })
        save_json("blog_posts.json", posts)
        return redirect(url_for("admin_blog"))
    return render_template("admin/blog_edit.html", post=None)


@app.route("/admin/blog/<slug>/edit", methods=["GET", "POST"])
@admin_required
def admin_blog_edit(slug: str):
    posts = load_json("blog_posts.json")
    idx = next((i for i, p in enumerate(posts) if p.get("slug") == slug), None)
    if idx is None:
        return "Not found", 404
    if request.method == "POST":
        posts[idx].update({
            "title": request.form.get("title", posts[idx]["title"]),
            "category": request.form.get("category", posts[idx].get("category", "")),
            "date": request.form.get("date", posts[idx].get("date", "")),
            "read_time": int(request.form.get("read_time", posts[idx].get("read_time", 5))),
            "excerpt": request.form.get("excerpt", posts[idx].get("excerpt", "")),
            "body_html": request.form.get("body_html", posts[idx].get("body_html", "")),
        })
        save_json("blog_posts.json", posts)
        return redirect(url_for("admin_blog"))
    return render_template("admin/blog_edit.html", post=posts[idx])


@app.route("/admin/blog/<slug>/delete", methods=["POST"])
@admin_required
def admin_blog_delete(slug: str):
    posts = load_json("blog_posts.json")
    posts = [p for p in posts if p.get("slug") != slug]
    save_json("blog_posts.json", posts)
    return redirect(url_for("admin_blog"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
