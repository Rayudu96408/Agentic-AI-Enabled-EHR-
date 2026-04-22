# agent/assessment.py
import json

def generate_clinical_assessment(entities):
    """
    Generate clinical assessment from extracted entities.
    entities can be either:
    1. Dictionary with 'entities' key
    2. List of entity dictionaries
    3. String (convert to list)
    """
    
    # Handle different input formats
    if isinstance(entities, str):
        try:
            # Try to parse as JSON string
            entities = json.loads(entities)
        except:
            # If not JSON, create simple structure
            entities = {"text": entities, "entities": [{"text": entities, "type": "SYMPTOM"}]}
    
    # Extract entity texts
    if isinstance(entities, dict):
        # Check if entities is in the expected format from BioBERT
        if "entities" in entities:
            entity_list = entities["entities"]
        elif "symptoms" in entities:
            # Handle your current mock format
            symptoms = entities.get("symptoms", [])
            entity_list = [{"text": s, "type": "SYMPTOM"} for s in symptoms]
        else:
            # Default: use the dict itself
            entity_list = [{"text": str(entities), "type": "UNKNOWN"}]
    elif isinstance(entities, list):
        entity_list = entities
    else:
        entity_list = [{"text": str(entities), "type": "UNKNOWN"}]
    
    # Extract terms from entities
    terms = []
    for entity in entity_list:
        if isinstance(entity, dict):
            # Try different possible keys
            text = entity.get("text") or entity.get("word") or entity.get("entity") or str(entity)
            terms.append(text)
        else:
            terms.append(str(entity))
    
    # Clean terms
    terms = [t for t in terms if t and t.strip()]
    
    # Generate assessment based on terms
    if not terms:
        return {
            "assessment": "Insufficient information for clinical assessment",
            "severity": "unknown",
            "recommendations": ["Obtain more clinical information"]
        }
    
    # Simple rule-based assessment (you can make this more sophisticated)
    terms_lower = [t.lower() for t in terms]
    
    assessment = ""
    severity = "mild"
    recommendations = []
    
    # Check for specific conditions
    if any(symptom in terms_lower for symptom in ["fever", "cough", "cold"]):
        assessment = "Upper respiratory tract infection likely"
        if "fever" in terms_lower and "cough" in terms_lower:
            assessment = "Possible influenza or viral respiratory infection"
        recommendations.extend(["Rest", "Hydration", "Symptomatic treatment"])
    
    if any(symptom in terms_lower for symptom in ["chest pain", "shortness of breath", "dyspnea"]):
        assessment = "Respiratory distress noted"
        severity = "moderate"
        recommendations.append("Chest X-ray recommended")
    
    if any(symptom in terms_lower for symptom in ["severe", "high fever", "difficulty breathing"]):
        severity = "severe"
        recommendations.append("Urgent medical evaluation needed")
    
    # Duration analysis
    for term in terms:
        if any(time_word in term.lower() for time_word in ["day", "week", "month", "year"]):
            if "3" in term or "three" in term.lower():
                if severity == "mild":
                    severity = "moderate"
                recommendations.append("Consider follow-up if symptoms persist beyond 5 days")
    
    # If no specific assessment generated
    if not assessment:
        assessment = f"Clinical findings: {', '.join(terms[:3])}"
    
    return {
        "assessment": assessment,
        "severity": severity,
        "recommendations": recommendations,
        "identified_terms": terms,
        "entity_count": len(terms)
    }

'''
# Test function
if __name__ == "__main__":
    # Test with different input formats
    test_cases = [
        # Your current format
        {
            "symptoms": ["fever", "cough"],
            "duration": "3 days",
            "entities": [
                {"text": "fever", "type": "SYMPTOM", "code": "386661006"},
                {"text": "cough", "type": "SYMPTOM", "code": "49727002"}
            ]
        },
        # List format
        [
            {"text": "headache", "type": "SYMPTOM"},
            {"text": "nausea", "type": "SYMPTOM"}
        ],
        # Simple string
        "Patient with fever and headache",
        # JSON string
        '{"entities": [{"text": "cough", "type": "SYMPTOM"}]}'
    ]
    
    for i, test_input in enumerate(test_cases):
        print(f"\nTest Case {i+1}:")
        print(f"Input: {test_input}")
        result = generate_clinical_assessment(test_input)
        print(f"Output: {json.dumps(result, indent=2)}")  '''