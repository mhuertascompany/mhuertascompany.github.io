import json
import unittest
from unittest.mock import patch
from io import BytesIO

from update_ads_metrics import calculate_metrics, fetch_papers


class ADSMetricsTests(unittest.TestCase):
    def test_metrics_and_thresholds(self):
        papers = [{'bibcode': str(i), 'citation_count': c}
                  for i, c in enumerate([120, 100, 5, 4, 3, 0])]
        m = calculate_metrics(papers)
        self.assertEqual((m['papers'], m['citations'], m['h_index'], m['i100']), (6, 232, 4, 2))

    def test_no_citations(self):
        m = calculate_metrics([{'bibcode': 'a'}])
        self.assertEqual(m['h_index'], 0)
        self.assertEqual(m['citations'], 0)

    def test_invalid_results_are_rejected(self):
        for papers in ([], [{'bibcode': 'a'}, {'bibcode': 'a'}],
                       [{'bibcode': 'a', 'citation_count': -1}],
                       [{'bibcode': 'a', 'citation_count': '100'}]):
            with self.assertRaises(ValueError):
                calculate_metrics(papers)

    def test_pagination_and_authorization(self):
        def response(docs):
            return BytesIO(json.dumps({'response': {'numFound': 2, 'docs': docs}}).encode())
        with patch('update_ads_metrics.urlopen', side_effect=[response([{'bibcode': 'a'}]), response([{'bibcode': 'b'}])]) as request:
            papers = fetch_papers('test-token')
        self.assertEqual(len(papers), 2)
        self.assertIn('start=1', request.call_args_list[1].args[0].full_url)
        self.assertEqual(request.call_args_list[0].args[0].get_header('Authorization'), 'Bearer test-token')

    def test_empty_response_does_not_become_zero_metrics(self):
        response = BytesIO(json.dumps({'response': {'numFound': 0, 'docs': []}}).encode())
        with patch('update_ads_metrics.urlopen', return_value=response):
            with self.assertRaises(ValueError):
                fetch_papers('test-token')


if __name__ == '__main__':
    unittest.main()
