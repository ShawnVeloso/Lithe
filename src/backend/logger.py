import logging
import os
import re
from logging.handlers import RotatingFileHandler

from src.backend.config import LOGS_DIR

class SecretsMasker(logging.Formatter):
    """Formatter that masks sensitive environment variables like API keys."""
    
    def __init__(self, fmt=None, datefmt=None, style='%', validate=True):
        super().__init__(fmt, datefmt, style, validate)
        # Attempt to load actual key if present, otherwise just mask anything that looks like a gemini key
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.mask = "********"

    def format(self, record):
        message = super().format(record)
        
        # Mask the exact key if known
        if self.api_key and self.api_key in message:
            message = message.replace(self.api_key, self.mask)
            
        # Also broadly mask "GEMINI_API_KEY=..." or similar patterns
        message = re.sub(r'(GEMINI_API_KEY\s*[=:]\s*[\'"]?)[^\s\'"]+([\'"]?)', r'\g<1>' + self.mask + r'\g<2>', message)
        return message


def setup_logger(name: str) -> logging.Logger:
    """Configures and returns a logger that writes to both console and rotating file."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # File handler
        log_file = LOGS_DIR / "backend.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        formatter = SecretsMasker(fmt=fmt)
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

# Create a root-level default logger
logger = setup_logger("lithe.backend")
