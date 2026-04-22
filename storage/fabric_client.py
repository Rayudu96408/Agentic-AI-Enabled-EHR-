#!/usr/bin/env python3
"""
Hyperledger Fabric Client for EHR System
Connects to Fabric network and manages ledger transactions
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import grpc
from google.protobuf import timestamp_pb2

# Add Fabric SDK path
fabric_path = os.path.join(os.path.dirname(__file__), '..', 'fabric-samples')
if os.path.exists(fabric_path):
    sys.path.append(fabric_path)

try:
    from hfc.fabric import Client
    from hfc.fabric.user import User
    from hfc.fabric.peer import Peer
    from hfc.fabric.orderer import Orderer
    from hfc.util import utils
    from hfc.fabric.transaction import Transaction
    FABRIC_AVAILABLE = True
except ImportError:
    FABRIC_AVAILABLE = False
    print("  Hyperledger Fabric SDK not available. Using mock ledger.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FabricLedgerClient:
    """
    Client for interacting with Hyperledger Fabric ledger
    """
    
    def __init__(self, network_config: str = None):
        """
        Initialize Fabric client
        
        Args:
            network_config: Path to network configuration file
        """
        self.client = None
        self.network = None
        self.channel = None
        self.user_context = None
        
        if FABRIC_AVAILABLE:
            self._initialize_fabric_client(network_config)
        else:
            logger.warning("Fabric SDK not available. Using mock ledger mode.")
    
    def _initialize_fabric_client(self, network_config: str = None):
        """Initialize Hyperledger Fabric client"""
        try:
            logger.info("Initializing Hyperledger Fabric client...")
            
            # Create client instance
            self.client = Client()
            
            # Load network configuration
            if network_config and os.path.exists(network_config):
                self.client.init_with_net_profile(network_config)
                logger.info(f"Loaded network config from: {network_config}")
            else:
                # Default test-network configuration
                self._load_default_config()
                logger.info("Using default test-network configuration")
            
            # Set user context (Admin from Org1)
            self.user_context = self.client.get_user('org1.example.com', 'Admin')
            
            # Initialize channel
            self.channel = self.client.new_channel('mychannel')
            
            # Add peers
            peer0_org1 = self.client.new_peer(
                'grpc://localhost:7051',
                tls_cert_path=os.path.join(
                    os.path.dirname(__file__),
                    '..', 'fabric-samples', 'test-network',
                    'organizations', 'peerOrganizations', 'org1.example.com',
                    'peers', 'peer0.org1.example.com', 'tls', 'ca.crt'
                )
            )
            self.channel.add_peer(peer0_org1)
            
            # Add orderer
            orderer = self.client.new_orderer(
                'grpc://localhost:7050',
                tls_cert_path=os.path.join(
                    os.path.dirname(__file__),
                    '..', 'fabric-samples', 'test-network',
                    'organizations', 'ordererOrganizations', 'example.com',
                    'orderers', 'orderer.example.com', 'msp', 'tlscacerts', 'tlsca.example.com-cert.pem'
                )
            )
            self.channel.add_orderer(orderer)
            
            logger.info(" Fabric client initialized successfully")
            
        except Exception as e:
            logger.error(f" Failed to initialize Fabric client: {e}")
            self.client = None
    
    def _load_default_config(self):
        """Load default test-network configuration"""
        try:
            # Path to test-network crypto materials
            base_path = os.path.join(
                os.path.dirname(__file__),
                '..', 'fabric-samples', 'test-network'
            )
            
            if not os.path.exists(base_path):
                logger.warning("fabric-samples/test-network not found")
                return
            
            # Load crypto materials
            org1_msp = os.path.join(
                base_path, 'organizations', 'peerOrganizations', 'org1.example.com',
                'users', 'Admin@org1.example.com', 'msp'
            )
            
            # Set crypto paths
            self.client.crypto_suite = {
                'path': org1_msp,
                'msp_id': 'Org1MSP'
            }
            
        except Exception as e:
            logger.error(f"Error loading default config: {e}")
    
    def write_to_ledger(self, 
                       patient_id: str, 
                       cid: str, 
                       hospital_id: str,
                       metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Write EHR record to Fabric ledger
        
        Args:
            patient_id: Patient identifier
            cid: IPFS Content ID
            hospital_id: Hospital identifier
            metadata: Additional metadata
            
        Returns:
            Transaction result
        """
        if not FABRIC_AVAILABLE or self.client is None:
            return self._mock_write_to_ledger(patient_id, cid, hospital_id, metadata)
        
        try:
            logger.info(f"Writing to ledger - Patient: {patient_id}, CID: {cid}")
            
            # Prepare transaction data
            tx_data = {
                "patient_id": patient_id,
                "cid": cid,
                "hospital_id": hospital_id,
                "timestamp": datetime.utcnow().isoformat(),
                "record_type": "EHR",
                "metadata": metadata or {}
            }
            
            # Create chaincode proposal
            args = [
                'CreateEHRRecord',
                patient_id,
                json.dumps(tx_data)
            ]
            
            # Build proposal
            proposal_req = self.client.new_proposal_req(
                prop_type='CHAINCODE',
                cc_type='GOLANG',
                cc_name='ehr',
                cc_version='1.0',
                fcn='invoke',
                args=args,
                cc_path='github.com/ehr_chaincode'
            )
            
            # Send proposal to peers
            responses = self.channel.send_proposal_req(proposal_req)
            
            # Check proposal responses
            for response in responses:
                if response.response.status != 200:
                    logger.error(f"Proposal failed: {response.response.message}")
                    raise Exception(f"Proposal failed: {response.response.message}")
            
            # Create transaction
            transaction = self.client.new_transaction(responses)
            
            # Send to orderer
            broadcast_response = self.channel.send_transaction(transaction)
            
            if broadcast_response.status != 'SUCCESS':
                raise Exception(f"Transaction failed: {broadcast_response.info}")
            
            # Get transaction ID
            tx_id = transaction.tx_id
            
            logger.info(f" Transaction successful - TX ID: {tx_id}")
            
            return {
                "status": "success",
                "transaction_id": tx_id,
                "patient_id": patient_id,
                "cid": cid,
                "hospital_id": hospital_id,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Record written to ledger successfully"
            }
            
        except Exception as e:
            logger.error(f" Ledger write failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "patient_id": patient_id,
                "cid": cid,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def query_ledger(self, patient_id: str = None, cid: str = None) -> Dict[str, Any]:
        """
        Query records from Fabric ledger
        
        Args:
            patient_id: Filter by patient ID
            cid: Filter by IPFS CID
            
        Returns:
            Query results
        """
        if not FABRIC_AVAILABLE or self.client is None:
            return self._mock_query_ledger(patient_id, cid)
        
        try:
            logger.info(f"Querying ledger - Patient: {patient_id}, CID: {cid}")
            
            # Prepare query arguments
            args = ['QueryEHRRecords']
            if patient_id:
                args.append(patient_id)
            elif cid:
                args.append(cid)
            else:
                args.append('all')
            
            # Create query proposal
            query_req = self.client.new_query_req(
                cc_name='ehr',
                fcn='invoke',
                args=args,
                cc_type='GOLANG'
            )
            
            # Send query
            responses = self.channel.send_query_req(query_req)
            
            # Process responses
            records = []
            for response in responses:
                if response.response.status == 200:
                    try:
                        # Parse response
                        data = json.loads(response.response.payload.decode('utf-8'))
                        if isinstance(data, list):
                            records.extend(data)
                        else:
                            records.append(data)
                    except:
                        records.append(response.response.payload.decode('utf-8'))
            
            return {
                "status": "success",
                "record_count": len(records),
                "records": records,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f" Ledger query failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_patient_history(self, patient_id: str) -> Dict[str, Any]:
        """
        Get complete history for a patient
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Patient history
        """
        if not FABRIC_AVAILABLE or self.client is None:
            return self._mock_get_patient_history(patient_id)
        
        try:
            logger.info(f"Getting history for patient: {patient_id}")
            
            args = ['GetPatientHistory', patient_id]
            
            query_req = self.client.new_query_req(
                cc_name='ehr',
                fcn='invoke',
                args=args,
                cc_type='GOLANG'
            )
            
            responses = self.channel.send_query_req(query_req)
            
            history = []
            for response in responses:
                if response.response.status == 200:
                    try:
                        data = json.loads(response.response.payload.decode('utf-8'))
                        history.extend(data)
                    except:
                        history.append(response.response.payload.decode('utf-8'))
            
            return {
                "status": "success",
                "patient_id": patient_id,
                "record_count": len(history),
                "history": history,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f" History query failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "patient_id": patient_id
            }
    
    def _mock_write_to_ledger(self, 
                             patient_id: str, 
                             cid: str, 
                             hospital_id: str,
                             metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock ledger write for testing"""
        logger.info("Using mock ledger write")
        
        import hashlib
        import random
        
        # Generate mock transaction ID
        tx_data = f"{patient_id}{cid}{hospital_id}{datetime.utcnow().isoformat()}"
        tx_id = hashlib.sha256(tx_data.encode()).hexdigest()[:32]
        
        return {
            "status": "success",
            "transaction_id": f"mock_tx_{tx_id}",
            "patient_id": patient_id,
            "cid": cid,
            "hospital_id": hospital_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Mock ledger write - Fabric not configured",
            "mock": True,
            "block_number": random.randint(1000, 9999)
        }
    
    def _mock_query_ledger(self, patient_id: str = None, cid: str = None) -> Dict[str, Any]:
        """Mock ledger query for testing"""
        logger.info("Using mock ledger query")
        
        import random
        from datetime import datetime, timedelta
        
        mock_records = []
        
        if patient_id:
            # Generate mock records for patient
            for i in range(random.randint(1, 5)):
                mock_records.append({
                    "patient_id": patient_id,
                    "cid": f"bafybeiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq{i}",
                    "hospital_id": f"Hospital{random.choice(['A', 'B', 'C'])}",
                    "timestamp": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
                    "record_type": random.choice(["Consultation", "Lab", "Imaging", "Prescription"])
                })
        elif cid:
            # Single record for CID
            mock_records.append({
                "patient_id": f"PAT{random.randint(100, 999)}",
                "cid": cid,
                "hospital_id": "GeneralHospital",
                "timestamp": datetime.utcnow().isoformat(),
                "record_type": "EHR"
            })
        else:
            # Multiple random records
            for i in range(random.randint(3, 10)):
                mock_records.append({
                    "patient_id": f"PAT{random.randint(100, 999)}",
                    "cid": f"bafybeiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq{i}",
                    "hospital_id": f"Hospital{random.choice(['A', 'B', 'C', 'D'])}",
                    "timestamp": (datetime.utcnow() - timedelta(days=random.randint(0, 90))).isoformat(),
                    "record_type": random.choice(["EHR", "Consultation", "Lab", "Imaging"])
                })
        
        return {
            "status": "success",
            "record_count": len(mock_records),
            "records": mock_records,
            "timestamp": datetime.utcnow().isoformat(),
            "mock": True
        }
    
    def _mock_get_patient_history(self, patient_id: str) -> Dict[str, Any]:
        """Mock patient history for testing"""
        logger.info(f"Using mock history for patient: {patient_id}")
        
        import random
        from datetime import datetime, timedelta
        
        history = []
        record_types = ["Initial Consultation", "Lab Test", "X-Ray", "Follow-up", "Prescription", "Surgery"]
        
        for i in range(random.randint(3, 8)):
            days_ago = random.randint(0, 365)
            history.append({
                "record_id": f"REC{random.randint(10000, 99999)}",
                "patient_id": patient_id,
                "record_type": random.choice(record_types),
                "hospital": f"Hospital{random.choice(['A', 'B', 'C'])}",
                "doctor": f"Dr. {random.choice(['Smith', 'Johnson', 'Williams', 'Brown'])}",
                "date": (datetime.utcnow() - timedelta(days=days_ago)).isoformat(),
                "description": f"Patient presented with {random.choice(['fever', 'cough', 'pain', 'fatigue'])}",
                "cid": f"bafybeiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq{i}",
                "blockchain_tx": f"tx_{hashlib.sha256(f'{patient_id}{i}'.encode()).hexdigest()[:20]}"
            })
        
        # Sort by date (newest first)
        history.sort(key=lambda x: x['date'], reverse=True)
        
        return {
            "status": "success",
            "patient_id": patient_id,
            "record_count": len(history),
            "history": history,
            "timestamp": datetime.utcnow().isoformat(),
            "mock": True
        }


# Factory function for easy instantiation
_fabric_client_instance = None

def get_fabric_client() -> FabricLedgerClient:
    """Get singleton instance of FabricLedgerClient"""
    global _fabric_client_instance
    if _fabric_client_instance is None:
        _fabric_client_instance = FabricLedgerClient()
    return _fabric_client_instance

# Your existing function with Fabric integration
def write_to_ledger(patient_id: str, cid: str, hospital_id: str = "HospitalA") -> Dict[str, Any]:
    """
    Write EHR record to Hyperledger Fabric ledger
    
    Args:
        patient_id: Patient identifier
        cid: IPFS Content ID
        hospital_id: Hospital identifier
        
    Returns:
        Transaction result
    """
    # Get Fabric client
    fabric_client = get_fabric_client()
    
    # Write to ledger
    return fabric_client.write_to_ledger(
        patient_id=patient_id,
        cid=cid,
        hospital_id=hospital_id
    )

def query_ledger(patient_id: str = None, cid: str = None) -> Dict[str, Any]:
    """
    Query records from Fabric ledger
    
    Args:
        patient_id: Filter by patient ID
        cid: Filter by IPFS CID
        
    Returns:
        Query results
    """
    fabric_client = get_fabric_client()
    return fabric_client.query_ledger(patient_id=patient_id, cid=cid)

def get_patient_history(patient_id: str) -> Dict[str, Any]:
    """
    Get complete history for a patient
    
    Args:
        patient_id: Patient identifier
        
    Returns:
        Patient history
    """
    fabric_client = get_fabric_client()
    return fabric_client.get_patient_history(patient_id)

'''
# Test functions
def test_fabric_integration():
    """Test Fabric integration"""
    print("🧪 Testing Hyperledger Fabric Integration")
    print("="*60)
    
    client = get_fabric_client()
    
    # Test write
    print("\n1. Testing ledger write...")
    result = write_to_ledger(
        patient_id="TEST001",
        cid="bafybeiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq",
        hospital_id="TestHospital"
    )
    
    print(f"✅ Write result: {result.get('status')}")
    print(f"📝 Transaction ID: {result.get('transaction_id', 'N/A')}")
    
    # Test query
    print("\n2. Testing ledger query...")
    query_result = query_ledger(patient_id="TEST001")
    
    if query_result.get('status') == 'success':
        print(f"✅ Query successful")
        print(f"📊 Records found: {query_result.get('record_count', 0)}")
        if query_result.get('records'):
            print(f"📄 First record: {json.dumps(query_result['records'][0], indent=2)}")
    
    # Test patient history
    print("\n3. Testing patient history...")
    history_result = get_patient_history("TEST001")
    
    if history_result.get('status') == 'success':
        print(f"✅ History retrieved")
        print(f"📅 Records in history: {history_result.get('record_count', 0)}")
    
    print("\n" + "="*60)
    print("✅ Fabric integration test complete")


if __name__ == "__main__":
    test_fabric_integration()'''