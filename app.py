from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
import os
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask import flash
from flask_socketio import SocketIO, send
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'
socketio = SocketIO(app)

def init_db():
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        # c.execute('DROP TABLE IF EXISTS parcels')  # For reinitialization
        # c.execute('DROP TABLE IF EXISTS delivery_partners')
        # Create Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                password TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                location TEXT,
                unique_id TEXT,
                security_question TEXT,
                security_answer TEXT
            )
        ''')

        # Create Parcels table
        c.execute('''CREATE TABLE IF NOT EXISTS parcels (
            id INTEGER PRIMARY KEY,
            recipient_id TEXT,
            user_id INTEGER,
            tracking_id TEXT,
            size TEXT,
            weight TEXT,
            description TEXT,
            delivery_option TEXT,
            insurance BOOLEAN,
            status TEXT DEFAULT 'Pending',
            current_status TEXT DEFAULT 'Pending',
            delivery_partner TEXT,
            estimated_delivery_time TEXT,
            time_slot TEXT,
            sent_date TEXT,  
            sent_time TEXT   
        )''')
        
        # Create Delivery Partners table
        c.execute('''
            CREATE TABLE IF NOT EXISTS delivery_partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                availability TEXT NOT NULL,
                username TEXT,
                password TEXT
            )
        ''')
        
        conn.commit()



# Run DB initialization once
init_db()

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

DATABASE = 'delivery.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Unique ID Generator
def generate_unique_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def generate_parcel_label(tracking_id, recipient_id, size, weight, description):
    # Concatenate all the information into a single string
    qr_data = f"Tracking ID: {tracking_id}\nRecipient ID: {recipient_id}\nSize: {size}\nWeight: {weight}\nDescription: {description}"

    # Create QR code for the tracking ID and other parcel details
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)  # Add the concatenated string to the QR code
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    # Define QR code save path
    qr_code_dir = 'D:\\post_setu\\static\\qr_codes'
    qr_code_path = os.path.join(qr_code_dir, f"{tracking_id}.png")

    # Create the directory if it doesn't exist
    os.makedirs(qr_code_dir, exist_ok=True)

    # Save QR code image
    img.save(qr_code_path)

    # Generate a PDF with the parcel information and QR code
    pdf_path = f"D:\\post_setu\\static\\labels\\{tracking_id}.pdf"  # Adjust the PDF path as needed
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    c = canvas.Canvas(pdf_path, pagesize=letter)
    
    # Add text to the PDF
    c.drawString(100, 750, f"Tracking ID: {tracking_id}")
    c.drawString(100, 730, f"Recipient Unique ID: {recipient_id}")
    c.drawString(100, 710, f"Parcel Size: {size}")
    c.drawString(100, 690, f"Parcel Weight: {weight}")
    c.drawString(100, 670, f"Description: {description}")
    
    # Add the QR code to the PDF
    c.drawImage(qr_code_path, 100, 550, width=100, height=100)  # Position the QR code
    
    # Save the PDF
    c.save()

    return pdf_path



def add_sample_delivery_partners():
    sample_partners = [
        ('Partner A', 'Location A', 'Available', 'partnerA', 'admin'),
        ('Partner B', 'Location B', 'Available', 'partnerB', 'admin'),
        ('Partner C', 'Location C', 'Unavailable', 'partnerC', 'admin'),
    ]
    
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        # Insert sample partners into the table
        c.executemany('INSERT INTO delivery_partners (name, location, availability, username, password) VALUES (?, ?, ?, ?, ?)', sample_partners)
        conn.commit()

        # Debugging: Print the delivery partners in the database
        c.execute('SELECT * FROM delivery_partners')
        print("Partners in database:", c.fetchall())

# add_sample_delivery_partners() #-------- only used when you have to update the database


# def assign_delivery_partner(parcel_location):
#     with sqlite3.connect('delivery.db') as conn:
#         c = conn.cursor()
#         # Find available delivery partners
#         c.execute('SELECT * FROM delivery_partners WHERE availability = "Available"')
#         partners = c.fetchall()

#         if partners:
#             selected_partner = partners[0][1]  # Get partner name (adjust as needed)
#             print(f"Assigned delivery partner: {selected_partner}")  # Debugging print
#             return selected_partner
#         else:
#             print("No available delivery partners")
#             return None

def assign_delivery_partner(parcel_location):
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        
        # Find available delivery partners
        c.execute('SELECT name FROM delivery_partners WHERE availability = "Available"')
        partners = c.fetchall()
        
        if not partners:
            print("No available delivery partners")
            return None

        # Find the delivery partner with the least assigned parcels
        min_parcels = None
        selected_partner = None

        for partner in partners:
            partner_name = partner[0]
            c.execute('SELECT COUNT(*) FROM parcels WHERE delivery_partner = ?', (partner_name,))
            parcel_count = c.fetchone()[0]

            if min_parcels is None or parcel_count < min_parcels:
                min_parcels = parcel_count
                selected_partner = partner_name

        print(f"Assigned delivery partner: {selected_partner}")  # Debugging print
        return selected_partner


file_path = 'delivery_data.xlsx'  # Change to your file path

# Preprocess the data
def preprocess_data(df):
    # Dropping irrelevant columns
    df = df.drop(columns=['Order ID', 'Sender ID', 'Recipient ID', 'Booking Date', 'Delivery Date', 'Route'])
    
    # Encode categorical columns
    label_encoders = {}
    categorical_columns = ['Delivery Address', 'Preferred Slot', 'Actual Slot', 'Region', 'Traffic Level', 'Weather', 'Vehicle']
    for col in categorical_columns:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])
        label_encoders[col] = le

    return df, label_encoders

df = pd.read_excel(file_path)
df, encoders = preprocess_data(df)

def suggest_time_slot(address_input):
    try:
        encoded_address = encoders['Delivery Address'].transform([address_input])[0]
        filtered_data = df[df['Delivery Address'] == encoded_address]
        
        if filtered_data.empty:
            return "No data available for the given address"
        
        most_common_slot = filtered_data['Preferred Slot'].mode()
        if not most_common_slot.empty:
            slot_encoded = most_common_slot[0]
            time_slot = encoders['Preferred Slot'].inverse_transform([slot_encoded])[0]
            return time_slot
        else:
            return "No preferred slot found"
    except Exception as e:
        return str(e)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/view_database', methods=['GET'])
def view_database():
    with sqlite3.connect('delivery.db') as conn:
        conn.row_factory = sqlite3.Row  # This allows us to access columns by name
        c = conn.cursor()

        # Fetch all data from the users table
        c.execute("SELECT * FROM users")
        users = c.fetchall()

        # Fetch all data from the parcels table
        c.execute("SELECT * FROM parcels")
        parcels = c.fetchall()

        # Fetch all data from the delivery_partners table
        c.execute("SELECT * FROM delivery_partners")
        delivery_partners = c.fetchall()

    # Render a simple HTML page to display the data
    return render_template('view_database.html', users=users, parcels=parcels, delivery_partners=delivery_partners)

def is_valid_phone(phone):
    return re.match(r"^\+?\d{10,15}$", phone) is not None

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        password = request.form['password']
        location = request.form['location']
        security_question = request.form['security_question']
        security_answer = request.form['security_answer']
        unique_id = generate_unique_id()

        if not is_valid_phone(phone):
            flash("Invalid phone number format!", "danger")
            return redirect(url_for('register'))

        password_hashed = generate_password_hash(password)

        with sqlite3.connect('delivery.db') as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            existing_user = c.fetchone()

            if existing_user:
                flash("Email already registered!", "danger")
                return redirect(url_for('register'))

            c.execute('''INSERT INTO users (username, email, phone, address, password, location, unique_id, security_question, security_answer) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (username, email, phone, address, password_hashed, location, unique_id, security_question, security_answer))
            conn.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

# Login Route (User)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
                
        with sqlite3.connect('delivery.db') as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                return redirect(url_for('dashboard'))
    
    return render_template('login.html')

# Route to handle forgot password
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user:
            # Send to security question
            session['email'] = email
            return redirect(url_for('security_question'))
        else:
            flash('Email not found.', 'danger')
            return redirect(url_for('forgot_password'))
    return render_template('forgot_password.html')


@app.route('/security_question', methods=['GET', 'POST'])
def security_question():
    if 'email' not in session:
        return redirect(url_for('login'))  # Redirect to login if no email in session

    email = session['email']
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

    if request.method == 'POST':
        answer = request.form['answer']
        if answer.lower() == user['security_answer'].lower():
            return redirect(url_for('reset_password'))
        else:
            flash('Incorrect answer to security question.', 'danger')
            return redirect(url_for('security_question'))

    return render_template('security_question.html', question=user['security_question'])


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'email' not in session:
        return redirect(url_for('login'))  # Redirect to login if no email in session

    email = session['email']
    if request.method == 'POST':
        print(request.form)  # Debugging: print the form data
        new_password = request.form.get('password')  # Use get() to avoid KeyError
        if new_password:
            hashed_password = generate_password_hash(new_password)
            db = get_db()
            db.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_password, email))
            db.commit()
            flash('Password reset successfully.', 'success')
            session.pop('email', None)  # Remove the email from session after resetting
            return redirect(url_for('login'))  # Redirect to the login page
        else:
            flash('Password cannot be empty.', 'danger')

    return render_template('reset_password.html')


# User Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
        user = c.fetchone()
    
    return render_template('dashboard.html', user=user)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
        user = c.fetchone()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        location = request.form['location']

        with sqlite3.connect('delivery.db') as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET username=?, email=?, phone=?, address=?, location=? WHERE id=?',
                      (username, email, phone, address, location, session['user_id']))
            conn.commit()

        return redirect(url_for('dashboard'))

    return render_template('profile.html', user=user)


@app.route('/send-parcel', methods=['GET', 'POST'])
def send_parcel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        recipient_id = request.form['recipient_id']
        size = request.form['size']
        weight = request.form['weight']
        description = request.form['description']
        delivery_option = request.form['delivery_option']
        insurance = request.form.get('insurance', 'No')
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H-%M-%S")
        
        # Generate a unique Tracking ID
        tracking_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

        # Store parcel information in the database
        with sqlite3.connect('delivery.db') as conn:
            c = conn.cursor()
            c.execute('INSERT INTO parcels (recipient_id, user_id, tracking_id, size, weight, description, delivery_option, insurance, sent_date, sent_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                      (recipient_id, session['user_id'], tracking_id, size, weight, description, delivery_option, insurance, current_date, current_time))
            conn.commit()

        # Generate the parcel label PDF
        pdf_path = generate_parcel_label(tracking_id, recipient_id, size, weight, description)

        # Notify the recipient (optional)
        # notify_recipient(recipient_id, tracking_id)

        return redirect(url_for('dashboard'))

    return render_template('send_parcel.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == 'admin' and password == 'admin@123':
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM parcels WHERE status != "Accepted"')
        parcels = c.fetchall()
    
    return render_template('admin_dashboard.html', parcels=parcels)


@app.route('/admin/approve/<int:parcel_id>', methods=['POST'])
def approve_parcel(parcel_id):
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM parcels WHERE id = ?', (parcel_id,))
        parcel = c.fetchone()

        if parcel:
            # Assign the delivery partner based on location
            delivery_partner = assign_delivery_partner(parcel[5])  # Assuming parcel[5] is the location

            if not delivery_partner:
                return "No available delivery partner", 400  # Handle the case where no partner is available

            delivery_option = parcel[7]
            estimated_delivery_time = "3 days" if delivery_option == 'Fast' else "10 days"

            # Update the parcel with the assigned delivery partner and estimated delivery time
            c.execute('UPDATE parcels SET status = "Accepted", delivery_partner = ?, estimated_delivery_time = ? WHERE id = ?',
                      (delivery_partner, estimated_delivery_time, parcel_id))
            conn.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/reject/<int:parcel_id>', methods=['POST'])
def reject_parcel(parcel_id):
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        # Delete the parcel
        c.execute('DELETE FROM parcels WHERE id = ?', (parcel_id,))
        conn.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/accepted_parcels')
def accepted_parcels():
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM parcels WHERE status = "Accepted" AND current_status != "Delivered"')  # Exclude delivered parcels
        parcels = c.fetchall()
    return render_template('accepted_parcels.html', parcels=parcels)


@app.route('/track_parcel', methods=['GET'])
def track_parcel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        
        # Fetch sent parcels (parcels sent by the user)
        c.execute('SELECT * FROM parcels WHERE user_id = ?', (user_id,))
        sent_parcels = c.fetchall()

        # Fetch receiving parcels (parcels received by the user)
        c.execute('SELECT * FROM parcels WHERE recipient_id = (SELECT unique_id FROM users WHERE id = ?)', (user_id,))
        receiving_parcels = c.fetchall()

    # Handle tracking by Tracking ID if provided
    tracking_id = request.args.get('tracking_id')
    parcel = None
    if tracking_id:
        with sqlite3.connect('delivery.db') as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM parcels WHERE tracking_id = ?', (tracking_id,))
            parcel = c.fetchone()

    # Calculate progress if the parcel is found
    if parcel:
        current_status = parcel[10]  # Assuming this is the correct index for current_status
        status = parcel[9]
        
        progress = {
            'Dispatched': 20,
            'In Transit': 40,
            'At Warehouse': 60,
            'Out for Delivery': 80,
            'Delivered': 100
        }.get(current_status, 0)
        
        parcel_details = {
            'tracking_id': parcel[3],  # Adjust index as per your schema
            'current_status': current_status,
            'status': status,
            'progress': progress
        }
    else:
        parcel_details = None

    return render_template('track_parcel.html', sent_parcels=sent_parcels, receiving_parcels=receiving_parcels, parcel=parcel_details)


@app.route('/parcel/<int:parcel_id>')
def view_parcel_details(parcel_id):
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM parcels WHERE id = ?', (parcel_id,))
        parcel = c.fetchone()
        
    if not parcel:
        return "Parcel not found", 404
    
    return render_template('parcel_details.html', parcel=parcel)

@app.template_filter('format_percentage')
def format_percentage(value):
    return f"{value if value is not None else 0}%"


@app.route('/delivery_partner_login', methods=['GET', 'POST'])
def delivery_partner_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with sqlite3.connect('delivery.db') as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM delivery_partners WHERE username = ? AND password = ?', (username, password))
            partner = c.fetchone()
            
            if partner:
                session['delivery_partner'] = partner[0]  # Store partner ID in session
                return redirect(url_for('delivery_partner_dashboard', partner_id=partner[0]))
        
    return render_template('delivery_partner_login.html')


@app.route('/delivery_partner_dashboard')
def delivery_partner_dashboard():
    if 'delivery_partner' not in session:
        return redirect(url_for('delivery_partner_login'))

    partner_id = session['delivery_partner']
    
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM delivery_partners WHERE id = ?', (partner_id,))
        partner = c.fetchone()
        
        # Fetch accepted parcels assigned to this delivery partner, excluding delivered parcels
        c.execute('SELECT * FROM parcels WHERE delivery_partner = ? AND current_status != "Delivered"', (partner[1],))  # Assuming partner[1] is the name
        accepted_parcels = c.fetchall()

        # Fetch the user details and location for each parcel (receiver's info)
        user_info = {}
        for parcel in accepted_parcels:
            recipient_id = parcel[1]  # Assuming recipient_id is the second field in the parcels table
            c.execute('SELECT * FROM users WHERE unique_id = ?', (recipient_id,))
            user = c.fetchone()
            
            # Assuming receiver location is in "latitude,longitude" format
            location = user[6]  # user[6] is the location column
            
            # Check if location is valid and contains a comma
            if location and ',' in location:
                lat, lon = location.split(',', 1)  # Only split once to handle more complex locations
            else:
                lat, lon = None, None  # Default to None if invalid
            
            # Save user info with parcel_id as key
            user_info[parcel[0]] = {
                'user': user,
                'lat': lat,
                'lon': lon
            }

    return render_template('delivery_partner_dashboard.html', partner=partner, accepted_parcels=accepted_parcels, user_info=user_info)


@app.route('/update_status/<int:parcel_id>', methods=['POST'])
def update_status(parcel_id):
    new_status = request.form['status']
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        c.execute('UPDATE parcels SET current_status = ? WHERE id = ?', (new_status, parcel_id))
        conn.commit()
    return redirect(url_for('delivery_partner_dashboard'))

@app.route('/suggest-slot', methods=['GET'])
def suggest_slot():
    address = request.args.get('address')
    if not address:
        return jsonify({'error': 'Address is required!'}), 400
    
    time_slot = suggest_time_slot(address)
    return jsonify({'slot': time_slot})

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    time_slot = data.get('timeSlot')
    parcel_id = data.get('parcelId')  # Make sure to receive parcelId

    if not time_slot or not parcel_id:
        return jsonify({'error': 'Time slot and parcel ID are required!'}), 400

    # Save to SQLite database
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        try:
            c.execute("UPDATE parcels SET time_slot = ? WHERE id = ?", (time_slot, parcel_id))
            conn.commit()
        except sqlite3.Error as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'message': 'Delivery scheduled successfully!'})

@app.route('/update_time_slot/<int:parcel_id>', methods=['POST'])
def update_time_slot(parcel_id):
    if 'delivery_partner' not in session:
        return redirect(url_for('delivery_partner_login'))

    new_time_slot = request.form['time_slot']
    
    with sqlite3.connect('delivery.db') as conn:
        c = conn.cursor()
        try:
            # Update the time slot for the parcel
            c.execute('UPDATE parcels SET time_slot = ? WHERE id = ?', (new_time_slot, parcel_id))
            conn.commit()
            flash('Time slot updated successfully', 'success')
        except sqlite3.Error as e:
            flash(f'Error updating time slot: {e}', 'error')
    
    return redirect(url_for('delivery_partner_dashboard'))



# Logout for Delivery Partner
@app.route('/delivery_partner_logout')
def delivery_partner_logout():
    session.pop('delivery_partner', None)
    return redirect(url_for('delivery_partner_login'))

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/chatbot_message', methods=['POST'])
def chatbot_message():
    user_message = request.form['message']
    
    bot_response = "Sorry, I didn't understand that."
    
    if "track" in user_message.lower():
        bot_response = "You can track your complaints on the [Track Complaints page]({})."
    elif "complaint" in user_message.lower():
        bot_response = "You can submit a complaint by visiting the [Complaint page]({})."
    elif "help" in user_message.lower():
        bot_response = "How can I assist you today? Feel free to ask any questions!"
    elif "feedback" in user_message.lower():
        bot_response = "You can submit feedback once your complaint is resolved on the [Feedback page]({})."  # Replace '123' with dynamic complaint ID if needed
    return bot_response

@socketio.on('message')
def handle_message(msg):
    print('Message from user: ' + msg)
    response = "I am a simple bot. You said: " + msg  # Simple response
    send(response, broadcast=True)


@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.form['message']
    
    bot_response = chatbot_message()  # Get the bot's response
    
    return render_template('chat.html', user_message=user_message, bot_response=bot_response)


if __name__ == '__main__':
    socketio.run(app, debug=True)  # Use SocketIO to run the app
