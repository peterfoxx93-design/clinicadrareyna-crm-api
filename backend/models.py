"""Modelos para CRM de Clínica Dental"""
import os
from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Doctor(db.Model):
    """Doctores de la clínica"""
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    specialty = db.Column(db.String(200), default='')  # Odontóloga, Ortodoncista, etc.
    bio = db.Column(db.Text, default='')  # Breve descripción
    photo_url = db.Column(db.String(500), default='')
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='doctor', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'specialty': self.specialty,
            'bio': self.bio,
            'photo_url': self.photo_url,
            'active': self.active,
            'sort_order': self.sort_order,
        }


class Patient(db.Model):
    """Paciente de la clínica dental"""
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), default='')
    email = db.Column(db.String(200), default='')
    birthdate = db.Column(db.String(20), default='')
    source = db.Column(db.String(50), default='whatsapp')
    status = db.Column(db.String(20), default='nuevo')
    notes = db.Column(db.Text, default='')
    referral_source = db.Column(db.String(100), default='')
    total_spent = db.Column(db.Float, default=0.0)
    last_visit = db.Column(db.DateTime, nullable=True)
    next_recall = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='patient', lazy='dynamic',
                                   cascade='all, delete-orphan',
                                   order_by='Appointment.appt_datetime.desc()')
    treatments = db.relationship('TreatmentPlan', backref='patient', lazy='dynamic',
                                 cascade='all, delete-orphan')
    interactions = db.relationship('PatientInteraction', backref='patient', lazy='dynamic',
                                   cascade='all, delete-orphan',
                                   order_by='PatientInteraction.created_at.desc()')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'birthdate': self.birthdate,
            'source': self.source,
            'status': self.status,
            'notes': self.notes,
            'referral_source': self.referral_source,
            'total_spent': self.total_spent,
            'last_visit': self.last_visit.isoformat() if self.last_visit else None,
            'next_recall': self.next_recall.isoformat() if self.next_recall else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Appointment(db.Model):
    """Citas agendadas"""
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    appt_datetime = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    appt_type = db.Column(db.String(50), default='consulta')
    notes = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='pendiente')
    reminder_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.name if self.patient else '',
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.name if self.doctor else '',
            'appt_datetime': self.appt_datetime.isoformat() if self.appt_datetime else None,
            'duration_minutes': self.duration_minutes,
            'appt_type': self.appt_type,
            'notes': self.notes,
            'status': self.status,
            'reminder_sent': self.reminder_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class BlockedSchedule(db.Model):
    """Bloqueo de horarios (días que el doctor no atiende)"""
    __tablename__ = 'blocked_schedules'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)  # null = toda la clínica
    block_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5), default='')  # HH:MM, vacío = todo el día
    end_time = db.Column(db.String(5), default='')
    reason = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'block_date': self.block_date.isoformat() if self.block_date else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'reason': self.reason,
        }


class TreatmentPlan(db.Model):
    """Planes de tratamiento"""
    __tablename__ = 'treatment_plans'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    title = db.Column(db.String(200), default='')
    description = db.Column(db.Text, default='')
    amount = db.Column(db.Float, default=0.0)
    amount_paid = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='presentado')
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.name if self.patient else '',
            'title': self.title,
            'description': self.description,
            'amount': self.amount,
            'amount_paid': self.amount_paid,
            'balance': self.amount - self.amount_paid,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class Service(db.Model):
    """Servicios de la clínica (se reflejan en el widget de reserva)"""
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    duration_minutes = db.Column(db.Integer, default=30)
    price = db.Column(db.Float, default=0.0)
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'duration_minutes': self.duration_minutes,
            'price': self.price,
            'active': self.active,
            'sort_order': self.sort_order,
        }


class PatientInteraction(db.Model):
    """Historial de interacciones con el paciente"""
    __tablename__ = 'patient_interactions'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    direction = db.Column(db.String(10), default='in')
    message = db.Column(db.Text, default='')
    ai_response = db.Column(db.Text, default='')
    channel = db.Column(db.String(50), default='whatsapp')
    channel_id = db.Column(db.String(100), default='')
    source_phone = db.Column(db.String(50), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'direction': self.direction,
            'message': self.message,
            'ai_response': self.ai_response[:300] if self.ai_response else '',
            'channel': self.channel,
            'channel_id': self.channel_id or '',
            'source_phone': self.source_phone or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def init_db(app):
    db.init_app(app)
    with app.app_context():
        # Create all tables (including new ones)
        db.create_all()
        # Create default admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', is_admin=True)
            admin.set_password('reyna2026')
            db.session.add(admin)
            db.session.commit()
        # Seed default doctors if none exist
        if Doctor.query.count() == 0:
            defaults = [
                ('Dra. Reyna Pimentel', 'Odontóloga General', 'Especialista en diseño de sonrisa y rehabilitación estética con más de 12 años de experiencia.', 0),
                ('Dr. Carlos Méndez', 'Ortodoncista', 'Especialista en ortodoncia y alineadores invisibles. Tratamiento de maloclusiones.', 1),
                ('Dra. María Fernández', 'Periodoncista', 'Especialista en encías e implantes dentales. Cirugía periodontal y regeneración ósea.', 2),
            ]
            for name, specialty, bio, order in defaults:
                db.session.add(Doctor(name=name, specialty=specialty, bio=bio, sort_order=order))
            db.session.commit()
