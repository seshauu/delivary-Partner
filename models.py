from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
from datetime import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(50), default='customer') 
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

class FoodOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.String(10), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    food_items = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Cooking')
    order_time = db.Column(db.DateTime, default=datetime.utcnow)
