import os
import sqlite3

# Read environment
APP_ENV = os.getenv("APP_ENV", "local")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "/app/data/local.db")
RESET_DB = os.getenv("RESET_DB", "True").lower() in ("true", "1")  # Set to True to reset DB

def init_sqlite():
    """Create SQLite DB and insert/update default products for local development."""
    print("🔧 Initializing SQLite local database...")

    # Ensure directory exists
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    c = conn.cursor()

    if RESET_DB:
        print("⚠️ Resetting database - dropping existing products table...")
        c.execute("DROP TABLE IF EXISTS products")

    # Create table if it doesn't exist
    c.execute("""
     CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        description VARCHAR(500),
        price DECIMAL(10,2),
        image_url VARCHAR(300),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Product seed data
    products = [
        (1, 'Laptop', 'High performance laptop', 103000.00, 'https://your-bucket.s3.amazonaws.com/laptop.jpg'),
        (2, 'Headphones', 'Noise cancelling headphones', 3000.00, 'https://your-bucket.s3.amazonaws.com/headphones.jpg'),
        (3, 'Keyboard', 'Mechanical RGB keyboard', 4000.00, 'https://your-bucket.s3.amazonaws.com/keyboard.jpg'),
        (4, 'Mouse', 'Wireless ergonomic mouse', 1200.00, 'https://your-bucket.s3.amazonaws.com/mouse.jpg'),
        (5, 'Smartwatch', 'Fitness tracking smartwatch', 8090.00, 'https://your-bucket.s3.amazonaws.com/smartwatch.jpg'),
        (6, 'Earphones', 'High performance laptop', 103000.00, 'https://your-bucket.s3.amazonaws.com/laptop.jpg'),
        (7, 'Mobile cable', 'Noise cancelling headphones', 3000.00, 'https://your-bucket.s3.amazonaws.com/headphones.jpg'),
        (8, 'Mobile Holder', 'Mechanical RGB keyboard', 4000.00, 'https://your-bucket.s3.amazonaws.com/keyboard.jpg'),
        (9, 'Power Bank', 'Mechanical RGB keyboard', 4000.00, 'https://your-bucket.s3.amazonaws.com/keyboard.jpg'),
        (10, 'iPhone 7', 'Fitness tracking smartwatch', 8090.00, 'https://your-bucket.s3.amazonaws.com/smartwatch.jpg')
    ]

    if RESET_DB:
        print("🟢 Inserting initial seed product data (fresh DB)...")
        c.executemany("""
        INSERT INTO products (id, name, description, price, image_url)
        VALUES (?, ?, ?, ?, ?)
        """, products)
    else:
        print("ℹ️ Upserting products without deleting existing entries...")
        for product in products:
            c.execute("""
            INSERT INTO products (id, name, description, price, image_url)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                price=excluded.price,
                image_url=excluded.image_url
            """, product)

    conn.commit()
    conn.close()
    print(f"✅ SQLite DB initialized at {SQLITE_DB_PATH}")


if __name__ == "__main__":
    if APP_ENV == "local":
        init_sqlite()
    else:
        print("⏭ Skipping init_db.py because APP_ENV != local (Production mode)")
