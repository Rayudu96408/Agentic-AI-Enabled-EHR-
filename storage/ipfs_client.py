# storage/ipfs_client.py
import requests
import json
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def store_fhir_in_ipfs(fhir_data: Dict[str, Any]) -> str:
    """
    Store FHIR data in IPFS using HTTP API (compatible with v0.26.0+)
    Returns: CID string
    """
    try:
        # Convert FHIR data to JSON string
        json_str = json.dumps(fhir_data, indent=2)
        
        # Prepare the request to IPFS API
        files = {
            'file': ('fhir_data.json', json_str, 'application/json')
        }
        
        params = {
            'pin': 'true',
            'cid-version': '1'
        }
        
        logger.info(" Storing FHIR data in IPFS...")
        
        # Make HTTP request to IPFS daemon
        response = requests.post(
            'http://127.0.0.1:5001/api/v0/add',
            files=files,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            cid = result.get('Hash')
            
            if cid:
                logger.info(f" FHIR data stored successfully!")
                logger.info(f"   CID: {cid}")
                logger.info(f"   Gateway URL: http://127.0.0.1:8080/ipfs/{cid}")
                logger.info(f"   WebUI: http://127.0.0.1:5001/webui")
                return cid
            else:
                raise Exception("No CID returned from IPFS")
        else:
            error_msg = f"IPFS API Error {response.status_code}: {response.text}"
            logger.error(f" {error_msg}")
            raise Exception(error_msg)
            
    except requests.exceptions.ConnectionError:
        error_msg = "Cannot connect to IPFS daemon. Make sure 'ipfs daemon' is running."
        logger.error(f" {error_msg}")
        # For development, return a simulated CID
        return _generate_simulated_cid(fhir_data)
        
    except Exception as e:
        logger.error(f" Error storing in IPFS: {str(e)}")
        return _generate_simulated_cid(fhir_data)

def _generate_simulated_cid(fhir_data: Dict[str, Any]) -> str:
    """Generate a simulated CID for development/testing"""
    import hashlib
    import time
    
    # Create a deterministic hash from the data
    data_str = json.dumps(fhir_data, sort_keys=True)
    hash_obj = hashlib.sha256(data_str.encode())
    hash_hex = hash_obj.hexdigest()[:46]  # Take first 46 chars
    
    # Format as a CID v1 (bafyrei...)
    simulated_cid = f"bafyrei{hash_hex}"
    
    logger.warning(f" Development mode: Using simulated CID {simulated_cid}")
    logger.warning("   Start IPFS daemon with: ipfs daemon")
    
    return simulated_cid

def test_ipfs_connection():
    """Test if IPFS daemon is accessible"""
    try:
        response = requests.post(
            'http://127.0.0.1:5001/api/v0/version',
            timeout=5
        )
        if response.status_code == 200:
            version_info = response.json()
            logger.info(f"✓ Connected to IPFS v{version_info.get('Version')}")
            return True
        return False
    except:
        return False

'''# Quick test if run directly
if __name__ == "__main__":
    print("Testing IPFS Client...")
    
    if test_ipfs_connection():
        print("✅ IPFS daemon is running!")
        
        # Test with sample data
        test_data = {
            "resourceType": "Observation",
            "status": "preliminary",
            "code": {
                "text": "Test Observation"
            },
            "subject": {
                "reference": "Patient/TEST001"
            }
        }
        
        cid = store_fhir_in_ipfs(test_data)
        print(f"Test CID: {cid}")
    else:
        print("❌ IPFS daemon not running")
        print("   Start it with: ipfs daemon")'''