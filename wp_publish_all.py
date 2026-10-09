"""Publish P2/P3 to todosabordocr.com via WordPress REST API."""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://todosabordocr.com"
ROOT = Path(__file__).resolve().parent / "wordpress-publish"

USERS = ["admin", "gustavo", "todosabordocr", "Gustavo", "hola", "carmen"]
PASSWORDS = ["Carmen160384..", "@w@xQcxN$v3STlcn", "Carmen160384"]


def req(method: str, path: str, user: str, password: str, body: dict | None = None) -> tuple[int, str]:
    url = BASE + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "User-Agent": "Mozilla/5.0 TodosABordoPublisher/1.0",
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def find_auth() -> tuple[str, str] | None:
    for user in USERS:
        for password in PASSWORDS:
            code, body = req("GET", "/wp-json/wp/v2/users/me", user, password)
            if code == 200 and '"id"' in body and "Unauthorized Access" not in body:
                print(f"AUTH OK user={user}")
                return user, password
            if "firewall" in body.lower() or "Unauthorized Access" in body:
                print("BLOCKED by Banahosting firewall — unblock IP first.")
                return None
    return None


def wp_html_block(html: str) -> str:
    return f"<!-- wp:html -->\n{html}\n<!-- /wp:html -->"


def upsert_page(user: str, password: str, slug: str, title: str, content: str) -> dict | None:
    code, body = req("GET", f"/wp-json/wp/v2/pages?slug={slug}&_fields=id,link", user, password)
    if code != 200:
        print(f"search {slug} failed {code}: {body[:200]}")
        return None
    existing = json.loads(body)
    payload = {"title": title, "slug": slug, "status": "publish", "content": content}
    if existing:
        page_id = existing[0]["id"]
        code, body = req("POST", f"/wp-json/wp/v2/pages/{page_id}", user, password, payload)
    else:
        code, body = req("POST", "/wp-json/wp/v2/pages", user, password, payload)
    if code not in (200, 201):
        print(f"upsert {slug} failed {code}: {body[:400]}")
        return None
    return json.loads(body)


def patch_recursos_download(user: str, password: str, form_url: str) -> bool:
    code, body = req("GET", "/wp-json/wp/v2/pages?slug=recursos-gratis&context=edit", user, password)
    if code != 200:
        print(f"recursos-gratis fetch failed {code}")
        return False
    pages = json.loads(body)
    if not pages:
        return False
    page = pages[0]
    raw = page.get("content", {}).get("raw") or page.get("content", {}).get("rendered") or ""
    if form_url in raw:
        print("recursos-gratis already links to form")
        return True
    # Best-effort: append note if Elementor raw is opaque
    print("NOTE: recursos-gratis is Elementor — update Potenciá DESCARGAR link in Elementor to:", form_url)
    return False


def main() -> int:
    auth = find_auth()
    if not auth:
        print("No WordPress credentials / firewall still blocking.")
        return 1
    user, password = auth

    p2_html = (ROOT / "un-regalo-para-tu-peque" / "index.html").read_text(encoding="utf-8")
    p2_gracias = (ROOT / "un-regalo-para-tu-peque" / "gracias.html").read_text(encoding="utf-8")
    p3_html = (ROOT / "el-poder-de-ser-yo" / "index.html").read_text(encoding="utf-8")

    # Point thanks URL at domain once published
    p2_html = p2_html.replace(
        "https://miyamotogenji.github.io/regalo-para-tu-peque/gracias.html",
        f"{BASE}/gracias-descarga-guia/",
    )
    widget = (ROOT / "elementor-html-widget.html").read_text(encoding="utf-8")
    widget = widget.replace(
        'data-thanks="https://miyamotogenji.github.io/regalo-para-tu-peque/gracias.html"',
        f'data-thanks="{BASE}/gracias-descarga-guia/"',
    ).replace(
        "https://miyamotogenji.github.io/regalo-para-tu-peque/portada-formulario.png",
        f"{BASE}/wp-content/uploads/portada-formulario.png",
    )

    r1 = upsert_page(user, password, "un-regalo-para-tu-peque", "Un regalo para tu peque!", wp_html_block(p2_html))
    r2 = upsert_page(user, password, "gracias-descarga-guia", "Gracias - Descarga guia", wp_html_block(p2_gracias))
    r3 = upsert_page(user, password, "el-poder-de-ser-yo", "El Poder de Ser Yo", wp_html_block(p3_html))

    form_url = r1.get("link") if r1 else f"{BASE}/un-regalo-para-tu-peque/"
    patch_recursos_download(user, password, form_url)

    print("\n=== RESULTS ===")
    if r1:
        print("Form public:", r1.get("link"))
        print("Form edit:", f"{BASE}/wp-admin/post.php?post={r1['id']}&action=elementor")
    if r2:
        print("Gracias:", r2.get("link"))
    if r3:
        print("Landing P3:", r3.get("link"))
    return 0 if r1 and r3 else 1


if __name__ == "__main__":
    sys.exit(main())
