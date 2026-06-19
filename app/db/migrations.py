from sqlalchemy import inspect, text

from app.db.session import engine


def ensure_product_timestamps() -> None:
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("products")}
    statements: list[str] = []
    if "last_crawled_at" not in columns:
        statements.append("ALTER TABLE products ADD COLUMN last_crawled_at TIMESTAMP WITH TIME ZONE")
    if "last_checked_at" not in columns:
        statements.append("ALTER TABLE products ADD COLUMN last_checked_at TIMESTAMP WITH TIME ZONE")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
