import logging
from api.database import engine, Base, SessionLocal
from api.models import Supplier, Product, EmissionFactor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DatabaseInitializer")

def init_database():
    logger.info("Creating database tables if they do not exist...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully.")

    db = SessionLocal()
    try:
        # Seed Suppliers
        if db.query(Supplier).count() == 0:
            logger.info("Seeding initial suppliers...")
            suppliers = [
                Supplier(name="Acme Steel Co.", country="CN", industry="Steel Manufacturing"),
                Supplier(name="Bengal Aluminum Ltd.", country="IN", industry="Aluminum Extrusion"),
                Supplier(name="Euro Metalworks", country="DE", industry="Fabricated Metal Products"),
                Supplier(name="US Alloys Corp", country="US", industry="Specialty Alloys"),
            ]
            db.add_all(suppliers)
            db.commit()
            logger.info("Suppliers seeded.")

        # Seed Products
        if db.query(Product).count() == 0:
            logger.info("Seeding initial products...")
            products = [
                Product(hs_code="720810", description="Flat-rolled products of iron or non-alloy steel, hot-rolled"),
                Product(hs_code="730630", description="Other tubes, pipes and hollow profiles, welded, of circular cross-section, of iron or steel"),
                Product(hs_code="760110", description="Unwrought aluminum, not alloyed"),
                Product(hs_code="760410", description="Aluminum bars, rods and profiles, of non-alloy aluminum"),
            ]
            db.add_all(products)
            db.commit()
            logger.info("Products seeded.")

        # Seed default Emission Factors
        if db.query(EmissionFactor).count() == 0:
            logger.info("Seeding initial emission factors...")
            # Fetch products to link factor rows properly
            p_720810 = db.query(Product).filter_by(hs_code="720810").first()
            p_730630 = db.query(Product).filter_by(hs_code="730630").first()
            p_760110 = db.query(Product).filter_by(hs_code="760110").first()
            p_760410 = db.query(Product).filter_by(hs_code="760410").first()

            factors = [
                # China (CN) has higher average carbon intensities
                EmissionFactor(product_id=p_720810.product_id, country="CN", year=2025, tCO2_per_unit=1.85),
                EmissionFactor(product_id=p_730630.product_id, country="CN", year=2025, tCO2_per_unit=2.10),
                EmissionFactor(product_id=p_760110.product_id, country="CN", year=2025, tCO2_per_unit=16.5),
                EmissionFactor(product_id=p_760410.product_id, country="CN", year=2025, tCO2_per_unit=18.2),

                # India (IN) also high intensity
                EmissionFactor(product_id=p_720810.product_id, country="IN", year=2025, tCO2_per_unit=1.95),
                EmissionFactor(product_id=p_730630.product_id, country="IN", year=2025, tCO2_per_unit=2.25),
                EmissionFactor(product_id=p_760110.product_id, country="IN", year=2025, tCO2_per_unit=18.0),
                EmissionFactor(product_id=p_760410.product_id, country="IN", year=2025, tCO2_per_unit=19.5),

                # Germany (DE) cleaner due to EU power grid
                EmissionFactor(product_id=p_720810.product_id, country="DE", year=2025, tCO2_per_unit=0.75),
                EmissionFactor(product_id=p_730630.product_id, country="DE", year=2025, tCO2_per_unit=0.90),
                EmissionFactor(product_id=p_760110.product_id, country="DE", year=2025, tCO2_per_unit=4.20),
                EmissionFactor(product_id=p_760410.product_id, country="DE", year=2025, tCO2_per_unit=4.80),

                # United States (US)
                EmissionFactor(product_id=p_720810.product_id, country="US", year=2025, tCO2_per_unit=1.10),
                EmissionFactor(product_id=p_730630.product_id, country="US", year=2025, tCO2_per_unit=1.30),
                EmissionFactor(product_id=p_760110.product_id, country="US", year=2025, tCO2_per_unit=7.50),
                EmissionFactor(product_id=p_760410.product_id, country="US", year=2025, tCO2_per_unit=8.20),
            ]
            db.add_all(factors)
            db.commit()
            logger.info("Emission factors seeded.")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
