"""Edition endpoints, split by read / write / export.

Re-exports ``router`` for ``main.py``."""
from fastapi import APIRouter

router = APIRouter(prefix="/admin/editions", tags=["editions"])

# Import sub-modules so their @router.<verb> decorators register endpoints
# on the shared router object above.
from . import read, write  # noqa: E402,F401
