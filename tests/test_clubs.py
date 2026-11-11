"""A club's profiles: which one reads which sheet."""
from curling_score import clubs

# Each sheet's channel, read from a stream of it on 2026-11-11: Go_JOSxJPsQ,
# Df66u7Sv84c, R-7qQORH0dQ and Vu6sd-fo0PE.
ROCHESTER_CHANNELS = {"A": "UCC4CItKubmNVSPpsDInEcWQ", "B": "UCeANiSRDAxfXybHkgQ0iY4w",
                      "C": "UCsAcOSWFFZDKce1DL5umYOA", "D": "UCBhd8WiPmssoGcoYVSGcXJQ"}


class TestForSheet:
    def test_rochester_s_channel_picks_the_sheet_s_own_profile(self):
        want = {"A": clubs.ROCHESTER, "B": clubs.ROCHESTER_B, "C": clubs.ROCHESTER_C, "D": clubs.ROCHESTER_D}
        for sheet, channel in ROCHESTER_CHANNELS.items():
            got = clubs.for_sheet(clubs.ROCHESTER, channel)
            assert got is want[sheet] and got.sheet == sheet

    def test_whichever_of_its_profiles_the_run_was_told(self):
        # --club rochester-b on a sheet D stream is still sheet D.
        for told in (clubs.ROCHESTER_B, clubs.ROCHESTER_BD, clubs.ROCHESTER_C):
            assert clubs.for_sheet(told, ROCHESTER_CHANNELS["D"]) is clubs.ROCHESTER_D

    def test_a_channel_it_does_not_know_keeps_the_profile(self):
        assert clubs.for_sheet(clubs.ROCHESTER_B, "UCnobody") is clubs.ROCHESTER_B
        assert clubs.for_sheet(clubs.ROCHESTER, None) is clubs.ROCHESTER

    def test_a_club_with_one_profile_is_itself(self):
        assert clubs.for_sheet(clubs.GRANITE, ROCHESTER_CHANNELS["A"]) is clubs.GRANITE
        assert clubs.GRANITE.sheet is None

    def test_a_club_s_sheets_share_its_models_and_never_pick_the_club(self):
        # A worker loads one overhead model, for the club it was set up with:
        # the channel may choose among that club's sheets, not change the model.
        for club in clubs.CLUBS.values():
            for _sheet, name in (club.sheet_channels or {}).values():
                other = clubs.CLUBS[name]
                assert (other.overhead_model, other.side_model) == (club.overhead_model, club.side_model)
                assert other.sheet_channels == club.sheet_channels
            assert not (club.sheet_channels and club.channel_ids), club.name


class TestTheSheetOnTheTimeline:
    def info(self, sheet=None, channel=ROCHESTER_CHANNELS["C"]):
        from curling_score.ingest.source import VideoInfo
        return VideoInfo("R-7qQORH0dQ", "2026-11-09 Mon Open - Aimi, Steven VS. Curtis, James", 7800.0,
                         True, False, None, sheet, channel)

    def test_a_title_with_no_sheet_takes_the_profile_s(self):
        from curling_score import analyze
        assert analyze.sheet_for(None, self.info(), clubs.ROCHESTER_C) == "C"
        assert analyze.sheet_for(None, self.info(), clubs.GRANITE) is None

    def test_the_title_s_number_and_the_caller_s_word_come_first(self):
        from curling_score import analyze
        assert analyze.sheet_for(None, self.info(sheet=2), clubs.ROCHESTER_C) == 2
        assert analyze.sheet_for(4, self.info(sheet=2), clubs.ROCHESTER_C) == 4

    def test_the_cli_reads_a_sheet_by_its_channel(self, monkeypatch, tmp_path):
        from curling_score import cli
        seen = {}
        monkeypatch.setattr(cli.source, "fetch_info", lambda url: self.info())
        monkeypatch.setattr(cli.analyze_mod, "analyze", lambda url, **kw: seen.update(kw) or {"games": []})
        monkeypatch.setattr(cli.analyze_mod, "write", lambda doc, out: tmp_path / "timeline.json")
        assert cli.main(["analyze", "u", "--out", str(tmp_path), "--club", "rochester"]) == 0
        assert seen["club"] is clubs.ROCHESTER_C and seen["info"].channel_id == ROCHESTER_CHANNELS["C"]

    def test_the_cli_asks_youtube_nothing_extra_for_a_club_of_one_profile(self, monkeypatch, tmp_path):
        from curling_score import cli
        seen = {}
        monkeypatch.setattr(cli.source, "fetch_info", lambda url: 1 / 0)
        monkeypatch.setattr(cli.analyze_mod, "analyze", lambda url, **kw: seen.update(kw) or {"games": []})
        monkeypatch.setattr(cli.analyze_mod, "write", lambda doc, out: tmp_path / "timeline.json")
        assert cli.main(["analyze", "u", "--out", str(tmp_path)]) == 0
        assert seen["club"] is clubs.GRANITE and seen["info"] is None
