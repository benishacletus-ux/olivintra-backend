from app import app, db
from sqlalchemy import text

with app.app_context():
    # Check if user_id column exists
    try:
        # Try to add user_id column
        db.session.execute(text('ALTER TABLE "order" ADD COLUMN user_id INTEGER REFERENCES user(id)'))
        db.session.commit()
        print("✅ user_id column added successfully!")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ user_id column already exists")
        else:
            print(f"❌ Error: {e}")