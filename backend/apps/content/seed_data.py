"""Default feeds.

Chosen for three reasons: they publish full RSS with real summaries, they cover
the topics the app offers, and they are stable. Only metadata and the
publisher's own syndication summary are ever stored — see Article's docstring
for the copyright reasoning.

The learner can disable any of these, or add their own, from the admin.
"""

SEED_SOURCES = [
    {
        "name": "BBC News — World",
        "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "homepage": "https://www.bbc.co.uk/news/world",
        "topic": "news",
    },
    {
        "name": "BBC News — Technology",
        "feed_url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "homepage": "https://www.bbc.co.uk/news/technology",
        "topic": "technology",
    },
    {
        "name": "BBC News — Science",
        "feed_url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "homepage": "https://www.bbc.co.uk/news/science_and_environment",
        "topic": "science",
    },
    {
        "name": "BBC News — Business",
        "feed_url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "homepage": "https://www.bbc.co.uk/news/business",
        "topic": "business",
    },
    {
        "name": "BBC News — Entertainment",
        "feed_url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
        "homepage": "https://www.bbc.co.uk/news/entertainment_and_arts",
        "topic": "movies",
    },
    {
        "name": "NASA Breaking News",
        "feed_url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "homepage": "https://www.nasa.gov/news/",
        "topic": "science",
    },
    {
        "name": "Ars Technica",
        "feed_url": "https://feeds.arstechnica.com/arstechnica/index",
        "homepage": "https://arstechnica.com/",
        "topic": "technology",
    },
    {
        "name": "The Guardian — Sport",
        "feed_url": "https://www.theguardian.com/uk/sport/rss",
        "homepage": "https://www.theguardian.com/uk/sport",
        "topic": "sports",
    },
]
