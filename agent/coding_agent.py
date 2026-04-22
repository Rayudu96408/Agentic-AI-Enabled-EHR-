# agent/coding_agent.py

import json
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate


class MedicalCodingAgent:
    """
    Converts clinical assessment into standardized medical codes
    (ICD-10, SNOMED, LOINC if possible)
    """

    def __init__(self):
        self.llm = Ollama(
            model="mistral",
            base_url="http://localhost:11434",
            temperature=0
        )

        self.prompt = PromptTemplate(
            input_variables=["text"],
            template="""
You are a certified medical coding specialist.

From the following clinical conclusion, extract and assign:

1. ICD-10 diagnosis codes
2. SNOMED CT codes (if possible)
3. Short standardized diagnosis names

Return STRICT JSON only in this format:

{{
  "diagnosis": [
    {{
      "name": "...",
      "icd10": "...",
      "snomed": "..."
    }}
  ]
}}

Clinical Conclusion:
{text}
"""
        )

    def normalize(self, clinical_text: str) -> dict:
        try:
            prompt = self.prompt.format(text=clinical_text)
            response = self.llm.invoke(prompt)

            # Sometimes LLM returns text before JSON
            json_start = response.find("{")
            json_text = response[json_start:]

            return json.loads(json_text)

        except Exception as e:
            print(" Coding Agent Error:", e)
            return {
                "diagnosis": [],
                "error": str(e),
                "raw_text": clinical_text
            }
