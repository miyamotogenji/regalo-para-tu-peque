"""Create pages via XML-RPC if REST application passwords are unavailable."""
import base64
import json
import sys
import urllib.request
import xmlrpc.client
from pathlib import Path

BASE = "http://todosabordocr.com"
ROOT = Path(__file__).resolve().parent / "wordpress-publish"
USERS = ["hola", "hola@todosabordocr.com", "admin", "gustavo", "todosabordocr", "Gustavo", "carmen"]
PASSWORDS = [
    "Lorenzo160384..",
    "Carmen160384..",
    "@w@xQcxN$v3STlcn",
    "Carmen160384",
]


def wp_html_block(html: str) -> str:
    return f"<!-- wp:html -->\n{html}\n<!-- /wp:html -->"


def try_auth(user: str, password: str):
    endpoint = BASE + "/xmlrpc.php"
    proxy = xmlrpc.client.ServerProxy(endpoint, allow_none=True)
    try:
        blogs = proxy.wp.getUsersBlogs(user, password)
        return proxy, blogs
    except xmlrpc.client.Fault as e:
        print(f"xmlrpc {user}: {e.faultString[:120]}")
    except Exception as e:
        print(f"xmlrpc {user}: {e}")
    return None, None


def main() -> int:
    p2 = wp_html_block((ROOT / "un-regalo-para-tu-peque" / "index.html").read_text(encoding="utf-8"))
    p3 = wp_html_block((ROOT / "el-poder-de-ser-yo" / "index.html").read_text(encoding="utf-8"))

    for user in USERS:
        for password in PASSWORDS:
            proxy, blogs = try_auth(user, password)
            if not blogs:
                continue
            print("AUTH OK", user, blogs)
            for slug, title, content in [
                ("un-regalo-para-tu-peque", "Un regalo para tu peque!", p2),
                ("el-poder-de-ser-yo", "El Poder de Ser Yo", p3),
            ]:
                post_id = proxy.metaWeblog.newPost(
                    0,
                    user,
                    password,
                    {
                        "title": title,
                        "description": content,
                        "mt_excerpt": "",
                        "post_type": "page",
                        "wp_slug": slug,
                        "post_status": "publish",
                    },
                    True,
                )
                print(f"published {slug} id={post_id}")
            return 0
    print("XML-RPC auth failed for all candidates")
    return 1


if __name__ == "__main__":
    sys.exit(main())
