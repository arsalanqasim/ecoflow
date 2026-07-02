import logging
import json
import time
from typing import List, Any
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult, CarbonResult
from api.database import SessionLocal
from api.models import Shipment, EmissionFactor, Emission, SupplierMetrics, Supplier
from fastmcp.data_processing_server import compute_emissions_join
from fastmcp.model_serving_server import predict_emissions_forecast

logger = logging.getLogger("CarbonCalculationAgent")

class CarbonCalculationAgent(BaseAgent):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="CarbonCalculationAgent",
            description="Calculates Scope 3 greenhouse gas emissions, manages emissions records, and computes supplier aggregate metrics.",
            capabilities=["run_calculation_cycle", "get_total_emissions", "get_historical_emissions", "run_forecast"],
            required_inputs=["unprocessed_shipments", "emission_factors"],
            produced_outputs=["carbon_results", "total_emissions_tCO2", "historical_emissions", "forecast_res"],
            estimated_cost=0.01,
            estimated_latency=1.5
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        start_time = time.time()
        logger.info(f"Executing task: {task.task_id} ({task.assigned_agent})")
        db = SessionLocal()
        
        try:
            task_type = task.input_data.get("action")
            
            if task_type == "run_calculation_cycle":
                # Query supplier verification data status via the communication bus before calculation
                if hasattr(state, "bus") and state.bus is not None:
                    from agents.collaboration import AgentRequest, AgentMessageType
                    
                    try:
                        suppliers = db.query(Supplier).all()
                        for supplier in suppliers:
                            req = AgentRequest(
                                sender="CarbonCalculationAgent",
                                recipient="SupplierAgent",
                                message_type=AgentMessageType.INFORMATION_REQUEST,
                                content=f"Verify carbon intensity data for supplier: {supplier.name}",
                                metadata={"supplier_id": supplier.supplier_id, "supplier_name": supplier.name}
                            )
                            resp = state.bus.send(req)
                            if resp and hasattr(resp, "data") and resp.data:
                                status = resp.data.get("status")
                                self.memory[f"supplier_status_{supplier.supplier_id}"] = status
                    except Exception as e:
                        logger.warning(f"Failed to query supplier statuses on bus: {e}")

                # 1. Fetch unprocessed shipments
                unprocessed_shipments = db.query(Shipment).filter_by(is_processed=False).all()
                if not unprocessed_shipments:
                    db.close()
                    elapsed = time.time() - start_time
                    return TaskResult(
                        task_id=task.task_id,
                        execution_status="COMPLETED",
                        output_data={"processed_count": 0, "message": "No unprocessed shipments found."},
                        execution_time=elapsed,
                        confidence=1.0
                    )

                # Serialize shipments
                shipments_data = [
                    {
                        "shipment_id": s.shipment_id,
                        "product_id": s.product_id,
                        "quantity": s.quantity,
                        "origin_country": s.origin_country
                    }
                    for s in unprocessed_shipments
                ]
                
                # 2. Fetch all emission factors
                all_factors = db.query(EmissionFactor).all()
                factors_data = [
                    {
                        "product_id": f.product_id,
                        "country": f.country,
                        "tCO2_per_unit": f.tCO2_per_unit
                    }
                    for f in all_factors
                ]

                # 3. Call FastMCP tool
                shipments_json = json.dumps(shipments_data)
                factors_json = json.dumps(factors_data)
                
                results_json = compute_emissions_join(shipments_json, factors_json)
                results = json.loads(results_json)
                
                if isinstance(results, dict) and results.get("status") == "error":
                    raise ValueError(f"FastMCP calculation failed: {results.get('message')}")

                # 4. Save results to Database & State
                carbon_results = []
                for res in results:
                    shipment_id = res["shipment_id"]
                    emission_tCO2 = res["emission_tCO2"]
                    method = res["method"]

                    # Save DB Emission record
                    emission = Emission(
                        shipment_id=shipment_id,
                        emission_tCO2=emission_tCO2,
                        method=method
                    )
                    db.add(emission)

                    # Mark shipment as processed
                    shipment = db.query(Shipment).filter_by(shipment_id=shipment_id).first()
                    if shipment:
                        shipment.is_processed = True

                    # Create Pydantic CarbonResult
                    supplier_id = shipment.supplier_id if shipment else None
                    status = self.memory.get(f"supplier_status_{supplier_id}", "Verified") if supplier_id else "Verified"
                    
                    res_confidence = 1.0 if method == "DIRECT_FACTOR" else 0.8
                    if status in ["Estimated", "Unknown"]:
                        res_confidence = min(res_confidence, 0.80)
                    elif status == "Missing":
                        res_confidence = min(res_confidence, 0.60)

                    carbon_results.append(
                        CarbonResult(
                            shipment_id=shipment_id,
                            emission_tCO2=emission_tCO2,
                            method=method,
                            confidence=res_confidence
                        )
                    )

                db.commit()

                # 5. Recalculate Supplier Metrics
                self._recalculate_supplier_metrics(db)
                db.commit()

                # Append results to shared state
                state.carbon_results.extend(carbon_results)

                statuses = [self.memory.get(f"supplier_status_{s.supplier_id}", "Verified") for s in unprocessed_shipments]
                task_confidence = 0.95
                if "Missing" in statuses or "Unknown" in statuses:
                    task_confidence = 0.70
                elif "Estimated" in statuses:
                    task_confidence = 0.80

                db.close()
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={
                        "processed_count": len(results),
                        "carbon_results": [r.dict() for r in carbon_results]
                    },
                    execution_time=elapsed,
                    confidence=task_confidence
                )

            elif task_type == "get_total_emissions":
                total_emissions_rows = db.query(Emission.emission_tCO2).all()
                sum_emissions = sum([r[0] for r in total_emissions_rows]) if total_emissions_rows else 0.0
                
                db.close()
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={"total_emissions_tCO2": sum_emissions},
                    execution_time=elapsed,
                    confidence=1.0
                )

            elif task_type == "get_historical_emissions":
                emissions_rows = db.query(
                    Shipment.date, 
                    Emission.emission_tCO2
                ).join(Emission, Shipment.shipment_id == Emission.shipment_id).order_by(Shipment.date).all()
                
                monthly_data = {}
                for row in emissions_rows:
                    month_key = row.date.strftime("%Y-%m-01")
                    monthly_data[month_key] = monthly_data.get(month_key, 0.0) + row.emission_tCO2

                historical_list = [{"date": k, "emission_tCO2": v} for k, v in monthly_data.items()]
                
                db.close()
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={"historical_emissions": historical_list},
                    execution_time=elapsed,
                    confidence=1.0
                )

            elif task_type == "run_forecast":
                # Get historical emissions from previous task result or state
                history = state.task_history
                hist_task = history.get("get_historical_emissions")
                if hist_task and "historical_emissions" in hist_task.output_data:
                    historical_list = hist_task.output_data["historical_emissions"]
                else:
                    # Query directly as fallback
                    emissions_rows = db.query(
                        Shipment.date, 
                        Emission.emission_tCO2
                    ).join(Emission, Shipment.shipment_id == Emission.shipment_id).order_by(Shipment.date).all()
                    
                    monthly_data = {}
                    for row in emissions_rows:
                        month_key = row.date.strftime("%Y-%m-01")
                        monthly_data[month_key] = monthly_data.get(month_key, 0.0) + row.emission_tCO2
                    historical_list = [{"date": k, "emission_tCO2": v} for k, v in monthly_data.items()]

                if len(historical_list) < 2:
                    db.close()
                    elapsed = time.time() - start_time
                    return TaskResult(
                        task_id=task.task_id,
                        execution_status="FAILED",
                        error_message="I don't have enough historical data to generate a forecast yet. Please import more shipments first.",
                        execution_time=elapsed,
                        confidence=0.0
                    )

                forecast_json = predict_emissions_forecast(json.dumps(historical_list), steps=4)
                forecast_res = json.loads(forecast_json)
                
                if isinstance(forecast_res, dict) and forecast_res.get("status") == "error":
                    raise ValueError(f"Forecasting calculation failed: {forecast_res.get('message')}")

                db.close()
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={"forecast_res": forecast_res},
                    execution_time=elapsed,
                    confidence=0.9
                )

            else:
                raise ValueError(f"Unsupported action: {task_type}")

        except Exception as e:
            db.rollback()
            db.close()
            logger.error(f"Error executing CarbonCalculationAgent: {e}")
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="FAILED",
                error_message=str(e),
                execution_time=elapsed,
                confidence=0.0
            )

    def _recalculate_supplier_metrics(self, db) -> None:
        """
        Aggregates emissions per supplier and determines compliance warning thresholds.
        """
        suppliers = db.query(Supplier).all()
        for supplier in suppliers:
            total_co2 = db.query(Emission.emission_tCO2)\
                          .join(Shipment, Emission.shipment_id == Shipment.shipment_id)\
                          .filter(Shipment.supplier_id == supplier.supplier_id)\
                          .all()
            
            sum_co2 = sum([r[0] for r in total_co2]) if total_co2 else 0.0

            # Compliance evaluation thresholds
            if sum_co2 == 0:
                compliance = "COMPLIANT"
            elif sum_co2 < 200.0:
                compliance = "COMPLIANT"
            elif sum_co2 <= 1000.0:
                compliance = "WARNING"
            else:
                compliance = "NON_COMPLIANT"

            metric_row = db.query(SupplierMetrics).filter_by(supplier_id=supplier.supplier_id).first()
            if metric_row:
                metric_row.total_emissions = sum_co2
                metric_row.compliance_status = compliance
            else:
                metric_row = SupplierMetrics(
                    supplier_id=supplier.supplier_id,
                    total_emissions=sum_co2,
                    compliance_status=compliance
                )
                db.add(metric_row)

    def handle_message(self, state: ExecutionState, message: Any, bus: Any) -> Any:
        from agents.collaboration import AgentResponse, AgentMessageType
        
        if message.message_type == AgentMessageType.INFORMATION_REQUEST:
            action = message.metadata.get("action")
            if action == "get_highest_contributors":
                from api.database import SessionLocal
                from api.models import Emission, Shipment, Product
                db = SessionLocal()
                try:
                    top_emissions = db.query(Emission).order_by(Emission.emission_tCO2.desc()).limit(3).all()
                    contributors = []
                    for e in top_emissions:
                        shipment = db.query(Shipment).filter_by(shipment_id=e.shipment_id).first()
                        product = db.query(Product).filter_by(product_id=shipment.product_id).first() if shipment else None
                        contributors.append({
                            "shipment_id": e.shipment_id,
                            "hs_code": product.hs_code if product else "Unknown",
                            "emissions": e.emission_tCO2
                        })
                    db.close()
                    return AgentResponse(
                        sender="CarbonCalculationAgent",
                        recipient=message.sender,
                        message_type=AgentMessageType.RESPONSE,
                        content=f"Highest emissions contributors: " + (", ".join([f"{c['hs_code']}: {c['emissions']} tCO2" for c in contributors])),
                        request_id=message.message_id,
                        data={"contributors": contributors}
                    )
                except Exception as ex:
                    db.close()
                    logger.error(f"Error getting contributors in CarbonCalculationAgent: {ex}")
                    return None
            
            elif action == "get_methodology_explanation":
                return AgentResponse(
                    sender="CarbonCalculationAgent",
                    recipient=message.sender,
                    message_type=AgentMessageType.RESPONSE,
                    content="Scope 3 emissions calculated using product-level HS code emission factors where country matching is available, falling back to global/regional averages where country-specific data is missing.",
                    request_id=message.message_id,
                    data={"method": "DIRECT_FACTOR with FALLBACK_AVERAGE averages"}
                )
        elif message.message_type == AgentMessageType.VERIFICATION_REQUEST:
            return AgentResponse(
                sender="CarbonCalculationAgent",
                recipient=message.sender,
                message_type=AgentMessageType.RESPONSE,
                content="Scope 3 emissions successfully computed. Direct factor calculation has high confidence; fallback averages have moderate confidence.",
                request_id=message.message_id
            )
        return None
