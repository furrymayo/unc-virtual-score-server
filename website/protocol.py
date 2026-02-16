# Serial protocol constants (mirrors C# implementation)
STX = 0x02
CR = 0x0D
ASCII_LOWER = 32

TP_BBALL_BASE_SOFT = 0x74  # 't'
TP_FOOTBALL = 0x66  # 'f'
TP_VOLLEYBALL = 0x76  # 'v'
TP_LACROSSE_FH = 0x6C  # 'l'
TP_WRESTLING = 0x77  # 'w'
TP_SOCCER = 0x73  # 's'

BBALL_LEN = 23
BASE_LEN = 52
SOFT_LEN = 75
LAX_LEN = 47
FH_LEN = 51


class PacketStreamParser:
    def __init__(self):
        self.state = 0
        self.packet = []

    def feed_bytes(self, data):
        packets = []
        for oes_char in data:
            if self.state == 0:
                if oes_char == STX:
                    self.packet = [oes_char]
                    self.state = 1
            elif self.state == 1:
                if oes_char in {
                    TP_BBALL_BASE_SOFT,
                    TP_FOOTBALL,
                    TP_VOLLEYBALL,
                    TP_LACROSSE_FH,
                    TP_WRESTLING,
                    TP_SOCCER,
                }:
                    self.packet.append(oes_char)
                    self.state = 2
                else:
                    self.packet = []
                    self.state = 0
            else:
                if oes_char >= ASCII_LOWER:
                    self.packet.append(oes_char)
                elif oes_char == CR:
                    self.packet.append(oes_char)
                    packets.append(self.packet)
                    self.packet = []
                    self.state = 0
                else:
                    self.packet = []
                    self.state = 0

        return packets


# --- Decoder helpers ---

def _decode_score(tens_byte, ones_byte):
    if tens_byte >= 176:
        tens = chr(tens_byte & 0x7F)
        ones = chr(ones_byte & 0x7F)
        return f"1{tens}{ones}"

    tens_char = " " if tens_byte == 0x3A else chr(tens_byte)
    return f"{tens_char}{chr(ones_byte)}"


def _decode_clock(min_tens, min_ones, sec_tens, sec_ones):
    if sec_ones == 0x3A:
        if min_tens == 0x3A:
            return f" 0{chr(min_ones)}.{chr(sec_tens)}"
        return f" {chr(min_tens)}{chr(min_ones)}.{chr(sec_tens)}"

    if min_tens == 0x3A:
        return f" {chr(min_ones)}:{chr(sec_tens)}{chr(sec_ones)}"

    return f"{chr(min_tens)}{chr(min_ones)}:{chr(sec_tens)}{chr(sec_ones)}"


def _decode_shot_clock(ms_byte, ls_byte):
    ms = 0x20 if ms_byte == 0x3A else ms_byte
    return f"{chr(ms)}{chr(ls_byte)}"


def _decode_penalty_time(min_byte, sec_tens_byte, sec_ones_byte):
    if sec_ones_byte == 0x3A:
        return f" {chr(min_byte)}{chr(sec_tens_byte)}{chr(sec_ones_byte)}"
    return f" {chr(min_byte)}:{chr(sec_tens_byte)}{chr(sec_ones_byte)}"


def _decode_simple_time(min_byte, sec_tens_byte, sec_ones_byte):
    return f"{chr(min_byte)}:{chr(sec_tens_byte)}{chr(sec_ones_byte)}"


# --- Sport parsers ---

def parse_basketball_data(packet):
    try:
        game_clock = _decode_clock(
            packet[2] & 0x7F, packet[3] & 0x7F, packet[4] & 0x7F, packet[5]
        )
        period = chr(packet[6])
        if period.isdigit() and int(period) > 4:
            period = "OT"

        home_score = _decode_score(packet[7], packet[8])
        visitor_score = _decode_score(packet[9], packet[10])

        hm_values = packet[16] - 0x30
        vs_values = packet[17] - 0x30
        hm_poss = hm_values & 0x01
        vs_poss = vs_values & 0x01
        hm_bonus = (hm_values & 0x02) > 0
        vs_bonus = (vs_values & 0x02) > 0
        hm_20_tol = (hm_values & 0x0C) // 4
        vs_20_tol = (vs_values & 0x0C) // 4

        hm_tol = chr(packet[11] & 0x7F)
        vs_tol = chr(packet[12] & 0x7F)

        hm_fouls = packet[13]
        if hm_fouls > 0x3A:
            hm_fouls_str = "10"
        elif hm_fouls == 0x3A:
            hm_fouls_str = " "
        else:
            hm_fouls_str = chr(hm_fouls)

        vs_fouls = packet[14]
        if vs_fouls > 0x3A:
            vs_fouls_str = "10"
        elif vs_fouls == 0x3A:
            vs_fouls_str = " "
        else:
            vs_fouls_str = chr(vs_fouls)

        shot_clock = _decode_shot_clock(packet[18], packet[19])

        possession = None
        if hm_poss == 0x01:
            possession = "home"
        elif vs_poss == 0x01:
            possession = "visitor"

        return {
            "game_clock": game_clock,
            "period": period,
            "home_score": home_score,
            "visitor_score": visitor_score,
            "home_full_tol": hm_tol,
            "visitor_full_tol": vs_tol,
            "home_20_tol": hm_20_tol,
            "visitor_20_tol": vs_20_tol,
            "home_fouls": hm_fouls_str,
            "visitor_fouls": vs_fouls_str,
            "shot_clock": shot_clock,
            "home_bonus": hm_bonus,
            "visitor_bonus": vs_bonus,
            "possession": possession,
        }
    except Exception as exc:
        return {"error": f"Basketball parse error: {exc}"}


def parse_football_data(packet):
    try:
        game_clock = _decode_clock(
            packet[2] & 0x7F, packet[3] & 0x7F, packet[4] & 0x7F, packet[5]
        )
        quarter = chr(packet[6])
        if quarter.isdigit() and int(quarter) > 4:
            quarter = "OT"

        home_score = _decode_score(packet[7], packet[8])
        visitor_score = _decode_score(packet[9], packet[10])

        hm_poss = packet[13]
        vs_poss = packet[14]

        hm_tol = chr(packet[11] & 0x7F)
        vs_tol = chr(packet[12] & 0x7F)

        shot_clock = _decode_shot_clock(packet[20], packet[21])
        down = chr(packet[15])

        ytg10s = packet[16]
        ytg1s = packet[17]
        if ytg10s == 0x3A:
            ytg10s = 0x20
        yards_to_go = f"{chr(ytg10s)}{chr(ytg1s)}"

        ball_on10s = packet[18]
        ball_on1s = packet[19]
        if ball_on10s == 0x3A:
            ball_on10s = 0x20
        ball_on = f"{chr(ball_on10s)}{chr(ball_on1s)}"

        possession = None
        if hm_poss == 0xB8:
            possession = "home"
        elif vs_poss == 0xB8:
            possession = "visitor"

        return {
            "game_clock": game_clock,
            "quarter": quarter,
            "home_score": home_score,
            "visitor_score": visitor_score,
            "home_full_tol": hm_tol,
            "visitor_full_tol": vs_tol,
            "shot_clock": shot_clock,
            "down": down,
            "yards_to_go": yards_to_go,
            "ball_on": ball_on,
            "possession": possession,
        }
    except Exception as exc:
        return {"error": f"Football parse error: {exc}"}


def parse_volleyball_data(packet):
    try:
        game_clock = _decode_clock(
            packet[2] & 0x7F, packet[3] & 0x7F, packet[4] & 0x7F, packet[5]
        )
        period = chr(packet[6])
        home_score = _decode_score(packet[7], packet[8])
        visitor_score = _decode_score(packet[9], packet[10])
        hm_tol = chr(packet[11] & 0x7F)
        vs_tol = chr(packet[12] & 0x7F)

        hm_values = packet[16] - 0x30
        vs_values = packet[17] - 0x30
        hm_poss = hm_values & 0x01
        vs_poss = vs_values & 0x01

        hm_sets_won = chr(packet[18])
        vs_sets_won = chr(packet[19])

        hm_set_scores = [
            _decode_score(packet[20], packet[21]),
            _decode_score(packet[22], packet[23]),
            _decode_score(packet[24], packet[25]),
            _decode_score(packet[26], packet[27]),
            _decode_score(packet[28], packet[29]),
        ]

        vs_set_scores = [
            _decode_score(packet[30], packet[31]),
            _decode_score(packet[32], packet[33]),
            _decode_score(packet[34], packet[35]),
            _decode_score(packet[36], packet[37]),
            _decode_score(packet[38], packet[39]),
        ]

        possession = None
        if hm_poss == 0x01:
            possession = "home"
        elif vs_poss == 0x01:
            possession = "visitor"

        return {
            "game_clock": game_clock,
            "period": period,
            "home_score": home_score,
            "visitor_score": visitor_score,
            "home_full_tol": hm_tol,
            "visitor_full_tol": vs_tol,
            "home_sets_won": hm_sets_won,
            "visitor_sets_won": vs_sets_won,
            "home_set_scores": hm_set_scores,
            "visitor_set_scores": vs_set_scores,
            "possession": possession,
        }
    except Exception as exc:
        return {"error": f"Volleyball parse error: {exc}"}


def parse_soccer_data(packet):
    try:
        game_clock = _decode_clock(
            packet[2] & 0x7F, packet[3] & 0x7F, packet[4] & 0x7F, packet[5]
        )
        period = chr(packet[6])
        home_score = _decode_score(packet[7], packet[8])
        visitor_score = _decode_score(packet[9], packet[10])

        hm_shots = _decode_score(packet[11], packet[12])
        hm_saves = _decode_score(packet[13], packet[14])
        hm_corners = _decode_score(packet[15], packet[16])
        hm_penalties = _decode_score(packet[17], packet[18])

        vs_shots = _decode_score(packet[19], packet[20])
        vs_saves = _decode_score(packet[21], packet[22])
        vs_corners = _decode_score(packet[23], packet[24])
        vs_penalties = _decode_score(packet[25], packet[26])

        return {
            "game_clock": game_clock,
            "period": period,
            "home_score": home_score,
            "visitor_score": visitor_score,
            "home_shots": hm_shots,
            "home_saves": hm_saves,
            "home_corners": hm_corners,
            "home_penalties": hm_penalties,
            "visitor_shots": vs_shots,
            "visitor_saves": vs_saves,
            "visitor_corners": vs_corners,
            "visitor_penalties": vs_penalties,
        }
    except Exception as exc:
        return {"error": f"Soccer parse error: {exc}"}


def parse_lacrosse_data(packet):
    try:
        game_clock = _decode_clock(
            packet[2] & 0x7F, packet[3] & 0x7F, packet[4] & 0x7F, packet[5]
        )
        period = chr(packet[6])
        home_score = _decode_score(packet[7], packet[8])
        visitor_score = _decode_score(packet[9], packet[10])
        home_tol = chr(packet[16] & 0x7F)
        visitor_tol = chr(packet[17] & 0x7F)

        home_shots = _decode_score(packet[18], packet[19])
        visitor_shots = _decode_score(packet[20], packet[21])

        hm_pen1_player = (
            f"{(' ' if packet[22] == 0x3A else chr(packet[22]))}{chr(packet[23])}"
        )
        hm_pen1_time = _decode_penalty_time(
            packet[24] & 0x7F, packet[25] & 0x7F, packet[26]
        )
        hm_pen2_player = (
            f"{(' ' if packet[27] == 0x3A else chr(packet[27]))}{chr(packet[28])}"
        )
        hm_pen2_time = _decode_penalty_time(
            packet[29] & 0x7F, packet[30] & 0x7F, packet[31]
        )

        vs_pen1_player = (
            f"{(' ' if packet[32] == 0x3A else chr(packet[32]))}{chr(packet[33])}"
        )
        vs_pen1_time = _decode_penalty_time(
            packet[34] & 0x7F, packet[35] & 0x7F, packet[36]
        )
        vs_pen2_player = (
            f"{(' ' if packet[37] == 0x3A else chr(packet[37]))}{chr(packet[38])}"
        )
        vs_pen2_time = _decode_penalty_time(
            packet[39] & 0x7F, packet[40] & 0x7F, packet[41]
        )

        shot_clock = _decode_shot_clock(packet[42], packet[43])

        return {
            "game_clock": game_clock,
            "period": period,
            "home_score": home_score,
            "visitor_score": visitor_score,
            "home_full_tol": home_tol,
            "visitor_full_tol": visitor_tol,
            "home_shots": home_shots,
            "visitor_shots": visitor_shots,
            "home_penalties": [
                {"player": hm_pen1_player, "time": hm_pen1_time},
                {"player": hm_pen2_player, "time": hm_pen2_time},
            ],
            "visitor_penalties": [
                {"player": vs_pen1_player, "time": vs_pen1_time},
                {"player": vs_pen2_player, "time": vs_pen2_time},
            ],
            "shot_clock": shot_clock,
        }
    except Exception as exc:
        return {"error": f"Lacrosse parse error: {exc}"}


def parse_hockey_data(packet):
    try:
        game_clock = _decode_clock(
            packet[2] & 0x7F, packet[3] & 0x7F, packet[4] & 0x7F, packet[5]
        )
        period = chr(packet[6])
        home_score = _decode_score(packet[7], packet[8])
        visitor_score = _decode_score(packet[9], packet[10])

        home_saves = f"{(' ' if packet[11] == 0x3A else chr(packet[11]))}{('0' if packet[12] == 0x3A else chr(packet[12]))}"
        visitor_saves = f"{(' ' if packet[13] == 0x3A else chr(packet[13]))}{('0' if packet[14] == 0x3A else chr(packet[14]))}"

        home_shots = _decode_score(packet[18], packet[19])
        visitor_shots = _decode_score(packet[20], packet[21])

        hm_pen1_player = (
            f"{(' ' if packet[22] == 0x3A else chr(packet[22]))}{chr(packet[23])}"
        )
        hm_pen1_time = _decode_penalty_time(
            packet[24] & 0x7F, packet[25] & 0x7F, packet[26]
        )
        hm_pen2_player = (
            f"{(' ' if packet[27] == 0x3A else chr(packet[27]))}{chr(packet[28])}"
        )
        hm_pen2_time = _decode_penalty_time(
            packet[29] & 0x7F, packet[30] & 0x7F, packet[31]
        )

        vs_pen1_player = (
            f"{(' ' if packet[32] == 0x3A else chr(packet[32]))}{chr(packet[33])}"
        )
        vs_pen1_time = _decode_penalty_time(
            packet[34] & 0x7F, packet[35] & 0x7F, packet[36]
        )
        vs_pen2_player = (
            f"{(' ' if packet[37] == 0x3A else chr(packet[37]))}{chr(packet[38])}"
        )
        vs_pen2_time = _decode_penalty_time(
            packet[39] & 0x7F, packet[40] & 0x7F, packet[41]
        )

        home_corners = f"{(' ' if packet[42] == 0x3A else chr(packet[42]))}{('0' if packet[43] == 0x3A else chr(packet[43]))}"
        visitor_corners = f"{(' ' if packet[44] == 0x3A else chr(packet[44]))}{('0' if packet[45] == 0x3A else chr(packet[45]))}"

        return {
            "game_clock": game_clock,
            "period": period,
            "home_score": home_score,
            "visitor_score": visitor_score,
            "home_saves": home_saves,
            "visitor_saves": visitor_saves,
            "home_shots": home_shots,
            "visitor_shots": visitor_shots,
            "home_penalties": [
                {"player": hm_pen1_player, "time": hm_pen1_time},
                {"player": hm_pen2_player, "time": hm_pen2_time},
            ],
            "visitor_penalties": [
                {"player": vs_pen1_player, "time": vs_pen1_time},
                {"player": vs_pen2_player, "time": vs_pen2_time},
            ],
            "home_corners": home_corners,
            "visitor_corners": visitor_corners,
        }
    except Exception as exc:
        return {"error": f"Hockey parse error: {exc}"}


def parse_wrestling_data(packet):
    try:
        game_clock = _decode_clock(
            packet[2] & 0x7F, packet[3] & 0x7F, packet[4] & 0x7F, packet[5]
        )
        period = chr(packet[6])
        home_score = _decode_score(packet[7], packet[8])
        visitor_score = _decode_score(packet[9], packet[10])

        home_team_points = _decode_score(packet[18], packet[19])
        visitor_team_points = _decode_score(packet[20], packet[21])

        weight_class = f"{chr(packet[22])}{chr(packet[23])}{chr(packet[24])}"

        home_adv_time = _decode_simple_time(
            packet[25] & 0x7F, packet[26] & 0x7F, packet[27]
        )
        visitor_adv_time = _decode_simple_time(
            packet[28] & 0x7F, packet[29] & 0x7F, packet[30]
        )
        home_inj_time = _decode_simple_time(
            packet[34] & 0x7F, packet[35] & 0x7F, packet[36]
        )
        visitor_inj_time = _decode_simple_time(
            packet[37] & 0x7F, packet[38] & 0x7F, packet[39]
        )

        return {
            "game_clock": game_clock,
            "period": period,
            "home_score": home_score,
            "visitor_score": visitor_score,
            "home_team_points": home_team_points,
            "visitor_team_points": visitor_team_points,
            "match_weight_class": weight_class,
            "home_adv_time": home_adv_time,
            "visitor_adv_time": visitor_adv_time,
            "home_inj_time": home_inj_time,
            "visitor_inj_time": visitor_inj_time,
        }
    except Exception as exc:
        return {"error": f"Wrestling parse error: {exc}"}


def parse_baseball_data(packet):
    try:
        vs_runs = f"{(' ' if packet[33] == 0x3A else chr(packet[33]))}{chr(packet[34])}"
        vs_hits = f"{(' ' if packet[35] == 0x3A else chr(packet[35]))}{chr(packet[36])}"
        vs_errors = f" {chr(packet[37])}"

        hm_runs = f"{(' ' if packet[38] == 0x3A else chr(packet[38]))}{chr(packet[39])}"
        hm_hits = f"{(' ' if packet[40] == 0x3A else chr(packet[40]))}{chr(packet[41])}"
        hm_errors = f" {chr(packet[42])}"

        vs_innings = [
            chr(packet[2]),
            chr(packet[3]),
            chr(packet[4]),
            chr(packet[17]),
            chr(packet[18]),
            chr(packet[19]),
            chr(packet[20]),
            chr(packet[21]),
            chr(packet[22]),
            chr(packet[23]),
        ]
        hm_innings = [
            chr(packet[5]),
            chr(packet[6]),
            chr(packet[7]),
            chr(packet[24]),
            chr(packet[25]),
            chr(packet[26]),
            chr(packet[27]),
            chr(packet[28]),
            chr(packet[29]),
            chr(packet[30]),
        ]

        batter_num = f"{(' ' if packet[8] == 0x3A else chr(packet[8]))}{chr(packet[9])}"
        balls = chr(packet[10])
        strikes = chr(packet[31])
        outs = chr(packet[43])

        pitch_h = 0x30 if packet[46] == 0x3A else packet[46]
        pitch_t = 0x30 if packet[47] == 0x3A else packet[47]
        pitch_o = 0x30 if packet[48] == 0x3A else packet[48]
        pitch_speed = f"{chr(pitch_h)}{chr(pitch_t)}{chr(pitch_o)}"

        vs_innings = [(" " if b == ":" else b) for b in vs_innings]
        hm_innings = [(" " if b == ":" else b) for b in hm_innings]

        return {
            "away_innings": vs_innings,
            "home_innings": hm_innings,
            "balls": balls,
            "strikes": strikes,
            "outs": outs,
            "batter_num": batter_num,
            "pitch_speed": pitch_speed,
            "away_runs": vs_runs,
            "away_hits": vs_hits,
            "away_errors": vs_errors,
            "home_runs": hm_runs,
            "home_hits": hm_hits,
            "home_errors": hm_errors,
        }
    except Exception as exc:
        return {"error": f"Baseball parse error: {exc}"}


def parse_softball_data(packet):
    try:
        team_at_bat = chr(packet[2])
        batting_team = "TOP" if team_at_bat == "1" else "BOT"
        inning_tens = " " if packet[3] == 0x3A else chr(packet[3])
        inning_ones = " " if packet[4] == 0x3A else chr(packet[4])
        inning = f"{inning_tens}{inning_ones}"

        batter_num = f"{(' ' if packet[5] == 0x3A else chr(packet[5]))}{('0' if packet[6] == 0x3A else chr(packet[6]))}"
        batter_avg = f"{('0' if packet[7] == 0x3A else chr(packet[7]))}{('0' if packet[8] == 0x3A else chr(packet[8]))}{('0' if packet[9] == 0x3A else chr(packet[9]))}"

        pitcher_num = f"{(' ' if packet[10] == 0x3A else chr(packet[10]))}{('0' if packet[11] == 0x3A else chr(packet[11]))}"
        pitcher_count = f"{(' ' if packet[71] == 0x3A else chr(packet[71]))}{(' ' if packet[12] == 0x3A else chr(packet[12]))}{('0' if packet[13] == 0x3A else chr(packet[13]))}"

        pitch_h = 0x30 if packet[22] == 0x3A else packet[22]
        pitch_t = 0x30 if packet[23] == 0x3A else packet[23]
        pitch_o = 0x30 if packet[24] == 0x3A else packet[24]
        pitch_speed = f"{chr(pitch_h)}{chr(pitch_t)}{chr(pitch_o)}"

        balls = chr(packet[25])
        strikes = chr(packet[26])
        outs = chr(packet[27])

        last_play_type = packet[28]
        last_play_pos = packet[29]
        if last_play_type == 0x3A:
            last_play = "N/A"
        elif last_play_type == 0x49:
            last_play = "  H"
        else:
            last_play = "  E" if last_play_pos == 0x3A else f" E{chr(last_play_pos)}"

        vs_runs = f"{(' ' if packet[30] == 0x3A else chr(packet[30]))}{chr(packet[31])}"
        vs_hits = f"{(' ' if packet[32] == 0x3A else chr(packet[32]))}{chr(packet[33])}"
        vs_errors = f" {chr(packet[34])}"

        hm_runs = f"{(' ' if packet[35] == 0x3A else chr(packet[35]))}{chr(packet[36])}"
        hm_hits = f"{(' ' if packet[37] == 0x3A else chr(packet[37]))}{chr(packet[38])}"
        hm_errors = f" {chr(packet[39])}"

        vs_innings = [chr(packet[i]) for i in range(40, 50)]
        hm_innings = [chr(packet[i]) for i in range(50, 60)]
        vs_innings = [(" " if b == ":" else b) for b in vs_innings]
        hm_innings = [(" " if b == ":" else b) for b in hm_innings]

        return {
            "inning": inning,
            "batting_team": batting_team,
            "batter_num": batter_num,
            "batter_avg": batter_avg,
            "pitcher_num": pitcher_num,
            "pitcher_count": pitcher_count,
            "pitch_speed": pitch_speed,
            "balls": balls,
            "strikes": strikes,
            "outs": outs,
            "last_play": last_play,
            "away_runs": vs_runs,
            "away_hits": vs_hits,
            "away_errors": vs_errors,
            "home_runs": hm_runs,
            "home_hits": hm_hits,
            "home_errors": hm_errors,
            "away_innings": vs_innings,
            "home_innings": hm_innings,
        }
    except Exception as exc:
        return {"error": f"Softball parse error: {exc}"}


# --- Dispatch ---

def identify_and_parse(packet):
    """Identify sport from packet type+length and parse it.

    Returns (sport_name, parsed_dict) or (None, None).
    """
    if len(packet) < 3:
        return None, None

    packet_type = packet[1]

    if packet_type == TP_BBALL_BASE_SOFT:
        if len(packet) == BBALL_LEN:
            return "Basketball", parse_basketball_data(packet)
        elif len(packet) == BASE_LEN:
            return "Baseball", parse_baseball_data(packet)
        elif len(packet) == SOFT_LEN:
            return "Softball", parse_softball_data(packet)
    elif packet_type == TP_FOOTBALL:
        return "Football", parse_football_data(packet)
    elif packet_type == TP_VOLLEYBALL:
        return "Volleyball", parse_volleyball_data(packet)
    elif packet_type == TP_LACROSSE_FH:
        if len(packet) == LAX_LEN:
            return "Lacrosse", parse_lacrosse_data(packet)
        elif len(packet) == FH_LEN:
            return "Hockey", parse_hockey_data(packet)
    elif packet_type == TP_WRESTLING:
        return "Wrestling", parse_wrestling_data(packet)
    elif packet_type == TP_SOCCER:
        return "Soccer", parse_soccer_data(packet)

    return None, None
