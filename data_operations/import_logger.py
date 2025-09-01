import logging
import os
from datetime import datetime


class ImportLogger:
    """Logger for data import operations"""
    
    def __init__(self, import_id: str = None):
        self.import_id = import_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.setup_logger()
    
    def setup_logger(self):
        """Setup file logger for import operations"""
        logs_dir = "logs/imports"
        os.makedirs(logs_dir, exist_ok=True)
        
        log_file = f"{logs_dir}/import_{self.import_id}.log"
        
        self.logger = logging.getLogger(f"import_{self.import_id}")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def log_mapping(self, entity_type: str, field: str, original: str, mapped: str):
        """Log field value mapping"""
        self.logger.info(f"🔄 {entity_type} {field} mapped: {original} -> {mapped}")
    
    def log_info(self, message: str):
        """Log general info message"""
        self.logger.info(message)
    
    def log_error(self, message: str):
        """Log error message"""
        self.logger.error(message)


# Global logger instance
_import_logger = None

def get_import_logger(import_id: str = None) -> ImportLogger:
    """Get or create import logger instance"""
    global _import_logger
    if _import_logger is None:
        _import_logger = ImportLogger(import_id)
    return _import_logger