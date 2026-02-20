from website.statcrew import (
    _find_ncaa_team,
    _hex_to_hsl,
    _is_valid_away_color,
    _parse_statcrew_xml,
    lookup_away_team_color,
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

    def test_base_runners_from_status_element(self):
        """Runners read directly from <status first="" second="" third="">."""
        xml = """<?xml version="1.0"?>
        <bsgame>
            <team vh="V" name="Away" code="AWY"/>
            <team vh="H" name="Home" code="HOM"/>
            <status vh="V" inning="1" batter="Batter, X" pitcher="Pitcher, Y"
                    first="Runner, A" second="" third="Runner, B"/>
        </bsgame>
        """
        result = _parse_statcrew_xml(xml)
        assert result["runner_first"] == "Runner, A"
        assert result["runner_second"] == ""
        assert result["runner_third"] == "Runner, B"

    def test_base_runners_parsed_from_play(self):
        """Runners on first and third from last <play> in current half-inning."""
        xml = """<?xml version="1.0"?>
        <bsgame>
            <team vh="V" name="Away" code="AWY"/>
            <team vh="H" name="Home" code="HOM"/>
            <status vh="V" inning="3" batter="Smith, John" pitcher="Doe, Jane"/>
            <plays>
                <batting vh="V" inning="3">
                    <play first="" second="" third=""/>
                    <play first="Runner, A" second="" third="Runner, B"/>
                </batting>
            </plays>
        </bsgame>
        """
        result = _parse_statcrew_xml(xml)
        assert result["runner_first"] == "Runner, A"
        assert result["runner_second"] == ""
        assert result["runner_third"] == "Runner, B"

    def test_base_runners_empty_when_no_plays(self):
        """Without a <plays> element, all runners should be empty."""
        xml = """<?xml version="1.0"?>
        <bsgame>
            <team vh="V" name="Away" code="AWY"/>
            <team vh="H" name="Home" code="HOM"/>
            <status vh="V" inning="1" batter="Smith, John" pitcher="Doe, Jane"/>
        </bsgame>
        """
        result = _parse_statcrew_xml(xml)
        assert result["runner_first"] == ""
        assert result["runner_second"] == ""
        assert result["runner_third"] == ""

    def test_base_runners_empty_when_game_complete(self):
        """When game is complete, all bases should be empty."""
        xml = """<?xml version="1.0"?>
        <bsgame>
            <team vh="V" name="Away" code="AWY"/>
            <team vh="H" name="Home" code="HOM"/>
            <status vh="H" inning="9" complete="Y" batter="" pitcher=""/>
            <plays>
                <batting vh="H" inning="9">
                    <play first="Runner, X" second="" third=""/>
                </batting>
            </plays>
        </bsgame>
        """
        result = _parse_statcrew_xml(xml)
        assert result["runner_first"] == ""
        assert result["runner_second"] == ""
        assert result["runner_third"] == ""

    def test_base_runners_correct_half_inning_targeting(self):
        """Uses <status vh inning> to find the right <batting> element."""
        xml = """<?xml version="1.0"?>
        <bsgame>
            <team vh="V" name="Away" code="AWY"/>
            <team vh="H" name="Home" code="HOM"/>
            <status vh="H" inning="2" batter="Batter, X" pitcher="Pitcher, Y"/>
            <plays>
                <batting vh="V" inning="1">
                    <play first="Old Runner" second="" third=""/>
                    <innsummary/>
                </batting>
                <batting vh="H" inning="1">
                    <play first="" second="Old Runner 2" third=""/>
                    <innsummary/>
                </batting>
                <batting vh="V" inning="2">
                    <play first="" second="" third="Wrong Runner"/>
                    <innsummary/>
                </batting>
                <batting vh="H" inning="2">
                    <play first="" second="Current Runner" third=""/>
                </batting>
            </plays>
        </bsgame>
        """
        result = _parse_statcrew_xml(xml)
        assert result["runner_first"] == ""
        assert result["runner_second"] == "Current Runner"
        assert result["runner_third"] == ""

    def test_base_runners_empty_when_innsummary_present(self):
        """When the targeted half-inning has <innsummary>, bases are empty."""
        xml = """<?xml version="1.0"?>
        <bsgame>
            <team vh="V" name="Away" code="AWY"/>
            <team vh="H" name="Home" code="HOM"/>
            <status vh="V" inning="3" batter="" pitcher=""/>
            <plays>
                <batting vh="V" inning="3">
                    <play first="Runner, A" second="" third=""/>
                    <innsummary/>
                </batting>
            </plays>
        </bsgame>
        """
        result = _parse_statcrew_xml(xml)
        assert result["runner_first"] == ""
        assert result["runner_second"] == ""
        assert result["runner_third"] == ""

    def test_base_runners_fallback_no_status_vh(self):
        """Fallback: when <status> lacks vh/inning, use last <batting> without <innsummary>."""
        xml = """<?xml version="1.0"?>
        <bsgame>
            <team vh="V" name="Away" code="AWY"/>
            <team vh="H" name="Home" code="HOM"/>
            <status batter="Someone" pitcher="Someone Else"/>
            <plays>
                <batting vh="V" inning="1">
                    <play first="Old" second="" third=""/>
                    <innsummary/>
                </batting>
                <batting vh="H" inning="1">
                    <play first="" second="Fallback Runner" third=""/>
                </batting>
            </plays>
        </bsgame>
        """
        result = _parse_statcrew_xml(xml)
        assert result["runner_first"] == ""
        assert result["runner_second"] == "Fallback Runner"
        assert result["runner_third"] == ""

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


class TestHexToHsl:
    def test_pure_red(self):
        h, s, l = _hex_to_hsl("#FF0000")
        assert abs(h - 0) < 1
        assert abs(s - 1.0) < 0.01
        assert abs(l - 0.5) < 0.01

    def test_pure_white(self):
        h, s, l = _hex_to_hsl("#FFFFFF")
        assert abs(l - 1.0) < 0.01

    def test_pure_black(self):
        h, s, l = _hex_to_hsl("#000000")
        assert abs(l - 0.0) < 0.01

    def test_carolina_blue(self):
        h, s, l = _hex_to_hsl("#4b9cd3")
        assert 195 < h < 215  # blue range

    def test_invalid_hex(self):
        h, s, l = _hex_to_hsl("xyz")
        assert (h, s, l) == (0, 0, 0)


class TestIsValidAwayColor:
    def test_rejects_white(self):
        assert _is_valid_away_color("#FFFFFF") is False

    def test_rejects_near_white(self):
        assert _is_valid_away_color("#EEEEEE") is False

    def test_rejects_black(self):
        assert _is_valid_away_color("#000000") is False

    def test_rejects_near_black(self):
        assert _is_valid_away_color("#111111") is False

    def test_rejects_blue(self):
        assert _is_valid_away_color("#004C7D") is False  # Duke blue

    def test_rejects_carolina_blue(self):
        assert _is_valid_away_color("#4b9cd3") is False

    def test_accepts_red(self):
        assert _is_valid_away_color("#CC0000") is True

    def test_accepts_orange(self):
        assert _is_valid_away_color("#F06014") is True  # Clemson orange

    def test_accepts_purple(self):
        assert _is_valid_away_color("#441F6F") is True  # Clemson purple

    def test_accepts_gold(self):
        assert _is_valid_away_color("#C29C41") is True


class TestFindNcaaTeam:
    def test_exact_match(self):
        team = _find_ncaa_team("Clemson Tigers", "")
        assert team is not None
        assert team["slug"] == "clemson_tigers"

    def test_prefix_match(self):
        # StatCrew might send "Duke" without "Blue Devils"
        team = _find_ncaa_team("Duke", "")
        assert team is not None
        assert team["slug"] == "duke_blue_devils"

    def test_code_slug_match(self):
        team = _find_ncaa_team("", "clemson")
        assert team is not None
        assert team["slug"] == "clemson_tigers"

    def test_no_match(self):
        team = _find_ncaa_team("Nonexistent School", "xyz")
        assert team is None

    def test_case_insensitive(self):
        team = _find_ncaa_team("CLEMSON TIGERS", "")
        assert team is not None
        assert team["slug"] == "clemson_tigers"

    def test_periods_stripped(self):
        # "U.S.C." → "usc" should match via prefix on "usc trojans"
        team = _find_ncaa_team("U.S.C.", "")
        assert team is not None
        assert "usc" in team["slug"]

    def test_empty_inputs(self):
        team = _find_ncaa_team("", "")
        assert team is None

    def test_none_inputs(self):
        team = _find_ncaa_team(None, None)
        assert team is None


class TestLookupAwayTeamColor:
    def test_duke_falls_back(self):
        """Duke only has white + blue — both rejected — should return fallback."""
        color = lookup_away_team_color("Duke Blue Devils", "duke")
        assert color == "#d46a6a"

    def test_nc_state_returns_red(self):
        color = lookup_away_team_color("North Carolina State Wolfpack", "")
        assert color != "#d46a6a"
        # NC State's red (#EF1216) should be valid
        assert _is_valid_away_color(color)

    def test_clemson_returns_valid(self):
        color = lookup_away_team_color("Clemson Tigers", "clemson")
        assert color != "#d46a6a"
        assert _is_valid_away_color(color)

    def test_unknown_returns_fallback(self):
        color = lookup_away_team_color("Unknown School", "xyz")
        assert color == "#d46a6a"

    def test_empty_returns_fallback(self):
        color = lookup_away_team_color("", "")
        assert color == "#d46a6a"

    def test_parser_includes_away_team_color(self):
        """The XML parser should add away_team_color to parsed output."""
        xml = """<?xml version="1.0"?>
        <bsgame>
            <team vh="V" name="Clemson Tigers" code="clemson"/>
            <team vh="H" name="North Carolina" code="unc"/>
        </bsgame>
        """
        result = _parse_statcrew_xml(xml)
        assert "away_team_color" in result
        assert result["away_team_color"] != "#d46a6a"
        assert _is_valid_away_color(result["away_team_color"])


class TestLacrosseStatcrew:
    MLAX_XML = """<?xml version="1.0"?>
    <lcgame source="PrestoSports" version="7.13.0" generated="02/15/2026">
      <venue date="2/15/2026" location="Chapel Hill, N.C." stadium="Dorrance Field"
             attend="543" gameid="" start="12:00 PM">
        <show sog="1" turnovers="0" faceoffs="1" dcs="0" penalties="0" clears="0"/>
      </venue>
      <status period="4" clock="00:00" complete="Y"/>
      <team vh="V" id="IONA" name="Iona" code="310" record="0-4">
        <totals>
          <shots g="7" a="2" sh="28" sog="13" freepos="0"/>
          <penalty count="2" seconds="90" foul="0"/>
          <misc facewon="9" facelost="25" gb="24" dc="0" turnover="19" ct="5"/>
          <goalie minutes="60:00" ga="23" saves="14" sf="65"/>
          <clear clearm="15" cleara="22"/>
        </totals>
      </team>
      <team vh="H" id="NORTH CA" name="North Carolina" code="457" record="3-0">
        <totals>
          <shots g="23" a="12" sh="50" sog="37" freepos="0"/>
          <penalty count="2" seconds="60" foul="0"/>
          <misc facewon="25" facelost="9" gb="47" dc="0" turnover="15" ct="7"/>
          <goalie minutes="60:00" ga="7" saves="6" sf="28"/>
          <clear clearm="15" cleara="19"/>
        </totals>
      </team>
    </lcgame>"""

    WLAX_XML = """<?xml version="1.0"?>
    <lcgame source="TAS For Lacrosse" version="1.16.01" generated="5/19/2022">
      <venue date="5/19/2022" location="Chapel Hill, N.C." stadium="Dorrance Field"
             attend="1052" gameid="WNC0519" start="7:32 pm">
        <show sog="1" turnovers="1" faceoffs="0" dcs="1" fpas="1" fouls="1" clears="1"/>
      </venue>
      <status period="4" clock="08:39"/>
      <team vh="V" id="SBU" name="Stony Brook" record="16-2" rank="7">
        <totals>
          <shots g="5" a="1" sh="19" sog="13" freepos="1"/>
          <penalty count="0" seconds="0" foul="17"/>
          <misc gb="12" dc="6" turnover="10" ct="11"/>
          <goalie minutes="51:21" ga="7" saves="7" sf="18"/>
          <clear clearm="15" cleara="16"/>
        </totals>
      </team>
      <team vh="H" id="NC" name="North Carolina" record="19-0" rank="1">
        <totals>
          <shots g="7" a="4" sh="18" sog="14" freepos="7"/>
          <penalty count="0" seconds="0" foul="9"/>
          <misc gb="12" dc="9" turnover="17" ct="6"/>
          <goalie minutes="51:21" ga="5" saves="8" sf="19"/>
          <clear clearm="17" cleara="20"/>
        </totals>
      </team>
    </lcgame>"""

    def test_mens_gender_detection(self):
        result = _parse_statcrew_xml(self.MLAX_XML)
        assert result["lacrosse_gender"] == "M"

    def test_womens_gender_detection(self):
        result = _parse_statcrew_xml(self.WLAX_XML)
        assert result["lacrosse_gender"] == "W"

    def test_mens_team_names(self):
        result = _parse_statcrew_xml(self.MLAX_XML)
        assert result["away_name"] == "Iona"
        assert result["home_name"] == "North Carolina"
        assert result["away_record"] == "0-4"
        assert result["home_record"] == "3-0"

    def test_womens_team_names(self):
        result = _parse_statcrew_xml(self.WLAX_XML)
        assert result["away_name"] == "Stony Brook"
        assert result["home_name"] == "North Carolina"

    def test_mens_away_team_color(self):
        result = _parse_statcrew_xml(self.MLAX_XML)
        assert "away_team_color" in result

    def test_mens_home_team_stats(self):
        result = _parse_statcrew_xml(self.MLAX_XML)
        stats = result["home_team_stats"]
        assert stats["goals"] == "23"
        assert stats["sog"] == "37"
        assert stats["facewon"] == "25"
        assert stats["facelost"] == "9"
        assert stats["fo_display"] == "25-9"
        assert stats["gb"] == "47"
        assert stats["turnover"] == "15"
        assert stats["ct"] == "7"
        assert stats["clears"] == "15/19"
        # Save %: 6 saves / 28 shots faced = 21%
        assert stats["save_pct"] == "21%"

    def test_mens_away_team_stats(self):
        result = _parse_statcrew_xml(self.MLAX_XML)
        stats = result["away_team_stats"]
        assert stats["facewon"] == "9"
        assert stats["facelost"] == "25"
        assert stats["fo_display"] == "9-25"
        assert stats["gb"] == "24"
        assert stats["turnover"] == "19"
        # Save %: 14 saves / 65 shots faced = 22%
        assert stats["save_pct"] == "22%"

    def test_womens_home_team_stats(self):
        result = _parse_statcrew_xml(self.WLAX_XML)
        stats = result["home_team_stats"]
        assert stats["dc"] == "9"
        assert stats["gb"] == "12"
        assert stats["turnover"] == "17"
        assert stats["ct"] == "6"
        assert stats["clears"] == "17/20"
        assert stats["fouls"] == "9"
        # Save %: 8 saves / 19 shots faced = 42%
        assert stats["save_pct"] == "42%"

    def test_womens_away_team_stats(self):
        result = _parse_statcrew_xml(self.WLAX_XML)
        stats = result["away_team_stats"]
        assert stats["dc"] == "6"
        assert stats["gb"] == "12"
        assert stats["turnover"] == "10"
        assert stats["ct"] == "11"
        assert stats["fouls"] == "17"
        # Save %: 7 saves / 18 shots faced = 39%
        assert stats["save_pct"] == "39%"

    def test_venue_parsed(self):
        result = _parse_statcrew_xml(self.MLAX_XML)
        assert result["venue"]["stadium"] == "Dorrance Field"
        assert result["venue"]["attendance"] == "543"

    def test_no_team_stats_without_totals(self):
        xml = """<?xml version="1.0"?>
        <lcgame>
          <venue date="2026-01-01"><show faceoffs="1" dcs="0"/></venue>
          <team vh="V" name="Away" code="A"/>
          <team vh="H" name="Home" code="H"/>
        </lcgame>"""
        result = _parse_statcrew_xml(xml)
        assert result["lacrosse_gender"] == "M"
        assert "away_team_stats" not in result
        assert "home_team_stats" not in result


class TestFootballStatcrew:
    FB_XML = """<?xml version="1.0"?>
    <fbgame source="NCAA In-Arena Utility" version="1.3.2" generated="11/22/2025">
      <venue date="11/22/2025" location="Chapel Hill, N.C." stadium="Kenan Stadium"
             attend="50000" gameid="FB1122"/>
      <team vh="V" code="193" id="DU" name="Duke" record="6-5">
        <linescore prds="4" line="7,10,7,8" score="32">
          <lineprd prd="1" score="7"/>
          <lineprd prd="2" score="10"/>
          <lineprd prd="3" score="7"/>
          <lineprd prd="4" score="8"/>
        </linescore>
        <totals totoff_plays="76" totoff_yards="352" totoff_avg="4.6">
          <firstdowns no="24" rush="9" pass="10" penalty="5"/>
          <penalties no="3" yds="27"/>
          <rush att="43" yds="177" td="3" long="29"/>
          <pass comp="20" att="33" int="0" yds="175" td="1" long="27"/>
          <fumbles no="1" lost="0"/>
        </totals>
      </team>
      <team vh="H" code="457" id="UNC" name="North Carolina" record="4-7">
        <linescore prds="4" line="14,7,0,7" score="28">
          <lineprd prd="1" score="14"/>
          <lineprd prd="2" score="7"/>
          <lineprd prd="3" score="0"/>
          <lineprd prd="4" score="7"/>
        </linescore>
        <totals totoff_plays="60" totoff_yards="280" totoff_avg="4.7">
          <firstdowns no="18" rush="6" pass="9" penalty="3"/>
          <penalties no="5" yds="45"/>
          <rush att="30" yds="120" td="2" long="22"/>
          <pass comp="15" att="25" int="2" yds="160" td="1" long="35"/>
          <fumbles no="2" lost="1"/>
        </totals>
      </team>
    </fbgame>"""

    def test_sport_detection(self):
        result = _parse_statcrew_xml(self.FB_XML)
        # Football should populate team stats (not basketball/lacrosse fields)
        assert "away_team_stats" in result
        assert "home_team_stats" in result
        assert "lacrosse_gender" not in result
        assert "basketball_gender" not in result

    def test_team_names(self):
        result = _parse_statcrew_xml(self.FB_XML)
        assert result["away_name"] == "Duke"
        assert result["home_name"] == "North Carolina"

    def test_away_team_color(self):
        result = _parse_statcrew_xml(self.FB_XML)
        assert "away_team_color" in result

    def test_away_team_stats(self):
        result = _parse_statcrew_xml(self.FB_XML)
        stats = result["away_team_stats"]
        assert stats["first_downs"] == "24"
        assert stats["total_yds"] == "352"
        assert stats["rush_yds"] == "177"
        assert stats["pass_yds"] == "175"
        assert stats["turnovers"] == "0"  # 0 fumbles lost + 0 interceptions
        assert stats["penalties"] == "3-27"

    def test_home_team_stats(self):
        result = _parse_statcrew_xml(self.FB_XML)
        stats = result["home_team_stats"]
        assert stats["first_downs"] == "18"
        assert stats["total_yds"] == "280"
        assert stats["rush_yds"] == "120"
        assert stats["pass_yds"] == "160"
        assert stats["turnovers"] == "3"  # 1 fumble lost + 2 interceptions
        assert stats["penalties"] == "5-45"

    def test_no_stats_without_totals(self):
        xml = """<?xml version="1.0"?>
        <fbgame>
          <team vh="V" name="Away"/>
          <team vh="H" name="Home"/>
        </fbgame>"""
        result = _parse_statcrew_xml(xml)
        assert "away_team_stats" not in result
        assert "home_team_stats" not in result


class TestSoccerStatcrew:
    SOC_XML = """<?xml version="1.0"?>
    <sogame source="Soccer LiveStats In-Arena Tool" version="2.7.0" generated="12/15/2025">
      <venue date="12/15/2025" location="Chapel Hill, N.C." stadium="Dorrance Field"
             attend="3500" gameid="SOC1215">
        <show sog="1" goaldesc="1" offsides="1" fouls="1" fhk="0"/>
      </venue>
      <status period="3" clock="91:54"/>
      <team vh="V" code="756" id="UW" name="Washington" record="16-6-2">
        <linescore periods="3" line="1,1,1" score="3" shots="13">
          <lineprd prd="1" score="1" shots="6" saves="2" corners="3" offsides="0" fouls="3"/>
          <lineprd prd="2" score="1" shots="6" saves="3" corners="2" offsides="0" fouls="5"/>
          <lineprd prd="3" score="1" shots="1" saves="0" corners="0" offsides="0" fouls="0"/>
        </linescore>
        <totals>
          <shots g="3" a="2" sh="13" sog="9"/>
          <penalty count="3" red="0" yellow="3" green="0" fouls="8"/>
          <misc minutes="1011" dsave="0"/>
          <goalie minutes="91:54" ga="2" saves="5" sf="17"/>
        </totals>
      </team>
      <team vh="H" code="490" id="NCSU" name="NC State" record="16-3-4">
        <linescore periods="3" line="0,2,0" score="2" shots="10">
          <lineprd prd="1" score="0" shots="4" saves="3" corners="1" offsides="2" fouls="4"/>
          <lineprd prd="2" score="2" shots="5" saves="1" corners="3" offsides="1" fouls="3"/>
          <lineprd prd="3" score="0" shots="1" saves="0" corners="0" offsides="0" fouls="1"/>
        </linescore>
        <totals>
          <shots g="2" a="1" sh="10" sog="7"/>
          <penalty count="1" red="0" yellow="1" green="0" fouls="8"/>
          <misc minutes="990" dsave="1"/>
          <goalie minutes="91:54" ga="3" saves="6" sf="12"/>
        </totals>
      </team>
    </sogame>"""

    def test_sport_detection(self):
        result = _parse_statcrew_xml(self.SOC_XML)
        assert "away_team_stats" in result
        assert "home_team_stats" in result
        assert "lacrosse_gender" not in result

    def test_team_names(self):
        result = _parse_statcrew_xml(self.SOC_XML)
        assert result["away_name"] == "Washington"
        assert result["home_name"] == "NC State"

    def test_away_team_color(self):
        result = _parse_statcrew_xml(self.SOC_XML)
        assert "away_team_color" in result

    def test_away_team_stats(self):
        result = _parse_statcrew_xml(self.SOC_XML)
        stats = result["away_team_stats"]
        assert stats["sog"] == "9"
        assert stats["fouls"] == "8"
        assert stats["offsides"] == "0"  # 0+0+0
        assert stats["save_pct"] == "29%"  # 5/17 = 29%
        assert stats["yc"] == "3"
        assert stats["rc"] == "0"

    def test_home_team_stats(self):
        result = _parse_statcrew_xml(self.SOC_XML)
        stats = result["home_team_stats"]
        assert stats["sog"] == "7"
        assert stats["fouls"] == "8"
        assert stats["offsides"] == "3"  # 2+1+0
        assert stats["save_pct"] == "50%"  # 6/12 = 50%
        assert stats["yc"] == "1"
        assert stats["rc"] == "0"

    def test_not_field_hockey(self):
        """fhk=0 should NOT produce field hockey stats (corners/dsaves)."""
        result = _parse_statcrew_xml(self.SOC_XML)
        stats = result["away_team_stats"]
        assert "corners" not in stats
        assert "dsaves" not in stats

    def test_no_stats_without_totals(self):
        xml = """<?xml version="1.0"?>
        <sogame>
          <venue><show fhk="0"/></venue>
          <team vh="V" name="Away"/>
          <team vh="H" name="Home"/>
        </sogame>"""
        result = _parse_statcrew_xml(xml)
        assert "away_team_stats" not in result
        assert "home_team_stats" not in result


class TestFieldHockeyStatcrew:
    FH_XML = """<?xml version="1.0"?>
    <sogame source="TAS For Soccer" version="1.16.01" generated="10/23/2022">
      <venue date="10/23/2022" location="Chapel Hill, N.C." stadium="Karen Shelton"
             attend="1200" gameid="FH1023">
        <show sog="1" goaldesc="1" offsides="0" fouls="0" fhk="1"/>
      </venue>
      <status period="4" clock="60:00"/>
      <team vh="V" id="SJU" name="Saint Joseph's" record="12-4" rank="9">
        <linescore periods="4" line="0,0,0,0" score="0" shots="7">
          <lineprd prd="1" score="0" shots="1" saves="1" fouls="0" corners="1" offsides="0"/>
          <lineprd prd="2" score="0" shots="0" saves="3" fouls="0" corners="0" offsides="0"/>
          <lineprd prd="3" score="0" shots="5" saves="3" fouls="0" corners="1" offsides="0"/>
          <lineprd prd="4" score="0" shots="1" saves="0" fouls="0" corners="0" offsides="0"/>
        </linescore>
        <totals>
          <shots g="0" a="0" sh="7" sog="5"/>
          <penalty count="0" red="0" yellow="0" green="0" fouls="0"/>
          <misc minutes="639" dsave="0"/>
          <goalie minutes="60:00" ga="6" saves="7" sf="17"/>
        </totals>
      </team>
      <team vh="H" id="NC" name="North Carolina" record="14-0" rank="1">
        <linescore periods="4" line="2,1,2,1" score="6" shots="25">
          <lineprd prd="1" score="2" shots="6" saves="0" fouls="0" corners="3" offsides="0"/>
          <lineprd prd="2" score="1" shots="7" saves="0" fouls="0" corners="2" offsides="0"/>
          <lineprd prd="3" score="2" shots="8" saves="1" fouls="0" corners="4" offsides="0"/>
          <lineprd prd="4" score="1" shots="4" saves="1" fouls="0" corners="1" offsides="0"/>
        </linescore>
        <totals>
          <shots g="6" a="4" sh="25" sog="18"/>
          <penalty count="0" red="0" yellow="0" green="0" fouls="0"/>
          <misc minutes="720" dsave="2"/>
          <goalie minutes="60:00" ga="0" saves="5" sf="7"/>
        </totals>
      </team>
    </sogame>"""

    def test_sport_detection_fhk(self):
        """fhk=1 should be detected as field hockey, not soccer."""
        result = _parse_statcrew_xml(self.FH_XML)
        assert "away_team_stats" in result
        stats = result["away_team_stats"]
        # Field hockey has corners and dsaves, not offsides/yc/rc
        assert "corners" in stats
        assert "dsaves" in stats
        assert "offsides" not in stats
        assert "yc" not in stats

    def test_team_names(self):
        result = _parse_statcrew_xml(self.FH_XML)
        assert result["away_name"] == "Saint Joseph's"
        assert result["home_name"] == "North Carolina"

    def test_away_team_color(self):
        result = _parse_statcrew_xml(self.FH_XML)
        assert "away_team_color" in result

    def test_away_team_stats(self):
        result = _parse_statcrew_xml(self.FH_XML)
        stats = result["away_team_stats"]
        assert stats["sog"] == "5"
        assert stats["corners"] == "2"  # 1+0+1+0
        assert stats["fouls"] == "0"
        assert stats["dsaves"] == "0"
        assert stats["save_pct"] == "41%"  # 7/17 = 41%

    def test_home_team_stats(self):
        result = _parse_statcrew_xml(self.FH_XML)
        stats = result["home_team_stats"]
        assert stats["sog"] == "18"
        assert stats["corners"] == "10"  # 3+2+4+1
        assert stats["fouls"] == "0"
        assert stats["dsaves"] == "2"
        assert stats["save_pct"] == "71%"  # 5/7 = 71%

    def test_no_stats_without_totals(self):
        xml = """<?xml version="1.0"?>
        <sogame>
          <venue><show fhk="1"/></venue>
          <team vh="V" name="Away"/>
          <team vh="H" name="Home"/>
        </sogame>"""
        result = _parse_statcrew_xml(xml)
        assert "away_team_stats" not in result
        assert "home_team_stats" not in result


class TestVolleyballStatcrew:
    VB_XML = """<?xml version="1.0"?>
    <vbgame source="Volleyball LiveStats In-Arena Tool" version="1.1.2" generated="Nov 29, 2025">
      <venue date="11/29/2025" location="Chapel Hill, N.C." stadium="Carmichael Arena"
             attend="4200" gameid="VB1129"/>
      <status complete="Y" vscore="3" hscore="2" game="5"/>
      <team vh="V" code="415" id="MIA" name="Miami (FL)" record="25-5">
        <linescore line="20,23,25,25,15" score="3">
          <linegame game="1" points="20"/>
          <linegame game="2" points="23"/>
          <linegame game="3" points="25"/>
          <linegame game="4" points="25"/>
          <linegame game="5" points="15"/>
        </linescore>
        <totals>
          <attack k="68" e="40" ta="186" pct=".151"/>
          <set a="66" e="0" ta="184"/>
          <serve sa="7" se="10" ta="107"/>
          <defense dig="77" re="4" ta="97"/>
          <block bs="2" ba="22" be="2" tb="13.0"/>
        </totals>
      </team>
      <team vh="H" code="457" id="UNC" name="North Carolina" record="21-7">
        <linescore line="25,25,22,16,10" score="2">
          <linegame game="1" points="25"/>
          <linegame game="2" points="25"/>
          <linegame game="3" points="22"/>
          <linegame game="4" points="16"/>
          <linegame game="5" points="10"/>
        </linescore>
        <totals>
          <attack k="55" e="35" ta="170" pct=".118"/>
          <set a="52" e="1" ta="160"/>
          <serve sa="4" se="8" ta="95"/>
          <defense dig="65" re="7" ta="85"/>
          <block bs="5" ba="18" be="3" tb="14.0"/>
        </totals>
      </team>
    </vbgame>"""

    def test_sport_detection(self):
        result = _parse_statcrew_xml(self.VB_XML)
        assert "away_team_stats" in result
        assert "home_team_stats" in result
        assert "lacrosse_gender" not in result
        assert "basketball_gender" not in result

    def test_team_names(self):
        result = _parse_statcrew_xml(self.VB_XML)
        assert result["away_name"] == "Miami (FL)"
        assert result["home_name"] == "North Carolina"

    def test_away_team_color(self):
        result = _parse_statcrew_xml(self.VB_XML)
        assert "away_team_color" in result

    def test_away_team_stats(self):
        result = _parse_statcrew_xml(self.VB_XML)
        stats = result["away_team_stats"]
        assert stats["kills"] == "68"
        assert stats["aces"] == "7"
        assert stats["digs"] == "77"
        assert stats["blocks"] == "13.0"
        assert stats["hit_pct"] == "15.1%"  # .151 * 100
        assert stats["errors"] == "40"

    def test_home_team_stats(self):
        result = _parse_statcrew_xml(self.VB_XML)
        stats = result["home_team_stats"]
        assert stats["kills"] == "55"
        assert stats["aces"] == "4"
        assert stats["digs"] == "65"
        assert stats["blocks"] == "14.0"
        assert stats["hit_pct"] == "11.8%"  # .118 * 100
        assert stats["errors"] == "35"

    def test_negative_hit_pct(self):
        """Negative hitting percentage should display correctly."""
        xml = """<?xml version="1.0"?>
        <vbgame>
          <team vh="V" name="Away">
            <totals>
              <attack k="5" e="10" ta="30" pct="-.167"/>
              <serve sa="0" se="0" ta="0"/>
              <defense dig="0" re="0" ta="0"/>
              <block bs="0" ba="0" be="0" tb="0"/>
            </totals>
          </team>
          <team vh="H" name="Home">
            <totals>
              <attack k="10" e="5" ta="30" pct=".167"/>
              <serve sa="1" se="0" ta="10"/>
              <defense dig="5" re="0" ta="10"/>
              <block bs="1" ba="2" be="0" tb="2.0"/>
            </totals>
          </team>
        </vbgame>"""
        result = _parse_statcrew_xml(xml)
        assert result["away_team_stats"]["hit_pct"] == "-16.7%"
        assert result["home_team_stats"]["hit_pct"] == "16.7%"

    def test_no_stats_without_totals(self):
        xml = """<?xml version="1.0"?>
        <vbgame>
          <team vh="V" name="Away"/>
          <team vh="H" name="Home"/>
        </vbgame>"""
        result = _parse_statcrew_xml(xml)
        assert "away_team_stats" not in result
        assert "home_team_stats" not in result
