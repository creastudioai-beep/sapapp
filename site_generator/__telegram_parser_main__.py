"""Entry point for running telegram_parser as a module.

Usage:
    python -m site_generator.telegram_parser --full
    python -m site_generator.telegram_parser --recent 50
"""
from .telegram_parser import main

if __name__ == "__main__":
    main()
