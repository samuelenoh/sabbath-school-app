"""Dated links to the official adult guide; never republishes lesson bodies."""
import json
import re
import threading
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

API_BASE = 'https://sabbath-school.adventech.io/api/v3/'
READER = 'https://absg.sspmadventist.org/'
_lock = threading.Lock()
_cache = {}

def published_date(value):
    return datetime.strptime(value, '%d/%m/%Y').date()

def fetch_metadata(path):
    # Only fixed publisher paths are requested; no member data or credentials leave the app.
    if not re.fullmatch(r'en/ss/(?:\d{4}-0[1-4]/sections/)?index\.json', path):
        raise ValueError('Unexpected publisher path')
    request = Request(API_BASE + path, headers={'User-Agent': 'SabbathSchoolManagement/1.0', 'Accept': 'application/json'})
    with urlopen(request, timeout=4) as response:
        if not response.geturl().startswith(API_BASE):
            raise ValueError('Unexpected publisher redirect')
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Publisher response too large')
    return json.loads(raw)

def select_current(day, feed, fetch=fetch_metadata):
    adult = next(group for group in feed['groups'] if group['title'] == 'Standard Adult')
    resources = [resource for resource in adult['resources']
                 if published_date(resource['startDate']) <= day <= published_date(resource['endDate'])]
    if len(resources) != 1:
        raise ValueError('No unique current publication')
    resource = resources[0]
    if not re.fullmatch(r'\d{4}-0[1-4]', resource['name']) or resource['index'] != 'en/ss/' + resource['name']:
        raise ValueError('Unexpected publication index')
    sections = fetch(resource['index'] + '/sections/index.json')
    documents = [document for section in sections['sections'] for document in section['documents']
                 if document.get('startDate') and document.get('endDate')
                 and published_date(document['startDate']) <= day <= published_date(document['endDate'])]
    if len(documents) != 1:
        raise ValueError('No unique current lesson')
    document = documents[0]
    if not re.fullmatch(r'\d{2}', document['name']):
        raise ValueError('Unexpected lesson index')
    start, end = published_date(document['startDate']), published_date(document['endDate'])
    if (end-start).days != 6 or start.weekday() != 5:
        raise ValueError('Unexpected lesson dates')
    for item in (resource, document):
        if not isinstance(item['title'], str) or not 1 <= len(item['title']) <= 250:
            raise ValueError('Invalid publication title')
    url = READER + 'en/' + resource['name'] + '/' + document['name']
    return {'available': True, 'day': day.isoformat(), 'language': 'English', 'edition': 'Standard Adult',
            'quarter_title': resource['title'], 'week_title': document['title'],
            'week_start': start.isoformat(), 'week_end': end.isoformat(), 'week_number': int(document['name']),
            'daily_url': url + '/' + str((day-start).days+1).zfill(2), 'weekly_url': url,
            'publisher_url': READER + 'this-week', 'source': 'General Conference · Adventech'}

def current_lesson(day=None, fetch=None):
    day = day or datetime.now(timezone.utc).date()  # Ghana/Accra has UTC dates year-round.
    fetch = fetch or fetch_metadata
    with _lock:
        now = time.monotonic()
        if _cache.get('day') == day and _cache.get('expires', 0) > now:
            return dict(_cache['result'])
        try:
            result = select_current(day, fetch('en/ss/index.json'), fetch)
            ttl = 900
        except Exception:
            result = {'available': False, 'day': day.isoformat(), 'language': 'English', 'edition': 'Standard Adult',
                      'publisher_url': READER + 'this-week', 'source': 'General Conference · Adventech',
                      'message': 'The current lesson details are temporarily unavailable. Open the publisher’s current study below.'}
            ttl = 300
        _cache.clear()
        _cache.update(day=day, expires=now+ttl, result=result)
        return dict(result)
