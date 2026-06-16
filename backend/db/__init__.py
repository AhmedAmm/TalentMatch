"""
db/
====
Database access layer.

Sub-modules
-----------
models     — Beanie ODM document classes (Employee, Job, Project, …)
operations — Async CRUD functions (the only file the rest of the app imports)

Usage
-----
    import db.operations as _db
    emp = await _db.get_employee("alice@example.com")

    from db.models import Employee  # only needed in startup / Beanie init
"""
from db.operations import *  # re-export all public functions
