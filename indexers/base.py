from abc import ABC, abstractmethod
from typing import List
from models import TorrentResult


class BaseIndexer(ABC):
    """Clase base abstracta para todos los indexers"""
    
    def __init__(self, config: dict):
        """
        Args:
            config: Dictionary with indexer configuration
        """
        self.config = config
        self.domain = config.get('domain')
        self.timeout = config.get('timeout', 30)
        self.enabled = config.get('enabled', True)
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del indexer"""
        pass
    
    @abstractmethod
    def search(self, query: str) -> List[TorrentResult]:
        """
        Busca torrents por query
        
        Args:
            query: Search term
            
        Returns:
            List of TorrentResult
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test indexer connection
        
        Returns:
            True if connection is successful, False otherwise
        """
        pass
