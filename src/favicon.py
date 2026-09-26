from PIL import Image, ImageDraw

from atomic import atomic_write

# A rising chart line in the site's orange on a white rounded square, so it
# stays visible on light and dark browser tabs. It deliberately ends on its
# highest point: an upward trend, one gentle dip, no spike.
ORANGE = '#f64b00'
POINTS = [(0.06, 0.84), (0.34, 0.54), (0.52, 0.64), (0.94, 0.14)]  # x, y in 0..1, y down
MARGIN = 0.10      # inset of the line inside the square
LINE_WIDTH = 0.11  # relative to the icon size
CORNER = 0.20      # corner radius, relative to the icon size


def _points(size):
    return [(size * (MARGIN + x * (1 - 2 * MARGIN)), size * (MARGIN + y * (1 - 2 * MARGIN)))
            for x, y in POINTS]


def _svg():
    pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in _points(100))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            f'<rect width="100" height="100" rx="{CORNER * 100:g}" fill="#fff"/>'
            f'<polyline points="{pts}" fill="none" stroke="{ORANGE}" stroke-width="{LINE_WIDTH * 100:g}" '
            'stroke-linejoin="round" stroke-linecap="round"/></svg>\n')


def _raster(size):
    """Draw large, then shrink, for smooth edges at 16 and 32 px."""
    n = 512
    im = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * CORNER, fill='white')
    pts = _points(n)
    w = int(n * LINE_WIDTH)
    d.line(pts, fill=ORANGE, width=w, joint='curve')
    for x, y in (pts[0], pts[-1]):  # round line ends, like the SVG
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=ORANGE)
    return im.resize((size, size), Image.LANCZOS)


def write_favicons(out_dir):
    """favicon.svg for modern browsers; favicon.ico (16 + 32 px) for everything
    that requests /favicon.ico directly (older browsers, bots, link previews)."""
    with atomic_write(f'{out_dir}/favicon.svg') as tmp, open(tmp, 'w') as f:
        f.write(_svg())
    with atomic_write(f'{out_dir}/favicon.ico') as tmp:
        _raster(32).save(tmp, format='ICO', sizes=[(16, 16), (32, 32)],
                         append_images=[_raster(16)])
