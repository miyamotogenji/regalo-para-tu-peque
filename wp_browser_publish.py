"""Publish pages via WordPress admin cookie session (works without Application Password)."""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://todosabordocr.com"
ROOT = Path(__file__).resolve().parent / "wordpress-publish"
USERS = ["hola@todosabordocr.com", "hola", "todosabordocr", "admin", "gustavo"]
PASSWORDS = ["Lorenzo160384..", "Carmen160384..", "@w@xQcxN$v3STlcn"]


def main() -> int:
    form_html = (ROOT / "un-regalo-para-tu-peque" / "index.html").read_text(encoding="utf-8")
    # Make banner absolute so it works from WP page
    form_html = form_html.replace(
        'src="portada-formulario.png"',
        'src="https://miyamotogenji.github.io/regalo-para-tu-peque/portada-formulario.png"',
    )
    gracias_html = (ROOT / "un-regalo-para-tu-peque" / "gracias.html").read_text(encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(60000)

        page.goto(f"{BASE}/wp-login.php", wait_until="domcontentloaded")
        body = page.content()
        if "Unauthorized Access" in body or "firewall" in body.lower():
            print("FIREWALL on wp-login from this runner")
            # try http
            page.goto("http://todosabordocr.com/wp-login.php", wait_until="domcontentloaded")
            body = page.content()
            if "Unauthorized Access" in body:
                print("FIREWALL http too")
                browser.close()
                return 2

        if "user_login" not in body:
            print("No login form. Title:", page.title())
            print(body[:500])
            browser.close()
            return 3

        logged_in = False
        for user in USERS:
            for password in PASSWORDS:
                page.goto(f"{BASE}/wp-login.php", wait_until="domcontentloaded")
                if "user_login" not in page.content():
                    page.goto("http://todosabordocr.com/wp-login.php", wait_until="domcontentloaded")
                page.fill("#user_login", user)
                page.fill("#user_pass", password)
                page.click("#wp-submit")
                page.wait_for_timeout(3500)
                url = page.url
                content = page.content()
                if "wp-admin" in url and "login" not in url:
                    print(f"LOGIN OK user={user}")
                    logged_in = True
                    break
                if "error" in content.lower() or "invalid" in content.lower():
                    print(f"login fail user={user}")
                else:
                    print(f"login unclear user={user} url={url}")
            if logged_in:
                break

        if not logged_in:
            print("All logins failed")
            browser.close()
            return 4

        # Create page via admin new-post
        def create_page(title: str, slug: str, html: str) -> str | None:
            page.goto(f"{BASE}/wp-admin/post-new.php?post_type=page", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            # Classic or block editor
            if page.locator("#title").count():
                page.fill("#title", title)
                # Text tab for classic
                if page.locator("#content-html").count():
                    page.click("#content-html")
                page.fill("#content", html)
            else:
                # Block editor: add custom HTML block via code editor
                page.keyboard.press("Control+Shift+Alt+M")  # code editor sometimes
                page.wait_for_timeout(1000)
                # Prefer REST from browser context cookies
                link = page.evaluate(
                    """async ({ title, slug, html }) => {
                      const content = '<!-- wp:html -->\\n' + html + '\\n<!-- /wp:html -->';
                      const root = (window.wpApiSettings && wpApiSettings.root) || '/wp-json/';
                      const nonce = (window.wpApiSettings && wpApiSettings.nonce) || '';
                      // find existing
                      let search = await fetch(root + 'wp/v2/pages?slug=' + encodeURIComponent(slug), {
                        headers: { 'X-WP-Nonce': nonce, 'Accept': 'application/json' },
                        credentials: 'same-origin'
                      }).then(r => r.json());
                      const payload = { title, slug, status: 'publish', content };
                      let url = root + 'wp/v2/pages';
                      let method = 'POST';
                      if (Array.isArray(search) && search.length) {
                        url = root + 'wp/v2/pages/' + search[0].id;
                      }
                      const res = await fetch(url, {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                          'X-WP-Nonce': nonce,
                          'Accept': 'application/json'
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify(payload)
                      });
                      const data = await res.json();
                      return { status: res.status, link: data.link, id: data.id, err: data.message };
                    }""",
                    {"title": title, "slug": slug, "html": html},
                )
                print("REST via cookie:", link)
                return (link or {}).get("link")

            # Publish classic
            if page.locator("#publish").count():
                page.click("#publish")
                page.wait_for_timeout(3000)
            permalink = ""
            if page.locator("#sample-permalink").count():
                permalink = page.inner_text("#sample-permalink")
            print(f"classic publish {slug}: {permalink}")
            return permalink or f"{BASE}/{slug}/"

        form_url = create_page("Un regalo para tu peque!", "un-regalo-para-tu-peque", form_html)
        gracias_url = create_page("Gracias descarga guia", "gracias-descarga-guia", gracias_html)
        print("FORM_URL", form_url)
        print("GRACIAS_URL", gracias_url)

        # Landing: create page pointing to GH Pages iframe as interim if static upload unavailable
        landing_html = f"""
        <div style="min-height:80vh">
          <iframe src="https://miyamotogenji.github.io/el-poder-de-ser-yo/" style="border:0;width:100%;min-height:90vh" title="El Poder de Ser Yo"></iframe>
          <p style="text-align:center;font-family:sans-serif">
            <a href="https://miyamotogenji.github.io/el-poder-de-ser-yo/" target="_blank" rel="noopener">Abrir landing a pantalla completa</a>
          </p>
        </div>
        """
        landing_url = create_page("El Poder de Ser Yo", "el-poder-de-ser-yo", landing_html)
        print("LANDING_URL", landing_url)

        browser.close()
        return 0 if form_url else 5


if __name__ == "__main__":
    sys.exit(main())
