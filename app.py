from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import uuid
import time

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_evaluation' # Necessary for Flask sessions
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nourishnet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(36), unique=True, nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'donor' or 'ngo'
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.Float, nullable=False)

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.String(36), unique=True, nullable=False)
    donor_id = db.Column(db.String(36), db.ForeignKey('user.uid'), nullable=False)
    donor_name = db.Column(db.String(100), nullable=False)
    donor_contact = db.Column(db.String(100), nullable=False)
    food_details = db.Column(db.Text, nullable=False)
    pickup_address = db.Column(db.String(200), nullable=False)
    pickup_time = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, completed
    accepted_by = db.Column(db.String(36), db.ForeignKey('user.uid'), nullable=True)
    ngo_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.Float, nullable=False)

# Create tables
with app.app_context():
    db.create_all()

# --- UTILITY FUNCTIONS ---

def get_current_user():
    """Retrieves current user data from the session."""
    user_id = session.get('user_id')
    return User.query.filter_by(uid=user_id).first() if user_id else None
# --- ROUTING AND VIEW FUNCTIONS ---

@app.route('/')
def index():
    """Renders the Home page or redirects to the Dashboard if logged in."""
    user = get_current_user()
    if user:
        return redirect(url_for('dashboard'))
    return render_template('index.html')
@app.route('/register', methods=['POST'])
def register():
    """Handles user registration and logs the user in."""
    role = request.form.get('role')
    name = request.form.get('name')
    contact = request.form.get('contact')
    location = request.form.get('location')

    # Simple ID generation (replaces Firebase UID)
    user_id = str(uuid.uuid4())

    user = User(
        uid=user_id,
        role=role,
        name=name,
        contact=contact,
        location=location,
        timestamp=time.time()
    )
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user_id
    return redirect(url_for('dashboard'))
@app.route('/logout')
def logout():
    """Logs the user out by clearing the session."""
    session.pop('user_id', None)
    return redirect(url_for('index'))
@app.route('/dashboard')
def dashboard():
    """Routes the user to the correct dashboard based on their role."""
    user = get_current_user()

    if not user:
        return redirect(url_for('index'))

    if user.role == 'donor':
        return render_donor_dashboard(user)
    elif user.role == 'ngo':
        return render_ngo_dashboard(user)

    return redirect(url_for('index'))
def render_donor_dashboard(user):
    """Gathers and displays donor's history."""
    user_donations = Donation.query.filter_by(donor_id=user.uid).all()
    # Sort by time (most recent first)
    user_donations.sort(key=lambda x: x.created_at, reverse=True)

    # Get stats
    total_users = User.query.count()
    total_donations = Donation.query.count()
    pending = Donation.query.filter_by(status='pending').count()
    accepted = Donation.query.filter_by(status='accepted').count()
    completed = Donation.query.filter_by(status='completed').count()

    return render_template('donor_dashboard.html', user=user, requests=user_donations, total_users=total_users, total_donations=total_donations, pending=pending, accepted=accepted, completed=completed)
@app.route('/post_donation', methods=['POST'])
def post_donation():
    """Creates a new donation request."""
    user = get_current_user()
    if not user or user.role != 'donor':
        return redirect(url_for('index'))

    donation_id = str(uuid.uuid4())

    donation = Donation(
        donation_id=donation_id,
        donor_id=user.uid,
        donor_name=user.name,
        donor_contact=user.contact,
        food_details=request.form.get('food_details'),
        pickup_address=request.form.get('pickup_address'),
        pickup_time=request.form.get('pickup_time'),
        status='pending',
        accepted_by=None,
        ngo_name=None,
        created_at=time.time()
    )
    db.session.add(donation)
    db.session.commit()
    return redirect(url_for('dashboard'))

# --- NGO LOGIC ---

def render_ngo_dashboard(user):
    """Gathers and displays pending and accepted donations for NGOs."""
    pending_donations = Donation.query.filter_by(status='pending').all()
    pending_donations.sort(key=lambda x: x.created_at, reverse=True)

    accepted_donations = Donation.query.filter_by(accepted_by=user.uid).all()
    accepted_donations.sort(key=lambda x: x.created_at, reverse=True)

    # Get stats
    total_users = User.query.count()
    total_donations = Donation.query.count()
    pending = Donation.query.filter_by(status='pending').count()
    accepted = Donation.query.filter_by(status='accepted').count()
    completed = Donation.query.filter_by(status='completed').count()

    return render_template(
        'ngo_dashboard.html',
        user=user,
        pending_requests=pending_donations,
        accepted_requests=accepted_donations,
        total_users=total_users,
        total_donations=total_donations,
        pending=pending,
        accepted=accepted,
        completed=completed
    )
@app.route('/accept_donation/<donation_id>')
def accept_donation(donation_id):
    """NGO accepts a pending donation."""
    user = get_current_user()
    donation = Donation.query.filter_by(donation_id=donation_id).first()
    if not user or user.role != 'ngo' or not donation or donation.status != 'pending':
        return redirect(url_for('dashboard')) # Or show error

    donation.status = 'accepted'
    donation.accepted_by = user.uid
    donation.ngo_name = user.name
    db.session.commit()

    return redirect(url_for('dashboard'))
@app.route('/complete_donation/<donation_id>')
def complete_donation(donation_id):
    """NGO marks an accepted donation as complete."""
    user = get_current_user()
    donation = Donation.query.filter_by(donation_id=donation_id).first()
    if not user or user.role != 'ngo' or not donation or donation.accepted_by != user.uid:
        return redirect(url_for('dashboard')) # Or show error

    donation.status = 'completed'
    db.session.commit()

    return redirect(url_for('dashboard'))
if __name__ == '__main__':
    app.run(debug=True) 

    

