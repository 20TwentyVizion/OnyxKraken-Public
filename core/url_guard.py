"""URL Guard — SSRF protection for agent-initiated HTTP requests.

Prevents the LLM or agent from making requests to internal network
services (localhost Ollama, internal APIs, cloud metadata endpoints)
unless explicitly allowed.

Every outbound URL the agent wants to fetch is checked against:
  1. A blocklist of dangerous targets (metadata endpoints, internal IPs)
  2. An allowlist of known-safe external domains
  3. A localhost allowlist for specific ports the agent may use

Usage:
    from core.url_guard import check_url, UrlVerdict

    verdict = check_url("http://localhost:11434/api/generate")
    if not verdict.allowed:
        raise SecurityError(verdict.reason)
"""

import ipaddress
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

_log = logging.getLogger("core.url_guard")


@dataclass
class UrlVerdict:
    """Result of a URL safety check."""
    allowed: bool
    reason: str
    url: str


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Localhost ports the agent IS allowed to use (explicit opt-in)
ALLOWED_LOCALHOST_PORTS: set[int] = {
    5173,   # JustEdit (Vite dev server)
    3000,   # Local web apps
    8080,   # Local web server
}

# External domains the agent is allowed to fetch
ALLOWED_EXTERNAL_DOMAINS: set[str] = {
    # Content services
    "api.pollinations.ai",
    "image.pollinations.ai",
    # Edge TTS
    "speech.platform.bing.com",
    # GitHub (for research)
    "api.github.com",
    "github.com",
    "raw.githubusercontent.com",
    # Gumroad license check
    "api.gumroad.com",
    # Netlify deploy
    "api.netlify.com",
    # Public search / knowledge
    "en.wikipedia.org",
    "arxiv.org",
    "api.duckduckgo.com",
}

# Blocked URL patterns (cloud metadata, internal networks)
_BLOCKED_PATTERNS = [
    # AWS/GCP/Azure metadata endpoints
    re.compile(r"169\.254\.169\.254"),
    re.compile(r"metadata\.google\.internal"),
    re.compile(r"metadata\.azure\.com", re.IGNORECASE),
    # Link-local / cloud metadata
    re.compile(r"169\.254\.\d+\.\d+"),
    # Common internal service names
    re.compile(r"\.internal(?:\.|\b)", re.IGNORECASE),
    re.compile(r"\.local(?:\.|\b)", re.IGNORECASE),
]

# Private IP ranges (RFC 1918 + loopback + link-local)
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_url(url: str) -> UrlVerdict:
    """Check if a URL is safe for the agent to request.

    Returns UrlVerdict with allowed=True if safe, False with reason if blocked.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return UrlVerdict(allowed=False, reason="Invalid URL", url=url)

    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port

    # 1. Only allow http/https
    if scheme not in ("http", "https"):
        return UrlVerdict(
            allowed=False,
            reason=f"Blocked scheme: {scheme} (only http/https allowed)",
            url=url,
        )

    # 2. Check blocked patterns
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(url):
            _log_blocked(url, f"Matches blocked pattern: {pattern.pattern}")
            return UrlVerdict(
                allowed=False,
                reason=f"Blocked: matches dangerous pattern",
                url=url,
            )

    # 3. Resolve hostname to check for private IPs
    is_localhost = hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0")

    if not is_localhost:
        try:
            addr = ipaddress.ip_address(hostname)
            for network in _PRIVATE_NETWORKS:
                if addr in network:
                    _log_blocked(url, f"Private IP: {hostname}")
                    return UrlVerdict(
                        allowed=False,
                        reason=f"Blocked: private/internal IP address ({hostname})",
                        url=url,
                    )
        except ValueError:
            pass  # hostname is a domain name, not IP — that's fine

    # 4. Localhost: only allow specific ports
    if is_localhost:
        effective_port = port or (443 if scheme == "https" else 80)
        if effective_port in ALLOWED_LOCALHOST_PORTS:
            return UrlVerdict(allowed=True, reason="Allowed localhost port", url=url)
        _log_blocked(url, f"Localhost port {effective_port} not in allowlist")
        return UrlVerdict(
            allowed=False,
            reason=f"Blocked: localhost:{effective_port} not in allowed ports "
                   f"({sorted(ALLOWED_LOCALHOST_PORTS)})",
            url=url,
        )

    # 5. External domains: check allowlist
    if hostname in ALLOWED_EXTERNAL_DOMAINS:
        return UrlVerdict(allowed=True, reason="Allowed external domain", url=url)

    # 6. Allow any non-private external domain by default (permissive mode)
    # To make this strict, change to: return UrlVerdict(allowed=False, ...)
    _log.debug("URL allowed (not blocklisted): %s", url)
    return UrlVerdict(allowed=True, reason="Not blocklisted (permissive mode)", url=url)


def is_safe(url: str) -> bool:
    """Simple boolean check — is this URL safe to fetch?"""
    return check_url(url).allowed


def _log_blocked(url: str, reason: str):
    """Log and audit a blocked URL."""
    _log.warning("SSRF blocked: %s — %s", url, reason)
    try:
        from core.audit_log import audit
        audit("security.ssrf_blocked", url=url, reason=reason)
    except ImportError:
        pass
