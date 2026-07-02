import os
import sys
import logging
import pandas as pd

# Adjust python path to import api and agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ScenarioRunner")

# Set SQLite URL for safety
os.environ["DATABASE_URL"] = "sqlite:///ecoflow.db"

from api.database import SessionLocal, engine, Base
from api.models import Supplier, Product, Shipment, Emission, CBAMAudit, SupplierMetrics, EmissionFactor
from agents.ai_assistant_agent import AIAssistantAgent
from agents.planner_agent import PlannerAgent
from agents.engine import ExecutionEngine
from agents.carbon_calc_agent import CarbonCalculationAgent
from agents.compliance_agent import ComplianceAgent
from agents.optimization_agent import OptimizationAgent
from agents.supplier_agent import SupplierAgent
from agents.conversation_agent import ConversationAgent
from agents.reflection_agent import ReflectionAgent

def setup_scenario_data():
    logger.info("Setting up database scenario data...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 1. Ensure clean slate
    db.query(CBAMAudit).delete()
    db.query(Emission).delete()
    db.query(SupplierMetrics).delete()
    db.query(Shipment).delete()
    
    # 2. Get or create Supplier
    supplier = db.query(Supplier).filter_by(name="Acme Steel Co.").first()
    if not supplier:
        supplier = Supplier(name="Acme Steel Co.", country="CN", industry="Steel Manufacturing")
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        
    # 3. Get or create Product
    product = db.query(Product).filter_by(hs_code="720810").first()
    if not product:
        product = Product(hs_code="720810", description="Flat-rolled steel")
        db.add(product)
        db.commit()
        db.refresh(product)
        
    # 4. Insert an unprocessed shipment from a country without direct factors (e.g. France 'FR')
    # This ensures that calculations fall back to the average, resulting in an "Estimated" status.
    shipment = Shipment(
        supplier_id=supplier.supplier_id,
        product_id=product.product_id,
        date=pd.Timestamp.now().date(),
        quantity=250.0,
        unit="tonnes",
        origin_country="FR",  # No France factor, triggers fallback
        dest_country="DE",
        is_processed=False
    )
    db.add(shipment)
    db.commit()
    logger.info(f"Scenario data loaded. Unprocessed shipment created for {supplier.name} from country {shipment.origin_country}.")
    db.close()

def run_scenario():
    setup_scenario_data()
    
    logger.info("Initializing AIAssistantAgent...")
    assistant = AIAssistantAgent()
    
    # Run the query that triggers carbon calculations, compliance audits, and route optimization
    query = "calculate emissions for unprocessed shipments"
    
    print("\n" + "="*80)
    print(f"RUNNING E2E MULTI-AGENT COLLABORATION SCENARIO")
    print(f"Goal: '{query}'")
    print("="*80 + "\n")
    
    # Instantiate agents directly for custom state tracking printout
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
    
    # 1. Plan
    print("[PLANNING] Planner formulation...")
    state = planner.plan_goal(query, agents_metadata)
    
    # 2. Run Execution Engine
    print("[EXECUTION] Starting Collaborative Execution Engine...")
    engine = ExecutionEngine(planner, agents)
    report = engine.run(state)
    
    # 3. Print the observable multi-agent trace!
    print("\n" + "="*50)
    print("OBSERVABLE AGENT-TO-AGENT MESSAGES & TIMELINE")
    print("="*50)
    
    print(f"\nTimeline Events ({len(state.execution_timeline)}):")
    for event in state.execution_timeline:
        print(f"[{event.timestamp}] {event.agent_name} -> Action: {event.action} | {event.message}")
        
    print(f"\nInter-Agent Communications Bus Messages ({len(state.agent_conversations)}):")
    for msg in state.agent_conversations:
        print(f"[{msg.timestamp}] {msg.sender} -> {msg.recipient} | Type: {msg.message_type.value}")
        print(f"  Content: '{msg.content}'")
        if msg.metadata:
            print(f"  Metadata: {msg.metadata}")
        if hasattr(msg, "data") and msg.data:
            print(f"  Payload Data: {msg.data}")
        print("-" * 40)
        
    print(f"\nNegotiation Events ({len(state.negotiation_events)}):")
    for neg in state.negotiation_events:
        print(f"Negotiation Topic: {neg.topic}")
        print(f"  Participants: {neg.agent_a} (Initial Conf: {neg.initial_confidence_a:.2f}) <-> {neg.agent_b} (Initial Conf: {neg.initial_confidence_b:.2f})")
        print("  Negotiation Dialogue:")
        for log in neg.negotiation_log:
            print(f"    * {log}")
        print(f"  Final Confidence A: {neg.final_confidence_a:.2f}")
        print(f"  Resolved Status: {neg.resolved}")
        print("-" * 40)
        
    print(f"\nConsensus Event:")
    for con in state.consensus_events:
        print(f"Topic: {con.topic}")
        print(f"  Consensus Score: {con.consensus_score * 100:.0f}%")
        print(f"  Supporting Agents: {', '.join(con.supporting_agents)}")
        if con.disagreeing_agents:
            print(f"  Disagreeing Agents: {', '.join(con.disagreeing_agents)}")
        print(f"  Final Recommendation: {con.final_recommendation}")
        print(f"  Evidence: {con.evidence_summary}")
        print("-" * 40)

    print(f"\nAgent Reputation Registry (Maintained by Planner):")
    reputation = state.planner_learning.get("agent_reputation", {})
    for agent, rep in reputation.items():
        print(f"  * Agent: {agent}")
        print(f"    - Accuracy: {rep['accuracy'] * 100:.1f}%")
        print(f"    - Helpfulness: {rep['helpfulness'] * 100:.1f}%")
        print(f"    - Confidence Calibration: {rep['confidence_calibration'] * 100:.1f}%")
        print(f"    - Response Latency: {rep['response_latency']:.3f}s")
        print(f"    - Successful Recommendations: {rep['successful_recommendations']}")
        
    print("\n" + "="*50)
    print("FINAL CONVERSATIONAL SUMMARY DELIVERED TO USER")
    print("="*50)
    
    # Retrieve final output from state
    conv_result = state.task_history.get("generate_response")
    if conv_result:
        print(conv_result.output_data.get("answer"))
    else:
        print("No summary response produced by ConversationAgent.")
        
    print("\n" + "="*80)
    print("SCENARIO COMPLETED SUCCESSFULLY")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_scenario()
