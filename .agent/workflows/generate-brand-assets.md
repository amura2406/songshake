---
description: Generate brand assets (favicon, logo, OG image, PWA icons) from a reference image with variant selection
---

# Brand Asset Generation Workflow

## Purpose
Generate a unified set of brand assets (favicon, app logo, OG image, PWA icons, apple-touch-icon) from a reference image, ensuring visual consistency across the project.

## Prerequisites
- A reference image (e.g., banner, existing logo, mood board) to derive the style from
- Pillow installed as a dev dependency (`uv add --dev Pillow`)

---

## Phase 1: Audit — Identify Asset Opportunities

### 1. Examine the Reference Image
Use `view_file` on the reference image to understand:
- Art style (e.g., cyberpunk, minimalist, flat)
- Color palette (note hex codes)
- Key visual motifs (e.g., cassette tape, waveform, mascot)

### 2. Scan the Codebase for Asset Gaps
Search for existing and missing assets:

```bash
# Find existing image assets
find_by_name("*.ico", project_root)
find_by_name("*.svg", project_root)
find_by_name("*.png", project_root)

# Check for favicon references
grep_search("favicon", "web/index.html")
grep_search("og:image", "web/")
grep_search("apple-touch-icon", "web/")
grep_search("manifest", "web/public/")

# Check for logo usage in components
grep_search("logo", "web/src/")
```

### 3. Compile Asset Checklist
Present findings to the user as a table:

| Asset | Current State | Action Needed |
|-------|--------------|---------------|
| Favicon (.ico) | Default/missing | Generate |
| App logo (navbar) | Generic icon | Replace |
| Login logo | Generic icon | Replace |
| OG image | Missing | Generate |
| Apple touch icon | Missing | Generate |
| PWA icons | Missing | Generate |
| Unused scaffolding | vite.svg, react.svg | Delete |

Ask the user which assets to generate.

---

## Phase 2: Generate Brand Icon — Variant Selection

> **CRITICAL**: This is the core creative step. Generate multiple variants for user choice.

### 4. Generate at Least 4 Icon Variants

Use `generate_image` to create **at least 4 distinct variants**. Each variant should:
- Match the reference image's style and color palette
- Be a **square icon** suitable for favicon/app icon use
- Be visually distinct from the other variants (different composition, motif emphasis, or perspective)

Pass the reference image via `ImagePaths` to maintain style consistency.

> [!CAUTION]
> **`generate_image` produces FAUX transparency!**
> The generated image will render a checkerboard pattern INTO the pixels — it is NOT real alpha transparency.
> This means prompting for "transparent background" is USELESS. Instead:
> - Prompt for a **solid dark background** (e.g., "Solid black rounded square background")
> - Then remove the background programmatically with Pillow in Phase 3

**Prompt strategy — request solid dark background:**
```
Variant 1: "A square app icon... [style details]. Solid black rounded square background, no checkerboard. Emphasis on [motif A]."
Variant 2: "A square app icon... [style details]. Solid black rounded square background, no checkerboard. Emphasis on [motif B]."
Variant 3: "A square app icon... [style details]. Solid black rounded square background, no checkerboard. Minimal/abstract version."
Variant 4: "A square app icon... [style details]. Solid black rounded square background, no checkerboard. Detailed/illustrated version."
```

### 5. Present Variants to User

Create an artifact markdown file with all variants embedded in a **carousel** so the user can see and compare them:

```markdown
# Icon Variants

````carousel
### Variant 1 — [Name]
[Description]
![Variant 1](/absolute/path/to/variant_1.png)
<!-- slide -->
### Variant 2 — [Name]
[Description]
![Variant 2](/absolute/path/to/variant_2.png)
````
```

Use `notify_user` with `PathsToReview` pointing to the artifact. Ask the user to:
1. **Pick one** as-is, OR
2. **Request modifications** to a specific variant, OR
3. **Request entirely new variants** if none are suitable

**Do NOT proceed until the user has explicitly chosen a variant.**

### 6. Handle Modification Requests (if any)

If the user requests modifications:
- Use `generate_image` again with the chosen variant as input via `ImagePaths`
- Apply the user's feedback in the prompt
- Present the modified version(s) for approval
- Repeat until the user approves

### 7. Consider Two-Tier Icon Design

> [!IMPORTANT]
> **Favicons need to be SIMPLE to be legible at 16×16 and 32×32 pixels.**
> A detailed icon with many small elements (floating objects, circuit patterns, fine textures) becomes an unreadable blob at favicon sizes.

**Recommended approach — two-tier design:**
1. **Favicon (16–48px):** A drastically simplified version — just the core motif, thick outlines, 2–3 colors, no decorative elements
2. **App icon (180–512px):** The full detailed variant

**Ask the user** if they want a simplified favicon variant. If yes:
- Generate 2+ simplified variants showing only the core motif
- Present via carousel artifact for selection
- Use the approved simplified version for ICO/32px, and the detailed version for larger sizes

---

## Phase 3: Convert & Wire — Generate All Sizes

### 8. Ensure Pillow is Available

Pillow must be installed in the project's uv environment:

> [!WARNING]
> **Do NOT use `uv run --with Pillow` or `pip3 install Pillow` with system Python.**
> - `uv run --with` may fail due to index authentication issues
> - System Python 3.9 compiles Pillow from source which takes 5+ minutes
> Instead, install Pillow as a dev dependency:

```bash
uv add --dev Pillow
```

### 9. Remove Background & Generate All Icon Sizes

The generated images will have a light/white background outside the rounded square shape (from the `generate_image` rendering). Remove it by making near-white pixels transparent.

**Write a standalone Python script** and run it via `uv run`:

// turbo
```python
# /tmp/gen_icons.py
from PIL import Image
import os, sys

# Accept paths as CLI arguments
FAVICON_SRC = sys.argv[1]  # Simplified favicon source (or same as ICON_SRC if single-tier)
ICON_SRC = sys.argv[2]     # Detailed app icon source
PUB = sys.argv[3]          # web/public directory
ASSETS = sys.argv[4]       # web/src/assets directory

def remove_light_bg(img_path, threshold=240):
    """Remove near-white background pixels by making them transparent."""
    img = Image.open(img_path).convert('RGBA')
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r > threshold and g > threshold and b > threshold:
                pixels[x, y] = (255, 255, 255, 0)
    return img

print("Processing favicon source...")
fav_img = remove_light_bg(FAVICON_SRC)
px = fav_img.getpixel((0, 0))
print(f"  corner alpha={px[3]} (expect 0)")

print("Processing app icon source...")
app_img = remove_light_bg(ICON_SRC)
px = app_img.getpixel((0, 0))
print(f"  corner alpha={px[3]} (expect 0)")

# Favicon ICO (multi-size) — from simplified source
sizes = [(16, 16), (32, 32), (48, 48)]
ico_imgs = [fav_img.resize(s, Image.LANCZOS) for s in sizes]
ico_imgs[0].save(os.path.join(PUB, "favicon.ico"), format="ICO", sizes=sizes, append_images=ico_imgs[1:])
print("Created favicon.ico (16, 32, 48)")

# Favicon PNG 32x32 — from simplified source
fav_img.resize((32, 32), Image.LANCZOS).save(os.path.join(PUB, "favicon-32x32.png"))
print("Created favicon-32x32.png")

# Apple touch icon 180x180 — from detailed source
app_img.resize((180, 180), Image.LANCZOS).save(os.path.join(PUB, "apple-touch-icon.png"))
print("Created apple-touch-icon.png")

# PWA icons — from detailed source
app_img.resize((192, 192), Image.LANCZOS).save(os.path.join(PUB, "icon-192.png"))
app_img.resize((512, 512), Image.LANCZOS).save(os.path.join(PUB, "icon-512.png"))
print("Created icon-192.png and icon-512.png")

# In-app logo 256x256 — from detailed source
app_img.resize((256, 256), Image.LANCZOS).save(os.path.join(ASSETS, "logo.png"))
print("Created logo.png (256x256)")

print("\nAll icons generated!")
```

Run with:
// turbo
```bash
uv run python3 /tmp/gen_icons.py \
  "<favicon_source_path>" \
  "<app_icon_source_path>" \
  "<project>/web/public" \
  "<project>/web/src/assets"
```

> [!TIP]
> If using a single-tier design (same image for all sizes), pass the same path for both `FAVICON_SRC` and `ICON_SRC`.

### 10. Verify Corner Transparency

// turbo
```bash
uv run python3 -c "
from PIL import Image
import os
pub = '<project>/web/public'
assets = '<project>/web/src/assets'
for f in ['favicon.ico', 'favicon-32x32.png', 'apple-touch-icon.png', 'icon-192.png', 'icon-512.png']:
    i = Image.open(os.path.join(pub, f)).convert('RGBA')
    px = i.getpixel((0, 0))
    print(f'{f}: {i.size} corner_alpha={px[3]} (expect 0)')
i = Image.open(os.path.join(assets, 'logo.png')).convert('RGBA')
px = i.getpixel((0, 0))
print(f'logo.png: {i.size} corner_alpha={px[3]} (expect 0)')
"
```

If any corner alpha is NOT 0, the background removal threshold needs adjustment. Inspect the source image's corner pixel values and adjust the threshold.

### 11. Update index.html

Replace the default favicon link(s) with:
```html
<link rel="icon" type="image/x-icon" href="/favicon.ico" />
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" />
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
```

### 12. Wire Logo into Components

Import and use `logo.png` in:
- **Navbar/Layout component** — replace any generic icon with `<img src={logoImg} ... />`
- **Login page** — replace any placeholder icon with the brand logo
- **Any other branding touchpoints** found during the audit

### 13. Clean Up Scaffolding

Delete any leftover scaffolding assets that are no longer referenced:
- `web/public/vite.svg`
- `web/src/assets/react.svg`
- Any other default framework assets

Also clean up the temp script: `rm /tmp/gen_icons.py`

---

## Phase 4: Verify

### 14. Browser Verification

Use `browser_subagent` to:
1. Navigate to the app's login page
2. Take a screenshot to verify the logo renders correctly
3. Check the favicon in the browser tab
4. Navigate to the main app layout to verify the navbar logo

### 15. Create Walkthrough

Document in `walkthrough.md`:
- The chosen variant(s) and why (embed the images)
- All files created, modified, and deleted
- Verification screenshots

---

## Optional: Additional Assets

If the user also wants these, generate them in the same session:

### README Banner

Generate a wide banner image for the project README.

#### A. Ask the User for Style Direction

Present at least 3 style options (adapt to the project's identity):

| # | Style | Description |
|---|-------|-------------|
| 1 | Illustrated scene | Full scene with characters, environment, and brand motifs |
| 2 | Logo + gradient | Clean logo centered on a styled gradient background |
| 3 | Abstract/pattern | Geometric or abstract pattern with brand colors and title text |
| 4 | Screenshot montage | App screenshots arranged in a hero-style composition |

Ask the user which style they prefer before generating.

#### B. Generate at Least 3 Banner Variants

Use `generate_image` for each variant:
- **Always use wide aspect ratio** — prompt for "wide panoramic banner, aspect ratio 16:9" or "wide landscape format, much wider than tall"
- Include the project name as text in the banner
- Match the established brand color palette and art style
- Pass the approved app icon via `ImagePaths` to maintain visual consistency

> [!TIP]
> Include phrasing like "ultra-wide panoramic banner image, 3:1 aspect ratio, landscape orientation, much wider than it is tall" to enforce the wide format. Image generators tend to default to square without strong aspect ratio cues.

Present all variants in a **carousel artifact** for the user to pick.

#### C. Wire into README

Save the chosen banner to the project root (e.g., `banner.png`) and add to `README.md`:

```markdown
<p align="center">
  <img src="banner.png" alt="Project Name" width="100%">
</p>
```

### OG Image (Social Sharing)
- Size: 1200×630
- Use `generate_image` with the brand style
- Add `<meta property="og:image" ...>` to `index.html`

### PWA Manifest
- Create `web/public/manifest.json` referencing `icon-192.png` and `icon-512.png`
- Add `<link rel="manifest" href="/manifest.json" />` to `index.html`

---

## Completion Criteria
- [ ] At least 4 icon variants generated and presented to user
- [ ] User explicitly approved one variant
- [ ] Two-tier design considered (simplified favicon vs detailed app icon)
- [ ] Chosen icon(s) processed with real RGBA transparency (corner alpha = 0)
- [ ] All icon sizes generated (ICO, 32px, 180px, 192px, 512px, 256px)
- [ ] `index.html` updated with favicon + apple-touch-icon links
- [ ] Logo wired into navbar and login components
- [ ] Scaffolding assets deleted
- [ ] Browser verification completed with screenshots
- [ ] (If requested) README banner generated in wide aspect ratio, user approved, wired into README
