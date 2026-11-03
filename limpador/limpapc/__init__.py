"""LimpaPC — analisador e limpador de disco e memória."""
APP_NAME = "LimpaPC"
GITHUB_REPO = "gabrielsarzi/teste"          # onde as versões são publicadas (GitHub Releases)
HOMEPAGE = f"https://github.com/{GITHUB_REPO}"
__version__ = "2.0.0"
try:  # o build automático grava aqui a versão oficial (ex.: 2.0.15)
    from ._build import VERSION as __version__  # type: ignore  # noqa: F401
except ImportError:
    pass
