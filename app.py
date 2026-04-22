from flask import Flask, render_template, request
import csv
import os
import subprocess
from datetime import datetime
import random
import string

app = Flask(__name__)

consent_requests = {}
update_notifications = {}
current_doctor = {}

# ===================== PATHS =====================

DATA_DIR = "data"
DOCTOR_CSV = f"{DATA_DIR}/doctors.csv"
TEXT_CSV = f"{DATA_DIR}/patient_text_information.csv"
IMAGE_DIR = f"{DATA_DIR}/patient_image_information"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

# ===================== CSV SCHEMA =====================

PATIENT_FIELDS = [
    "did",
    "aadhar",
    "name",
    "age",
    "gender",
    "hospitalname",
    "description"
]

# ===================== HELPERS =====================

def generate_did():
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=8))
    return f"DID-{random_part}"


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    clean = [{k: r.get(k, "") for k in fields} for r in rows]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(clean)


def find_patient(did):
    for p in read_csv(TEXT_CSV):
        if p["did"] == did:
            return p
    return None


def save_patient(data):
    rows = read_csv(TEXT_CSV)
    rows.append(data)
    write_csv(TEXT_CSV, rows, PATIENT_FIELDS)


# ===================== ROUTES =====================

@app.route("/")
def index():
    return render_template("index.html")


# ===================== PATIENT LOGIN =====================

@app.route("/patient-login", methods=["GET", "POST"])
def patient_login():

    if request.method == "POST":

        did = request.form["did"]
        aadhar = request.form["aadhar"]

        patients = read_csv(TEXT_CSV)

        patient = next(
            (p for p in patients if p["did"] == did and p["aadhar"] == aadhar),
            None
        )
        print(f"patient information: ")

        if patient:
            return render_template(
                "patient_dashboard.html",
                patient=patient
            )

        return "<h3>Invalid DID or Aadhar</h3>"

    return render_template("register_login.html")


# ===================== PATIENT REGISTER =====================

@app.route("/patient-register", methods=["POST"])
def patient_register():

    aadhar = request.form["aadhar"]

    patients = read_csv(TEXT_CSV)

    # Check if Aadhar already exists
    existing_patient = next(
        (p for p in patients if p["aadhar"] == aadhar),
        None
    )

    # ================= UPDATE EXISTING =================
    if existing_patient:

        existing_patient["name"] = request.form["name"]
        existing_patient["age"] = request.form["age"]
        existing_patient["gender"] = request.form["gender"]
        existing_patient["hospitalname"] = request.form["hospitalname"]

        write_csv(TEXT_CSV, patients, PATIENT_FIELDS)

        return f"""
        <h2>Patient Updated Successfully</h2>
        <h3>Your DID : {existing_patient['did']}</h3>
        <a href="/patient-login">Login</a>
        """

    # ================= NEW PATIENT =================
    else:
        did = generate_did()

        patient = {
            "did": did,
            "aadhar": aadhar,
            "name": request.form["name"],
            "age": request.form["age"],
            "gender": request.form["gender"],
            "hospitalname": request.form["hospitalname"],
            "description": ""
        }

        save_patient(patient)

        return f"""
        <h2>Registration Successful</h2>
        <h3>Your DID : {did}</h3>
        <a href="/patient-login">Login</a>
        """

# ===================== PATIENT HISTORY =====================

@app.route("/patient-history/<did>")
def patient_history(did):

    ehr_path = f"{DATA_DIR}/ehr_records.csv"

    if not os.path.exists(ehr_path):
        return "<h3>No records found</h3>"

    history = []

    with open(ehr_path, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for r in reader:

            csv_did = r.get("did", "").strip()

            if csv_did == did.strip():
                history.append(r)

    print("Found records:", len(history))   # DEBUG

    return render_template(
        "patient_history.html",
        did=did,
        history=history
    )


# ===================== PATIENT NEW =====================

@app.route("/patient-new")
def patient_new():

    empty = dict.fromkeys(PATIENT_FIELDS, "")

    return render_template(
        "form.html",
        patient=empty,
        is_update=False
    )


# ===================== DOCTOR VIEW =====================

@app.route("/doctor-view/<did>")
def doctor_view(did):
    print(f"did doctor recied:  {did}")
    ehr_path = f"{DATA_DIR}/ehr_records.csv"

    with open(ehr_path, newline="", encoding="utf-8") as f:
        history = [
            r for r in csv.DictReader(f)
            if r["did"] == did
        ]

    return render_template(
        "doctor_patient_view.html",
        did=did,
        history=history,
        doctor=current_doctor
    )


@app.route("/doctor-ehr/<did>")
def doctor_ehr(did):

    ehr_path = f"{DATA_DIR}/ehr_records.csv"

    history = []

    if os.path.exists(ehr_path):

        with open(ehr_path, newline="", encoding="utf-8") as f:

            history = [
                r for r in csv.DictReader(f)
                if r.get("did") == did
            ]

    return render_template(
        "doctor_ehr_partial.html",
        did=did,
        history=history
    )

# ===================== DOCTOR UPDATE =====================

@app.route("/doctor-update/<did>")
def doctor_update(did):

    ehr_path = f"{DATA_DIR}/ehr_records.csv"

    with open(ehr_path, newline="", encoding="utf-8") as f:
        history = [
            r for r in csv.DictReader(f)
            if r["did"] == did
        ]

    return render_template(
        "doctor_update_view.html",
        did=did,
        history=history,
        doctor=current_doctor
    )


# ===================== UPDATE RECORD =====================

@app.route("/doctor-update-record", methods=["POST"])
def doctor_update_record():

    ehr_id = request.form["ehr_id"]
    disease = request.form["disease"]
    code = request.form["code"]
    final = request.form["final_assessment"]

    ehr_path = f"{DATA_DIR}/ehr_records.csv"

    with open(ehr_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    did = ""

    for r in rows:
        if r["ehr_id"] == ehr_id:
            r["disease"] = disease
            r["code"] = code
            r["final_assessment"] = final
            did = r["did"]

    with open(ehr_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    update_notifications[did] = "updated"

    return '''
    <script>
    alert("Updation done successfully");
    window.location="/ehr-login";
    </script>
    '''


# ===================== CONSENT =====================

@app.route("/request-consent", methods=["POST"])
def request_consent():

    data = request.json
    did = data["did"]
    print(f"patient did: {did}")
    action = data["action"]

    consent_requests[did] = {
        "action": action,
        "status": "pending"
    }

    return {"status":"sent"}

@app.route("/check-consent/<did>")
def check_consent(did):

    request_data = consent_requests.get(did)

    if request_data:

        if request_data["status"] == "pending":
            return {
                "status": "pending",
                "action": request_data["action"]
            }

        if request_data["status"] == "allowed":
            return {"status": "allowed"}

        if request_data["status"] == "denied":
            return {"status": "denied"}

    return {"status": "none"}

@app.route("/check-doctor-consent/<did>")
def check_doctor_consent(did):

    request_data = consent_requests.get(did)

    if request_data:

        if request_data["status"] == "allowed":
            return {
                "status":"allowed",
                "action":request_data["action"]
            }

        if request_data["status"] == "denied":
            return {"status":"denied"}

    return {"status":"waiting"}


@app.route("/allow-consent/<did>")
def allow_consent(did):

    if did in consent_requests:
        consent_requests[did]["status"] = "allowed"

    return {"status":"allowed"}


@app.route("/deny-consent/<did>")
def deny_consents(did):

    if did in consent_requests:
        consent_requests[did]["status"] = "denied"

    return {"status":"denied"}

@app.route("/check-update/<did>")
def check_update(did):

    if did in update_notifications:

        del update_notifications[did]

        return {"status":"updated"}

    return {"status":"none"}

# ===================== DOCTOR LOGIN =====================

@app.route("/ehr-login", methods=["GET", "POST"])
def ehr_login():

    if request.method == "POST":

        role = request.form["role"]
        print(f"role: {role}")
        if role == "patient":
            did = request.form["did"]
            aadhar = request.form["aadhar"]
            print(f"did: {did}   aadhar : {aadhar}")
            with open(TEXT_CSV, newline="", encoding="utf-8") as f:
                patients = list(csv.DictReader(f))


            patient = next(
                (p for p in patients
                if p["did"].strip() == did.strip()
                and p["aadhar"].strip() == aadhar.strip()),
                None
            )

            if not patient:
                return "<h3>Invalid DID or Aadhar</h3>"

            ehr_path = f"{DATA_DIR}/ehr_records.csv"

            history = []

            if os.path.exists(ehr_path):
                with open(ehr_path, newline="", encoding="utf-8") as f:
                    history = [
                        r for r in csv.DictReader(f)
                        if r.get("did") == did
                    ]

            return render_template(
                "ehr.html",
                patient_id=did,
                role="patient",
                history=history
            )
        elif role == "doctor":

            doctor_id = request.form["doctor_id"]

            with open(DOCTOR_CSV, newline="", encoding="utf-8") as f:
                doctors = list(csv.DictReader(f))

            doctor = next((d for d in doctors if d["doctor_id"] == doctor_id), None)

            if not doctor:
                return "<h3>Invalid Doctor ID</h3>"

            global current_doctor
            current_doctor = doctor

            patients = read_csv(TEXT_CSV)

            return render_template(
                "doctor_dashboard.html",
                doctor=doctor,
                patients=patients
            )
        else:
            print("im coming out")

    return render_template("ehr_login.html")



@app.route("/submit", methods=["POST"])
def submit():

    aadhar = request.form["aadhar"]

    patients = read_csv(TEXT_CSV)

    # ================= CHECK EXISTING PATIENT =================

    existing_patient = next(
        (p for p in patients if p["aadhar"] == aadhar),
        None
    )

    # ================= UPDATE EXISTING =================

    if existing_patient:

        did = existing_patient["did"]

        existing_patient["name"] = request.form["name"]
        existing_patient["age"] = request.form["age"]
        existing_patient["gender"] = request.form["gender"]
        existing_patient["hospitalname"] = request.form["hospitalname"]
        existing_patient["description"] = request.form.get("problem_text", "")

        write_csv(TEXT_CSV, patients, PATIENT_FIELDS)

    # ================= NEW PATIENT =================

    else:

        did = generate_did()

        patient = {
            "did": did,
            "aadhar": aadhar,
            "name": request.form["name"],
            "age": request.form["age"],
            "gender": request.form["gender"],
            "hospitalname": request.form["hospitalname"],
            "description": request.form.get("problem_text", "")
        }

        save_patient(patient)

    # -------- MODE --------
    mode = request.form["mode"]

    # -------- IMAGE --------
    image_path = ""
    image = request.files.get("problem_image")

    if image and image.filename:
        image_path = f"{IMAGE_DIR}/{did}_{image.filename}"
        image.save(image_path)

    # -------- CALL AGENTIC AI --------
    subprocess.run(
        ["python", "main.py", did, mode, image_path],
        check=True
    )

    return f"""
    <h2>Agentic AI Processing Completed</h2>
    <h3>Your DID : {did}</h3>
    <a href="/patient-login">Go to Login</a>
    """

# ===================== RUN =====================

if __name__ == "__main__":
    app.run(debug=True)