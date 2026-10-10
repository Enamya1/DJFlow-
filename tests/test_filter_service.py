import json
import pytest

from app.services.filesystem_library import TrackInfo
from app.services.filter_service import (
    FilterCriteria,
    apply_filters,
    sort_tracks,
    is_camelot_compatible,
    bpm_match,
    camelot_number,
    save_preset,
    load_presets,
)


def _track(**kw):
    defaults = dict(file_path="/t.mp3", title="T", artist="A", album="Al", genre="House",
                    duration_seconds=180.0, bpm=128.0, musical_key="Am", camelot_key="8A",
                    file_format="mp3", energy=0.6, favorite=False, rating=3, analyzed=True)
    defaults.update(kw)
    return TrackInfo(**defaults)


@pytest.fixture
def tracks():
    return [
        _track(title="A1", artist="DJ Alpha", genre="House", bpm=128.0, musical_key="Am", camelot_key="8A", energy=0.7),
        _track(title="A2", artist="DJ Beta", genre="Techno", bpm=130.0, musical_key="Em", camelot_key="9A", energy=0.8),
        _track(title="A3", artist="DJ Alpha", genre="House", bpm=122.0, musical_key="C", camelot_key="8B", energy=0.4),
        _track(title="A4", artist="DJ Gamma", genre="Trance", bpm=140.0, musical_key="G", camelot_key="9B", energy=0.9, favorite=True),
        _track(title="A5", artist="DJ Delta", genre="House", bpm=None, musical_key=None, camelot_key=None, analyzed=False),
    ]


class TestCamelotCompatibility:
    def test_adjacent_keys_compatible(self):
        assert is_camelot_compatible("8A", "7A") is True
        assert is_camelot_compatible("8A", "9A") is True

    def test_same_key_compatible(self):
        assert is_camelot_compatible("8A", "8A") is True

    def test_different_mode_incompatible(self):
        assert is_camelot_compatible("8A", "8B") is False

    def test_far_keys_incompatible(self):
        assert is_camelot_compatible("1A", "7A") is False

    def test_none_returns_false(self):
        assert is_camelot_compatible(None, "8A") is False
        assert is_camelot_compatible("8A", None) is False

    def test_wheel_wrap(self):
        assert is_camelot_compatible("1A", "12A") is True
        assert is_camelot_compatible("12A", "1A") is True


class TestBpmMatch:
    def test_close_match(self):
        assert bpm_match(128.0, 126.0, tolerance=6.0) is True

    def test_outside_tolerance(self):
        assert bpm_match(128.0, 140.0, tolerance=6.0) is False

    def test_half_time_match(self):
        assert bpm_match(64.0, 128.0, tolerance=6.0, allow_half_double=True) is True

    def test_double_time_match(self):
        assert bpm_match(128.0, 256.0, tolerance=6.0, allow_half_double=True) is True

    def test_disabled_half_double(self):
        assert bpm_match(64.0, 128.0, tolerance=6.0, allow_half_double=False) is False

    def test_none_returns_false(self):
        assert bpm_match(None, 128.0) is False
        assert bpm_match(128.0, None) is False


class TestApplyFilters:
    def test_bpm_range(self, tracks):
        crit = FilterCriteria(bpm_min=125, bpm_max=132)
        result = apply_filters(tracks, crit)
        titles = {t.title for t in result}
        assert titles == {"A1", "A2"}

    def test_genre_filter(self, tracks):
        crit = FilterCriteria(genre="House")
        result = apply_filters(tracks, crit)
        assert all(t.genre == "House" for t in result)

    def test_artist_substring(self, tracks):
        crit = FilterCriteria(artist="Alpha")
        result = apply_filters(tracks, crit)
        assert {t.title for t in result} == {"A1", "A3"}

    def test_file_format(self, tracks):
        crit = FilterCriteria(file_format="mp3")
        assert len(apply_filters(tracks, crit)) == len(tracks)

    def test_favorite(self, tracks):
        crit = FilterCriteria(favorite=True)
        result = apply_filters(tracks, crit)
        assert {t.title for t in result} == {"A4"}

    def test_analyzed(self, tracks):
        crit = FilterCriteria(analyzed=True)
        result = apply_filters(tracks, crit)
        assert "A5" not in {t.title for t in result}

    def test_musical_key(self, tracks):
        crit = FilterCriteria(musical_key="Am")
        result = apply_filters(tracks, crit)
        assert all(t.musical_key == "Am" for t in result)

    def test_camelot_key(self, tracks):
        crit = FilterCriteria(camelot_key="8A")
        result = apply_filters(tracks, crit)
        assert all(t.camelot_key == "8A" for t in result)

    def test_compatible_camelot(self, tracks):
        crit = FilterCriteria(compatible_camelot="8A")
        result = apply_filters(tracks, crit)
        titles = {t.title for t in result}
        assert "A1" in titles
        assert "A2" in titles
        assert "A5" not in titles

    def test_bpm_match_target(self, tracks):
        crit = FilterCriteria(bpm_match_target=128.0, bpm_tolerance=4.0)
        result = apply_filters(tracks, crit)
        assert {t.title for t in result} == {"A1", "A2"}

    def test_energy_range(self, tracks):
        crit = FilterCriteria(energy_min=0.8)
        result = apply_filters(tracks, crit)
        assert {t.title for t in result} == {"A2", "A4"}

    def test_duration_range(self, tracks):
        crit = FilterCriteria(duration_min=100, duration_max=200)
        assert len(apply_filters(tracks, crit)) == len(tracks)

    def test_combined_filters(self, tracks):
        crit = FilterCriteria(genre="House", bpm_min=125)
        result = apply_filters(tracks, crit)
        assert {t.title for t in result} == {"A1"}

    def test_missing_metadata_true(self, tracks):
        crit = FilterCriteria(missing_metadata=True)
        result = apply_filters(tracks, crit)
        assert all(t.title == "A5" for t in result)

    def test_reset_criteria_returns_all(self, tracks):
        crit = FilterCriteria()
        assert len(apply_filters(tracks, crit)) == len(tracks)


class TestSortTracks:
    def test_sort_by_bpm_desc(self, tracks):
        result = sort_tracks(tracks, "bpm", descending=True)
        bpms = [t.bpm for t in result if t.bpm is not None]
        assert bpms == sorted(bpms, reverse=True)

    def test_sort_by_title_asc(self, tracks):
        result = sort_tracks(tracks, "title", descending=False)
        titles = [t.title for t in result]
        assert titles == sorted(titles)


class TestPresets:
    def test_save_and_load_preset(self, tmp_path):
        path = str(tmp_path / "presets.json")
        crit = FilterCriteria(bpm_min=120, bpm_max=130, genre="House")
        save_preset("House 120-130", crit, path)
        presets = load_presets(path)
        assert "House 120-130" in presets
        assert presets["House 120-130"]["bpm_min"] == 120

    def test_load_nonexistent_returns_empty(self, tmp_path):
        assert load_presets(str(tmp_path / "nope.json")) == {}
