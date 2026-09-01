import random
import numpy as np
import pandas as pd
import datetime
from sqlalchemy.orm import Session
from app.db.session import Base
from app.db.models import Merchant, Customer, Gateway, Issuer, Transaction, Incident, SimulationScenario
from app.config import settings

def seed_database(db: Session, num_transactions: int = 50000, seed: int = 42) -> dict:
    """
    Generates a realistic, correlated synthetic payment ecosystem of transactions.
    Uses seed 42 for 100% deterministic reproducibility.
    """
    np.random.seed(seed)
    random.seed(seed)

    # Ensure tables exist on the current connection engine
    Base.metadata.create_all(bind=db.get_bind())

    # 1. Clear existing data
    db.query(Transaction).delete()
    db.query(Incident).delete()
    db.query(Customer).delete()
    db.query(Merchant).delete()
    db.query(Gateway).delete()
    db.query(Issuer).delete()
    db.query(SimulationScenario).delete()
    db.commit()

    # 2. Seed Merchants
    merchants_data = [
        {"id": "mch_01", "name": "OmniStore E-Commerce", "industry": "E-Commerce"},
        {"id": "mch_02", "name": "CloudSaaS Pay", "industry": "SaaS / Subscriptions"},
        {"id": "mch_03", "name": "FinFlex Travel", "industry": "Travel & Ticketing"},
        {"id": "mch_04", "name": "QuickMart Grocery", "industry": "Retail Grocery"}
    ]
    merchants = [Merchant(**m) for m in merchants_data]
    db.add_all(merchants)

    # 3. Seed Gateways
    gateways_data = [
        {"id": "gtw_a", "code": "gateway_a", "name": "Razorpay Prime", "baseline_failure_rate": 0.018, "status": "HEALTHY"},
        {"id": "gtw_b", "code": "gateway_b", "name": "PayU Enterprise", "baseline_failure_rate": 0.022, "status": "HEALTHY"},
        {"id": "gtw_c", "code": "gateway_c", "name": "Cashfree Switch", "baseline_failure_rate": 0.035, "status": "HEALTHY"}
    ]
    gateways = [Gateway(**g) for g in gateways_data]
    db.add_all(gateways)

    # 4. Seed Issuers
    issuers_data = [
        {"id": "isr_hdfc", "code": "hdfc", "name": "HDFC Bank", "baseline_failure_rate": 0.015},
        {"id": "isr_icici", "code": "icici", "name": "ICICI Bank", "baseline_failure_rate": 0.020},
        {"id": "isr_sbi", "code": "sbi", "name": "State Bank of India", "baseline_failure_rate": 0.038},
        {"id": "isr_axis", "code": "axis", "name": "Axis Bank", "baseline_failure_rate": 0.022}
    ]
    issuers = [Issuer(**i) for i in issuers_data]
    db.add_all(issuers)

    # 5. Seed Customers (1,000 unique realistic customers)
    num_customers = 1000
    customers = []
    first_names = ["Aarav", "Ananya", "Rohan", "Priya", "Vikram", "Neha", "Karan", "Sneha", "Aditya", "Meera"]
    last_names = ["Sharma", "Verma", "Patel", "Reddy", "Iyer", "Gupta", "Nair", "Chopra", "Deshmukh", "Joshi"]
    
    for c_idx in range(num_customers):
        c_id = f"cust_{c_idx+1:04d}"
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        # Bimodal historical success rate: most customers are high (0.85-0.98), few are problematic (0.50-0.70)
        hist_rate = round(float(np.random.beta(a=12, b=2)), 4)
        customers.append(Customer(
            id=c_id,
            name=f"{fname} {lname}",
            email=f"{fname.lower()}.{lname.lower()}{c_idx+1}@example.com",
            historical_success_rate=hist_rate,
            country="IN"
        ))
    db.add_all(customers)
    db.commit()

    # 6. Generate Synthetic Transactions
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    start_time = now - datetime.timedelta(days=7)

    # Distribution parameters
    payment_methods = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING"]
    method_probs = [0.45, 0.30, 0.15, 0.10]
    
    gtw_weights = [0.50, 0.35, 0.15] # Gateway A has most volume
    isr_weights = [0.35, 0.30, 0.20, 0.15]
    mch_ids = [m["id"] for m in merchants_data]

    # Pre-generate random timestamps across 7 days
    time_deltas = np.sort(np.random.uniform(0, 7 * 86400, num_transactions))
    
    transactions = []
    
    for idx in range(num_transactions):
        txn_id = f"txn_{idx+1:06d}"
        timestamp = start_time + datetime.timedelta(seconds=float(time_deltas[idx]))
        
        # Pick correlated entities
        customer = customers[idx % num_customers]
        merchant_id = random.choice(mch_ids)
        gateway = gateways[np.random.choice([0, 1, 2], p=gtw_weights)]
        issuer = issuers[np.random.choice([0, 1, 2, 3], p=isr_weights)]
        payment_method = np.random.choice(payment_methods, p=method_probs)
        
        # Amount based on payment method
        if payment_method == "UPI":
            amount = round(float(np.random.gamma(shape=2.5, scale=600)), 2) # avg ~1500
        elif payment_method == "NET_BANKING":
            amount = round(float(np.random.gamma(shape=5.0, scale=3000)), 2) # avg ~15000
        else:
            amount = round(float(np.random.gamma(shape=3.5, scale=1800)), 2) # avg ~6300
        amount = max(amount, 99.0)

        # Device type correlated with payment method
        if payment_method == "UPI":
            device_type = np.random.choice(["MOBILE_ANDROID", "MOBILE_IOS"], p=[0.75, 0.25])
        else:
            device_type = np.random.choice(["DESKTOP", "WEB", "MOBILE_ANDROID", "MOBILE_IOS"], p=[0.40, 0.30, 0.20, 0.10])

        # Latency correlated with gateway and payment method
        base_latency = 180 if gateway.code == "gateway_a" else (220 if gateway.code == "gateway_b" else 280)
        latency_ms = int(np.random.normal(loc=base_latency, scale=40))
        latency_ms = max(latency_ms, 80)

        # Subscription flag (higher for SaaS merchant)
        subscription_flag = (merchant_id == "mch_02") and (random.random() < 0.60)

        # Risk score (0.0 to 1.0)
        risk_score = round(float(np.random.beta(a=1.5, b=25)), 4)

        # Failure probability calculation based on correlated features
        failure_prob = gateway.baseline_failure_rate + issuer.baseline_failure_rate + (1.0 - customer.historical_success_rate) * 0.05
        if payment_method == "NET_BANKING":
            failure_prob += 0.015
        if risk_score > 0.35:
            failure_prob += 0.20

        is_failed = random.random() < failure_prob

        if not is_failed:
            status = "SUCCESS"
            failure_code = "SUCCESS"
            failure_category = "NONE"
            is_recoverable_gt = False
        else:
            status = "FAILED"
            # Failure categorization logic based on correlations
            fail_type_roll = random.random()
            if risk_score > 0.35 or fail_type_roll < 0.10:
                failure_code = "RISK_REJECTED"
                failure_category = "COMPLIANCE_RISK"
                is_recoverable_gt = False
            elif fail_type_roll < 0.50:
                failure_code = "GATEWAY_TIMEOUT"
                failure_category = "TECHNICAL_TIMEOUT"
                # High recoverability if customer has strong history
                is_recoverable_gt = customer.historical_success_rate >= 0.70
            elif fail_type_roll < 0.80:
                failure_code = "INSUFFICIENT_FUNDS"
                failure_category = "USER_ERROR"
                # Recoverable via dynamic delay / customer nudge if customer history is decent
                is_recoverable_gt = customer.historical_success_rate >= 0.80
            else:
                failure_code = "CARD_EXPIRED" if payment_method in ["CREDIT_CARD", "DEBIT_CARD"] else "AUTHENTICATION_FAILED"
                failure_category = "USER_ERROR"
                is_recoverable_gt = customer.historical_success_rate >= 0.75

        transactions.append(Transaction(
            id=txn_id,
            customer_id=customer.id,
            merchant_id=merchant_id,
            gateway_id=gateway.id,
            issuer_id=issuer.id,
            amount=amount,
            currency="INR",
            timestamp=timestamp,
            payment_method=payment_method,
            country="IN",
            device_type=device_type,
            failure_code=failure_code,
            failure_category=failure_category,
            retry_count=0,
            customer_historical_success_rate=customer.historical_success_rate,
            subscription_flag=subscription_flag,
            checkout_session_id=f"sess_{idx+1:06d}",
            latency_ms=latency_ms,
            risk_score=risk_score,
            status=status,
            recovered_amount=0.0,
            scenario_tag="NORMAL",
            is_recoverable_ground_truth=is_recoverable_gt
        ))

    # Bulk insert transactions in batches for maximum speed
    batch_size = 5000
    for i in range(0, len(transactions), batch_size):
        db.add_all(transactions[i:i+batch_size])
        db.commit()

    # 7. Initialize baseline scenario status record
    db.add(SimulationScenario(
        id="scen_gateway_b_deg",
        name="GATEWAY_DEGRADATION",
        target_gateway="gtw_b",
        failure_multiplier=6.5,
        is_active=False
    ))
    db.commit()

    return {
        "status": "success",
        "transactions_generated": len(transactions),
        "customers_generated": len(customers),
        "seed_used": seed
    }
