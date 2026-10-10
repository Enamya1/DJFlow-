from app.database.models import Track
from app.database.repository import TrackRepository


def _make_track(title, artist="Unknown", album=None, genre="Electronic",
                duration=180.0, fmt="MP3", path=None):
    return Track(
        title=title, artist=artist, album=album, genre=genre,
        duration_seconds=duration, file_format=fmt,
        file_path=path or f"/music/{title}.{fmt.lower()}",
    )


def test_search_by_title(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Midnight Drive", artist="DJ Alpha"))
    repo.insert(_make_track("Sunset Groove", artist="DJ Beta"))

    results = repo.search(query="midnight")
    assert len(results) == 1
    assert results[0].title == "Midnight Drive"


def test_search_by_artist(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Track A", artist="DJ Alpha"))
    repo.insert(_make_track("Track B", artist="DJ Beta"))

    results = repo.search(query="alpha")
    assert len(results) == 1
    assert results[0].artist == "DJ Alpha"


def test_filter_by_genre(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("A", genre="House"))
    repo.insert(_make_track("B", genre="Techno"))
    repo.insert(_make_track("C", genre="House"))

    results = repo.search(genre="House")
    assert len(results) == 2


def test_filter_by_format(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("A", fmt="MP3"))
    repo.insert(_make_track("B", fmt="FLAC"))

    results = repo.search(file_format="FLAC")
    assert len(results) == 1
    assert results[0].title == "B"


def test_filter_by_duration_range(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Short", duration=60.0))
    repo.insert(_make_track("Medium", duration=200.0))
    repo.insert(_make_track("Long", duration=400.0))

    results = repo.search(min_duration=100.0, max_duration=300.0)
    assert len(results) == 1
    assert results[0].title == "Medium"


def test_sorting_by_title(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Zebra"))
    repo.insert(_make_track("Apple"))
    repo.insert(_make_track("Mango"))

    results = repo.search(sort_by="title", sort_order="ASC")
    titles = [t.title for t in results]
    assert titles == ["Apple", "Mango", "Zebra"]


def test_sorting_descending(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Zebra", duration=100.0))
    repo.insert(_make_track("Apple", duration=300.0))
    repo.insert(_make_track("Mango", duration=200.0))

    results = repo.search(sort_by="duration_seconds", sort_order="DESC")
    titles = [t.title for t in results]
    assert titles == ["Apple", "Mango", "Zebra"]


def test_favorites_filter(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Fav1"))
    repo.insert(_make_track("Normal"))
    repo.set_favorite(1, True)

    results = repo.search(favorite_only=True)
    assert len(results) == 1
    assert results[0].title == "Fav1"
