from flask import Flask, redirect, url_for, session, render_template, request, jsonify
from wtforms import StringField, BooleanField
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Regexp, Length
from sqlalchemy_utils import UUIDType
import uuid
from pyotp import TOTP
import pyotp
import qrcode
import os
import secrets
from sqlalchemy.exc import IntegrityError
from flask import flash, jsonify
from wtforms import StringField, PasswordField, SubmitField, DateField, TimeField, SelectField
from wtforms.validators import DataRequired, EqualTo
from sqlalchemy import create_engine, UniqueConstraint
from sqlalchemy_utils import database_exists, create_database
from wtforms_alchemy import PhoneNumberField
from flask import session, redirect, url_for

app = Flask(__name__, static_folder='assets', static_url_path="")
app.config.update({
    'SECRET_KEY': 'your_secret_key',    
    'SQLALCHEMY_DATABASE_URI': 'postgresql://postgres:changeme@172.19.0.2/badminton',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False
})
def validate_database():
     engine = create_engine('postgresql://postgres:changeme@172.19.0.2/badminton')
     if not database_exists(engine.url): # Checks for the first time  
         create_database(engine.url)     # Create new DB    
         print("New Database Created" + database_exists(engine.url)) # Verifies if database is there or not.
     else:
         print("Database Already Exists")


db = SQLAlchemy(app)
with app.app_context():
    db.create_all()
migrate = Migrate(app, db)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile_number = db.Column(db.String(100), unique=True, nullable=False)   
    totp_secret_key = db.Column(db.String(36), nullable=False)
    qr_code = db.Column(db.String(200), nullable=False)

class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    mobile_number = StringField('Mobile', validators=[DataRequired(), Regexp('^[6-9][0-9]{9}$')])
    #mobile_number = StringField('Mobile',validators=[DataRequired(), Regexp('^[7-9][0-9]{9}$')])
    submit = SubmitField('Submit')

class Court(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cost_per_hour = db.Column(db.Numeric, nullable=False)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100), nullable=False)
    court_id = db.Column(db.Integer, db.ForeignKey('court.id'), nullable=False)
    booking_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    __table_args__ = (
        UniqueConstraint('court_id', 'booking_date', 'start_time', 'end_time', name='unique_booking'),
    )
    # Take 'user' session variable after successful login  for the 'user' field

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100), nullable=False)
    attendance_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)
    # Take 'user' session variable after successful login for the 'user' field

class CourtForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    cost_per_hour = StringField('Cost per Hour', validators=[DataRequired()])
    submit = SubmitField('Submit')

class AddBookingForm(FlaskForm):
    court_id = StringField('Court ID', validators=[DataRequired()])
    booking_date = DateField('Date', validators=[DataRequired()])
    user = StringField('User', validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    submit = SubmitField('Add Booking')

class AddAttendanceForm(FlaskForm):
    user = StringField('User', validators=[DataRequired()])
    attendance_date = DateField('Date', validators=[DataRequired()])
    status = SelectField('Status', choices=[('present', 'Present'), ('absent', 'Absent')], validators=[DataRequired()])
    submit = SubmitField('Add Attendance')

@app.route('/')
def home():
    return 'Hello, guest! <a href="/logout">Login</a>'

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        name = form.name.data
        mobile_number = form.mobile_number.data
        # Generate TOTP secret key and QR code
        totp_secret_key = pyotp.random_base32()
        qr_code_path = generate_qr_code(mobile_number, totp_secret_key)
        # Save TOTP secret key and QR code path to database
        user = User(name=name, mobile_number=mobile_number,  totp_secret_key=totp_secret_key, qr_code=qr_code_path)
        db.session.add(user)
        db.session.commit()
        flash('User registered successfully!', 'success')
        return redirect(url_for('setup_2fa', user_id=user.id))
    return render_template('register.html', form=form)

# New route for 2FA setup
@app.route('/setup-2fa/<int:user_id>')
def setup_2fa(user_id):
    user = User.query.get_or_404(user_id)
    
    # Generate QR code for user's TOTP secret key
    qr_code_path = generate_qr_code(user.mobile_number, user.totp_secret_key)
    prefix = '/static/'
    qr_code_strip = qr_code_path[qr_code_path.startswith(prefix) and len(prefix):]
    print(qr_code_strip)
    return render_template('setup_2fa.html', user=user, qr_code_path=qr_code_path)

def generate_qr_code(mobile_number, secret):
    otpauth_url = TOTP(secret).provisioning_uri(mobile_number, issuer_name='YourApp')
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(otpauth_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_path = f"assets/qr_codes/{mobile_number}_qr.png"
    qr_img.save(qr_path)
    return qr_path

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile_number = request.form['mobile_number']
        totp_code = request.form['totp_code']
        
        # Query the user by mobile_number
        user = User.query.filter_by(mobile_number=mobile_number).first()
        if user:
            # Verify the TOTP code
            totp = TOTP(user.totp_secret_key)
            if totp.verify(totp_code):
                # TOTP code is valid
                session['user_id'] = user.id
                session['user'] = user.name
                flash('Logged in successfully!', 'success')
                return redirect(url_for('index'))
            else:
                # TOTP code is invalid
                flash('Invalid TOTP code. Please try again.', 'error')
                return redirect(url_for('login'))
        else:
            # User not found
            flash('User not found. Please register.', 'error')
            return redirect(url_for('register'))
    return render_template('login.html')


# CRUD APIs for Courts
@app.route('/courts', methods=['GET'])
def get_courts():
    courts = Court.query.all()
    return render_template('courts.html', courts=courts)

@app.route('/courts/add', methods=['GET', 'POST'])
def add_court():
    form = CourtForm()
    if form.validate_on_submit():
        court = Court(name=form.name.data, cost_per_hour=form.cost_per_hour.data)
        db.session.add(court)
        db.session.commit()
        return redirect(url_for('.get_courts'))
    return render_template('add_court.html', form=form)

@app.route('/courts/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def manage_court(id):
    court = Court.query.get_or_404(id)
    if request.method == 'GET':
        return render_template('court_details.html', court=court)
    elif request.method == 'PUT':
        data = request.json
        court.name = data['name']
        court.cost_per_hour = data['cost_per_hour']
        db.session.commit()
        return redirect(url_for('.get_courts'))
    elif request.method == 'DELETE':
        db.session.delete(court)
        db.session.commit()
        return '', 204



# Similar CRUD APIs for Attendance

# Logout route
@app.route('/logout')
def logout():
    # Clear session variables
    session.clear()
    # Redirect to the login page (replace 'login' with the actual login route)
    return redirect(url_for('login'))

# Route to display session variables (for testing)
@app.route('/session')
def show_session():
    session_dict = dict(session)
    return jsonify(session_dict)

def generate_totp_secret():
    #return secrets.token_hex(16)  # Generate TOTP secret key
    #return TOTP().secret()
    pyotp.random_base32()

# CREATE: Add booking route
@app.route('/add_booking', methods=['GET', 'POST'])
def add_booking():
    
    form = AddBookingForm()
    if form.validate_on_submit():
        booking = Booking(
            court_id=form.court_id.data,
            booking_date=form.booking_date.data,
            user = form.user.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data
        )
        try:
            db.session.add(booking)
            db.session.commit()
            flash('Booking added successfully!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('Duplicate booking detected! Please choose a different time slot.', 'error')
        redirect_url = url_for('view_bookings')
        
        return render_template('redirect.html', redirect_url=redirect_url)
        
    else:
        return render_template('add_booking.html', form=form)

# READ: View bookings route
@app.route('/view_bookings')
def view_bookings():
    bookings = Booking.query.all()
    return render_template('view_bookings.html', bookings=bookings)

# UPDATE: Edit booking route
@app.route('/edit_booking/<int:booking_id>', methods=['GET', 'POST'])
def edit_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    form = AddBookingForm(obj=booking)
    if form.validate_on_submit():
        form.populate_obj(booking)
        db.session.commit()
        return redirect(url_for('booking_success'))
    return render_template('edit_booking.html', form=form, booking_id=booking_id)

# DELETE: Delete booking route
@app.route('/delete_booking/<int:booking_id>', methods=['POST'])
def delete_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    db.session.delete(booking)
    db.session.commit()
    return redirect(url_for('booking_success'))

# CREATE: Add attendance route
@app.route('/add_attendance', methods=['GET', 'POST'])
def add_attendance():
    form = AddAttendanceForm()
    if form.validate_on_submit():
        attendance = Attendance(
            user=form.user.data,
            attendance_date=form.attendance_date.data,
            status=form.status.data
        )
        db.session.add(attendance)
        db.session.commit()
        return redirect(url_for('view_attendance'))
    return render_template('add_attendance.html', form=form)

# READ: View attendance route
@app.route('/view_attendance')
def view_attendance():
    attendance = Attendance.query.all()
    return render_template('view_attendance.html', attendance=attendance)

# UPDATE: Edit attendance route
@app.route('/edit_attendance/<int:attendance_id>', methods=['GET', 'POST'])
def edit_attendance(attendance_id):
    attendance = Attendance.query.get_or_404(attendance_id)
    form = AddAttendanceForm(obj=attendance)
    if form.validate_on_submit():
        form.populate_obj(attendance)
        db.session.commit()
        return redirect(url_for('attendance_success'))
    return render_template('edit_attendance.html', form=form, attendance_id=attendance_id)

# DELETE: Delete attendance route
@app.route('/delete_attendance/<int:attendance_id>', methods=['POST'])
def delete_attendance(attendance_id):
    attendance = Attendance.query.get_or_404(attendance_id)
    db.session.delete(attendance)
    db.session.commit()
    return redirect(url_for('attendance_success'))


if __name__ == '__main__':    
    app.run(debug=True, host='0.0.0.0')
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True