"""RSS and Atom parsing.

Pure functions over a string of XML: no network, no database. That makes feed
handling testable against fixtures rather than against the live internet.

**Why stdlib rather than feedparser:** the parsing we need is narrow — title,
link, id, date, summary — and `xml.etree` covers RSS 2.0 and Atom in about a
hundred lines. Adding a dependency for that conflicts with the project's rule
about unnecessary packages. If real feeds turn out to need feedparser's
tolerance for malformed XML and exotic encodings, swapping it in behind
`parse_feed()` is a single-function change.

Everything returned here is **untrusted**: it is third-party text fetched over
the network. Callers must treat it as data, never as instructions, and it is
wrapped accordingly before it ever reaches a model.
"""
from __future__ import annotations

import datetime as dt
import html
import re
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

# Namespaces that show up in the feeds we care about.
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


class FeedError(Exception):
    """The feed could not be parsed."""


@dataclass
class FeedItem:
    """One entry. `summary` is the publisher's own syndication summary."""

    title: str
    url: str
    guid: str
    summary: str = ""
    published_at: dt.datetime | None = None
    author: str = ""
    categories: list[str] = field(default_factory=list)


@dataclass
class ParsedFeed:
    title: str
    items: list[FeedItem] = field(default_factory=list)


def strip_html(value: str, *, limit: int = 1200) -> str:
    """Turn a feed's HTML summary into plain text.

    Feed summaries routinely contain markup, tracking pixels and entity escapes.
    Stripping tags here also removes the most obvious vector for smuggling
    markup into the UI.
    """
    if not value:
        return ""
    text = _TAG.sub(" ", value)
    text = html.unescape(text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text[:limit]


def _parse_date(value: str) -> dt.datetime | None:
    """Feed dates are RFC 822 (RSS) or ISO 8601 (Atom), and often malformed."""
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
        if parsed:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _text(element, *paths: str) -> str:
    """First non-empty match among several possible element paths."""
    for path in paths:
        found = element.find(path, NS)
        if found is not None and (found.text or "").strip():
            return found.text.strip()
    return ""


def _parse_rss(root) -> ParsedFeed:
    channel = root.find("channel")
    if channel is None:
        raise FeedError("RSS feed has no <channel>.")

    feed = ParsedFeed(title=_text(channel, "title") or "Untitled feed")
    for item in channel.findall("item"):
        link = _text(item, "link")
        guid = _text(item, "guid") or link
        if not link and not guid:
            continue  # An entry we cannot link back to is useless and unlinkable.
        feed.items.append(
            FeedItem(
                title=_text(item, "title") or "Untitled",
                url=link or guid,
                guid=guid or link,
                summary=strip_html(_text(item, "description", "content:encoded")),
                published_at=_parse_date(_text(item, "pubDate", "dc:date")),
                author=_text(item, "author", "dc:creator"),
                categories=[
                    (category.text or "").strip()
                    for category in item.findall("category")
                    if (category.text or "").strip()
                ],
            )
        )
    return feed


def _parse_atom(root) -> ParsedFeed:
    feed = ParsedFeed(title=_text(root, "atom:title") or "Untitled feed")
    for entry in root.findall("atom:entry", NS):
        link = ""
        for candidate in entry.findall("atom:link", NS):
            rel = candidate.get("rel", "alternate")
            if rel == "alternate" and candidate.get("href"):
                link = candidate.get("href")
                break
        if not link:
            first = entry.find("atom:link", NS)
            link = first.get("href", "") if first is not None else ""

        guid = _text(entry, "atom:id") or link
        if not link and not guid:
            continue

        feed.items.append(
            FeedItem(
                title=_text(entry, "atom:title") or "Untitled",
                url=link or guid,
                guid=guid or link,
                summary=strip_html(_text(entry, "atom:summary", "atom:content")),
                published_at=_parse_date(_text(entry, "atom:published", "atom:updated")),
                author=_text(entry, "atom:author/atom:name"),
                categories=[
                    category.get("term", "")
                    for category in entry.findall("atom:category", NS)
                    if category.get("term")
                ],
            )
        )
    return feed


def parse_feed(xml: str | bytes) -> ParsedFeed:
    """Parse RSS 2.0 or Atom. Raises FeedError on anything unusable."""
    if not xml or not str(xml).strip():
        raise FeedError("The feed was empty.")
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise FeedError(f"The feed is not valid XML: {exc}") from exc

    tag = root.tag.split("}")[-1]
    if tag == "rss":
        return _parse_rss(root)
    if tag == "feed":
        return _parse_atom(root)
    if tag == "RDF":  # RSS 1.0 keeps <item> as siblings of <channel>
        feed = ParsedFeed(title=_text(root, "{*}channel/{*}title") or "Untitled feed")
        for item in root.findall("{*}item"):
            link = _text(item, "{*}link")
            if not link:
                continue
            feed.items.append(
                FeedItem(
                    title=_text(item, "{*}title") or "Untitled",
                    url=link,
                    guid=item.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about") or link,
                    summary=strip_html(_text(item, "{*}description")),
                    published_at=_parse_date(_text(item, "dc:date")),
                )
            )
        return feed
    raise FeedError(f"Unrecognised feed format: <{tag}>.")
