"""
Character backgrounds.

Flavor text only — no mechanical weight (contrast with races.py, where
each entry carries a stat-modifier dict). Kept as a flat list rather than
a dict since there's no per-entry data to attach yet; if that changes
later (e.g. starting items), this can grow into a dict like races.py
without touching any calling code beyond an iteration change.
"""

BACKGROUNDS = [
    "Soldier",
    "Scholar",
    "Criminal",
    "Noble",
    "Artisan",
    "Sailor",
    "Wanderer",
    "Outlander",
    "Acolyte",
    "Entertainer",
    "Farmer",
    "Merchant",
]