from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean, Text, func
from sqlalchemy.orm import relationship
from api.database import Base

class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    country = Column(String(2), nullable=False)  # ISO 2-letter country code
    industry = Column(String(100), nullable=True)

    shipments = relationship("Shipment", back_populates="supplier")
    metrics = relationship("SupplierMetrics", uselist=False, back_populates="supplier")

class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    hs_code = Column(String(10), nullable=False, unique=True, index=True)  # Harmonized System tariff code
    description = Column(Text, nullable=True)

    shipments = relationship("Shipment", back_populates="product")
    emission_factors = relationship("EmissionFactor", back_populates="product")

class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    date = Column(Date, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(10), nullable=False)  # e.g., kg, tonnes, pieces
    origin_country = Column(String(2), nullable=False)
    dest_country = Column(String(2), nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)

    supplier = relationship("Supplier", back_populates="shipments")
    product = relationship("Product", back_populates="shipments")
    emission = relationship("Emission", uselist=False, back_populates="shipment")

class EmissionFactor(Base):
    __tablename__ = "emission_factors"

    factor_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    country = Column(String(2), nullable=False)  # ISO code (or 'DEFAULT' / '*' for generic fallback)
    year = Column(Integer, nullable=False)
    tCO2_per_unit = Column(Float, nullable=False)  # Metric tons of CO2 equivalent per unit

    product = relationship("Product", back_populates="emission_factors")

class Emission(Base):
    __tablename__ = "emissions"

    emission_id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.shipment_id"), nullable=False, unique=True)
    emission_tCO2 = Column(Float, nullable=False)
    calculated_at = Column(DateTime, server_default=func.now(), nullable=False)
    method = Column(String(50), nullable=False)  # e.g., 'DIRECT_FACTOR', 'FALLBACK_AVERAGE'

    shipment = relationship("Shipment", back_populates="emission")
    cbam_audit = relationship("CBAMAudit", uselist=False, back_populates="emission")

class SupplierMetrics(Base):
    __tablename__ = "supplier_metrics"

    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), primary_key=True)
    total_emissions = Column(Float, default=0.0, nullable=False)
    last_update = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    compliance_status = Column(String(50), default="UNKNOWN", nullable=False)

    supplier = relationship("Supplier", back_populates="metrics")

class CBAMAudit(Base):
    __tablename__ = "cbam_audits"

    audit_id = Column(Integer, primary_key=True, index=True)
    emission_id = Column(Integer, ForeignKey("emissions.emission_id"), nullable=False, unique=True)
    tariff_due_eur = Column(Float, default=0.0, nullable=False)
    compliance_status = Column(Text, nullable=True)
    audited_at = Column(DateTime, server_default=func.now(), nullable=False)

    emission = relationship("Emission", back_populates="cbam_audit")
