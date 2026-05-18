"""
Contact Management System for MIRA - Medical Intelligence Robotic Automation
"""

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import re
import os

# App Configuration

app = Flask(__name__)

# CORS allows the frontend (browser) to talk to the backend
CORS(app)

# SQLite database file will be created in the same folder as app.py
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'contacts.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialise SQLAlchemy with our app
db = SQLAlchemy(app)


# Database Model (Table Definition)

class Contact(db.Model):
    """
    This class defines the 'contact' table in the SQLite database.
    Each attribute = one column in the table.
    """
    __tablename__ = 'contact'

    id          = db.Column(db.Integer, primary_key=True)   # Auto-incrementing unique ID
    first_name  = db.Column(db.String(50),  nullable=False)  # Cannot be empty
    last_name   = db.Column(db.String(50),  nullable=False)
    address     = db.Column(db.String(200), nullable=False)
    email       = db.Column(db.String(100), nullable=False, unique=True)  # Must be unique
    phone       = db.Column(db.String(15),  nullable=False)

    def to_dict(self):
        """
        Convert a Contact object to a Python dictionary.
        This lets Flask send it as JSON to the frontend.
        """
        return {
            'id':         self.id,
            'first_name': self.first_name,
            'last_name':  self.last_name,
            'address':    self.address,
            'email':      self.email,
            'phone':      self.phone
        }


# Validation Helper

def validate_contact(data):
    """
    Validates incoming contact data before saving to database.
    Returns (True, None) if valid, or (False, error_message) if invalid.
    """
    errors = []

    # Check all required fields exist and are not empty
    required = ['first_name', 'last_name', 'address', 'email', 'phone']
    for field in required:
        if not data.get(field, '').strip():
            errors.append(f"{field.replace('_', ' ').title()} is required.")

    # Validate email format using regex
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if data.get('email') and not re.match(email_pattern, data['email']):
        errors.append("Invalid email format.")

    # Validate phone: must be 10 digits (Indian format) or with country code
    phone = data.get('phone', '').strip().replace(' ', '').replace('-', '')
    phone_pattern = r'^(\+61)?0\d{9}$'
    if phone and not re.match(phone_pattern, phone):
        errors.append("Invalid phone number. Use 10-digit Indian format (e.g. 9876543210).")

    if errors:
        return False, errors
    return True, None


# Routes

# ── Serve the frontend HTML page ──
@app.route('/')
def index():
    """Serve the main HTML page (templates/index.html)"""
    return render_template('index.html')


# ── CREATE: POST /api/contacts ──
@app.route('/api/contacts', methods=['POST'])
def create_contact():
    """
    Receives JSON data from frontend.
    Validates it, checks for duplicates, then saves to database.
    """
    data = request.get_json()  # Parse JSON body sent from frontend

    # Validate the data
    is_valid, errors = validate_contact(data)
    if not is_valid:
        return jsonify({'success': False, 'errors': errors}), 400

    # Check if email already exists (duplicate check)
    existing = Contact.query.filter_by(email=data['email'].strip()).first()
    if existing:
        return jsonify({'success': False, 'errors': ['Email already exists.']}), 409

    # Create a new Contact object and save it
    contact = Contact(
        first_name = data['first_name'].strip(),
        last_name  = data['last_name'].strip(),
        address    = data['address'].strip(),
        email      = data['email'].strip().lower(),
        phone      = data['phone'].strip()
    )
    db.session.add(contact)     # Stage the new record
    db.session.commit()         # Write to database

    return jsonify({'success': True, 'contact': contact.to_dict()}), 201


# ── READ ALL: GET /api/contacts ──
@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    """
    Returns all contacts from the database as a JSON array.
    Supports optional search via ?search=keyword query parameter.
    """
    search = request.args.get('search', '').strip()  # ?search=John

    if search:
        # Search across first name, last name, email
        contacts = Contact.query.filter(
            (Contact.first_name.ilike(f'%{search}%')) |
            (Contact.last_name.ilike(f'%{search}%'))  |
            (Contact.email.ilike(f'%{search}%'))
        ).all()
    else:
        contacts = Contact.query.order_by(Contact.first_name).all()

    # Convert list of Contact objects to list of dicts, then to JSON
    return jsonify({'success': True, 'contacts': [c.to_dict() for c in contacts]})


# ── READ ONE: GET /api/contacts/<id> ──
@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    """Returns a single contact by its ID."""
    contact = Contact.query.get_or_404(contact_id)
    return jsonify({'success': True, 'contact': contact.to_dict()})


# ── UPDATE: PUT /api/contacts/<id> ──
@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    """
    Updates an existing contact.
    Finds the record by ID, updates its fields, saves back to DB.
    """
    contact = Contact.query.get_or_404(contact_id)
    data    = request.get_json()

    # Validate updated data
    is_valid, errors = validate_contact(data)
    if not is_valid:
        return jsonify({'success': False, 'errors': errors}), 400

    # Check for duplicate email — but ignore THIS contact's own email
    existing = Contact.query.filter(
        Contact.email == data['email'].strip().lower(),
        Contact.id != contact_id
    ).first()
    if existing:
        return jsonify({'success': False, 'errors': ['Email already used by another contact.']}), 409

    # Update the fields
    contact.first_name = data['first_name'].strip()
    contact.last_name  = data['last_name'].strip()
    contact.address    = data['address'].strip()
    contact.email      = data['email'].strip().lower()
    contact.phone      = data['phone'].strip()

    db.session.commit()  # Save changes to database

    return jsonify({'success': True, 'contact': contact.to_dict()})


# ── DELETE: DELETE /api/contacts/<id> ──
@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    """Deletes a contact record permanently from the database."""
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Contact deleted successfully.'})

# Run the App

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create the database tables if they don't exist
        print(" Database tables created.")
    print(" MIRA Contact Manager running at http://127.0.0.1:5000")
    app.run(debug=True)  # debug=True = auto-reload on code changes
