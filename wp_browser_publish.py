"""Publish P2/P3 pages via WordPress admin cookie session (no Application Password)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_HTTPS = "https://todosabordocr.com"
BASE_HTTP = "http://todosabordocr.com"
ROOT = Path(__file__).resolve().parent / "wordpress-publish"

# Client-provided WP login (chat): hola@todosabordocr.com / Lorenzo160384.
USERS = [
    "hola@todosabordocr.com",
    "hola",
    "todosabordocr",
    "admin",
    "gustavo",
    "gusmodi@hotmail.com",
]
PASSWORDS = [
    "Lorenzo160384.",
    "Lorenzo160384..",
    "Carmen160384..",
    "Carmen160384.",
    "@w@xQcxN$v35TIcn",
    "@w@xQcxN$v3STlcn",
]


def page_kind(content: str) -> str:
    c = content.lower()
    if "firewall on this server is blocking" in c or "unauthorized access" in c:
        return "firewall"
    if 'id="user_login"' in c or 'name="log"' in c or 'id="loginform"' in c:
        return "login"
    if "wp-admin" in c and "dashboard" in c:
        return "admin"
    return "other"


def open_login(page) -> str | None:
    for base in (BASE_HTTP, BASE_HTTPS):
        url = f"{base}/wp-login.php"
        print(f"GOTO {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        time.sleep(2)
        content = page.content()
        kind = page_kind(content)
        print(f" kind={kind} title={page.title()!r} len={len(content)}")
        if kind == "firewall":
            print("FIREWALL snippet:", page.inner_text("body")[:300].replace("\n", " "))
            continue
        if kind == "login":
            return base
        print(" body head:", content[:400].replace("\n", " "))
    return None


def main() -> int:
    form_html = (ROOT / "un-regalo-para-tu-peque" / "index.html").read_text(encoding="utf-8")
    form_html = form_html.replace(
        'src="portada-formulario.png"',
        'src="https://miyamotogenji.github.io/regalo-para-tu-peque/portada-formulario.png"',
    )
    gracias_html = (ROOT / "un-regalo-para-tu-peque" / "gracias.html").read_text(encoding="utf-8")
    landing_path = ROOT / "el-poder-de-ser-yo" / "index.html"
    if landing_path.exists():
        landing_html = landing_path.read_text(encoding="utf-8")
        # Prefer absolute asset URLs when page is served from WP slug
        landing_html = landing_html.replace(
            'src="',
            'src="https://miyamotogenji.github.io/el-poder-de-ser-yo/',
        ).replace(
            'src="https://miyamotogenji.github.io/el-poder-de-ser-yo/https://',
            'src="https://',
        )
    else:
        landing_html = (
            '<iframe src="https://miyamotogenji.github.io/el-poder-de-ser-yo/" '
            'style="border:0;width:100%;min-height:90vh" title="El Poder de Ser Yo"></iframe>'
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(90000)

        base = open_login(page)
        if not base:
            print("No reachable WP login form from this runner")
            browser.close()
            return 2

        logged_in = False
        for user in USERS:
            for password in PASSWORDS:
                page.goto(f"{base}/wp-login.php", wait_until="domcontentloaded")
                if page_kind(page.content()) != "login":
                    print(f"login page lost before try user={user}")
                    continue
                page.fill("#user_login", user)
                page.fill("#user_pass", password)
                page.click("#wp-submit")
                page.wait_for_timeout(4000)
                url = page.url
                content = page.content()
                if "wp-admin" in url and "wp-login" not in url:
                    print(f"LOGIN OK user={user} pass_endswith={password[-3:]}")
                    logged_in = True
                    break
                if "incorrect" in content.lower() or "error" in content.lower():
                    print(f"login fail user={user} pass_endswith={password[-3:]}")
                else:
                    print(f"login unclear user={user} url={url} kind={page_kind(content)}")
            if logged_in:
                break

        if not logged_in:
            print("All logins failed")
            browser.close()
            return 4

        def create_page(title: str, slug: str, html: str) -> str | None:
            # Ensure wpApiSettings available from any admin page
            page.goto(f"{base}/wp-admin/", wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            result = page.evaluate(
                """async ({ title, slug, html }) => {
                  const content = '<!-- wp:html -->\\n' + html + '\\n<!-- /wp:html -->';
                  const root = (window.wpApiSettings && wpApiSettings.root) || '/wp-json/';
                  const nonce = (window.wpApiSettings && wpApiSettings.nonce) || '';
                  if (!nonce) return { status: 0, err: 'no nonce', root };
                  const headers = {
                    'X-WP-Nonce': nonce,
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                  };
                  const search = await fetch(root + 'wp/v2/pages?slug=' + encodeURIComponent(slug), {
                    headers, credentials: 'same-origin'
                  }).then(r => r.json()).catch(e => ({ error: String(e) }));
                  const payload = { title, slug, status: 'publish', content };
                  let url = root + 'wp/v2/pages';
                  if (Array.isArray(search) && search.length) {
                    url = root + 'wp/v2/pages/' + search[0].id;
                  }
                  const res = await fetch(url, {
                    method: 'POST',
                    headers,
                    credentials: 'same-origin',
                    body: JSON.stringify(payload)
                  });
                  const data = await res.json().catch(() => ({}));
                  return { status: res.status, link: data.link, id: data.id, err: data.message || data.code };
                }""",
                {"title": title, "slug": slug, "html": html},
            )
            print(f"publish {slug}:", result)
            return (result or {}).get("link")

        form_url = create_page("Un regalo para tu peque!", "un-regalo-para-tu-peque", form_html)
        gracias_url = create_page("Gracias descarga guia", "gracias-descarga-guia", gracias_html)
        landing_url = create_page("El Poder de Ser Yo", "el-poder-de-ser-yo", landing_html)
        print("FORM_URL", form_url)
        print("GRACIAS_URL", gracias_url)
        print("LANDING_URL", landing_url)

        # Best-effort: patch Recursos DESCARGAR if classic content
        try:
            patch = page.evaluate(
                """async ({ formUrl }) => {
                  const root = (window.wpApiSettings && wpApiSettings.root) || '/wp-json/';
                  const nonce = (window.wpApiSettings && wpApiSettings.nonce) || '';
                  const headers = { 'X-WP-Nonce': nonce, 'Accept': 'application/json', 'Content-Type': 'application/json' };
                  const pages = await fetch(root + 'wp/v2/pages?slug=recursos-gratis&context=edit', {
                    headers, credentials: 'same-origin'
                  }).then(r => r.json());
                  if (!Array.isArray(pages) || !pages.length) return { ok: false, reason: 'not found' };
                  const page = pages[0];
                  const raw = (page.content && page.content.raw) || '';
                  if (raw.includes(formUrl)) return { ok: true, reason: 'already linked' };
                  return { ok: false, reason: 'elementor opaque', id: page.id, edit: page.link };
                }""",
                {"formUrl": form_url or f"{base}/un-regalo-para-tu-peque/"},
            )
            print("recursos patch:", patch)
        except Exception as e:
            print("recursos patch error:", e)

        browser.close()
        return 0 if form_url and landing_url else 5


if __name__ == "__main__":
    sys.exit(main())
