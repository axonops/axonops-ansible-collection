import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from axonopscli.components.apply_tuned_alerts import AlertsApplier, _MAX_POST_ATTEMPTS
from axonopscli.utils import HTTPCodeError


def _applier():
    ax = MagicMock()
    ax.get_cluster_type.return_value = "cassandra"
    args = SimpleNamespace(org="acme", cluster="demo", v=0)
    return AlertsApplier(ax, args), ax


def _one_rule_input():
    return {
        "name": "demo",
        "metricrules": [{
            "id": "r1",
            "alert": "CPU usage per host",
            "expr": "x >= 1",
            "operator": ">=",
            "warningValue": 1,
            "criticalValue": 2,
        }],
    }


class TestApplyRetriesTransient(unittest.TestCase):
    """A 502/503/504 is a gateway timeout — the POST upserts by rule id, so
    retrying it is safe. Other statuses (4xx) and non-HTTP errors are not
    retried. time.sleep is patched so tests don't actually wait."""

    def test_retries_504_then_succeeds(self):
        applier, ax = _applier()
        calls = {"n": 0}

        def side_effect(*a, **k):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise HTTPCodeError("gateway timeout", status_code=504)
            return {}

        ax.do_request.side_effect = side_effect
        with patch("axonopscli.components.apply_tuned_alerts.time.sleep") as slept:
            result = applier.apply(_one_rule_input(), dry_run=False,
                                   continue_on_error=False, allow_redacted=True)

        self.assertEqual(ax.do_request.call_count, 3)
        self.assertEqual(result.applied, ["CPU usage per host"])
        self.assertEqual(result.failed, [])
        self.assertTrue(slept.called)

    def test_gives_up_after_max_attempts(self):
        applier, ax = _applier()
        ax.do_request.side_effect = HTTPCodeError("gw", status_code=504)
        with patch("axonopscli.components.apply_tuned_alerts.time.sleep"):
            with self.assertRaises(HTTPCodeError):
                applier.apply(_one_rule_input(), dry_run=False,
                              continue_on_error=False, allow_redacted=True)
        self.assertEqual(ax.do_request.call_count, _MAX_POST_ATTEMPTS)

    def test_persistent_504_recorded_when_continue_on_error(self):
        applier, ax = _applier()
        ax.do_request.side_effect = HTTPCodeError("gw", status_code=504)
        with patch("axonopscli.components.apply_tuned_alerts.time.sleep"):
            result = applier.apply(_one_rule_input(), dry_run=False,
                                   continue_on_error=True, allow_redacted=True)
        self.assertEqual(ax.do_request.call_count, _MAX_POST_ATTEMPTS)
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.applied, [])

    def test_does_not_retry_4xx(self):
        applier, ax = _applier()
        ax.do_request.side_effect = HTTPCodeError("bad request", status_code=400)
        with patch("axonopscli.components.apply_tuned_alerts.time.sleep") as slept:
            with self.assertRaises(HTTPCodeError):
                applier.apply(_one_rule_input(), dry_run=False,
                              continue_on_error=False, allow_redacted=True)
        self.assertEqual(ax.do_request.call_count, 1)
        self.assertFalse(slept.called)

    def test_does_not_retry_non_http_error(self):
        applier, ax = _applier()
        ax.do_request.side_effect = ValueError("boom")
        with patch("axonopscli.components.apply_tuned_alerts.time.sleep"):
            with self.assertRaises(ValueError):
                applier.apply(_one_rule_input(), dry_run=False,
                              continue_on_error=False, allow_redacted=True)
        self.assertEqual(ax.do_request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
