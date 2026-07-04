import razorpay
import json
import hmac
import hashlib
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from models import db, Order

from config import Config

payment_bp = Blueprint('payment', __name__, url_prefix='/payment')

# Initialize Razorpay client
client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))


@payment_bp.route('/initiate', methods=['POST'])
# REMOVED: @login_required - Allow guest checkout
def initiate_payment():
    """Initiate payment for an order - Guest checkout enabled"""
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        amount = data.get('amount')
        currency = data.get('currency', 'INR')
        customer_name = data.get('customer_name')
        customer_email = data.get('customer_email')
        customer_phone = data.get('customer_phone')
        
        # Validate amount
        if not amount or amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        # Get order from database
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Check if order already has a razorpay order
        if order.razorpay_order_id:
            return jsonify({
                'success': True,
                'order_id': order.razorpay_order_id,
                'amount': float(amount),
                'currency': currency,
                'key_id': Config.RAZORPAY_KEY_ID,
                'customer_name': customer_name,
                'customer_email': customer_email,
                'customer_phone': customer_phone
            })
        
        # Create Razorpay order
        try:
            razorpay_order = client.order.create({
                'amount': int(amount * 100),  # Amount in paise
                'currency': currency,
                'payment_capture': 1,
                'receipt': f'order_{order_id}',
                'notes': {
                    'order_id': str(order_id),
                    'customer_name': customer_name,
                    'customer_email': customer_email
                }
            })
        except Exception as e:
            print(f"Razorpay order creation error: {e}")
            return jsonify({'error': f'Payment gateway error: {str(e)}'}), 500
        
        # Save razorpay_order_id to order
        order.razorpay_order_id = razorpay_order['id']
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order_id': razorpay_order['id'],
            'amount': float(amount),
            'currency': currency,
            'key_id': Config.RAZORPAY_KEY_ID,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone
        })
        
    except Exception as e:
        print(f"Payment initiation error: {e}")
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/verify', methods=['POST'])
# REMOVED: @login_required - Allow guest checkout
def verify_payment():
    """Verify payment signature - Guest checkout enabled"""
    try:
        data = request.get_json()
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')
        
        # Verify signature
        params_dict = {
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_order_id': razorpay_order_id,
            'razorpay_signature': razorpay_signature
        }
        
        client.utility.verify_payment_signature(params_dict)
        
        # Update order status
        order = Order.query.filter_by(razorpay_order_id=razorpay_order_id).first()
        if order:
            order.payment_status = 'paid'
            order.payment_id = razorpay_payment_id
            order.status = 'confirmed'
            db.session.commit()
            
            # Clear cart
            session.pop('cart', None)
            
            return jsonify({
                'success': True,
                'message': 'Payment verified successfully',
                'order_id': order.id
            })
        
        return jsonify({'error': 'Order not found'}), 404
        
    except razorpay.errors.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/webhook', methods=['POST'])
def webhook():
    """Handle Razorpay webhook for real-time updates"""
    try:
        # Verify webhook signature
        payload = request.get_data()
        signature = request.headers.get('X-Razorpay-Signature')
        
        # Verify signature
        expected_signature = hmac.new(
            Config.RAZORPAY_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        data = request.get_json()
        event = data.get('event')
        
        if event == 'payment.captured':
            payment_data = data.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment_data.get('notes', {}).get('order_id')
            payment_id = payment_data.get('id')
            
            if order_id:
                order = Order.query.get(int(order_id))
                if order:
                    order.payment_status = 'paid'
                    order.payment_id = payment_id
                    order.status = 'confirmed'
                    db.session.commit()
                    print(f"✅ Payment captured for order #{order.order_number}")
        
        elif event == 'payment.failed':
            payment_data = data.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment_data.get('notes', {}).get('order_id')
            
            if order_id:
                order = Order.query.get(int(order_id))
                if order:
                    order.payment_status = 'failed'
                    db.session.commit()
                    print(f"❌ Payment failed for order #{order.order_number}")
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ✅ ADDED: Payment Checkout Route
@payment_bp.route('/checkout/<int:order_id>')
def payment_checkout(order_id):
    """Payment checkout page - Guest checkout enabled"""
    from models import Product  # Import here to avoid circular imports
    
    order = Order.query.get_or_404(order_id)
    
    # Calculate cart items
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


@payment_bp.route('/success/<int:order_id>')
def payment_success(order_id):
    """Payment success page"""
    order = Order.query.get_or_404(order_id)
    session.pop('cart', None)
    return render_template('payment_success.html', order=order)


@payment_bp.route('/failed/<int:order_id>')
def payment_failed(order_id):
    """Payment failed page"""
    order = Order.query.get_or_404(order_id)
    return render_template('payment_failed.html', order=order)


@payment_bp.route('/retry/<int:order_id>')
# REMOVED: @login_required - Allow guest checkout
def payment_retry(order_id):
    """Retry payment for failed order - Guest checkout enabled"""
    order = Order.query.get_or_404(order_id)
    if order.payment_status == 'paid':
        flash('This order is already paid!', 'info')
        return redirect(url_for('payment.payment_success', order_id=order.id))
    
    return render_template('payment_retry.html', order=order)