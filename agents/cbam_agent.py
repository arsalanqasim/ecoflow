import os
import logging
from dotenv import load_dotenv
from api.database import SessionLocal
from api.models import Emission, Shipment, Product, CBAMAudit
from google import genai
from google.genai.errors import APIError

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CBAMAuditAgent")

class CBAMAuditAgent:
    """
    CBAMAuditAgent audits carbon emissions against EU Carbon Border Adjustment Mechanism (CBAM) rules,
    calculates potential tariff liabilities, and uses Gemini to generate compliance notes.
    """
    def __init__(self):
        self.agent_name = "CBAMAuditAgent"
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        # Initialize Gemini Client if API key is available
        if self.api_key:
            try:
                self.genai_client = genai.Client()
                logger.info(f"{self.agent_name} initialized with Gemini Client.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}. Fallback templates will be used.")
                self.genai_client = None
        else:
            logger.info(f"{self.agent_name} initialized. Using template compliance notes (No GEMINI_API_KEY found).")
            self.genai_client = None

    def generate_compliance_note(self, product_desc: str, origin: str, emissions: float, tariff: float, carbon_price: float) -> str:
        """
        Drafts a natural language audit note summarizing CBAM implications.
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
                logger.warning(f"Gemini API returned error: {api_err}. Falling back to template.")
            except Exception as e:
                logger.warning(f"Failed to call Gemini API: {e}. Falling back to template.")

        # Fallback template
        return (
            f"Import of '{product_desc}' from {origin} has been audited for CBAM compliance. "
            f"With embedded emissions of {emissions:.2f} tCO2, the calculated border adjustment tariff is €{tariff:.2f} "
            f"based on current carbon price of €{carbon_price:.2f}/tCO2. "
            f"Recommendation: Review local decarbonization incentives or clean electricity certificates from the supplier."
        )

    def run_audit_cycle(self, carbon_price: float = 80.0) -> dict:
        """
        Queries calculated emissions, determines CBAM scope and tariff dues,
        generates narratives, and writes audit records to the DB.
        """
        logger.info("Executing CBAM audit cycle...")
        db = SessionLocal()
        audits_created = 0

        try:
            # Fetch emissions that do not have a corresponding audit record
            unaudited_emissions = db.query(Emission).outerjoin(CBAMAudit).filter(CBAMAudit.audit_id == None).all()
            
            if not unaudited_emissions:
                logger.info("No unaudited emissions records found.")
                return {"status": "success", "audits_created": 0}

            logger.info(f"Found {len(unaudited_emissions)} unaudited emissions records.")

            for emission in unaudited_emissions:
                # Retrieve shipment details
                shipment = db.query(Shipment).filter_by(shipment_id=emission.shipment_id).first()
                if not shipment:
                    logger.warning(f"Emission ID {emission.emission_id} references non-existent shipment {emission.shipment_id}.")
                    continue

                # Determine if shipment is in CBAM scope (Non-EU imports)
                origin = shipment.origin_country
                
                # Check if origin is EU (DE is Germany, in our seeder DE is our primary EU importer destination)
                # Any country other than DE (and other EU countries) is subject to CBAM border adjustment.
                if origin == "DE":
                    tariff = 0.0
                    compliance_status = "EXEMPT (EU Origin)"
                    note = "Shipment originates within the European Union and is exempt from Carbon Border Adjustment tariffs."
                else:
                    # Calculate tariff
                    tariff = emission.emission_tCO2 * carbon_price
                    compliance_status = "SUBJECT TO TARIFF"
                    
                    # Fetch product info
                    product = db.query(Product).filter_by(product_id=shipment.product_id).first()
                    product_desc = product.description if product else "Unknown Goods"
                    
                    # Generate audit explanation
                    note = self.generate_compliance_note(
                        product_desc=product_desc,
                        origin=origin,
                        emissions=emission.emission_tCO2,
                        tariff=tariff,
                        carbon_price=carbon_price
                    )

                # Write to CBAMAudit
                audit = CBAMAudit(
                    emission_id=emission.emission_id,
                    tariff_due_eur=tariff,
                    compliance_status=f"[{compliance_status}] {note}"
                )
                db.add(audit)
                audits_created += 1

            db.commit()
            logger.info(f"Audit cycle completed. Saved {audits_created} audits.")
            return {"status": "success", "audits_created": audits_created}

        except Exception as e:
            db.rollback()
            logger.error(f"Error during CBAM audit cycle: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            db.close()

if __name__ == "__main__":
    agent = CBAMAuditAgent()
    result = agent.run_audit_cycle()
    print("Audit Cycle Result:", result)
