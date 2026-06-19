import os
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from api.database import SessionLocal
from api.models import Shipment, Emission, CBAMAudit, SupplierMetrics, Supplier
from fastmcp.model_serving_server import predict_emissions_forecast

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIAssistantAgent")

class AIAssistantAgent:
    """
    AIAssistantAgent acts as the primary orchestrator, interfacing with the user query pipeline.
    It resolves DB queries and calls downstream agents or FastMCP tools based on keywords/intents.
    """
    def __init__(self):
        self.agent_name = "AIAssistantAgent"
        logger.info(f"{self.agent_name} initialized.")

    def process_query(self, query: str, conversation_id: str = "default") -> dict:
        """
        Parses natural language queries and executes database searches or calls prediction tools.
        """
        logger.info(f"Processing query: '{query}' in conversation: {conversation_id}")
        query_lower = query.lower()
        db = SessionLocal()

        try:
            # Intent 1: Forecasting future carbon emissions
            if "forecast" in query_lower or "predict" in query_lower or "future" in query_lower:
                # Query historical emissions grouped by month/date
                emissions_rows = db.query(
                    Shipment.date, 
                    Emission.emission_tCO2
                ).join(Emission, Shipment.shipment_id == Emission.shipment_id).order_by(Shipment.date).all()
                
                if len(emissions_rows) < 2:
                    return {
                        "answer": "I don't have enough historical data to generate a forecast yet. Please import more shipments first.",
                        "charts": [],
                        "status": "success"
                    }

                # Group by month for forecasting input
                monthly_data = {}
                for row in emissions_rows:
                    month_key = row.date.strftime("%Y-%m-01")
                    monthly_data[month_key] = monthly_data.get(month_key, 0.0) + row.emission_tCO2

                historical_list = [{"date": k, "emission_tCO2": v} for k, v in monthly_data.items()]
                
                # Call forecasting tool
                forecast_json = predict_emissions_forecast(json.dumps(historical_list), steps=4)
                forecast_res = json.loads(forecast_json)
                
                if isinstance(forecast_res, dict) and forecast_res.get("status") == "error":
                    return {
                        "answer": f"Forecasting calculation failed: {forecast_res.get('message')}",
                        "charts": [],
                        "status": "error"
                    }

                # Format answer
                answer = "Here is the Scope 3 emissions forecast for the next 4 months based on historical shipment logs:\n"
                for entry in forecast_res:
                    answer += f"- **{entry['date']}**: {entry['predicted_emission_tCO2']:.2f} tCO2\n"

                chart_data = {
                    "type": "forecast",
                    "data": forecast_res
                }

                return {
                    "answer": answer,
                    "charts": [chart_data],
                    "status": "success"
                }

            # Intent 2: Top Emitting Supplier
            elif "top emitter" in query_lower or "highest emissions" in query_lower or "top supplier" in query_lower:
                top_metrics = db.query(SupplierMetrics).order_by(SupplierMetrics.total_emissions.desc()).first()
                if not top_metrics:
                    return {
                        "answer": "No supplier emissions calculations have been computed yet.",
                        "charts": [],
                        "status": "success"
                    }
                
                supplier = db.query(Supplier).filter_by(supplier_id=top_metrics.supplier_id).first()
                supplier_name = supplier.name if supplier else "Unknown"

                return {
                    "answer": (
                        f"The supplier with the highest Scope 3 carbon footprint is **{supplier_name}** "
                        f"with a total of **{top_metrics.total_emissions:.2f} tCO2** emitted. "
                        f"Current compliance status: **{top_metrics.compliance_status}**."
                    ),
                    "charts": [],
                    "status": "success"
                }

            # Intent 3: Total CBAM liabilities
            elif "cbam" in query_lower or "tariff" in query_lower or "duty" in query_lower or "liabilities" in query_lower:
                total_tariff = db.query(CBAMAudit.tariff_due_eur).all()
                sum_tariff = sum([r[0] for r in total_tariff]) if total_tariff else 0.0

                return {
                    "answer": (
                        f"The total audited border adjustment (CBAM) tariff liability for imported shipments is "
                        f"**€{sum_tariff:,.2f}**. This matches current EU import tariff carbon pricing constraints."
                    ),
                    "charts": [],
                    "status": "success"
                }

            # Intent 4: Standard default summary query
            else:
                total_emissions = db.query(Emission.emission_tCO2).all()
                sum_emissions = sum([r[0] for r in total_emissions]) if total_emissions else 0.0
                
                return {
                    "answer": (
                        f"Welcome! I am your EcoFlow sustainability assistant. "
                        f"Currently, we are tracking a total of **{sum_emissions:.2f} tCO2** of Scope 3 emissions "
                        f"across your supply chain network. Ask me about 'forecasting future emissions', "
                        f"'highest emitting supplier', or 'total CBAM liabilities' for deeper audit details!"
                    ),
                    "charts": [],
                    "status": "success"
                }

        except Exception as e:
            logger.error(f"Error handling query: {e}")
            return {
                "answer": "An error occurred while retrieving carbon metrics.",
                "charts": [],
                "status": "error"
            }
        finally:
            db.close()

if __name__ == "__main__":
    agent = AIAssistantAgent()
    print("Forecasting Query:", agent.process_query("forecast emissions"))
    print("Top Emitter Query:", agent.process_query("highest emissions"))
