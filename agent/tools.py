from langchain.tools import Tool
from models.biobert import extract_entities_from_text
from models.multimodal_xray import generate_impression_from_xray

biobert_tool = Tool(
    name="BioBERT_Text_Analyzer",
    func=extract_entities_from_text,
    description="Extract medical entities from clinical text"
)

xray_tool = Tool(
    name="XRay_Impression_Generator",
    func=generate_impression_from_xray,
    description="Generate radiology impression text from X-ray image"
)
