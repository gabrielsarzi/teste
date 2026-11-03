"""Ponto de entrada do LimpaOne.

Uso:  python main.py               abre o programa
      python main.py --auto-clean  limpeza silenciosa (usada pela limpeza automática agendada)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from limpaone.autoclean import cli_main
    if not cli_main(sys.argv[1:]):
        from limpaone.gui import main
        main()
