from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from config import MONGO_URI, DB_NAME, HOST, PORT, DEBUG

app = Flask(__name__)
app.secret_key = "cambia-esta-clave"

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
    telefono = request.form.get("telefono", "").strip()
    if not nombre:
        flash("El nombre es obligatorio", "danger")
        return redirect(url_for("pacientes"))
    pacientes_collection.insert_one({"nombre": nombre, "edad": edad, "telefono": telefono, "historial": []})
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
@app.route("/receta/<paciente_id>", methods=["GET", "POST"])
def nueva_receta(paciente_id):
    oid = to_objectid(paciente_id)
    paciente = pacientes_collection.find_one({"_id": oid})
    if not paciente:
        flash("Paciente no encontrado", "danger")
        return redirect(url_for("pacientes"))

    medicamentos = list(medicamentos_collection.find({"es_pediatrico": True}).sort("nombre", 1))

    if request.method == "POST":
        sintomas = request.form.get("sintomas", "").strip()
        diagnostico = request.form.get("diagnostico", "").strip()
        indicaciones = request.form.get("indicaciones", "").strip()
        receta = request.form.getlist("medicamentos")
        nuevo_historial = {
            "sintomas": sintomas, 
            "diagnostico": diagnostico, 
            "indicaciones": indicaciones,
            "receta": receta,
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        pacientes_collection.update_one({"_id": oid}, {"$push": {"historial": nuevo_historial}})
        flash("Receta guardada en el historial", "success")
        return redirect(url_for("historial", paciente_id=paciente_id))

    return render_template("nueva_receta.html", paciente=paciente, medicamentos=medicamentos)

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
    return render_template("receta_print.html", paciente=paciente, receta=receta, indice=indice)

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
