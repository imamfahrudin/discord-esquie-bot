"""Entrypoint wrapper for the esquie_bot package.

This file preserves backward compatibility: running `python bot.py` will still
launch the bot, but the implementation lives in the `esquie_bot` package.
"""

from esquie_bot import run


if __name__ == '__main__':
    run()