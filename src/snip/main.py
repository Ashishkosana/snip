"""Console entry point: ``snip`` launches the API with uvicorn."""

from __future__ import annotations

import uvicorn

from snip.config import get_settings


def _port_from(base_url: str) -> int:
    _, _, port = base_url.removeprefix("http://").removeprefix("https://").partition(":")
    return int(port) if port.isdigit() else 8000


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "snip.app:app",
        host="0.0.0.0",
        port=_port_from(settings.base_url),
        reload=False,
    )


if __name__ == "__main__":
    main()
