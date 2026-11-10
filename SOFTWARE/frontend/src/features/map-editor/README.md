# Parcel Map Editor — vođeni unos

Geografski digital twin editor na satelitskoj podlozi (Esri World Imagery).

## Rute

- `/orchard/new/map-editor` — **Nova parcela** (glavni tok)
- `/orchard/:parcelId/map-editor` — izmena postojeće (učitava granicu / raspored)

## Wizard koraci

1. **Naziv i lokacija** — naziv, godina sadnje + adresa/koordinate/Maps link na satelitskoj mapi  
2. **Granica** — crtanje poligona klikovima, prevlačenje temena, automatska površina (ha)  
3. **Sadnja** — broj redova, razmak redova/sadnica, margina od granica (ili po ivici), stranica paralelno sa kojom idu redovi → iscrtavanje  
4. **Pregled** — tabela „red → broj sadnica”; izmena granice, brisanje sadnice, ponovno generisanje  
5. **Sorte** — padajuća lista + boja po sorti  
6. **Dodela** — sorta po redu (klik), opciono druga godina sadnje po redu  
7. **Čuvanje** — commit granice, redova, stabala i sorti

## API (dopune)

- `POST /map-editor/resolve-location` — adresa / koordinate / Maps URL  
- Preview/commit: `last_row_offset_m`, `target_row_count`, `varieties`

## Persistence

Isto kao ranije: `parcels.boundary`, `map_layout`, `orchard_rows.geometry`, `trees.lat/lng`. Pravougaona šema (`/orchard/new`) ostaje dostupna kao alternativni unos.
