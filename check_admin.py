from app import app, db
from models import Admin

with app.app_context():
    admins = Admin.query.all()
    print(f"Found {len(admins)} admin users:")
    for admin in admins:
        print(f"  - {admin.username}")
    
    if not admins:
        print("No admin users found! Creating one...")
        admin = Admin(username='olivintra')
        admin.set_password('olivintra2026')
        db.session.add(admin)
        db.session.commit()
        print("Admin created successfully!")