from app.database.models import Track
from app.database.repository import TrackRepository


def _make_track(title, path=None):
    return Track(
        title=title, artist="Artist", genre="House", duration_seconds=200.0,
        file_format="MP3", file_path=path or f"/music/{title}.mp3",
    )


def test_set_favorite_persists(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Track1"))
    repo.set_favorite(1, True)

    t = repo.get_by_id(1)
    assert t.favorite == 1
    assert repo.count_favorites() == 1


def test_unset_favorite(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Track1"))
    repo.set_favorite(1, True)
    repo.set_favorite(1, False)

    assert repo.get_by_id(1).favorite == 0
    assert repo.count_favorites() == 0


def test_set_rating_persists(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Track1"))
    repo.set_rating(1, 4)

    assert repo.get_by_id(1).rating == 4


def test_rating_clamped_to_valid_range(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Track1"))
    repo.set_rating(1, 10)
    assert repo.get_by_id(1).rating == 5
    repo.set_rating(1, -3)
    assert repo.get_by_id(1).rating == 0


def test_custom_tags_persist(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("Track1"))
    repo.set_tags(1, "summer, vocal, peak")

    t = repo.get_by_id(1)
    assert t.user_tags == "summer, vocal, peak"


def test_remove_track_does_not_affect_others(tmp_db):
    repo = TrackRepository(tmp_db)
    repo.insert(_make_track("A", path="/music/a.mp3"))
    repo.insert(_make_track("B", path="/music/b.mp3"))
    repo.delete(1)

    assert repo.count() == 1
    assert repo.get_by_id(2) is not None
    assert repo.get_by_id(1) is None
