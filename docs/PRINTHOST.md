# Optional laminated label printing

This integration targets the Brother PT-P950NW CUPS queue with 36 mm laminated tape. The PDF is 104 x 36 mm. It is independent from the QL-700 thermal-label broker. Check the queue name and loaded tape before printing; a queue name cannot confirm the installed consumable.

## On the PlateLink server

```sh
pip install '.[labels]'
# Install Poppler's pdftoppm through your operating system package manager.
mkdir -p data
cp examples/print-config.example.json data/print-config.json
chmod 600 data/print-config.json
```

Set `public_url` to the address clients will use to open QR links. Set `bridge_url` and a random token shared with PrintHost. Never publish this configuration. `reportlab` must be installed in the same Python environment that runs PlateLink. Rendering uses DejaVu fonts if present, otherwise PDF standard fonts.

## On PrintHost (Linux/CUPS)

Copy `integrations/printhost/print_bridge.py` into `~/platelink-print/`. Generate a random token, store it in `~/platelink-print/token` with mode 600, and put the same value in the server's private configuration. Use a trusted network only.

```sh
mkdir -p ~/platelink-print
chmod 700 ~/platelink-print
# Create token separately; do not paste it into a public issue or command transcript.
python3 ~/platelink-print/print_bridge.py --host 127.0.0.1 --port 8132
```

For a remote PlateLink server, choose your private LAN/VPN address for `--host`. The example systemd user unit defaults to loopback; edit it deliberately for your network. Do not disable authentication or expose this service publicly.

The bridge uses the fixed queue `Brother_PTP950NW_36mm`, one copy, matching-media checks, auto cut and half cut. Adapt the fixed command in `command()` only after verifying your own CUPS/driver options. It accepts bounded PDF payloads and a bearer token; it does not offer arbitrary printer selection or command execution.

## Preview and output

Use **Etiqueta** on a plate card or its details, review the image, and press **Imprimir una etiqueta**. A PDF download is also available. Request IDs persist across retries. If the queue submission has an uncertain outcome, inspect PrintHost/CUPS before creating a new submission: automatic reprinting is intentionally blocked.

The integration has automated mock tests and reviewed PDF previews. A successful health endpoint or CUPS response is not proof that a label physically emerged. Validate alignment, cut length and QR scanning on your own printer before producing a batch.
