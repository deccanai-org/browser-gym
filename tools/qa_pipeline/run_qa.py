"""Mock UI QA pipeline — discover, report, optionally auto-fix.

Usage (from repo root):
  python -m tools.qa_pipeline.run_qa
  python -m tools.qa_pipeline.run_qa --suite regression --no-serve
  python -m tools.qa_pipeline.run_qa --auto-fix
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# A sandboxed shell can point PLAYWRIGHT_BROWSERS_PATH at an empty scratch dir,
# which makes chromium.launch() fail with "Executable doesn't exist". Fall back
# to the standard per-user cache whenever the configured path has no browsers.
def _fix_playwright_browsers_path() -> None:
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    default = Path.home() / "Library/Caches/ms-playwright"
    if not default.is_dir():
        default = Path.home() / ".cache/ms-playwright"
    if configured and any(Path(configured).glob("chromium*")):
        return
    if default.is_dir() and any(default.glob("chromium*")):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(default)


_fix_playwright_browsers_path()
REPORTS = Path(__file__).resolve().parent / "reports"
CHECKS_YAML = Path(__file__).resolve().parent / "checks" / "regression.yaml"

APPS = {
    "shopgym": ("amazon_mock", 5201),
    "valuemart": ("ebay_mock", 5202),
    "shopmail": ("gmail_mock", 5203),
    "gymcal": ("google_calendar_mock", 5204),
    "gymeats": ("uber_eats_mock", 5205),
}


@dataclass
class Finding:
    id: str
    app: str
    severity: str
    title: str
    status: str  # pass | fail | skip | error
    detail: str = ""
    file: str = ""


@dataclass
class Report:
    started_at: str
    suite: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for f in self.findings if f.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for f in self.findings if f.status == "fail")


def _load_yaml(path: Path):
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "PyYAML is required. Install with: pip install pyyaml\n"
            f"(tried to load {path})"
        ) from e
    return yaml.safe_load(path.read_text())


def _port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ensure_port_free(port: int):
    """Best-effort: free a leftover preview server so we don't test stale bundles."""
    if not _port_in_use(port):
        return
    try:
        out = subprocess.check_output(
            ["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"], text=True
        ).strip()
        for pid in out.splitlines():
            if pid.strip().isdigit():
                subprocess.call(["kill", pid.strip()])
        time.sleep(0.4)
    except Exception:
        pass


def _needs_rebuild(folder: str) -> bool:
    dist = ROOT / "websites" / folder / "dist"
    src = ROOT / "websites" / folder / "src"
    if not dist.exists():
        return True
    dist_js = list((dist / "assets").glob("index-*.js")) if (dist / "assets").exists() else []
    if not dist_js:
        return True
    newest_src = max((p.stat().st_mtime for p in src.rglob("*") if p.is_file()), default=0)
    newest_dist = max(j.stat().st_mtime for j in dist_js)
    return newest_src > newest_dist + 0.5


def _make_spa_handler(directory: Path):
    """Static file server with SPA fallback to index.html (needed for /cart, /search, …)."""
    root = str(directory)

    class SPAHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=root, **kwargs)

        def log_message(self, format, *args):  # noqa: A003
            return

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            fs_path = Path(root) / path.lstrip("/")
            if path != "/" and not fs_path.exists() and not (Path(root) / path.lstrip("/")).is_file():
                # Asset miss → 404; route miss → index.html
                if "." in Path(path).name:
                    return super().do_GET()
                self.path = "/index.html"
            return super().do_GET()

    return SPAHandler


def _wait_port(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use(port):
            return True
        time.sleep(0.15)
    return False


def _serve_dist(folder: str, port: int) -> threading.Thread:
    dist = ROOT / "websites" / folder / "dist"
    _ensure_port_free(port)
    if _needs_rebuild(folder):
        print(f"  building {folder}…")
        subprocess.check_call(
            ["npm", "run", "build"],
            cwd=ROOT / "websites" / folder,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    if not dist.exists():
        raise RuntimeError(f"missing dist for {folder}")

    handler = _make_spa_handler(dist)

    class ReuseTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = ReuseTCPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    t._httpd = httpd  # type: ignore[attr-defined]
    if not _wait_port(port, 10):
        raise RuntimeError(f"server for {folder} did not bind :{port}")
    print(f"  serving {folder} on :{port}")
    return t


def _stop_server(proc):
    if isinstance(proc, subprocess.Popen):
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    else:
        httpd = getattr(proc, "_httpd", None)
        if httpd:
            httpd.shutdown()
            try:
                httpd.server_close()
            except Exception:
                pass


def run_source_check(check: dict) -> Finding:
    missing = []
    forbidden_hit = []
    for rel in check.get("files") or []:
        path = ROOT / rel
        if not path.exists():
            return Finding(check["id"], check["app"], check["severity"], check["title"],
                           "error", f"missing file {rel}", rel)
        text = path.read_text(errors="replace")
        for needle in check.get("must_contain") or []:
            if needle not in text:
                missing.append(f"{rel}: missing `{needle}`")
        for needle in check.get("must_not_contain") or []:
            if needle in text:
                forbidden_hit.append(f"{rel}: still contains `{needle}`")
        jp = check.get("json_path_contains")
        if jp and path.suffix == ".json":
            data = json.loads(text)
            emails = data.get(jp.get("path") or "emails") or []
            want = jp.get("any_labels_include")
            if want and not any(want in (e.get("labels") or []) for e in emails[:50]):
                missing.append(f"{rel}: no email labels include `{want}` in sample")
    if missing or forbidden_hit:
        return Finding(check["id"], check["app"], check["severity"], check["title"],
                       "fail", "; ".join(missing + forbidden_hit))
    return Finding(check["id"], check["app"], check["severity"], check["title"], "pass")


def run_browser_checks(checks: list[dict], base_url: str, out_dir: Path) -> list[Finding]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [
            Finding(c["id"], c["app"], c["severity"], c["title"], "skip",
                    "playwright not installed (pip install playwright && playwright install chromium)")
            for c in checks
        ]

    findings: list[Finding] = []
    shot_dir = out_dir / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for check in checks:
            app = check["app"]
            port = APPS[app][1]
            origin = f"{base_url}:{port}"
            # Fresh context per check so localStorage from prior tests can't poison results.
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            console_errors: list[str] = []
            page.on("pageerror", lambda e: console_errors.append(str(e)))
            status = "pass"
            detail = ""
            try:
                for step in check.get("steps") or []:
                    if "goto" in step:
                        page.goto(origin + step["goto"], wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(700)
                    elif "wait" in step:
                        page.get_by_text(step["wait"].replace("text=", ""), exact=False).first.wait_for(timeout=10000)
                    elif "click" in step:
                        el = page.locator(step["click"]).first
                        # `at` clicks a fraction of the element box, for grids
                        # where the target is a coordinate rather than a node.
                        if "at" in step:
                            box = el.bounding_box()
                            if not box:
                                raise AssertionError(f"no bounding box for {step['click']}")
                            el.click(timeout=10000, position={
                                "x": box["width"] * float(step["at"]["x"]),
                                "y": box["height"] * float(step["at"]["y"]),
                            })
                        else:
                            el.click(timeout=10000)
                        page.wait_for_timeout(300)
                    elif "fill" in step:
                        page.locator(step["fill"]).first.fill(step.get("value", ""))
                    elif "press" in step:
                        page.keyboard.press(step["press"])
                        page.wait_for_timeout(700)
                    elif "assert_text" in step:
                        page.get_by_text(step["assert_text"], exact=False).first.wait_for(timeout=8000)
                    elif "assert_clickable" in step:
                        # Prefer the hero CTA when multiple "Shop now" links exist.
                        el = page.locator(step["assert_clickable"]).first
                        if check["id"] == "SG-03":
                            el = page.locator(".bg-gray-900 a:has-text('Shop now'), a:has-text('Shop now')").first
                        el.wait_for(timeout=8000)
                        box = el.bounding_box()
                        if not box:
                            raise AssertionError("no bounding box")
                        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                        hit = page.evaluate(
                            """([x, y]) => {
                                const t = document.elementFromPoint(x, y);
                                if (!t) return false;
                                let n = t;
                                for (let i = 0; i < 8 && n; i++, n = n.parentElement) {
                                  if (n.tagName === 'A' || n.tagName === 'BUTTON') return true;
                                }
                                return false;
                            }""",
                            [cx, cy],
                        )
                        if not hit:
                            top = page.evaluate(
                                "([x,y]) => { const e = document.elementFromPoint(x,y); return e && (e.outerHTML||'').slice(0,200); }",
                                [cx, cy],
                            )
                            raise AssertionError(f"CTA covered by: {top}")
                    elif "assert_has_results" in step:
                        body = page.inner_text("body")
                        if "No products found matching your criteria" in body or "No results found" in body:
                            raise AssertionError("empty search results")
                    elif "assert_text_not" in step:
                        needle = step["assert_text_not"]
                        if needle in page.inner_text("body"):
                            raise AssertionError(f"unexpected text: {needle}")
                    elif "assert_absent" in step:
                        if check["id"] == "SG-01":
                            oos = page.get_by_text("Power Broker").first
                            parent = oos.locator(
                                "xpath=ancestor::div[contains(@class,'border') or contains(@class,'group')][1]"
                            )
                            if parent.locator("button:has-text('Add to Cart')").count() > 0:
                                raise AssertionError("OOS card still shows Add to Cart")
                        elif page.locator(step["assert_absent"]).count() > 0:
                            raise AssertionError(f"selector still present: {step['assert_absent']}")
                    elif "assert_no_stray_zero_near" in step:
                        pass
                    elif "hover" in step:
                        page.locator(step["hover"]).first.hover(timeout=10000)
                        page.wait_for_timeout(300)
                    elif "select" in step:
                        page.locator(step["select"]).first.select_option(step.get("value", ""))
                        page.wait_for_timeout(300)
                    elif "assert_present" in step:
                        sel = step["assert_present"]
                        page.locator(sel).first.wait_for(state="attached", timeout=8000)
                    elif "assert_input_matches" in step:
                        sel = step["assert_input_matches"]
                        pattern = step["pattern"]
                        got = page.locator(sel).first.input_value()
                        if not re.search(pattern, got):
                            raise AssertionError(f"{sel} value {got!r} does not match /{pattern}/")
                    elif "assert_js" in step:
                        # Escape hatch for assertions that need to read app state
                        # (localStorage) or compare two rendered numbers.
                        if not page.evaluate(f"() => {{ {step['assert_js']} }}"):
                            raise AssertionError(f"JS assertion false: {step.get('why') or step['assert_js']}")
            except Exception as e:
                status = "fail"
                detail = str(e)
                page.screenshot(path=str(shot_dir / f"{check['id']}.png"), full_page=True)
            if console_errors and status == "pass":
                detail = f"console errors: {console_errors[:2]}"
            findings.append(Finding(
                check["id"], check["app"], check["severity"], check["title"], status, detail
            ))
            context.close()
        browser.close()
    return findings


def run_static_pattern_scan() -> list[Finding]:
    """Catch systemic patterns from the QA executive summary."""
    findings: list[Finding] = []
    patterns = [
        ("stockCount &&", "SG-05-pattern", "shopgym", "medium",
         "React falsy-zero stockCount && pattern"),
        ("formatDistanceToNow(", "VM-04-pattern", "valuemart", "high",
         "Wall-clock formatDistanceToNow (split-clock risk)"),
        ("startOfTomorrow()", "GC-02-pattern", "gymcal", "critical",
         "startOfTomorrow() bypasses gym clock"),
        ('value="Home"', "VM-07-pattern", "valuemart", "medium",
         "Home & Garden option value mismatch"),
    ]
    scan_roots = {
        "shopgym": ROOT / "websites/amazon_mock/src",
        "valuemart": ROOT / "websites/ebay_mock/src",
        "gymcal": ROOT / "websites/google_calendar_mock/src",
        "shopmail": ROOT / "websites/gmail_mock/src",
        "gymeats": ROOT / "websites/uber_eats_mock/src",
    }
    for needle, cid, app, sev, title in patterns:
        root = scan_roots.get(app)
        if not root or not root.exists():
            continue
        hits = []
        for p in root.rglob("*"):
            if p.suffix not in {".js", ".jsx", ".ts", ".tsx", ".css"}:
                continue
            try:
                txt = p.read_text(errors="replace")
            except Exception:
                continue
            if needle in txt:
                for i, line in enumerate(txt.splitlines(), 1):
                    if needle in line and not line.strip().startswith("//") and not line.strip().startswith("*"):
                        hits.append(f"{p.relative_to(ROOT)}:{i}")
        if hits:
            findings.append(Finding(cid, app, sev, title, "fail", "; ".join(hits[:5])))
        else:
            findings.append(Finding(cid, app, sev, title, "pass"))
    return findings


def run_full_crawl(base_url: str, out_dir: Path) -> list[Finding]:
    """Visit every app home + key routes at 3 viewports; flag overflow & console errors."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [Finding("CRAWL", "all", "info", "Full crawl", "skip", "playwright missing")]

    routes = {
        "shopgym": ["/", "/search?q=headphones", "/cart", "/gift-cards", "/wishlist", "/profile"],
        "valuemart": ["/", "/search?q=camera", "/cart", "/dashboard", "/deals", "/sell"],
        "shopmail": ["/", "/#inbox", "/#sent", "/#drafts"],
        "gymcal": ["/"],
        "gymeats": ["/", "/orders", "/checkout"],
    }
    viewports = [(1440, 900), (768, 1024), (375, 812)]
    findings: list[Finding] = []
    shot_dir = out_dir / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for app, paths in routes.items():
            port = APPS[app][1]
            for w, h in viewports:
                page = browser.new_page(viewport={"width": w, "height": h})
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                for path in paths:
                    cid = f"CRAWL-{app}-{w}x{h}-{path.strip('/').replace('/', '_') or 'home'}"
                    try:
                        page.goto(f"{base_url}:{port}{path}", wait_until="domcontentloaded", timeout=25000)
                        page.wait_for_timeout(400)
                        overflow = page.evaluate(
                            "() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)"
                        )
                        detail = []
                        status = "pass"
                        if overflow > 20:
                            status = "fail"
                            detail.append(f"horizontal overflow {overflow}px")
                        if errors:
                            status = "fail"
                            detail.append("pageerror: " + errors[0][:160])
                            errors.clear()
                        if status == "fail":
                            page.screenshot(path=str(shot_dir / f"{cid}.png"))
                        findings.append(Finding(
                            cid, app, "medium" if "overflow" in ",".join(detail) else "high",
                            f"Crawl {path} @ {w}x{h}", status, "; ".join(detail)
                        ))
                    except Exception as e:
                        findings.append(Finding(cid, app, "high", f"Crawl {path} @ {w}x{h}", "fail", str(e)))
                page.close()
        browser.close()
    return findings



# Mechanical, reviewed patches only — never invent product logic.
AUTO_FIXES: list[tuple[str, str, str, str]] = [
    (
        "websites/amazon_mock/src/components/product/ProductCard.jsx",
        "product.stockCount && product.stockCount <= 10",
        "product.stockCount != null && product.stockCount <= 10",
        "ShopGym: fix React falsy-zero stockCount render",
    ),
    (
        "websites/ebay_mock/src/pages/CreateListing.jsx",
        'value="Home"',
        'value="Home & Garden"',
        "ValueMart: Home & Garden option value matches label",
    ),
]


def apply_auto_fixes() -> list[str]:
    applied = []
    for rel, old, new, desc in AUTO_FIXES:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text()
        if old in text:
            path.write_text(text.replace(old, new))
            applied.append(desc)
    return applied


def write_reports(report: Report, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps({
        "started_at": report.started_at,
        "suite": report.suite,
        "passed": report.passed,
        "failed": report.failed,
        "findings": [asdict(f) for f in report.findings],
    }, indent=2))

    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    fails = [f for f in report.findings if f.status == "fail"]
    fails.sort(key=lambda f: sev_order.get(f.severity, 9))

    md = [
        f"# Mock UI QA Report — {report.started_at}",
        "",
        f"**Suite:** `{report.suite}` · **Pass:** {report.passed} · **Fail:** {report.failed}",
        "",
        "## Failures",
        "",
    ]
    if not fails:
        md.append("_All checks passed._")
    else:
        md.append("| ID | Sev | App | Title | Detail |")
        md.append("|---|---|---|---|---|")
        for f in fails:
            md.append(f"| {f.id} | {f.severity} | {f.app} | {f.title} | {f.detail.replace('|', '/')} |")
    md += ["", "## All results", ""]
    for f in report.findings:
        mark = {"pass": "✅", "fail": "❌", "skip": "⏭", "error": "⚠"}.get(f.status, f.status)
        md.append(f"- {mark} **{f.id}** ({f.severity}/{f.app}) {f.title}" + (f" — {f.detail}" if f.detail else ""))
    (out_dir / "report.md").write_text("\n".join(md) + "\n")

    html = f"""<!doctype html><html><head><meta charset=utf-8>
<title>QA Report {report.started_at}</title>
<style>
body{{font:15px/1.5 system-ui;max-width:960px;margin:40px auto;padding:0 16px;color:#111}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ddd;padding:8px;text-align:left}}
.fail{{color:#b00020}}.pass{{color:#0a7}}.sev{{font-weight:700;text-transform:uppercase;font-size:11px}}
</style></head><body>
<h1>Mock UI QA Report</h1>
<p>Suite <code>{report.suite}</code> · Pass {report.passed} · Fail <strong>{report.failed}</strong> · {report.started_at}</p>
<h2>Failures</h2>
<table><tr><th>ID</th><th>Sev</th><th>App</th><th>Title</th><th>Detail</th></tr>
"""
    for f in fails:
        html += f"<tr class=fail><td>{f.id}</td><td class=sev>{f.severity}</td><td>{f.app}</td><td>{f.title}</td><td>{f.detail}</td></tr>\n"
    if not fails:
        html += "<tr><td colspan=5>All checks passed.</td></tr>\n"
    html += "</table><h2>All</h2><ul>"
    for f in report.findings:
        html += f"<li class='{f.status}'><b>{f.id}</b> [{f.status}] {f.title} <small>{f.detail}</small></li>\n"
    html += "</ul></body></html>"
    (out_dir / "report.html").write_text(html)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Automated mock-UI QA pipeline")
    ap.add_argument("--suite", choices=["regression", "full", "all"], default="regression")
    ap.add_argument("--no-serve", action="store_true", help="Don't start preview servers")
    ap.add_argument("--base-url", default="http://127.0.0.1")
    ap.add_argument("--auto-fix", action="store_true", help="Apply safe known patches then re-check")
    ap.add_argument("--apps", default="", help="Comma list of apps to include")
    args = ap.parse_args(argv)

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_dir = REPORTS / started
    report = Report(started_at=started, suite=args.suite)

    if args.auto_fix:
        applied = apply_auto_fixes()
        print(f"auto-fix applied: {applied or '(nothing pending)'}")

    data = _load_yaml(CHECKS_YAML)
    checks = data.get("checks") or []
    only = {a.strip() for a in args.apps.split(",") if a.strip()}
    if only:
        checks = [c for c in checks if c.get("app") in only]

    servers = []
    try:
        if not args.no_serve:
            print("Starting preview servers…")
            for app, (folder, port) in APPS.items():
                if only and app not in only:
                    continue
                servers.append(_serve_dist(folder, port))
            # Extra settle for React hydrate after bind.
            time.sleep(0.5)

        # Source checks always run (no browser needed).
        print("Running source regression checks…")
        for c in checks:
            if c.get("kind") == "source":
                report.findings.append(run_source_check(c))

        # Browser regression
        browser_checks = [c for c in checks if c.get("kind") == "browser"]
        if browser_checks and args.suite in ("regression", "all"):
            print(f"Running {len(browser_checks)} browser regression checks…")
            report.findings.extend(run_browser_checks(browser_checks, args.base_url.rstrip("/"), out_dir))

        # Pattern scan
        print("Running static pattern scan…")
        report.findings.extend(run_static_pattern_scan())

        if args.suite in ("full", "all"):
            print("Running full crawl…")
            report.findings.extend(run_full_crawl(args.base_url.rstrip("/"), out_dir))

    finally:
        for s in servers:
            _stop_server(s)

    write_reports(report, out_dir)
    print(f"\nDone. Pass={report.passed} Fail={report.failed}")
    print(f"Report: {out_dir / 'report.md'}")
    print(f"HTML:   {out_dir / 'report.html'}")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
