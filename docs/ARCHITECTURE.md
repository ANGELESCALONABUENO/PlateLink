# Architecture

- `core.py`: SQLite inventory, stable UUIDs, faces, recipes and event history.
- `bridge.py`: read-only Spoolman/material references and validated connection settings.
- `lab.py`: compact assignment API, compatibility and revision checks.
- `server.py` + `web/`: shared inventory dashboard and same-origin mutation checks.
- `__init__.py`, `panel.html`, `texture_window.py`: Orca Script capability windows.
- `textures.py`: texture selection; STL ownership remains with PrinterLink.
- `label_print.py` + `render_label.py`: optional, preview-first label generation.
- `integrations/printhost/`: narrow authenticated CUPS label adapter, no 3D printer APIs.

Data, tokens, photos, connection URLs and print jobs are external runtime state and excluded from the repository. Back up your data directory before updates. The inventory server is designed for a trusted network; origin checks do not replace authentication.
