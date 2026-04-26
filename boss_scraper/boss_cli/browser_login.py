"""Browser-assisted login enhancement via Camoufox.

Hybrid approach:
1. Complete the QR login flow via HTTP (httpx) to obtain session cookies
   (wt2, wbg, zp_at).
2. Inject those cookies into a Camoufox browser and navigate to the site
   so that client-side JavaScript generates ``__zp_stoken__``.
3. Export all cookies from the browser context.

This gives us the complete cookie set that pure HTTP cannot achieve.

NOTE: Boss Zhipin uses aggressive anti-bot detection that may prevent
``__zp_stoken__`` generation even in Camoufox.  The QR login still
works without it for most APIs (recommend, chat, applied, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from typing import Any

from .auth import Credential, qr_login, save_credential
from .constants import BASE_URL

logger = logging.getLogger(__name__)

# Cookie domains to export from browser
BROWSER_EXPORT_DOMAINS = (".zhipin.com", "zhipin.com", "www.zhipin.com")


class BrowserLoginUnavailable(RuntimeError):
    """Raised when the camoufox browser backend cannot be started."""


def _ensure_camoufox_ready() -> None:
    """Validate that the Camoufox package and browser binary are available."""
    try:
        import camoufox  # noqa: F401
    except ImportError as exc:
        raise BrowserLoginUnavailable(
            "camoufox 未安装。安装: pip install 'kabi-boss-cli[browser]'"
        ) from exc

    try:
        result = subprocess.run(
            [sys.executable, "-m", "camoufox", "path"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BrowserLoginUnavailable(
            "无法验证 Camoufox 浏览器安装状态。"
        ) from exc

    if result.returncode != 0 or not result.stdout.strip():
        raise BrowserLoginUnavailable(
            "Camoufox 浏览器运行时缺失。运行: python -m camoufox fetch"
        )


def _normalize_browser_cookies(raw_cookies: list[dict[str, Any]]) -> dict[str, str]:
    """Convert Playwright cookie entries into a flat dict, filtering to zhipin.com."""
    cookies: dict[str, str] = {}
    for entry in raw_cookies:
        name = entry.get("name")
        value = entry.get("value")
        domain = entry.get("domain", "")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        if not any(domain.endswith(d) for d in BROWSER_EXPORT_DOMAINS):
            continue
        cookies[name] = value
    return cookies


def _hydrate_stoken_via_browser(cookies: dict[str, str]) -> dict[str, str]:
    """Inject session cookies into a Camoufox browser and harvest __zp_stoken__.

    Boss Zhipin's client-side JS generates __zp_stoken__ on page load.
    We open a browser with the session cookies already set, visit the
    site, and let JS run.

    NOTE: This may fail if the anti-bot JS fingerprints the browser
    environment and refuses to generate the token.
    """
    from camoufox.sync_api import Camoufox

    playwright_cookies = []
    for name, value in cookies.items():
        playwright_cookies.append({
            "name": name,
            "value": value,
            "domain": ".zhipin.com",
            "path": "/",
        })

    with Camoufox(headless=True) as browser:
        context = browser.new_context()
        context.add_cookies(playwright_cookies)
        page = context.new_page()

        try:
            page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=20_000)
        except Exception:
            logger.debug("Camoufox page load did not reach networkidle")

        # Give JS time to set cookies
        try:
            page.wait_for_timeout(3000)
        except Exception:
            pass

        result = _normalize_browser_cookies(context.cookies())

    return result


def browser_qr_login(
    *,
    on_status: callable | None = None,
) -> Credential:
    """Hybrid QR login: HTTP for session + Camoufox for __zp_stoken__.

    1. Run the standard HTTP QR login flow (user scans in terminal)
    2. If __zp_stoken__ is missing, try headless Camoufox to generate it
    3. Return the credential (complete or partial)
    """
    _ensure_camoufox_ready()

    def _emit(msg: str) -> None:
        if on_status:
            on_status(msg)
        else:
            print(msg)

    # Step 1: Complete QR login via HTTP (reuse existing flow)
    cred = asyncio.run(qr_login())

    # Step 2: If __zp_stoken__ is missing, try to hydrate via browser
    if "__zp_stoken__" not in cred.cookies:
        _emit("\n🔧 正在通过浏览器补全 __zp_stoken__...")

        try:
            enriched = _hydrate_stoken_via_browser(cred.cookies)
        except Exception as exc:
            logger.warning("Browser __zp_stoken__ hydration failed: %s", exc)
            _emit("⚠️  浏览器补全 __zp_stoken__ 失败")
            return cred

        if "__zp_stoken__" in enriched:
            merged = {**cred.cookies, **enriched}
            cred = Credential(cookies=merged)
            save_credential(cred)
            _emit("✅ __zp_stoken__ 补全成功！所有接口可正常使用")
        else:
            _emit("⚠️  浏览器未能生成 __zp_stoken__（Boss 直聘反爬检测）")
            _emit("   recommend/chat/applied 等接口仍可使用，search 可能受限")

    return cred
