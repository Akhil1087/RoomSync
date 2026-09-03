from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin


db = SQLAlchemy()


class Admin(UserMixin, db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def role(self):
        return "admin"


class Student(UserMixin, db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile = db.relationship("Profile", back_populates="student", uselist=False, cascade="all, delete-orphan")

    @property
    def role(self):
        return "student"


class PGFlat(db.Model):
    __tablename__ = "pg_flats"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    address_line = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(20), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    image_urls = db.Column(db.Text, default="")
    rent_range_min = db.Column(db.Integer, default=0)
    rent_range_max = db.Column(db.Integer, default=0)
    amenities = db.Column(db.Text, default="")
    total_rooms = db.Column(db.Integer, default=0)
    available_rooms = db.Column(db.Integer, default=0)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profiles = db.relationship("Profile", back_populates="pg_flat")
    rooms = db.relationship("Room", back_populates="pg_flat", cascade="all, delete-orphan")

    @property
    def images(self):
        return [x.strip() for x in (self.image_urls or "").splitlines() if x.strip()]

    @property
    def amenity_list(self):
        return [x.strip() for x in (self.amenities or "").split(",") if x.strip()]


class Profile(db.Model):
    __tablename__ = "profiles"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), unique=True, nullable=False)
    budget_min = db.Column(db.Integer, default=0)
    budget_max = db.Column(db.Integer, default=0)
    sleep_schedule = db.Column(db.String(40), default="")
    cleanliness_level = db.Column(db.Integer, default=3)
    food_habits = db.Column(db.String(60), default="")
    social_habits = db.Column(db.String(60), default="")
    study_habits = db.Column(db.String(60), default="")
    bio = db.Column(db.Text, default="")
    pg_flat_id = db.Column(db.Integer, db.ForeignKey("pg_flats.id"))
    looking_since = db.Column(db.Date, default=datetime.utcnow().date)
    student = db.relationship("Student", back_populates="profile")
    pg_flat = db.relationship("PGFlat", back_populates="profiles")


class Room(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)
    pg_flat_id = db.Column(db.Integer, db.ForeignKey("pg_flats.id"), nullable=False)
    room_type = db.Column(db.String(60), nullable=False)
    rent_per_bed = db.Column(db.Integer, default=0)
    beds_available = db.Column(db.Integer, default=0)
    pg_flat = db.relationship("PGFlat", back_populates="rooms")


class ContactRequest(db.Model):
    __tablename__ = "contact_requests"
    id = db.Column(db.Integer, primary_key=True)
    from_student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    to_student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    from_student = db.relationship("Student", foreign_keys=[from_student_id])
    to_student = db.relationship("Student", foreign_keys=[to_student_id])


class ChatLog(db.Model):
    __tablename__ = "chat_logs"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sender = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
