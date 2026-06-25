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
VALENTINA_SYSTEM_PROMPT = """Eres Valentina, ejecutiva de atención al paciente. Tu objetivo es CAPTURAR DATOS y AGENDAR CITAS en el CRM.

DOCTORES DISPONIBLES (sugiere según el motivo):
- Dra. Reyna Pimentel: Diseño de sonrisa, limpieza general, blanqueamiento, endodoncia, revisión general
- Dr. Carlos Méndez (Ortodoncista): Brackets, alineadores, ortodoncia correctiva
- Dra. María Fernández (Periodoncista): Encías, limpieza profunda, periodoncia, implantes
- Si el paciente NO SABE qué necesita: sugiere consulta general con Dra. Reyna

FLUJO OBLIGATORIO (completa los 4 pasos siempre):
PASO 1 - Identificar: ¿Es paciente NUEVO o ya ha venido antes? ¿Qué servicio/motivo de consulta necesita?
PASO 2 - Sugerir doctor: Según el motivo, recomienda UNO de los doctores arriba
PASO 3 - Recolectar datos: PREGUNTA UNO POR UNO: nombre completo, teléfono, correo (OPCIONAL), y qué día/hora prefiere
PASO 4 - Confirmar: Una vez tengas nombre+teléfono+día+hora+doctor → CONFIRMA la cita con el paciente
PASO 5 - Agendar: Cuando el paciente CONFIRME, USA LA FUNCIÓN create_appointment con los datos recolectados (nombre, teléfono, doctor_id, fecha, hora, motivo). LUEGO dile al paciente que la cita quedó registrada.

REGLAS:
- Hablas español dominicano profesional y cálido
- NUNCA digas que eres una IA
- Máximo 3 párrafos por respuesta
- Ve paso a paso, no preguntes todo de una vez
- Si no tiene correo, CONTINÚA sin problema

CLÍNICA: C/ Amalio Alonzo #24, Nagua. Tel: (809) 584-7033. Horario: Lun-Vie 8AM-5PM, Sáb 8AM-1PM"""

def call_ai(user_msg, history=None):
    from models import Doctor, Appointment, BlockedSchedule
    from datetime import datetime, date, timedelta
    
    doctors = Doctor.query.filter_by(is_active=True).order_by(Doctor.sort_order).all()
    extra = ""
    if doctors:
        extra += "\nDOCTORES:\n"
        for d in doctors:
            extra += f"- ID {d.id}: {d.name} ({d.specialty or 'General'})\n"
    
    today = date.today()
    extra += "\nDISPONIBILIDAD (PROXIMOS 3 DIAS):\n"
    days_n = ['lun','mar','mie','jue','vie','sab','dom']
    for i in range(3):
        day = today + timedelta(days=i)
        if day.weekday() == 6: continue
        extra += f"\n{days_n[day.weekday()]} {day.strftime('%d/%m')}:\n"
        for doc in doctors:
            slots = [f'{h:02d}:{m:02d}' for h in range(8,17) for m in [0,30]]
            if day.weekday() == 5: slots = [s for s in slots if int(s.split(':')[0]) < 13]
            for b in BlockedSchedule.query.filter(BlockedSchedule.block_date == day, db.or_(BlockedSchedule.doctor_id == doc.id, BlockedSchedule.doctor_id.is_(None))).all():
                if b.start_time:
                    bs = int(b.start_time.split(':')[0])*60+int(b.start_time.split(':')[1])
                    be = int(b.end_time.split(':')[0])*60+int(b.end_time.split(':')[1]) if b.end_time else bs+30
                    slots = [s for s in slots if not (bs <= int(s.split(':')[0])*60+int(s.split(':')[1]) < be)]
            for a in Appointment.query.filter(Appointment.doctor_id == doc.id, db.func.date(Appointment.appt_datetime) == day, Appointment.status.in_(['pendiente','confirmada'])).all():
                ast = a.appt_datetime.hour*60+a.appt_datetime.minute
                aen = ast+(a.duration_minutes or 30)
                slots = [s for s in slots if not (ast <= int(s.split(':')[0])*60+int(s.split(':')[1]) < aen)]
            extra += f"  {doc.name}: {', '.join(slots[:5]) if slots else 'Lleno'}\n"
    
    prompt = VALENTINA_SYSTEM_PROMPT + extra
    
    messages = [{'role': 'system', 'content': prompt}]
    if history:
        for h in history[-8:]:
            messages.append({'role': 'user', 'content': h.get('user','')})
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
            'max_tokens': 800,
            'temperature': 0.7,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise Exception(f'AI error: {resp.status_code}')
    return resp.json()['choices'][0]['message']['content']


def api_chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Mensaje requerido'}), 400
        reply = call_ai(data['message'].strip(), data.get('history', []))
        
        # Auto-log interaction
        try:
            from models import PatientInteraction
            log = PatientInteraction(
                patient_id=0,
                direction='in',
                message=data['message'].strip(),
                ai_response=reply,
                channel='web',
                channel_id=data.get('channel_id', ''),
                source_phone=data.get('phone', ''),
            )
            db.session.add(log)
            db.session.commit()
        except:
            db.session.rollback()
        
        # Detectar si el paciente confirmo la cita
        try:
            from models import Patient, Appointment, Doctor, BlockedSchedule
            from datetime import datetime, date, timedelta
            import re
            
            full_text = reply.lower() + ' ' + ' '.join([h.get('user','') + ' ' + h.get('bot','') for h in (data.get('history') or [])]).lower()
            
            # Buscar confirmacion: si el paciente dijo si/ok/vale Y Valentina dice "cita creada" o "agendada"
            confirm = any(w in data['message'].lower() for w in ['si','ok','vale','confirmo','dale','de acuerdo','adelante','perfecto'])
            registered = any(w in reply.lower() for w in ['cita creada','agendada','registrada','confirmada','te esperamos','quedo registrada'])
            
            if confirm and registered:
                # Extraer datos
                nm = re.search(r'(?:soy|me llamo|mi nombre es|nombre[\s:]*)\s*(?:el |la )?([A-Za-z\s]{3,40}?)(?:,|\.|$)', full_text, re.I)
                pm = re.search(r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', full_text)
                dm = re.search(r'(\d{1,2})[\/](\d{1,2})', full_text)
                tm = re.search(r'(\d{1,2}):(\d{2})', full_text)
                
                if nm and pm:
                    name_val = nm.group(1).strip()
                    phone_val = pm.group(1).strip()
                    target_date = date.today() + timedelta(days=1)
                    target_time = '09:00'
                    
                    if dm:
                        try: target_date = date(date.today().year, int(dm.group(2)), int(dm.group(1)))
                        except: pass
                    if tm:
                        target_time = f'{int(tm.group(1)):02d}:{tm.group(2)}'
                    
                    # Buscar paciente
                    patient = Patient.query.filter_by(phone=phone_val).first()
                    if not patient:
                        patient = Patient(name=name_val, phone=phone_val, source='web_chat', status='nuevo')
                        db.session.add(patient)
                        db.session.flush()
                    
                    appt_dt = datetime.strptime(f'{target_date.isoformat()} {target_time}', '%Y-%m-%d %H:%M')
                    appt = Appointment(patient_id=patient.id, doctor_id=1, appt_datetime=appt_dt, status='pendiente')
                    db.session.add(appt)
                    if patient.status == 'nuevo':
                        patient.status = 'agendado'
                    db.session.commit()
                    print(f'[Booking] CREADA: {name_val} - {phone_val} - {target_date} {target_time}')
        except Exception as e:
            db.session.rollback()
            print(f'[Booking] Error: {e}')
        
        return jsonify({'response': reply, 'success': True})
    except Exception as e:
        print(f'[Chat API] Error: {e}')
        return jsonify({'error': 'Error interno'}), 500

# ============================================================

@app.route('/chat-widget.js')
def chat_widget_js():
    from flask import make_response
    js = """
(function(){
var cid=localStorage.getItem('chat_uid')||(Date.now().toString(36)+Math.random().toString(36).slice(2,8));
localStorage.setItem('chat_uid',cid);
var d=document.createElement('div');
d.innerHTML='<button id="vbtn" style="position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:#1a4b8c;color:white;border:none;cursor:pointer;z-index:9999;box-shadow:0 4px 15px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg></button>';
document.body.appendChild(d);
var b=document.getElementById('vbtn');
b.onclick=function(){
var p=document.createElement('div');p.id='vpanel';
p.innerHTML='<div style="position:fixed;bottom:96px;right:24px;width:340px;height:520px;background:white;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.2);z-index:9999;overflow:hidden;display:flex;flex-direction:column"><div style="background:#1a4b8c;color:white;padding:16px 20px;display:flex;align-items:center;gap:12px"><div style="width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,0.2);display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:16px">V</div><div><p style="margin:0;font-weight:600;font-size:14px">Valentina</p><p style="margin:0;font-size:12px;opacity:0.7">Online</p></div><span onclick="document.getElementById('vpanel').remove();" style="margin-left:auto;cursor:pointer;font-size:18px;opacity:0.7">&#10005;</span></div><div id="vmsgs" style="flex:1;overflow-y:auto;padding:16px;background:#f0f4f8"><div style="background:white;border-radius:12px 12px 12px 4px;padding:10px 14px;max-width:85%;font-size:14px;color:#374151;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:8px">&#161;Hola! &#128075; Soy Valentina, asistente de la Dra. Reyna. &#191;En qu&#233; puedo ayudarte?</div></div><div style="border-top:1px solid #e5e7eb;padding:12px;display:flex;gap:8px;background:white"><input id="vinp" placeholder="Escribe tu mensaje..." style="flex:1;padding:10px 16px;border:1px solid #d1d5db;border-radius:24px;font-size:14px;outline:none"/><button id="vsend" style="width:40px;height:40px;border-radius:50%;background:#1a4b8c;color:white;border:none;cursor:pointer;font-size:18px">&#8594;</button></div></div>';
document.body.appendChild(p);
b.style.display='none';
var inp=document.getElementById('vinp'),msgs=document.getElementById('vmsgs'),send=document.getElementById('vsend');
send.onclick=async function(){var m=inp.value.trim();if(!m)return;inp.value='';
msgs.innerHTML+='<div style="display:flex;justify-content:flex-end;margin-bottom:8px"><div style="background:#1a4b8c;color:white;border-radius:12px 12px 4px 12px;padding:10px 14px;max-width:85%;font-size:14px">'+m.replace(/</g,'&lt;')+'</div></div>';
try{var r=await(await fetch("https://clinicadrareyna-crm-api.onrender.com/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,history:[],channel_id:cid,phone:""})})).json();var reply=r.response||"Disculpa, no pude procesar tu mensaje.";}
catch(e){var reply="Error de conexi&#243;n. Intenta de nuevo.";}
msgs.innerHTML+='<div style="display:flex;justify-content:flex-start;margin-bottom:8px"><div style="background:white;border-radius:12px 12px 12px 4px;padding:10px 14px;max-width:85%;font-size:14px;color:#374151;box-shadow:0 1px 3px rgba(0,0,0,0.08)">'+reply+'</div></div>';
msgs.scrollTop=msgs.scrollHeight;};
inp.onkeydown=function(e){if(e.key==='Enter')send.click();};};
})();

"""
    resp = make_response(js)
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

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
