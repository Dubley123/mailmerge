import logging
import sys
import os
import yaml
from dotenv import load_dotenv

# Global configuration
_LOG_CONFIG = {
    "level": logging.INFO,
    "formatter": logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
    "is_disabled": False,
    "initialized": False
}

def load_config():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config.yaml'))
    print(f"Loading logger configuration from: {config_path}")
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

def init_logger():
    """
    Initialize logger configuration from config.yaml file.
    This should be called once at application startup.
    """
    # Reload .env to ensure we have the latest values
    load_dotenv(override=True)
    
    config = load_config()
    log_level_env = config.get("LOG_DETAIL_LEVEL", "HIGH").upper()
    
    if log_level_env == "NONE":
        _LOG_CONFIG["is_disabled"] = True
        _LOG_CONFIG["level"] = logging.CRITICAL + 1
        _LOG_CONFIG["formatter"] = None
    elif log_level_env == "LOW":
        _LOG_CONFIG["is_disabled"] = False
        _LOG_CONFIG["level"] = logging.INFO
        _LOG_CONFIG["formatter"] = logging.Formatter('[%(levelname)s]: %(message)s')
    else: # HIGH or default
        _LOG_CONFIG["is_disabled"] = False
        _LOG_CONFIG["level"] = logging.INFO
        _LOG_CONFIG["formatter"] = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    _LOG_CONFIG["initialized"] = True

def get_logger(name: str):
    """
    Get a configured logger instance.
    Uses the configuration set by init_logger().
    If init_logger() has not been called, it uses default settings (HIGH).
    """
    logger = logging.getLogger(name)
    
    # Only configure if handlers haven't been added yet
    if not logger.handlers:
        if _LOG_CONFIG["is_disabled"]:
            logger.setLevel(logging.CRITICAL + 1)
            logger.addHandler(logging.NullHandler())
            return logger

        logger.setLevel(_LOG_CONFIG["level"])
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(_LOG_CONFIG["level"])
        
        if _LOG_CONFIG["formatter"]:
            handler.setFormatter(_LOG_CONFIG["formatter"])
            
        logger.addHandler(handler)
        
        # Prevent propagation to root logger if it's also configured to avoid double logging
        logger.propagate = False
        
    return logger
