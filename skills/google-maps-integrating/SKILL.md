---
name: google-maps-integrating
description: Use this skill every time you do anything with Google Maps saved lists or starred places.
---

The Google session is read from the browser, nothing to set up.

- `scripts/google-maps-lists.py` lists all saved lists of the account as CSV.
- `scripts/google-maps-list-export.py <list-url>` exports the places of one list as CSV.

Own, followed and shared lists go through one list endpoint.
Starred places have no list id and are fetched by a custom search, which returns at most 200 places.
