# Investment analysis pipeline

This layer consumes CSV exports from the existing scraper. It is separate from main.py so current scraping behaviour is unchanged.

## 1. Scrape sale and rental listings

Run separate searches by transaction, type, source, and neighborhood, for example:

    python main.py --source mubawab --transaction sale --property-type maison --location "Mnihla" --max-pages 5
    python main.py --source mubawab --transaction rent --property-type maison --location "Mnihla" --max-pages 5

Repeat across target Greater Tunis neighborhoods and supported sources. Use the corresponding processed CSV export for each transaction.

## 2. Analyze exports

    python investment_analysis.py --sales-csv path/to/sale_export.csv --rents-csv path/to/rent_export.csv --output-dir data/investment_analysis

Produces houses_for_sale.csv, houses_for_rent.csv, neighborhood_analysis.csv, investment_opportunities.csv, and investment_report.md.

Defaults: 150,000 TND budget; 700 TND monthly rent target; at least two eligible same-neighborhood rental ads; 5% registration, 1% registry, 1.5% legal/admin, 2% agency, 5% maintenance, 5% vacancy, 10,000 TND repair allowance when unfinished work is mentioned, and 2% initial contingency. These are screening assumptions, not legal advice or fee quotes. All can be overridden with CLI options.

## Classification safeguards

- Explicit standalone wording is required before a rental listing can count as a comparable; it is still not proof of legal status or exclusive occupancy.
- Apartments, floors of villas, shared accommodation, commercial properties, and seasonal rentals are excluded.
- Generic house/villa labels without explicit independent-house evidence remain unverified.
- A rental estimate requires at least two eligible advertisements in the same normalized neighborhood. Otherwise the report does not infer a rent.
- Asking rents are not completed rental transactions. Seller availability is unconfirmed unless listing text says unavailable.
- Source website terms and robots guidance must be respected. Do not bypass CAPTCHAs or anti-bot controls.
