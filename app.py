from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_restful import Api, Resource
import os
from datetime import datetime
from flask_restful import Resource, reqparse
from flask_migrate import Migrate
from sqlalchemy.dialects.mysql import JSON  # Use JSON type for MySQL
from sqlalchemy.exc import SQLAlchemyError


# Initialize Flask app and configurations
app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:password@localhost/store'

app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure the uploads folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
migrate = Migrate(app, db)
api = Api(app)


# User Model
class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(50), nullable=True)
    password = db.Column(db.String(180), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    profile = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Automatically set to current time
    user_type = db.Column(db.String(15),  nullable=True)

class ProductModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(80), unique=True, nullable=False)    
    product_image = db.Column(db.String(255), nullable=True)
    product_price = db.Column(db.Integer,nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Automatically set to current time


class AddToCartModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product_model.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('UserModel', backref=db.backref('cart', lazy=True))
    product = db.relationship('ProductModel', backref=db.backref('cart_items', lazy=True))


class OrderPlaceModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_model.id'), nullable=False)
    total_price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='Pending')  # Status: Pending, Confirmed, Delivered, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cart_items = db.Column(JSON, nullable=False)  # JSON field to store cart items

    # Relationship
    user = db.relationship('UserModel', backref=db.backref('orders', lazy=True))


# Resource: Signup
class SignupResource(Resource):
    def post(self):
        data = request.json
        email = data.get('email')
        password = data.get('password')


        if not email or not password:
            return ({'message': 'email and password are required'}), 400

        if UserModel.query.filter_by(email=email).first():
            return ({'message': 'Email already exists'}), 400

        hashed_password = generate_password_hash(password)
        new_user = UserModel(email=email, password=hashed_password,user_type='customer')
        db.session.add(new_user)
        db.session.commit()
        return ({'message': 'User created successfully','status':201}), 201

# Resource: Login
class LoginResource(Resource):
    def post(self):
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        user = UserModel.query.filter_by(email=email).first()
        print("user---",user)
        if not user or not check_password_hash(user.password, password):
            return ({'message': 'Invalid email or password'}), 401

        access_token = create_access_token(identity=user.email)
        return ({'access_token': access_token,'status':200}), 200

# Resource: User Operations
class UserResource(Resource):
    # @jwt_required()
    def get(self, user_id):
        user = UserModel.query.get(user_id)
        if not user:
            return ({'message': 'User not found'}), 404
        return ({
            'id': user.id,
            'full_name': user.full_name,
            'email': user.email,
            'phone': user.phone,
            'profile': request.host_url + user.profile if user.profile else None ,
            'address':user.address,
            'user_type':user.user_type
        ,'status':200}), 200

    # @jwt_required()
    def put(self, user_id):
        data = request.form
        file = request.files.get('profile')
        user = UserModel.query.get(user_id)
        if not user:
            return ({'message': 'User not found'}), 404

        # Update fields
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        user.address = data.get('address')
        user.full_name = data.get('full_name')
        print("valuesssss--->>> ",user.phone,user.address)
        # Update password if provided
        if 'password' in data:
            user.password = generate_password_hash(data['password'])

        # Handle profile image
        if file:
            # Delete old profile image
            if user.profile and os.path.exists(user.profile):
                os.remove(user.profile)
            # Save new profile image
            filename = secure_filename(file.filename)
            profile_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(profile_path)
            user.profile = profile_path
        print("@@##### ",user.address)
        try:
            db.session.commit()
            return ({'message': 'User updated successfully','status':202}), 200
        except Exception as e:
            return {'error':str(e),'message':"phone number should be unique",'status':400}

# Resource: User List
class UserListResource(Resource):
    # @jwt_required()
    def get(self):
        users = UserModel.query.all()
        return ([{
            'id': user.id,
            'full_name': user.full_name,
            'email': user.email,
            'phone': user.phone,
            'profile': request.host_url + user.profile if user.profile else None,
            'address':user.address,
            'user_type':user.user_type
        } for user in users]), 200

class AddProduct(Resource):
    # @jwt_required()
    def post(self):
        data = request.form
        file = request.files.get('product_image')

        if not data.get('product_name') or not data.get('product_price'):
            return {'message': 'Product name and price are required'}, 400
        try:
            filename = None
            if file:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

            product = ProductModel(
                product_name=data.get('product_name'),
                product_price=int(data.get('product_price')),
                product_image=file_path if file else None,
            )
            db.session.add(product)
            db.session.commit()

            return {'message': 'Product added successfully', 'product': product.id,'status':201}, 201

        except Exception as e:
            return {'message': 'Error occurred', 'error': str(e),'status':500}, 500


class GetProduct(Resource):
    # @jwt_required()
    def get(self, product_id=None):
        if product_id:
            product = ProductModel.query.get(product_id)
            if not product:
                return {'message': 'Product not found'}, 404

            return {
                'id': product.id,
                'product_name': product.product_name,
                'product_price': product.product_price,
                'product_image': request.host_url + product.product_image if product.product_image else None,
                'created_at': product.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'status':200  # Convert datetime to string
            },

        # List all products
        products = ProductModel.query.all()
        return [
            {
                'id': p.id,
                'product_name': p.product_name,
                'product_price': p.product_price,
                'product_image': request.host_url + p.product_image if p.product_image else None,
                'created_at': p.created_at.strftime('%Y-%m-%d %H:%M:%S')  # Convert datetime to string
            }
            for p in products
        ]

class UpdateProduct(Resource):
    # @jwt_required()
    def put(self, product_id):
        data = request.form
        file = request.files.get('product_image')

        product = ProductModel.query.get(product_id)
        if not product:
            return {'message': 'Product not found'}, 404

        try:
            if data.get('product_name'):
                product.product_name = data.get('product_name')
            if data.get('product_price'):
                product.product_price = int(data.get('product_price'))
            if file:
                # Save new image
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                product.product_image = file_path

            db.session.commit()
            return {'message': 'Product updated successfully','status':202}, 200

        except Exception as e:
            return {'message': 'Error occurred', 'error': str(e)}, 500

class DeleteProduct(Resource):
    # @jwt_required()
    def delete(self, product_id):
        product = ProductModel.query.get(product_id)
        if not product:
            return {'message': 'Product not found'}, 404

        try:
            db.session.delete(product)
            db.session.commit()
            return {'message': 'Product deleted successfully','status':204}, 200

        except Exception as e:
            return {'message': 'Error occurred', 'error': str(e),'status':500}, 500


class AddToCart(Resource):
    @jwt_required()
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('product_id', type=int, required=True, help="Product ID is required")
        parser.add_argument('quantity', type=int, default=1, help="Quantity must be an integer")
        args = parser.parse_args()

        current_user = get_jwt_identity()  # Assuming user ID is stored in JWT
        current_user_id=UserModel.query.filter_by(email=get_jwt_identity()).first()
        print("current user -- ",current_user_id.id)
        # Check if product exists
        product = ProductModel.query.get(args['product_id'])
        if not product:
            return {'message': 'Product not found'}, 404

        # Check if the product is already in the user's cart
        cart_item = AddToCartModel.query.filter_by(user_id=current_user_id.id, product_id=args['product_id']).first()

        if cart_item:
            cart_item.quantity = args['quantity']  # Update quantity if already in cart
        else:
            cart_item = AddToCartModel(
                user_id=current_user_id.id,
                product_id=args['product_id'],
                quantity=args['quantity']
            )
            db.session.add(cart_item)

        db.session.commit()
        return {'message': 'Product added to cart successfully','status':201}, 201

class GetCart(Resource):
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()  # Assuming user ID is stored in JWT
        print("current ",current_user_id)
        user = UserModel.query.filter_by(email=current_user_id).first()
        cart_items = AddToCartModel.query.filter_by(user_id=user.id).all()
        if not cart_items:
            return {'message': 'Cart is empty'}, 200

        cart_details = []
        total_price = 0

        for item in cart_items:
            product = item.product
            item_total = product.product_price * item.quantity
            total_price += item_total
            cart_details.append({
                'product_id': product.id,
                'product_name': product.product_name,
                'product_price': product.product_price,
                'quantity': item.quantity,
                'total': item_total
            })

        return {
            'cart': cart_details,
            'grand_total': total_price  # Add taxes/discounts here if needed
        }, 200
    

class PlaceOrder(Resource):
    @jwt_required()
    def post(self):
        user = UserModel.query.filter_by(email=get_jwt_identity()).first() 

        try:
            # Fetch cart items for the user
            cart_items = AddToCartModel.query.filter_by(user_id=user.id).all()

            if not cart_items:
                return {"message": "Cart is empty"}, 400

            # Prepare cart items JSON and calculate total price
            items_list = []
            total_price = 0
            for item in cart_items:
                product = ProductModel.query.get(item.product_id)
                if not product:
                    continue

                items_list.append({
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "product_price": product.product_price,
                    "quantity": item.quantity
                })
                total_price += product.product_price * item.quantity

            # Create a new order
            new_order = OrderPlaceModel(
                user_id=user.id,
                total_price=total_price,
                cart_items=items_list  # Store cart items as JSON
            )
            db.session.add(new_order)

            # Clear the cart after order placement
            AddToCartModel.query.filter_by(user_id=user.id).delete()
            db.session.commit()

            return {
                "message": "Order placed successfully",
                "order": {
                    "order_id": new_order.id,
                    "total_price": new_order.total_price,
                    "payment_status": new_order.status,
                    "cart_items": new_order.cart_items,
                    'status':201

                }
            }

        except SQLAlchemyError as e:
            db.session.rollback()
            return {"message": "Error occurred", "error": str(e)}, 500
    @jwt_required()
    def get(self):
        user = UserModel.query.filter_by(email=get_jwt_identity()).first() 
        try:
            # Fetch cart items for the user
            order_details = OrderPlaceModel.query.filter_by(user_id=user.id).all()
            if order_details:
                return [  {'id' :order.id,'full_name':order.user.full_name,'Address':order.user.address,'payment_status':order.status,'total_price':order.total_price,'items':order.cart_items } for order in order_details ]
            else:
                return {'message':'No Order Found Have One Please.'}
        except :
            return {'error':'exception error'}
        
    
class CreateUserVendor(Resource):
    @jwt_required()
    def put(self,user_email):
        user = UserModel.query.filter_by(email=user_email).first()
        if not user:
            return {'message':'No User Found with this email','status':404}
        current_user = UserModel.query.filter_by(email = get_jwt_identity()).first()
        print("user")
        if current_user.user_type != 'admin':
            return {'message':'You are not autherized for the action.','status':400}
        user.user_type='vendor'
        db.session.commit()
        return {'message':'You are become Vendor Now.','status':202}

class UpdateOrderStatus(Resource):
    @jwt_required()
    def put(self, order_id):
    
        order = OrderPlaceModel.query.get(order_id)
        if not order:
            return {'message': 'Product not found'}, 404
        try:
            order.status='success'
            db.session.commit()
            return {'message': 'Order Success successfully'}, 200

        except Exception as e:
            return {'message': 'Error occurred', 'error': str(e)}, 500




# Add Users API
api.add_resource(SignupResource, '/signup')
api.add_resource(LoginResource, '/login')
api.add_resource(UserResource, '/user/<int:user_id>')
api.add_resource(UserListResource, '/users')

## Products Api 
api.add_resource(AddProduct, '/product/add')
api.add_resource(GetProduct, '/product', '/product/<int:product_id>')
api.add_resource(UpdateProduct, '/product/update/<int:product_id>')
api.add_resource(DeleteProduct, '/product/delete/<int:product_id>')

### add to cart api
api.add_resource(AddToCart, '/cart/add')
api.add_resource(GetCart, '/cart')

### order place ##
api.add_resource(PlaceOrder,'/order')
api.add_resource(UpdateOrderStatus, '/order/status/<int:order_id>')

##### make new user As Vendor ###
api.add_resource(CreateUserVendor, '/user/create-vendor/<string:user_email>')


##################### Render HTML Page For Admin #######

@app.route('/', methods=['GET'])
def view_users():
    return render_template('users.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True,host='0.0.0.0')
