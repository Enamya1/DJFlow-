# DJFlow Studio — Phase 1

A professional Windows desktop application for DJs to organize, search, and filter their music library.

## Technology Stack

- **Python 3.12+** (developed on 3.13)
- **PySide6** — Qt-based graphical interface
- **SQLite** — persistent local storage (stdlib `sqlite3`)
- **Mutagen** — audio metadata extraction
- **pytest** — automated tests
- **PyInstaller** — future Windows packaging

## Project Structure

```
DJFlowStudio/
├── main.py                      # Application entry point
├── requirements.txt
├── README.md
├── app/
│   ├── ui/
│   │   ├── main_window.py       # Main window + sidebar navigation
│   │   ├── theme.py             # Dark theme stylesheet
│   │   ├── dashboard.py         # Dashboard with real DB statistics
│   │   ├── library_view.py      # Library table + filters + details panel
│   │   ├── library_model.py     # QAbstractTableModel + proxy (search/sort/filter)
│   │   ├── settings_view.py     # Settings screen
│   │   └── placeholder_view.py  # Placeholder for future phases
│   ├── database/
│   │   ├── migrations.py        # Schema, indexes, FKs, connection mgmt
│   │   ├── models.py            # Track / Playlist / ImportResult dataclasses
│   │   └── repository.py        # TrackRepository, PlaylistRepository, SettingsRepository
│   ├── services/
│   │   ├── metadata_service.py  # Mutagen-based metadata + artwork extraction
│   │   └── library_service.py   # Import, scan, duplicate detection, background scanner
│   └── utils/
│       ├── file_utils.py        # Path validation, hashing, format support, duration formatting
│       └── logging_config.py    # Logging setup (console + file)
├── tests/
│   ├── conftest.py
│   ├── test_database.py
│   ├── test_metadata.py
│   ├── test_duplicates.py
│   ├── test_search_filter.py
│   ├── test_favorites_ratings.py
│   └── test_file_handling.py
├── assets/
└── data/                        # Runtime: djflow.db, artwork/, logs/
```

## Setup

```powershell
cd d:\ty_now\DJFlow-
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> If you already have the dependencies installed globally, the `venv` step is optional.

## Run the Application

```powershell
python main.py
```

The application creates a SQLite database at `data/djflow.db` on first launch.

## Run the Tests

```powershell
python -m pytest tests/ -v
```

## Phase 1 Features

### Dashboard
- Real statistics: total tracks, analyzed tracks, playlists, favorites
- Recently imported tracks list
- Favorite tracks list
- Quick actions: import folder, open library, open settings

### Music Import
- Import individual audio files
- Import entire folders (recursive or non-recursive)
- Drag-and-drop files/folders into the library
- Duplicate detection by file path and SHA-256 content hash
- Missing/unreadable file reporting
- Background scanning with progress bar and cancel button
- Supported formats: MP3, WAV, FLAC, AAC/M4A, OGG, AIFF

### Metadata Extraction
Title, artist, album, genre, duration, year, track number, bitrate, sample rate, embedded artwork.
Filename is used as a fallback title when metadata is missing. No metadata is fabricated.

### Library
- Efficient `QAbstractTableModel` (no per-row widgets)
- Columns: Artwork, Title, Artist, Album, Genre, Duration, BPM, Key, Format, Location
- Unknown BPM / musical key displayed as "Unknown"
- Search by title, artist, album, genre
- Sorting by any column (click header)
- Filters: genre, file format, duration range (min/max), favorites only
- Favorites toggle, 0–5 star ratings, custom comma-separated tags
- Track details panel with artwork and full metadata
- Open containing folder
- Remove from library (original file is NOT deleted)
- All changes persist in SQLite

### Settings
- Music library directory selection
- Import files / import folder / rescan library buttons
- Recursive scan toggle

## Reliability
- File path validation and safe handling
- SQLite WAL mode + foreign keys + indexes
- Thread-safe database writes (lock + `check_same_thread=False`)
- Background scanning keeps the UI responsive
- Cancellation of in-progress scans
- Logging to console and `data/logs/djflow.log`

## Packaging (Future)

```powershell
pyinstaller --name "DJFlow Studio" --windowed --onefile main.py
```
