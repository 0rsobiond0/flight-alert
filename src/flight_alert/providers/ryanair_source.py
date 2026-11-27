from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.pricing import total_for_passengers
from flight_alert.providers.base import FlightProvider


BASE_URL = "https://www.ryanair.com"
SITEMAP_URLS = tuple(
    f"{BASE_URL}/ie/en/flights/content/{index}/sitemap.xml" for index in range(6)
)
ORIGIN_SLUGS = {"BGY": ("bergamo",), "MXP": ("milan", "malpensa"), "LIN": ("milan", "linate")}


@dataclass(frozen=True)
class ParsedRyanairPage:
    destinations: list[str]
    offers: list[FlightOffer]


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, str]] = []
        self.scripts: list[str] = []
        self._row: dict[str, str] | None = None
        self._cell_class = ""
        self._text: list[str] = []
        self._href = ""
        self._in_script = False
        self._script_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        classes = attrs_map.get("class", "") or ""
        if tag == "tr" and "sse-flight-table__row" in classes:
            self._row = {}
        elif self._row is not None and tag == "td":
            self._cell_class = classes
            self._text = []
            self._href = ""
        elif self._row is not None and tag == "a":
            self._href = attrs_map.get("href", "") or ""
        elif tag == "script" and attrs_map.get("type") == "application/ld+json":
            self._in_script = True
            self._script_text = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_text.append(data)
        elif self._row is not None and self._cell_class:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._row is not None and self._cell_class:
            value = " ".join("".join(self._text).split())
            self._row[self._cell_class] = value
            if self._href:
                self._row[f"{self._cell_class}:href"] = self._href
            self._cell_class = ""
            self._text = []
            self._href = ""
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "script" and self._in_script:
            self.scripts.append("".join(self._script_text))
            self._in_script = False
            self._script_text = []


def build_route_url(origin: str, destination: str) -> str:
    slugs = {"BGY": "bergamo", "MXP": "milan", "LIN": "milan"}
    destination_slugs = {"ATH": "athens", "SKP": "skopje", "SKG": "thessaloniki"}
    try:
        origin_slug = slugs[origin.upper()]
        destination_slug = destination_slugs[destination.upper()]
    except KeyError as exc:
        raise ValueError(f"unsupported route code: {exc.args[0]}") from exc
    return f"{BASE_URL}/ie/en/flights/flights-from-{origin_slug}-to-{destination_slug}"


def _find_value(row: dict[str, str], fragment: str) -> str:
    for key, value in row.items():
        if fragment in key and not key.endswith(":href"):
            return value
    return ""


def _find_href(row: dict[str, str]) -> str:
    for key, value in row.items():
        if key.endswith(":href"):
            return value
    return ""


def _parse_price(value: str) -> Decimal:
    cleaned = value.replace("€", "").replace("EUR", "").replace(" ", "").strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        raise ValueError(f"could not parse price: {value!r}")
    return Decimal(match.group(0))


def _date_from_href(href: str) -> date | None:
    match = re.search(r"dateOut=(\d{4}-\d{2}-\d{2})", href)
    return date.fromisoformat(match.group(1)) if match else None


def _parse_date(value: str, href: str) -> date:
    from_href = _date_from_href(href)
    if from_href:
        return from_href
    match = re.search(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|lun|mar|mer|gio|ven|sab|dom)\s+(\d{1,2})\s+([A-Za-zÀ-ÿ]+)", value, re.I)
    if not match:
        raise ValueError(f"could not parse departure date: {value!r}")
    months = {
        "jan": 1, "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "may": 5,
        "jun": 6, "giu": 6, "jul": 7, "lug": 7, "aug": 8, "ago": 8,
        "sep": 9, "set": 9, "oct": 10, "ott": 10, "nov": 11, "dec": 12, "dic": 12,
    }
    month = months.get(match.group(2).lower()[:3])
    if month is None:
        raise ValueError(f"unknown departure month: {match.group(2)!r}")
    today = date.today()
    year = today.year + (1 if month < today.month else 0)
    return date(year, month, int(match.group(1)))


def _parse_time(value: str) -> time:
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", value)
    if not match:
        return time(12, 0)
    return time(int(match.group(1)), int(match.group(2)))


def _canonical_link(source_url: str, href: str) -> str:
    return urljoin(source_url, html.unescape(href)) if href else source_url


def _parse_jsonld_flights(scripts: list[str], source_url: str, source_name: str) -> list[FlightOffer]:
    results: list[FlightOffer] = []
    now = datetime.now(timezone.utc)
    for script in scripts:
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        graph = payload.get("@graph", []) if isinstance(payload, dict) else []
        for item in graph:
            if not isinstance(item, dict) or item.get("@type") != "Flight":
                continue
            try:
                departure = datetime.fromisoformat(item["departureTime"]).replace(tzinfo=timezone.utc)
                origin = item["departureAirport"]["iataCode"].upper()
                destination = item["arrivalAirport"]["iataCode"].upper()
                offer = item["offers"]
                price = _parse_price(str(offer["price"]))
                url = str(offer.get("url") or source_url)
            except (KeyError, TypeError, ValueError):
                continue
            total = total_for_passengers(price, 2, per_person=True)
            leg = FlightLeg(origin, destination, departure, departure + timedelta(hours=2), "FR", None, total, "small personal item only", url, source_name, now, False)
            results.append(FlightOffer((leg,), 1, 2, total, "separate_one_way", source_name, now, url, "Ryanair SEO fare; verify at checkout"))
    return results


def parse_ryanair_page(page_html: str, source_url: str, source_name: str = "ryanair-public") -> ParsedRyanairPage:
    parser = _TableParser()
    parser.feed(page_html)
    offers: list[FlightOffer] = []
    now = datetime.now(timezone.utc)
    for row in parser.rows:
        try:
            origin = _find_value(row, "__from").split()[-1].upper()
            destination = _find_value(row, "__to").split()[-1].upper()
            href = _find_href(row)
            departure_date = _parse_date(_find_value(row, "__date"), href)
            departure = datetime.combine(departure_date, _parse_time(_find_value(row, "dep-time")), timezone.utc)
            price = _parse_price(_find_value(row, "price"))
        except (ValueError, IndexError):
            continue
        total = total_for_passengers(price, 2, per_person=True)
        url = _canonical_link(source_url, href)
        leg = FlightLeg(origin, destination, departure, departure + timedelta(hours=2), "FR", None, total, "small personal item only", url, source_name, now, False)
        offers.append(FlightOffer((leg,), 1, 2, total, "separate_one_way", source_name, now, url, "Ryanair SEO fare; verify at checkout"))
    if not offers:
        offers = _parse_jsonld_flights(parser.scripts, source_url, source_name)
    destinations = sorted({offer.legs[0].destination for offer in offers})
    return ParsedRyanairPage(destinations, offers)


class RyanairPublicProvider(FlightProvider):
    name = "ryanair-public"

    def __init__(self, http_client: httpx.Client, route_urls: dict[str, list[str]] | None = None, max_routes: int = 100):
        self.http_client = http_client
        self.route_urls = route_urls or {}
        self.max_routes = max_routes
        self._offers_by_route: dict[str, list[FlightOffer]] = {}
        self._destinations: list[str] | None = None

    @classmethod
    def from_html(cls, html_text: str, source_url: str) -> "RyanairPublicProvider":
        parsed = parse_ryanair_page(html_text, source_url)
        provider = cls(httpx.Client())
        provider._offers_by_route[source_url] = parsed.offers
        provider.route_urls = {parsed.offers[0].legs[0].origin: [source_url]} if parsed.offers else {}
        provider._destinations = parsed.destinations
        return provider

    def _discover_route_urls(self, origins: tuple[str, ...]) -> dict[str, list[str]]:
        routes: dict[str, list[str]] = {origin: [] for origin in origins}
        for sitemap_url in SITEMAP_URLS:
            try:
                response = self.http_client.get(sitemap_url, timeout=30)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            urls = re.findall(r"<loc>(https://www\.ryanair\.com/[^<]+/flights/flights-from-[^<]+)</loc>", response.text)
            for url in urls:
                path = urlparse(url).path.lower()
                for origin in origins:
                    if any(f"/flights/flights-from-{slug}-to-" in path for slug in ORIGIN_SLUGS.get(origin, ())):
                        if url not in routes[origin] and len(routes[origin]) < self.max_routes:
                            routes[origin].append(url)
        return routes

    def _load_page(self, url: str) -> list[FlightOffer]:
        if url not in self._offers_by_route:
            response = self.http_client.get(url, timeout=30, follow_redirects=True)
            response.raise_for_status()
            self._offers_by_route[url] = parse_ryanair_page(response.text, url).offers
        return self._offers_by_route[url]

    def destinations(self, origins: tuple[str, ...]) -> list[str]:
        if self._destinations is not None:
            return self._destinations
        self.route_urls = self._discover_route_urls(origins)
        destinations: set[str] = set()
        for urls in self.route_urls.values():
            for url in urls:
                try:
                    destinations.update(offer.legs[0].destination for offer in self._load_page(url))
                except (httpx.HTTPError, ValueError):
                    continue
        self._destinations = sorted(destinations)
        return self._destinations

    def search(self, origin, destination, start_date, end_date, nights, passengers):
        results: list[FlightOffer] = []
        for offers in self._offers_by_route.values():
            results.extend(
                offer for offer in offers
                if offer.legs[0].origin == origin
                and offer.legs[0].destination == destination
                and start_date <= offer.legs[0].departure.date() <= end_date
                and offer.passengers == passengers
            )
        return results
