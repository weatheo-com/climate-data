# data.gov.rs: checklist for the owner

1. Create an account at https://data.gov.rs (login top right), confirm the e-mail.
2. Create the organisation (profile > "Нова организација"): name, description and website from ORG.md, logo optional. The portal admins may need to approve it; wait for that before step 4.
3. Profile > API key (https://data.gov.rs/sr/admin/ , "Профил" > "API кључ"): copy the key into the shell only: `export UDATA_API_KEY=...`. Check how publish_udata.py reads it (`grep -n environ scripts/publish_udata.py`). Do not commit it.
4. Get the organisation id (page of the organisation > "API" link, or `curl -s https://data.gov.rs/api/1/organizations/?q=weatheo | python3 -m json.tool | grep '"id"'`).
5. Make sure release v1.0.0 with the rs_*.csv / .parquet / rs_datapackage.json files exists on GitHub (the resource URLs point there).
6. Dry run (nothing is sent; --lookup adds read-only GETs):
   `cd climate-data && python3 scripts/publish_udata.py --base https://data.gov.rs --org <ORG_ID> --meta portals/data.gov.rs/RS-A.json --lookup`
   (same for RS-B.json)
7. Publish: same command plus `--apply`.
8. Afterwards, check in the web form of each dataset (the script sends title, description, tags, license, frequency, temporal_coverage and spatial):
   - Spatial coverage: sent by the script from "spatial" in RS-A.json / RS-B.json (granularity "Општина" sr:municipality, zone "Србија" country:rs); set it by hand in the form only if the page does not show it.
   - Licence: "sodl" (Српска лиценца за отворене податке, owner choice 2026-11-13; it allows commercial reuse with attribution). The description says the same data are CC BY 4.0 in the repository and gives the RZS source, download date and the changes, as SODL requires.
9. Check the two dataset pages (Cyrillic text, 3 resources each, links work).

Firewall notes (2026-11-13): data.gov.rs answers 403 (HTML page) to descriptions with markdown links `[text](url)` (write `text: url`) and to the capitalised Cyrillic "То су"; and to a third resource on these datasets whatever its title, URL or format. RS-A and RS-B are published with the CSV and Parquet resources only; the datapackage is linked from the description (GitHub repository).
