import os
import json
import boto3
import pymysql
import sqlite3
import logging

from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename

# ======================================================================
# LOGGING CONFIGURATION (CloudWatch / Elastic Beanstalk)
# ======================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ======================================================================
# FLASK APP
# ======================================================================
app = application = Flask(__name__)

# ======================================================================
# PART 1 — ENVIRONMENT MODE
# ======================================================================
ENV_MODE = os.environ.get("APP_ENV", "local")  # local | aws
logger.info(f"Application starting | ENV_MODE = {ENV_MODE}")

# ======================================================================
# PART 2 — AWS SECRETS MANAGER HELPER
# ======================================================================
def get_db_secret():
    """Fetch DB credentials from AWS Secrets Manager (AWS mode only)."""
    if ENV_MODE == "local":
        logger.info("Skipping Secrets Manager (local mode)")
        return None

    secret_name = os.environ.get("DB_SECRET_NAME")
    region = os.environ.get("AWS_REGION", "ap-south-1")

    logger.info(
        f"Fetching DB secret from Secrets Manager | "
        f"SecretName={secret_name}, Region={region}"
    )

    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)

    logger.info("Successfully retrieved DB secret")
    return json.loads(response["SecretString"])

# ======================================================================
# PART 3 — DATABASE CONNECTION HANDLER
# ======================================================================
def get_db_connection():

    # -----------------------------
    # LOCAL MODE → SQLITE
    # -----------------------------
    if ENV_MODE == "local":
        db_path = os.getenv("SQLITE_DB_PATH", "/app/data/local.db")
        logger.info(f"Using SQLite database | Path={db_path}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -----------------------------
    # AWS MODE → RDS MySQL
    # -----------------------------
    logger.info("Using AWS RDS MySQL (cloud mode)")
    secret = get_db_secret()

    logger.info(
        f"Connecting to RDS | Host={secret['host']} | "
        f"DB={secret['dbname']} | User={secret['username']}"
    )

    return pymysql.connect(
        host=secret["host"],
        user=secret["username"],
        password=secret["password"],
        database=secret["dbname"],
        cursorclass=pymysql.cursors.DictCursor
    )

# ======================================================================
# PART 4 — DB QUERIES
# ======================================================================
def get_all_products():
    logger.info("Fetching all products from database")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    conn.close()
    logger.info(f"Total products fetched: {len(products)}")
    return products

def get_product(pid):
    logger.info(f"Fetching product | ProductID={pid}")
    with get_db_connection() as conn:
        cur = conn.cursor()
        if ENV_MODE == "local":
            query = "SELECT * FROM products WHERE id=?"
        else:
            query = "SELECT * FROM products WHERE id=%s"
        cur.execute(query, (pid,))
        product = cur.fetchone()

        if product:
            logger.info(f"Product found | ProductID={pid}")
        else:
            logger.warning(f"Product NOT found | ProductID={pid}")

        return product

# ======================================================================
# PART 5 — AWS HELPER FUNCTIONS (SQS + S3)
# ======================================================================
def get_sqs():
    if ENV_MODE == "local":
        logger.info("SQS disabled (local mode)")
        return None

    q = os.environ.get("SQS_QUEUE_URL")
    if q:
        logger.info(f"SQS enabled | QueueURL={q}")
        return boto3.client("sqs")

    logger.warning("SQS_QUEUE_URL not set")
    return None

def get_s3():
    if ENV_MODE == "local":
        logger.info("S3 disabled (local mode)")
        return None

    bucket = os.environ.get("S3_BUCKET")
    if bucket:
        logger.info(f"S3 enabled | Bucket={bucket}")
        return boto3.client("s3")

    logger.warning("S3_BUCKET not set")
    return None

# ======================================================================
# PART 6 — CART (DEMO)
# ======================================================================
cart = {}

# ======================================================================
# PART 7 — ROUTES
# ======================================================================
@app.route("/")
def home():
    logger.info("Home page requested")
    products = get_all_products()

    for p in products:
        if not p.get("image_url") if ENV_MODE != "local" else not p["image_url"]:
            p["image_url"] = url_for("static", filename="placeholder.png")

    return render_template("index.html", products=products)

@app.route("/product/<int:pid>")
def product(pid):
    logger.info(f"Product page requested | ProductID={pid}")
    p = get_product(pid)

    if not p:
        logger.warning(f"Product page 404 | ProductID={pid}")
        return "Product not found", 404

    if not p.get("image_url") if ENV_MODE != "local" else not p["image_url"]:
        p["image_url"] = url_for("static", filename="placeholder.png")

    return render_template("product.html", product=p)

@app.route("/cart")
def view_cart():
    logger.info("Cart page requested")
    items = []
    total = 0

    for pid, qty in cart.items():
        p = get_product(pid)
        if not p:
            continue
        subtotal = p["price"] * qty
        items.append({"product": p, "qty": qty, "subtotal": subtotal})
        total += subtotal

    logger.info(f"Cart items={len(items)} | Total={total}")
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/add/<int:pid>", methods=["POST"])
def add_to_cart(pid):
    cart[pid] = cart.get(pid, 0) + 1
    logger.info(f"Added to cart | ProductID={pid} | Qty={cart[pid]}")
    return redirect("/cart")

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    logger.info("Checkout endpoint hit")

    if request.method == "GET":
        logger.info("Checkout GET request")
        return render_template("checkout.html")

    logger.info("Checkout POST request received")

    name = request.form.get("name")
    email = request.form.get("email")
    order = {"name": name, "email": email, "items": cart}

    logger.info(f"Order received | Name={name} | Email={email}")

    sqs_sent = False
    file_url = None

    # OPTIONAL FILE UPLOAD → S3
    if "image" in request.files:
        f = request.files["image"]
        if f.filename and ENV_MODE != "local":
            filename = secure_filename(f.filename)
            s3 = get_s3()
            if s3:
                bucket = os.environ["S3_BUCKET"]
                s3.upload_fileobj(f, bucket, filename)
                file_url = f"https://{bucket}.s3.amazonaws.com/{filename}"
                logger.info(f"File uploaded to S3 | URL={file_url}")

    # SEND ORDER TO SQS
    if ENV_MODE != "local":
        sqs = get_sqs()
        if sqs:
            sqs.send_message(
                QueueUrl=os.environ["SQS_QUEUE_URL"],
                MessageBody=json.dumps(order)
            )
            sqs_sent = True
            logger.info("Order message sent to SQS")

    cart.clear()
    logger.info("Cart cleared after checkout")

    return render_template(
        "checkout.html",
        success=True,
        order=order,
        sqs_sent=sqs_sent,
        file_url=file_url
    )

# ======================================================================
# RUN APP
# ======================================================================
if __name__ == "__main__":
    logger.info("Starting Flask development server")
    app.run(host="0.0.0.0", port=5000, debug=True)
