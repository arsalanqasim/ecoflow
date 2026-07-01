import os
import logging
import time
from typing import List
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult, ComplianceResult
from api.database import SessionLocal
from api.models import Emission, Shipment, Product, CBAMAudit
from google import genai
from google.genai.errors import APIError

logger = logging.getLogger("ComplianceAgent")

class ComplianceAgent(BaseAgent):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            try:
                self.genai_client = genai.Client()
                logger.info("ComplianceAgent initialized with Gemini Client.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client in ComplianceAgent: {e}. Fallback templates will be used.")
                self.genai_client = None
        else:
            logger.info("ComplianceAgent initialized. Using template compliance notes (No GEMINI_API_KEY found).")
            self.genai_client = None

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="ComplianceAgent",
            description="Audits carbon emissions against CBAM / regulatory frameworks and generates compliance reports/audit notes.",
            capabilities=["run_audit_cycle", "get_cbam_liabilities"],
            required_inputs=["carbon_results"],
            produced_outputs=["compliance_results", "cbam_liabilities_eur"],
            estimated_cost=0.02,
            estimated_latency=2.0
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        start_time = time.time()
        logger.info(f"Executing task: {task.task_id} ({task.assigned_agent})")
        db = SessionLocal()
        
        try:
            task_type = task.input_data.get("action")
            
            if task_type == "run_audit_cycle":
                carbon_price = task.input_data.get("carbon_price", 80.0)
                
                # Fetch emissions that do not have a corresponding audit record
                unaudited_emissions = db.query(Emission).outerjoin(CBAMAudit).filter(CBAMAudit.audit_id == None).all()
                
                if not unaudited_emissions:
                    db.close()
                    elapsed = time.time() - start_time
                    return TaskResult(
                        task_id=task.task_id,
                        execution_status="COMPLETED",
                        output_data={"audits_created": 0, "message": "No unaudited emissions records found."},
                        execution_time=elapsed,
                        confidence=1.0
                    )

                compliance_results = []
                for emission in unaudited_emissions:
                    shipment = db.query(Shipment).filter_by(shipment_id=emission.shipment_id).first()
                    if not shipment:
                        logger.warning(f"Emission ID {emission.emission_id} references non-existent shipment {emission.shipment_id}.")
                        continue

                    origin = shipment.origin_country
                    if origin == "DE":
                        tariff = 0.0
                        compliance_status = "EXEMPT (EU Origin)"
                        note = "Shipment originates within the European Union and is exempt from Carbon Border Adjustment tariffs."
                    else:
                        # Calculation of tariff is required for the audit, but the agent's main logic is deciding compliance
                        tariff = emission.emission_tCO2 * carbon_price
                        compliance_status = "SUBJECT TO TARIFF"
                        
                        product = db.query(Product).filter_by(product_id=shipment.product_id).first()
                        product_desc = product.description if product else "Unknown Goods"
                        
                        note = self.generate_compliance_note(
                            product_desc=product_desc,
                            origin=origin,
                            emissions=emission.emission_tCO2,
                            tariff=tariff,
                            carbon_price=carbon_price
                        )

                    audit = CBAMAudit(
                        emission_id=emission.emission_id,
                        tariff_due_eur=tariff,
                        compliance_status=f"[{compliance_status}] {note}"
                    )
                    db.add(audit)
                    
                    compliance_results.append(
                        ComplianceResult(
                            emission_id=emission.emission_id,
                            tariff_due_eur=tariff,
                            compliance_status=compliance_status,
                            audit_note=note
                        )
                    )

                db.commit()
                
                # Update state
                state.compliance_results.extend(compliance_results)
                
                db.close()
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={
                        "audits_created": len(compliance_results),
                        "compliance_results": [r.dict() for r in compliance_results]
                    },
                    execution_time=elapsed,
                    confidence=0.98
                )

            elif task_type == "get_cbam_liabilities":
                total_tariff = db.query(CBAMAudit.tariff_due_eur).all()
                sum_tariff = sum([r[0] for r in total_tariff]) if total_tariff else 0.0
                
                db.close()
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={"cbam_liabilities_eur": sum_tariff},
                    execution_time=elapsed,
                    confidence=1.0
                )
                
            else:
                raise ValueError(f"Unsupported action: {task_type}")

        except Exception as e:
            db.rollback()
            db.close()
            logger.error(f"Error executing ComplianceAgent: {e}")
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="FAILED",
                error_message=str(e),
                execution_time=elapsed,
                confidence=0.0
            )

    def generate_compliance_note(self, product_desc: str, origin: str, emissions: float, tariff: float, carbon_price: float) -> str:
        """
        Drafts a regulatory compliance audit note.
        """
        prompt = (
            f"Write a professional, concise regulatory compliance audit note (max 3 sentences) "
            f"for an import shipment. Product: {product_desc}, Country of Origin: {origin}, "
            f"Embedded Carbon: {emissions:.2f} tCO2, Calculated Tariff: €{tariff:.2f} (at carbon price €{carbon_price:.2f}/tCO2). "
            f"Discuss the tariff liability and recommend next steps."
        )

        if self.genai_client:
            try:
                response = self.genai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                if response.text:
                    return response.text.strip()
            except APIError as api_err:
                logger.warning(f"Gemini API returned error in ComplianceAgent: {api_err}. Falling back to template.")
            except Exception as e:
                logger.warning(f"Failed to call Gemini API in ComplianceAgent: {e}. Falling back to template.")

        # Fallback template
        return (
            f"Import of '{product_desc}' from {origin} has been audited for CBAM compliance. "
            f"With embedded emissions of {emissions:.2f} tCO2, the calculated border adjustment tariff is €{tariff:.2f} "
            f"based on current carbon price of €{carbon_price:.2f}/tCO2. "
            f"Recommendation: Review local decarbonization incentives or clean electricity certificates from the supplier."
        )
