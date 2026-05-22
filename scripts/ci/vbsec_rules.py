"""vbsec rule IDs and deterministic patterns aligned with tanviet12/vbsec."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Canonical rule set (https://github.com/tanviet12/vbsec)
ALL_VBSEC_RULE_IDS: tuple[str, ...] = (
    "HARDCODED-SECRET",
    "SQL-INJECTION",
    "XSS",
    "IDOR",
    "SLOPSQUATTING",
    "BRUTE-FORCE",
    "MASS-ASSIGNMENT",
    "INSECURE-DESERIALIZATION",
    "SSRF",
    "PATH-TRAVERSAL",
    "CSRF",
    "BROKEN-ACCESS-CONTROL",
    "WEAK-PASSWORD-HASHING",
    "JWT-NONE-ALGORITHM",
    "CORS-MISCONFIG",
    "UNRESTRICTED-FILE-UPLOAD",
    "VERBOSE-ERROR-DEBUG-MODE",
    "MISSING-RATE-LIMIT",
    "RACE-CONDITION",
    "OUTDATED-DEPENDENCY",
    "COMMAND-INJECTION",
)

# Known typosquat / suspicious package names (subset from vbsec SLOPSQUATTING rule)
TYPOSQUAT_PACKAGES: frozenset[str] = frozenset(
    {
        "requets",
        "requestes",
        "urlib3",
        "python-dateutil2",
        "djando",
        "flaskk",
        "fastpai",
        "pyjwt2",
        "boto33",
        "cryptograpy",
        "passlib2",
        "cross-env.js",
        "event-stream",
    }
)

BANDIT_TO_VBSEC: dict[str, tuple[str, str]] = {
    "B102": ("COMMAND-INJECTION", "CRITICAL"),
    "B104": ("BROKEN-ACCESS-CONTROL", "MEDIUM"),
    "B201": ("VERBOSE-ERROR-DEBUG-MODE", "HIGH"),
    "B301": ("INSECURE-DESERIALIZATION", "CRITICAL"),
    "B303": ("WEAK-PASSWORD-HASHING", "HIGH"),
    "B324": ("WEAK-PASSWORD-HASHING", "HIGH"),
    "B307": ("COMMAND-INJECTION", "HIGH"),
    "B501": ("BROKEN-ACCESS-CONTROL", "HIGH"),
    "B506": ("BROKEN-ACCESS-CONTROL", "HIGH"),
    "B608": ("SQL-INJECTION", "CRITICAL"),
    "B701": ("BROKEN-ACCESS-CONTROL", "HIGH"),
}


@dataclass(frozen=True)
class PatternRule:
    rule_id: str
    severity: str
    issue_summary: str
    fix_summary: str
    pattern: re.Pattern[str]
    extensions: frozenset[str] = frozenset({".py", ".ts", ".tsx", ".js", ".jsx"})


def get_pattern_rules() -> list[PatternRule]:
    """High-signal patterns derived from vbsec generic + language overlays."""
    return [
        # JWT
        PatternRule(
            "JWT-NONE-ALGORITHM",
            "CRITICAL",
            "JWT verify disabled or none algorithm",
            "Use RS256/HS256; never verify=False or algorithms=['none']",
            re.compile(
                r"verify\s*=\s*False|algorithms\s*=\s*\[[^\]]*['\"]none['\"]",
                re.I,
            ),
        ),
        # Deserialization
        PatternRule(
            "INSECURE-DESERIALIZATION",
            "CRITICAL",
            "Unsafe deserialization (pickle/yaml load)",
            "Avoid pickle.loads; use yaml.safe_load only",
            re.compile(r"pickle\.loads\s*\(|yaml\.load\s*\([^)]*\)", re.I),
        ),
        PatternRule(
            "INSECURE-DESERIALIZATION",
            "CRITICAL",
            "marshal.loads usage",
            "Do not deserialize untrusted marshal data",
            re.compile(r"marshal\.loads\s*\(", re.I),
        ),
        # Command injection
        PatternRule(
            "COMMAND-INJECTION",
            "CRITICAL",
            "subprocess with shell=True",
            "Use shell=False and argument list",
            re.compile(
                r"subprocess\.(run|Popen|call|check_output)\([^)]*shell\s*=\s*True",
                re.I,
            ),
        ),
        PatternRule(
            "COMMAND-INJECTION",
            "CRITICAL",
            "os.system with dynamic input",
            "Use subprocess without shell; validate input",
            re.compile(r"os\.system\s*\(\s*[^\"']", re.I),
        ),
        PatternRule(
            "COMMAND-INJECTION",
            "HIGH",
            "eval/exec on dynamic input",
            "Remove eval/exec; use safe parsers",
            re.compile(r"\b(eval|exec)\s*\(\s*[^\"']", re.I),
        ),
        # SQL
        PatternRule(
            "SQL-INJECTION",
            "CRITICAL",
            "Dynamic SQL string formatting",
            "Use parameterized queries / ORM",
            re.compile(
                r"(execute|executemany)\s*\(\s*f[\"']|\.format\s*\([^)]*\)\s*%|"
                r"SELECT\s+.*\+\s*|\.raw\s*\(\s*f[\"']",
                re.I,
            ),
        ),
        # SSRF — flag only when the URL argument is plausibly user/request-controlled
        PatternRule(
            "SSRF",
            "HIGH",
            "HTTP client called with request-derived URL",
            "Validate URL host/IP; use allowlist (see url_safety)",
            re.compile(
                r"requests\.(get|post|put|delete|request)\s*\(\s*"
                r"(?:request\.|body\.|params\.|query\.|form\.|headers\.|"
                r"(?:req|ctx|payload|input|data|user_)\.)",
                re.I,
            ),
        ),
        PatternRule(
            "SSRF",
            "HIGH",
            "httpx called with request-derived URL",
            "Validate URL host/IP; use allowlist (see url_safety)",
            re.compile(
                r"httpx\.(get|post|put|delete|request)\s*\(\s*"
                r"(?:request\.|body\.|params\.|query\.|form\.|headers\.|"
                r"(?:req|ctx|payload|input|document_url|target_url|download_url|redirect_url))",
                re.I,
            ),
        ),
        PatternRule(
            "SSRF",
            "HIGH",
            "urllib urlopen with request-derived URL",
            "Validate URL host/IP; use allowlist (see url_safety)",
            re.compile(
                r"urllib\.request\.urlopen\s*\(\s*"
                r"(?:request\.|body\.|params\.|query\.|form\.|headers\.|"
                r"(?:req|ctx|payload|input|document_url|target_url|download_url))",
                re.I,
            ),
        ),
        PatternRule(
            "SSRF",
            "HIGH",
            "fetch/axios with user-controlled URL",
            "Restrict origins; block private IPs",
            re.compile(
                r"(fetch|axios\.(get|post|request))\s*\(\s*(req\.|params\.|body\.|[a-zA-Z_]+\.url)",
                re.I,
            ),
            extensions=frozenset({".ts", ".tsx", ".js", ".jsx"}),
        ),
        # Path traversal
        PatternRule(
            "PATH-TRAVERSAL",
            "HIGH",
            "File open with dynamic path",
            "Normalize path and enforce base directory prefix",
            re.compile(
                r"open\s*\(\s*[a-zA-Z_][\w.]*\s*,|"
                r"Path\s*\(\s*[a-zA-Z_][\w.]*\s*\)\s*\.(read|write)|"
                r"os\.path\.join\s*\([^)]*,\s*(req\.|params\.|[a-zA-Z_]+\.)",
                re.I,
            ),
        ),
        # XSS
        PatternRule(
            "XSS",
            "HIGH",
            "Unsafe HTML/DOM sink",
            "Sanitize with DOMPurify/bleach; avoid raw HTML sinks",
            re.compile(
                r"dangerouslySetInnerHTML|v-html\s*=|\.innerHTML\s*=|"
                r"bypassSecurityTrust(Html|Script|Url)|\{\{\{\s*",
                re.I,
            ),
        ),
        PatternRule(
            "XSS",
            "HIGH",
            "Jinja/Twig safe filter bypass",
            "Remove |safe / |raw on user content",
            re.compile(r"\|\s*(safe|raw)\b", re.I),
            extensions=frozenset({".py", ".html", ".jinja", ".j2"}),
        ),
        # Mass assignment
        PatternRule(
            "MASS-ASSIGNMENT",
            "CRITICAL",
            "Bulk update from untrusted dict",
            "Use explicit allowlist of fields on models",
            re.compile(
                r"\.update\s*\(\s*\*\*|Object\.assign\s*\([^,]+,\s*req\.|"
                r"setattr\s*\([^,]+,\s*[^'\"]+,\s*[^)]*request",
                re.I,
            ),
        ),
        # CORS
        PatternRule(
            "CORS-MISCONFIG",
            "HIGH",
            "CORS wildcard with credentials",
            "Use explicit origin allowlist; never * + credentials",
            re.compile(
                r"allow_origins\s*=\s*\[[^\]]*['\"]\*['\"][^\]]*\].*allow_credentials\s*=\s*True|"
                r"Access-Control-Allow-Origin['\"]\s*,\s*['\"]\*['\"].*credentials\s*:\s*true|"
                r"cors\s*\(\s*\{[^}]*origin\s*:\s*(true|['\"]\*['\"])[^}]*credentials\s*:\s*true",
                re.I | re.S,
            ),
        ),
        PatternRule(
            "CORS-MISCONFIG",
            "HIGH",
            "Echo Origin header with credentials",
            "Whitelist fixed origins",
            re.compile(
                r"Access-Control-Allow-Origin['\"]\s*,\s*.*req\.headers\.origin|"
                r"allow_origin_regex\s*=\s*['\"].*\*",
                re.I,
            ),
        ),
        # CSRF (cookie session without protection)
        PatternRule(
            "CSRF",
            "HIGH",
            "Session cookie without SameSite",
            "Set SameSite=Lax/Strict; add CSRF token for cookie auth",
            re.compile(
                r"set_cookie\s*\((?![^)]*same_site)[^)]*\)|"
                r"SessionMiddleware\s*\((?![^)]*same_site)[^)]*\)",
                re.I | re.S,
            ),
        ),
        # File upload
        PatternRule(
            "UNRESTRICTED-FILE-UPLOAD",
            "CRITICAL",
            "Upload without content-type/size validation",
            "Validate MIME, extension allowlist, and max size",
            re.compile(
                r"UploadFile\s*\((?![^)]*content_type)(?![^)]*size)[^)]*\)",
                re.I | re.S,
            ),
            extensions=frozenset({".py"}),
        ),
        PatternRule(
            "UNRESTRICTED-FILE-UPLOAD",
            "HIGH",
            "Multer/express upload without limits",
            "Add fileFilter, limits.fileSize, and MIME checks",
            re.compile(r"multer\s*\(\s*\{[^}]*\}\s*\)(?!.*limits)", re.I | re.S),
            extensions=frozenset({".ts", ".js"}),
        ),
        # Debug / verbose errors
        PatternRule(
            "VERBOSE-ERROR-DEBUG-MODE",
            "HIGH",
            "Debug mode enabled in app config",
            "Disable debug in production; use structured logging",
            re.compile(
                r"APP_ENV\s*=\s*['\"]development['\"]|debug\s*=\s*True|"
                r"FLASK_DEBUG\s*=\s*1|werkzeug\.run_simple\s*\(",
                re.I,
            ),
        ),
        # Weak hashing
        PatternRule(
            "WEAK-PASSWORD-HASHING",
            "CRITICAL",
            "MD5/SHA1 password hashing",
            "Use bcrypt/argon2/scrypt",
            re.compile(r"hashlib\.(md5|sha1)\s*\([^)]*password", re.I),
        ),
        # Rate limit / brute force
        PatternRule(
            "BRUTE-FORCE",
            "HIGH",
            "Login/auth endpoint without rate limit decorator",
            "Add @limiter.limit on login/register/reset routes",
            re.compile(
                r"@router\.(post|put)\s*\(\s*['\"][^'\"]*/(login|signin|register|reset)[^'\"]*['\"]"
                r"[^)]*\)\s*\n(?!.*@limiter\.limit)",
                re.I | re.S,
            ),
            extensions=frozenset({".py"}),
        ),
        PatternRule(
            "MISSING-RATE-LIMIT",
            "HIGH",
            "Expensive AI/external call without rate limit nearby",
            "Add per-user rate limits on costly endpoints",
            re.compile(
                r"openai\.(chat|completions|images)|anthropic\.messages|"
                r"sendgrid\.|twilio\.",
                re.I,
            ),
        ),
        # Race condition (file write heuristics)
        PatternRule(
            "RACE-CONDITION",
            "MEDIUM",
            "Check-then-act on shared file without lock",
            "Use file locks, DB transactions, or atomic writes",
            re.compile(
                r"if\s+not\s+os\.path\.exists\s*\([^)]+\):\s*\n\s*open\s*\(",
                re.I,
            ),
            extensions=frozenset({".py"}),
        ),
        # Secrets in workflow/json
        PatternRule(
            "HARDCODED-SECRET",
            "CRITICAL",
            "Hardcoded API key/password in JSON workflow",
            "Use n8n credentials store or env vars",
            re.compile(
                r'"(api[_-]?key|password|secret|token|private[_-]?key)"\s*:\s*"[^{][^"]{8,}"',
                re.I,
            ),
            extensions=frozenset({".json"}),
        ),
        # SQL in migrations
        PatternRule(
            "SQL-INJECTION",
            "HIGH",
            "Dynamic SQL in migration (review manually)",
            "Use static SQL or parameterized migrations only",
            re.compile(r"EXECUTE\s+.*\|\||format\s*\(", re.I),
            extensions=frozenset({".sql"}),
        ),
    ]
