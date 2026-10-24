"""Build data/geo/de_postcodes.csv from the GeoNames German postal-code export.

Source: https://github.com/zauberware/postal-codes-json-xml-csv (data/DE.zip), itself derived from
GeoNames (https://www.geonames.org/), licensed CC BY 4.0. Rows that name a company instead of a
place (large-customer postcodes) are dropped.

    python scripts/build_gazetteer.py path/to/zipcodes.de.csv
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

COMPANY = re.compile(r"\b(GmbH|AG|KG|mbH|e\.V\.|SE|OHG|Bank|Versicherung|Postfach|Großkunde)\b", re.I)
OUT = Path(__file__).resolve().parents[1] / "data" / "geo" / "de_postcodes.csv"


def main(src: str) -> None:
    by_zip: dict[str, tuple[str, str, float, float]] = {}
    for r in csv.DictReader(open(src, encoding="utf-8")):
        place = r["place"].strip()
        if COMPANY.search(place) or not r["latitude"]:
            continue
        z = r["zipcode"].strip()
        if z not in by_zip:
            by_zip[z] = (place, r["state"].strip(), round(float(r["latitude"]), 4), round(float(r["longitude"]), 4))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["plz", "place", "state", "lat", "lon"])
        for z in sorted(by_zip):
            w.writerow([z, *by_zip[z]])
    places = defaultdict(int)
    for p, *_ in by_zip.values():
        places[p] += 1
    print(f"{len(by_zip)} postcodes, {len(places)} places -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
