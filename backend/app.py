"""Clínica Dental CRM — Backend Flask"""
import os, sys, json, csv, io
from datetime import datetime, date, timedelta
from functools import wraps
from collections import Counter

from flask import (Flask, render_template, request, redirect, url_for,
                   jsonify, session, send_from_directory)
from flask_login import (LoginManager, login_user, logout_user,
                          login_required, current_user)
from sqlalchemy import func

sys.path.insert(0, os.path.dirname(__file__))
from models import db, User, Patient, Appointment, TreatmentPlan, PatientInteraction, init_db

# Config
BASE = os.path.dirname(os.path.dirname(__file__))
FRONTEND = os.path.join(BASE, 'frontend')

app = Flask(__name__,
            static_folder=FRONTEND,
            template_folder=FRONTEND)
app.debug = False
app.secret_key = os.environ.get('CLINICA_SECRET', 'reyna-pimentel-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE, 'data', 'clinica.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

init_db(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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

@app.route('/reportes')
@login_required
def reportes():
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
    return jsonify({'appointment': appt.to_dict(), 'success': True}), 201

@app.route('/api/appointments/<int:aid>', methods=['PUT'])
@login_required
def api_update_appointment(aid):
    appt = db.session.get(Appointment, aid)
    if not appt:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
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
