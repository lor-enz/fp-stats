"""Smoke test: build the whole site from the sample data in tests/fixture.

CI runs this inside the freshly built image, before pushing it, so a broken
import, dependency or dockerfile never reaches saturn:

    docker run --rm -v "$PWD/tests:/tests:ro" fp-stats:test python3 /tests/smoke.py

Locally (from the repo root): .venv/bin/python tests/smoke.py
The sample data is made up; it is not real scraped data.
"""
import contextlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# Inside the image the code lives in /app; in a checkout it's in src/.
SRC = '/app' if os.path.exists('/app/pages.py') else os.path.join(HERE, '..', 'src')
sys.path.insert(0, SRC)

import data   # noqa: E402
import pages  # noqa: E402
import main   # noqa: E402,F401  (scraper: checks its imports, e.g. requests)

EXPECTED = [
    'index.html', 'creators.html',
    'LinusTechTips.html', 'plot_LinusTechTips.svg', 'plot_LinusTechTips.png',
    'Example-Creator.html', 'plot_Example-Creator.svg', 'plot_Example-Creator.png',
    'TechDeals.html', 'plot_TechDeals.svg', 'plot_TechDeals.png',
]


def run():
    out = tempfile.mkdtemp()
    data.DATA_FOLDER = os.path.join(HERE, 'fixture')
    pages.PLOT_FOLDER = out
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        pages.build_site()
    print(log.getvalue())

    problems = []
    if 'FAILED' in log.getvalue():
        problems.append('a build step failed (see log above)')
    if 'No data for Broken Creator' not in log.getvalue():
        problems.append('the empty data file was not skipped as expected')
    for name in EXPECTED:
        path = os.path.join(out, name)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            problems.append(f'missing or empty: {name}')
    leftovers = [f for f in os.listdir(out) if f.endswith('.tmp')]
    if leftovers:
        problems.append(f'temporary files left behind: {leftovers}')
    index_path = os.path.join(out, 'index.html')
    index = open(index_path).read() if os.path.exists(index_path) else ''
    for needed in ('42,890', '/plot_LinusTechTips.svg', 'id="stale"', '</html>'):
        if needed not in index:
            problems.append(f'index.html does not contain {needed!r}')

    if problems:
        print('SMOKE TEST FAILED:\n  ' + '\n  '.join(problems))
        sys.exit(1)
    print(f'Smoke test passed ({len(os.listdir(out))} files).')


if __name__ == '__main__':
    run()
