import sys

from .cli import main
from .ingest.erros import LayoutError
from .output.validators import ValidationError

try:
    main()
except (LayoutError, ValidationError, ValueError) as exc:
    print(f"ERRO: {exc}", file=sys.stderr)
    sys.exit(1)
