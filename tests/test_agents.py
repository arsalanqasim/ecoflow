import json
import pytest
import pandas as pd
from api.database import SessionLocal
from api.models import Supplier, Product, Shipment, Emission, SupplierMetrics, EmissionFactor
from agents.data_ingest_agent import DataIngestAgent
from agents.carbon_agent import CarbonAnalysisAgent
from fastmcp.data_processing_server import compute_emissions_join

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_data_ingest_validation():
    agent = DataIngestAgent()
    
    # Valid columns
    valid_df = pd.DataFrame(columns=[
        "shipment_date", "supplier_name", "hs_code", 
        "quantity", "unit", "origin_country", "dest_country"
    ])
    is_valid, msg = agent.validate_csv(valid_df)
    assert is_valid is True
    assert msg == ""

    # Invalid columns
    invalid_df = pd.DataFrame(columns=["shipment_date", "supplier_name"])
    is_valid, msg = agent.validate_csv(invalid_df)
    assert is_valid is False
    assert "Missing required columns" in msg

def test_compute_emissions_join_tool():
    # Setup test inputs
    shipments = [
        {"shipment_id": 999, "product_id": 100, "quantity": 10.0, "origin_country": "CN"}
    ]
    factors = [
        {"product_id": 100, "country": "CN", "tCO2_per_unit": 2.5},
        {"product_id": 100, "country": "US", "tCO2_per_unit": 1.2}
    ]

    shipments_json = json.dumps(shipments)
    factors_json = json.dumps(factors)

    result_json = compute_emissions_join(shipments_json, factors_json)
    result = json.loads(result_json)

    assert len(result) == 1
    assert result[0]["shipment_id"] == 999
    assert result[0]["emission_tCO2"] == 25.0
    assert result[0]["method"] == "DIRECT_FACTOR"

def test_compute_emissions_fallback_tool():
    # Setup test inputs where country is missing and fallback average is applied
    shipments = [
        {"shipment_id": 888, "product_id": 100, "quantity": 10.0, "origin_country": "DE"}
    ]
    factors = [
        {"product_id": 100, "country": "CN", "tCO2_per_unit": 2.0},
        {"product_id": 100, "country": "US", "tCO2_per_unit": 1.0}
    ]

    shipments_json = json.dumps(shipments)
    factors_json = json.dumps(factors)

    result_json = compute_emissions_join(shipments_json, factors_json)
    result = json.loads(result_json)

    assert len(result) == 1
    assert result[0]["shipment_id"] == 888
    # Fallback takes mean of 2.0 and 1.0 -> 1.5
    assert result[0]["emission_tCO2"] == 15.0
    assert result[0]["method"] == "FALLBACK_AVERAGE"

def test_carbon_agent_run_cycle(db_session):
    # Pre-clean leftover records from prior failed runs
    from api.models import CBAMAudit
    db_session.query(SupplierMetrics).filter(SupplierMetrics.supplier.has(name="Test Ingest Supplier")).delete(synchronize_session=False)
    db_session.query(CBAMAudit).filter(CBAMAudit.emission.has(emission_tCO2=25.0)).delete(synchronize_session=False)
    db_session.query(Emission).filter_by(emission_tCO2=25.0).delete()
    db_session.query(Shipment).filter_by(quantity=5.0).delete()
    db_session.query(EmissionFactor).filter_by(tCO2_per_unit=5.0).delete()
    db_session.query(Product).filter_by(hs_code="999999").delete()
    db_session.query(Supplier).filter_by(name="Test Ingest Supplier").delete()
    db_session.commit()

    # 1. Setup a test supplier, product, and factor
    supplier = Supplier(name="Test Ingest Supplier", country="US", industry="Testing")
    db_session.add(supplier)
    db_session.commit()
    
    product = Product(hs_code="999999", description="Test Ingestion Product")
    db_session.add(product)
    db_session.commit()

    factor = EmissionFactor(product_id=product.product_id, country="US", year=2025, tCO2_per_unit=5.0)
    db_session.add(factor)
    db_session.commit()

    # 2. Add an unprocessed shipment
    shipment = Shipment(
        supplier_id=supplier.supplier_id,
        product_id=product.product_id,
        date=pd.Timestamp.now().date(),
        quantity=5.0,
        unit="tonnes",
        origin_country="US",
        dest_country="DE",
        is_processed=False
    )
    db_session.add(shipment)
    db_session.commit()

    # 3. Instantiate CarbonAnalysisAgent and trigger calculation
    agent = CarbonAnalysisAgent()
    result = agent.run_calculation_cycle()

    assert result["status"] == "success"
    assert result["processed_count"] >= 1

    # 4. Verify Emission table contains results
    emission_record = db_session.query(Emission).filter_by(shipment_id=shipment.shipment_id).first()
    assert emission_record is not None
    # 5.0 quantity * 5.0 factor = 25.0 tCO2
    assert emission_record.emission_tCO2 == 25.0
    assert emission_record.method == "DIRECT_FACTOR"

    # 5. Verify Supplier metrics is updated
    metrics = db_session.query(SupplierMetrics).filter_by(supplier_id=supplier.supplier_id).first()
    assert metrics is not None
    assert metrics.total_emissions == 25.0
    assert metrics.compliance_status == "COMPLIANT"

    # Clean up test records to maintain database sanity
    from api.models import CBAMAudit
    db_session.query(CBAMAudit).filter_by(emission_id=emission_record.emission_id).delete()
    db_session.delete(metrics)
    db_session.delete(emission_record)
    db_session.delete(shipment)
    db_session.delete(factor)
    db_session.delete(product)
    db_session.delete(supplier)
    db_session.commit()

def test_cbam_agent_audit_cycle(db_session):
    from agents.cbam_agent import CBAMAuditAgent
    from api.models import CBAMAudit

    # Pre-clean leftover records from prior failed runs
    db_session.query(CBAMAudit).filter(CBAMAudit.emission.has(emission_tCO2=200.0)).delete(synchronize_session=False)
    db_session.query(Emission).filter_by(emission_tCO2=200.0).delete()
    db_session.query(Shipment).filter_by(quantity=100.0).delete()
    db_session.query(Product).filter_by(hs_code="888888").delete()
    db_session.query(Supplier).filter_by(name="Test CBAM Supplier").delete()
    db_session.commit()

    # 1. Setup a test supplier, product, shipment, emission
    supplier = Supplier(name="Test CBAM Supplier", country="CN", industry="Testing")
    db_session.add(supplier)
    db_session.commit()

    product = Product(hs_code="888888", description="Test CBAM Product")
    db_session.add(product)
    db_session.commit()

    shipment = Shipment(
        supplier_id=supplier.supplier_id,
        product_id=product.product_id,
        date=pd.Timestamp.now().date(),
        quantity=100.0,
        unit="tonnes",
        origin_country="CN",
        dest_country="DE",
        is_processed=True
    )
    db_session.add(shipment)
    db_session.commit()

    emission = Emission(
        shipment_id=shipment.shipment_id,
        emission_tCO2=200.0,
        method="DIRECT_FACTOR"
    )
    db_session.add(emission)
    db_session.commit()

    # 2. Run CBAM agent audit cycle
    agent = CBAMAuditAgent()
    result = agent.run_audit_cycle(carbon_price=80.0)

    assert result["status"] == "success"
    assert result["audits_created"] == 1

    # 3. Assert DB record exists and tariff is correct (200.0 tCO2 * 80.0 EUR = 16000.0 EUR)
    audit = db_session.query(CBAMAudit).filter_by(emission_id=emission.emission_id).first()
    assert audit is not None
    assert audit.tariff_due_eur == 16000.0
    assert "SUBJECT TO TARIFF" in audit.compliance_status

    # Cleanup
    db_session.delete(audit)
    db_session.delete(emission)
    db_session.delete(shipment)
    db_session.delete(product)
    db_session.delete(supplier)
    db_session.commit()

def test_api_endpoints():
    from fastapi.testclient import TestClient
    from api.app import app

    client = TestClient(app)

    # Test GET /
    response = client.get("/")
    assert response.status_code == 200
    assert "EcoFlow API is running" in response.json()["message"]

    # Test GET /api/dashboard/summary
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_emissions_tCO2" in data
    assert "cbam_liabilities_eur" in data
    assert "top_emitting_supplier" in data

    # Test POST /api/query
    response = client.post("/api/query", json={
        "user_id": 1,
        "question": "Show top emitting supplier",
        "context": {}
    })
    assert response.status_code == 200
    assert "answer" in response.json()
    assert response.json()["status"] == "success"

