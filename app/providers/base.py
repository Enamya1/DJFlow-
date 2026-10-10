import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    source: str
    track_id: str
    title: str
    artist: str = "Unknown"
    album: Optional[str] = None
    genre: Optional[str] = None
    duration_seconds: Optional[float] = None
    artwork_url: Optional[str] = None
    source_url: Optional[str] = None
    preview_url: Optional[str] = None
    download_url: Optional[str] = None
    download_available: bool = False
    license_name: Optional[str] = None
    license_url: Optional[str] = None
    year: Optional[str] = None
    file_format: Optional[str] = None


class MusicProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> List[SearchResult]:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def credential_error(self) -> Optional[str]:
        ...
