import os
import pytest

from app.services.folder_templates import (
    sanitize_name,
    bpm_range_label,
    build_path,
    resolve_destination,
    unique_destination,
)


class TestSanitizeName:
    def test_strips_invalid_chars(self):
        assert sanitize_name('My:File<>Name|*?.wav') == 'My_File__Name___.wav'

    def test_empty_returns_fallback(self):
        assert sanitize_name("", fallback="Unknown") == "Unknown"

    def test_none_returns_fallback(self):
        assert sanitize_name(None, fallback="Empty") == "Empty"

    def test_strips_trailing_dots_and_spaces(self):
        assert sanitize_name("  hello...  ") == "hello"

    def test_windows_reserved_names(self):
        assert sanitize_name("CON") == "_CON"
        assert sanitize_name("NUL") == "_NUL"

    def test_truncates_long_names(self):
        long = "a" * 500
        result = sanitize_name(long)
        assert len(result) == 200


class TestBpmRangeLabel:
    @pytest.mark.parametrize("bpm,expected", [
        (None, "Unknown BPM"),
        (50, "Below 60 BPM"),
        (80, "60-99 BPM"),
        (110, "100-119 BPM"),
        (122, "120-124 BPM"),
        (128, "125-129 BPM"),
        (132, "130-134 BPM"),
        (137, "135-139 BPM"),
        (150, "140-159 BPM"),
        (180, "160-199 BPM"),
        (210, "200+ BPM"),
    ])
    def test_ranges(self, bpm, expected):
        assert bpm_range_label(bpm) == expected


class TestBuildPath:
    def test_simple_template(self):
        fields = {"genre": "House", "artist": "DJ Test"}
        result = build_path("{genre}/{artist}", fields, base_dir="C:/Music")
        assert result == "C:/Music/House/DJ Test"

    def test_unknown_field_uses_unknown(self):
        fields = {"genre": None, "artist": "DJ Test"}
        result = build_path("{genre}/{artist}", fields)
        assert result.startswith("Unknown/")

    def test_bpm_range_fallback(self):
        fields = {"bpm_range": None}
        result = build_path("{bpm_range}", fields, unknown_bpm_fallback="Unknown BPM")
        assert result == "Unknown BPM"

    def test_musical_key_fallback(self):
        fields = {"musical_key": None}
        result = build_path("{musical_key}", fields, unknown_key_fallback="No Key")
        assert result == "No Key"

    def test_sanitizes_field_values(self):
        fields = {"genre": "House:Techno"}
        result = build_path("{genre}", fields)
        assert ":" not in result


class TestResolveDestination:
    def test_full_path(self):
        fields = {"genre": "House", "artist": "DJ Test", "album": "Album One"}
        result = resolve_destination(
            fields,
            base_dir="C:/Music",
            folder_template="{genre}/{artist}",
            file_template="{artist} - {album}",
            extension=".mp3",
        )
        assert result == "C:/Music/House/DJ Test/DJ Test - Album One.mp3"

    def test_extension_strips_leading_dot(self):
        result = resolve_destination(
            {"artist": "X"}, "C:/M", "{artist}", "{artist}", "flac"
        )
        assert result.endswith(".flac")


class TestUniqueDestination:
    def test_no_existing_returns_original(self, tmp_path):
        path = str(tmp_path / "song.mp3")
        assert unique_destination(path) == path

    def test_appends_index_on_conflict(self, tmp_path):
        path = tmp_path / "song.mp3"
        path.write_text("existing")
        result = unique_destination(str(path))
        assert result == str(tmp_path / "song (1).mp3")

    def test_multiple_conflicts(self, tmp_path):
        base = tmp_path / "song.mp3"
        base.write_text("0")
        (tmp_path / "song (1).mp3").write_text("1")
        (tmp_path / "song (2).mp3").write_text("2")
        result = unique_destination(str(base))
        assert result == str(tmp_path / "song (3).mp3")
