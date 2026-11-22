"""Discovery filters must never recommend live streams, duplicates or Shorts."""
import unittest
from viralcut.discovery import rank_entries


class DiscoveryTests(unittest.TestCase):
    def video(self, **patch):
        return dict({'id': 'abcdefghijk', 'title': 'Наука интервью',
                     'duration': 1800, 'view_count': 50000}, **patch)

    def test_unsuitable_and_duplicate_entries(self):
        valid = self.video()
        entries = [valid, valid, self.video(id='bcdefghijkl', duration=30),
                   self.video(id='cdefghijklm', live_status='is_live'),
                   self.video(id='defghijklmn', title='Science interview'),
                   self.video(id='invalid!'), self.video(id='efghijklmno', duration=None)]
        self.assertEqual([v['id'] for v in rank_entries(entries, 'ru', 'views')], ['abcdefghijk'])

    def test_unknown_views_are_not_invented(self):
        result = rank_entries([self.video(view_count=None)], 'ru', 'recommended')
        self.assertIsNone(result[0]['views'])

    def test_sorting_and_english_selection(self):
        entries = [self.video(title='Science podcast', view_count=10),
                   self.video(id='bcdefghijkl', title='Another interview', view_count=100)]
        result = rank_entries(entries, 'en', 'views')
        self.assertEqual(result[0]['views'], 100)
        self.assertEqual(result[0]['url'], 'https://www.youtube.com/watch?v=bcdefghijkl')


if __name__ == '__main__':
    unittest.main()
