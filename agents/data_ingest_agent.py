import os
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from api.database import SessionLocal
from api.models import Supplier, Product, Shipment

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DataIngestAgent")

class DataIngestAgent:
    """
    DataIngestAgent is responsible for loading raw datasets (CSVs/JSONs),
    sanitizing columns, validating schemas, resolving IDs, and inserting
    raw records into PostgreSQL.
    """
    def __init__(self):
        self.agent_name = "DataIngestAgent"
        logger.info(f"{self.agent_name} initialized.")

    def validate_csv(self, df: pd.DataFrame) -> tuple[bool, str]:
        """
        Validates CSV schema and columns.
        """
        required_cols = [
            "shipment_date", "supplier_name", "hs_code", 
            "quantity", "unit", "origin_country", "dest_country"
        ]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return False, f"Missing required columns: {', '.join(missing_cols)}"
        return True, ""

    def ingest_shipments(self, file_path: str) -> dict:
        """
        Reads shipment records from CSV, resolves foreign keys, and inserts rows into the database.
        """
        logger.info(f"Ingesting shipments from {file_path}")
        
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            return {"status": "error", "records_loaded": 0, "errors": [error_msg]}

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            error_msg = f"Failed to parse CSV file: {e}"
            logger.error(error_msg)
            return {"status": "error", "records_loaded": 0, "errors": [error_msg]}

        # Validate Schema
        is_valid, validation_msg = self.validate_csv(df)
        if not is_valid:
            logger.error(validation_msg)
            return {"status": "error", "records_loaded": 0, "errors": [validation_msg]}

        db = SessionLocal()
        records_loaded = 0
        errors = []

        try:
            # Pre-fetch lookup dictionaries to reduce query overhead
            suppliers_cache = {s.name: s.supplier_id for s in db.query(Supplier).all()}
            products_cache = {p.hs_code: p.product_id for p in db.query(Product).all()}

            for index, row in df.iterrows():
                try:
                    supplier_name = row["supplier_name"]
                    hs_code = str(row["hs_code"]).strip()
                    
                    # Resolve Supplier
                    supplier_id = suppliers_cache.get(supplier_name)
                    if not supplier_id:
                        err = f"Row {index}: Supplier name '{supplier_name}' not registered in database."
                        logger.warning(err)
                        errors.append(err)
                        continue
                        
                    # Resolve Product
                    product_id = products_cache.get(hs_code)
                    if not product_id:
                        err = f"Row {index}: Product HS code '{hs_code}' not registered in database."
                        logger.warning(err)
                        errors.append(err)
                        continue

                    # Parse Date
                    shipment_date = datetime.strptime(str(row["shipment_date"]).strip(), "%Y-%m-%d").date()
                    
                    # Create Shipment Model
                    shipment = Shipment(
                        supplier_id=supplier_id,
                        product_id=product_id,
                        date=shipment_date,
                        quantity=float(row["quantity"]),
                        unit=str(row["unit"]).strip(),
                        origin_country=str(row["origin_country"]).strip(),
                        dest_country=str(row["dest_country"]).strip(),
                        is_processed=False
                    )
                    db.add(shipment)
                    records_loaded += 1

                except ValueError as ve:
                    err = f"Row {index}: Value error parsing fields: {ve}"
                    logger.warning(err)
                    errors.append(err)
                except Exception as ex:
                    err = f"Row {index}: Unexpected error: {ex}"
                    logger.warning(err)
                    errors.append(err)

            db.commit()
            logger.info(f"Ingestion finished. Loaded {records_loaded} records successfully.")
            
            return {
                "status": "success" if records_loaded > 0 else "failed",
                "records_loaded": records_loaded,
                "errors": errors
            }

        except Exception as e:
            db.rollback()
            err_msg = f"Transaction rolled back due to error: {e}"
            logger.error(err_msg)
            return {"status": "error", "records_loaded": 0, "errors": [err_msg]}
        finally:
            db.close()

if __name__ == "__main__":
    agent = DataIngestAgent()
    sample_csv = os.path.join("data", "sample_inputs", "shipments_2025_q1_q2.csv")
    result = agent.ingest_shipments(sample_csv)
    print("Ingestion Result:", result)
