# In flask shell or fix_stock.py
from app import app
from models import Product, db

with app.app_context():
    # Find a product and set stock to 0
    product = Product.query.filter_by(name='Blue Co Ord').first()
    if product:
        product.stock = 0
        product.in_stock = False
        db.session.commit()
        print(f"✅ {product.name} is now OUT OF STOCK")