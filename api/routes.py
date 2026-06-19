import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from api.schemas import QueryRequest, QueryResponse, DashboardSummaryResponse
from api.database import SessionLocal
from api.models import Emission, CBAMAudit, SupplierMetrics, Supplier
from agents.ai_assistant_agent import AIAssistantAgent
from agents.data_ingest_agent import DataIngestAgent
from agents.carbon_agent import CarbonAnalysisAgent
from agents.cbam_agent import CBAMAuditAgent as RegulatoryAuditAgent

router = APIRouter()

# Instantiate agents
assistant = AIAssistantAgent()
ingestor = DataIngestAgent()
carbon_analyst = CarbonAnalysisAgent()
cbam_auditor = RegulatoryAuditAgent()

@router.post("/query", response_model=QueryResponse)
async def query_agent(payload: QueryRequest):
    """
    Accepts natural language user questions and routes them to the AI Assistant Agent.
    """
    try:
        res = assistant.process_query(payload.question, conversation_id=str(payload.user_id))
        return QueryResponse(
            answer=res["answer"],
            charts=res["charts"],
            status=res["status"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent routing failed: {e}")

@router.post("/data/upload")
async def upload_shipments(file: UploadFile = File(...)):
    """
    Uploads a shipment CSV, triggers the ingestion agent, and automatically
    runs the downstream carbon calculation and regulatory audit cycles.
    """
    # Create temp directory
    temp_dir = "data/temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write uploaded file: {e}")

    try:
        # 1. Ingest Data
        ingest_result = ingestor.ingest_shipments(temp_path)
        if ingest_result["status"] == "error":
            raise ValueError(f"Ingestion agent failed: {ingest_result['errors']}")

        records_loaded = ingest_result["records_loaded"]

        # 2. Run Carbon calculation cycle (if records loaded)
        if records_loaded > 0:
            calc_result = carbon_analyst.run_calculation_cycle()
            if calc_result["status"] == "error":
                raise ValueError(f"Carbon analysis agent failed: {calc_result.get('message')}")

            # 3. Run CBAM audit cycle
            audit_result = cbam_auditor.run_audit_cycle()
            if audit_result["status"] == "error":
                raise ValueError(f"CBAM audit agent failed: {audit_result.get('message')}")

        return {
            "status": "success",
            "filename": file.filename,
            "records_loaded": records_loaded,
            "message": f"Successfully ingested {records_loaded} shipments, recalculated emissions, and updated CBAM audits."
        }

    except Exception as ex:
        return {
            "status": "error",
            "filename": file.filename,
            "records_loaded": 0,
            "message": str(ex)
        }
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary():
    """
    Queries database aggregates to serve live summary metrics to the dashboard cards.
    """
    db = SessionLocal()
    try:
        # Total emissions
        emissions_total = db.query(Emission.emission_tCO2).all()
        sum_emissions = sum([r[0] for r in emissions_total]) if emissions_total else 0.0

        # Total CBAM liabilities
        tariff_total = db.query(CBAMAudit.tariff_due_eur).all()
        sum_tariff = sum([r[0] for r in tariff_total]) if tariff_total else 0.0

        # Top emitting supplier
        top_metrics = db.query(SupplierMetrics).order_by(SupplierMetrics.total_emissions.desc()).first()
        top_supplier_name = "None"
        if top_metrics:
            supplier = db.query(Supplier).filter_by(supplier_id=top_metrics.supplier_id).first()
            if supplier:
                top_supplier_name = f"{supplier.name} ({top_metrics.total_emissions:.2f} tCO2)"

        # Compliance ratio
        total_suppliers = db.query(SupplierMetrics).count()
        compliant_suppliers = db.query(SupplierMetrics).filter_by(compliance_status="COMPLIANT").count()
        
        compliant_ratio = 1.0
        if total_suppliers > 0:
            compliant_ratio = compliant_suppliers / total_suppliers

        return DashboardSummaryResponse(
            total_emissions_tCO2=round(sum_emissions, 2),
            cbam_liabilities_eur=round(sum_tariff, 2),
            top_emitting_supplier=top_supplier_name,
            compliant_ratio=round(compliant_ratio, 4)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation failed: {e}")
    finally:
        db.close()
