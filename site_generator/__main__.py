"""Entry point for running site_generator as a module.

Usage:
    python -m site_generator [options]

This file is REQUIRED for ``python -m site_generator`` to work.
Without it, Python raises:
    No module named site_generator.__main__;
    'site_generator' is a package and cannot be directly executed
"""
from .main import main

if __name__ == "__main__":
    main()
