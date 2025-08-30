from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from config import MONGO_URI, DB_NAME, HOST, PORT, DEBUG

app = Flask(__name__)
app.secret_key = "cambia-esta-clave"

# Filtro personalizado para formatear fechas
@app.template_filter('strftime')
def strftime_filter(date, format='%d/%m/%Y'):
    if isinstance(date, str) and date == 'now':
        return datetime.now().strftime(format)
    return date.strftime(format) if date else ''

# Conexión a MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
pacientes_collection = db.pacientes
medicamentos_collection = db.medicamentos

def to_objectid(id_str):
    try:
        return ObjectId(id_str)
    except Exception:
        return None

@app.route("/")
def index():
    total_pacientes = pacientes_collection.count_documents({})
    total_medicamentos = medicamentos_collection.count_documents({})
    return render_template("index.html", total_pacientes=total_pacientes, total_medicamentos=total_medicamentos)

# ---------- PACIENTES ----------
@app.route("/pacientes")
def pacientes():
    pacientes = list(pacientes_collection.find().sort("nombre", 1))
    return render_template("pacientes.html", pacientes=pacientes)

@app.route("/pacientes/nuevo", methods=["POST"])
def nuevo_paciente():
    nombre = request.form.get("nombre", "").strip()
    edad = request.form.get("edad", "").strip()
    peso = request.form.get("peso", "").strip()
    talla = request.form.get("talla", "").strip()
    pc = request.form.get("pc", "").strip()
    fecha_consulta = request.form.get("fecha_consulta", "").strip()
    nombre_familiar = request.form.get("nombre_familiar", "").strip()
    edad_familiar = request.form.get("edad_familiar", "").strip()
    telefono = request.form.get("telefono", "").strip()
    if not nombre:
        flash("El nombre es obligatorio", "danger")
        return redirect(url_for("pacientes"))
    paciente_data = {
        "nombre": nombre, 
        "edad": edad, 
        "peso": peso,
        "talla": talla,
        "pc": pc,
        "fecha_consulta": fecha_consulta,
        "nombre_familiar": nombre_familiar,
        "edad_familiar": edad_familiar,
        "telefono": telefono, 
        "historial": []
    }
    pacientes_collection.insert_one(paciente_data)
    flash("Paciente agregado", "success")
    return redirect(url_for("pacientes"))

# ---------- MEDICAMENTOS ----------
@app.route("/medicamentos")
def medicamentos():
    meds = list(medicamentos_collection.find().sort("nombre", 1))
    return render_template("medicamentos.html", medicamentos=meds)

@app.route("/medicamentos/nuevo", methods=["POST"])
def nuevo_medicamento():
    nombre = request.form.get("nombre", "").strip()
    es_pediatrico = request.form.get("es_pediatrico") == "on"
    if not nombre:
        flash("El nombre del medicamento es obligatorio", "danger")
        return redirect(url_for("medicamentos"))
    if medicamentos_collection.count_documents({"nombre": {"$regex": f"^{nombre}$", "$options": "i"}}) == 0:
        medicamentos_collection.insert_one({"nombre": nombre, "es_pediatrico": es_pediatrico})
        flash("Medicamento agregado", "success")
    else:
        flash("El medicamento ya existe", "warning")
    return redirect(url_for("medicamentos"))

@app.route("/medicamentos/eliminar/<id>")
def eliminar_medicamento(id):
    oid = to_objectid(id)
    if oid:
        medicamentos_collection.delete_one({"_id": oid})
        flash("Medicamento eliminado", "info")
    return redirect(url_for("medicamentos"))

# ---------- RECETA & HISTORIAL ----------
@app.route("/receta/<paciente_id>/<tipo>", methods=["GET", "POST"])
def nueva_receta(paciente_id, tipo):
    oid = to_objectid(paciente_id)
    paciente = pacientes_collection.find_one({"_id": oid})
    if not paciente:
        flash("Paciente no encontrado", "danger")
        return redirect(url_for("pacientes"))

    if tipo not in ['dieta', 'diagnostico']:
        flash("Tipo de receta no válido", "danger")
        return redirect(url_for("pacientes"))

    medicamentos = list(medicamentos_collection.find({"es_pediatrico": True}).sort("nombre", 1))

    if request.method == "POST":
        sintomas = request.form.get("sintomas", "").strip()
        diagnostico = request.form.get("diagnostico", "").strip()
        indicaciones = request.form.get("indicaciones", "").strip()
        
        if tipo == 'dieta':
            dieta_contenido = request.form.get("dieta_contenido", "").strip()
            nuevo_historial = {
                "tipo": "dieta",
                "sintomas": sintomas, 
                "diagnostico": diagnostico, 
                "indicaciones": indicaciones,
                "dieta_contenido": dieta_contenido,
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
        else:
            receta = request.form.getlist("medicamentos")
            nuevo_historial = {
                "tipo": "diagnostico",
                "sintomas": sintomas, 
                "diagnostico": diagnostico, 
                "indicaciones": indicaciones,
                "receta": receta,
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
        
        pacientes_collection.update_one({"_id": oid}, {"$push": {"historial": nuevo_historial}})
        flash(f"Receta de {tipo} guardada en el historial", "success")
        return redirect(url_for("historial", paciente_id=paciente_id))

    return render_template("nueva_receta.html", paciente=paciente, medicamentos=medicamentos, tipo=tipo)

@app.route("/historial/<paciente_id>")
def historial(paciente_id):
    oid = to_objectid(paciente_id)
    paciente = pacientes_collection.find_one({"_id": oid})
    if not paciente:
        flash("Paciente no encontrado", "danger")
        return redirect(url_for("pacientes"))
    return render_template("historial.html", paciente=paciente)

@app.route("/receta/print/<paciente_id>/<int:indice>")
def receta_print(paciente_id, indice):
    oid = to_objectid(paciente_id)
    paciente = pacientes_collection.find_one({"_id": oid})
    if not paciente or indice < 0 or indice >= len(paciente.get("historial", [])):
        flash("Receta no encontrada", "danger")
        return redirect(url_for("historial", paciente_id=paciente_id))
    receta = paciente["historial"][indice]
    fecha_actual = datetime.now()
    return render_template("receta_print.html", 
                         paciente=paciente, 
                         receta=receta, 
                         indice=indice,
                         fecha_actual=fecha_actual)

# ---------- CHATBOT Y RESERVAS ----------
@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@app.route("/enviar-preconsulta", methods=["POST"])
def enviar_preconsulta():
    try:
        # Recopilar datos del formulario
        datos = {
            'motivo_consulta': request.form.get('motivo_consulta'),
            'fiebre_actual': request.form.get('fiebre_actual'),
            'duracion_sintomas': request.form.get('duracion_sintomas'),
            'evolucion_sintomas': request.form.get('evolucion_sintomas'),
            'edad_nino': request.form.get('edad_nino'),
            'alimentacion': request.form.get('alimentacion'),
            'llamada_urgente': request.form.get('llamada_urgente'),
            'telefono_contacto': request.form.get('telefono_contacto'),
            'informacion_adicional': request.form.get('informacion_adicional')
        }
        
        # Crear el mensaje de correo
        asunto = f"📋 Nueva Pre-Consulta Pediátrica - {datos['edad_nino']}"
        
        cuerpo_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; padding: 20px;">
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <div style="text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #4c63d2;">
                    <h2 style="color: #4c63d2; margin: 0;">🩺 Nueva Pre-Consulta Pediátrica</h2>
                    <p style="color: #666; margin: 5px 0;">Información recopilada del asistente virtual</p>
                    <small style="color: #999;">Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #4c63d2; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        👶 Información del Paciente
                    </h3>
                    <p><strong>Edad:</strong> {datos['edad_nino']}</p>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #4c63d2; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        🏥 Motivo de Consulta
                    </h3>
                    <p><strong>Motivo principal:</strong> {datos['motivo_consulta']}</p>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #4c63d2; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        🌡️ Estado Actual
                    </h3>
                    <p><strong>Fiebre:</strong> {datos['fiebre_actual']}</p>
                    <p><strong>Duración de síntomas:</strong> {datos['duracion_sintomas']}</p>
                    <p><strong>Evolución:</strong> {datos['evolucion_sintomas']}</p>
                    <p><strong>Alimentación:</strong> {datos['alimentacion']}</p>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #4c63d2; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        📞 Contacto
                    </h3>
                    <p><strong>Llamada urgente:</strong> {datos['llamada_urgente']}</p>
                    {f"<p><strong>Teléfono:</strong> {datos['telefono_contacto']}</p>" if datos['telefono_contacto'] else ""}
                </div>
                
                {f'''<div style="margin-bottom: 25px;">
                    <h3 style="color: #4c63d2; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        📝 Información Adicional
                    </h3>
                    <p>{datos['informacion_adicional']}</p>
                </div>''' if datos['informacion_adicional'] else ''}
                
                <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin-top: 20px;">
                    <p style="margin: 0; color: #856404;">
                        <strong>⚠️ Recordatorio:</strong> Esta información fue recopilada mediante el asistente virtual. 
                        Se recomienda confirmar los datos durante la consulta presencial.
                    </p>
                </div>
            </div>
        </div>
        """
        
        # Enviar correo
        msg = Message(
            subject=asunto,
            sender=app.config['MAIL_USERNAME'],
            recipients=[DOCTOR_EMAIL],
            html=cuerpo_html
        )
        
        mail.send(msg)
        
        return {"success": True, "message": "Información enviada correctamente"}
        
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        return {"success": False, "error": str(e)}, 500

@app.route("/reservar-cita")
def reservar_cita():
    return render_template("reservar_cita.html")

@app.route("/procesar-reserva", methods=["POST"])
def procesar_reserva():
    try:
        # Recopilar datos del formulario
        datos_reserva = {
            'nombre_paciente': request.form.get('nombre_paciente'),
            'edad': request.form.get('edad'),
            'sexo': request.form.get('sexo'),
            'nombre_responsable': request.form.get('nombre_responsable'),
            'telefono': request.form.get('telefono'),
            'email': request.form.get('email'),
            'fecha_preferida': request.form.get('fecha_preferida'),
            'hora_preferida': request.form.get('hora_preferida'),
            'motivo_consulta': request.form.get('motivo_consulta')
        }
        
        # Crear el mensaje de correo para el doctor
        asunto = f"📅 Nueva Solicitud de Cita - {datos_reserva['nombre_paciente']}"
        
        cuerpo_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; padding: 20px;">
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <div style="text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #28a745;">
                    <h2 style="color: #28a745; margin: 0;">📅 Nueva Solicitud de Cita</h2>
                    <p style="color: #666; margin: 5px 0;">Reserva de consulta pediátrica</p>
                    <small style="color: #999;">Fecha de solicitud: {datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #28a745; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        👶 Datos del Paciente
                    </h3>
                    <p><strong>Nombre:</strong> {datos_reserva['nombre_paciente']}</p>
                    <p><strong>Edad:</strong> {datos_reserva['edad'] or 'No especificada'}</p>
                    <p><strong>Sexo:</strong> {datos_reserva['sexo'] or 'No especificado'}</p>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #28a745; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        👨‍👩‍👧‍👦 Datos del Responsable
                    </h3>
                    <p><strong>Nombre:</strong> {datos_reserva['nombre_responsable']}</p>
                    <p><strong>Teléfono:</strong> {datos_reserva['telefono']}</p>
                    {f"<p><strong>Email:</strong> {datos_reserva['email']}</p>" if datos_reserva['email'] else ""}
                </div>
                
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #28a745; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        📅 Cita Solicitada
                    </h3>
                    <p><strong>Fecha preferida:</strong> {datos_reserva['fecha_preferida']}</p>
                    <p><strong>Hora preferida:</strong> {datos_reserva['hora_preferida']}</p>
                </div>
                
                {f'''<div style="margin-bottom: 25px;">
                    <h3 style="color: #28a745; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                        🏥 Motivo de Consulta
                    </h3>
                    <p>{datos_reserva['motivo_consulta']}</p>
                </div>''' if datos_reserva['motivo_consulta'] else ''}
                
                <div style="background: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; padding: 15px; margin-top: 20px;">
                    <p style="margin: 0; color: #155724;">
                        <strong>📞 Acción requerida:</strong> Contactar al responsable para confirmar la disponibilidad 
                        y agendar la cita en el horario solicitado.
                    </p>
                </div>
            </div>
        </div>
        """
        
        # Enviar correo al doctor
        msg = Message(
            subject=asunto,
            sender=app.config['MAIL_USERNAME'],
            recipients=[DOCTOR_EMAIL],
            html=cuerpo_html
        )
        
        mail.send(msg)
        
        # Enviar correo de confirmación al paciente (si proporcionó email)
        if datos_reserva['email']:
            msg_paciente = Message(
                subject="✅ Solicitud de Cita Recibida - Consultorio Pediátrico",
                sender=app.config['MAIL_USERNAME'],
                recipients=[datos_reserva['email']],
                html=f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; padding: 20px;">
                    <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <div style="text-align: center; margin-bottom: 30px;">
                            <h2 style="color: #4c63d2; margin: 0;">✅ Solicitud Recibida</h2>
                            <p style="color: #666;">Consultorio Pediátrico</p>
                        </div>
                        
                        <p>Estimado/a <strong>{datos_reserva['nombre_responsable']}</strong>,</p>
                        
                        <p>Hemos recibido su solicitud de cita para <strong>{datos_reserva['nombre_paciente']}</strong>.</p>
                        
                        <div style="background: #f8f9ff; border-left: 4px solid #4c63d2; padding: 15px; margin: 20px 0;">
                            <p><strong>Fecha solicitada:</strong> {datos_reserva['fecha_preferida']}</p>
                            <p><strong>Hora solicitada:</strong> {datos_reserva['hora_preferida']}</p>
                        </div>
                        
                        <p>Nos pondremos en contacto con usted en las próximas horas para confirmar la disponibilidad y agendar su cita.</p>
                        
                        <p>Si tiene alguna urgencia, no dude en contactarnos directamente.</p>
                        
                        <p>Saludos cordiales,<br>
                        <strong>Consultorio Pediátrico</strong></p>
                    </div>
                </div>
                """
            )
            mail.send(msg_paciente)
        
        flash("¡Solicitud de cita enviada correctamente! Nos pondremos en contacto contigo pronto.", "success")
        return redirect(url_for("index"))
        
    except Exception as e:
        print(f"Error al procesar reserva: {e}")
        flash("Error al enviar la solicitud. Por favor intenta nuevamente.", "danger")
        return redirect(url_for("reservar_cita"))

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)