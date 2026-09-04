from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import engine, Base, SessionLocal
from app.db.models import Transaction, Incident
from app.simulator.generator import seed_database
from app.simulator.scenario_engine import inject_gateway_degradation
from app.api import health, transactions, dashboard, simulator, evaluation, recovery, incidents, simulation_api, investigation_api

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    Base.metadata.create_all(bind=engine)
    
    # Check if database is empty; if so, seed 50,000 synthetic transactions deterministically
    db = SessionLocal()
    try:
        count = db.query(Transaction).count()
        if count == 0:
            print("Database is empty. Initializing synthetic 50,000 payment dataset (seed 42)...")
            seed_database(db, num_transactions=settings.DEFAULT_NUM_TRANSACTIONS, seed=settings.SEED)
            print("Injecting canonical Gateway B degradation scenario for demo readiness...")
            inject_gateway_degradation(db, gateway_code="gateway_b")
            print("Canonical demo state initialization complete.")
        else:
            # If DB exists but has 0 active incidents, inject canonical Gateway B scenario
            active_inc_count = db.query(Incident).filter(Incident.status == "ACTIVE").count()
            if active_inc_count == 0:
                print("No active incidents found. Initializing canonical Gateway B degradation scenario...")
                inject_gateway_degradation(db, gateway_code="gateway_b")
    finally:
        db.close()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health.router, prefix=settings.API_V1_STR, tags=["Health"])
app.include_router(transactions.router, prefix=settings.API_V1_STR, tags=["Transactions"])
app.include_router(dashboard.router, prefix=settings.API_V1_STR, tags=["Dashboard"])
app.include_router(simulator.router, prefix=settings.API_V1_STR, tags=["Simulator"])
app.include_router(evaluation.router, prefix=settings.API_V1_STR, tags=["Evaluation"])
app.include_router(recovery.router, prefix=settings.API_V1_STR, tags=["Recovery Engine"])
app.include_router(incidents.router, prefix=settings.API_V1_STR, tags=["Incident Intelligence"])
app.include_router(simulation_api.router, prefix=settings.API_V1_STR, tags=["What-If Simulation"])
app.include_router(investigation_api.router, prefix=settings.API_V1_STR, tags=["AI Investigation Assistant"])





@app.get("/")
def root():
    return {
        "message": "Welcome to RecoverX API",
        "docs": "/docs",
        "version": settings.VERSION
    }
