from curling_score.detect import device


class TestTheDeviceAsked:
    def test_nothing_asked_adds_nothing_to_a_call(self, monkeypatch):
        monkeypatch.delenv(device.ENV_VAR, raising=False)
        assert device.chosen() is None
        assert device.kwargs() == {}

    def test_the_environment_names_one_for_every_detector(self, monkeypatch):
        monkeypatch.setenv(device.ENV_VAR, "mps")
        assert device.chosen() == "mps"
        assert device.kwargs() == {"device": "mps"}

    def test_a_callers_own_device_wins(self, monkeypatch):
        monkeypatch.setenv(device.ENV_VAR, "mps")
        assert device.chosen("cpu") == "cpu"

    def test_use_sets_it_and_none_leaves_it(self, monkeypatch):
        # Set, then unset: `use` writes the environment itself, and only a
        # variable monkeypatch has touched is put back afterwards.
        monkeypatch.setenv(device.ENV_VAR, "cpu")
        monkeypatch.delenv(device.ENV_VAR)
        device.use(None)
        assert device.chosen() is None
        device.use("mps")
        assert device.chosen() == "mps"
