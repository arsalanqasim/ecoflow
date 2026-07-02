from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class IdentityMetadata(BaseModel):
    agent_id: str
    organization_name: str
    version: str = "1.0.0"
    jurisdiction: str = "EU"
    supported_languages: List[str] = ["en", "de"]

class SecurityPolicy(BaseModel):
    required_permissions: List[str]
    authentication_type: str = "mutual_tls_jwt"

class TrustMetadata(BaseModel):
    initial_trust_score: float = 1.0
    is_certified: bool = True
    audit_history_years: int = 3

class HealthStatus(BaseModel):
    availability: bool = True
    status: str = "ACTIVE"  # ACTIVE, MAINTENANCE, SUSPENDED

class AgentCard(BaseModel):
    identity: IdentityMetadata
    role: str
    capabilities: List[str]
    allowed_requests: List[str]
    input_schemas: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    output_schemas: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    supported_message_types: List[str] = Field(default_factory=list)
    security_policies: SecurityPolicy
    trust_metadata: TrustMetadata
    health: HealthStatus

# Pre-registered Agent Cards for A2A network
AGENT_CARDS = {
    "Supplier_A": AgentCard(
        identity=IdentityMetadata(agent_id="supplier_a_agent", organization_name="Supplier A Corp", jurisdiction="FR"),
        role="Supplier",
        capabilities=["get_scope3_emissions", "get_electricity_mix"],
        allowed_requests=["Carbon Data Request", "Electricity Mix Request", "Evidence Request"],
        input_schemas={
            "get_scope3_emissions": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "quantity": {"type": "number"}
                },
                "required": ["product_id"]
            }
        },
        output_schemas={
            "get_scope3_emissions": {
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"},
                    "emissions_tCO2": {"type": "number"},
                    "disclosure_type": {"type": "string"},  # Verified, Estimated, Redacted, Unavailable, Restricted
                    "verification_source": {"type": "string"}
                },
                "required": ["supplier_id", "emissions_tCO2", "disclosure_type"]
            }
        },
        supported_message_types=["Carbon Data Request", "Evidence Request"],
        security_policies=SecurityPolicy(required_permissions=["READ_EMISSIONS"]),
        trust_metadata=TrustMetadata(initial_trust_score=0.98, is_certified=True),
        health=HealthStatus(availability=True, status="ACTIVE")
    ),
    
    "Supplier_B": AgentCard(
        identity=IdentityMetadata(agent_id="supplier_b_agent", organization_name="Supplier B Corp", jurisdiction="DE"),
        role="Supplier",
        capabilities=["get_scope3_emissions"],
        allowed_requests=["Carbon Data Request"],
        input_schemas={
            "get_scope3_emissions": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"}
                },
                "required": ["product_id"]
            }
        },
        output_schemas={
            "get_scope3_emissions": {
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"},
                    "emissions_tCO2": {"type": "number"},
                    "disclosure_type": {"type": "string"}
                },
                "required": ["supplier_id", "emissions_tCO2", "disclosure_type"]
            }
        },
        supported_message_types=["Carbon Data Request"],
        security_policies=SecurityPolicy(required_permissions=["READ_EMISSIONS"]),
        trust_metadata=TrustMetadata(initial_trust_score=0.85, is_certified=True),
        health=HealthStatus(availability=True, status="ACTIVE")
    ),
    
    "Supplier_C": AgentCard(
        identity=IdentityMetadata(agent_id="supplier_c_agent", organization_name="Supplier C Corp", jurisdiction="CN"),
        role="Supplier",
        capabilities=["get_scope3_emissions"],
        allowed_requests=["Carbon Data Request"],
        input_schemas={
            "get_scope3_emissions": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"}
                },
                "required": ["product_id"]
            }
        },
        output_schemas={
            "get_scope3_emissions": {
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"},
                    "emissions_tCO2": {"type": "number"},
                    "disclosure_type": {"type": "string"}
                },
                "required": ["supplier_id", "emissions_tCO2", "disclosure_type"]
            }
        },
        supported_message_types=["Carbon Data Request"],
        security_policies=SecurityPolicy(required_permissions=["READ_SCOPE3"]),
        trust_metadata=TrustMetadata(initial_trust_score=0.75, is_certified=False),
        health=HealthStatus(availability=True, status="ACTIVE")
    ),
    
    "Certification_Authority": AgentCard(
        identity=IdentityMetadata(agent_id="ca_agent", organization_name="CertiTrust Global", jurisdiction="BE"),
        role="Certification Authority",
        capabilities=["verify_supplier_certification", "validate_carbon_declaration"],
        allowed_requests=["Verification Request", "Certification Request", "Audit Request"],
        security_policies=SecurityPolicy(required_permissions=["READ_CERTIFICATION"]),
        trust_metadata=TrustMetadata(initial_trust_score=1.0, is_certified=True),
        health=HealthStatus(availability=True, status="ACTIVE")
    ),
    
    "Logistics_Provider": AgentCard(
        identity=IdentityMetadata(agent_id="logistics_agent", organization_name="GreenFreight Logistics", jurisdiction="NL"),
        role="Logistics Provider",
        capabilities=["get_shipping_emissions", "verify_route"],
        allowed_requests=["Carbon Data Request", "Evidence Request"],
        security_policies=SecurityPolicy(required_permissions=["READ_TRANSPORT"]),
        trust_metadata=TrustMetadata(initial_trust_score=0.95, is_certified=True),
        health=HealthStatus(availability=True, status="ACTIVE")
    )
}
