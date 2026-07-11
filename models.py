from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json
import ast

db = SQLAlchemy()

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<Admin {self.username}>'

# ==================== USER MODEL (CUSTOMER) ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(10))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='user', lazy=True)
    activities = db.relationship('UserActivity', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

# ==================== USER ACTIVITY MODEL ====================

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80))
    email = db.Column(db.String(120))
    activity_type = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserActivity {self.username} - {self.activity_type} at {self.created_at}>'

# ==================== CATEGORY MODEL ====================

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    image = db.Column(db.String(200))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    products = db.relationship('Product', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'

# ==================== PRODUCT MODEL ====================

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)
    image = db.Column(db.String(200))
    images = db.Column(db.Text)  # JSON array for multiple images
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    is_featured = db.Column(db.Boolean, default=False)
    is_best_seller = db.Column(db.Boolean, default=False)
    is_new_arrival = db.Column(db.Boolean, default=False)
    stock = db.Column(db.Integer, default=0)
    in_stock = db.Column(db.Boolean, default=True)
    rating = db.Column(db.Float, default=0)
    review_count = db.Column(db.Integer, default=0)
    material = db.Column(db.String(100))
    care_instructions = db.Column(db.Text)
    sizes = db.Column(db.Text)  # JSON array for sizes like ["S", "M", "L", "XL", "XXL"]
    
    # ============ ADDED: Free Size Field ============
    is_free_size = db.Column(db.Boolean, default=False)  # <-- NEW FIELD
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with reviews
    reviews = db.relationship('Review', backref='product', lazy=True, cascade='all, delete-orphan')
    
    # ==================== IMAGE HELPER METHODS ====================
    def get_images(self):
        """Get list of image filenames from JSON"""
        if self.images:
            try:
                return json.loads(self.images)
            except:
                return []
        return []
    
    def set_images(self, image_list):
        """Set images from list to JSON"""
        self.images = json.dumps(image_list) if image_list else None
    
    def add_image(self, filename):
        """Add a single image to the product"""
        images = self.get_images()
        images.append(filename)
        self.set_images(images)
    
    def remove_image(self, index):
        """Remove image by index"""
        images = self.get_images()
        if 0 <= index < len(images):
            images.pop(index)
            self.set_images(images)
            return True
        return False
    
    def get_all_images(self):
        """Get all images including main image"""
        images = []
        if self.image:
            images.append(self.image)
        images.extend(self.get_images())
        return images
    
    # ==================== IMAGE OPTIMIZATION HELPER ====================
    def get_optimized_image(self, width=300, height=400):
        """Get optimized product image URL with Cloudinary transformations
        
        Args:
            width: Desired width (default 300)
            height: Desired height (default 400)
        
        Returns:
            Optimized image URL with Cloudinary transformations
        """
        if not self.image:
            return f"https://via.placeholder.com/{width}x{height}/cccccc/333333?text=Olivintra"
        
        # Check if it's a Cloudinary URL
        if 'res.cloudinary.com' in self.image or 'cloudinary' in self.image:
            parts = self.image.split('/upload/')
            if len(parts) == 2:
                # Add transformations for consistent 3:4 ratio
                return f"{parts[0]}/upload/w_{width},h_{height},c_fill,f_auto,q_auto/{parts[1]}"
        
        # Return original if not Cloudinary
        return self.image
    
    def get_optimized_images(self, width=300, height=400):
        """Get optimized URLs for all images (main + additional)
        
        Args:
            width: Desired width (default 300)
            height: Desired height (default 400)
        
        Returns:
            List of optimized image URLs
        """
        images = []
        
        # Main image
        if self.image:
            images.append(self.get_optimized_image(width, height))
        
        # Additional images
        for img in self.get_images():
            if img:
                if 'res.cloudinary.com' in img or 'cloudinary' in img:
                    parts = img.split('/upload/')
                    if len(parts) == 2:
                        images.append(f"{parts[0]}/upload/w_{width},h_{height},c_fill,f_auto,q_auto/{parts[1]}")
                    else:
                        images.append(img)
                else:
                    images.append(img)
        
        return images
    
    # ==================== SIZE HELPER METHODS - FIXED ====================
    def get_sizes(self):
        """Get list of sizes from JSON - handles all formats"""
        if not self.sizes:
            return []
        
        # If it's already a list
        if isinstance(self.sizes, list):
            return self.sizes
        
        if isinstance(self.sizes, str):
            # Try to parse as JSON
            try:
                # Clean up the string
                clean_str = self.sizes
                # Remove escaped quotes
                clean_str = clean_str.replace('\\"', '"')
                # Remove extra brackets if present
                if clean_str.startswith('"[') and clean_str.endswith(']"'):
                    clean_str = clean_str[1:-1]
                # Parse JSON
                sizes = json.loads(clean_str)
                if isinstance(sizes, list):
                    return sizes
            except:
                pass
            
            # Try parsing with ast.literal_eval for Python list strings
            try:
                sizes = ast.literal_eval(self.sizes)
                if isinstance(sizes, list):
                    return sizes
            except:
                pass
            
            # If it's a comma-separated string
            if ',' in self.sizes:
                return [s.strip() for s in self.sizes.split(',') if s.strip()]
            
            # If it's a single value
            if self.sizes.strip():
                return [self.sizes.strip()]
        
        return []
    
    def set_sizes(self, size_list):
        """Set sizes from list to JSON"""
        if size_list and isinstance(size_list, list):
            # Clean the list - remove empty strings
            cleaned_list = [s.strip() for s in size_list if s and s.strip()]
            self.sizes = json.dumps(cleaned_list) if cleaned_list else None
        else:
            self.sizes = None
    
    def has_size(self, size):
        """Check if a specific size is available"""
        sizes = self.get_sizes()
        return size in sizes
    
    def get_sizes_display(self):
        """Get sizes as a comma-separated string for display"""
        sizes = self.get_sizes()
        return ', '.join(sizes) if sizes else 'No sizes'
    
    # ==================== FREE SIZE HELPER ====================
    def is_free_size_product(self):
        """Check if product is free size"""
        return self.is_free_size or not self.get_sizes()
    
    def __repr__(self):
        return f'<Product {self.name}>'

# ==================== ORDER MODEL ====================

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(10))
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    
    # ========== PAYMENT FIELDS - ADDED ==========
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, failed
    payment_method = db.Column(db.String(50), default='COD')
    razorpay_order_id = db.Column(db.String(100), nullable=True)
    payment_id = db.Column(db.String(100), nullable=True)
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.order_number}>'

# ==================== ORDER ITEM MODEL ====================

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False)
    size = db.Column(db.String(20))  # Selected size
    color = db.Column(db.String(50))
    
    product = db.relationship('Product')
    
    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity} (Size: {self.size})>'

# ==================== CONTACT MESSAGE MODEL ====================

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ContactMessage from {self.name}>'

# ==================== REVIEW MODEL ====================

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200))
    comment = db.Column(db.Text, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Review {self.id} - {self.rating}⭐>'

# ==================== HERO SLIDE MODEL ====================

class HeroSlide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(200))
    description = db.Column(db.Text)
    button_text = db.Column(db.String(50), default='Shop Now')
    button_link = db.Column(db.String(200), default='/shop')
    image = db.Column(db.String(200))
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<HeroSlide {self.title}>'

# ==================== NOTIFY ME MODEL ====================

class NotifyMe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    is_notified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product')
    
    def __repr__(self):
        return f'<NotifyMe for {self.product_name}>'