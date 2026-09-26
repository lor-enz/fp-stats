import os
from contextlib import contextmanager


@contextmanager
def atomic_write(path):
    """Yield a temporary path next to `path`; once written, rename it over `path`.

    nginx serves the output folder while the site is rebuilt. A rename swaps
    the file in one step, so a visitor never gets a half-written page or chart.
    If writing fails, the previous file stays in place.
    """
    tmp = f'{path}.tmp'
    try:
        yield tmp
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
