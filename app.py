from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from models import FoodOrder, User, db
from forms import LoginForm, RegistrationForm  # Import RegistrationForm if used
from datetime import datetime,time
from flask_migrate import Migrate
from models import db
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy import Column, Integer, String, DateTime
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_object('config.Config')
db.init_app(app)
migrate = Migrate(app, db)

app = Flask(__name__)
app.config.from_object('config.Config')
db.init_app(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('order'))
        else:
            flash('Login unsuccessful. Check email and password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))





# Import RegistrationForm if used

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered. Please use a different email.', 'warning')
            return redirect(url_for('register'))
        
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(email=form.email.data, password=hashed_password, role=form.role.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You are now able to log in.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()  # Rollback the session to avoid partial commits
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('register'))
    
    return render_template('register.html', form=form)



@app.route('/order', methods=['GET', 'POST'])
@login_required
def order():
    if request.method == 'POST':
        table_id = request.form['table_id']
        customer_name = current_user.email  # Use current_user.email for customer_name
        food_items = request.form.getlist('food_items')

        # Check if there's already an order for this table ID and customer
        existing_order = FoodOrder.query.filter_by(
            table_id=table_id,
            customer_name=customer_name,
            status='Cooking'
        ).first()

        if existing_order:
            flash('You already have an order in progress for this table.', 'warning')
            return redirect(url_for('order'))

        new_order = FoodOrder(
            table_id=table_id,
            customer_name=customer_name,
            food_items=', '.join(food_items),
            status='Sent to Kitchen',  # Initial status when placed
            order_time=datetime.now()
        )
        db.session.add(new_order)
        db.session.commit()

        flash('Order placed successfully!', 'success')
        return redirect(url_for('status', order_id=new_order.id))

    return render_template('order.html')


@app.route('/update_order_status/<int:order_id>/<status>', methods=['POST'])
@login_required
def update_order_status(order_id, status):
    if current_user.role != 'admin':
        flash('Access denied. Admins only.', 'danger')
        return redirect(url_for('home'))

    order = FoodOrder.query.get(order_id)
    if order:
        if status in ['Cooking', 'Ready']:
            order.status = status
            db.session.commit()
            flash(f'Order marked as {status}!', 'success')
        else:
            flash('Invalid status.', 'danger')
    else:
        flash('Order not found.', 'danger')

    return redirect(url_for('kitchen'))


@app.route('/delete_order/<int:order_id>', methods=['POST'])
@login_required
def delete_order(order_id):
    if current_user.role != 'admin':
        flash('Access denied. Admins only.', 'danger')
        return redirect(url_for('home'))

    order = FoodOrder.query.get(order_id)
    if order:
        db.session.delete(order)
        db.session.commit()
        flash('Order deleted successfully!', 'success')
    else:
        flash('Order not found.', 'danger')

    return redirect(url_for('customer_orders'))


@app.route('/kitchen', methods=['GET', 'POST'])
@login_required
def kitchen():
    if current_user.role != 'admin':
        flash('Access denied. Admins only.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        if 'start_cooking' in request.form:
            order_id = request.form['order_id']
            return redirect(url_for('start_cooking', order_id=order_id))
        elif 'mark_ready' in request.form:
            order_id = request.form['order_id']
            return redirect(url_for('mark_ready', order_id=order_id))

    # Fetch orders that are in the 'Sent to Kitchen' or 'Cooking' status
    orders = FoodOrder.query.filter(FoodOrder.status.in_(['Sent to Kitchen', 'Cooking'])).all()
    return render_template('kitchen.html', orders=orders)


@app.route('/customer_orders')
@login_required
def customer_orders():
    now = datetime.now()
    start_of_day = datetime.combine(now, time.min)
    end_of_day = datetime.combine(now, time.max)

    if current_user.role == 'admin':
        # Admin view: show all orders for the current day
        orders = db.session.query(
            FoodOrder.table_id,
            FoodOrder.customer_name,
            FoodOrder.status,
            func.count(FoodOrder.id).label('order_count'),
            func.group_concat(FoodOrder.status).label('statuses')
        ).filter(FoodOrder.order_time.between(start_of_day, end_of_day)) \
         .group_by(FoodOrder.table_id, FoodOrder.customer_name, FoodOrder.status).all()
    else:
        # Customer view: show only the logged-in customer's orders for the current day
        orders = db.session.query(
            FoodOrder.table_id,
            FoodOrder.status,
            func.count(FoodOrder.id).label('order_count'),
            func.group_concat(FoodOrder.status).label('statuses')
        ).filter(FoodOrder.customer_name == current_user.email,
                 FoodOrder.order_time.between(start_of_day, end_of_day)) \
         .group_by(FoodOrder.table_id, FoodOrder.status).all()

    # Categorize orders by status
    orders_by_status = {
        'Ready': [],
        'Cooking': [],
        'Sent to Kitchen': []
    }

    for order in orders:
        status = order.status
        if status in orders_by_status:
            orders_by_status[status].append(order)

    return render_template('customer_orders.html', orders_by_status=orders_by_status)



@app.route('/status/<int:order_id>')
@login_required
def status(order_id):
    order = FoodOrder.query.get(order_id)
    return render_template('status.html', order=order)

@app.route('/recommended')
@login_required
def recommended():
    return render_template('recommended.html')

if __name__ == '__main__':
    app.run(debug=True)
