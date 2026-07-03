from app import app
from models import db, Admin

with app.app_context():
    admin = Admin.query.filter_by(username='olivintra').first()
    if not admin:
        admin = Admin(username='olivintra')
        admin.set_password('olivintra2026')
        db.session.add(admin)
        db.session.commit()
        print('✅ Admin user created successfully!')
    else:
        print('✅ Admin user already exists!')
    
    print('=' * 50)
    print('👤 Username: olivintra')
    print('🔑 Password: olivintra2026')
    print('=' * 50)