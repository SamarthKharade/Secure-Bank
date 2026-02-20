import re
from collections import defaultdict


CATEGORY_KEYWORDS = {
    "food": ["zomato", "swiggy", "restaurant", "food", "cafe", "coffee", "pizza", "burger", "hotel", "dining"],
    "transport": ["uber", "ola", "taxi", "fuel", "petrol", "metro", "bus", "train", "rapido", "auto"],
    "shopping": ["amazon", "flipkart", "myntra", "mall", "shop", "store", "market", "meesho"],
    "utilities": ["electricity", "water", "gas", "internet", "broadband", "wifi", "bill", "jio", "airtel"],
    "entertainment": ["netflix", "amazon prime", "hotstar", "movie", "theatre", "spotify", "gaming"],
    "medical": ["pharmacy", "hospital", "clinic", "doctor", "medicine", "health", "apollo", "medplus"],
    "education": ["school", "college", "university", "course", "udemy", "tuition", "book"],
    "transfer": ["transfer", "neft", "imps", "upi", "sent to", "received from"],
    "other": []
}


def classify_transaction(description: str) -> str:
    """Classify a transaction description into a spending category."""
    description_lower = description.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == "other":
            continue
        for keyword in keywords:
            if keyword in description_lower:
                return category

    return "other"


def analyze_spending(transactions: list) -> dict:
    """
    Analyze spending patterns from a list of transactions.
    Returns category-wise breakdown and summary.
    """
    category_totals = defaultdict(float)
    category_counts = defaultdict(int)
    monthly_spending = defaultdict(float)

    debit_transactions = [t for t in transactions if t.get("type") == "debit"]
    total_spent = 0

    for txn in debit_transactions:
        amount = txn.get("amount", 0)
        description = txn.get("description", "")
        timestamp = txn.get("timestamp")

        category = txn.get("category") or classify_transaction(description)

        category_totals[category] += amount
        category_counts[category] += 1
        total_spent += amount

        if timestamp:
            month_key = str(timestamp)[:7]  # YYYY-MM
            monthly_spending[month_key] += amount

    # Build breakdown with percentages
    breakdown = {}
    for category, total in category_totals.items():
        breakdown[category] = {
            "total": round(total, 2),
            "count": category_counts[category],
            "percentage": round((total / total_spent * 100) if total_spent > 0 else 0, 1)
        }

    # Sort by total descending
    sorted_breakdown = dict(sorted(breakdown.items(), key=lambda x: x[1]["total"], reverse=True))

    return {
        "total_spent": round(total_spent, 2),
        "transaction_count": len(debit_transactions),
        "category_breakdown": sorted_breakdown,
        "monthly_trend": dict(sorted(monthly_spending.items())),
        "top_category": max(category_totals, key=category_totals.get) if category_totals else "none"
    }
