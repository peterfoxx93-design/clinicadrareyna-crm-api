"""Clínica Dental CRM — Backend Flask (Render compatible)"""
import os, sys, json, csv, io
from datetime import datetime, date, timedelta
from functools import wraps
from collections import Counter

from flask import (Flask, render_template, request, redirect, url_for,
                   jsonify, session, send_from_directory)
from flask_login import (LoginManager, login_user, logout_user,
                          login_required, current_user)
from flask_cors import CORS
from sqlalchemy import func
import requests as http_req

import resend

sys.path.insert(0, os.path.dirname(__file__))
from models import db, User, Patient, Appointment, TreatmentPlan, PatientInteraction, Service, Doctor, BlockedSchedule, init_db

# Resend
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', 're_8WZh1FS5_NNxkw7opeabxFV7QixMu97cH')
resend.api_key = RESEND_API_KEY
RESEND_FROM = os.environ.get('RESEND_FROM', 'onboarding@resend.dev')
RESEND_TO = os.environ.get('RESEND_TO', 'espartaco.rd@gmail.com')

def send_clinic_email(subject, html_body):
    """Envía email via Resend."""
    try:
        resend.Emails.send({
            "from": RESEND_FROM,
            "to": [RESEND_TO],
            "subject": subject,
            "html": html_body,
        })
    except Exception as e:
        print(f"[Resend] Error sending email: {e}")

# ============================================================
# Chat AI Config — Valentina (Clínica Dental)
# ============================================================
OPENROUTER_KEY = ''
for key_name in ['OPENROUTER_API_KEY_1', 'OPENROUTER_API_KEY_2', 'OPENROUTER_API_KEY']:
    val = os.environ.get(key_name, '')
    if val:
        OPENROUTER_KEY = val
        break
if not OPENROUTER_KEY:
    try:
        with open(os.path.expanduser('~/.env')) as f:
            for line in f:
                if 'OPENROUTER_API_KEY' in line and '=' in line:
                    OPENROUTER_KEY = line.split('=', 1)[1].strip().strip("'\"")
                    break
    except:
        pass

CHAT_MODEL = 'deepseek/deepseek-v4-flash'
VALENTINA_SYSTEM_PROMPT = "Eres Valentina, asistente virtual de la Dra. Reyna Pimentel, odontóloga en Nagua, RD. Ayudas a pacientes a agendar citas. Respondes en español dominicano profesional y cálido. NUNCA digas que eres una IA. NUNCA menciones herramientas internas. Tus respuestas son concisas, máx 3 párrafos. La clínica está en C/ Amalio Alonzo #24, Nagua. Tel: (809) 584-7033."

def call_ai(user_msg, history=None):
    messages = [{'role': 'system', 'content': VALENTINA_SYSTEM_PROMPT}]
    if history:
        for h in history[-6:]:
            messages.append({'role': 'user', 'content': h.get('user', '')})
            if h.get('bot'):
                messages.append({'role': 'assistant', 'content': h['bot']})
    messages.append({'role': 'user', 'content': user_msg})

    resp = http_req.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {OPENROUTER_KEY}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://dra-reyna-pimentel.vercel.app',
        },
        json={
            'model': CHAT_MODEL,
            'messages': messages,
            'max_tokens': 500,
            'temperature': 0.7,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise Exception(f'AI API error: {resp.status_code}')
    reply = resp.json()['choices'][0]['message']['content']
    if 'mcp_' in reply or 'write_file' in reply:
        reply = reply.split('mcp_')[0].strip() or 'Entendido. ¿En qué más puedo ayudarte?'
    return reply

# Config
BASE = os.path.dirname(os.path.dirname(__file__))
FRONTEND = os.path.join(BASE, 'frontend')

app = Flask(__name__,
            static_folder=FRONTEND,
            template_folder=FRONTEND)
app.debug = False
app.secret_key = os.environ.get('CLINICA_SECRET', 'reyna-pimentel-2026')

# Database: Render provides DATABASE_URL (postgres://) — fix for SQLAlchemy
database_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE, 'data', 'clinica.db'))
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# CORS — permite que la landing page (Vercel) llame a la API
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'https://dra-reyna-pimentel.vercel.app,https://*.vercel.app')
CORS(app, origins=CORS_ORIGINS.split(','), supports_credentials=True)

init_db(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ============================================================
# SEED SERVICES
# ============================================================
def seed_services():
    """Create default services if none exist."""
    if Service.query.count() == 0:
        defaults = [
            ('Consulta general', 'Evaluación completa del estado bucal', 30, 1500.0),
            ('Limpieza bucal', 'Profilaxis dental: limpieza profunda y remoción de sarro', 45, 2500.0),
            ('Ortodoncia invisible', 'Consulta inicial de alineadores Invisalign', 60, 0.0),
            ('Extracción simple', 'Extracción de pieza dental sin complicaciones', 30, 3000.0),
            ('Blanqueamiento dental', 'Blanqueamiento con gel profesional y leds', 60, 8500.0),
            ('Radiografía panorámica', 'Estudio radiográfico completo de la boca', 15, 1200.0),
            ('Revisión de ortodoncia', 'Control periódico de brackets o alineadores', 20, 0.0),
            ('Urgencia dental', 'Atención inmediata para emergencias', 30, 0.0),
        ]
        for i, (name, desc, dur, price) in enumerate(defaults):
            db.session.add(Service(name=name, description=desc, duration_minutes=dur, price=price, sort_order=i))
        db.session.commit()

with app.app_context():
    seed_services()
    # Migration: add doctor_id column if missing
    try:
        db.session.execute(db.text('ALTER TABLE appointments ADD COLUMN doctor_id INTEGER REFERENCES doctors(id)'))
        db.session.commit()
        print("[Migration] Added doctor_id to appointments")
    except Exception:
        db.session.rollback()
        # Column already exists, no problem

# ============================================================
# PUBLIC ROUTES (no auth)
# ============================================================
@app.route('/agendar')
def public_booking():
    """Página pública de reserva de citas."""
    return send_from_directory(FRONTEND, 'agendar.html')

@app.route('/api/public/services', methods=['GET'])
def api_public_services():
    """Lista servicios activos (público)."""
    services = Service.query.filter_by(active=True).order_by(Service.sort_order).all()
    return jsonify({'services': [s.to_dict() for s in services]})

@app.route('/api/public/book', methods=['POST'])
def api_public_book():
    """Reserva pública sin autenticación."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos requeridos'}), 400

    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()
    service_name = (data.get('service') or 'consulta').strip()
    doctor_id = data.get('doctor_id')
    appt_datetime_str = data.get('datetime', '').strip()

    if not name:
        return jsonify({'error': 'El nombre es obligatorio'}), 400
    if not appt_datetime_str:
        return jsonify({'error': 'La fecha y hora son obligatorias'}), 400

    try:
        appt_datetime = datetime.fromisoformat(appt_datetime_str)
    except:
        return jsonify({'error': 'Formato de fecha inválido'}), 400

    # Find or create patient
    patient = Patient.query.filter_by(phone=phone).first() if phone else None
    if not patient:
        patient = Patient.query.filter_by(email=email).first() if email else None
    if not patient:
        patient = Patient(name=name, phone=phone, email=email,
                          source='web', status='nuevo',
                          notes=f'Reserva vía web. Servicio: {service_name}')
        db.session.add(patient)
        db.session.flush()

    # Create appointment
    appt = Appointment(
        patient_id=patient.id,
        appt_datetime=appt_datetime,
        duration_minutes=30,
        appt_type=service_name,
        doctor_id=doctor_id if doctor_id else None,
        notes=f'Reservado desde la web',
        status='pendiente',
    )
    db.session.add(appt)

    if patient.status == 'nuevo':
        patient.status = 'agendado'

    db.session.commit()

    # Notify via Resend
    try:
        appt_date = appt_datetime.strftime('%d/%m/%Y')
        appt_time = appt_datetime.strftime('%I:%M %p')
        send_clinic_email(
            f"🆕 Reserva web — {name}",
            f"<h2>Nueva reserva desde la web</h2>"
            f"<p><strong>Paciente:</strong> {name}<br>"
            f"<strong>Teléfono:</strong> {phone or '—'}<br>"
            f"<strong>Email:</strong> {email or '—'}<br>"
            f"<strong>Servicio:</strong> {service_name}<br>"
            f"<strong>Fecha:</strong> {appt_date}<br>"
            f"<strong>Hora:</strong> {appt_time}</p>"
            f"<p>Ingresa al CRM para confirmar la cita.</p>"
        )
    except Exception as e:
        print(f"[Resend] notify error: {e}")

    return jsonify({'success': True, 'appointment_id': appt.id}), 201

@app.route('/api/public/doctors', methods=['GET'])
def api_public_doctors():
    """Lista doctores activos (público)."""
    doctors = Doctor.query.filter_by(active=True).order_by(Doctor.sort_order).all()
    return jsonify({'doctors': [d.to_dict() for d in doctors]})

@app.route('/api/public/availability', methods=['GET'])
def api_public_availability():
    """Horarios disponibles para un doctor en una fecha específica."""
    doctor_id = request.args.get('doctor_id', type=int)
    date_str = request.args.get('date', '').strip()

    if not doctor_id or not date_str:
        return jsonify({'error': 'doctor_id and date required'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return jsonify({'error': 'Invalid date format (use YYYY-MM-DD)'}), 400

    # Check if date is in the past
    if target_date < date.today():
        return jsonify({'slots': []})

    # Check if it's weekend (Sunday=6)
    if target_date.weekday() == 6:
        return jsonify({'slots': []})

    # Generate all possible slots (8:00 - 17:00, 30min intervals)
    all_slots = []
    for h in range(8, 17):
        for m in [0, 30]:
            all_slots.append(f'{h:02d}:{m:02d}')

    # Saturday: only until 13:00
    if target_date.weekday() == 5:
        all_slots = [s for s in all_slots if int(s.split(':')[0]) < 13]

    # Remove slots that are blocked
    blocked = BlockedSchedule.query.filter(
        BlockedSchedule.block_date == target_date,
        db.or_(BlockedSchedule.doctor_id == doctor_id, BlockedSchedule.doctor_id.is_(None))
    ).all()

    blocked_slots = set()
    for b in blocked:
        if not b.start_time and not b.end_time:
            # Whole day blocked
            return jsonify({'slots': []})
        # Parse blocked range
        b_start = int(b.start_time.split(':')[0]) * 60 + int(b.start_time.split(':')[1])
        b_end = int(b.end_time.split(':')[0]) * 60 + int(b.end_time.split(':')[1]) if b.end_time else b_start + 30
        for s in all_slots:
            s_min = int(s.split(':')[0]) * 60 + int(s.split(':')[1])
            if b_start <= s_min < b_end:
                blocked_slots.add(s)

    # Remove slots that already have appointments
    booked = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        db.func.date(Appointment.appt_datetime) == target_date,
        Appointment.status.in_(['pendiente', 'confirmada'])
    ).all()

    for appt in booked:
        appt_start = appt.appt_datetime.hour * 60 + appt.appt_datetime.minute
        appt_end = appt_start + (appt.duration_minutes or 30)
        for s in all_slots:
            s_min = int(s.split(':')[0]) * 60 + int(s.split(':')[1])
            if appt_start <= s_min < appt_end:
                blocked_slots.add(s)

    # Available slots
    available = [s for s in all_slots if s not in blocked_slots]

    return jsonify({'slots': available, 'date': date_str, 'doctor_id': doctor_id})

# ============================================================
# CONFIG
# ============================================================
CONFIG_PATH = os.path.join(BASE, 'config', 'clinica_config.json')

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except:
        return {
            "clinica": {
                "nombre": "Clínica Dental Pimentel",
                "eslogan": "Tu sonrisa, nuestra prioridad",
                "direccion": "Puerto Plata, República Dominicana",
                "telefono": "809-584-7033",
                "email": "contacto@clinicadentalpimentel.com",
                "sitio_web": "dra-reyna-pimentel.vercel.app",
                "color_primario": "#4472C4",
                "color_secundario": "#2c5aa0"
            }
        }

# ============================================================
# AUTH
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next', '/')
            return redirect(next_page)
        return render_template('login.html', error='Usuario o contraseña incorrectos')
    return render_template('login_clinica.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# ============================================================
# PAGES
# ============================================================
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard_clinica.html')

@app.route('/pacientes')
@login_required
def pacientes():
    return render_template('dashboard_clinica.html')

@app.route('/paciente/<int:pid>')
@login_required
def paciente_detail(pid):
    return render_template('dashboard_clinica.html')

@app.route('/citas')
@login_required
def citas():
    return render_template('dashboard_clinica.html')

@app.route('/tratamientos')
@login_required
def tratamientos():
    return render_template('dashboard_clinica.html')

@app.route('/recall')
@login_required
def recall():
    return render_template('dashboard_clinica.html')

@app.route('/servicios')
@login_required
def servicios():
    return render_template('dashboard_clinica.html')

@app.route('/reportes')
@login_required
def reportes():
    return render_template('dashboard_clinica.html')

@app.route('/doctores')
@login_required
def doctores():
    return render_template('dashboard_clinica.html')

@app.route('/bloqueo')
@login_required
def bloqueo():
    return render_template('dashboard_clinica.html')

@app.route('/finanzas')
@login_required
def finanzas():
    return render_template('dashboard_clinica.html')

# ============================================================
# API — Stats
# ============================================================
@app.route('/api/stats', methods=['GET'])
@login_required
def api_get_stats():
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total = Patient.query.count()
    today_new = Patient.query.filter(Patient.created_at >= today_start).count()
    
    by_status = {}
    for s in ['nuevo', 'agendado', 'diagnosticado', 'plan_aceptado',
              'en_tratamiento', 'completado', 'retorno', 'perdido']:
        by_status[s] = Patient.query.filter_by(status=s).count()

    today_appts = Appointment.query.filter(
        Appointment.appt_datetime >= today_start,
        Appointment.appt_datetime < today_start + timedelta(days=1)
    ).count()

    upcoming = Appointment.query.filter(
        Appointment.appt_datetime >= now,
        Appointment.status.in_(['pendiente', 'confirmada'])
    ).count()

    # Recall count: patients with next_recall <= 30 days from now
    recall_due = Patient.query.filter(
        Patient.next_recall <= now + timedelta(days=30),
        Patient.next_recall.isnot(None),
        Patient.status != 'perdido'
    ).count()

    # Treatment plans pending acceptance
    plans_pending = TreatmentPlan.query.filter(
        TreatmentPlan.status == 'presentado'
    ).count()

    active_treatments = TreatmentPlan.query.filter(
        TreatmentPlan.status.in_(['aceptado', 'en_progreso'])
    ).count()

    # Monthly revenue (simplified)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_revenue = db.session.query(func.sum(TreatmentPlan.amount_paid)).filter(
        TreatmentPlan.completed_at >= month_start
    ).scalar() or 0.0

    return jsonify({
        'total_patients': total,
        'today_new': today_new,
        'by_status': by_status,
        'today_appointments': today_appts,
        'upcoming_appointments': upcoming,
        'recall_due': recall_due,
        'plans_pending': plans_pending,
        'active_treatments': active_treatments,
        'month_revenue': month_revenue,
    })

# ============================================================
# API — Patients
# ============================================================
@app.route('/api/patients', methods=['GET'])
@login_required
def api_get_patients():
    status_filter = request.args.get('status')
    search = request.args.get('search', '').strip()
    recall = request.args.get('recall', '').lower() == 'true'

    query = Patient.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(Patient.name.ilike(like),
                   Patient.phone.ilike(like))
        )
    if recall:
        cutoff = datetime.utcnow() + timedelta(days=30)
        query = query.filter(
            Patient.next_recall <= cutoff,
            Patient.next_recall.isnot(None),
            Patient.status != 'perdido'
        )

    query = query.order_by(Patient.updated_at.desc())
    patients = query.all()
    return jsonify({
        'patients': [p.to_dict() for p in patients],
        'total': len(patients)
    })

@app.route('/api/patients', methods=['POST'])
@login_required
def api_create_patient():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name is required'}), 400

    patient = Patient(
        name=data['name'].strip(),
        phone=data.get('phone', '').strip(),
        email=data.get('email', '').strip(),
        birthdate=data.get('birthdate', ''),
        source=data.get('source', 'whatsapp'),
        status='nuevo',
        referral_source=data.get('referral_source', ''),
        notes=data.get('notes', ''),
    )
    db.session.add(patient)
    db.session.commit()
    return jsonify({'patient': patient.to_dict(), 'success': True}), 201

@app.route('/api/patients/<int:pid>', methods=['GET'])
@login_required
def api_get_patient(pid):
    patient = db.session.get(Patient, pid)
    if not patient:
        return jsonify({'error': 'not found'}), 404
    data = patient.to_dict()
    data['appointments'] = [a.to_dict() for a in patient.appointments.all()]
    data['treatments'] = [t.to_dict() for t in patient.treatments.all()]
    data['interactions'] = [i.to_dict() for i in patient.interactions.all()]
    return jsonify(data)

@app.route('/api/patients/<int:pid>', methods=['PUT'])
@login_required
def api_update_patient(pid):
    patient = db.session.get(Patient, pid)
    if not patient:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    for field in ['name', 'phone', 'email', 'birthdate', 'source', 'status',
                  'notes', 'referral_source', 'total_spent', 'last_visit', 'next_recall']:
        if field in data:
            setattr(patient, field, data[field])
    patient.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'patient': patient.to_dict(), 'success': True})

@app.route('/api/patients/<int:pid>', methods=['DELETE'])
@login_required
def api_delete_patient(pid):
    patient = db.session.get(Patient, pid)
    if not patient:
        return jsonify({'error': 'not found'}), 404
    db.session.delete(patient)
    db.session.commit()
    return jsonify({'success': True})

# ============================================================
# API — Appointments
# ============================================================
@app.route('/api/appointments', methods=['GET'])
@login_required
def api_get_appointments():
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    today = request.args.get('today', '').lower() == 'true'

    query = Appointment.query
    if today:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(
            Appointment.appt_datetime >= today_start,
            Appointment.appt_datetime < today_start + timedelta(days=1)
        )
    if date_from:
        query = query.filter(Appointment.appt_datetime >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Appointment.appt_datetime <= datetime.fromisoformat(date_to))

    appointments = query.order_by(Appointment.appt_datetime).all()
    return jsonify({
        'appointments': [a.to_dict() for a in appointments],
        'total': len(appointments)
    })

@app.route('/api/appointments', methods=['POST'])
@login_required
def api_create_appointment():
    data = request.get_json()
    if not data or not data.get('patient_id') or not data.get('appt_datetime'):
        return jsonify({'error': 'patient_id and appt_datetime required'}), 400

    appt = Appointment(
        patient_id=data['patient_id'],
        appt_datetime=datetime.fromisoformat(data['appt_datetime']),
        duration_minutes=data.get('duration_minutes', 30),
        appt_type=data.get('appt_type', 'consulta'),
        notes=data.get('notes', ''),
        status='pendiente',
    )
    db.session.add(appt)

    # Update patient status
    patient = db.session.get(Patient, data['patient_id'])
    if patient and patient.status == 'nuevo':
        patient.status = 'agendado'

    db.session.commit()

    # Notify — nueva cita agendada
    try:
        pt_name = patient.name if patient else 'Paciente'
        appt_date = appt.appt_datetime.strftime('%d/%m/%Y')
        appt_time = appt.appt_datetime.strftime('%I:%M %p')
        send_clinic_email(
            f"🆕 Nueva cita agendada — {pt_name}",
            f"<h2>Nueva cita registrada</h2>"
            f"<p><strong>Paciente:</strong> {pt_name}<br>"
            f"<strong>Servicio:</strong> {appt.appt_type}<br>"
            f"<strong>Fecha:</strong> {appt_date}<br>"
            f"<strong>Hora:</strong> {appt_time}<br>"
            f"<strong>Estado:</strong> Pendiente de confirmación</p>"
            f"<p>Ingresa al CRM para confirmar o reprogramar.</p>"
        )
    except Exception as e:
        print(f"[Resend] notify error: {e}")

    return jsonify({'appointment': appt.to_dict(), 'success': True}), 201

@app.route('/api/appointments/<int:aid>', methods=['PUT'])
@login_required
def api_update_appointment(aid):
    appt = db.session.get(Appointment, aid)
    if not appt:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    old_status = appt.status
    for field in ['appt_datetime', 'duration_minutes', 'appt_type', 'notes', 'status']:
        if field in data:
            if field == 'appt_datetime':
                setattr(appt, field, datetime.fromisoformat(data[field]))
            else:
                setattr(appt, field, data[field])

    # If completed, update patient
    if data.get('status') == 'completada':
        patient = appt.patient
        patient.last_visit = datetime.utcnow()
        # Set recall for 6 months
        patient.next_recall = datetime.utcnow() + timedelta(days=180)
        if patient.status == 'agendado' or patient.status == 'en_tratamiento':
            patient.status = 'completado'
        # Set next recall on patient
        db.session.add(patient)

    db.session.commit()

    # Notify — cita confirmada
    if data.get('status') == 'confirmada' and old_status != 'confirmada':
        try:
            pt = appt.patient
            pt_name = pt.name if pt else 'Paciente'
            appt_date = appt.appt_datetime.strftime('%d/%m/%Y')
            appt_time = appt.appt_datetime.strftime('%I:%M %p')
            send_clinic_email(
                f"✅ Cita confirmada — {pt_name}",
                f"<h2>¡Cita confirmada!</h2>"
                f"<p><strong>Paciente:</strong> {pt_name}<br>"
                f"<strong>Servicio:</strong> {appt.appt_type}<br>"
                f"<strong>Fecha:</strong> {appt_date}<br>"
                f"<strong>Hora:</strong> {appt_time}</p>"
                f"<p>✅ La cita ha sido confirmada.</p>"
            )
        except Exception as e:
            print(f"[Resend] notify error: {e}")

    # Notify — cita cancelada
    if data.get('status') == 'cancelada' and old_status != 'cancelada':
        try:
            pt = appt.patient
            pt_name = pt.name if pt else 'Paciente'
            send_clinic_email(
                f"❌ Cita cancelada — {pt_name}",
                f"<h2>Cita cancelada</h2>"
                f"<p><strong>Paciente:</strong> {pt_name}<br>"
                f"<strong>Servicio:</strong> {appt.appt_type}</p>"
                f"<p>La cita ha sido cancelada.</p>"
            )
        except Exception as e:
            print(f"[Resend] notify error: {e}")

    return jsonify({'appointment': appt.to_dict(), 'success': True})

# ============================================================
# API — Treatment Plans
# ============================================================
@app.route('/api/treatments', methods=['GET'])
@login_required
def api_get_treatments():
    status_filter = request.args.get('status')
    query = TreatmentPlan.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    treatments = query.order_by(TreatmentPlan.created_at.desc()).all()
    return jsonify({'treatments': [t.to_dict() for t in treatments]})

@app.route('/api/treatments', methods=['POST'])
@login_required
def api_create_treatment():
    data = request.get_json()
    if not data or not data.get('patient_id'):
        return jsonify({'error': 'patient_id required'}), 400

    plan = TreatmentPlan(
        patient_id=data['patient_id'],
        title=data.get('title', ''),
        description=data.get('description', ''),
        amount=data.get('amount', 0.0),
        amount_paid=data.get('amount_paid', 0.0),
        status=data.get('status', 'presentado'),
        notes=data.get('notes', ''),
    )
    db.session.add(plan)

    # Update patient status
    patient = db.session.get(Patient, data['patient_id'])
    if patient and patient.status == 'agendado':
        patient.status = 'diagnosticado'

    db.session.commit()
    return jsonify({'treatment': plan.to_dict(), 'success': True}), 201

@app.route('/api/treatments/<int:tid>', methods=['PUT'])
@login_required
def api_update_treatment(tid):
    plan = db.session.get(TreatmentPlan, tid)
    if not plan:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    for field in ['title', 'description', 'amount', 'amount_paid', 'status', 'notes']:
        if field in data:
            setattr(plan, field, data[field])

    if data.get('status') == 'aceptado':
        plan.patient.status = 'plan_aceptado'
    elif data.get('status') == 'completado':
        plan.completed_at = datetime.utcnow()
        plan.patient.status = 'completado'
        plan.patient.last_visit = datetime.utcnow()
        plan.patient.next_recall = datetime.utcnow() + timedelta(days=180)

    db.session.commit()
    return jsonify({'treatment': plan.to_dict(), 'success': True})

# ============================================================
# API — Interactions
# ============================================================
@app.route('/api/patients/<int:pid>/interactions', methods=['GET', 'POST'])
@login_required
def api_patient_interactions(pid):
    if request.method == 'POST':
        data = request.get_json()
        ix = PatientInteraction(
            patient_id=pid,
            direction=data.get('direction', 'in'),
            message=data.get('message', ''),
            channel=data.get('channel', 'whatsapp'),
        )
        db.session.add(ix)
        db.session.commit()
        return jsonify({'interaction': ix.to_dict(), 'success': True}), 201

    limit = request.args.get('limit', 50, type=int)
    interactions = PatientInteraction.query.filter_by(patient_id=pid)\
        .order_by(PatientInteraction.created_at.desc()).limit(limit).all()
    return jsonify({'interactions': [i.to_dict() for i in interactions]})


# ============================================================
# API — Services (admin CRUD)
# ============================================================
@app.route('/api/services', methods=['GET'])
@login_required
def api_get_services():
    services = Service.query.order_by(Service.sort_order).all()
    return jsonify({'services': [s.to_dict() for s in services]})

@app.route('/api/services', methods=['POST'])
@login_required
def api_create_service():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    service = Service(
        name=data['name'].strip(),
        description=(data.get('description') or '').strip(),
        duration_minutes=int(data.get('duration_minutes', 30)),
        price=float(data.get('price', 0.0)),
        active=data.get('active', True),
        sort_order=int(data.get('sort_order', 0)),
    )
    db.session.add(service)
    db.session.commit()
    return jsonify({'service': service.to_dict(), 'success': True}), 201

@app.route('/api/services/<int:sid>', methods=['PUT'])
@login_required
def api_update_service(sid):
    service = db.session.get(Service, sid)
    if not service:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    for field in ['name', 'description', 'duration_minutes', 'price', 'active', 'sort_order']:
        if field in data:
            setattr(service, field, data[field])
    db.session.commit()
    return jsonify({'service': service.to_dict(), 'success': True})

@app.route('/api/services/<int:sid>', methods=['DELETE'])
@login_required
def api_delete_service(sid):
    service = db.session.get(Service, sid)
    if not service:
        return jsonify({'error': 'not found'}), 404
    db.session.delete(service)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# API — Recall
# ============================================================
@app.route('/api/recall', methods=['GET'])
@login_required
def api_get_recall():
    """Patients due for recall (next_recall within 30 days or overdue)"""
    now = datetime.utcnow()
    cutoff = now + timedelta(days=30)
    
    patients = Patient.query.filter(
        Patient.next_recall <= cutoff,
        Patient.next_recall.isnot(None),
        Patient.status != 'perdido'
    ).order_by(Patient.next_recall).all()

    result = []
    for p in patients:
        days_overdue = 0
        if p.next_recall and p.next_recall < now:
            days_overdue = (now - p.next_recall).days
        result.append({
            **p.to_dict(),
            'days_overdue': days_overdue,
            'recall_date': p.next_recall.strftime('%d/%m/%Y') if p.next_recall else '',
        })
    return jsonify({'recalls': result, 'total': len(result)})

# ============================================================
# API — Reports
# ============================================================
@app.route('/api/report', methods=['GET'])
@login_required
def api_get_report():
    days = request.args.get('days', 30, type=int)
    now = datetime.utcnow()
    cutoff = now - timedelta(days=days) if days > 0 else datetime(2020, 1, 1)

    config = load_config()

    patients = Patient.query.filter(Patient.created_at >= cutoff).all()
    total = len(patients)
    
    by_status = {}
    for s in ['nuevo', 'agendado', 'diagnosticado', 'plan_aceptado',
              'en_tratamiento', 'completado', 'retorno', 'perdido']:
        by_status[s] = sum(1 for p in patients if p.status == s)

    appts = Appointment.query.filter(Appointment.appt_datetime >= cutoff).all()
    treatments = TreatmentPlan.query.filter(TreatmentPlan.created_at >= cutoff).all()

    # Daily new patients
    daily_counts = Counter()
    for p in patients:
        daily_counts[p.created_at.strftime('%Y-%m-%d')] += 1
    daily_sorted = sorted(daily_counts.items())
    
    revenue = sum(t.amount_paid for t in treatments if t.completed_at and t.completed_at >= cutoff)

    patient_rows = [{
        'nombre': p.name,
        'telefono': p.phone,
        'estado': p.status,
        'fuente': p.source,
        'ultima_visita': p.last_visit.strftime('%d/%m/%Y') if p.last_visit else '-',
        'creado': p.created_at.strftime('%d/%m/%Y'),
    } for p in patients]

    return jsonify({
        'config': config,
        'periodo': {'dias': days},
        'resumen': {
            'total': total,
            'por_estado': by_status,
            'citas': len(appts),
            'tratamientos': len(treatments),
            'ingresos': revenue,
        },
        'daily': {
            'labels': [d[0][5:] for d in daily_sorted],
            'values': [d[1] for d in daily_sorted],
        },
        'patients': patient_rows,
        'generated_at': now.isoformat(),
    })

# ============================================================
# API — Finance Dashboard
# ============================================================
@app.route('/api/finance/overview', methods=['GET'])
@login_required
def api_finance_overview():
    """Financial overview: total income, monthly breakdown, by service, pending."""
    now = datetime.utcnow()

    # Total income (all paid amounts)
    total_income = db.session.query(func.sum(TreatmentPlan.amount_paid)).scalar() or 0.0

    # Pending balance (treatment plans with balance > 0)
    pending_balance = db.session.query(func.sum(TreatmentPlan.amount - TreatmentPlan.amount_paid)).filter(
        TreatmentPlan.status.in_(['aceptado', 'en_progreso', 'presentado'])
    ).scalar() or 0.0

    # This month income
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_income = db.session.query(func.sum(TreatmentPlan.amount_paid)).filter(
        TreatmentPlan.completed_at >= month_start
    ).scalar() or 0.0

    # Monthly breakdown (last 12 months)
    months = []
    for i in range(11, -1, -1):
        m_start = (month_start - timedelta(days=30 * i)).replace(day=1)
        if i > 0:
            m_end = (month_start - timedelta(days=30 * (i - 1))).replace(day=1)
        else:
            m_end = now
        income = db.session.query(func.sum(TreatmentPlan.amount_paid)).filter(
            TreatmentPlan.completed_at >= m_start,
            TreatmentPlan.completed_at < m_end
        ).scalar() or 0.0
        months.append({
            'month': m_start.strftime('%Y-%m'),
            'income': float(income),
        })

    # Income by service (from completed treatment plans)
    services_income = db.session.query(
        TreatmentPlan.title,
        func.sum(TreatmentPlan.amount_paid)
    ).filter(
        TreatmentPlan.completed_at.isnot(None)
    ).group_by(TreatmentPlan.title).all()

    # Completed treatments count
    completed_treatments = TreatmentPlan.query.filter(
        TreatmentPlan.status == 'completado'
    ).count()

    # Active treatments count
    active_treatments = TreatmentPlan.query.filter(
        TreatmentPlan.status.in_(['aceptado', 'en_progreso'])
    ).count()

    return jsonify({
        'total_income': float(total_income),
        'pending_balance': float(pending_balance),
        'month_income': float(month_income),
        'monthly': months,
        'by_service': [{'service': s, 'income': float(v)} for s, v in services_income],
        'completed_treatments': completed_treatments,
        'active_treatments': active_treatments,
    })

@app.route('/api/finance/pending', methods=['GET'])
@login_required
def api_finance_pending():
    """List treatment plans with pending balance."""
    plans = TreatmentPlan.query.filter(
        TreatmentPlan.amount > TreatmentPlan.amount_paid,
        TreatmentPlan.status.in_(['presentado', 'aceptado', 'en_progreso'])
    ).order_by(TreatmentPlan.created_at.desc()).all()

    return jsonify({
        'pending': [{
            'id': p.id,
            'patient_name': p.patient.name,
            'patient_id': p.patient_id,
            'title': p.title,
            'amount': float(p.amount),
            'amount_paid': float(p.amount_paid),
            'balance': float(p.amount - p.amount_paid),
            'status': p.status,
            'created_at': p.created_at.isoformat() if p.created_at else None,
        } for p in plans],
        'total': len(plans)
    })

# ============================================================
# API — Doctors CRUD (admin)
# ============================================================
@app.route('/api/doctors', methods=['GET'])
@login_required
def api_get_doctors():
    doctors = Doctor.query.order_by(Doctor.sort_order).all()
    return jsonify({'doctors': [d.to_dict() for d in doctors]})

@app.route('/api/doctors', methods=['POST'])
@login_required
def api_create_doctor():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    doctor = Doctor(
        name=data['name'].strip(),
        specialty=data.get('specialty', '').strip(),
        bio=data.get('bio', '').strip(),
        photo_url=data.get('photo_url', '').strip(),
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(doctor)
    db.session.commit()
    return jsonify({'doctor': doctor.to_dict(), 'success': True}), 201

@app.route('/api/doctors/<int:did>', methods=['PUT'])
@login_required
def api_update_doctor(did):
    doctor = db.session.get(Doctor, did)
    if not doctor:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    for field in ['name', 'specialty', 'bio', 'photo_url', 'active', 'sort_order']:
        if field in data:
            setattr(doctor, field, data[field])
    db.session.commit()
    return jsonify({'doctor': doctor.to_dict(), 'success': True})

@app.route('/api/doctors/<int:did>', methods=['DELETE'])
@login_required
def api_delete_doctor(did):
    doctor = db.session.get(Doctor, did)
    if not doctor:
        return jsonify({'error': 'not found'}), 404
    db.session.delete(doctor)
    db.session.commit()
    return jsonify({'success': True})

# ============================================================
# API — Blocked Schedules (admin)
# ============================================================
@app.route('/api/blocked-schedules', methods=['GET'])
@login_required
def api_get_blocked():
    doctor_id = request.args.get('doctor_id', type=int)
    query = BlockedSchedule.query
    if doctor_id:
        query = query.filter_by(doctor_id=doctor_id)
    blocked = query.order_by(BlockedSchedule.block_date.desc()).all()
    return jsonify({'blocked': [b.to_dict() for b in blocked]})

@app.route('/api/blocked-schedules', methods=['POST'])
@login_required
def api_create_blocked():
    data = request.get_json()
    if not data or not data.get('block_date'):
        return jsonify({'error': 'block_date is required'}), 400
    try:
        block_date = datetime.strptime(data['block_date'], '%Y-%m-%d').date()
    except:
        return jsonify({'error': 'Invalid date format'}), 400
    blocked = BlockedSchedule(
        doctor_id=data.get('doctor_id'),
        block_date=block_date,
        start_time=data.get('start_time', ''),
        end_time=data.get('end_time', ''),
        reason=data.get('reason', ''),
    )
    db.session.add(blocked)
    db.session.commit()
    return jsonify({'blocked': blocked.to_dict(), 'success': True}), 201

@app.route('/api/blocked-schedules/<int:bid>', methods=['DELETE'])
@login_required
def api_delete_blocked(bid):
    blocked = db.session.get(BlockedSchedule, bid)
    if not blocked:
        return jsonify({'error': 'not found'}), 404
    db.session.delete(blocked)
    db.session.commit()
    return jsonify({'success': True})

# ============================================================
# API — Chat Web Widget (Valentina)
# ============================================================

@app.route('/api/chat', methods=['POST'])
def api_chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Mensaje requerido'}), 400
        reply = call_ai(data['message'].strip(), data.get('history', []))
        return jsonify({'response': reply, 'success': True})
    except Exception as e:
        print(f'[Chat API] Error: {e}')
        return jsonify({'error': 'Error interno'}), 500

# ============================================================
# Static files
# ============================================================
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND, filename)

# ============================================================
# Run
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8766))
    app.run(host='0.0.0.0', port=port)
