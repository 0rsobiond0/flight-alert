from datetime import date
from decimal import Decimal

from flight_alert.providers.ryanair_source import (
    RyanairPublicProvider,
    build_route_url,
    parse_ryanair_page,
)


HTML = """
<html><head><link rel="canonical" href="https://www.ryanair.com/ie/en/flights/flights-from-bergamo-to-athens"></head>
<body>
<table class="sse-flight-table__table"><tbody>
<tr class="sse-flight-table__row">
<td class="sse-flight-table__from"><span class="sse-flight-table__iata">BGY</span></td>
<td class="sse-flight-table__to"><span class="sse-flight-table__iata">ATH</span></td>
<td class="sse-flight-table__date">Sat 13 Feb</td>
<td class="sse-flight-table__dep-time">21:05</td>
<td class="sse-flight-table__price-wrap"><a href="/ie/en/trip/flights/select?dateOut=2027-02-13&originIata=BGY&destinationIata=ATH">€19.99</a></td>
</tr>
</tbody></table>
<script type="application/ld+json">{"@graph":[{"@type":"Flight","departureTime":"2027-02-13","departureAirport":{"iataCode":"BGY"},"arrivalAirport":{"iataCode":"ATH"},"offers":{"priceCurrency":"EUR","price":"19.99","url":"https://www.ryanair.com/ie/en/flights/flights-from-bergamo-to-athens"}}]}</script>
</body></html>
"""


def test_builds_canonical_route_url():
    assert build_route_url("BGY", "ATH").endswith("/flights-from-bergamo-to-athens")


def test_parses_ryanair_table_into_verified_one_way_offer():
    result = parse_ryanair_page(HTML, "https://www.ryanair.com/ie/en/flights/flights-from-bergamo-to-athens")
    assert result.destinations == ["ATH"]
    assert len(result.offers) == 1
    offer = result.offers[0]
    assert offer.legs[0].origin == "BGY"
    assert offer.legs[0].destination == "ATH"
    assert offer.legs[0].departure.date() == date(2027, 2, 13)
    assert offer.total_mandatory_eur == Decimal("39.98")
    assert offer.verified is False
    assert offer.booking_url.startswith("https://www.ryanair.com")


def test_provider_filters_routes_and_dates_from_cached_payload():
    provider = RyanairPublicProvider.from_html(HTML, source_url="https://www.ryanair.com/ie/en/flights/flights-from-bergamo-to-athens")
    assert provider.destinations(("BGY",)) == ["ATH"]
    offers = provider.search("BGY", "ATH", date(2027, 2, 1), date(2027, 2, 28), 1, 2)
    assert len(offers) == 1
