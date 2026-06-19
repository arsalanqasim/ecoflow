import os
import logging
import json
from dotenv import load_dotenv
from api.database import SessionLocal
from api.models import Shipment, EmissionFactor, Emission, SupplierMetrics, Supplier
# Direct tool import for local computation robustness while maintaining server execution
from fastmcp.data_processing_server import compute_emissions_join

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CarbonAnalysisAgent")

class CarbonAnalysisAgent:
    """
    CarbonAnalysisAgent calculates Scope 3 greenhouse gas emissions.
    It queries unprocessed shipments, calls the FastMCP computation tool,
    saves emission results, and aggregates supplier metrics.
    """
    def __init__(self):
        self.agent_name = "CarbonAnalysisAgent"
        logger.info(f"{self.agent_name} initialized.")

    def run_calculation_cycle(self) -> dict:
        """
        Executes a single processing cycle: queries DB, merges data using FastMCP,
        updates emissions and supplier aggregated cache tables.
        """
        logger.info("Executing carbon calculation cycle...")
        db = SessionLocal()
        
        try:
            # 1. Fetch unprocessed shipments
            unprocessed_shipments = db.query(Shipment).filter_by(is_processed=False).all()
            if not unprocessed_shipments:
                logger.info("No unprocessed shipments found in database.")
                return {"status": "success", "processed_count": 0}

            logger.info(f"Found {len(unprocessed_shipments)} unprocessed shipments.")
            
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

            # 3. Call FastMCP tool (using direct import for pythonic reliability)
            logger.info("Invoking FastMCP data join calculation tool...")
            shipments_json = json.dumps(shipments_data)
            factors_json = json.dumps(factors_data)
            
            results_json = compute_emissions_join(shipments_json, factors_json)
            results = json.loads(results_json)
            
            if isinstance(results, dict) and results.get("status") == "error":
                raise ValueError(f"FastMCP calculation failed: {results.get('message')}")

            # 4. Save results to Database
            logger.info("Writing emission records to database...")
            for res in results:
                shipment_id = res["shipment_id"]
                emission_tCO2 = res["emission_tCO2"]
                method = res["method"]

                # Save Emission record
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

            db.commit()
            logger.info("Emission records committed successfully.")

            # 5. Aggregate Supplier Metrics
            self.recalculate_supplier_metrics(db)
            db.commit()

            return {
                "status": "success",
                "processed_count": len(results)
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error during carbon calculation cycle: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            db.close()

    def recalculate_supplier_metrics(self, db) -> None:
        """
        Aggregates emissions per supplier and determines compliance warning thresholds.
        """
        logger.info("Recalculating supplier metrics cache...")
        
        # Query total emissions per supplier
        suppliers = db.query(Supplier).all()
        
        for supplier in suppliers:
            # Query sum of emissions for shipments belonging to this supplier
            total_co2 = db.query(Emission.emission_tCO2)\
                          .join(Shipment, Emission.shipment_id == Shipment.shipment_id)\
                          .filter(Shipment.supplier_id == supplier.supplier_id)\
                          .all()
            
            sum_co2 = sum([r[0] for r in total_co2]) if total_co2 else 0.0

            # Compliance evaluation
            # < 200 tonnes: COMPLIANT
            # 200 - 1000 tonnes: WARNING
            # > 1000 tonnes: NON_COMPLIANT
            if sum_co2 == 0:
                compliance = "COMPLIANT"
            elif sum_co2 < 200.0:
                compliance = "COMPLIANT"
            elif sum_co2 <= 1000.0:
                compliance = "WARNING"
            else:
                compliance = "NON_COMPLIANT"

            # Check if metrics row already exists
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

        logger.info("Supplier metrics cache updated.")

if __name__ == "__main__":
    agent = CarbonAnalysisAgent()
    result = agent.run_calculation_cycle()
    print("Calculation Cycle Result:", result)
