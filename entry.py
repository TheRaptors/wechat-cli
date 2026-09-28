"""PyInstaller entry point — avoids relative import issues."""

import sys


def _configure_stdio():
    """Avoid UnicodeEncodeError on Windows consoles (cp1252/gbk) when printing Chinese help."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_stdio()

from wechat_cli.main import cli

if __name__ == "__main__":
    cli()
