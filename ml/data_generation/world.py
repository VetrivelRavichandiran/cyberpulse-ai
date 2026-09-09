"""CYBERPULSE AI — synthetic world definition.

Defines the fictional geographic region, banks, ATMs, accounts and the
controlled fraud-ring patterns that give the dataset learnable signal.

All identifiers are synthetic. No real persons, banks or institutions are
represented. Coordinates are real-world-format (WGS84) but the entities,
transactions and complaints are entirely generated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# ── Region: a compact 6-district area (Karnataka-style, synthetic entities) ─
DISTRICTS = [
    # name,            center_lat, center_lon, spread_deg
    ("Bengaluru Urban",   12.9716,  77.5946,  0.055),
    ("Bengaluru Rural",   13.0919,  77.5547,  0.050),
    ("Mandya",            12.6390,  76.9930,  0.055),
    ("Ramanagara",        13.3333,  77.4500,  0.045),
    ("Chikkaballapura",   13.0097,  77.7172,  0.050),
    ("Mysuru",            12.3052,  76.6552,  0.050),
]
STATE = "Karnataka"

BANKS = [
    ("B001", "State Bank of India"),
    ("B002", "HDFC Bank"),
    ("B003", "ICICI Bank"),
    ("B004", "Punjab National Bank"),
    ("B005", "Bank of Baroda"),
    ("B006", "Axis Bank"),
    ("B007", "Kotak Mahindra Bank"),
    ("B008", "Canara Bank"),
]

CRIME_CATEGORIES = [
    ("UPI_FRAUD", 0.34),
    ("BANKING_FRAUD", 0.18),
    ("PHISHING", 0.14),
    ("SOCIAL_ENGINEERING", 0.12),
    ("INVESTMENT_SCAM", 0.10),
    ("ROMANCE_SCAM", 0.06),
    ("SIM_SWAP", 0.04),
    ("CASH_ON_DELIVERY_FRAUD", 0.02),
]

TX_TYPES = ["ATM_WITHDRAWAL", "UPI_TRANSFER", "NEFT", "IMPS", "CARD_PAYMENT"]


@dataclass(frozen=True)
class District:
    name: str
    lat: float
    lon: float
    spread: float

    def point(self, rng) -> tuple[float, float]:
        """Random point inside the district (Gaussian blob)."""
        lat = self.lat + rng.normal(0, self.spread * 0.6)
        lon = self.lon + rng.normal(0, self.spread * 0.6)
        return round(lat, 6), round(lon, 6)


@dataclass
class FraudRing:
    """A controlled fraud pattern with learnable structure.

    Lifecycle (the signal the model must learn):
      1. Complaint surge in `complaint_district` (victims report).
      2. UPI inflow into mule accounts (funds aggregation).
      3. Small recon withdrawals at target ATMs (ATM testing).
      4. Structured cash-out burst at target ATMs in `cashout_district`.

    `active_days` = (start_day, end_day) relative to the dataset origin.
    """
    ring_id: str
    complaint_district: str
    cashout_district: str
    mule_accounts: list[str]
    target_atms: list[str]
    active_days: tuple[int, int]
    peak_hours: tuple[int, int]
    cross_district: bool
    emerging: bool = False
    scale: float = 1.0


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_districts() -> list[District]:
    return [District(*d) for d in DISTRICTS]