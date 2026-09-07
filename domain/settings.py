"""
Domain constants — pure Python, no pydantic / env / frameworks.

File này CHỈ dùng cho:
- default khi tạo NodeState / hàm domain không truyền kwargs
- unit test domain (không load .env)

KHÔNG dùng để vận hành production. Giá trị runtime = config/settings.py
(+ .env), inject bởi RuntimeService khi construct NodeState.
"""

# Node must keep detection state long enough before entering ready lists
START_READY_AFTER_SEC = 30
END_READY_AFTER_SEC = 60

# End node có hàng trở lại trong khi đang flag → reset pair sau N giây
END_FLAG_RESET_AFTER_SEC = 30

# get_node_priority fallback khi node_id không có chữ số
PRIORITY_FALLBACK = 999_999
