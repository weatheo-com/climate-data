# data.gov.rs: checklist for the owner

1. Create an account at https://data.gov.rs (login top right), confirm the e-mail.
2. Create the organisation (profile > "Нова организација"): name, description and website from ORG.md, logo optional. The portal admins may need to approve it; wait for that before step 4.
3. Profile > API key (https://data.gov.rs/sr/admin/ , "Профил" > "API кључ"): copy the key into the shell only: `export UDATA_API_KEY=...`. Check how publish_udata.py reads it (`grep -n environ scripts/publish_udata.py`). Do not commit it.
4. Get the organisation id (page of the organisation > "API" link, or `curl -s https://data.gov.rs/api/1/organizations/?q=weatheo | python3 -m json.tool | grep '"id"'`).
5. Make sure release v1.0.0 with the RS_*.csv / .parquet / datapackage.json files exists on GitHub (the resource URLs point there).
6. Dry run (nothing is sent; --lookup adds read-only GETs):
   `cd climate-data && python3 scripts/publish_udata.py --base https://data.gov.rs --org <ORG_ID> --meta portals/data.gov.rs/RS-A.json --lookup`
   (same for RS-B.json)
7. Publish: same command plus `--apply`.
8. Afterwards, in the web form of each dataset set by hand what the script does not send (it only sends title, description, tags, license, frequency, temporal_coverage):
   - Spatial coverage: granularity "Општина" (sr:municipality), zone "Србија" (country:rs), as in RS-A.json "spatial".
   - Licence: data.gov.rs offers only "sodl" and "notspecified". Datasets are posted as "notspecified" because the data are CC BY 4.0, not SODL; the description states CC BY 4.0 and the Copernicus text. Do not change to sodl.
9. Check the two dataset pages (Cyrillic text, 3 resources each, links work).
