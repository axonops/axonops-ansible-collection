import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from axonopscli.components.tune_alerts import (
    TuneAlertsConfig, TuneAlertsOrchestrator, MetricQuerier,
)


def _config(days_back=7, **overrides):
    """Build a minimal TuneAlertsConfig for orchestrator window tests."""
    base = dict(
        profile="default", percentile=99.0,
        warning_headroom=0.10, critical_headroom=0.20,
        min_samples=100, max_delta=10.0,
        include=[], exclude=[], rules=[],
        days_back=days_back,
    )
    base.update(overrides)
    return TuneAlertsConfig(**base)


def _input(name="x"):
    return {"name": "c1", "metricrules": [{
        "id": "r1", "alert": name,
        "expr": "host_CPU{} >= 50.0",
        "operator": ">=", "warningValue": 50, "criticalValue": 80,
    }]}


def _args():
    return SimpleNamespace(org="o", cluster="c1", v=0, cluster_type="cassandra",
                           token="t", url=None, username=None, password=None)


class TestDaysBackWindow(unittest.TestCase):
    """The tune window is `now - days_back*86400 → now`. Default is 7 days,
    overridable to e.g. 30 to harvest more samples on sparse metric series."""

    def test_config_default_days_back_is_seven(self):
        c = _config()
        self.assertEqual(c.days_back, 7)

    def test_orchestrator_uses_days_back_for_window(self):
        # Capture (start_ts, end_ts) the orchestrator passes to the querier.
        seen = {}

        def fake_query(self, promql, start, end, step="1m"):
            seen["start"], seen["end"] = start, end
            return [1.0] * 200  # plenty of samples → tunes

        ax = MagicMock(); ax.get_cluster_type.return_value = "cassandra"
        cfg = _config(days_back=30)
        orch = TuneAlertsOrchestrator(ax, _args(), cfg)

        # Freeze time so the test is deterministic.
        with patch("axonopscli.components.tune_alerts.time.time", return_value=10_000_000), \
             patch.object(MetricQuerier, "query", new=fake_query):
            orch.tune_all(_input())

        self.assertEqual(seen["end"], 10_000_000)
        self.assertEqual(seen["start"], 10_000_000 - 30 * 86400)

    def test_orchestrator_default_window_is_seven_days(self):
        seen = {}

        def fake_query(self, promql, start, end, step="1m"):
            seen["start"], seen["end"] = start, end
            return [1.0] * 200

        ax = MagicMock(); ax.get_cluster_type.return_value = "cassandra"
        orch = TuneAlertsOrchestrator(ax, _args(), _config())  # default

        with patch("axonopscli.components.tune_alerts.time.time", return_value=10_000_000), \
             patch.object(MetricQuerier, "query", new=fake_query):
            orch.tune_all(_input())

        self.assertEqual(seen["start"], 10_000_000 - 7 * 86400)


if __name__ == "__main__":
    unittest.main()
