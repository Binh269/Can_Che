#!/usr/bin/env python
"""Tiem ich quan ly Django cho du an Web_Can."""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WebCan.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Khong the import Django. Dam bao da cai dat va PYTHONPATH dung."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
