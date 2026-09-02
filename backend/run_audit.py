import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import engine, Base, SessionLocal
from app.db.models import Transaction
from app.simulator.generator import seed_database
from app.engine.baseline_engine import evaluate_naive_baseline_and_recoverx

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    count = db.query(Transaction).count()
    print(f"Database total transaction count: {count}")
    if count == 0:
        print("Seeding 50,000 transactions (seed 42)...")
        seed_database(db, num_transactions=50000, seed=42)
    
    results = evaluate_naive_baseline_and_recoverx(db)
    print("\n=== BASELINE VS RECOVERX COMPARISON RESULTS ===")
    print(json.dumps(results, indent=2))
finally:
    db.close()
