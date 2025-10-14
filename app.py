from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///kitchen.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://',
                                                                                          'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Database Models
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    unit = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    min_order_qty = db.Column(db.Float, default=1)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    ordered_by = db.Column(db.String(100))
    total_amount = db.Column(db.Float)
    status = db.Column(db.String(50), default='Confirmed')
    items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    item = db.relationship('Item', backref='order_items')


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))


# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['full_name'] = user.full_name
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid credentials')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/menu')
def menu():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    category = request.args.get('category', 'all')
    search = request.args.get('search', '')

    query = Item.query

    if category != 'all':
        query = query.filter_by(category=category)

    if search:
        query = query.filter(Item.name.ilike(f'%{search}%'))

    items = query.order_by(Item.category, Item.name).all()
    categories = db.session.query(Item.category).distinct().all()

    return render_template('menu.html',
                           items=items,
                           categories=[c[0] for c in categories],
                           current_category=category,
                           search=search)


@app.route('/api/items')
def api_items():
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')

    query = Item.query

    if category != 'all':
        query = query.filter_by(category=category)

    if search:
        query = query.filter(Item.name.ilike(f'%{search}%'))

    items = query.order_by(Item.category, Item.name).all()

    return jsonify([{
        'id': item.id,
        'name': item.name,
        'category': item.category,
        'unit': item.unit,
        'price': item.price,
        'min_order_qty': item.min_order_qty
    } for item in items])


@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('cart.html')


@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.json
    cart_items = data.get('items', [])

    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400

    # Create order
    order = Order(
        ordered_by=session.get('full_name', session.get('username')),
        total_amount=0,
        status='Confirmed'
    )
    db.session.add(order)
    db.session.flush()

    total = 0
    for cart_item in cart_items:
        item = Item.query.get(cart_item['id'])
        if item:
            quantity = float(cart_item['quantity'])
            subtotal = quantity * item.price
            total += subtotal

            order_item = OrderItem(
                order_id=order.id,
                item_id=item.id,
                quantity=quantity,
                unit_price=item.price,
                subtotal=subtotal
            )
            db.session.add(order_item)

    order.total_amount = total
    db.session.commit()

    return jsonify({
        'success': True,
        'order_id': order.id,
        'total': total
    })


@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    orders = Order.query.order_by(Order.order_date.desc()).all()
    return render_template('orders.html', orders=orders)


@app.route('/api/orders')
def api_orders():
    orders = Order.query.order_by(Order.order_date.desc()).limit(50).all()

    return jsonify([{
        'id': order.id,
        'order_date': order.order_date.strftime('%Y-%m-%d %H:%M'),
        'ordered_by': order.ordered_by,
        'total_amount': order.total_amount,
        'status': order.status,
        'items': [{
            'name': oi.item.name,
            'quantity': oi.quantity,
            'unit': oi.item.unit,
            'unit_price': oi.unit_price,
            'subtotal': oi.subtotal
        } for oi in order.items]
    } for order in orders])


@app.route('/api/budget')
def api_budget():
    from datetime import timedelta

    # Get this week's orders
    today = datetime.utcnow()
    week_start = today - timedelta(days=today.weekday())

    week_orders = Order.query.filter(Order.order_date >= week_start).all()
    week_total = sum(order.total_amount for order in week_orders)

    weekly_budget = 10000  # AED

    return jsonify({
        'weekly_budget': weekly_budget,
        'spent': week_total,
        'remaining': weekly_budget - week_total,
        'percentage': (week_total / weekly_budget * 100) if weekly_budget > 0 else 0
    })


# Initialize database
def init_db():
    with app.app_context():
        db.create_all()

        # Create default user if none exists
        if User.query.count() == 0:
            default_user = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                full_name='Administrator'
            )
            db.session.add(default_user)
            db.session.commit()
            print("Default user created: admin / admin123")


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)