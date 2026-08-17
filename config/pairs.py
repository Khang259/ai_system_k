"""
Validate pairs config — extracted from original config.py.
TODO: move to MongoDB collection for dynamic config via UI.
"""

PAIRS_AE_5 = [
    ("start_10000060", "end_10000760"),
    ("start_10000059", "end_10000761"),
    ("start_10001050", "end_10000759"),
    ("start_10001051", "end_10000385"),
    ("start_10001052", "end_10000382"),
    ("start_10001053", "end_10000376"),
    ("start_10001054", "end_10000373"),
    ("start_10001055", "end_10000367"),
    ("start_10001056", "end_10000394"),
    ("start_10001057", "end_10000370"),
    ("start_10000062", "end_10000396"),
    ("start_10002232", "end_10000361"),
    ("start_10002233", "end_10000364"),
    ("start_10001762", "end_10001495"),
    ("start_10001763", "end_10000379"),
    # Xe trống AE5
    ("start_10000391",),
    ("start_10001287",),
    ("start_10001290",),
    ("start_10001293",),
    ("start_10001295",),
    ("start_10001299",),
    ("start_10001384", "end_10000044"),
    ("start_10001384", "end_10000045"),
    ("start_10001384", "end_10000046"),
    ("start_10001384", "end_10000047"),
    ("start_10001385", "end_10000044"),
    ("start_10001385", "end_10000045"),
    ("start_10001385", "end_10000046"),
    ("start_10001385", "end_10000047"),
    ("start_10001386", "end_10000044"),
    ("start_10001386", "end_10000045"),
    ("start_10001386", "end_10000046"),
    ("start_10001386", "end_10000047"),
]

PAIRS_AE_6 = [
    ("start_10000037", "end_10000276"),
    ("start_10000038", "end_10000282"),
    ("start_10000039", "end_10000280"),
    ("start_10000040", "end_10000284"),
    ("start_10000041", "end_10000286"),
    ("start_10000042", "end_10000288"),
    ("start_10000989", "end_10000757"),
    ("start_10000992", "end_10000758"),
    ("start_10000063", "end_10000266"),
    ("start_10000749", "end_10000270"),
    ("start_10000748", "end_10000268"),
    ("start_10000747", "end_10000913"),
    ("start_10000746", "end_10001793"),
    ("start_10000745", "end_10000290"),
    ("start_10000744", "end_10001797"),
    ("start_10000743", "end_10001796"),
]

VALIDATE_PAIRS = PAIRS_AE_5 + PAIRS_AE_6

VALIDATE_PAIRS_BY_ZONE = {
    "AE5": PAIRS_AE_5,
    "AE6": PAIRS_AE_6,
}
