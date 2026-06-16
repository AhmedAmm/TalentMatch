"""
security/
=========
Security layer for the SmartStaff backend.

Sub-modules
-----------
sanitizers  — sanitize_string, sanitize_dict, check_nosql_injection
validators  — validate_email_field, validate_pdf_upload
turnstile   — verify_turnstile (Cloudflare bot-detection)
middleware  — SecurityMiddleware (ASGI), RateLimiter
auth        — JWT + bcrypt authentication (create_user, login, verify_token, …)

Public re-exports
-----------------
Everything a FastAPI route handler typically needs is importable directly
from ``security``:

    from security import sanitize_string, validate_email_field, verify_turnstile
    from security import check_nosql_injection, validate_pdf_upload
    from security.middleware import SecurityMiddleware
    import security.auth as _auth
"""
from security.sanitizers import sanitize_string, sanitize_dict, check_nosql_injection
from security.validators import validate_email_field, validate_pdf_upload
from security.turnstile  import verify_turnstile
from security.middleware import SecurityMiddleware, RateLimiter

__all__ = [
    "sanitize_string",
    "sanitize_dict",
    "check_nosql_injection",
    "validate_email_field",
    "validate_pdf_upload",
    "verify_turnstile",
    "SecurityMiddleware",
    "RateLimiter",
]
