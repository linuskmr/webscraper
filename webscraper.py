import asyncio
import dataclasses
from datetime import datetime, timedelta
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import List, Dict, Tuple

import httpx
from bs4 import BeautifulSoup


@dataclass
class DifferentiatingElement:
    """A element that has differences between to timestamps."""

    old: BeautifulSoup
    new: BeautifulSoup


@dataclass
class UrlDiff:
    """A difference of a URL at two timestamps."""

    url: str
    """The URL that was diff'ed."""

    differentiating_elements: List[DifferentiatingElement]
    """The elements that have different content."""

    old_timestamp: str
    """The iso timestamp of the old version of the webpage."""

    new_timestamp: str
    """The iso timestamp of the new version of the webpage."""


@dataclass
class CacheEntry:
    """A cache entry for a URL. This stores at which the time the URL had which content."""

    html: str
    """The HTML content of the URL."""

    timestamp: str
    """The iso timestamp of the HTML content."""


Cache = Dict[str, CacheEntry]
"""The cache is a mapping from URLs to CacheEntry's, stored in the cache.json file."""


class EnhancedJSONEncoder(json.JSONEncoder):
    """Enhanced JSON encoder that can handle dataclasses and datetime objects.
    From https://stackoverflow.com/a/51286749/14350146
    """
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def compare_html(old_html: BeautifulSoup, new_html: BeautifulSoup) -> List[DifferentiatingElement]:
    """Compares two BeautifulSoup DOM trees recursively and returns the differing elements."""

    if old_html == new_html:
        # Html is equal; no differences
        return []

    # HTML DOMs differ, so try to find the differentiating children
    diff = []
    old_children = old_html.findChildren(recursive=False)
    new_children = new_html.findChildren(recursive=False)
    for old_child, new_child in zip(old_children, new_children):
        diff.extend(compare_html(old_child, new_child))

    # If there are no differentiating children, the differentiating element is the current one
    if not diff:
        return [DifferentiatingElement(old_html, new_html)]
    else:
        return diff


async def diff_url(client: httpx.AsyncClient, url: str, cache: Cache) -> UrlDiff:
    """Fetches an url, updates the corresponding cache entry and returns the the differences."""

    # Fetch new html content
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    new_html_str = response.text

    # Get old html content from cache
    old_cache_entry = cache.get(url, {})
    old_html_str = old_cache_entry.get('html', '')

    # Parse html strings as BeautifulSoup DOM trees
    old_html = BeautifulSoup(old_html_str, 'html.parser')
    new_html = BeautifulSoup(new_html_str, 'html.parser')

    # Compare old and new html content recursive
    differentiating_elements = compare_html(old_html, new_html)

    # Save the new html content for the next run
    cache[url] = CacheEntry(html=new_html_str, timestamp=datetime.now().isoformat())

    return UrlDiff(
        url=url,
        differentiating_elements=differentiating_elements,
        old_timestamp=old_cache_entry.get('timestamp', datetime.min),
        new_timestamp=datetime.now().isoformat(),
    )

async def do_diff(urls: List[str]):
    print(f'Checking {urls=}', file=sys.stderr)

    # Read last contents of monitored urls from cache
    cache_path = Path('cache.json')
    try:
        cache: Cache = json.loads(cache_path.read_text())
    except FileNotFoundError:
        cache: Cache = {}

    # Fetch all monitored urls, compare differences, and update cache entries
    async with httpx.AsyncClient() as client:
        url_diffs: List[UrlDiff] = await asyncio.gather(
            *[diff_url(client, url, cache) for url in urls]
        )

    # Print differences
    for url_diff in url_diffs:
        if not url_diff.differentiating_elements:
            continue
        print(f'CHANGE {url_diff.url}')
        print(f'OLD: {url_diff.old_timestamp}')
        print(f'NEW: {url_diff.new_timestamp}')
        for change in url_diff.differentiating_elements:
            print(f'WAS at {url_diff.old_timestamp}')
            print(change.old)
            print(f'IS NOW at {url_diff.new_timestamp}')
            print(change.new)
        print('\n' * 3)

    # Save new contents of monitored urls to cache
    cache_path.write_text(json.dumps(cache, indent=4, cls=EnhancedJSONEncoder))


async def main():
    while True:
        print(f'Fetching now {datetime.now()}', file=sys.stderr)
        config = json.loads(Path('config.json').read_text())
        await do_diff(config['urls'])

        delay = timedelta(minutes=int(config['interval_in_minutes']))
        print(f'Waiting {delay} for next fetch', file=sys.stderr)
        await asyncio.sleep(delay.seconds)


if __name__ == '__main__':
    asyncio.run(main())
