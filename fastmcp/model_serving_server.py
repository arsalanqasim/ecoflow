import logging
import json
from datetime import datetime, timedelta
import numpy as np
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ModelServingServer")

mcp = FastMCP("ModelServing")

@mcp.tool()
def predict_emissions_forecast(historical_emissions_json: str, steps: int = 4) -> str:
    """
    Computes a linear regression model on historical monthly emission aggregates
    and forecasts future carbon footprint values.
    
    Arguments:
    - historical_emissions_json: JSON string of list of historical entries (keys: date, emission_tCO2)
    - steps: Number of future months to forecast (default 4)
    
    Returns:
    - Serialized JSON list of forecasted emission records (keys: date, predicted_emission_tCO2)
    """
    logger.info("Executing emissions forecasting tool.")
    try:
        data = json.loads(historical_emissions_json)
    except Exception as e:
        logger.error(f"Failed to parse input JSON: {e}")
        return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

    if not data or len(data) < 2:
        logger.warning("Insufficient data points for forecasting. Minimum required: 2.")
        return json.dumps({"status": "error", "message": "At least 2 data points are required."})

    # Parse and sort by date
    parsed_data = []
    for entry in data:
        parsed_data.append({
            "date": datetime.strptime(str(entry["date"]), "%Y-%m-%d"),
            "val": float(entry["emission_tCO2"])
        })
    parsed_data.sort(key=lambda x: x["date"])

    # Extract time series steps
    # Convert dates to relative integers (days since start date) to fit regression
    start_date = parsed_data[0]["date"]
    x = np.array([(entry["date"] - start_date).days for entry in parsed_data], dtype=float)
    y = np.array([entry["val"] for entry in parsed_data], dtype=float)

    # Perform simple linear regression: y = slope * x + intercept
    try:
        slope, intercept = np.polyfit(x, y, 1)
        logger.info(f"Fitted model: slope={slope:.4f}, intercept={intercept:.4f}")
    except Exception as e:
        logger.error(f"Linear regression fitting failed: {e}")
        return json.dumps({"status": "error", "message": f"Regression fit failed: {e}"})

    # Project future periods
    # We will assume a monthly stride (30 days) from the last date
    last_date = parsed_data[-1]["date"]
    predictions = []
    
    for i in range(1, steps + 1):
        future_date = last_date + timedelta(days=30 * i)
        future_x = (future_date - start_date).days
        predicted_val = slope * future_x + intercept
        
        # Ensure emissions cannot be negative
        predicted_val = max(0.0, round(float(predicted_val), 4))
        
        predictions.append({
            "date": future_date.strftime("%Y-%m-%d"),
            "predicted_emission_tCO2": predicted_val
        })

    return json.dumps(predictions)

if __name__ == "__main__":
    mcp.run()
