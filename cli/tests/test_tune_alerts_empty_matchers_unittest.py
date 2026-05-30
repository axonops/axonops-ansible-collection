import unittest

from axonopscli.components.tune_alerts import ExprRewriter


class TestDropEmptyMatchers(unittest.TestCase):
    """AxonOps seeds some default rules with placeholder matchers like
    events{host_id='',...}. The alert engine treats an empty host_id as "all
    hosts", but the raw query_range endpoint returns 500 for an empty-string
    label matcher. drop_empty_matchers removes such matchers from the QUERY
    expression so the sample query succeeds — the stored rule is left untouched.
    """

    def test_drops_leading_empty_matcher(self):
        out = ExprRewriter.drop_empty_matchers(
            "events{host_id='',level='error',type='authentication'}")
        self.assertEqual(out, "events{level='error',type='authentication'}")

    def test_drops_trailing_empty_matcher(self):
        out = ExprRewriter.drop_empty_matchers("events{type='jmx',host_id=''}")
        self.assertEqual(out, "events{type='jmx'}")

    def test_drops_only_matcher_leaving_empty_braces(self):
        out = ExprRewriter.drop_empty_matchers("events{host_id=''}")
        self.assertEqual(out, "events{}")

    def test_also_drops_empty_regex_match(self):
        out = ExprRewriter.drop_empty_matchers("events{host_id=~'',type='jmx'}")
        self.assertEqual(out, "events{type='jmx'}")

    def test_keeps_negated_empty_matcher(self):
        # scope!='' means "scope is non-empty" — a meaningful filter, not a
        # placeholder. It must survive.
        expr = "cas_Table_MaxPartitionSize{scope!='',keyspace='system',scope='peers'}"
        self.assertEqual(ExprRewriter.drop_empty_matchers(expr), expr)

    def test_no_empty_matchers_is_unchanged(self):
        expr = "cas_ClientRequest_Latency{function!='Min|Max',consistency='LOCAL_QUORUM',percentile='99thPercentile'}"
        self.assertEqual(ExprRewriter.drop_empty_matchers(expr), expr)

    def test_preserves_comma_in_value_when_dropping_a_sibling(self):
        # The value carries commas; dropping host_id='' must not split it.
        out = ExprRewriter.drop_empty_matchers(
            "cas_Table_Foo{host_id='',keyspace=~'a,b,c'}")
        self.assertEqual(out, "cas_Table_Foo{keyspace=~'a,b,c'}")


if __name__ == "__main__":
    unittest.main()
