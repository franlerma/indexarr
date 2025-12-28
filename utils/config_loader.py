import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = 'config.yaml') -> Dict[str, Any]:
    """
    Load configuration from a YAML file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dictionary with configuration
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def get_enabled_indexers(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Get enabled indexers from configuration
    
    Args:
        config: Complete configuration dictionary
        
    Returns:
        Dictionary with enabled indexers
    """
    indexers = config.get('indexers', {})
    enabled = {}
    
    for name, indexer_config in indexers.items():
        if indexer_config.get('enabled', False):
            enabled[name] = indexer_config
    
    return enabled
