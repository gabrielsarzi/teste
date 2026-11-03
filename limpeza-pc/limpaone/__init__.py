"""LimpaOne — limpeza, otimização e recuperação de arquivos para o seu computador."""
APP_NAME = "LimpaOne"
PUBLISHER = "Sarzi Tecnologia"
SITE = "https://limpaone.sarzitecnologia.com.br"
GITHUB_REPO = "gabrielsarzi/teste"          # onde as versões são publicadas (GitHub Releases)
HOMEPAGE = f"https://github.com/{GITHUB_REPO}"
__version__ = "3.0.0"
try:  # o build automático grava aqui a versão oficial (ex.: 3.0.15)
    from ._build import VERSION as __version__  # type: ignore  # noqa: F401
except ImportError:
    pass
