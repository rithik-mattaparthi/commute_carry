from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import bcrypt
from datetime import datetime
from werkzeug.utils import secure_filename
import os  # Also make sure you have this import for file path operations

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Change this to a random secret key


# File Upload Configuration
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit

# Create folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# MongoDB configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/commute_carry"
mongo = PyMongo(app)

@app.route('/')
def home():
    if 'email' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        
        user = mongo.db.users.find_one({'email': email})
        
        if user and bcrypt.checkpw(password, user['password']):
            session['email'] = email
            session['user_id'] = str(user['_id'])
            return redirect(url_for('role_selection'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        
        # Check if user already exists
        if mongo.db.users.find_one({'email': email}):
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        
        # Insert new user
        mongo.db.users.insert_one({
            'name': name,  
            'email': email,
            'password': hashed,
            'role': None  # Role will be set later
        })
        
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/role_selection', methods=['GET', 'POST'])
def role_selection():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        role = request.form['role']
        mongo.db.users.update_one(
            {'email': session['email']},
            {'$set': {'role': role}}
        )
        return redirect(url_for('dashboard'))
    
    # Check if user already has a role
    user = mongo.db.users.find_one({'email': session['email']})
    if user and user.get('role'):
        return redirect(url_for('dashboard'))
    
    return render_template('role_selection.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'email': session['email']})
    if not user:
        session.clear()
        return redirect(url_for('login'))

    if not user.get('role'):
        return redirect(url_for('role_selection'))

    if request.method == 'POST':
        from_loc = request.form.get('from_location')
        to_loc = request.form.get('to_location')
        mode = request.form.get('transport_mode')

        # Save traveler route info
        mongo.db.travelers.insert_one({
            'user_id': session['user_id'],
            'route': {
                'from': from_loc,
                'to': to_loc
            },
            'mode': mode,
            'available': True
        })


        flash('Your travel route has been saved.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('dashboard.html', user=user)


@app.route('/create_parcel', methods=['GET', 'POST'])
def create_parcel():
    if 'email' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Handle file upload
        id_proof = request.files['id_proof']
        filename = None
        
        if id_proof and id_proof.filename != '':
            # Secure the filename and save the file
            filename = secure_filename(f"{session['user_id']}_{id_proof.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            id_proof.save(filepath)

        # ✅ Create parcel document with sender_email
        parcel = {
            'sender_id': session['user_id'],
            'sender_email': session['email'],  # ✅ Add this line
            'details': request.form.get('details'),
            'dimensions': {
                'length': float(request.form.get('length')),
                'width': float(request.form.get('width')),
                'height': float(request.form.get('height'))
            },
            'weight_grams': int(request.form.get('weight')),
            'receiver': {
                'name': request.form.get('receiver_name'),
                'phone': request.form.get('receiver_phone'),
                'id_proof': filename
            },
            'travel': {
                'from': request.form.get('from_location'),
                'to': request.form.get('to_location')
            },
            'instructions': request.form.get('delivery_instructions'),
            'status': 'pending',
            'created_at': datetime.now()
        }

        mongo.db.parcels.insert_one(parcel)
        return redirect(url_for('available_travelers', 
                           from_location=parcel['travel']['from'],
                           to_location=parcel['travel']['to']))

    # Get user's approximate location for auto-fill
    user_location = "Your Location"  # Default
    return render_template('create_parcel.html', user_location=user_location)




@app.route('/available_travelers')
def available_travelers():
    if 'email' not in session:
        return redirect(url_for('login'))

    travelers = list(mongo.db.travelers.find({'available': True}))

    return render_template('available_travelers.html', travelers=travelers)



@app.route('/select_traveler/<traveler_id>')
def select_traveler(traveler_id):
    if 'email' not in session:
        return redirect(url_for('login'))
    
    # In a real app, you would:
    # 1. Associate the traveler with the parcel
    # 2. Update both traveler and parcel status
    # 3. Maybe send notifications
    
    flash(f'Traveler selected successfully!', 'success')
    return redirect(url_for('dashboard'))



@app.route('/parcel_history')
def parcel_history():
    if 'email' not in session:
        return redirect(url_for('login'))

    email = session['email']
    parcels = list(mongo.db.parcels.find({'sender_email': email}))
    
    return render_template('parcel_history.html', parcels=parcels)


@app.route('/find_travelers')
def find_travelers():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'email': session['email']})
    if not user:
        return redirect(url_for('logout'))

    # You can also store user location during registration or profile update
    user_location = user.get('location', 'Hyderabad')  # default to Hyderabad

    # Filter travelers with matching from-location
    travelers = list(mongo.db.travelers.find({
        'route.from': user_location,
        'available': True
    }))

    return render_template('find_travelers.html', travelers=travelers, user_location=user_location)


@app.route('/available_parcels')
def available_parcels():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'email': session['email']})
    
    traveler_route = mongo.db.travelers.find_one({'email': user['email']}, {'_id': 0, 'route': 1})
    
    all_parcels = list(mongo.db.parcels.find({'status': 'available'}))

    if traveler_route and 'route' in traveler_route:
        from_loc = traveler_route['route'].get('from')
        to_loc = traveler_route['route'].get('to')

        route_specific_parcels = [
            p for p in all_parcels
            if p.get('from_location') == from_loc and p.get('to_location') == to_loc
        ]
    else:
        route_specific_parcels = []

    return render_template('available_parcels.html',
                           user=user,
                           all_parcels=all_parcels,
                           matched_parcels=route_specific_parcels)




        
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


    
@app.route('/switch_role', methods=['POST'])
def switch_role():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'email': session['email']})
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('login'))

    current_role = user.get('role')
    if current_role not in ['sender', 'traveler']:
        flash('Invalid role.', 'error')
        return redirect(url_for('dashboard'))

    # Switch to the opposite role
    new_role = 'sender' if current_role == 'traveler' else 'traveler'

    mongo.db.users.update_one(
        {'email': session['email']},
        {'$set': {'role': new_role}}
    )

    flash(f'Switched to {new_role.capitalize()} role.', 'success')
    return redirect(url_for('dashboard'))



@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

if __name__ == '__main__':
    app.run(debug=True)      
    
    
    

   
    
    
