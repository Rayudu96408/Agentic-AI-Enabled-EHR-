# fhir/fhir_converter.py
import uuid
from datetime import datetime
import json
from typing import Dict, Any, List, Union

def build_fhir_observation(patient_id: str, assessment: Union[Dict, str], 
                          normalized_entities: Union[Dict, List, str]) -> Dict[str, Any]:
    """
    Build FHIR Observation resource from clinical data.
    
    Args:
        patient_id: Patient identifier
        assessment: Clinical assessment (dict or string)
        normalized_entities: Normalized medical entities (dict, list, or string)
    
    Returns:
        FHIR Observation resource as dictionary
    """
    
    # Generate unique ID
    observation_id = str(uuid.uuid4())[:8]
    
    # Handle assessment parameter (could be string or dict)
    if isinstance(assessment, str):
        assessment_text = assessment
        severity = "unknown"
        recommendations = []
    elif isinstance(assessment, dict):
        assessment_text = assessment.get("assessment", "Clinical assessment")
        severity = assessment.get("severity", "unknown")
        recommendations = assessment.get("recommendations", [])
    else:
        assessment_text = str(assessment)
        severity = "unknown"
        recommendations = []
    
    # Handle normalized_entities parameter
    snomed_codes = []
    icd10_codes = []
    loinc_codes = []
    
    print(f"DEBUG FHIR: normalized_entities type: {type(normalized_entities)}")
    
    if isinstance(normalized_entities, dict):
        # Extract codes from dictionary
        if "snomed_codes" in normalized_entities:
            snomed_codes = normalized_entities["snomed_codes"]
        if "icd10_codes" in normalized_entities:
            icd10_codes = normalized_entities["icd10_codes"]
        if "loinc_codes" in normalized_entities:
            loinc_codes = normalized_entities["loinc_codes"]
        
        # Handle different formats within snomed_codes
        processed_snomed = []
        for item in snomed_codes:
            if isinstance(item, dict):
                # Extract code from dict
                code = item.get("code") or item.get("snomed_ct") or str(item)
                display = item.get("display") or item.get("text", "SNOMED CT Code")
                processed_snomed.append({"code": code, "display": display})
            elif isinstance(item, str):
                processed_snomed.append({"code": item, "display": "SNOMED CT Code"})
        
        snomed_codes = processed_snomed
    
    elif isinstance(normalized_entities, list):
        # Assume list of codes or entities
        for item in normalized_entities:
            if isinstance(item, dict):
                if "snomed_ct" in item:
                    snomed_codes.append({
                        "code": item["snomed_ct"],
                        "display": item.get("display", "SNOMED CT Code")
                    })
                elif "icd10" in item:
                    icd10_codes.append(item["icd10"])
                elif "loinc" in item:
                    loinc_codes.append(item["loinc"])
    
    elif isinstance(normalized_entities, str):
        # Try to parse as JSON
        try:
            parsed = json.loads(normalized_entities)
            return build_fhir_observation(patient_id, assessment, parsed)
        except:
            # If not JSON, use as text note
            pass
    
    # Build FHIR Observation resource
    fhir_obs = {
        "resourceType": "Observation",
        "id": f"obs-{observation_id}",
        "status": "preliminary",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "exam",
                        "display": "Exam"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "75325-1",
                    "display": "Clinical impression"
                }
            ],
            "text": assessment_text
        },
        "subject": {
            "reference": f"Patient/{patient_id}",
            "display": f"Patient {patient_id}"
        },
        "effectiveDateTime": datetime.now().isoformat(),
        "issued": datetime.now().isoformat(),
        "performer": [
            {
                "reference": "Practitioner/AI-Agent-001",
                "display": "Clinical AI Agent"
            }
        ],
        "valueString": assessment_text,
        "interpretation": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                        "code": "N" if severity == "mild" else "A",
                        "display": "Normal" if severity == "mild" else "Abnormal"
                    }
                ]
            }
        ],
        "note": [
            {
                "text": f"Generated by AI Clinical Agent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        ]
    }
    
    # Add severity if available
    if severity and severity != "unknown":
        fhir_obs["extension"] = [{
            "url": "http://hl7.org/fhir/StructureDefinition/observation-severity",
            "valueString": severity
        }]
    
    # Add SNOMED CT codes if available
    if snomed_codes:
        coding_list = []
        for code_item in snomed_codes:
            if isinstance(code_item, dict):
                code = code_item.get("code", "")
                display = code_item.get("display", "")
            else:
                code = str(code_item)
                display = "SNOMED CT Code"
            
            if code:
                coding_list.append({
                    "system": "http://snomed.info/sct",
                    "code": code,
                    "display": display
                })
        
        if coding_list:
            fhir_obs.setdefault("extension", []).append({
                "url": "http://example.org/fhir/StructureDefinition/snomed-codes",
                "valueCodeableConcept": {
                    "coding": coding_list
                }
            })
    
    # Add recommendations if available
    if recommendations:
        rec_text = "; ".join(recommendations) if isinstance(recommendations, list) else str(recommendations)
        fhir_obs["note"].append({
            "text": f"Recommendations: {rec_text}"
        })
    
    print(f" FHIR Observation created: Observation/{fhir_obs['id']}")
    print(f"   Status: {fhir_obs['status']}")
    print(f"   Assessment: {assessment_text[:50]}...")
    
    return fhir_obs

'''
# Test function
if __name__ == "__main__":
    # Test with your data format
    test_patient_id = "PAT001"
    
    test_assessment = {
        "assessment": "Upper respiratory tract infection likely",
        "severity": "mild",
        "recommendations": ["Rest", "Hydration", "Follow-up if worsens"]
    }
    
    test_normalized = {
        "snomed_codes": [
            {"code": "386661006", "display": "Fever"},
            {"code": "49727002", "display": "Cough"}
        ],
        "icd10_codes": ["R50.9", "R05"],
        "loinc_codes": []
    }
    
    print("Testing FHIR Converter...")
    fhir_result = build_fhir_observation(test_patient_id, test_assessment, test_normalized)
    
    print("\nGenerated FHIR Observation:")
    print(json.dumps(fhir_result, indent=2, default=str))'''