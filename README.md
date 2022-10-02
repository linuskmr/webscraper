# webscraper

webscraper monitors websites for changes by scraping it in an interval.

It stores the last scraped version of the website in the `cache.json` file
and compares it to the newly fetched version. It is doing so by diffing the HTML
trees via [BeautifulSoup](https://pypi.org/project/beautifulsoup4/).
So, it only prints the bits that changed to the console.

The project was inspired by [distill.io](https://distill.io/).


## Install requirements

webscraper uses `httpx` for web requests and `beautifulsoup4` for HTML parsing. 

    $ pip install -r requirements.txt


## Usage

The `config.json` is used to configure the webscraper.

You can adjust the `urls` and the `interval_in_minutes` attributes.
The webscraper will automatically load the updated config on the next fetch.

    $ python3 webscraper.py
