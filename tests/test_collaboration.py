import pytest
from datetime import datetime
from agents.shared_state import ExecutionState, Task, TaskResult
from agents.planner_agent import PlannerAgent
from agents.engine import ExecutionEngine
from agents.carbon_calc_agent import CarbonCalculationAgent
from agents.compliance_agent import ComplianceAgent
from agents.supplier_agent import SupplierAgent
from agents.optimization_agent import OptimizationAgent
from agents.conversation_agent import ConversationAgent
from agents.collaboration import (
    AgentCommunicationBus, AgentMessageType, AgentRequest, AgentResponse, AgentCritique
)

def test_communication_bus_routing():
    state = ExecutionState(user_goal="Test bus routing")
    agents = {
        "SupplierAgent": SupplierAgent(),
        "CarbonCalculationAgent": CarbonCalculationAgent()
    }
    
    bus = AgentCommunicationBus(state, agents)
    state.bus = bus
    
    # Create request message
    req = AgentRequest(
        sender="CarbonCalculationAgent",
        recipient="SupplierAgent",
        message_type=AgentMessageType.INFORMATION_REQUEST,
        content="Get status of supplier",
        metadata={"supplier_id": 1} # Acme Steel Co. seeded in init_db
    )
    
    resp = bus.send(req)
    
    assert resp is not None
    assert isinstance(resp, AgentResponse)
    assert resp.sender == "SupplierAgent"
    assert resp.recipient == "CarbonCalculationAgent"
    assert "status" in resp.data
    
    # Assert bus logged messages
    assert len(state.agent_conversations) == 2 # request and response
    assert len(state.agent_requests) == 1
    assert len(state.agent_responses) == 1

def test_agent_short_term_memory():
    agent = SupplierAgent()
    
    # Memory is empty initially
    assert len(agent.memory) == 0
    
    # Store some values
    agent.memory["supplier_status_1"] = "Verified"
    agent.memory["latencies"] = [0.1, 0.2]
    
    assert agent.memory["supplier_status_1"] == "Verified"
    assert len(agent.memory["latencies"]) == 2
    
    # Clear memory
    agent.clear_memory()
    assert len(agent.memory) == 0

def test_consensus_generation_and_reputation_updates():
    planner = PlannerAgent()
    agents = {
        "CarbonCalculationAgent": CarbonCalculationAgent(),
        "ComplianceAgent": ComplianceAgent(),
        "SupplierAgent": SupplierAgent(),
        "OptimizationAgent": OptimizationAgent(),
        "ConversationAgent": ConversationAgent()
    }
    
    engine = ExecutionEngine(planner, agents)
    
    state = ExecutionState(user_goal="calculate emissions")
    
    # Execute a simple run which populates some task history
    # For testing, we mock the results in the state directly to trigger consensus and reputation updates
    task_calc = Task(task_id="run_calc", assigned_agent="CarbonCalculationAgent")
    res_calc = TaskResult(
        task_id="run_calc",
        execution_status="COMPLETED",
        output_data={"processed_count": 1, "carbon_results": []},
        confidence=0.85
    )
    state.task_history["run_calc"] = res_calc
    
    # Record reputation update via planner
    planner._update_agent_reputation(state, task_calc, res_calc)
    
    # Verify reputation registry updated
    assert "CarbonCalculationAgent" in state.planner_learning["agent_reputation"]
    rep = state.planner_learning["agent_reputation"]["CarbonCalculationAgent"]
    assert rep["total_runs"] == 1
    assert rep["accuracy"] == 1.0
    
    # Run consensus evaluation directly
    engine._evaluate_agent_consensus(state)
    
    # Verify consensus event recorded
    assert len(state.consensus_events) == 1
    consensus = state.consensus_events[0]
    assert consensus.topic == "Verification of Scope 3 Carbon Emissions Data"
    assert consensus.consensus_score == 0.9  # average of Carbon (0.85) and Supplier (0.95) fallback

def test_negotiation_flow():
    planner = PlannerAgent()
    agents = {
        "CarbonCalculationAgent": CarbonCalculationAgent(),
        "ComplianceAgent": ComplianceAgent()
    }
    engine = ExecutionEngine(planner, agents)
    
    state = ExecutionState(user_goal="calculate emissions")
    state.bus = AgentCommunicationBus(state, agents)
    
    # Mock unaudited emissions and estimated method to trigger compliance audit cycle negotiation
    from api.database import SessionLocal
    from api.models import Emission, Shipment, Supplier, Product, CBAMAudit
    
    db = SessionLocal()
    # 1. Clear database tables
    db.query(CBAMAudit).delete()
    db.query(Emission).delete()
    db.query(Shipment).delete()
    
    # Ensure supplier and product exist
    supplier = db.query(Supplier).first()
    if not supplier:
        supplier = Supplier(name="Test Supplier", country="FR", industry="Steel")
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        
    product = db.query(Product).first()
    if not product:
        product = Product(hs_code="720810", description="Test steel")
        db.add(product)
        db.commit()
        db.refresh(product)
        
    # Create shipment
    shipment = Shipment(
        supplier_id=supplier.supplier_id,
        product_id=product.product_id,
        date=datetime.now().date(),
        quantity=100.0,
        unit="tonnes",
        origin_country="FR",
        dest_country="DE",
        is_processed=True
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    
    # Create emission with FALLBACK_AVERAGE method
    emission = Emission(
        shipment_id=shipment.shipment_id,
        emission_tCO2=100.0,
        method="FALLBACK_AVERAGE"
    )
    db.add(emission)
    db.commit()
    db.refresh(emission)
    db.close()
    
    # Run compliance audit cycle task
    task = Task(task_id="run_audit", assigned_agent="ComplianceAgent", input_data={"action": "run_audit_cycle"})
    result = agents["ComplianceAgent"].execute(state, task)
    
    # Verify negotiation logs and updated confidence
    assert len(state.negotiation_events) == 1
    neg = state.negotiation_events[0]
    assert neg.resolved is True
    assert neg.initial_confidence_a == 0.58
    assert neg.final_confidence_a == 0.85
    assert result.confidence == 0.85
