import json
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
meds_col = db.medicamentos

with open("seed_medications.json", "r", encoding="utf-8") as f:
    meds = json.load(f)

insertados = 0
for m in meds:
    if meds_col.count_documents({"nombre": m["nombre"]}) == 0:
        meds_col.insert_one(m)
        insertados += 1

print(f"Medicamentos insertados: {insertados}")
