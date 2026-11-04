"""Whether this process reads the repo-root `.env`. Imported before settings, so it must not import them."""

import os


def dotenv_ignored() -> bool:
    return os.environ.get("ADVISE_WORKBENCH_IGNORE_DOTENV") == "1"
