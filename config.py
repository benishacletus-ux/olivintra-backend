import os
from dotenv import load_dotenv

load_dotenv()

# Get the absolute path to your project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'olivintra-secret-key-2026'
    
    # Use absolute path for database - this is the most reliable method
    DB_PATH = os.path.join(BASE_DIR, 'olivintra.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder with absolute path
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'olivintra'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'olivintra2026'
    
    # WhatsApp Integration
    WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER') or '+919037392700'
    WHATSAPP_URL = f'https://wa.me/{WHATSAPP_NUMBER}'
    
    # ==================== SESSION SETTINGS ====================
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400
    
    # ==================== REMEMBER ME SETTINGS ====================
    REMEMBER_COOKIE_DURATION = 30 * 24 * 60 * 60
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    
    # ==================== RAZORPAY PAYMENT CONFIGURATION ====================
    # Get Razorpay keys from environment variables or use test keys
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID') or 'rzp_test_YourKeyIdHere'
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET') or 'YourSecretKeyHere'
    RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET') or 'whsec_YourWebhookSecret'
    
    # ==================== PAYMENT SETTINGS ====================
    PAYMENT_CURRENCY = os.environ.get('PAYMENT_CURRENCY') or 'INR'
    PAYMENT_CAPTURE = os.environ.get('PAYMENT_CAPTURE') or 'automatic'

# Create necessary folders
os.makedirs(os.path.join(BASE_DIR, 'static', 'uploads'), exist_ok=True)

print(f"Database will be created at: {Config.DB_PATH}")
print(f"Upload folder: {Config.UPLOAD_FOLDER}")
print(f"WhatsApp: {Config.WHATSAPP_URL}")
print(f"Razorpay Key ID: {Config.RAZORPAY_KEY_ID[:20]}... (hidden)")