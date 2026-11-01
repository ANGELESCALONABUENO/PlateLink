# PlateLink textures — 2026-11-01

Built-in image_gen mode. Five separate, seamless, edge-to-edge square surface images, without logos, lettering, grid, plate outline, perspective, shadows or vignette. Descriptors: fine black granular engineering surface; black 2×2 carbon twill; smooth black glass; warm gold granular PEI; fine brushed silver metal.

Original PNGs: src/inmateriis_platelink/textures/{engineering,carbon,black-glass,gold-pei,high-temperature-metal}.png. Integrity hashes: textures/manifest.json.

Final user specification: **70% opacity / 30% transparency**. The plugin installs PNG copies using opacity.py, preserving RGB and setting uniform alpha 179/255 (nearest 8-bit value). Alpha is checked by tests. Versioned local paths avoid replacing an image still cached by Orca. AI alpha-edit attempts were insufficiently uniform and are not shipped.

PrinterLink owns bed_custom_model. PlateLink writes only bed_custom_texture. It monitors the installed inventory face every 10 seconds while its popup is open. Profile saving remains Orca's normal explicit flow. No printer commands.
