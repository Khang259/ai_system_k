import logging
from datetime import datetime
import os

def setup_logger(name, log_file, level=logging.DEBUG):
    """Setup logger with file handler."""
    date_str = datetime.now().strftime("%Y%m%d")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    # encoding utf-8: log tiếng Việt có dấu + ký tự → sẽ lỗi trên console cp1252
    handler = logging.FileHandler(f"{log_file}_{date_str}.log", encoding="utf-8")
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    
    return logger