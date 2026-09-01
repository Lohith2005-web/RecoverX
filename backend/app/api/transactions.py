from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import Transaction, Customer, Gateway, Issuer, Merchant

router = APIRouter()

@router.get("/transactions/count")
def get_transaction_counts(db: Session = Depends(get_db)):
    total = db.query(func.count(Transaction.id)).scalar() or 0
    success = db.query(func.count(Transaction.id)).filter(Transaction.status == "SUCCESS").scalar() or 0
    failed = db.query(func.count(Transaction.id)).filter(Transaction.status == "FAILED").scalar() or 0
    recovered = db.query(func.count(Transaction.id)).filter(Transaction.status == "RECOVERED").scalar() or 0
    
    return {
        "total_transactions": total,
        "successful_transactions": success,
        "failed_transactions": failed,
        "recovered_transactions": recovered,
        "failure_rate": round(failed / total if total > 0 else 0.0, 4)
    }

@router.get("/transactions")
def list_transactions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    gateway_id: Optional[str] = None,
    failure_category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Transaction)
    
    if status:
        query = query.filter(Transaction.status == status)
    if gateway_id:
        query = query.filter(Transaction.gateway_id == gateway_id)
    if failure_category:
        query = query.filter(Transaction.failure_category == failure_category)

    total_matching = query.count()
    txns = query.order_by(Transaction.timestamp.desc()).offset(offset).limit(limit).all()

    results = []
    for t in txns:
        results.append({
            "id": t.id,
            "customer_id": t.customer_id,
            "merchant_id": t.merchant_id,
            "gateway_id": t.gateway_id,
            "issuer_id": t.issuer_id,
            "amount": t.amount,
            "currency": t.currency,
            "timestamp": t.timestamp.isoformat(),
            "payment_method": t.payment_method,
            "device_type": t.device_type,
            "failure_code": t.failure_code,
            "failure_category": t.failure_category,
            "retry_count": t.retry_count,
            "customer_historical_success_rate": t.customer_historical_success_rate,
            "subscription_flag": t.subscription_flag,
            "latency_ms": t.latency_ms,
            "risk_score": t.risk_score,
            "status": t.status,
            "recovered_amount": t.recovered_amount,
            "scenario_tag": t.scenario_tag,
            "is_recoverable_ground_truth": t.is_recoverable_ground_truth
        })

    return {
        "total": total_matching,
        "limit": limit,
        "offset": offset,
        "transactions": results
    }

@router.get("/transactions/{transaction_id}")
def get_transaction_detail(transaction_id: str, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")

    customer = db.query(Customer).filter(Customer.id == t.customer_id).first()
    gateway = db.query(Gateway).filter(Gateway.id == t.gateway_id).first()
    issuer = db.query(Issuer).filter(Issuer.id == t.issuer_id).first()
    merchant = db.query(Merchant).filter(Merchant.id == t.merchant_id).first()

    return {
        "id": t.id,
        "amount": t.amount,
        "currency": t.currency,
        "timestamp": t.timestamp.isoformat(),
        "payment_method": t.payment_method,
        "device_type": t.device_type,
        "status": t.status,
        "failure_code": t.failure_code,
        "failure_category": t.failure_category,
        "retry_count": t.retry_count,
        "latency_ms": t.latency_ms,
        "risk_score": t.risk_score,
        "subscription_flag": t.subscription_flag,
        "scenario_tag": t.scenario_tag,
        "is_recoverable_ground_truth": t.is_recoverable_ground_truth,
        "customer": {
            "id": customer.id if customer else t.customer_id,
            "name": customer.name if customer else "Unknown",
            "historical_success_rate": t.customer_historical_success_rate
        },
        "gateway": {
            "id": gateway.id if gateway else t.gateway_id,
            "name": gateway.name if gateway else "Unknown",
            "status": gateway.status if gateway else "HEALTHY"
        },
        "issuer": {
            "id": issuer.id if issuer else t.issuer_id,
            "name": issuer.name if issuer else "Unknown"
        },
        "merchant": {
            "id": merchant.id if merchant else t.merchant_id,
            "name": merchant.name if merchant else "Unknown"
        }
    }
