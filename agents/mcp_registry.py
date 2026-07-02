import time
import uuid
import logging
import json
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

logger = logging.getLogger("MCPRegistry")

class MCPSessionContext(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tools_used: List[str] = Field(default_factory=list)
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)
    cached_responses: Dict[str, Any] = Field(default_factory=dict)
    failures: List[Dict[str, Any]] = Field(default_factory=list)
    fallbacks: List[Dict[str, Any]] = Field(default_factory=list)
    total_token_usage: int = 0
    total_latency: float = 0.0
    permissions_granted: List[str] = Field(default_factory=lambda: ["READ_DB", "WRITE_DB", "RUN_CALC", "RUN_AUDIT"])

class ToolHealth(BaseModel):
    availability: float = 1.0
    avg_latency: float = 0.0
    error_rate: float = 0.0
    success_count: int = 0
    total_count: int = 0

class MCPTool(BaseModel):
    name: str
    server_name: str
    description: str
    capabilities: List[str]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    supported_domains: List[str]
    estimated_latency: float
    estimated_cost: float
    reliability_score: float
    version: str
    tags: List[str]
    required_permissions: List[str]
    example_usage: str
    func: Any = Field(exclude=True) # Exclude callable from serialization

def validate_schema(data: Any, schema: Dict[str, Any]) -> bool:
    if not isinstance(schema, dict):
        return True
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(data, dict):
            raise TypeError("Expected object data structure.")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Check required fields
        for req in required:
            if req not in data:
                raise ValueError(f"Missing required field: '{req}'")
                
        # Check property types
        for k, v in data.items():
            if k in properties:
                prop_type = properties[k].get("type")
                if prop_type == "integer":
                    if isinstance(v, bool) or not isinstance(v, (int, float)):
                        raise TypeError(f"Property '{k}' must be an integer, got {type(v).__name__}")
                elif prop_type == "number":
                    if isinstance(v, bool) or not isinstance(v, (int, float)):
                        raise TypeError(f"Property '{k}' must be a number, got {type(v).__name__}")
                elif prop_type == "string":
                    if not isinstance(v, str):
                        raise TypeError(f"Property '{k}' must be a string, got {type(v).__name__}")
                elif prop_type == "boolean":
                    if not isinstance(v, bool):
                        raise TypeError(f"Property '{k}' must be a boolean, got {type(v).__name__}")
                elif prop_type == "array":
                    if not isinstance(v, list):
                        raise TypeError(f"Property '{k}' must be an array, got {type(v).__name__}")
    return True

# --- Virtual MCP Servers Implementations ---

def get_supplier_carbon_status_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    supplier_id = args.get("supplier_id")
    supplier_name = args.get("supplier_name")
    
    from api.database import SessionLocal
    from api.models import Supplier, Shipment, Emission
    
    db = SessionLocal()
    try:
        if supplier_id:
            supplier = db.query(Supplier).filter_by(supplier_id=supplier_id).first()
        elif supplier_name:
            supplier = db.query(Supplier).filter(Supplier.name.like(f"%{supplier_name}%")).first()
        else:
            supplier = None
            
        if not supplier:
            return {"supplier_name": "Unknown", "status": "Unknown", "confidence": 0.5}
            
        shipments = db.query(Shipment).filter_by(supplier_id=supplier.supplier_id).all()
        if not shipments:
            status = "Missing"
            confidence = 0.5
        else:
            shipment_ids = [s.shipment_id for s in shipments]
            emissions = db.query(Emission).filter(Emission.shipment_id.in_(shipment_ids)).all()
            if not emissions:
                status = "Unknown"
                confidence = 0.5
            else:
                methods = [e.method for e in emissions]
                if "FALLBACK_AVERAGE" in methods:
                    status = "Estimated"
                    confidence = 0.8
                else:
                    status = "Verified"
                    confidence = 1.0
        db.close()
        return {"supplier_name": supplier.name, "status": status, "confidence": confidence}
    except Exception as e:
        db.close()
        logger.error(f"Error in get_supplier_carbon_status_impl: {e}")
        raise e

def get_supplier_evidence_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    supplier_id = args.get("supplier_id")
    return {
        "supplier_id": supplier_id,
        "certificates": [{"type": "ISO 14064", "issued_date": "2025-01-15", "status": "Active"}]
    }

def compute_emissions_join_impl(args: Dict[str, Any]) -> str:
    shipments_json = args.get("shipments_json")
    factors_json = args.get("factors_json")
    from fastmcp.data_processing_server import compute_emissions_join
    return compute_emissions_join(shipments_json, factors_json)

def compute_regional_grid_intensity_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    country_code = args.get("country_code", "EU").strip().upper()
    # Mock realistic grid mixes: France low-carbon nuclear/renewables, China heavy coal
    grid_intensity = 0.40  # regional average default
    source = "EU Grid Default"
    confidence = 0.80
    
    if country_code == "FR":
        grid_intensity = 0.05
        source = "RTE France Real-Time Mix"
        confidence = 0.95
    elif country_code == "CN":
        grid_intensity = 0.62
        source = "China National Grid Factor"
        confidence = 0.90
    elif country_code == "DE":
        grid_intensity = 0.35
        source = "UBA Germany Factor"
        confidence = 0.90
        
    return {
        "country_code": country_code,
        "grid_intensity_tCO2_per_MWh": grid_intensity,
        "source": source,
        "confidence": confidence
    }

def query_cbam_regulations_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    hs_code = str(args.get("hs_code", ""))
    is_regulated = hs_code.startswith(("72", "73", "76", "28", "31"))  # Steel, Iron, Aluminum, Fertilizer, Cement
    return {
        "hs_code": hs_code,
        "is_regulated": is_regulated,
        "regulation_info": "CBAM regulated sector under EU Import Scope A." if is_regulated else "Not in scope."
    }

def audit_cbam_tariff_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    shipment_id = args.get("shipment_id")
    carbon_price = args.get("carbon_price", 80.0)
    
    from api.database import SessionLocal
    from api.models import Shipment, Emission, CBAMAudit, Product
    db = SessionLocal()
    try:
        shipment = db.query(Shipment).filter_by(shipment_id=shipment_id).first()
        if not shipment:
            db.close()
            return {"shipment_id": shipment_id, "tariff_due_eur": 0.0, "compliance_status": "Unknown"}
            
        emission = db.query(Emission).filter_by(shipment_id=shipment_id).first()
        if not emission:
            db.close()
            return {"shipment_id": shipment_id, "tariff_due_eur": 0.0, "compliance_status": "No Emissions Calculated"}
            
        tariff = emission.emission_tCO2 * carbon_price
        
        # Write/Update Audit row in DB using emission_id
        audit_row = db.query(CBAMAudit).filter_by(emission_id=emission.emission_id).first()
        if audit_row:
            audit_row.tariff_due_eur = tariff
        else:
            audit_row = CBAMAudit(
                emission_id=emission.emission_id,
                tariff_due_eur=tariff,
                compliance_status="SUBJECT TO TARIFF"
            )
            db.add(audit_row)
            
        db.commit()
        db.close()
        
        return {
            "shipment_id": shipment_id,
            "tariff_due_eur": round(tariff, 2),
            "compliance_status": "COMPLIANT"
        }
    except Exception as e:
        db.close()
        logger.error(f"Error in audit_cbam_tariff_impl: {e}")
        raise e

def optimize_logistics_routes_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    shipment_id = args.get("shipment_id")
    
    from api.database import SessionLocal
    from api.models import Emission
    db = SessionLocal()
    try:
        emission = db.query(Emission).filter_by(shipment_id=shipment_id).first()
        original = emission.emission_tCO2 if emission else 100.0
        db.close()
        
        optimized = original * 0.6  # 40% reduction
        savings = original - optimized
        return {
            "shipment_id": shipment_id,
            "original_emissions": original,
            "optimized_emissions": optimized,
            "savings_tCO2": round(savings, 2),
            "alternative_carrier": "GreenFreight Eco-Rail"
        }
    except Exception as e:
        db.close()
        logger.error(f"Error in optimize_logistics_routes_impl: {e}")
        raise e

def predict_emissions_forecast_impl(args: Dict[str, Any]) -> str:
    historical_emissions_json = args.get("historical_emissions_json")
    steps = args.get("steps", 4)
    from fastmcp.model_serving_server import predict_emissions_forecast
    return predict_emissions_forecast(historical_emissions_json, steps=steps)

# --- MCP Registry Engine ---

class MCPToolRegistry:
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.health_db: Dict[str, ToolHealth] = {}
        self._initialize_default_tools()
        
    def _initialize_default_tools(self):
        # 1. Supplier Tools
        self.register_tool(MCPTool(
            name="get_supplier_carbon_status",
            server_name="Supplier Intelligence Server",
            description="Queries supplier database audits and determines if emission records are verified, estimated, or missing.",
            capabilities=["verify_supplier", "check_supplier_data_status"],
            input_schema={
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"},
                    "supplier_name": {"type": "string"}
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "supplier_name": {"type": "string"},
                    "status": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["supplier_name", "status"]
            },
            supported_domains=["sustainability", "compliance"],
            estimated_latency=0.05,
            estimated_cost=0.001,
            reliability_score=0.98,
            version="1.0.0",
            tags=["supplier", "status"],
            required_permissions=["READ_DB"],
            example_usage="get_supplier_carbon_status(supplier_id=1)",
            func=get_supplier_carbon_status_impl
        ))
        
        self.register_tool(MCPTool(
            name="get_supplier_evidence",
            server_name="Supplier Intelligence Server",
            description="Retrieves evidence certificates and emission reports uploaded by the supplier.",
            capabilities=["fetch_certificates", "supplier_evidence"],
            input_schema={
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"}
                },
                "required": ["supplier_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"},
                    "certificates": {"type": "array"}
                }
            },
            supported_domains=["sustainability", "legal"],
            estimated_latency=0.10,
            estimated_cost=0.002,
            reliability_score=0.95,
            version="1.0.0",
            tags=["evidence", "compliance"],
            required_permissions=["READ_DB"],
            example_usage="get_supplier_evidence(supplier_id=1)",
            func=get_supplier_evidence_impl
        ))
        
        # 2. Carbon Calculation Tools
        self.register_tool(MCPTool(
            name="compute_emissions_join",
            server_name="Carbon Intelligence Server",
            description="Performs database merges between shipments and carbon intensity factors to compute shipment-level emissions.",
            capabilities=["calc_emissions", "merge_join_factors"],
            input_schema={
                "type": "object",
                "properties": {
                    "shipments_json": {"type": "string"},
                    "factors_json": {"type": "string"}
                },
                "required": ["shipments_json", "factors_json"]
            },
            output_schema={"type": "string"},
            supported_domains=["sustainability"],
            estimated_latency=0.15,
            estimated_cost=0.005,
            reliability_score=0.99,
            version="1.0.0",
            tags=["emissions", "calculator"],
            required_permissions=["READ_DB", "RUN_CALC"],
            example_usage="compute_emissions_join(shipments_json='...', factors_json='...')",
            func=compute_emissions_join_impl
        ))
        
        self.register_tool(MCPTool(
            name="compute_regional_grid_intensity",
            server_name="Carbon Intelligence Server",
            description="Fetches regional electricity grid carbon intensity values (e.g. RTE France nuclear mix vs global averages) to serve as fallbacks.",
            capabilities=["fallback_grid_factors", "grid_intensity"],
            input_schema={
                "type": "object",
                "properties": {
                    "country_code": {"type": "string"}
                },
                "required": ["country_code"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "country_code": {"type": "string"},
                    "grid_intensity_tCO2_per_MWh": {"type": "number"},
                    "source": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["country_code", "grid_intensity_tCO2_per_MWh"]
            },
            supported_domains=["sustainability"],
            estimated_latency=0.02,
            estimated_cost=0.0005,
            reliability_score=0.97,
            version="1.0.0",
            tags=["grid", "intensity"],
            required_permissions=["READ_DB"],
            example_usage="compute_regional_grid_intensity(country_code='FR')",
            func=compute_regional_grid_intensity_impl
        ))
        
        # 3. CBAM Tools
        self.register_tool(MCPTool(
            name="query_cbam_regulations",
            server_name="CBAM Knowledge Server",
            description="Checks if product HS codes fall under EU Border Adjustment regulations scope details.",
            capabilities=["check_cbam_scope", "query_regulations"],
            input_schema={
                "type": "object",
                "properties": {
                    "hs_code": {"type": "string"}
                },
                "required": ["hs_code"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "hs_code": {"type": "string"},
                    "is_regulated": {"type": "boolean"},
                    "regulation_info": {"type": "string"}
                }
            },
            supported_domains=["compliance"],
            estimated_latency=0.05,
            estimated_cost=0.001,
            reliability_score=0.96,
            version="1.0.0",
            tags=["cbam", "regulations"],
            required_permissions=["READ_DB"],
            example_usage="query_cbam_regulations(hs_code='720810')",
            func=query_cbam_regulations_impl
        ))
        
        self.register_tool(MCPTool(
            name="audit_cbam_tariff",
            server_name="CBAM Knowledge Server",
            description="Audits calculated shipment emissions to compute compliance Border Adjustment tariff dues and commits to audit DB.",
            capabilities=["audit_tariffs", "cbam_calculation"],
            input_schema={
                "type": "object",
                "properties": {
                    "shipment_id": {"type": "integer"},
                    "carbon_price": {"type": "number"}
                },
                "required": ["shipment_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "shipment_id": {"type": "integer"},
                    "tariff_due_eur": {"type": "number"},
                    "compliance_status": {"type": "string"}
                },
                "required": ["shipment_id", "tariff_due_eur"]
            },
            supported_domains=["compliance", "sustainability"],
            estimated_latency=0.08,
            estimated_cost=0.003,
            reliability_score=0.98,
            version="1.0.0",
            tags=["cbam", "tariff"],
            required_permissions=["READ_DB", "WRITE_DB", "RUN_AUDIT"],
            example_usage="audit_cbam_tariff(shipment_id=1, carbon_price=80.0)",
            func=audit_cbam_tariff_impl
        ))
        
        # 4. Logistics Optimization Tools
        self.register_tool(MCPTool(
            name="optimize_logistics_routes",
            server_name="Logistics Optimization Server",
            description="Applies logistics re-routing logic to suggest green carrier corridors.",
            capabilities=["optimize_logistics", "route_optimization"],
            input_schema={
                "type": "object",
                "properties": {
                    "shipment_id": {"type": "integer"}
                },
                "required": ["shipment_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "shipment_id": {"type": "integer"},
                    "original_emissions": {"type": "number"},
                    "optimized_emissions": {"type": "number"},
                    "savings_tCO2": {"type": "number"},
                    "alternative_carrier": {"type": "string"}
                }
            },
            supported_domains=["logistics"],
            estimated_latency=0.04,
            estimated_cost=0.0015,
            reliability_score=0.94,
            version="1.0.0",
            tags=["logistics", "optimization"],
            required_permissions=["READ_DB"],
            example_usage="optimize_logistics_routes(shipment_id=1)",
            func=optimize_logistics_routes_impl
        ))
        
        # 5. Forecast Tools
        self.register_tool(MCPTool(
            name="predict_emissions_forecast",
            server_name="Forecast Server",
            description="Calculates linear regression projections on historical emissions to forecast future targets.",
            capabilities=["run_forecast", "forecast_emissions"],
            input_schema={
                "type": "object",
                "properties": {
                    "historical_emissions_json": {"type": "string"},
                    "steps": {"type": "integer"}
                },
                "required": ["historical_emissions_json"]
            },
            output_schema={"type": "string"},
            supported_domains=["sustainability"],
            estimated_latency=0.12,
            estimated_cost=0.004,
            reliability_score=0.98,
            version="1.0.0",
            tags=["forecast", "emissions"],
            required_permissions=["READ_DB"],
            example_usage="predict_emissions_forecast(historical_emissions_json='...', steps=4)",
            func=predict_emissions_forecast_impl
        ))

    def register_tool(self, tool: MCPTool):
        self.tools[tool.name] = tool
        self.health_db[tool.name] = ToolHealth()
        
    def list_tools(self) -> List[MCPTool]:
        return list(self.tools.values())
        
    def get_tool(self, name: str) -> Optional[MCPTool]:
        return self.tools.get(name)
        
    def search_tools(self, query: str) -> List[MCPTool]:
        query_lower = query.lower()
        words = [w.strip() for w in query_lower.replace("_", " ").split() if w.strip()]
        if not words:
            return []
            
        matches = []
        for name, tool in self.tools.items():
            name_norm = name.lower().replace("_", " ")
            desc_norm = tool.description.lower()
            caps_norm = [c.lower().replace("_", " ") for c in tool.capabilities]
            tags_norm = [t.lower() for t in tool.tags]
            
            match_all = True
            for word in words:
                found = (word in name_norm or 
                         word in desc_norm or 
                         any(word in cap for cap in caps_norm) or
                         any(word in tag for tag in tags_norm))
                if not found:
                    match_all = False
                    break
            if match_all:
                matches.append(tool)
        return matches

    def execute_tool(self, tool_name: str, args: Dict[str, Any], state: Any) -> Any:
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found in registry.")
            
        health = self.health_db[tool_name]
        health.total_count += 1
        
        # 1. Initialize MCP Session Context on state if not present
        if not getattr(state, "mcp_session", None):
            state.mcp_session = MCPSessionContext()
            
        session = state.mcp_session
        
        # 2. Check Security Permissions
        for perm in tool.required_permissions:
            if perm not in session.permissions_granted:
                health.error_rate = (health.error_rate * (health.total_count - 1) + 1.0) / health.total_count
                err_msg = f"Security Violation: Permission '{perm}' is required to run tool '{tool_name}'."
                logger.error(err_msg)
                
                # Log failure to session context
                session.failures.append({
                    "tool_name": tool_name,
                    "error_type": "PermissionError",
                    "message": err_msg,
                    "timestamp": time.time()
                })
                raise PermissionError(err_msg)

        # 3. Response Caching
        cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        if cache_key in session.cached_responses:
            cache_entry = session.cached_responses[cache_key]
            # Verify cache entry hasn't expired (60s cache TTL)
            if time.time() - cache_entry["timestamp"] < 60.0:
                logger.info(f"[CACHE HIT] Returning cached output for tool: {tool_name}")
                health.success_count += 1
                health.availability = health.success_count / health.total_count
                
                # Log trace event
                state.mcp_validation_events.append({
                    "tool_name": tool_name,
                    "type": "CACHE_HIT",
                    "timestamp": time.time(),
                    "cached_at": cache_entry["timestamp"]
                })
                return cache_entry["data"]

        # 4. Input Schema Validation
        try:
            validate_schema(args, tool.input_schema)
        except Exception as ve:
            health.error_rate = (health.error_rate * (health.total_count - 1) + 1.0) / health.total_count
            err_msg = f"Input validation failed for tool '{tool_name}': {ve}"
            logger.error(err_msg)
            session.failures.append({
                "tool_name": tool_name,
                "error_type": "InputSchemaValidationError",
                "message": err_msg,
                "timestamp": time.time()
            })
            raise ve

        # 5. Execution & Latency Monitoring
        start_time = time.time()
        try:
            result = tool.func(args)
            duration = time.time() - start_time
            
            # Update health statistics
            health.success_count += 1
            health.avg_latency = (health.avg_latency * (health.success_count - 1) + duration) / health.success_count
            health.availability = health.success_count / health.total_count
            health.error_rate = (health.total_count - health.success_count) / health.total_count
            
            # Update session context statistics
            session.total_latency += duration
            if tool_name not in session.tools_used:
                session.tools_used.append(tool_name)
                
        except Exception as e:
            duration = time.time() - start_time
            health.error_rate = (health.error_rate * (health.total_count - 1) + 1.0) / health.total_count
            health.avg_latency = (health.avg_latency * (health.total_count - 1) + duration) / health.total_count
            
            err_msg = f"Execution failed in tool '{tool_name}': {e}"
            logger.error(err_msg)
            session.failures.append({
                "tool_name": tool_name,
                "error_type": type(e).__name__,
                "message": err_msg,
                "timestamp": time.time()
            })
            raise e

        # 6. Output Schema Validation
        try:
            validate_schema(result, tool.output_schema)
            state.mcp_validation_events.append({
                "tool_name": tool_name,
                "type": "VALIDATION_SUCCESS",
                "timestamp": time.time(),
                "duration": duration
            })
        except Exception as o_ve:
            err_msg = f"Output schema validation failed for tool '{tool_name}': {o_ve}"
            logger.warning(err_msg)
            state.mcp_validation_events.append({
                "tool_name": tool_name,
                "type": "VALIDATION_FAILURE",
                "message": err_msg,
                "timestamp": time.time()
            })
            # We don't fail immediately, but log warning as requested by fallbacks

        # 7. Write to Response Cache
        session.cached_responses[cache_key] = {
            "data": result,
            "timestamp": time.time(),
            "confidence": tool.reliability_score,
            "freshness": "Fresh"
        }
        
        # 8. Record to Execution History
        session.execution_history.append({
            "tool_name": tool_name,
            "arguments": args,
            "result_summary": str(result)[:200] + "..." if len(str(result)) > 200 else str(result),
            "latency": duration,
            "timestamp": time.time()
        })
        
        # Write performance metrics
        state.mcp_performance_metrics[tool_name] = {
            "availability": health.availability,
            "avg_latency": health.avg_latency,
            "error_rate": health.error_rate,
            "total_count": health.total_count
        }
        
        return result

# Singleton Instance
registry = MCPToolRegistry()
