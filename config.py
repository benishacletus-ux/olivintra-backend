import os
from dotenv import load_dotenv

load_dotenv()

# Get the absolute path to your project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'olivintra-secret-key-2026'
    
    # ==================== DATABASE CONFIGURATION ====================
    # ✅ Use Neon PostgreSQL (removed channel_binding parameter)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://neondb_owner:npg_6TzO5FmClygW@ep-odd-surf-atcwalt0-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    
    # ==================== UPLOAD CONFIGURATION ====================
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    
    # ==================== ADMIN CREDENTIALS ====================
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'olivintra'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'olivintra2026'
    
    # ==================== WHATSAPP INTEGRATION ====================
    WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER') or '+919037392700'
    WHATSAPP_URL = f'https://wa.me/{WHATSAPP_NUMBER}'
    
    # ==================== SESSION SETTINGS ====================
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # ==================== REMEMBER ME SETTINGS ====================
    REMEMBER_COOKIE_DURATION = 30 * 24 * 60 * 60  # 30 days
    REMEMBER_COOKIE_SECURE = False  # Set to True in production with HTTPS
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    
    # ==================== RAZORPAY PAYMENT CONFIGURATION ====================
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID') or 'rzp_test_YourKeyIdHere'
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET') or 'YourSecretKeyHere'
    RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET') or 'whsec_YourWebhookSecret'
    
    # ==================== PAYMENT SETTINGS ====================
    PAYMENT_CURRENCY = os.environ.get('PAYMENT_CURRENCY') or 'INR'
    PAYMENT_CAPTURE = os.environ.get('PAYMENT_CAPTURE') or 'automatic'
    
    # ==================== CLOUDINARY CONFIGURATION ====================
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME') or 'ehwp5jee'
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY') or '984251329922223'
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET') or 'T5z2nHBBkOF37KiBTdBJBccJKSA'
    
    # ==================== FREE SHIPPING THRESHOLD ====================
    FREE_SHIPPING_THRESHOLD = 2999  # Free shipping on orders above ₹2999
    SHIPPING_CHARGE = 60  # Flat shipping charge for orders below threshold

# ==================== CREATE UPLOAD FOLDER ====================
os.makedirs(os.path.join(BASE_DIR, 'static', 'uploads'), exist_ok=True)

# ==================== PRINT CONFIGURATION (for debugging) ====================
print("=" * 50)
print("📋 OLIVINTRA CONFIGURATION")
print("=" * 50)
print(f"✅ Database: PostgreSQL (Neon)")
print(f"📁 Upload folder: {Config.UPLOAD_FOLDER}")
print(f"💬 WhatsApp: {Config.WHATSAPP_URL}")
print(f"💳 Razorpay Key ID: {Config.RAZORPAY_KEY_ID[:15]}...")
print(f"☁️  Cloudinary: {Config.CLOUDINARY_CLOUD_NAME}")
print(f"🚚 Free Shipping: ₹{Config.FREE_SHIPPING_THRESHOLD}+")
print("=" * 50)