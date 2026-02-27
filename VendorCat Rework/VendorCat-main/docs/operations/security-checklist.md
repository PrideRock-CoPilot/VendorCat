# Security Checklist

This document provides a security checklist for VendorCatalog development and deployment.

## Input Validation

### URL Validation

**Risk**: Open redirect, SSRF attacks

**Rule**: Validate all URL inputs before storage or redirect

**Pattern**:
```python
from urllib.parse import urlparse

def validate_url(url: str, allowed_schemes=['http', 'https']) -> str:
    if not url:
        raise ValueError("URL required")
    
    parsed = urlparse(url)
    
    if parsed.scheme not in allowed_schemes:
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    
    if not parsed.netloc:
        raise ValueError("URL must have domain")
    
    # Reject localhost/private IPs (SSRF protection)
    if parsed.netloc in ['localhost', '127.0.0.1', '0.0.0.0']:
        raise ValueError("Private IP addresses not allowed")
    
    return url
```

**Checklist**:
- [ ] All URL fields validated before storage
- [ ] URL scheme restricted to http/https
- [ ] Private IPs rejected (SSRF protection)
- [ ] URL length limited (max 2048 chars)

---

### Email Validation

**Risk**: Email injection, spam

**Rule**: Validate email format

**Pattern**:
```python
import re

def validate_email(email: str) -> str:
    if not email:
        raise ValueError("Email required")
    
    if len(email) > 254:
        raise ValueError("Email too long")
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValueError("Invalid email format")
    
    return email.lower()
```

**Checklist**:
- [ ] Email format validated with regex
- [ ] Email length limited (max 254 chars)
- [ ] Email normalized to lowercase

---

### Text Input Validation

**Risk**: SQL injection, XSS, data corruption

**Rule**: Validate length, type, and allowed characters

**Pattern**:
```python
def validate_text(text: str, max_length: int, field_name: str) -> str:
    if not text:
        raise ValueError(f"{field_name} required")
    
    if len(text) > max_length:
        raise ValueError(f"{field_name} too long (max {max_length})")
    
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in ['\n', '\r', '\t'])
    
    return text.strip()
```

**Checklist**:
- [ ] All text inputs have max length
- [ ] Control characters removed
- [ ] Leading/trailing whitespace trimmed
- [ ] Use Pydantic models for complex validation

---

### Integer/Numeric Validation

**Risk**: Integer overflow, invalid data

**Pattern**:
```python
def validate_positive_int(value: int, field_name: str) -> int:
    if value is None:
        raise ValueError(f"{field_name} required")
    
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be integer")
    
    if value < 0:
        raise ValueError(f"{field_name} must be positive")
    
    return value
```

**Checklist**:
- [ ] Numeric inputs validated for type
- [ ] Range checks applied (min/max)
- [ ] Foreign key IDs validated for existence

---

## XSS Prevention

### Template Output Escaping

**Risk**: Cross-site scripting (XSS)

**Rule**: Auto-escape all template variables unless sanitized

**Default (Safe)**:
```jinja2
{# Jinja2 auto-escapes by default #}
<div>{{ vendor.name }}</div>  <!-- Safe: auto-escaped -->
```

**Manual Sanitization (When Using |safe)**:
```python
import bleach

def sanitize_html(content: str) -> str:
    allowed_tags = ['p', 'b', 'i', 'u', 'br', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3']
    allowed_attrs = {'a': ['href', 'title']}
    
    return bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )

# In repository
def save_vendor_notes(vendor_id: int, notes_html: str):
    sanitized = sanitize_html(notes_html)
    repo.update_vendor_notes(vendor_id, sanitized)
```

**Template**:
```jinja2
<div class="vendor-notes">
    {{ vendor.notes | safe }}  {# Safe because sanitized at write time #}
</div>
```

**Checklist**:
- [ ] All |safe usage audited
- [ ] User HTML content sanitized at write time
- [ ] Allowed tags whitelist defined
- [ ] Event handlers stripped (onclick, onerror)

---

### Content Security Policy (CSP)

**Rule**: Restrict script sources to prevent XSS

**Implementation**:
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # Allow inline scripts (tighten if possible)
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'"
    )
    return response
```

**Checklist**:
- [ ] CSP header set
- [ ] Script sources restricted
- [ ] Inline scripts minimized
- [ ] CSP violations monitored

---

## SQL Injection Prevention

### Parameterized Queries (Always)

**Risk**: SQL injection

**Rule**: Never concatenate user input into SQL

**Bad**:
```python
# NEVER DO THIS
vendor_id = request.form.get("vendor_id")
query = f"SELECT * FROM vendor WHERE vendor_id = {vendor_id}"  # SQL INJECTION
cursor.execute(query)
```

**Good**:
```python
vendor_id = request.form.get("vendor_id")
query = "SELECT * FROM vendor WHERE vendor_id = ?"  # Parameterized
cursor.execute(query, (vendor_id,))
```

**Checklist**:
- [ ] All queries use parameterized statements
- [ ] No f-strings with user input in SQL
- [ ] Repository pattern enforces parameterization
- [ ] Lint rule detects SQL concatenation

---

## Authentication and Authorization

### Session Management

**Rule**: Secure session cookies

**Pattern**:
```python
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key="<SECURE_RANDOM_KEY>",  # From environment variable
    session_cookie="vendorcat_session",
    max_age=28800,  # 8 hours
    same_site="lax",
    https_only=True  # Require HTTPS in production
)
```

**Checklist**:
- [ ] Session secret in environment variable (not hardcoded)
- [ ] Cookie httpOnly=True
- [ ] Cookie secure=True in production
- [ ] Session timeout configured (8 hours)
- [ ] Session regenerated on login

---

### Password Storage

**Rule**: Hash passwords with bcrypt

**Pattern**:
```python
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

**Checklist**:
- [ ] Passwords hashed with bcrypt (or argon2)
- [ ] No plaintext passwords in database
- [ ] Password complexity requirements enforced
- [ ] Password reset tokens expire (1 hour)

**Note**: VendorCatalog uses Databricks auth (not local passwords), but document for potential future use.

---

## Secrets Management

### Environment Variables

**Rule**: Never hardcode secrets

**Bad**:
```python
# NEVER DO THIS
DB_PASSWORD = "my_secret_password"  # Hardcoded secret
```

**Good**:
```python
import os

DB_PASSWORD = os.environ.get("DB_PASSWORD")
if not DB_PASSWORD:
    raise RuntimeError("DB_PASSWORD environment variable not set")
```

**Checklist**:
- [ ] All secrets in environment variables
- [ ] No secrets committed to git
- [ ] .env files in .gitignore
- [ ] Secrets rotated quarterly

---

### API Keys

**Rule**: Protect API keys, rotate regularly

**Pattern**:
```python
# Generate API key
import secrets

api_key = secrets.token_urlsafe(32)

# Store hashed version in database
hashed_key = hash_password(api_key)
repo.create_api_key(user_id=123, hashed_key=hashed_key)

# Show key once to user (cannot retrieve later)
print(f"Your API key (save it now): {api_key}")
```

**Checklist**:
- [ ] API keys hashed before storage
- [ ] Keys shown once on creation
- [ ] Keys expire after 90 days
- [ ] Key rotation process documented

---

## Rate Limiting

### Request Rate Limiting

**Risk**: Brute force, DoS attacks

**Rule**: Limit requests per user/IP

**Pattern**:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

@app.post("/login")
@limiter.limit("5/minute")  # 5 login attempts per minute
async def login(request: Request):
    # ... login logic
```

**Checklist**:
- [ ] Login endpoint rate limited (5/min)
- [ ] API endpoints rate limited (100/min per user)
- [ ] Rate limit varies by endpoint sensitivity
- [ ] Rate limit headers returned (X-RateLimit-*)

---

## Dependency Security

### Vulnerability Scanning

**Rule**: Scan dependencies for known vulnerabilities

**Tool**: `pip-audit`

**Usage**:
```bash
pip-audit --desc
```

**Checklist**:
- [ ] Dependencies scanned weekly
- [ ] High/Critical vulnerabilities fixed within 7 days
- [ ] Dependabot enabled on GitHub repo
- [ ] Security alerts monitored

---

### Dependency Pinning

**Rule**: Pin exact versions in requirements.txt

**Pattern**:
```txt
# Good: Exact versions
fastapi==0.115.0
uvicorn==0.32.0
databricks-sql-connector==3.5.0

# Bad: Unpinned versions
fastapi
uvicorn>=0.30.0
```

**Checklist**:
- [ ] All dependencies pinned to exact versions
- [ ] Dependencies updated monthly (not automatically)
- [ ] Updates tested before production deploy

---

## HTTPS and Transport Security

### HTTPS Enforcement

**Rule**: Require HTTPS in production

**Pattern**:
```python
@app.middleware("http")
async def enforce_https(request: Request, call_next):
    if request.url.scheme != "https" and not request.url.hostname == "localhost":
        return RedirectResponse(str(request.url).replace("http://", "https://"), status_code=301)
    return await call_next(request)
```

**Checklist**:
- [ ] HTTPS enforced in production
- [ ] HTTP redirects to HTTPS
- [ ] HSTS header set (Strict-Transport-Security)
- [ ] Valid SSL certificate

---

### Security Headers

**Rule**: Set security headers on all responses

**Pattern**:
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

**Checklist**:
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY (prevent clickjacking)
- [ ] X-XSS-Protection: 1; mode=block
- [ ] Strict-Transport-Security (HSTS)
- [ ] Content-Security-Policy set

---

## Logging and Monitoring

### Sensitive Data in Logs

**Rule**: Never log passwords, tokens, PII

**Bad**:
```python
logger.info(f"User login: username={username}, password={password}")  # NEVER LOG PASSWORD
```

**Good**:
```python
logger.info(f"User login: username={username}")  # No password
```

**Checklist**:
- [ ] Passwords never logged
- [ ] API keys never logged
- [ ] PII redacted in logs (email → e***@example.com)
- [ ] Log scrubbing regex applied

---

### Security Event Logging

**Rule**: Log all security-relevant events

**Events to log**:
- Login success/failure
- Permission grant/deny
- Admin actions (role change, user delete)
- Suspicious activity (SQL injection attempt, XSS attempt)

**Pattern**:
```python
def log_security_event(event_type: str, user: str, details: dict):
    logger.warning(json.dumps({
        "event": "security",
        "type": event_type,
        "user": user,
        "details": details,
        "timestamp": datetime.utcnow().isoformat()
    }))
```

**Checklist**:
- [ ] Security events logged
- [ ] Logs sent to SIEM (if available)
- [ ] Alerts configured for suspicious patterns

---

## Deployment Security

### Production Configuration

**Checklist**:
- [ ] DEBUG mode disabled
- [ ] Exception details hidden in prod (no stack traces to users)
- [ ] Admin panel disabled or password-protected
- [ ] Default credentials changed
- [ ] Unused endpoints disabled

---

### Database Security

**Checklist**:
- [ ] Database user has minimal permissions (no DROP, CREATE USER)
- [ ] Database connection encrypted (TLS)
- [ ] Database backups encrypted
- [ ] Read-only credentials for analytics users

---

## Security Review Cadence

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Dependency vulnerability scan | Weekly | Tech Lead |
| Security header check | Monthly | Tech Lead |
| Penetration test | Annually | Security Team |
| Access review (who has admin?) | Quarterly | Security Lead |
| Secrets rotation | Quarterly | Ops Team |
| Security training | Annually | All developers |

---

Last updated: 2026-02-15
