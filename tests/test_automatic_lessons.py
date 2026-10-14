import copy
import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import automatic_lessons as lessons

FEED = {'groups': [{'title': 'Standard Adult', 'resources': [
    {'title': 'Synthetic quarterly', 'name': '2026-01', 'index': 'en/ss/2026-01', 'startDate': '27/12/2025', 'endDate': '27/03/2026'}]}]}
SECTIONS = {'sections': [{'documents': [
    {'title': 'Synthetic first week', 'name': '01', 'startDate': '27/12/2025', 'endDate': '02/01/2026'},
    {'title': 'Synthetic second week', 'name': '02', 'startDate': '03/01/2026', 'endDate': '09/01/2026'}]}]}

class AutomaticLessonTests(unittest.TestCase):
    def setUp(self): lessons._cache.clear()
    def test_published_dates_handle_new_year_and_daily_offsets(self):
        for day, suffix in [(date(2025,12,27),'/01'),(date(2026,1,1),'/06'),(date(2026,1,2),'/07')]:
            result=lessons.select_current(day, FEED, lambda _: SECTIONS)
            self.assertTrue(result['daily_url'].endswith('/2026-01/01'+suffix))
            self.assertEqual(result['week_title'],'Synthetic first week')
        self.assertTrue(lessons.select_current(date(2026,1,3),FEED,lambda _:SECTIONS)['daily_url'].endswith('/02/01'))
    def test_unpublished_and_ambiguous_dates_are_not_guessed(self):
        with self.assertRaises(ValueError):lessons.select_current(date(2027,1,1),FEED,lambda _:SECTIONS)
        feed=copy.deepcopy(FEED);feed['groups'][0]['resources']*=2
        with self.assertRaises(ValueError):lessons.select_current(date(2026,1,1),feed,lambda _:SECTIONS)
    def test_publisher_paths_and_week_dates_are_validated(self):
        feed=copy.deepcopy(FEED);feed['groups'][0]['resources'][0]['index']='https://untrusted.invalid/'
        with self.assertRaises(ValueError):lessons.select_current(date(2026,1,1),feed,lambda _:SECTIONS)
        sections=copy.deepcopy(SECTIONS);sections['sections'][0]['documents'][0]['endDate']='03/01/2026'
        with self.assertRaises(ValueError):lessons.select_current(date(2026,1,1),FEED,lambda _:sections)
        with self.assertRaises(ValueError):lessons.fetch_metadata('../untrusted')
    def test_cache_avoids_repeat_requests_and_rolls_on_the_new_day(self):
        calls=[]
        def fetch(path):calls.append(path);return FEED if path=='en/ss/index.json' else SECTIONS
        first=lessons.current_lesson(date(2026,1,1),fetch)
        self.assertEqual(lessons.current_lesson(date(2026,1,1),fetch),first);self.assertEqual(len(calls),2)
        next_day=lessons.current_lesson(date(2026,1,2),fetch)
        self.assertEqual(len(calls),4);self.assertNotEqual(first['daily_url'],next_day['daily_url'])
    def test_provider_failure_is_honest_and_excludes_internal_details(self):
        def fail(_):raise TimeoutError('private diagnostic detail')
        result=lessons.current_lesson(date(2026,1,1),fail)
        self.assertFalse(result['available']);self.assertEqual(result['publisher_url'],'https://absg.sspmadventist.org/this-week')
        self.assertNotIn('private diagnostic',str(result));self.assertNotIn('week_title',result)
    def test_cache_contains_metadata_without_lesson_bodies(self):
        feed=copy.deepcopy(FEED);feed['groups'][0]['resources'][0]['description']='not for redistribution'
        sections=copy.deepcopy(SECTIONS);sections['sections'][0]['documents'][0]['content']='not for redistribution'
        result=lessons.current_lesson(date(2026,1,1),lambda path:feed if path=='en/ss/index.json' else sections)
        self.assertNotIn('not for redistribution',str(result));self.assertNotIn('not for redistribution',str(lessons._cache))

if __name__=='__main__':unittest.main()
