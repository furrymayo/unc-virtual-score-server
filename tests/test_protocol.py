from website.protocol import (
    PacketStreamParser,
    STX, CR,
    TP_BBALL_BASE_SOFT, TP_FOOTBALL, TP_VOLLEYBALL,
    BBALL_LEN,
    _decode_score, _decode_clock,
    identify_and_parse,
    parse_basketball_data, parse_volleyball_data, parse_football_data,
)


def _make_packet(packet_type, body_len):
    """Build a minimal valid packet: STX + type + (body_len - 3) data bytes + CR."""
    data_bytes = [0x30] * (body_len - 3)  # ASCII '0' as filler
    return [STX, packet_type] + data_bytes + [CR]


class TestPacketStreamParser:
    def test_single_complete_packet(self):
        pkt = _make_packet(TP_VOLLEYBALL, 20)
        parser = PacketStreamParser()
        result = parser.feed_bytes(pkt)
        assert len(result) == 1
        assert result[0][0] == STX
        assert result[0][1] == TP_VOLLEYBALL
        assert result[0][-1] == CR

    def test_split_delivery(self):
        pkt = _make_packet(TP_VOLLEYBALL, 20)
        mid = len(pkt) // 2
        parser = PacketStreamParser()
        result1 = parser.feed_bytes(pkt[:mid])
        result2 = parser.feed_bytes(pkt[mid:])
        assert len(result1) == 0
        assert len(result2) == 1
        assert result2[0] == pkt

    def test_garbage_before_packet(self):
        garbage = [0xFF, 0x10, 0x00]
        pkt = _make_packet(TP_FOOTBALL, 15)
        parser = PacketStreamParser()
        result = parser.feed_bytes(garbage + pkt)
        assert len(result) == 1

    def test_invalid_type_rejected(self):
        bad = [STX, 0x01, 0x30, 0x30, CR]
        parser = PacketStreamParser()
        result = parser.feed_bytes(bad)
        assert len(result) == 0


class TestDecoders:
    def test_decode_score_normal(self):
        assert _decode_score(ord("3"), ord("5")) == "35"

    def test_decode_score_triple_digit(self):
        result = _decode_score(176, 0xB0)
        assert result.startswith("1")

    def test_decode_score_blank_tens(self):
        result = _decode_score(0x3A, ord("7"))
        assert result.strip() == "7"

    def test_decode_clock_normal(self):
        result = _decode_clock(ord("1"), ord("2"), ord("3"), ord("4"))
        assert result == "12:34"

    def test_decode_clock_tenths(self):
        result = _decode_clock(0x3A, ord("5"), ord("3"), 0x3A)
        assert "5" in result and "3" in result


class TestSportParsers:
    def _build_basketball_packet(self):
        pkt = [0] * BBALL_LEN
        pkt[0] = STX
        pkt[1] = TP_BBALL_BASE_SOFT
        # clock bytes
        pkt[2] = ord("1") | 0x80  # min tens (with high bit)
        pkt[3] = ord("2") | 0x80
        pkt[4] = ord("3") | 0x80
        pkt[5] = ord("4")
        pkt[6] = ord("2")  # period
        pkt[7] = ord("4")  # home score tens
        pkt[8] = ord("5")  # home score ones
        pkt[9] = ord("3")  # visitor score tens
        pkt[10] = ord("8")  # visitor score ones
        pkt[11] = ord("3") | 0x80  # home tol
        pkt[12] = ord("2") | 0x80  # visitor tol
        pkt[13] = ord("5")  # home fouls
        pkt[14] = ord("3")  # visitor fouls
        pkt[15] = 0x30
        pkt[16] = 0x31  # hm_values (poss=1)
        pkt[17] = 0x30  # vs_values
        pkt[18] = ord("2")  # shot clock ms
        pkt[19] = ord("4")  # shot clock ls
        pkt[20] = 0x30
        pkt[21] = 0x30
        pkt[22] = CR
        return pkt

    def test_basketball_parse(self):
        pkt = self._build_basketball_packet()
        result = parse_basketball_data(pkt)
        assert "error" not in result
        assert result["period"] == "2"
        assert result["home_score"] == "45"
        assert result["visitor_score"] == "38"
        assert result["possession"] == "home"

    def test_volleyball_parse(self):
        pkt = [0x30] * 42
        pkt[0] = STX
        pkt[1] = TP_VOLLEYBALL
        pkt[2] = ord("0") | 0x80
        pkt[3] = ord("5") | 0x80
        pkt[4] = ord("0") | 0x80
        pkt[5] = ord("0")
        pkt[6] = ord("3")
        pkt[7] = ord("2")
        pkt[8] = ord("5")
        pkt[9] = ord("1")
        pkt[10] = ord("8")
        pkt[11] = ord("2") | 0x80
        pkt[12] = ord("1") | 0x80
        pkt[16] = 0x31  # home poss
        pkt[17] = 0x30
        pkt[18] = ord("2")
        pkt[19] = ord("1")
        pkt[-1] = CR
        result = parse_volleyball_data(pkt)
        assert "error" not in result
        assert result["period"] == "3"

    def test_football_parse(self):
        pkt = [0x30] * 24
        pkt[0] = STX
        pkt[1] = TP_FOOTBALL
        pkt[2] = ord("0") | 0x80
        pkt[3] = ord("7") | 0x80
        pkt[4] = ord("3") | 0x80
        pkt[5] = ord("0")
        pkt[6] = ord("3")  # quarter
        pkt[7] = ord("2")
        pkt[8] = ord("1")
        pkt[9] = ord("1")
        pkt[10] = ord("4")
        pkt[11] = ord("3") | 0x80
        pkt[12] = ord("3") | 0x80
        pkt[13] = 0xB8  # home possession
        pkt[14] = 0x30
        pkt[15] = ord("2")
        pkt[16] = 0x3A
        pkt[17] = ord("5")
        pkt[18] = ord("4")
        pkt[19] = ord("5")
        pkt[20] = ord("1")
        pkt[21] = ord("5")
        pkt[-1] = CR
        result = parse_football_data(pkt)
        assert "error" not in result
        assert result["quarter"] == "3"
        assert result["possession"] == "home"


class TestIdentifyAndParse:
    def test_basketball_routing(self):
        pkt = [0x30] * BBALL_LEN
        pkt[0] = STX
        pkt[1] = TP_BBALL_BASE_SOFT
        pkt[-1] = CR
        sport, parsed = identify_and_parse(pkt)
        assert sport == "Basketball"
        assert parsed is not None

    def test_short_packet_rejected(self):
        sport, parsed = identify_and_parse([STX, TP_VOLLEYBALL])
        assert sport is None
        assert parsed is None

    def test_unknown_type_rejected(self):
        sport, parsed = identify_and_parse([STX, 0x01, 0x30, CR])
        assert sport is None
        assert parsed is None
