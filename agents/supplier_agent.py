import logging
import time
from typing import List, Optional, Any
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult, SupplierResponse
from api.database import SessionLocal
from api.models import Supplier, SupplierMetrics, Shipment, Emission

logger = logging.getLogger("SupplierAgent")

class SupplierAgent(BaseAgent):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="SupplierAgent",
            description="Provides supplier emissions metrics and resolves supplier data completeness statuses (Verified, Estimated, Missing, Unknown).",
            capabilities=["get_supplier_metrics", "get_top_emitter"],
            required_inputs=[],
            produced_outputs=["supplier_responses", "top_emitting_supplier"],
            estimated_cost=0.01,
            estimated_latency=1.0
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        start_time = time.time()
        logger.info(f"Executing task: {task.task_id} ({task.assigned_agent})")
        db = SessionLocal()
        
        try:
            task_type = task.input_data.get("action")
            
            if task_type == "get_supplier_metrics":
                suppliers = db.query(Supplier).all()
                supplier_responses = []
                
                for supplier in suppliers:
                    metrics = db.query(SupplierMetrics).filter_by(supplier_id=supplier.supplier_id).first()
                    total_co2 = metrics.total_emissions if metrics else 0.0
                    
                    # Query shipments for this supplier to check verification status
                    shipments = db.query(Shipment).filter_by(supplier_id=supplier.supplier_id).all()
                    
                    if not shipments:
                        status = "Missing"
                    else:
                        # Check methods in emission
                        shipment_ids = [s.shipment_id for s in shipments]
                        emissions = db.query(Emission).filter(Emission.shipment_id.in_(shipment_ids)).all()
                        
                        if not emissions:
                            status = "Unknown"
                        else:
                            methods = [e.method for e in emissions]
                            if "FALLBACK_AVERAGE" in methods:
                                status = "Estimated"
                            else:
                                status = "Verified"

                    res = SupplierResponse(
                        supplier_id=supplier.supplier_id,
                        supplier_name=supplier.name,
                        emission_data_status=status,
                        reported_emissions=total_co2 if total_co2 > 0 else None,
                        verification_source="EcoFlow Data Log" if status in ["Verified", "Estimated"] else None
                    )
                    supplier_responses.append(res)
                
                # Append to shared state
                state.supplier_responses.extend(supplier_responses)
                
                has_missing = any(r.emission_data_status in ["Missing", "Unknown"] for r in supplier_responses)
                risks = ["Supplier emissions data missing or unknown, using default averages"] if has_missing else []
                recs = ["Request direct carbon logs from missing suppliers", "Run supplier verification audit"] if has_missing else []
                
                db.close()
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={"supplier_responses": [r.dict() for r in supplier_responses]},
                    execution_time=elapsed,
                    confidence=0.95 if not has_missing else 0.80,
                    risks=risks,
                    recommendations=recs,
                    need_planner_intervention=has_missing
                )

            elif task_type == "get_top_emitter":
                top_metrics = db.query(SupplierMetrics).order_by(SupplierMetrics.total_emissions.desc()).first()
                
                if not top_metrics:
                    db.close()
                    elapsed = time.time() - start_time
                    return TaskResult(
                        task_id=task.task_id,
                        execution_status="COMPLETED",
                        output_data={"top_emitting_supplier": None, "message": "No supplier metrics computed yet."},
                        execution_time=elapsed,
                        confidence=1.0
                    )
                
                supplier = db.query(Supplier).filter_by(supplier_id=top_metrics.supplier_id).first()
                supplier_name = supplier.name if supplier else "Unknown"
                
                db.close()
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={
                        "supplier_id": top_metrics.supplier_id,
                        "supplier_name": supplier_name,
                        "total_emissions": top_metrics.total_emissions,
                        "compliance_status": top_metrics.compliance_status
                    },
                    execution_time=elapsed,
                    confidence=1.0
                )
            else:
                raise ValueError(f"Unsupported action: {task_type}")

        except Exception as e:
            db.rollback()
            db.close()
            logger.error(f"Error executing SupplierAgent: {e}")
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="FAILED",
                error_message=str(e),
                execution_time=elapsed,
                confidence=0.0
            )

    def handle_message(self, state: ExecutionState, message: Any, bus: Any) -> Any:
        from agents.collaboration import AgentResponse, AgentMessageType
        
        if message.message_type in [AgentMessageType.INFORMATION_REQUEST, AgentMessageType.EVIDENCE_REQUEST]:
            supplier_id = message.metadata.get("supplier_id")
            supplier_name = message.metadata.get("supplier_name")
            
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
                    db.close()
                    return AgentResponse(
                        sender="SupplierAgent",
                        recipient=message.sender,
                        message_type=AgentMessageType.RESPONSE,
                        content="Supplier not found.",
                        request_id=message.message_id,
                        data={"status": "Unknown", "confidence": 0.5}
                    )
                    
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
                return AgentResponse(
                    sender="SupplierAgent",
                    recipient=message.sender,
                    message_type=AgentMessageType.RESPONSE,
                    content=f"Supplier {supplier.name} carbon status is {status} (confidence {confidence}).",
                    request_id=message.message_id,
                    data={"supplier_name": supplier.name, "status": status, "confidence": confidence}
                )
            except Exception as e:
                db.close()
                logger.error(f"Error handling message in SupplierAgent: {e}")
                return None
        elif message.message_type == AgentMessageType.VERIFICATION_REQUEST:
            return AgentResponse(
                sender="SupplierAgent",
                recipient=message.sender,
                message_type=AgentMessageType.RESPONSE,
                content="Supplier database contains verified carbon logs for some, but fallback estimates are active for others.",
                request_id=message.message_id
            )
        return None
