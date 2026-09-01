import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import Transaction, Gateway, Customer, Merchant, Issuer

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_database_initialization(db_session):
    """
    Test creating database tables and basic CRUD operations.
    """
    mch = Merchant(id="mch_test", name="Test Merchant", industry="Testing")
    gtw = Gateway(id="gtw_test", code="gateway_test", name="Test Gateway", baseline_failure_rate=0.02)
    isr = Issuer(id="isr_test", code="test_bank", name="Test Bank", baseline_failure_rate=0.01)
    cust = Customer(id="cust_test", name="Test Customer", email="test@example.com", historical_success_rate=0.90)

    db_session.add_all([mch, gtw, isr, cust])
    db_session.commit()

    assert db_session.query(Merchant).count() == 1
    assert db_session.query(Gateway).count() == 1
    assert db_session.query(Issuer).count() == 1
    assert db_session.query(Customer).count() == 1
