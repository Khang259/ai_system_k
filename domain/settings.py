"""
Domain constants — pure Python, no pydantic / env / frameworks.

config/settings.py may override these via composition root when constructing
NodeState (Phase 1 facade / later Runtime start).
"""

# Node must keep detection state long enough before entering ready lists
START_READY_AFTER_SEC = 30
END_READY_AFTER_SEC = 60

# End node có hàng trở lại trong khi đang flag → reset pair sau N giây
END_FLAG_RESET_AFTER_SEC = 30

# get_node_priority fallback khi node_id không có chữ số
PRIORITY_FALLBACK = 999_999
