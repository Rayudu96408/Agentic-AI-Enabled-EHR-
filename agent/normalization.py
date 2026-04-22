# agent/normalization.py
import json
from typing import Dict, Any, List, Union

def normalize_entities(entities: Union[Dict, List, str]) -> Dict[str, Any]:
    """
    Normalize medical entities to standard codes.
    Handles multiple input formats.
    """
    
    print(f"DEBUG normalize_entities: Received type: {type(entities)}")
    if isinstance(entities, str):
        print(f"DEBUG: String content: {entities[:100]}...")
    
    # Handle different input formats
    if isinstance(entities, str):
        try:
            # Try to parse as JSON
            entities = json.loads(entities)
        except json.JSONDecodeError:
            # If not JSON, create a simple structure
            return {
                "original_text": entities,
                "snomed_codes": [],
                "icd10_codes": [],
                "loinc_codes": [],
                "rxnorm_codes": [],
                "normalized_terms": [entities],
                "note": "Could not parse as structured entities"
            }
    
    # Initialize result
    result = {
        "snomed_codes": [],
        "icd10_codes": [],
        "loinc_codes": [],
        "rxnorm_codes": [],
        "normalized_terms": [],
        "original_entities": entities if isinstance(entities, (dict, list)) else str(entities)
    }
    
    # Extract entities based on format
    entity_list = []
    
    if isinstance(entities, dict):
        # Handle dictionary format
        if "entities" in entities:
            entity_list = entities["entities"]
        elif "symptoms" in entities:
            # Convert symptoms list to entity format
            symptoms = entities.get("symptoms", [])
            entity_list = [{"text": s, "type": "SYMPTOM"} for s in symptoms]
        elif "text" in entities:
            entity_list = [entities]
        else:
            # Try to extract any list-like values
            for key, value in entities.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            entity_list.append(item)
                        else:
                            entity_list.append({"text": str(item), "type": key.upper()})
    
    elif isinstance(entities, list):
        entity_list = entities
    
    else:
        # Unknown format
        return {
            "snomed_codes": [],
            "icd10_codes": [],
            "loinc_codes": [],
            "rxnorm_codes": [],
            "normalized_terms": [str(entities)],
            "note": "Unknown entity format"
        }
    
    # Process each entity
    for entity in entity_list:
        if not isinstance(entity, dict):
            # Convert non-dict to dict
            entity = {"text": str(entity), "type": "UNKNOWN"}
        
        # Extract text from various possible keys
        text = entity.get("text") or entity.get("word") or entity.get("entity") or str(entity)
        entity_type = entity.get("type", "UNKNOWN")
        code = entity.get("code") or entity.get("cui") or entity.get("id", "")
        
        if not text or text == "{}":
            continue
        
        # Add to normalized terms
        result["normalized_terms"].append({
            "original": text,
            "type": entity_type,
            "standardized": text.lower(),
            "code": code
        })
        
        # Map to standard codes based on entity type and text
        # This is a simplified mapping - in reality, you'd use a medical ontology API
        
        text_lower = text.lower()
        
        # SNOMED CT mappings (simplified)
        snomed_map = {
            "fever": "386661006",
            "cough": "49727002",
            "headache": "25064002",
            "nausea": "422587007",
            "fatigue": "84229001",
            "pain": "22253000",
            "infection": "40733004",
            "inflammation": "23583003"
        }
        
        # ICD-10 mappings
        icd10_map = {
            "fever": "R50.9",
            "cough": "R05",
            "headache": "R51",
            "nausea": "R11.0",
            "fatigue": "R53.83",
            "pain": "R52",
            "infection": "B99.9",
            "inflammation": "R69"
        }
        
        # Check mappings
        for keyword, snomed_code in snomed_map.items():
            if keyword in text_lower:
                result["snomed_codes"].append({
                    "code": snomed_code,
                    "display": keyword.capitalize(),
                    "source_text": text
                })
                break
        
        for keyword, icd10_code in icd10_map.items():
            if keyword in text_lower:
                result["icd10_codes"].append({
                    "code": icd10_code,
                    "display": keyword.capitalize(),
                    "source_text": text
                })
                break
        
        # If entity already has a code, use it
        if code:
            if code.startswith("SNOMED") or len(code) == 9:  # SNOMED CT codes are typically 9 digits
                result["snomed_codes"].append({
                    "code": code.replace("SNOMED:", "").strip(),
                    "display": text,
                    "source_text": text
                })
            elif code.startswith("ICD10") or "-" in code:
                result["icd10_codes"].append({
                    "code": code.replace("ICD10:", "").strip(),
                    "display": text,
                    "source_text": text
                })
            elif code.startswith("LOINC"):
                result["loinc_codes"].append({
                    "code": code.replace("LOINC:", "").strip(),
                    "display": text,
                    "source_text": text
                })
    
    # Remove duplicates
    for key in ["snomed_codes", "icd10_codes", "loinc_codes", "rxnorm_codes"]:
        # Convert list of dicts to tuple set for deduplication
        seen = set()
        unique_list = []
        for item in result[key]:
            if isinstance(item, dict):
                item_tuple = tuple(sorted(item.items()))
                if item_tuple not in seen:
                    seen.add(item_tuple)
                    unique_list.append(item)
        result[key] = unique_list
    
    return result

'''
# Test function
if __name__ == "__main__":
    # Test with your current format
    test_input = {
        "symptoms": ["fever", "cough"],
        "duration": "3 days",
        "entities": [
            {"text": "fever", "type": "SYMPTOM", "code": "386661006"},
            {"text": "cough", "type": "SYMPTOM", "code": "49727002"}
        ]
    }
    
    print("Test 1: Dictionary with entities")
    result1 = normalize_entities(test_input)
    print(json.dumps(result1, indent=2))
    
    print("\nTest 2: List of entities")
    test_input2 = [
        {"text": "headache", "type": "SYMPTOM"},
        {"text": "nausea", "type": "SYMPTOM"}
    ]
    result2 = normalize_entities(test_input2)
    print(json.dumps(result2, indent=2))
    
    print("\nTest 3: String input")
    test_input3 = "Patient with fever and cough"
    result3 = normalize_entities(test_input3)
    print(json.dumps(result3, indent=2))'''