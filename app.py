import math
import os
from datetime import date
from functools import wraps
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from matching import WEIGHTS, calculate_compatibility, get_ranked_matches
from models import Admin, ChatLog, ContactRequest, PGFlat, Profile, Room, Student, db

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "roomsync-dev-secret-change-me")
db_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'roomsync.db'}")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

CAMPUS_LAT = float(os.environ.get("CAMPUS_LAT", "28.6850"))
CAMPUS_LON = float(os.environ.get("CAMPUS_LON", "77.2060"))
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


@login_manager.user_loader
def load_user(user_id):
    kind, _, raw_id = user_id.partition(":")
    if kind == "admin":
        return db.session.get(Admin, int(raw_id))
    return db.session.get(Student, int(raw_id))


def _user_id(self):
    return f"{self.role}:{self.id}"

# UserMixin normally uses id; override with a stable role prefix to avoid collisions.
Admin.get_id = _user_id
Student.get_id = _user_id


def student_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if getattr(current_user, "role", None) != "student":
            flash("Student access only.", "danger")
            return redirect(url_for("admin_dashboard"))
        if not current_user.active:
            logout_user()
            flash("Your account is inactive.", "danger")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if getattr(current_user, "role", None) != "admin":
            flash("Admin access denied.", "danger")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


def distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def seed_data():
    if Admin.query.first():
        return
    admin = Admin(username="admin", password_hash=generate_password_hash("admin123"))
    db.session.add(admin)
    db.session.flush()
    listings = [
        PGFlat(name="Campus Nest PG", description="Student-friendly PG with Wi-Fi, meals and study spaces.", address_line="18 University Road", city="Delhi", state="Delhi", pincode="110007", latitude=28.689, longitude=77.212, rent_range_min=6500, rent_range_max=11000, amenities="WiFi, Food, Laundry, Study Room", total_rooms=30, available_rooms=8, created_by_admin_id=admin.id),
        PGFlat(name="Green View Flats", description="Quiet shared flats close to campus and public transport.", address_line="42 North Avenue", city="Delhi", state="Delhi", pincode="110009", latitude=28.695, longitude=77.201, rent_range_min=8000, rent_range_max=14000, amenities="WiFi, Parking, Kitchen, Balcony", total_rooms=16, available_rooms=4, created_by_admin_id=admin.id),
        PGFlat(name="Student Square", description="Affordable co-living property with common lounge.", address_line="7 College Lane", city="Delhi", state="Delhi", pincode="110006", latitude=28.676, longitude=77.214, rent_range_min=5500, rent_range_max=9500, amenities="WiFi, Food, Common Room", total_rooms=24, available_rooms=6, created_by_admin_id=admin.id),
    ]
    for pg in listings:
        pg.image_urls = "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=1200&q=80\nhttps://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=80"
        db.session.add(pg)
    db.session.commit()
    for pg, rooms in zip(listings, [("Single", 11000, 2), ("Twin", 8000, 4), ("Twin", 7000, 3)]):
        db.session.add(Room(pg_flat_id=pg.id, room_type=rooms[0], rent_per_bed=rooms[1], beds_available=rooms[2]))
    db.session.commit()


@app.context_processor
def inject_globals():
    return {"campus_lat": CAMPUS_LAT, "campus_lon": CAMPUS_LON, "weights": WEIGHTS}


@app.route("/")
def home():
    listings = PGFlat.query.order_by(PGFlat.created_at.desc()).limit(6).all()
    return render_template("home.html", listings=listings)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Name, email and a password of at least 6 characters are required.", "danger")
        elif Student.query.filter_by(email=email).first() or Admin.query.filter_by(username=email).first():
            flash("An account with that email already exists.", "danger")
        else:
            student = Student(full_name=name, email=email, phone=phone, password_hash=generate_password_hash(password))
            db.session.add(student)
            db.session.commit()
            login_user(student)
            flash("Account created. Now complete your roommate profile.", "success")
            return redirect(url_for("profile"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        student = Student.query.filter_by(email=email).first()
        if student and student.active and check_password_hash(student.password_hash, password):
            login_user(student)
            return redirect(url_for("dashboard"))
        flash("Invalid student login details.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/profile", methods=["GET", "POST"])
@student_required
def profile():
    profile = current_user.profile or Profile(student_id=current_user.id)
    pgs = PGFlat.query.order_by(PGFlat.name).all()
    if request.method == "POST":
        profile.budget_min = parse_int(request.form.get("budget_min"))
        profile.budget_max = parse_int(request.form.get("budget_max"))
        profile.sleep_schedule = request.form.get("sleep_schedule", "")
        profile.cleanliness_level = parse_int(request.form.get("cleanliness_level"), 3)
        profile.food_habits = request.form.get("food_habits", "")
        profile.social_habits = request.form.get("social_habits", "")
        profile.study_habits = request.form.get("study_habits", "")
        profile.bio = request.form.get("bio", "").strip()
        profile.pg_flat_id = parse_int(request.form.get("pg_flat_id"), 0) or None
        profile.looking_since = date.fromisoformat(request.form.get("looking_since")) if request.form.get("looking_since") else date.today()
        current_user.phone = request.form.get("phone", "").strip()
        db.session.add(profile)
        db.session.commit()
        flash("Profile saved successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("profile_form.html", profile=profile, pgs=pgs)


@app.route("/dashboard")
@student_required
def dashboard():
    return render_template("dashboard.html", profile=current_user.profile)


@app.route("/pgs")
@student_required
def browse_pgs():
    city = request.args.get("city", "").strip()
    max_rent = parse_int(request.args.get("max_rent"), 0)
    max_distance = parse_float(request.args.get("distance"), 0)
    amenity = request.args.get("amenity", "").strip().lower()
    listings = PGFlat.query.order_by(PGFlat.name).all()
    items = []
    for pg in listings:
        d = distance_km(CAMPUS_LAT, CAMPUS_LON, pg.latitude, pg.longitude)
        if city and pg.city.lower() != city.lower():
            continue
        if max_rent and pg.rent_range_min > max_rent:
            continue
        if max_distance and d > max_distance:
            continue
        if amenity and amenity not in (pg.amenities or "").lower():
            continue
        items.append((pg, d))
    cities = sorted({p.city for p in listings})
    return render_template("pgs.html", items=items, cities=cities)


@app.route("/pg/<int:pg_id>")
@student_required
def pg_detail(pg_id):
    pg = db.get_or_404(PGFlat, pg_id)
    students = get_ranked_matches(current_user, Student.query.all(), pg_id=pg.id)
    distance = distance_km(CAMPUS_LAT, CAMPUS_LON, pg.latitude, pg.longitude)
    return render_template("pg_detail.html", pg=pg, students=students, distance=distance)


@app.route("/student/<int:student_id>")
@student_required
def student_view(student_id):
    student = db.get_or_404(Student, student_id)
    if not student.active or not student.profile:
        flash("Profile unavailable.", "warning")
        return redirect(url_for("browse_pgs"))
    score, breakdown = calculate_compatibility(current_user.profile, student.profile)
    return render_template("student_view.html", student=student, score=score, breakdown=breakdown)


@app.route("/matches")
@student_required
def matches():
    results = get_ranked_matches(current_user, Student.query.all())
    return render_template("matches.html", results=results)


@app.post("/contact/<int:student_id>")
@student_required
def contact(student_id):
    if student_id == current_user.id:
        flash("You cannot contact yourself.", "warning")
        return redirect(request.referrer or url_for("matches"))
    target = db.get_or_404(Student, student_id)
    existing = ContactRequest.query.filter_by(from_student_id=current_user.id, to_student_id=target.id, status="pending").first()
    if not existing:
        db.session.add(ContactRequest(from_student_id=current_user.id, to_student_id=target.id))
        db.session.commit()
        flash("Contact request sent.", "success")
    else:
        flash("You already have a pending request.", "info")
    return redirect(request.referrer or url_for("matches"))


@app.route("/requests")
@student_required
def requests_page():
    incoming = ContactRequest.query.filter_by(to_student_id=current_user.id).order_by(ContactRequest.created_at.desc()).all()
    outgoing = ContactRequest.query.filter_by(from_student_id=current_user.id).order_by(ContactRequest.created_at.desc()).all()
    return render_template("requests.html", incoming=incoming, outgoing=outgoing)


@app.post("/requests/<int:req_id>/<action>")
@student_required
def request_action(req_id, action):
    req = db.get_or_404(ContactRequest, req_id)
    if req.to_student_id != current_user.id or action not in {"accept", "decline"}:
        flash("Action not allowed.", "danger")
        return redirect(url_for("requests_page"))
    req.status = "accepted" if action == "accept" else "declined"
    db.session.commit()
    flash(f"Request {req.status}.", "success")
    return redirect(url_for("requests_page"))


# ---------------- Admin ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            login_user(admin)
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "danger")
    return render_template("admin_login.html")


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", students=Student.query.count(), pgs=PGFlat.query.count(), requests=ContactRequest.query.count())


@app.route("/admin/pgs")
@admin_required
def admin_pgs():
    return render_template("admin_pgs.html", pgs=PGFlat.query.order_by(PGFlat.created_at.desc()).all())


@app.route("/admin/pg/new", methods=["GET", "POST"])
@app.route("/admin/pg/<int:pg_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_pg_form(pg_id=None):
    pg = db.session.get(PGFlat, pg_id) if pg_id else PGFlat()
    if request.method == "POST":
        pg.name = request.form.get("name", "").strip()
        pg.description = request.form.get("description", "").strip()
        pg.address_line = request.form.get("address_line", "").strip()
        pg.city = request.form.get("city", "").strip()
        pg.state = request.form.get("state", "").strip()
        pg.pincode = request.form.get("pincode", "").strip()
        pg.latitude = parse_float(request.form.get("latitude"))
        pg.longitude = parse_float(request.form.get("longitude"))
        pg.rent_range_min = parse_int(request.form.get("rent_range_min"))
        pg.rent_range_max = parse_int(request.form.get("rent_range_max"))
        pg.amenities = request.form.get("amenities", "").strip()
        pg.total_rooms = parse_int(request.form.get("total_rooms"))
        pg.available_rooms = parse_int(request.form.get("available_rooms"))
        urls = request.form.get("image_urls", "").strip()
        uploaded = []
        for file in request.files.getlist("images"):
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                stem, ext = os.path.splitext(filename)
                final = f"{stem}-{os.urandom(4).hex()}{ext}"
                file.save(UPLOAD_DIR / final)
                uploaded.append(url_for("static", filename=f"uploads/{final}"))
        pg.image_urls = "\n".join([x for x in [urls, "\n".join(uploaded)] if x])
        pg.created_by_admin_id = current_user.id
        if not pg.id:
            db.session.add(pg)
        db.session.commit()
        flash("PG listing saved.", "success")
        return redirect(url_for("admin_pgs"))
    return render_template("admin_pg_form.html", pg=pg)


@app.post("/admin/pg/<int:pg_id>/delete")
@admin_required
def admin_pg_delete(pg_id):
    pg = db.get_or_404(PGFlat, pg_id)
    db.session.delete(pg)
    db.session.commit()
    flash("PG listing deleted.", "success")
    return redirect(url_for("admin_pgs"))


@app.route("/admin/students")
@admin_required
def admin_students():
    return render_template("admin_students.html", students=Student.query.order_by(Student.created_at.desc()).all())


@app.post("/admin/student/<int:student_id>/toggle")
@admin_required
def admin_toggle_student(student_id):
    student = db.get_or_404(Student, student_id)
    student.active = not student.active
    db.session.commit()
    flash("Student status updated.", "success")
    return redirect(url_for("admin_students"))


# ---------------- Rule-based assistant ----------------
FAQ = {
    "compatibility": "Compatibility is weighted: budget 20%, cleanliness 20%, sleep 20%, food 15%, social 15%, study 10%.",
    "edit profile": "Open My Profile from the navigation bar, update your preferences, and press Save Profile.",
    "contact": "Open a student profile or match card and press Send Contact Request. The other student can accept or decline it.",
    "pg": "PGs are added by the admin. Choose your preferred PG while creating or editing your student profile.",
    "distance": "Distance is calculated in a straight line from the configured campus coordinates. Browse PGs and choose a distance filter.",
    "admin": "Admin tools are private and are available only through the separate /admin/login route.",
}

GUIDE = [
    ("budget", "What is your monthly budget? Reply like 7000-12000.", "budget"),
    ("sleep_schedule", "What is your sleep schedule: Early, Regular, or Late?", "sleep_schedule"),
    ("cleanliness_level", "How clean are you on a scale of 1 to 5?", "cleanliness_level"),
    ("food_habits", "What are your food habits: Vegetarian, Non-vegetarian, Eggetarian, Vegan, or No preference?", "food_habits"),
    ("social_habits", "How social are you: Quiet, Moderate, Social, or Very social?", "social_habits"),
    ("study_habits", "How do you study: Quiet, Moderate, Group study, or Flexible?", "study_habits"),
    ("pg_flat_id", "Which PG would you prefer? Open My Profile after this and choose it from the property list.", "pg_flat_id"),
]


def parse_guide_answer(field, message):
    m = message.strip().lower()
    if field == "budget":
        import re
        nums = [int(x) for x in re.findall(r"\d+", m)]
        if len(nums) >= 2:
            return {"budget_min": nums[0], "budget_max": nums[1]}
        return None
    if field == "cleanliness_level":
        import re
        nums = re.findall(r"[1-5]", m)
        return {field: int(nums[0])} if nums else None
    choices = {
        "sleep_schedule": ["Early", "Regular", "Late"],
        "food_habits": ["Vegetarian", "Non-vegetarian", "Eggetarian", "Vegan", "No preference"],
        "social_habits": ["Quiet", "Moderate", "Social", "Very social"],
        "study_habits": ["Quiet", "Moderate", "Group study", "Flexible"],
    }
    if field in choices:
        for choice in choices[field]:
            if choice.lower() in m:
                return {field: choice}
    return None


def assistant_reply(message):
    m = message.lower().strip()
    if any(x in m for x in ["fill my profile", "build my profile", "complete my profile", "help me fill"]):
        from flask import session
        session["guide_index"] = 0
        return GUIDE[0][1], GUIDE[0][0], None
    for key, reply in FAQ.items():
        if key in m:
            return reply, None, None
    if "hello" in m or "hi" in m:
        return "Hi! I can explain matching, PGs, profiles, distance or contact requests. Say 'help me fill my profile' to start guided setup.", None, None
    return "I can help with compatibility, editing your profile, PG listings, distance filters, contact requests, or guided profile setup.", None, None


@app.post("/api/chat")
@student_required
def api_chat():
    from flask import session
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"reply": "Type a question and I'll help."})
    db.session.add(ChatLog(student_id=current_user.id, message=message, sender="student"))

    # Continue an active guided profile session.
    if "guide_index" in session:
        idx = int(session.get("guide_index", 0))
        if idx < len(GUIDE):
            field, question, form_field = GUIDE[idx]
            parsed = parse_guide_answer(field, message)
            if not parsed:
                reply = f"I couldn't read that yet. {question}"
                db.session.add(ChatLog(student_id=current_user.id, message=reply, sender="assistant"))
                db.session.commit()
                return jsonify({"reply": reply, "field": None, "values": {}})
            # Save immediately where possible.
            profile = current_user.profile or Profile(student_id=current_user.id)
            for key, value in parsed.items():
                setattr(profile, key, value)
            db.session.add(profile)
            db.session.commit()
            idx += 1
            session["guide_index"] = idx
            if idx >= len(GUIDE):
                session.pop("guide_index", None)
                reply = "Done! I saved the answers I collected. Open My Profile to choose your PG and add your bio, then save the profile."
                values = parsed
            else:
                reply = f"Saved. {GUIDE[idx][1]}"
                values = parsed
            db.session.add(ChatLog(student_id=current_user.id, message=reply, sender="assistant"))
            db.session.commit()
            return jsonify({"reply": reply, "field": field, "values": values})

    reply, _, _ = assistant_reply(message)
    db.session.add(ChatLog(student_id=current_user.id, message=reply, sender="assistant"))
    db.session.commit()
    return jsonify({"reply": reply, "field": None, "values": {}})


with app.app_context():
    db.create_all()
    seed_data()


if __name__ == "__main__":
    app.run(debug=True)
