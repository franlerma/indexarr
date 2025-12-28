from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class TorrentResult:
    """Standard torrent result model compatible with Jackett"""
    
    title: str
    guid: str  # Unique torrent ID
    link: str  # Direct download URL for .torrent
    details_url: str  # Details page URL
    indexer: str  # Indexer name
    
    # Optional fields
    size: Optional[int] = None  # Size in bytes
    seeders: Optional[int] = None
    leechers: Optional[int] = None
    publish_date: Optional[datetime] = None
    category: Optional[str] = None
    imdb_id: Optional[str] = None
    
    # TV specific fields
    season: Optional[int] = None
    episode: Optional[int] = None
    
    def to_jackett_format(self) -> dict:
        """Convert result to Jackett/Torznab JSON format"""
        result = {
            "Title": self.title,
            "Guid": self.guid,
            "Link": self.link,
            "Details": self.details_url,
            "Tracker": self.indexer,
        }
        
        if self.size is not None:
            result["Size"] = self.size
        
        if self.seeders is not None:
            result["Seeders"] = self.seeders
            
        if self.leechers is not None:
            result["Peers"] = self.leechers
            
        if self.publish_date:
            result["PublishDate"] = self.publish_date.isoformat()
            
        if self.category:
            # Map Spanish categories to Torznab category IDs
            category_map = {
                'Películas': [2000],  # Movies
                'Movies': [2000],
                'Series': [5000],     # TV
                'Documentales': [7000], # Other
                'Documentaries': [7000]
            }
            result["Category"] = category_map.get(self.category, [8000])  # 8000 = Other
            result["CategoryDesc"] = self.category
            
        if self.imdb_id:
            result["Imdb"] = self.imdb_id
            
        return result
