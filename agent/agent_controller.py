import os
import sys
import json
import csv
import uuid
from datetime import datetime

from langchain.agents import initialize_agent, AgentType
from langchain_community.llms import Ollama
from langchain.tools import Tool

# project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# ===== MODELS =====
from models.biobert_ner import extract_medical_entities
from models.r2gen_model import load_r2gen_model

# ===== AGENTS =====
from agent.coding_agent import MedicalCodingAgent

# ===== PIPELINE =====
from agent.assessment import generate_clinical_assessment
from fhir.fhir_converter import build_fhir_observation
from storage.ipfs_client import store_fhir_in_ipfs
from storage.fabric_client import write_to_ledger


class ClinicalAgent:

    def __init__(self):

        print("\n========== Initializing Multi-Agent System ==========")

        self.r2gen_model = load_r2gen_model()

        self.llm = Ollama(
            model="mistral",
            base_url="http://localhost:11434"
        )

        self.coding_agent = MedicalCodingAgent()

        # -------- TOOLS --------
        self.text_tool = Tool(
            name="TextMedicalNER",
            func=self.text_agent_tool,
            description="Extract medical entities from clinical text"
        )

        self.image_tool = Tool(
            name="XrayAnalyzer",
            func=self.image_agent_tool,
            description="Analyze chest X-ray image"
        )

        self.fusion_tool = Tool(
            name="ClinicalFusion",
            func=self.fusion_agent_tool,
            description="Fuse medical opinions into final diagnosis"
        )

        # -------- AGENTS --------
        self.text_agent = initialize_agent(
            [self.text_tool],
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )

        self.image_agent = initialize_agent(
            [self.image_tool],
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )

        self.fusion_agent = initialize_agent(
            [self.fusion_tool],
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )

        print(" Multi-Agent System Ready")
        print("====================================================\n")

    # ==================================================
    # TOOLS
    # ==================================================

    def text_agent_tool(self, text: str):

        entities = extract_medical_entities(text)

        return json.dumps(entities)

    def image_agent_tool(self, image_path: str):

        if not os.path.exists(image_path):
            return "Image not found. No radiology findings."

        result = self.r2gen_model.analyze(image_path)

        return result["report"]["full_report"]

    def fusion_agent_tool(self, opinions: str):

        prompt = f"""
You are a senior doctor.

Combine the following medical opinions and provide:

1. Final diagnosis
2. Severity
3. Treatment advice

Medical Opinions:
{opinions}
"""

        return self.llm.invoke(prompt)

    # ==================================================
    # DISEASE EXTRACTION
    # ==================================================

    def extract_diseases(self, conclusion: str):

        entities = extract_medical_entities(conclusion)

        diseases = []

        for e in entities:

            if isinstance(e, dict):

                label = str(e.get("label", "")).lower()
                text = str(e.get("text", "")).lower()

                if any(x in label for x in ["disease", "diagnosis", "problem"]):

                    if text not in ["confidence", "entities", "symptoms", "duration"]:
                        diseases.append(text)

            elif isinstance(e, str):

                if e.lower() not in ["confidence", "entities", "symptoms", "duration"]:
                    diseases.append(e.lower())

        diseases = list(set(diseases))

        if len(diseases) == 0:

            print("Using LLM extracting Disease from clinical text...")

            prompt = f"""
From the following clinical text identify the most likely disease or condition.

Clinical Text:
{conclusion}

Return only disease names as JSON list.

Example:
["pneumonia"]
"""

            llm_result = self.llm.invoke(prompt)

            try:
                diseases = json.loads(str(llm_result))
            except:
                diseases = [str(llm_result)]

        if len(diseases) == 1:
            return diseases[0]

        elif len(diseases) > 1:
            return diseases

        else:
            return "Unknown condition"

    # ==================================================
    # SAVE TO EHR CSV
    # ==================================================

    def save_to_ehr_csv(self, patient_id, hospitalname, description, disease, code, final_assessment):

        file_path = "ehr_records.csv"

        file_exists = os.path.exists(file_path)

        ehr_id = str(uuid.uuid4())

        timestamp = datetime.now().isoformat()

        row = [
            ehr_id,
            patient_id,
            hospitalname,
            description,
            disease,
            code,
            final_assessment,
            timestamp
        ]

        with open(file_path, "a", newline="") as file:

            writer = csv.writer(file)

            if not file_exists:

                writer.writerow([
                    "ehr_id",
                    "patient_id",
                    "hospitalname",
                    "description",
                    "disease",
                    "code",
                    "final_assessment",
                    "timestamp"
                ])

            writer.writerow(row)

        print("\n--- EHR RECORD SAVED ---")

    # ==================================================
    # MAIN PIPELINE
    # ==================================================

    def process(self, mode, patient_id, text, image_path=None, hospital_id="HospitalA"):

        print("\n========== MULTI-AGENT PROCESS START ==========")

        # ---------- TEXT AGENT ----------
        print("\n--- TEXT AGENT OUTPUT (BioBERT) ---")

        text_entities = extract_medical_entities(text)

        print(json.dumps(text_entities, indent=2))

        text_assessment = generate_clinical_assessment(text_entities)

        print("\nText Assessment:")
        print(json.dumps(text_assessment, indent=2))

        # ---------- IMAGE AGENT ----------
        image_assessment = None

        if mode == "2":

            print("\n--- IMAGE AGENT OUTPUT (R2Gen) ---")

            if image_path and os.path.exists(image_path):

                img_result = self.r2gen_model.analyze(image_path)
                image_report = img_result["report"]

            else:

                image_report = {
                    "findings": "No image available",
                    "impression": "No radiology conclusion"
                }

            print(json.dumps(image_report, indent=2))

            image_entities = extract_medical_entities(
                image_report["findings"] + " " + image_report["impression"]
            )

            image_assessment = generate_clinical_assessment(image_entities)

            print("\nImage Assessment:")
            print(json.dumps(image_assessment, indent=2))

        # ---------- FUSION AGENT ----------
        print("\n--- FUSION AGENT FINAL CONCLUSION ---")

        fusion_prompt = f"""
TEXT ASSESSMENT:
{text_assessment}

IMAGE ASSESSMENT:
{image_assessment if image_assessment else "Not available"}

Provide final medical conclusion.
"""

        final_assessment = self.llm.invoke(fusion_prompt)

        print(final_assessment)

        # ---------- DISEASE EXTRACTION ----------
        print("\n--- DISEASE EXTRACTION FROM CONCLUSION ---")

        diseases = self.extract_diseases(str(final_assessment))

        print("Detected Disease(s):", diseases)

        if isinstance(diseases, list):
            diseases = diseases[0]

        # ---------- MEDICAL CODING ----------
        print("\n--- MEDICAL CODING AGENT OUTPUT ---")

        coded = self.coding_agent.normalize(diseases)

        print(json.dumps(coded, indent=2))

        code = ""

        if isinstance(coded, dict):

            diagnosis_list = coded.get("diagnosis", [])

            if isinstance(diagnosis_list, list) and len(diagnosis_list) > 0:

                first_diag = diagnosis_list[0]

                code = first_diag.get("icd10", "")

        # ---------- FHIR ----------
        print("\n--- FHIR RESOURCE ---")

        fhir = build_fhir_observation(patient_id, final_assessment, coded)

        print(json.dumps(fhir, indent=2))

        # ---------- IPFS ----------
        print("\n--- IPFS STORAGE ---")

        cid = store_fhir_in_ipfs(fhir)

        print("CID:", cid)

        # ---------- BLOCKCHAIN ----------
        print("\n--- BLOCKCHAIN LEDGER ---")

        ledger = write_to_ledger(patient_id, cid, hospital_id)

        print(json.dumps(ledger, indent=2))

        # ---------- SAVE CSV ----------
        print("\n--- SAVING TO EHR CSV ---")

        self.save_to_ehr_csv(
            patient_id,
            hospital_id,
            text,
            diseases,
            code,
            final_assessment
        )

        print("\n========== PROCESS COMPLETE ==========")

        return {
            "patient_id": patient_id,
            "text_assessment": text_assessment,
            "image_assessment": image_assessment,
            "final_assessment": final_assessment,
            "disease": diseases,
            "code": code,
            "medical_codes": coded,
            "fhir": fhir,
            "ipfs_cid": cid,
            "ledger": ledger,
            "timestamp": datetime.now().isoformat()
        }