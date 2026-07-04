from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_cors import CORS  # <-- ADDED
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
import secrets
import re
from functools import wraps

from config import Config
from models import db, Admin, Category, Product, Order, OrderItem, ContactMessage, Review, HeroSlide, User, UserActivity

# ========== IMPORT PAYMENT BLUEPRINT ==========
from payment_routes import payment_bp

app = Flask(__name__)
app.config.from_object(Config)

# ========== ADD CORS ==========
CORS(app)  # <-- ADDED - Allows Netlify to call your API

db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# ========== REGISTER PAYMENT BLUEPRINT ==========
app.register_blueprint(payment_bp)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
# COMPLETELY DISABLE all login messages
login_manager.login_message = None
login_manager.login_message_category = None
login_manager.needs_refresh_message = None
login_manager.needs_refresh_message_category = None

@login_manager.user_loader
def load_user(user_id):
    # Try Admin first (for admin routes)
    admin = Admin.query.get(int(user_id))
    if admin:
        return admin
    return None

# Create admin user if not exists
@app.before_request
def create_admin():
    if not Admin.query.first():
        admin = Admin(username=Config.ADMIN_USERNAME)
        admin.set_password(Config.ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()

@app.context_processor
def utility_processor():
    def cart_count():
        if 'cart' in session:
            return sum(item['quantity'] for item in session['cart'])
        return 0
    
    # WhatsApp Integration
    whatsapp_number = '+919037392700'
    whatsapp_url = f'https://wa.me/{whatsapp_number}'
    
    # Add datetime to templates
    def now():
        return datetime.now()
    
    return dict(
        cart_count=cart_count,
        whatsapp_number=whatsapp_number,
        whatsapp_url=whatsapp_url,
        datetime=datetime
    )

# ==================== HELPER FUNCTIONS ====================

def admin_required(f):
    """Decorator to check if user is admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login as admin to continue.', 'error')
            return redirect(url_for('admin_login'))
        # Check if user is Admin (not User)
        if not isinstance(current_user, Admin):
            flash('Access denied. Admin only.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def is_admin():
    """Check if current user is admin"""
    if not current_user.is_authenticated:
        return False
    return isinstance(current_user, Admin)

def update_product_rating(product_id):
    """Helper function to update product rating"""
    from models import Product, Review
    
    avg_rating = db.session.query(db.func.avg(Review.rating)).filter_by(
        product_id=product_id, 
        is_approved=True
    ).scalar() or 0
    
    product = db.session.get(Product, product_id)
    if product:
        product.rating = float(avg_rating)
        product.review_count = Review.query.filter_by(
            product_id=product_id, 
            is_approved=True
        ).count()
        db.session.commit()

# ==================== FRONTEND ROUTES ====================

@app.route('/')
def index():
    featured_products = Product.query.filter_by(is_featured=True).limit(6).all()
    best_sellers = Product.query.filter_by(is_best_seller=True).limit(6).all()
    new_arrivals = Product.query.filter_by(is_new_arrival=True).limit(6).all()
    categories = Category.query.all()
    hero_slides = HeroSlide.query.filter_by(is_active=True).order_by(HeroSlide.order).all()
    latest_reviews = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).limit(6).all()
    
    return render_template('index.html', 
                         featured_products=featured_products,
                         best_sellers=best_sellers,
                         new_arrivals=new_arrivals,
                         categories=categories,
                         latest_reviews=latest_reviews,
                         hero_slides=hero_slides)

# ==================== NEW ARRIVALS & BEST SELLERS SEPARATE PAGES ====================

@app.route('/new-arrivals')
def new_arrivals():
    """Show only new arrival products"""
    products = Product.query.filter_by(is_new_arrival=True).all()
    return render_template('new_arrivals.html', products=products)

@app.route('/best-sellers')
def best_sellers():
    """Show only best seller products"""
    products = Product.query.filter_by(is_best_seller=True).all()
    return render_template('best_sellers.html', products=products)

@app.route('/shop')
def shop():
    category_slug = request.args.get('category')
    search = request.args.get('search')
    sort = request.args.get('sort', 'newest')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    
    query = Product.query
    
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first()
        if category:
            query = query.filter_by(category_id=category.id)
    
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    
    search_suggestions = []
    if search:
        search_terms = search.strip().split()
        conditions = []
        for term in search_terms:
            conditions.append(Product.name.contains(term))
            conditions.append(Product.description.contains(term))
            conditions.append(Product.material.contains(term))
        
        if conditions:
            from sqlalchemy import or_
            query = query.filter(or_(*conditions))
        
        matching_products = Product.query.filter(
            db.or_(
                Product.name.contains(search),
                Product.description.contains(search),
                Product.material.contains(search)
            )
        ).limit(20).all()
        
        keywords = set()
        for product in matching_products:
            for word in product.name.split():
                if len(word) > 2 and word.lower() != search.lower():
                    keywords.add(word.lower())
            if product.category:
                for word in product.category.name.split():
                    if len(word) > 2 and word.lower() != search.lower():
                        keywords.add(word.lower())
            if product.material:
                for word in product.material.split():
                    if len(word) > 2 and word.lower() != search.lower():
                        keywords.add(word.lower())
        
        search_lower = search.lower()
        search_suggestions = [kw for kw in keywords if kw != search_lower][:8]
    
    if sort == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_high':
        query = query.order_by(Product.price.desc())
    elif sort == 'popular':
        query = query.order_by(Product.rating.desc())
    else:
        query = query.order_by(Product.created_at.desc())
    
    products = query.all()
    categories = Category.query.all()
    
    price_min = db.session.query(db.func.min(Product.price)).scalar() or 0
    price_max = db.session.query(db.func.max(Product.price)).scalar() or 10000
    
    price_ranges = [
        {'label': 'Under ₹500', 'min': 0, 'max': 500},
        {'label': '₹500 - ₹1,000', 'min': 500, 'max': 1000},
        {'label': '₹1,000 - ₹2,000', 'min': 1000, 'max': 2000},
        {'label': '₹2,000 - ₹5,000', 'min': 2000, 'max': 5000},
        {'label': '₹5,000 - ₹10,000', 'min': 5000, 'max': 10000},
        {'label': 'Above ₹10,000', 'min': 10000, 'max': None},
    ]
    
    return render_template('shop.html', 
                         products=products, 
                         categories=categories, 
                         selected_category=category_slug,
                         search=search,
                         search_suggestions=search_suggestions,
                         sort=sort,
                         min_price=min_price,
                         max_price=max_price,
                         price_min=price_min,
                         price_max=price_max,
                         price_ranges=price_ranges)

@app.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    related = Product.query.filter_by(category_id=product.category_id).filter(Product.id != product.id).limit(4).all()
    reviews = Review.query.filter_by(product_id=product.id, is_approved=True).order_by(Review.created_at.desc()).all()
    
    return render_template('product.html', product=product, related=related, reviews=reviews)

# ==================== CART ROUTES (Guest Checkout) ====================

@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))
    size = request.form.get('size', 'Standard')
    
    if 'cart' not in session:
        session['cart'] = []
    
    cart = session['cart']
    
    # Check if same product with same size already in cart
    for item in cart:
        if item['product_id'] == product_id and item.get('size') == size:
            item['quantity'] += quantity
            session.modified = True
            flash('Cart updated successfully!', 'success')
            return redirect(url_for('cart'))
    
    cart.append({'product_id': product_id, 'quantity': quantity, 'size': size})
    session.modified = True
    flash('Product added to cart!', 'success')
    return redirect(url_for('cart'))

@app.route('/remove-from-cart', methods=['POST'])
def remove_from_cart():
    product_id = request.form.get('product_id')
    
    if 'cart' in session:
        cart = session['cart']
        for item in cart[:]:
            if item['product_id'] == product_id:
                cart.remove(item)
                session.modified = True
                break
    
    return jsonify({'status': 'success', 'count': sum(i['quantity'] for i in session.get('cart', []))})

@app.route('/cart')
def cart():
    cart_items = []
    subtotal = 0
    if 'cart' in session:
        for item in session['cart']:
            product = db.session.get(Product, item['product_id'])
            if product:
                cart_items.append({
                    'product': product,
                    'quantity': item['quantity'],
                    'size': item.get('size', 'N/A')
                })
                subtotal += product.price * item['quantity']
    
    shipping = 60 if subtotal < 2999 else 0
    total = subtotal + shipping
    
    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal, shipping=shipping, total=total)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        cart_items = []
        subtotal = 0
        if 'cart' in session:
            for item in session['cart']:
                product = db.session.get(Product, item['product_id'])
                if product:
                    cart_items.append({
                        'product': product,
                        'quantity': item['quantity'],
                        'size': item.get('size', 'N/A')
                    })
                    subtotal += product.price * item['quantity']
        
        if not cart_items:
            flash('Your cart is empty', 'error')
            return redirect(url_for('shop'))
        
        # Calculate shipping
        shipping = 60 if subtotal < 2999 else 0
        total = subtotal + shipping
        
        order_number = f"OL-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
        
        order = Order(
            order_number=order_number,
            customer_name=request.form.get('name'),
            customer_email=request.form.get('email'),
            customer_phone=request.form.get('phone'),
            shipping_address=request.form.get('address'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            pincode=request.form.get('pincode'),
            total_amount=total,  # Now includes shipping
            payment_method='Razorpay',
            payment_status='pending',
            notes=request.form.get('notes'),
            user_id=None  # Guest checkout
        )
        db.session.add(order)
        db.session.flush()
        
        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item['product'].id,
                product_name=item['product'].name,
                quantity=item['quantity'],
                price=item['product'].price,
                size=item['size']
            )
            db.session.add(order_item)
        
        db.session.commit()
        
        # Redirect to payment page instead of confirmation
        flash('Please complete your payment to confirm the order.', 'info')
        return redirect(url_for('payment_checkout', order_id=order.id))
    
    # ========== GET REQUEST - Calculate cart items and total ==========
    cart_items = []
    subtotal = 0
    if 'cart' in session:
        for item in session['cart']:
            product = db.session.get(Product, item['product_id'])
            if product:
                cart_items.append({
                    'product': product,
                    'quantity': item['quantity'],
                    'size': item.get('size', 'N/A')
                })
                subtotal += product.price * item['quantity']
    
    shipping = 60 if subtotal < 2999 else 0
    total = subtotal + shipping
    
    return render_template('checkout.html', cart_items=cart_items, subtotal=subtotal, shipping=shipping, total=total)

# ==================== PAYMENT CHECKOUT ROUTE ====================

@app.route('/payment/checkout/<int:order_id>')
def payment_checkout(order_id):
    order = Order.query.get_or_404(order_id)
    
    cart_items = []
    subtotal = 0
    for item in order.items:
        product = Product.query.get(item.product_id)
        if product:
            cart_items.append({
                'product': product,
                'quantity': item.quantity,
                'size': item.size
            })
            subtotal += product.price * item.quantity
    
    shipping = 60 if subtotal < 2999 else 0
    total = subtotal + shipping
    
    return render_template('payment_checkout.html', 
                         order=order, 
                         cart_items=cart_items, 
                         subtotal=subtotal,
                         shipping=shipping,
                         total=total)

@app.route('/order-confirmation/<int:order_id>')
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_confirmation.html', order=order)

# ==================== MY ORDERS ROUTE - EMAIL ONLY ====================

@app.route('/my-orders', methods=['GET', 'POST'])
def my_orders():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if email:
            # Find all orders with this email
            orders = Order.query.filter_by(
                customer_email=email
            ).order_by(Order.created_at.desc()).all()
            
            if orders:
                return render_template('my_orders.html', orders=orders, searched=True, email=email)
            else:
                flash('No orders found with this email address', 'error')
                return render_template('my_orders.html', orders=[], searched=False, email=email)
        else:
            flash('Please enter your email address', 'error')
            return render_template('my_orders.html', orders=[], searched=False)
    
    # GET request - show search form
    return render_template('my_orders.html', orders=[], searched=False)

# ==================== SUBMIT REVIEW ROUTE ====================

@app.route('/submit-review', methods=['POST'])
def submit_review():
    product_id = request.form.get('product_id')
    order_id = request.form.get('order_id')
    rating = int(request.form.get('rating', 0))
    title = request.form.get('title')
    comment = request.form.get('comment')
    customer_name = request.form.get('customer_name')
    customer_email = request.form.get('customer_email')
    
    if not all([product_id, order_id, rating, comment, customer_name, customer_email]):
        flash('Please fill in all required fields', 'error')
        return redirect(url_for('my_orders'))
    
    if rating < 1 or rating > 5:
        flash('Please select a valid rating', 'error')
        return redirect(url_for('my_orders'))
    
    order = Order.query.get(order_id)
    if not order:
        flash('Invalid order', 'error')
        return redirect(url_for('my_orders'))
    
    order_item = OrderItem.query.filter_by(order_id=order_id, product_id=product_id).first()
    if not order_item:
        flash('You can only review products you purchased', 'error')
        return redirect(url_for('my_orders'))
    
    existing_review = Review.query.filter_by(product_id=product_id, order_id=order_id).first()
    if existing_review:
        flash('You have already reviewed this product', 'info')
        return redirect(url_for('my_orders'))
    
    review = Review(
        product_id=product_id,
        order_id=order_id,
        customer_name=customer_name,
        customer_email=customer_email,
        rating=rating,
        title=title,
        comment=comment,
        is_verified=True,
        is_approved=True
    )
    db.session.add(review)
    db.session.commit()
    
    update_product_rating(product_id)
    
    flash('Thank you for your review!', 'success')
    return redirect(url_for('my_orders'))

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        message = ContactMessage(
            name=request.form.get('name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            message=request.form.get('message')
        )
        db.session.add(message)
        db.session.commit()
        flash('Thank you for your message!', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about.html')

# ==================== LEGAL POLICY ROUTES ====================

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/shipping-policy')
def shipping_policy():
    return render_template('shipping_policy.html')

@app.route('/return-policy')
def return_policy():
    return render_template('return_policy.html')

@app.route('/cancellation-policy')
def cancellation_policy():
    return render_template('cancellation_policy.html')

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    if email:
        flash('Thank you for subscribing!', 'success')
    return redirect(url_for('index'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # If already logged in as admin, go to dashboard
    if current_user.is_authenticated and isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            login_user(admin)
            flash('✅ Admin login successful! Welcome to Admin Panel.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('❌ Invalid admin username or password.', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    if not isinstance(current_user, Admin):
        flash('Access denied. Admin only.', 'error')
        return redirect(url_for('admin_login'))
    
    total_products = Product.query.count()
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    confirmed_orders = Order.query.filter_by(status='confirmed').count()
    shipped_orders = Order.query.filter_by(status='shipped').count()
    delivered_orders = Order.query.filter_by(status='delivered').count()
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).filter(Order.status != 'cancelled').scalar() or 0
    unread_messages = ContactMessage.query.filter_by(is_read=False).count()
    pending_reviews = Review.query.filter_by(is_approved=False).count()
    
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    recent_messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_products=total_products,
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         confirmed_orders=confirmed_orders,
                         shipped_orders=shipped_orders,
                         delivered_orders=delivered_orders,
                         total_revenue=total_revenue,
                         unread_messages=unread_messages,
                         pending_reviews=pending_reviews,
                         recent_orders=recent_orders,
                         recent_messages=recent_messages)

# ==================== ADMIN NOTIFICATIONS API ====================

@app.route('/admin/notifications/count')
@login_required
@admin_required
def admin_notifications_count():
    """Get real-time notification counts for admin panel"""
    try:
        pending_orders = Order.query.filter_by(status='pending').count()
        pending_reviews = Review.query.filter_by(is_approved=False).count()
        unread_messages = ContactMessage.query.filter_by(is_read=False).count()
        
        return jsonify({
            'pending_orders': pending_orders,
            'pending_reviews': pending_reviews,
            'unread_messages': unread_messages,
            'total': pending_orders + pending_reviews + unread_messages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ADMIN STOCK MANAGEMENT ROUTES ====================

@app.route('/admin/stock-management')
@login_required
@admin_required
def admin_stock_management():
    """Admin: Stock management page"""
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/stock_management.html', products=products)

@app.route('/admin/product/update-stock', methods=['POST'])
@login_required
@admin_required
def admin_update_stock():
    """Admin: Update product stock status"""
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        in_stock = data.get('in_stock')
        
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404
        
        product.in_stock = in_stock
        if in_stock and product.stock == 0:
            product.stock = 1
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Stock updated for {product.name}',
            'product_id': product_id,
            'in_stock': in_stock
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/product/bulk-update-stock', methods=['POST'])
@login_required
@admin_required
def admin_bulk_update_stock():
    """Admin: Bulk update stock status"""
    try:
        data = request.get_json()
        updates = data.get('updates', [])
        
        updated_count = 0
        for update in updates:
            product = db.session.get(Product, update.get('product_id'))
            if product:
                product.in_stock = update.get('in_stock')
                if product.in_stock and product.stock == 0:
                    product.stock = 1
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} products',
            'updated_count': updated_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/products/stock-data')
@login_required
@admin_required
def admin_products_stock_data():
    """Admin: Get all products with stock status as JSON"""
    products = Product.query.order_by(Product.created_at.desc()).all()
    
    product_data = []
    for product in products:
        product_data.append({
            'id': product.id,
            'name': product.name,
            'slug': product.slug,
            'price': product.price,
            'image': product.image,
            'stock': product.stock,
            'in_stock': product.in_stock,
            'created_at': product.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return jsonify({'products': product_data})

# ==================== REAL-TIME ORDER COUNT API ====================

@app.route('/admin/orders/count')
@login_required
@admin_required
def admin_orders_count():
    """Get real-time order counts for dashboard"""
    try:
        total = Order.query.count()
        pending = Order.query.filter_by(status='pending').count()
        confirmed = Order.query.filter_by(status='confirmed').count()
        shipped = Order.query.filter_by(status='shipped').count()
        delivered = Order.query.filter_by(status='delivered').count()
        completed = Order.query.filter_by(status='completed').count()
        
        return jsonify({
            'total': total,
            'pending': pending,
            'confirmed': confirmed,
            'shipped': shipped,
            'delivered': delivered,
            'completed': completed
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ADMIN DASHBOARD ANALYTICS API ====================

@app.route('/admin/analytics/data')
@login_required
@admin_required
def admin_analytics_data():
    """Get real-time analytics data for dashboard including today, yesterday, month, year revenue"""
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        week_ago = today - timedelta(days=6)
        
        # Today's revenue and orders
        today_data = db.session.query(
            func.sum(Order.total_amount).label('revenue'),
            func.count(Order.id).label('count')
        ).filter(
            func.date(Order.created_at) == today,
            Order.status != 'cancelled'
        ).first()
        
        # Yesterday's revenue and orders
        yesterday_data = db.session.query(
            func.sum(Order.total_amount).label('revenue'),
            func.count(Order.id).label('count')
        ).filter(
            func.date(Order.created_at) == yesterday,
            Order.status != 'cancelled'
        ).first()
        
        # Month's revenue and orders
        month_data = db.session.query(
            func.sum(Order.total_amount).label('revenue'),
            func.count(Order.id).label('count')
        ).filter(
            func.date(Order.created_at) >= month_start,
            Order.status != 'cancelled'
        ).first()
        
        # Year's revenue and orders
        year_data = db.session.query(
            func.sum(Order.total_amount).label('revenue'),
            func.count(Order.id).label('count')
        ).filter(
            func.date(Order.created_at) >= year_start,
            Order.status != 'cancelled'
        ).first()
        
        # Daily orders and revenue for charts (last 7 days)
        daily_orders = db.session.query(
            func.date(Order.created_at).label('date'),
            func.count(Order.id).label('count')
        ).filter(
            func.date(Order.created_at) >= week_ago
        ).group_by(
            func.date(Order.created_at)
        ).all()
        
        daily_revenue = db.session.query(
            func.date(Order.created_at).label('date'),
            func.sum(Order.total_amount).label('total')
        ).filter(
            func.date(Order.created_at) >= week_ago,
            Order.status != 'cancelled'
        ).group_by(
            func.date(Order.created_at)
        ).all()
        
        # Prepare chart data
        days = []
        orders = []
        revenue = []
        
        for i in range(7):
            date_obj = week_ago + timedelta(days=i)
            date_str = date_obj.strftime('%a')
            days.append(date_str)
            
            order_count = 0
            for d in daily_orders:
                if d.date == date_obj:
                    order_count = d.count
                    break
            orders.append(order_count)
            
            revenue_amount = 0
            for d in daily_revenue:
                if d.date == date_obj:
                    revenue_amount = float(d.total or 0)
                    break
            revenue.append(revenue_amount)
        
        # Total counts
        total_orders = Order.query.count()
        pending_orders = Order.query.filter_by(status='pending').count()
        confirmed_orders = Order.query.filter_by(status='confirmed').count()
        shipped_orders = Order.query.filter_by(status='shipped').count()
        delivered_orders = Order.query.filter_by(status='delivered').count()
        total_revenue = db.session.query(func.sum(Order.total_amount)).filter(Order.status != 'cancelled').scalar() or 0
        
        return jsonify({
            'today_revenue': float(today_data.revenue or 0) if today_data else 0,
            'today_orders': today_data.count or 0 if today_data else 0,
            'yesterday_revenue': float(yesterday_data.revenue or 0) if yesterday_data else 0,
            'yesterday_orders': yesterday_data.count or 0 if yesterday_data else 0,
            'month_revenue': float(month_data.revenue or 0) if month_data else 0,
            'month_orders': month_data.count or 0 if month_data else 0,
            'year_revenue': float(year_data.revenue or 0) if year_data else 0,
            'year_orders': year_data.count or 0 if year_data else 0,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'confirmed_orders': confirmed_orders,
            'shipped_orders': shipped_orders,
            'delivered_orders': delivered_orders,
            'total_revenue': float(total_revenue or 0),
            'avg_order': float(total_revenue / total_orders if total_orders > 0 else 0),
            'days': days,
            'orders': orders,
            'revenue': revenue
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# ==================== ADMIN RECENT ORDERS & MESSAGES API ====================

@app.route('/admin/recent-orders')
@login_required
@admin_required
def admin_recent_orders():
    """Get recent orders for dashboard"""
    try:
        orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
        order_data = [{
            'id': o.id,
            'order_number': o.order_number,
            'customer_name': o.customer_name,
            'total_amount': float(o.total_amount),
            'status': o.status,
            'created_at': o.created_at.isoformat() if o.created_at else None
        } for o in orders]
        return jsonify(order_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/recent-messages')
@login_required
@admin_required
def admin_recent_messages():
    """Get recent messages for dashboard"""
    try:
        messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all()
        message_data = [{
            'id': m.id,
            'name': m.name,
            'email': m.email,
            'message': m.message,
            'is_read': m.is_read,
            'created_at': m.created_at.isoformat() if m.created_at else None
        } for m in messages]
        return jsonify(message_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== REST OF ADMIN ROUTES ====================

@app.route('/admin/products')
@login_required
@admin_required
def admin_products():
    products = Product.query.all()
    return render_template('admin/products.html', products=products)

# ==================== FIXED: ADMIN ADD PRODUCT WITH SIZE HANDLING ====================

@app.route('/admin/product/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_product():
    categories = Category.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug') or re.sub(r'[^a-z0-9-]', '-', name.lower().replace(' ', '-'))
        
        # Check for duplicate slug
        existing_product = Product.query.filter_by(slug=slug).first()
        if existing_product:
            import random
            import string
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            slug = f"{slug}-{random_suffix}"
            flash(f'Slug already exists. Using "{slug}" instead.', 'info')
        
        description = request.form.get('description')
        price = float(request.form.get('price'))
        original_price = request.form.get('original_price')
        category_id = request.form.get('category_id')
        is_featured = request.form.get('is_featured') == 'on'
        is_best_seller = request.form.get('is_best_seller') == 'on'
        is_new_arrival = request.form.get('is_new_arrival') == 'on'
        stock = int(request.form.get('stock', 0))
        material = request.form.get('material')
        care_instructions = request.form.get('care_instructions')
        
        # ============ FIX: Handle sizes properly ============
        sizes_str = request.form.get('sizes', '').strip()
        if sizes_str:
            # Clean up the string - remove extra quotes and brackets
            sizes_str = sizes_str.replace('\\"', '"').replace('"[', '[').replace(']"', ']').replace('""', '"')
            # Remove leading/trailing quotes if present
            if sizes_str.startswith('"') and sizes_str.endswith('"'):
                sizes_str = sizes_str[1:-1]
            # Try to parse as JSON if it's a JSON string
            try:
                sizes_list = json.loads(sizes_str)
                if isinstance(sizes_list, list):
                    sizes_json = json.dumps(sizes_list)
                else:
                    # If it's a comma-separated string
                    sizes_list = [s.strip() for s in str(sizes_list).split(',') if s.strip()]
                    sizes_json = json.dumps(sizes_list)
            except:
                # If JSON parsing fails, treat as comma-separated
                sizes_list = [s.strip() for s in sizes_str.split(',') if s.strip()]
                sizes_json = json.dumps(sizes_list)
        else:
            sizes_json = None
        
        # Handle main image
        image = None
        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            filename = secure_filename(file.filename)
            filename = f"product_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image = filename
        
        images_list = []
        if 'images[]' in request.files:
            files = request.files.getlist('images[]')
            
            if len(files) > 5:
                flash('Maximum 5 additional images allowed', 'error')
                return render_template('admin/add_product.html', categories=categories)
            
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    filename = f"product_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    images_list.append(filename)
        
        product = Product(
            name=name,
            slug=slug,
            description=description,
            price=price,
            original_price=float(original_price) if original_price else None,
            image=image,
            category_id=category_id if category_id else None,
            is_featured=is_featured,
            is_best_seller=is_best_seller,
            is_new_arrival=is_new_arrival,
            stock=stock,
            in_stock=stock > 0,
            material=material,
            care_instructions=care_instructions,
            sizes=sizes_json
        )
        product.set_images(images_list)
        
        db.session.add(product)
        db.session.commit()
        sizes_list_display = json.loads(sizes_json) if sizes_json else []
        flash(f'Product added successfully with {len(images_list)} additional images and {len(sizes_list_display)} sizes', 'success')
        return redirect(url_for('admin_products'))
    
    return render_template('admin/add_product.html', categories=categories)

# ==================== FIXED: ADMIN EDIT PRODUCT WITH SIZE HANDLING ====================

@app.route('/admin/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_product(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.all()
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.slug = request.form.get('slug') or re.sub(r'[^a-z0-9-]', '-', product.name.lower().replace(' ', '-'))
        
        # Check if slug is taken by another product
        existing = Product.query.filter_by(slug=product.slug).first()
        if existing and existing.id != product.id:
            import random
            import string
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            product.slug = f"{product.slug}-{random_suffix}"
            flash(f'Slug already exists. Using "{product.slug}" instead.', 'info')
        
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.original_price = float(request.form.get('original_price')) if request.form.get('original_price') else None
        product.category_id = request.form.get('category_id') if request.form.get('category_id') else None
        product.is_featured = request.form.get('is_featured') == 'on'
        product.is_best_seller = request.form.get('is_best_seller') == 'on'
        product.is_new_arrival = request.form.get('is_new_arrival') == 'on'
        product.stock = int(request.form.get('stock', 0))
        product.material = request.form.get('material')
        product.care_instructions = request.form.get('care_instructions')
        
        # ============ FIX: Handle sizes properly ============
        sizes_str = request.form.get('sizes', '').strip()
        if sizes_str:
            # Clean up the string - remove extra quotes and brackets
            sizes_str = sizes_str.replace('\\"', '"').replace('"[', '[').replace(']"', ']').replace('""', '"')
            # Remove leading/trailing quotes if present
            if sizes_str.startswith('"') and sizes_str.endswith('"'):
                sizes_str = sizes_str[1:-1]
            # Try to parse as JSON if it's a JSON string
            try:
                sizes_list = json.loads(sizes_str)
                if isinstance(sizes_list, list):
                    product.sizes = json.dumps(sizes_list)
                else:
                    # If it's a comma-separated string
                    sizes_list = [s.strip() for s in str(sizes_list).split(',') if s.strip()]
                    product.sizes = json.dumps(sizes_list)
            except:
                # If JSON parsing fails, treat as comma-separated
                sizes_list = [s.strip() for s in sizes_str.split(',') if s.strip()]
                product.sizes = json.dumps(sizes_list)
        else:
            product.sizes = None
        
        # Handle main image
        if 'image' in request.files and request.files['image'].filename:
            if product.image:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            file = request.files['image']
            filename = secure_filename(file.filename)
            filename = f"product_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            product.image = filename
        
        # Handle additional images
        if 'images[]' in request.files:
            files = request.files.getlist('images[]')
            current_images = product.get_images()
            
            if len(current_images) + len(files) > 5:
                flash(f'Maximum 5 additional images allowed. You already have {len(current_images)} images.', 'error')
                return render_template('admin/edit_product.html', product=product, categories=categories)
            
            new_images = []
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    filename = f"product_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    new_images.append(filename)
            
            current_images.extend(new_images)
            product.set_images(current_images)
        
        db.session.commit()
        flash('Product updated successfully', 'success')
        return redirect(url_for('admin_products'))
    
    return render_template('admin/edit_product.html', product=product, categories=categories)

# ==================== FIXED: ADMIN DELETE PRODUCT WITH AJAX SUPPORT ====================

@app.route('/admin/product/delete/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_delete_product(id):
    product = Product.query.get_or_404(id)
    
    try:
        # Delete main image
        if product.image:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
            if os.path.exists(old_path):
                os.remove(old_path)
        
        # Delete additional images
        images = product.get_images()
        for img in images:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], img)
            if os.path.exists(old_path):
                os.remove(old_path)
        
        # Delete product
        db.session.delete(product)
        db.session.commit()
        
        # Check if AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Product deleted successfully'})
        
        flash('Product deleted successfully', 'success')
        return redirect(url_for('admin_products'))
        
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        
        flash('Error deleting product: ' + str(e), 'error')
        return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    status = request.args.get('status')
    query = Order.query
    if status:
        query = query.filter_by(status=status)
    orders = query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/order/<int:id>')
@login_required
@admin_required
def admin_order_detail(id):
    order = Order.query.get_or_404(id)
    return render_template('admin/order_detail.html', order=order)

@app.route('/admin/order/update-status/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_update_order_status(id):
    order = Order.query.get_or_404(id)
    order.status = request.form.get('status')
    db.session.commit()
    flash('Order status updated', 'success')
    return redirect(url_for('admin_order_detail', id=id))

@app.route('/admin/categories')
@login_required
@admin_required
def admin_categories():
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/category/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_category():
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug') or re.sub(r'[^a-z0-9-]', '-', name.lower().replace(' ', '-'))
        description = request.form.get('description')
        
        image = None
        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            filename = secure_filename(file.filename)
            filename = f"category_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image = filename
        
        category = Category(name=name, slug=slug, description=description, image=image)
        db.session.add(category)
        db.session.commit()
        flash('Category added successfully', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/add_category.html')

@app.route('/admin/category/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_category(id):
    category = Category.query.get_or_404(id)
    
    if request.method == 'POST':
        category.name = request.form.get('name')
        category.slug = request.form.get('slug') or re.sub(r'[^a-z0-9-]', '-', category.name.lower().replace(' ', '-'))
        category.description = request.form.get('description')
        
        if 'image' in request.files and request.files['image'].filename:
            if category.image:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], category.image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            file = request.files['image']
            filename = secure_filename(file.filename)
            filename = f"category_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            category.image = filename
        
        db.session.commit()
        flash('Category updated successfully', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/edit_category.html', category=category)

@app.route('/admin/category/delete/<int:id>')
@login_required
@admin_required
def admin_delete_category(id):
    category = Category.query.get_or_404(id)
    
    if category.image:
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], category.image)
        if os.path.exists(old_path):
            os.remove(old_path)
    
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/messages')
@login_required
@admin_required
def admin_messages():
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)

@app.route('/admin/message/read/<int:id>')
@login_required
@admin_required
def admin_message_read(id):
    message = ContactMessage.query.get_or_404(id)
    message.is_read = True
    db.session.commit()
    flash('Message marked as read', 'success')
    return redirect(url_for('admin_messages'))

@app.route('/admin/message/delete/<int:id>')
@login_required
@admin_required
def admin_message_delete(id):
    message = ContactMessage.query.get_or_404(id)
    db.session.delete(message)
    db.session.commit()
    flash('Message deleted', 'success')
    return redirect(url_for('admin_messages'))

# ==================== ADMIN REVIEW ROUTES - COMPLETE ====================

@app.route('/admin/reviews')
@login_required
@admin_required
def admin_reviews():
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template('admin/reviews.html', reviews=reviews)

@app.route('/admin/review/approve/<int:id>')
@login_required
@admin_required
def admin_review_approve(id):
    review = Review.query.get_or_404(id)
    review.is_approved = True
    db.session.commit()
    update_product_rating(review.product_id)
    flash('Review approved successfully', 'success')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/review/unapprove/<int:id>')
@login_required
@admin_required
def admin_review_unapprove(id):
    review = Review.query.get_or_404(id)
    review.is_approved = False
    db.session.commit()
    update_product_rating(review.product_id)
    flash('Review unapproved', 'info')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/review/verify/<int:id>')
@login_required
@admin_required
def admin_review_verify(id):
    review = Review.query.get_or_404(id)
    review.is_verified = True
    db.session.commit()
    flash('Review marked as verified', 'success')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/review/unverify/<int:id>')
@login_required
@admin_required
def admin_review_unverify(id):
    review = Review.query.get_or_404(id)
    review.is_verified = False
    db.session.commit()
    flash('Review unverified', 'info')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/review/delete/<int:id>')
@login_required
@admin_required
def admin_review_delete(id):
    review = Review.query.get_or_404(id)
    product_id = review.product_id
    db.session.delete(review)
    db.session.commit()
    update_product_rating(product_id)
    flash('Review deleted successfully', 'success')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/hero')
@login_required
@admin_required
def admin_hero():
    slides = HeroSlide.query.order_by(HeroSlide.order).all()
    return render_template('admin/hero.html', slides=slides)

@app.route('/admin/hero/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_hero_add():
    if request.method == 'POST':
        title = request.form.get('title')
        subtitle = request.form.get('subtitle')
        description = request.form.get('description')
        button_text = request.form.get('button_text')
        button_link = request.form.get('button_link')
        order = int(request.form.get('order', 0))
        is_active = request.form.get('is_active') == 'on'
        
        image = None
        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            filename = secure_filename(file.filename)
            filename = f"hero_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image = filename
        
        slide = HeroSlide(
            title=title,
            subtitle=subtitle,
            description=description,
            button_text=button_text,
            button_link=button_link,
            image=image,
            order=order,
            is_active=is_active
        )
        db.session.add(slide)
        db.session.commit()
        flash('Hero slide added successfully', 'success')
        return redirect(url_for('admin_hero'))
    
    return render_template('admin/hero_add.html')

@app.route('/admin/hero/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_hero_edit(id):
    slide = HeroSlide.query.get_or_404(id)
    
    if request.method == 'POST':
        slide.title = request.form.get('title')
        slide.subtitle = request.form.get('subtitle')
        slide.description = request.form.get('description')
        slide.button_text = request.form.get('button_text')
        slide.button_link = request.form.get('button_link')
        slide.order = int(request.form.get('order', 0))
        slide.is_active = request.form.get('is_active') == 'on'
        
        if 'image' in request.files and request.files['image'].filename:
            if slide.image:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], slide.image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            file = request.files['image']
            filename = secure_filename(file.filename)
            filename = f"hero_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            slide.image = filename
        
        db.session.commit()
        flash('Hero slide updated successfully', 'success')
        return redirect(url_for('admin_hero'))
    
    return render_template('admin/hero_edit.html', slide=slide)

@app.route('/admin/hero/delete/<int:id>')
@login_required
@admin_required
def admin_hero_delete(id):
    slide = HeroSlide.query.get_or_404(id)
    if slide.image:
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], slide.image)
        if os.path.exists(old_path):
            os.remove(old_path)
    db.session.delete(slide)
    db.session.commit()
    flash('Hero slide deleted successfully', 'success')
    return redirect(url_for('admin_hero'))

# ==================== ADMIN HERO TOGGLE ROUTE ====================

@app.route('/admin/hero/toggle/<int:id>')
@login_required
@admin_required
def admin_hero_toggle(id):
    """Toggle hero slide active status"""
    slide = HeroSlide.query.get_or_404(id)
    slide.is_active = not slide.is_active
    db.session.commit()
    status = 'activated' if slide.is_active else 'deactivated'
    flash(f'Hero slide "{slide.title}" {status} successfully!', 'success')
    return redirect(url_for('admin_hero'))

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return "Internal Server Error", 500

# ==================== CREATE TABLES ====================
with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Add escapejs filter for Jinja2
@app.template_filter('escapejs')
def escapejs_filter(value):
    """Escape JavaScript string"""
    if value is None:
        return ''
    # Escape single quotes and backslashes
    return value.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')

# ==================== API ROUTES FOR FRONTEND ====================

@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'API is running',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/products', methods=['GET'])
def api_products():
    """Get all products as JSON"""
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'slug': p.slug,
        'price': float(p.price),
        'original_price': float(p.original_price) if p.original_price else None,
        'description': p.description,
        'image': p.image,
        'category': p.category.name if p.category else None,
        'in_stock': p.in_stock,
        'rating': float(p.rating) if p.rating else 0,
        'created_at': p.created_at.isoformat() if p.created_at else None
    } for p in products])

@app.route('/api/product/<slug>', methods=['GET'])
def api_product_detail(slug):
    """Get single product as JSON"""
    product = Product.query.filter_by(slug=slug).first()
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'id': product.id,
        'name': product.name,
        'slug': product.slug,
        'price': float(product.price),
        'original_price': float(product.original_price) if product.original_price else None,
        'description': product.description,
        'image': product.image,
        'images': product.get_images(),
        'category': product.category.name if product.category else None,
        'category_id': product.category_id,
        'in_stock': product.in_stock,
        'stock': product.stock,
        'rating': float(product.rating) if product.rating else 0,
        'review_count': product.review_count or 0,
        'sizes': json.loads(product.sizes) if product.sizes else [],
        'material': product.material,
        'care_instructions': product.care_instructions,
        'is_featured': product.is_featured,
        'is_best_seller': product.is_best_seller,
        'is_new_arrival': product.is_new_arrival,
        'created_at': product.created_at.isoformat() if product.created_at else None
    })

@app.route('/api/categories', methods=['GET'])
def api_categories():
    """Get all categories as JSON"""
    categories = Category.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'slug': c.slug,
        'description': c.description,
        'image': c.image
    } for c in categories])

# ==================== HERO SLIDES API ====================

@app.route('/api/hero-slides', methods=['GET'])
def api_hero_slides():
    """Get hero slides as JSON"""
    try:
        slides = HeroSlide.query.filter_by(is_active=True).order_by(HeroSlide.order).all()
        return jsonify([{
            'id': s.id,
            'title': s.title,
            'subtitle': s.subtitle,
            'description': s.description,
            'button_text': s.button_text,
            'button_link': s.button_link,
            'image': s.image,
            'order': s.order,
            'is_active': s.is_active,
            'created_at': s.created_at.isoformat() if s.created_at else None
        } for s in slides])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/create-order', methods=['POST'])
def api_create_order():
    """Create order from frontend"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'address', 'city', 'state', 'pincode', 'cart_items']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        # Calculate subtotal
        subtotal = 0
        cart_items_data = []
        for item in data['cart_items']:
            product = Product.query.get(item['product_id'])
            if not product:
                return jsonify({'success': False, 'error': f'Product {item["product_id"]} not found'}), 404
            subtotal += product.price * item['quantity']
            cart_items_data.append({
                'product': product,
                'quantity': item['quantity'],
                'size': item.get('size', 'N/A')
            })
        
        shipping = 60 if subtotal < 2999 else 0
        total = subtotal + shipping
        
        # Generate order number
        order_number = f"OL-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
        
        # Create order
        order = Order(
            order_number=order_number,
            customer_name=data['name'],
            customer_email=data['email'],
            customer_phone=data['phone'],
            shipping_address=data['address'],
            city=data['city'],
            state=data['state'],
            pincode=data['pincode'],
            total_amount=total,
            payment_method='Razorpay',
            payment_status='pending',
            notes=data.get('notes', ''),
            user_id=None
        )
        db.session.add(order)
        db.session.flush()
        
        # Add order items
        for item in cart_items_data:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item['product'].id,
                product_name=item['product'].name,
                quantity=item['quantity'],
                price=item['product'].price,
                size=item['size']
            )
            db.session.add(order_item)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order_id': order.id,
            'order_number': order.order_number,
            'total_amount': float(total),
            'subtotal': float(subtotal),
            'shipping': float(shipping)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/verify-payment', methods=['POST'])
def api_verify_payment():
    """Verify payment from frontend"""
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        payment_id = data.get('payment_id')
        signature = data.get('signature')
        
        # Your Razorpay verification logic here
        # This is a placeholder - you'll integrate with your payment_routes.py
        
        # Update order status
        order = Order.query.get(order_id)
        if order:
            order.payment_status = 'paid'
            order.status = 'confirmed'
            order.razorpay_payment_id = payment_id
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment verified',
            'order_id': order_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/order/<int:order_id>', methods=['GET'])
def api_get_order(order_id):
    """Get order details as JSON"""
    order = Order.query.get_or_404(order_id)
    return jsonify({
        'id': order.id,
        'order_number': order.order_number,
        'customer_name': order.customer_name,
        'customer_email': order.customer_email,
        'customer_phone': order.customer_phone,
        'shipping_address': order.shipping_address,
        'city': order.city,
        'state': order.state,
        'pincode': order.pincode,
        'total_amount': float(order.total_amount),
        'status': order.status,
        'payment_status': order.payment_status,
        'payment_method': order.payment_method,
        'created_at': order.created_at.isoformat() if order.created_at else None,
        'items': [{
            'product_name': item.product_name,
            'quantity': item.quantity,
            'price': float(item.price),
            'size': item.size
        } for item in order.items]
    })

@app.route('/api/my-orders', methods=['POST'])
def api_my_orders():
    """Get orders by email"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        orders = Order.query.filter_by(customer_email=email).order_by(Order.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'orders': [{
                'id': o.id,
                'order_number': o.order_number,
                'total_amount': float(o.total_amount),
                'status': o.status,
                'payment_status': o.payment_status,
                'created_at': o.created_at.isoformat() if o.created_at else None,
                'items': [{
                    'product_name': item.product_name,
                    'quantity': item.quantity,
                    'price': float(item.price),
                    'size': item.size
                } for item in o.items]
            } for o in orders]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/submit-review', methods=['POST'])
def api_submit_review():
    """Submit review from frontend"""
    try:
        data = request.get_json()
        
        required_fields = ['product_id', 'order_id', 'rating', 'comment', 'customer_name', 'customer_email']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        # Check if already reviewed
        existing_review = Review.query.filter_by(
            product_id=data['product_id'],
            order_id=data['order_id']
        ).first()
        
        if existing_review:
            return jsonify({'success': False, 'error': 'You have already reviewed this product'}), 400
        
        review = Review(
            product_id=data['product_id'],
            order_id=data['order_id'],
            customer_name=data['customer_name'],
            customer_email=data['customer_email'],
            rating=data['rating'],
            title=data.get('title', ''),
            comment=data['comment'],
            is_verified=True,
            is_approved=True
        )
        db.session.add(review)
        db.session.commit()
        
        update_product_rating(data['product_id'])
        
        return jsonify({
            'success': True,
            'message': 'Review submitted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/contact', methods=['POST'])
def api_contact():
    """Submit contact form from frontend"""
    try:
        data = request.get_json()
        
        required_fields = ['name', 'email', 'message']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        message = ContactMessage(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone', ''),
            message=data['message']
        )
        db.session.add(message)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Message sent successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUN APP ====================
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Olivintra is starting...")
    print("=" * 50)
    print("🌐 Server running at:")
    print("   http://127.0.0.1:5000")
    print("   http://localhost:5000")
    print("🔐 Admin login: http://localhost:5000/admin/login")
    print("👤 Admin Username: olivintra")
    print("🔑 Admin Password: olivintra2026")
    print("=" * 50)
    print("📦 Guest Checkout: Enabled (No login required)")
    print("📋 My Orders: http://localhost:5000/my-orders (Search by email only)")
    print("📊 Admin Analytics: http://localhost:5000/admin")
    print("🔔 Admin Notifications: http://localhost:5000/admin/notifications/count")
    print("=" * 50)
    print("🔄 API Endpoints added for frontend:")
    print("   /api/health")
    print("   /api/products")
    print("   /api/product/<slug>")
    print("   /api/categories")
    print("   /api/hero-slides")
    print("   /api/create-order")
    print("   /api/verify-payment")
    print("   /api/order/<id>")
    print("   /api/my-orders")
    print("   /api/submit-review")
    print("   /api/contact")
    print("=" * 50)
    print("Press CTRL+C to stop")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)