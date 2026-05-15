"""Routes package — modular APIRouter builders.

Each module exposes a `build_*_router(...)` factory that takes the DB
handle and any shared helpers it needs, then returns an APIRouter ready
to be included on the top-level `/api` router.

This factory pattern keeps the migration low-risk: nothing in `server.py`
imports from routes, and routes only depend on what's explicitly passed
in — no circular imports, and the legacy code path stays untouched.
"""
