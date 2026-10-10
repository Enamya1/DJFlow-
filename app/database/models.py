from dataclasses import dataclass, field, asdict
from typing import Optional, List


@dataclass
class Track:
    id: Optional[int] = None
    title: str = ""
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    duration_seconds: Optional[float] = None
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    camelot_key: Optional[str] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    file_format: Optional[str] = None
    file_path: str = ""
    file_hash: Optional[str] = None
    artwork_path: Optional[str] = None
    rating: int = 0
    favorite: int = 0
    user_tags: str = ""
    date_added: Optional[str] = None
    date_modified: Optional[str] = None
    last_played: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> "Track":
        if row is None:
            return None
        data = dict(row)
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__})


@dataclass
class Playlist:
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    created_at: Optional[str] = None


@dataclass
class ImportResult:
    imported: int = 0
    skipped_duplicates: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)
    unreadable: List[str] = field(default_factory=list)
