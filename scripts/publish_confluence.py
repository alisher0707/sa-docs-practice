#!/usr/bin/env python3
"""
Публикация документации из git в Confluence. Страницы-копии с номером версии в шапке.

  python3 scripts/publish_confluence.py --dry-run          # собрать страницы в public/confluence/, ничего не отправлять
  python3 scripts/publish_confluence.py                    # опубликовать

Что публикуется (дерево страниц):
  <CONFLUENCE_ROOT_TITLE>                       — корневая страница с реестром методов
    └─ <system>                                 — README системы
         └─ API-NNN <title>                     — карточка метода

Шапка каждой страницы: тег версии, дата, коммит, ссылка на исходный файл в git
и предупреждение «сгенерировано автоматически, не редактировать вручную».
Страница обновляется, только если изменился её исходный файл (версия страницы в Confluence не «шумит»).

Настройки — переменные окружения (в CI — из секретов репозитория):
  CONFLUENCE_URL          Cloud: https://<site>.atlassian.net/wiki     Data Center: https://wiki.bank.local
  CONFLUENCE_DEPLOYMENT   cloud | dc
  CONFLUENCE_SPACE        ключ пространства, например SAP
  CONFLUENCE_USER         Cloud: email учётной записи (для dc не нужен)
  CONFLUENCE_TOKEN        Cloud: API-токен Atlassian · Data Center: персональный токен (PAT)
  CONFLUENCE_ROOT_TITLE   заголовок корневой страницы (по умолчанию «Документация систем (из git)»)
  REPO_URL                адрес репозитория для ссылок (в GitHub Actions берётся автоматически)
Зависимости: pyyaml, markdown.
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import markdown
import yaml

ROOT = Path(__file__).resolve().parent.parent
MARK = "sa-docs-source"   # метка-хэш исходника в теле страницы


# ---------- сборка содержимого ----------

def git(*args, default=""):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else default


def split_front_matter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]


def md_to_storage(md_text, src_path, repo_url, ref):
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"], output_format="xhtml")

    def fix_link(m):
        href = m.group(1)
        if re.match(r"^(https?:|mailto:|#)", href):
            return m.group(0)
        target = (ROOT / src_path).parent.joinpath(href).resolve()
        try:
            rel = target.relative_to(ROOT).as_posix()
        except ValueError:
            return m.group(0)
        return f'href="{html.escape(repo_url)}/blob/{ref}/{rel}"'

    return re.sub(r'href="([^"]+)"', fix_link, body)


def header(meta_lines, src_path, repo_url, ref, digest):
    link = f'{html.escape(repo_url)}/blob/{ref}/{src_path}'
    hist = f'{html.escape(repo_url)}/commits/{ref}/{src_path}'
    rows = "".join(f"<p>{line}</p>" for line in meta_lines)
    return (
        '<ac:structured-macro ac:name="info"><ac:rich-text-body>'
        f"{rows}"
        f'<p>Источник: <a href="{link}">{html.escape(src_path)}</a> · '
        f'<a href="{hist}">история изменений и согласований</a></p>'
        "<p><strong>Сгенерировано автоматически из git. Не редактируйте вручную</strong> — "
        "изменения вносятся только через Pull Request.</p>"
        f"<p><sub>{MARK}:{digest}</sub></p>"
        "</ac:rich-text-body></ac:structured-macro>"
    )


def build_pages(ref, repo_url):
    today = date.today().strftime("%d.%m.%Y")
    commit = git("rev-parse", "--short", "HEAD", default="local")
    meta = [f"<strong>Версия {html.escape(ref)}</strong> · {today} · коммит {commit}"]
    root_title = os.environ.get("CONFLUENCE_ROOT_TITLE", "Документация систем (из git)")
    pages = []

    def add(title, parent, src_path, md_text, extra_meta=()):
        digest = hashlib.sha256(md_text.encode()).hexdigest()[:16]
        body = header(meta + list(extra_meta), src_path, repo_url, ref, digest) + md_to_storage(md_text, src_path, repo_url, ref)
        pages.append({"title": title, "parent": parent, "body": body, "digest": digest})

    reg = ROOT / "registry" / "METHODS.md"
    add(root_title, None, "registry/METHODS.md", reg.read_text(encoding="utf-8") if reg.exists() else "Реестр пуст")

    for sysdir in sorted(p for p in (ROOT / "systems").iterdir() if p.is_dir()):
        readme = sysdir / "README.md"
        sys_title = sysdir.name
        add(sys_title, root_title, readme.relative_to(ROOT).as_posix(),
            readme.read_text(encoding="utf-8") if readme.exists() else f"# {sys_title}")
        for card in sorted((sysdir / "methods").glob("*.md")):
            fm, body = split_front_matter(card.read_text(encoding="utf-8"))
            title = f"{fm.get('id', card.stem)} {fm.get('title', '')}".strip()
            extra = [f"Статус: <strong>{html.escape(str(fm.get('status', '—')))}</strong> · "
                     f"версия контракта {html.escape(str(fm.get('contract_version', '—')))} · "
                     f"владелец {html.escape(str(fm.get('owner', '—')))}"]
            add(title, sys_title, card.relative_to(ROOT).as_posix(), body, extra)
    return pages


# ---------- Confluence API ----------

class Confluence:
    def __init__(self, url, deployment, space, user, token):
        self.url, self.dep, self.space = url.rstrip("/"), deployment, space
        if deployment == "cloud":
            self.auth = "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()
        else:
            self.auth = "Bearer " + token

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.url + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": self.auth, "Accept": "application/json",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raise SystemExit(f"ERROR {method} {path}: HTTP {e.code} {e.read().decode(errors='replace')[:400]}")

    # Cloud — REST v2; Data Center — REST v1
    def space_info(self):
        if self.dep == "cloud":
            r = self.call("GET", f"/api/v2/spaces?keys={urllib.parse.quote(self.space)}")
            s = r["results"][0]
            return s["id"], s.get("homepageId")
        r = self.call("GET", f"/rest/api/space/{urllib.parse.quote(self.space)}?expand=homepage")
        return self.space, (r.get("homepage") or {}).get("id")

    def find(self, space_id, title):
        q = urllib.parse.quote(title)
        if self.dep == "cloud":
            r = self.call("GET", f"/api/v2/pages?space-id={space_id}&title={q}&body-format=storage&status=current")
            res = r.get("results", [])
            if not res:
                return None
            p = res[0]
            return {"id": p["id"], "version": p["version"]["number"], "body": p["body"]["storage"]["value"]}
        r = self.call("GET", f"/rest/api/content?spaceKey={urllib.parse.quote(self.space)}&title={q}&expand=body.storage,version")
        res = r.get("results", [])
        if not res:
            return None
        p = res[0]
        return {"id": p["id"], "version": p["version"]["number"], "body": p["body"]["storage"]["value"]}

    def create(self, space_id, title, parent_id, body):
        if self.dep == "cloud":
            data = {"spaceId": space_id, "status": "current", "title": title,
                    "body": {"representation": "storage", "value": body}}
            if parent_id:
                data["parentId"] = parent_id
            return self.call("POST", "/api/v2/pages", data)["id"]
        data = {"type": "page", "title": title, "space": {"key": self.space},
                "body": {"storage": {"value": body, "representation": "storage"}}}
        if parent_id:
            data["ancestors"] = [{"id": parent_id}]
        return self.call("POST", "/rest/api/content", data)["id"]

    def update(self, page_id, title, body, version, message):
        if self.dep == "cloud":
            self.call("PUT", f"/api/v2/pages/{page_id}", {
                "id": page_id, "status": "current", "title": title,
                "body": {"representation": "storage", "value": body},
                "version": {"number": version + 1, "message": message}})
        else:
            self.call("PUT", f"/rest/api/content/{page_id}", {
                "id": page_id, "type": "page", "title": title, "space": {"key": self.space},
                "body": {"storage": {"value": body, "representation": "storage"}},
                "version": {"number": version + 1, "message": message}})

    def label(self, page_id):
        try:
            self.call("POST", f"/rest/api/content/{page_id}/label",
                      [{"prefix": "global", "name": "autogen"}, {"prefix": "global", "name": "sa-docs"}])
        except SystemExit as e:
            print(f"WARN  метки не поставлены: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ref", default=os.environ.get("GITHUB_REF_NAME") or git("describe", "--tags", "--always", default="local"))
    a = ap.parse_args()

    repo_url = os.environ.get("REPO_URL") or (
        f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}" if os.environ.get("GITHUB_REPOSITORY")
        else "https://github.com/<owner>/<repo>")
    pages = build_pages(a.ref, repo_url)

    if a.dry_run:
        out = ROOT / "public" / "confluence"
        out.mkdir(parents=True, exist_ok=True)
        for i, p in enumerate(pages):
            (out / f"{i:02d}.html").write_text(f"<!-- {p['title']} (parent: {p['parent']}) -->\n{p['body']}", encoding="utf-8")
        print(f"OK    dry-run: {len(pages)} страниц собрано в {out.relative_to(ROOT)}")
        return 0

    need = ["CONFLUENCE_URL", "CONFLUENCE_DEPLOYMENT", "CONFLUENCE_SPACE", "CONFLUENCE_TOKEN"]
    missing = [k for k in need if not os.environ.get(k)]
    if os.environ.get("CONFLUENCE_DEPLOYMENT") == "cloud" and not os.environ.get("CONFLUENCE_USER"):
        missing.append("CONFLUENCE_USER")
    if missing:
        print(f"ERROR не заданы переменные: {', '.join(missing)}")
        return 1
    if os.environ["CONFLUENCE_DEPLOYMENT"] not in ("cloud", "dc"):
        print("ERROR CONFLUENCE_DEPLOYMENT должен быть cloud или dc")
        return 1

    c = Confluence(os.environ["CONFLUENCE_URL"], os.environ["CONFLUENCE_DEPLOYMENT"], os.environ["CONFLUENCE_SPACE"],
                   os.environ.get("CONFLUENCE_USER", ""), os.environ["CONFLUENCE_TOKEN"])
    space_id, home_id = c.space_info()
    ids = {}
    for p in pages:
        parent_id = ids.get(p["parent"]) if p["parent"] else home_id
        existing = c.find(space_id, p["title"])
        if existing is None:
            ids[p["title"]] = c.create(space_id, p["title"], parent_id, p["body"])
            c.label(ids[p["title"]])
            print(f"NEW   {p['title']}")
        elif f"{MARK}:{p['digest']}" in existing["body"]:
            ids[p["title"]] = existing["id"]
            print(f"SAME  {p['title']}")
        else:
            c.update(existing["id"], p["title"], p["body"], existing["version"], f"Автопубликация {a.ref}")
            ids[p["title"]] = existing["id"]
            print(f"UPD   {p['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
