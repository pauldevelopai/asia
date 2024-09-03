from sqlalchemy import create_engine, MetaData, Table, Column, LargeBinary, text

DATABASE_URI = "sqlite:///podcasts.db"
engine = create_engine(DATABASE_URI)
metadata = MetaData()

# Reflect the existing database
metadata.reflect(bind=engine)

# Get the 'script' table
script_table = Table('script', metadata, autoload_with=engine)

# Add the 'audio' column
if 'audio' not in script_table.c:
    with engine.connect() as conn:
        conn.execute(text('ALTER TABLE script ADD COLUMN audio BLOB'))

print("Database schema updated successfully.")