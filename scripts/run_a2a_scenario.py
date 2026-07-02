import os
import sys
import logging
import pandas as pd

# Adjust python path to import api and agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Set SQLite URL
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
    
    # Clear tables
    db.query(CBAMAudit).delete()
    db.query(Emission).delete()
    db.query(SupplierMetrics).delete()
    db.query(Shipment).delete()
    db.query(Product).delete()
    db.query(Supplier).delete()
    db.commit()
    
    # Create A2A Suppliers (Matching names in Agent Cards and DB ID autoincrement sequence)
    supplier_a = Supplier(name="Supplier A Corp", country="FR", industry="Steel Fabrication")
    supplier_b = Supplier(name="Supplier B Corp", country="US", industry="Alloys Manufacturing")
    supplier_c = Supplier(name="Supplier C Corp", country="CN", industry="Ore Refining")
    db.add_all([supplier_a, supplier_b, supplier_c])
    db.commit()
    
    # Retrieve auto IDs
    db.refresh(supplier_a)
    db.refresh(supplier_b)
    db.refresh(supplier_c)
    
    # Create Product
    product = Product(hs_code="720810", description="Flat-rolled steel coils")
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Create three unprocessed shipments
    ship_a = Shipment(
        supplier_id=supplier_a.supplier_id,
        product_id=product.product_id,
        date=pd.Timestamp.now().date(),
        quantity=100.0,
        unit="tonnes",
        origin_country="FR",
        dest_country="DE",
        is_processed=False
    )
    ship_b = Shipment(
        supplier_id=supplier_b.supplier_id,
        product_id=product.product_id,
        date=pd.Timestamp.now().date(),
        quantity=200.0,
        unit="tonnes",
        origin_country="US",
        dest_country="DE",
        is_processed=False
    )
    ship_c = Shipment(
        supplier_id=supplier_c.supplier_id,
        product_id=product.product_id,
        date=pd.Timestamp.now().date(),
        quantity=300.0,
        unit="tonnes",
        origin_country="CN",
        dest_country="DE",
        is_processed=False
    )
    db.add_all([ship_a, ship_b, ship_c])
    db.commit()
    db.close()

def run_a2a_scenario():
    setup_scenario_data()
    
    goal = "calculate emissions for A2A federated suppliers"
    
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
    
    # Formulate A2A Task DAG
    state = planner.plan_goal(goal, agents_metadata)
    
    engine = ExecutionEngine(planner, agents)
    report = engine.run(state)
    
    print("\nDEBUG INFO:")
    print(f"Planned tasks: {[t.task_id for t in state.current_tasks]}")
    print(f"Executed tasks in history: {list(state.task_history.keys())}")
    for tid, res in state.task_history.items():
        print(f"  Task {tid}: Status: {res.execution_status} | Outputs: {list(res.output_data.keys())} | Error: {res.error_message}")
    
    print("\n" + "="*95)
    print("A2A FEDERATED ENTERPRISE SCENARIO TRACE LOGS")
    print("="*95 + "\n")
    
    # 1. Show agent card discoveries
    print("[1] DISCOVERED AGENT CARDS IN A2A DIRECTORY:")
    discover_res = state.task_history.get("discover_cards")
    if discover_res and "discovered_agent_cards" in discover_res.output_data:
        for org, card in discover_res.output_data["discovered_agent_cards"].items():
            print(f"  * Org: '{card['identity']['organization_name']}' | Role: {card['role']}")
            print(f"    - Endpoint Agent ID: {card['identity']['agent_id']} | Version: {card['identity']['version']}")
            print(f"    - Supported Requests: {card['allowed_requests']}")
            print(f"    - Security Policy: Authentication = {card['security_policies']['authentication_type']} | Required Permissions = {card['security_policies']['required_permissions']}")
            print(f"    - Initial Trust Score: {card['trust_metadata']['initial_trust_score']} | certified: {card['trust_metadata']['is_certified']}")
            print("-" * 75)
            
    # 2. Show Session handshakes
    print("\n[2] ACTIVE A2A REMOTE SESSIONS:")
    for org, sess in state.a2a_sessions.items():
        print(f"  * Remote Org: {org}")
        print(f"    - Session ID: {sess.session_id}")
        print(f"    - Authentication State: {sess.auth_state}")
        print(f"    - Permission Grants: {sess.permission_grants}")
        print(f"    - Negotiation State: {sess.negotiation_state}")
        print(f"    - Message Handshake History:")
        for msg in sess.conversation_history:
            print(f"      [{msg.sender} -> {msg.recipient}] {msg.request_type} | Payload: {msg.payload}")
        print("-" * 75)
        
    # 3. Show Dynamic Trust Engine scores
    print("\n[3] DYNAMIC TRUST ENGINE SCORES:")
    for org, score in state.a2a_trust_scores.items():
        print(f"  * Organization: {org} -> Final Trust score: {score:.2f}/1.00")
        
    # 4. Show Cross-Validation & Consensus Reports
    print("\n[4] REMOTE CONSENSUS ENGINE REPORT:")
    consensus_report = state.planner_learning.get("consensus_report") if hasattr(state, "planner_learning") and state.planner_learning else None
    if consensus_report:
        print(f"  * Consensus Agreement Ratio: {consensus_report['consensus_score']*100:.0f}%")
        print(f"  * Audit Findings & Cross-Validations:")
        for cv in consensus_report["cross_validations"]:
            print(f"    - {cv}")
        print(f"  * Final compliance Filing recommendation: {consensus_report['final_recommendation']}")
        print(f"  * Consensus Summary: {consensus_report['summary']}")

    # 5. Final natural language report including trace
    print("\n" + "="*95)
    print("FINAL SUMMARY REPORT DELIVERED TO USER")
    print("="*95)
    conv_result = state.task_history.get("generate_response")
    if conv_result:
        print(conv_result.output_data.get("answer"))
    print("="*95 + "\n")

if __name__ == "__main__":
    run_a2a_scenario()
