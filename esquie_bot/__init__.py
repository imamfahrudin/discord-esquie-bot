"""esquie_bot package

Provide a lazy-run wrapper so importing the package does not import
`esquie_bot.main` (which depends on runtime-heavy packages like ``discord``)
until `run()` is actually called. This makes it possible to import the
package in environments that don't have Discord installed (useful for tests
or quick checks).
"""

from typing import Any


def run(*args: Any, **kwargs: Any) -> Any:
	"""Lazily import and call the real run() from ``esquie_bot.main``.

	This avoids importing Discord (and other heavy deps) at package import
	time.
	"""
	from .main import run as _run

	return _run(*args, **kwargs)


__all__ = ["run"]
