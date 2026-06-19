import logging
import json
import pandas as pd
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DataProcessingServer")

mcp = FastMCP("DataProcessing")

@mcp.tool()
def compute_emissions_join(shipments_json: str, factors_json: str) -> str:
    """
    Performs optimized merge join between shipments and emission factors,
    calculates carbon intensity, and applies fallbacks if specific country factors are missing.
    
    Arguments:
    - shipments_json: JSON string of list of shipments (keys: shipment_id, product_id, quantity, origin_country)
    - factors_json: JSON string of list of emission factors (keys: product_id, country, tCO2_per_unit)
    
    Returns:
    - Serialized JSON list of computed emission objects.
    """
    logger.info("Starting emissions join calculation tool.")
    try:
        shipments_list = json.loads(shipments_json)
        factors_list = json.loads(factors_json)
    except Exception as e:
        logger.error(f"Failed to parse JSON inputs: {e}")
        return json.dumps({"status": "error", "message": f"Invalid JSON inputs: {e}"})

    if not shipments_list:
        logger.info("No shipments provided for calculation.")
        return json.dumps([])

    df_shipments = pd.DataFrame(shipments_list)
    df_factors = pd.DataFrame(factors_list)

    # Standardize column types
    df_shipments["product_id"] = df_shipments["product_id"].astype(int)
    df_shipments["quantity"] = df_shipments["quantity"].astype(float)
    
    if not df_factors.empty:
        df_factors["product_id"] = df_factors["product_id"].astype(int)
        df_factors["tCO2_per_unit"] = df_factors["tCO2_per_unit"].astype(float)

    results = []

    # Calculate average factor per product as fallback
    fallback_factors = {}
    if not df_factors.empty:
        fallback_factors = df_factors.groupby("product_id")["tCO2_per_unit"].mean().to_dict()

    for _, shipment in df_shipments.iterrows():
        shipment_id = int(shipment["shipment_id"])
        product_id = int(shipment["product_id"])
        origin_country = str(shipment["origin_country"]).strip()
        quantity = float(shipment["quantity"])

        # Try exact match (product_id and country)
        factor_row = df_factors[(df_factors["product_id"] == product_id) & (df_factors["country"] == origin_country)] if not df_factors.empty else pd.DataFrame()

        if not factor_row.empty:
            factor = factor_row.iloc[0]["tCO2_per_unit"]
            method = "DIRECT_FACTOR"
        else:
            # Fallback to product average
            factor = fallback_factors.get(product_id, 1.0) # default to 1.0 tCO2/unit if completely missing
            method = "FALLBACK_AVERAGE"
            logger.warning(f"No direct factor found for Product {product_id} from {origin_country}. Used fallback: {factor}")

        emission_tCO2 = quantity * factor
        results.append({
            "shipment_id": shipment_id,
            "emission_tCO2": round(emission_tCO2, 4),
            "method": method
        })

    return json.dumps(results)

if __name__ == "__main__":
    mcp.run()
