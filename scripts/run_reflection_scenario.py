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
from agents.certification_agent import CertificationAgent
from agents.transport_agent import TransportAgent

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
    
    # Create A2A Suppliers
    supplier_a = Supplier(name="Supplier A Corp", country="FR", industry="Steel Fabrication")
    supplier_b = Supplier(name="Supplier B Corp", country="DE", industry="Alloys Manufacturing")
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
        origin_country="DE",
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

def run_reflection_scenario():
    setup_scenario_data()
    
    goal = "calculate emissions for A2A federated suppliers"
    
    planner = PlannerAgent()
    agents = {
        "CarbonCalculationAgent": CarbonCalculationAgent(),
        "ComplianceAgent": ComplianceAgent(),
        "OptimizationAgent": OptimizationAgent(),
        "SupplierAgent": SupplierAgent(),
        "ConversationAgent": ConversationAgent(),
        "ReflectionAgent": ReflectionAgent(),
        "CertificationAgent": CertificationAgent(),
        "TransportAgent": TransportAgent()
    }
    
    agents_metadata = [a.metadata.model_dump() for a in agents.values()]
    
    # Formulate initial Task DAG
    state = planner.plan_goal(goal, agents_metadata)
    
    engine = ExecutionEngine(planner, agents)
    report = engine.run(state)
    
    print("\n" + "="*95)
    print("SELF-REFLECTING AUTONOMOUS AI SYSTEM - RUN TIMELINE")
    print("="*95 + "\n")
    
    # 1. Timeline steps
    print("[1] EXECUTION TIMELINE EVENTS:")
    for evt in state.execution_timeline:
        print(f"  * [{evt.timestamp}] Agent: {evt.agent_name} -> Action: {evt.action}")
        print(f"    - Message: {evt.message}")
        print("-" * 75)
        
    # 2. Quality Score Dashboard
    print("\n[2] QUALITY SCORE DASHBOARD:")
    if state.quality_scores:
        for name, score in state.quality_scores.items():
            print(f"  * {name}: {score:.2f}/1.00")
    print("-" * 75)
            
    # 3. Reflection Timeline
    print("\n[3] SELF-REFLECTION & CORRECTION TIMELINE:")
    for i, evt in enumerate(state.reflection_events, 1):
        print(f"  * event {i}: Stage = {evt['stage']}")
        if evt.get("detected_failure"):
            print(f"    - Failure Classification: {evt['detected_failure']} (Severity: {evt['severity']})")
            print(f"    - Root Cause Analysis: {evt['root_cause']}")
        if evt.get("confidence_change"):
            bef = evt["confidence_change"]["before"]
            aft = evt["confidence_change"]["after"]
            if bef != aft:
                print(f"    - Confidence Recalibration: {bef*100:.0f}% -> {aft*100:.0f}% (Goal updated)")
        if evt.get("recovery_action"):
            print(f"    - Recovery Recommendation: {evt['recovery_action']}")
        print(f"    - Summary: {evt['summary']}")
        print("-" * 75)
        
    # 4. Final summary report delivered to user
    print("\n" + "="*95)
    print("FINAL SUMMARY REPORT DELIVERED TO USER")
    print("="*95)
    conv_result = state.task_history.get("generate_response")
    if conv_result:
        print(conv_result.output_data.get("answer"))
    print("="*95 + "\n")

if __name__ == "__main__":
    run_reflection_scenario()
