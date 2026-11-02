"""Ponto de entrada do LimpaPC.  Uso:  python main.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from limpapc.gui import main  # noqa: E402

if __name__ == "__main__":
    main()
