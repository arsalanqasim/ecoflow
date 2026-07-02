import time
from typing import Dict, Any, List, Optional
from agents.agent_cards import AGENT_CARDS, AgentCard
from agents.a2a_session import RemoteAgentSession, A2AMessage

class A2ADirectory:
    def __init__(self):
        self.cards: Dict[str, AgentCard] = AGENT_CARDS
        
    def get_agent_card(self, org_name: str) -> Optional[AgentCard]:
        return self.cards.get(org_name)
        
    def list_agent_cards(self) -> List[AgentCard]:
        return list(self.cards.values())

    def get_or_create_session(self, remote_org: str, state: Any) -> RemoteAgentSession:
        if not hasattr(state, "a2a_sessions") or state.a2a_sessions is None:
            state.a2a_sessions = {}
        
        if remote_org not in state.a2a_sessions:
            session = RemoteAgentSession(remote_org=remote_org)
            state.a2a_sessions[remote_org] = session
        else:
            session = state.a2a_sessions[remote_org]
            
        return session

    def send_remote_message(self, remote_org: str, request_type: str, payload: Dict[str, Any], state: Any) -> Dict[str, Any]:
        """
        Abstract A2A Communication Endpoint.
        Simulates remote network execution, audits requests/responses, and enforces security.
        """
        start_time = time.time()
        session = self.get_or_create_session(remote_org, state)
        card = self.get_agent_card(remote_org)
        
        if not card:
            raise ValueError(f"Organization '{remote_org}' not found in Agent Directory.")
            
        # Log request in session conversation history
        req_msg = session.log_message(
            sender="EcoFlow Corp",
            recipient=remote_org,
            request_type=request_type,
            payload=payload
        )
        
        # Log request in Distributed Audit Trail
        audit_entry = {
            "session_id": session.session_id,
            "remote_org": remote_org,
            "type": "A2A_REQUEST",
            "request_type": request_type,
            "payload": payload,
            "auth_state": session.auth_state,
            "timestamp": time.time()
        }
        state.a2a_audit_trail.append(audit_entry)
        
        # Handle Failure Simulations based on payload settings
        failure_trigger = payload.get("simulate_failure")
        if failure_trigger == "OFFLINE" or not card.health.availability:
            raise ConnectionError(f"Remote Agent Failure: {remote_org} is offline.")
        elif failure_trigger == "TIMEOUT":
            time.sleep(0.01)
            raise TimeoutError(f"Remote Agent Timeout: {remote_org} failed to respond in time.")
        elif failure_trigger == "MALFORMED":
            return {"bad_key": None}  # trigger schema validator error
        elif failure_trigger == "VERSION_MISMATCH":
            raise ValueError(f"A2A Protocol Mismatch: remote version 2.0.0 incompatible with client version {card.identity.version}")
            
        # 1. Authentication Check
        auth_token = payload.get("auth_token", session.auth_token)
        if auth_token:
            session.authenticate("EcoFlow Corp", auth_token)
            
        if session.auth_state == "EXPIRED":
            err_msg = "Authentication Expired: Security token has expired."
            session.log_message(remote_org, "EcoFlow Corp", "Error Response", {"error": err_msg})
            state.a2a_audit_trail.append({
                "session_id": session.session_id,
                "remote_org": remote_org,
                "type": "A2A_FAILURE",
                "error": "AuthExpired",
                "message": err_msg,
                "timestamp": time.time()
            })
            raise ConnectionRefusedError(err_msg)
            
        if session.auth_state != "AUTHENTICATED":
            err_msg = "Authentication Required: Security handshake missing."
            session.log_message(remote_org, "EcoFlow Corp", "Error Response", {"error": err_msg})
            state.a2a_audit_trail.append({
                "session_id": session.session_id,
                "remote_org": remote_org,
                "type": "A2A_FAILURE",
                "error": "Unauthenticated",
                "message": err_msg,
                "timestamp": time.time()
            })
            raise ConnectionRefusedError(err_msg)

        # 2. Authorization (Permission Check)
        required_perm = card.security_policies.required_permissions[0]
        if required_perm not in session.permission_grants:
            # Handle special Negotiation for Supplier C
            if request_type == "Negotiate" and remote_org == "Supplier_C":
                session.negotiation_state = "AGREED"
                session.permission_grants.append("READ_SCOPE3")  # grant temporary access
                session.permission_grants.append("READ_EMISSIONS")
                resp_payload = {
                    "status": "Negotiated",
                    "granted_permissions": ["READ_SCOPE3", "READ_EMISSIONS"],
                    "message": "Negotiation accepted: monthly averages will be disclosed under READ_EMISSIONS."
                }
                session.log_message(remote_org, "EcoFlow Corp", "Negotiation Response", resp_payload)
                state.a2a_audit_trail.append({
                    "session_id": session.session_id,
                    "remote_org": remote_org,
                    "type": "A2A_RESPONSE",
                    "response": resp_payload,
                    "latency": time.time() - start_time,
                    "timestamp": time.time()
                })
                return resp_payload
                
            err_msg = f"Access Denied: Required permission '{required_perm}' is not granted."
            session.log_message(remote_org, "EcoFlow Corp", "Error Response", {"error": err_msg})
            state.a2a_audit_trail.append({
                "session_id": session.session_id,
                "remote_org": remote_org,
                "type": "A2A_FAILURE",
                "error": "PermissionDenied",
                "message": err_msg,
                "timestamp": time.time()
            })
            raise PermissionError(err_msg)

        # 3. Request Dispatching / Remote Database Mock Routing
        response_payload = {}
        
        if remote_org == "Supplier_A":
            # Direct Verified Log
            response_payload = {
                "supplier_id": 1,
                "supplier_name": "Supplier A Corp",
                "emissions_tCO2": 150.0,
                "disclosure_type": "Verified",
                "verification_source": "Annual Auditor Statement 2025"
            }
        elif remote_org == "Supplier_B":
            # Estimated averages
            response_payload = {
                "supplier_id": 2,
                "supplier_name": "Supplier B Corp",
                "emissions_tCO2": 320.0,
                "disclosure_type": "Estimated",
                "verification_source": "Industry Average Sector Database"
            }
        elif remote_org == "Supplier_C":
            # Partial/Estimated values after negotiation
            response_payload = {
                "supplier_id": 3,
                "supplier_name": "Supplier C Corp",
                "emissions_tCO2": 450.0,
                "disclosure_type": "Estimated",
                "verification_source": "Self-Declared Estimated Log"
            }
        elif remote_org == "Certification_Authority":
            supplier_name = payload.get("supplier_name", "")
            if "Supplier A" in supplier_name:
                response_payload = {
                    "is_certified": True,
                    "status": "APPROVED",
                    "audit_timestamp": time.strftime("%Y-%m-%d"),
                    "certificate_id": "CERT-2025-FR-991A",
                    "explanation": "Certified annual audit conforms to standard ISO-14064."
                }
            elif "Supplier B" in supplier_name:
                response_payload = {
                    "is_certified": True,
                    "status": "APPROVED",
                    "audit_timestamp": time.strftime("%Y-%m-%d"),
                    "certificate_id": "CERT-2025-DE-043B",
                    "explanation": "Standard certification confirmed, using industry standard fallbacks."
                }
            else:
                response_payload = {
                    "is_certified": False,
                    "status": "REJECTED",
                    "audit_timestamp": None,
                    "explanation": "Supplier certification database contains no entries for this organization."
                }
        elif remote_org == "Logistics_Provider":
            response_payload = {
                "shipping_emissions_tCO2": 45.0,
                "route_verified": True,
                "fuel_source": "Biodiesel B100 Mix",
                "carrier_certification": "Carrier-EcoPass-Logistics"
            }

        # Log response in session
        session.log_message(remote_org, "EcoFlow Corp", "A2A Response", response_payload)
        
        # Log response in audit trail
        latency = time.time() - start_time
        state.a2a_audit_trail.append({
            "session_id": session.session_id,
            "remote_org": remote_org,
            "type": "A2A_RESPONSE",
            "response": response_payload,
            "latency": latency,
            "timestamp": time.time()
        })
        
        return response_payload

a2a_directory = A2ADirectory()
