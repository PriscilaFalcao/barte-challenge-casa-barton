import re
import unicodedata


def norm_texto(texto) -> str:
    """Sem acento, minúsculo, espaços colapsados. Usado para achar cabeçalhos e nomes de aba."""
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()
