from website.trackman import (
    _parse_trackman_payload,
    _parse_trackman_json,
    normalize_sport,
)


class TestNormalizeSport:
    def test_valid_baseball(self):
        assert normalize_sport("baseball") == "Baseball"

    def test_valid_softball(self):
        assert normalize_sport("Softball") == "Softball"

    def test_invalid(self):
        assert normalize_sport("Hockey") is None

    def test_empty(self):
        assert normalize_sport("") is None

    def test_none(self):
        assert normalize_sport(None) is None


class TestParseTrackmanPayload:
    def test_broadcast_format(self):
        payload = {
            "Pitch": {"Speed": 92.5, "SpinRate": 2200},
            "Hit": {"Speed": 105.0, "Angle": 28.0, "Distance": 400.0},
            "PlayId": "abc123",
        }
        result = _parse_trackman_payload(payload)
        assert result["feed_type"] == "broadcast"
        assert result["pitch_speed"] == 92.5
        assert result["hit_exit_velocity"] == 105.0

    def test_scoreboard_format(self):
        payload = {
            "PitchExitSpeed": 88.0,
            "HitSpeed": 99.0,
            "Id": "xyz",
        }
        result = _parse_trackman_payload(payload)
        assert result["feed_type"] == "scoreboard"
        assert result["pitch_speed"] == 88.0
        assert result["hit_exit_velocity"] == 99.0

    def test_empty_payload(self):
        result = _parse_trackman_payload({})
        assert result.get("feed_type") == "scoreboard"
        assert "pitch_speed" not in result
        assert "hit_exit_velocity" not in result

    def test_non_dict(self):
        assert _parse_trackman_payload("not a dict") == {}


class TestParseTrackmanJson:
    def test_single_object(self):
        result = _parse_trackman_json('{"PitchSpeed": 90}')
        assert len(result) == 1
        assert result[0]["PitchSpeed"] == 90

    def test_array(self):
        result = _parse_trackman_json('[{"a": 1}, {"b": 2}]')
        assert len(result) == 2

    def test_ndjson(self):
        result = _parse_trackman_json('{"a": 1}\n{"b": 2}')
        assert len(result) == 2

    def test_empty(self):
        assert _parse_trackman_json("") == []
        assert _parse_trackman_json(None) == []

    def test_invalid_json(self):
        assert _parse_trackman_json("not json") == []
