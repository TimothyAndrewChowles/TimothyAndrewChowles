"""Utility script to look up U.S. property addresses via OpenStreetMap Nominatim.

The script accepts a list of property names (via a file, positional arguments, or
stdin) and returns the best-match address and coordinates using Nominatim's
geocoding service. Although the primary use case is Texas properties, the
``--country`` flag allows the script to work for anywhere in the USA (or another
country code).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional

import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "property-geocoder/1.0 (https://openai.com)"


class GeocodingError(Exception):
    """Raised when a property cannot be geocoded."""


def read_properties(args: argparse.Namespace) -> List[str]:
    """Return a list of property names from args or stdin.

    The function will read, in order of precedence:
      1. Lines from a file provided by ``--file``.
      2. Positional arguments listed after the options.
      3. Non-empty lines from standard input.
    """

    if args.file:
        path = Path(args.file)
        if not path.exists():
            raise FileNotFoundError(f"Property file not found: {path}")
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]

    if args.properties:
        return [item.strip() for item in args.properties if item.strip()]

    if sys.stdin.isatty():
        raise ValueError("No properties provided. Use --file, positional arguments, or pipe input.")

    return [line.strip() for line in sys.stdin if line.strip()]


def geocode_property(name: str, *, country: str, timeout: int) -> dict:
    """Query Nominatim for a single property name.

    Args:
        name: Property name or address to geocode.
        country: ISO 3166-1 alpha-2 country code used to narrow the search.
        timeout: Request timeout in seconds.

    Returns:
        A dictionary of the top search result from Nominatim.

    Raises:
        GeocodingError: If no results are found.
    """

    params = {
        "q": name,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": country,
    }

    response = requests.get(
        NOMINATIM_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    results = response.json()

    if not results:
        raise GeocodingError(f"No results for '{name}'.")

    return results[0]


def lookup_properties(properties: Iterable[str], *, country: str, pause: float, timeout: int) -> List[dict]:
    """Geocode an iterable of property names while respecting rate limits."""

    cache = {}
    results: List[dict] = []

    for name in properties:
        if name in cache:
            results.append(cache[name])
            continue

        try:
            result = geocode_property(name, country=country, timeout=timeout)
            cache[name] = result
            results.append(result)
        except GeocodingError as exc:
            sys.stderr.write(str(exc) + "\n")
        time.sleep(pause)

    return results


def write_results_csv(results: List[dict], output: Optional[Path]) -> None:
    """Write geocoding results as CSV to stdout or a file."""

    fieldnames = [
        "query",
        "display_name",
        "latitude",
        "longitude",
        "type",
        "class",
    ]

    destination = sys.stdout if output is None else output.open("w", newline="", encoding="utf-8")

    with destination as dest:
        writer = csv.DictWriter(dest, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            writer.writerow(
                {
                    "query": item.get("name") or item.get("display_name"),
                    "display_name": item.get("display_name"),
                    "latitude": item.get("lat"),
                    "longitude": item.get("lon"),
                    "type": item.get("type"),
                    "class": item.get("class"),
                }
            )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Geocode property names using Nominatim (OpenStreetMap).")
    parser.add_argument(
        "properties",
        nargs="*",
        help="Property names to geocode (ignored when --file is provided).",
    )
    parser.add_argument(
        "-f",
        "--file",
        help="Path to a newline-separated file of property names.",
    )
    parser.add_argument(
        "-c",
        "--country",
        default="us",
        help="ISO country code to constrain results (default: us).",
    )
    parser.add_argument(
        "-p",
        "--pause",
        type=float,
        default=1.0,
        help="Seconds to wait between requests to respect Nominatim rate limits (default: 1.0).",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=15,
        help="HTTP timeout in seconds (default: 15).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional path to write CSV output. Defaults to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        properties = read_properties(args)
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1

    results = lookup_properties(properties, country=args.country, pause=args.pause, timeout=args.timeout)

    if not results:
        sys.stderr.write("No properties were successfully geocoded.\n")
        return 1

    try:
        write_results_csv(results, args.output)
    except OSError as exc:
        sys.stderr.write(f"Failed to write output: {exc}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
