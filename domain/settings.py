"""
Domain constants — pure Python, no pydantic / env / frameworks.

File này CHỈ dùng cho:
- default khi tạo NodeState / hàm domain không truyền kwargs
- unit test domain (không load .env)

KHÔNG dùng để vận hành production. Giá trị runtime = config/settings.py
(+ .env), inject bởi RuntimeService khi construct NodeState.
"""

# Node must keep detection state long enough before entering ready lists
START_READY_AFTER_SEC = 10
END_READY_AFTER_SEC = 10

# start_sort_key fallback khi Mongo thiếu / invalid priority
PRIORITY_FALLBACK = 999_999
