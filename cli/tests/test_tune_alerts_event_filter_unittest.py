import unittest

from axonopscli.components.tune_alerts import _is_event_metric_rule


class TestIsEventMetricRule(unittest.TestCase):
    """AxonOps stores log alerts (and some event-type metric alerts) under the
    `events` metric. Log alerts have no PromQL trailing threshold; the
    event-type ones do, but the events metric isn't queryable via query_range
    (server-side 500). Either way the tuner can't do anything useful with them,
    so they get filtered out with one short reason instead of producing a
    wall of `cannot parse expr` lines in the summary.
    """

    def test_log_alert_shape_with_message_and_source(self):
        # Log alerts seeded via log_alert_rule come back as
        # events{message=...,source=...} with no trailing threshold.
        self.assertTrue(_is_event_metric_rule(
            'events{message="\\"is now DOWN\\"",source="/var/log/cassandra/system.log"}'
        ))

    def test_event_metric_alert_with_threshold(self):
        # The pre-existing events{type=...} alerts (Failed Auth, DDL, JMX, ...)
        # do carry a trailing threshold, but events still can't be queried
        # via query_range — they should be filtered too.
        self.assertTrue(_is_event_metric_rule(
            "events{level='error',type='authentication'} >= 1.0"
        ))
        self.assertTrue(_is_event_metric_rule("events{type='jmx'} >= 10.0"))

    def test_leading_whitespace_tolerated(self):
        self.assertTrue(_is_event_metric_rule("   events{type='jmx'} >= 10.0"))

    def test_other_metrics_are_not_event_shape(self):
        self.assertFalse(_is_event_metric_rule(
            "cas_ClientRequest_Latency{consistency='LOCAL_QUORUM'} >= 1000"
        ))
        self.assertFalse(_is_event_metric_rule(
            "cas_Table_TombstoneScannedHistogram{keyspace='myks',scope='users'} >= 500"
        ))

    def test_similarly_named_metrics_are_not_matched(self):
        # Anchor on the full metric name so we don't false-positive on
        # something like `events_per_second{}` or `my_events{}`.
        self.assertFalse(_is_event_metric_rule("events_per_second{} >= 1"))
        self.assertFalse(_is_event_metric_rule("my_events{} >= 1"))

    def test_empty_and_none_are_not_event_shape(self):
        self.assertFalse(_is_event_metric_rule(""))
        self.assertFalse(_is_event_metric_rule(None))


if __name__ == "__main__":
    unittest.main()
