# main.py

import sys
import csv
import uuid
import os
from datetime import datetime
from agent.agent_controller import ClinicalAgent

DATA_DIR = "data"
TEXT_CSV = f"{DATA_DIR}/patient_text_information.csv"
EHR_CSV = f"{DATA_DIR}/ehr_records.csv"

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------- ARGUMENTS ----------------
did = sys.argv[1]
mode = sys.argv[2]          # text | image | both
image_path = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None

# ---------------- LOAD PATIENT ----------------
with open(TEXT_CSV, newline="", encoding="utf-8") as f:
    patients = list(csv.DictReader(f))
    patient = next(p for p in patients if p["did"] == did)

# ---------------- RUN AGENTIC AI ----------------
agent = ClinicalAgent()

result = agent.process(
    mode=mode,
    patient_id=did,
    text=patient["description"],
    image_path=image_path,
    hospital_id=patient["hospitalname"]
)

# ---------------- EXTRACT RESULTS ----------------
final_assessment = result.get("final_assessment", "No AI conclusion generated")

# get disease and encoding from agent
disease = result.get("disease", "Unknown")
code = result.get("code", "")

# ensure disease is string
if isinstance(disease, list):
    disease = disease[0]

# ---------------- PREPARE EHR RECORD ----------------
ehr_record = {
    "ehr_id": f"EHR-{uuid.uuid4()}",
    "did": did,
    "hospitalname": patient["hospitalname"],
    "description": patient["description"],
    "disease": disease,
    "code": code,
    "final_assessment": final_assessment,
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# ---------------- WRITE EHR CSV ----------------
file_exists = os.path.exists(EHR_CSV)

with open(EHR_CSV, "a", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "ehr_id",
            "did",
            "hospitalname",
            "description",
            "disease",
            "code",
            "final_assessment",
            "timestamp"
        ]
    )

    if not file_exists:
        writer.writeheader()

    writer.writerow(ehr_record)

print("✅ EHR record stored successfully")