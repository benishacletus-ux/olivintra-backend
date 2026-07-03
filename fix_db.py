import sqlite3

def add_updated_at_column():
    try:
        # Connect to the database
        conn = sqlite3.connect('olivintra.db')
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(category)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'updated_at' not in columns:
            # Add the column
            cursor.execute("ALTER TABLE category ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            print("✅ Added 'updated_at' column to category table")
        else:
            print("ℹ️ 'updated_at' column already exists")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    add_updated_at_column()
    print("Done!")