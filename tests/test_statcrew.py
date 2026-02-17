from website.statcrew import (
    _parse_statcrew_xml,
    normalize_sport,
)


class TestNormalizeSport:
    def test_valid_basketball(self):
        assert normalize_sport("basketball") == "Basketball"

    def test_valid_baseball(self):
        assert normalize_sport("Baseball") == "Baseball"

    def test_valid_softball(self):
        assert normalize_sport("softball") == "Softball"

    def test_valid_hockey(self):
        assert normalize_sport("HOCKEY") == "Hockey"

    def test_valid_football(self):
        assert normalize_sport("football") == "Football"

    def test_valid_lacrosse(self):
        assert normalize_sport("Lacrosse") == "Lacrosse"

    def test_valid_volleyball(self):
        assert normalize_sport("volleyball") == "Volleyball"

    def test_valid_wrestling(self):
        assert normalize_sport("wrestling") == "Wrestling"

    def test_valid_soccer(self):
        assert normalize_sport("soccer") == "Soccer"

    def test_valid_gymnastics(self):
        assert normalize_sport("gymnastics") == "Gymnastics"

    def test_invalid(self):
        assert normalize_sport("curling") is None

    def test_empty(self):
        assert normalize_sport("") is None

    def test_none(self):
        assert normalize_sport(None) is None

    def test_whitespace(self):
        assert normalize_sport("  baseball  ") == "Baseball"


class TestParseStatcrewXml:
    def test_empty_string(self):
        result = _parse_statcrew_xml("")
        assert result == {}

    def test_none(self):
        result = _parse_statcrew_xml(None)
        assert result == {}

    def test_invalid_xml(self):
        result = _parse_statcrew_xml("<invalid>")
        assert result == {}

    def test_basic_venue(self):
        xml = """<?xml version="1.0"?>
        <game>
            <venue date="2024-03-15" location="Stadium" attend="5000" gameid="G123"/>
        </game>
        """
        result = _parse_statcrew_xml(xml)
        assert "venue" in result
        assert result["venue"]["date"] == "2024-03-15"
        assert result["venue"]["location"] == "Stadium"
        assert result["venue"]["attendance"] == "5000"
        assert result["venue"]["gameid"] == "G123"

    def test_team_info(self):
        xml = """<?xml version="1.0"?>
        <game>
            <team id="H" name="Home Team" code="HOM"/>
            <team id="V" name="Visitor Team" code="VIS"/>
        </game>
        """
        result = _parse_statcrew_xml(xml)
        assert "teams" in result
        assert len(result["teams"]) == 2
        assert result["teams"][0]["id"] == "H"
        assert result["teams"][0]["name"] == "Home Team"
        assert result["teams"][1]["id"] == "V"
        assert result["teams"][1]["name"] == "Visitor Team"

    def test_linescore(self):
        xml = """<?xml version="1.0"?>
        <game>
            <team id="H" name="Home">
                <linescore runs="5" hits="8" errs="1">
                    <lineinn score="1"/>
                    <lineinn score="0"/>
                    <lineinn score="2"/>
                </linescore>
            </team>
        </game>
        """
        result = _parse_statcrew_xml(xml)
        assert "teams" in result
        assert len(result["teams"]) == 1
        team = result["teams"][0]
        assert team["linescore"]["runs"] == "5"
        assert team["linescore"]["hits"] == "8"
        assert team["linescore"]["errs"] == "1"
        assert team["innings"] == ["1", "0", "2"]

    def test_player_stats(self):
        xml = """<?xml version="1.0"?>
        <game>
            <team id="H" name="Home">
                <player name="John Doe" uni="12" pos="P">
                    <stats ip="6.0" h="4" r="2" er="2" bb="1" so="8"/>
                </player>
                <player name="Jane Smith" uni="5" pos="CF">
                    <stats ab="4" r="1" h="2" rbi="1" bb="0"/>
                </player>
            </team>
        </game>
        """
        result = _parse_statcrew_xml(xml)
        assert "players" in result
        assert "H" in result["players"]
        players = result["players"]["H"]
        assert len(players) == 2
        assert players[0]["name"] == "John Doe"
        assert players[0]["uni"] == "12"
        assert players[0]["pos"] == "P"
        assert players[0]["stats"]["ip"] == "6.0"
        assert players[0]["stats"]["so"] == "8"
        assert players[1]["name"] == "Jane Smith"
        assert players[1]["stats"]["ab"] == "4"

    def test_team_totals(self):
        xml = """<?xml version="1.0"?>
        <game>
            <team id="H" name="Home">
                <totals>
                    <stats ab="35" r="5" h="10" rbi="5" bb="3"/>
                </totals>
            </team>
        </game>
        """
        result = _parse_statcrew_xml(xml)
        assert "teams" in result
        assert len(result["teams"]) == 1
        team = result["teams"][0]
        assert "totals" in team
        assert team["totals"]["ab"] == "35"
        assert team["totals"]["r"] == "5"
        assert team["totals"]["h"] == "10"

    def test_fallback_generic_parsing(self):
        xml = """<?xml version="1.0"?>
        <data>
            <score>42</score>
            <status active="true"/>
        </data>
        """
        result = _parse_statcrew_xml(xml)
        # Should fallback to generic parsing
        assert "score" in result or "status_active" in result

    def test_complex_game(self):
        xml = """<?xml version="1.0"?>
        <game>
            <venue date="2024-03-15" location="Stadium" attend="5000"/>
            <team id="H" name="Home Team">
                <linescore runs="5" hits="8" errs="1">
                    <lineinn score="1"/>
                    <lineinn score="2"/>
                    <lineinn score="2"/>
                </linescore>
                <totals>
                    <stats ab="30" h="8" r="5"/>
                </totals>
                <player name="Player 1" uni="1" pos="P">
                    <stats ip="9.0" so="12"/>
                </player>
            </team>
            <team id="V" name="Visitor Team">
                <linescore runs="3" hits="6" errs="0">
                    <lineinn score="1"/>
                    <lineinn score="1"/>
                    <lineinn score="1"/>
                </linescore>
            </team>
        </game>
        """
        result = _parse_statcrew_xml(xml)
        assert "venue" in result
        assert "teams" in result
        assert len(result["teams"]) == 2
        assert "players" in result
        assert "H" in result["players"]
        assert result["teams"][0]["linescore"]["runs"] == "5"
        assert result["teams"][1]["linescore"]["runs"] == "3"
