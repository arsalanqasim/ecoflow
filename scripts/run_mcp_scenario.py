import os
import sys
import logging
import pandas as pd

# Adjust python path to import api and agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MCPScenarioRunner")

# Set SQLite URL for safety
os.environ["DATABASE_URL"] = "sqlite:///ecoflow.db"

from api.database import SessionLocal, engine, Base
from api.models import Supplier, Product, Shipment, Emission, CBAMAudit, SupplierMetrics
from agents.planner_agent import PlannerAgent
from agents.engine import ExecutionEngine
from agents.carbon_calc_agent import CarbonCalculationAgent
from agents.compliance_agent import ComplianceAgent
from agents.optimization_agent import OptimizationAgent
from agents.supplier_agent import SupplierAgent
from agents.conversation_agent import ConversationAgent
from agents.reflection_agent import ReflectionAgent

def setup_scenario_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Clean slate
    db.query(CBAMAudit).delete()
    db.query(Emission).delete()
    db.query(SupplierMetrics).delete()
    db.query(Shipment).delete()
    
    # Get or create Supplier
    supplier = db.query(Supplier).filter_by(name="Acme Steel Co.").first()
    if not supplier:
        supplier = Supplier(name="Acme Steel Co.", country="CN", industry="Steel Manufacturing")
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        
    # Get or create Product
    product = db.query(Product).filter_by(hs_code="720810").first()
    if not product:
        product = Product(hs_code="720810", description="Flat-rolled steel")
        db.add(product)
        db.commit()
        db.refresh(product)
        
    # Create unprocessed shipment from France FR (no country factor, triggers fallback)
    shipment = Shipment(
        supplier_id=supplier.supplier_id,
        product_id=product.product_id,
        date=pd.Timestamp.now().date(),
        quantity=250.0,
        unit="tonnes",
        origin_country="FR",  
        dest_country="DE",
        is_processed=False
    )
    db.add(shipment)
    db.commit()
    db.close()

def run_scenario():
    setup_scenario_data()
    
    query = "calculate emissions for unprocessed shipments"
    
    planner = PlannerAgent()
    agents = {
        "CarbonCalculationAgent": CarbonCalculationAgent(),
        "ComplianceAgent": ComplianceAgent(),
        "OptimizationAgent": OptimizationAgent(),
        "SupplierAgent": SupplierAgent(),
        "ConversationAgent": ConversationAgent(),
        "ReflectionAgent": ReflectionAgent()
    }
    
    agents_metadata = [a.metadata.dict() for a in agents.values()]
    
    state = planner.plan_goal(query, agents_metadata)
    
    engine = ExecutionEngine(planner, agents)
    report = engine.run(state)
    
    print("\n" + "="*90)
    print("DEMO: OBSERVABLE AGENT TOOL DISCOVERY & EXECUTION TRACE")
    print("="*90 + "\n")
    
    # Print Discovery Events
    print("[1] TOOL DISCOVERY EVENTS:")
    for ev in state.mcp_discovery_events:
        print(f"  * Agent: {ev['agent_name']}")
        print(f"    - Query: '{ev['query']}'")
        print(f"    - Discovered Candidates: {', '.join(ev['discovered_tools'])}")
        print("-" * 50)
        
    # Print Selection Explainability
    print("\n[2] TOOL SELECTION DECISIONS (EXPLAINABILITY):")
    for dec in state.mcp_selection_decisions:
        print(f"  * Agent: {dec['agent_name']}")
        print(f"    - Selected Tool: `{dec['selected_tool']}`")
        print(f"    - Reasoning Summary: {dec['reasoning']}")
        print("-" * 50)
        
    # Print Fallbacks & Chains
    print("\n[3] MCP TOOL CHAINS:")
    print("  Emissions Calculation Chain: get_supplier_carbon_status -> compute_regional_grid_intensity (Fallback) -> compute_emissions_join")
    for chain in state.mcp_tool_chains:
        print(f"  * Agent: {chain['agent_name']} -> Executed `{chain['tool_name']}`")
        print(f"    - Arguments: {chain['args']}")
        
    # Print Fallbacks
    if state.mcp_fallback_events:
        print("\n[4] MCP FALLBACK EVENTS:")
        for fb in state.mcp_fallback_events:
            print(f"  * Agent: {fb['agent_name']}")
            print(f"    - Condition: {fb['type']} (Supplier {fb['supplier_id']} direct factors missing)")
            print(f"    - Action: Discovered and executed regional grid intensity fallback `{fb['fallback_tool']}` (Intensity: {fb['fallback_value']} tCO2/MWh)")
            
    # Print Validation Logs
    print("\n[5] TOOL OUTPUT VALIDATION STATUSES:")
    for val in state.mcp_validation_events:
        status_str = "SUCCESS" if val.get("is_valid", True) else "FAILURE"
        msg = val.get("message", "Validation successful.")
        print(f"  * Tool: `{val['tool_name']}` -> Validation status: {status_str} | Message: {msg}")

    print("\n" + "="*90)
    print("FINAL SUMMARY REPORT DELIVERED TO USER")
    print("="*90)
    conv_result = state.task_history.get("generate_response")
    if conv_result:
         print(conv_result.output_data.get("answer"))
    print("="*90 + "\n")

if __name__ == "__main__":
    run_scenario()
