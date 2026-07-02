import pytest
import time
from agents.shared_state import ExecutionState
from agents.mcp_registry import registry, MCPTool, MCPSessionContext, validate_schema

def test_mcp_tool_registration_and_search():
    # Verify default tools exist
    tools = registry.list_tools()
    assert len(tools) >= 5
    
    # Search registry for supplier tools
    supplier_tools = registry.search_tools("supplier")
    assert len(supplier_tools) >= 2
    assert any(t.name == "get_supplier_carbon_status" for t in supplier_tools)
    
    # Search by capability
    calc_tools = registry.search_tools("calc_emissions")
    assert len(calc_tools) >= 1
    assert calc_tools[0].name == "compute_emissions_join"

def test_mcp_schema_validation():
    # Positive validation
    input_schema = {
        "type": "object",
        "properties": {
            "supplier_id": {"type": "integer"},
            "supplier_name": {"type": "string"}
        },
        "required": ["supplier_id"]
    }
    
    args = {"supplier_id": 42, "supplier_name": "Test Co."}
    assert validate_schema(args, input_schema) is True
    
    # Negative validation - missing required key
    bad_args = {"supplier_name": "Test Co."}
    with pytest.raises(ValueError, match="Missing required field: 'supplier_id'"):
        validate_schema(bad_args, input_schema)
        
    # Negative validation - invalid type
    bad_type = {"supplier_id": "forty-two"}
    with pytest.raises(TypeError, match="Property 'supplier_id' must be an integer"):
        validate_schema(bad_type, input_schema)

def test_mcp_caching():
    state = ExecutionState(user_goal="Test caching")
    state.mcp_session = MCPSessionContext()
    
    # Run tool first time (cache miss)
    args = {"country_code": "FR"}
    res1 = registry.execute_tool("compute_regional_grid_intensity", args, state)
    
    # Confirm cache was written
    cache_key = f"compute_regional_grid_intensity:{registry.execute_tool.__name__}" # actually it's json dump args
    assert len(state.mcp_session.cached_responses) == 1
    
    # Run tool second time (cache hit)
    start_hits = len([e for e in state.mcp_validation_events if e.get("type") == "CACHE_HIT"])
    res2 = registry.execute_tool("compute_regional_grid_intensity", args, state)
    
    assert res1 == res2
    end_hits = len([e for e in state.mcp_validation_events if e.get("type") == "CACHE_HIT"])
    assert end_hits == start_hits + 1

def test_mcp_permissions():
    state = ExecutionState(user_goal="Test permissions")
    state.mcp_session = MCPSessionContext()
    
    # Remove RUN_AUDIT permission
    state.mcp_session.permissions_granted = ["READ_DB", "WRITE_DB"]
    
    # Attempt executing CBAM audit which requires RUN_AUDIT
    args = {"shipment_id": 1, "carbon_price": 80.0}
    with pytest.raises(PermissionError, match="Permission 'RUN_AUDIT' is required"):
        registry.execute_tool("audit_cbam_tariff", args, state)
        
    # Confirm failure logged to session context
    assert len(state.mcp_session.failures) == 1
    assert state.mcp_session.failures[0]["error_type"] == "PermissionError"

def test_mcp_health_metrics():
    state = ExecutionState(user_goal="Test health metrics")
    state.mcp_session = MCPSessionContext()
    
    # Clear metrics
    tool_name = "compute_regional_grid_intensity"
    registry.health_db[tool_name].total_count = 0
    registry.health_db[tool_name].success_count = 0
    
    # Execute tool
    registry.execute_tool(tool_name, {"country_code": "CN"}, state)
    
    health = registry.health_db[tool_name]
    assert health.total_count == 1
    assert health.success_count == 1
    assert health.availability == 1.0
    assert health.error_rate == 0.0
    assert health.avg_latency > 0.0
