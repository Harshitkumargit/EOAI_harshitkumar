"""Optional browser smoke check using an already installed Chrome/Edge; installs nothing.

Usage: py -3.10 scripts/check_dashboard.py path/to/dashboard.html
Produces a checked copy and screenshots beside the source in browser-check/.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

CHECK = r"""
<script>
(() => {
 const failures = [...(window.__qaErrors || [])];
 const cell = document.getElementById('cell');
 if (!cell || !cell.options.length) failures.push('No cell options');
 if (document.querySelectorAll('#map path').length !== cell.options.length) failures.push('Map/cell mismatch');
 if (document.querySelectorAll('#cards .card').length !== 4) failures.push('Summary cards missing');
 if (!document.getElementById('skill').textContent.includes('Skill')) failures.push('Metrics missing');
 if (cell && cell.options.length) {
   cell.value = cell.options[cell.options.length - 1].value;
   cell.dispatchEvent(new Event('change'));
   if (!document.getElementById('cell-detail').textContent.includes(cell.value)) failures.push('Selector did not update');
   document.querySelector('#map path').dispatchEvent(new MouseEvent('click'));
   if (cell.value !== cell.options[0].value) failures.push('Map click did not update');
 }
 if (document.documentElement.scrollWidth > window.innerWidth + 2) failures.push('Page overflows horizontally: '+document.documentElement.scrollWidth+'/'+window.innerWidth);
 document.documentElement.dataset.qaViewport = window.innerWidth+'x'+window.innerHeight;
 document.documentElement.dataset.qa = failures.length ? 'FAIL' : 'PASS';
 document.documentElement.dataset.qaDetail = failures.join('; ');
})();
</script>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--browser", type=Path)
    args = parser.parse_args()
    candidates = [args.browser] if args.browser else [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")]
    browser = next((p for p in candidates if p and p.is_file()), None)
    if browser is None:
        raise SystemExit("No existing Chromium browser found. Pass --browser; nothing was installed.")
    source = args.html.resolve()
    out = source.parent / "browser-check"
    workspace = Path(__file__).resolve().parents[1]
    if not out.resolve().is_relative_to(workspace):
        raise SystemExit("Browser checks and temporary profile cleanup are restricted to this project directory.")
    out.mkdir(exist_ok=True)
    html = source.read_text(encoding="utf-8")
    html = html.replace("<head>", "<head><script>window.__qaErrors=[];window.addEventListener('error',e=>window.__qaErrors.push(e.message));</script>")
    checked = out / "checked.html"
    checked.write_text(html.replace("</body>", CHECK + "</body>"), encoding="utf-8")
    # Windows Chrome enforces a minimum window width; 600 avoids clipped captures.
    for name, width, height in [("desktop", 1400, 3200), ("narrow", 600, 2400)]:
        with tempfile.TemporaryDirectory(prefix="browser-profile-", dir=out) as profile:
            command = [str(browser), "--headless", "--disable-gpu", "--force-device-scale-factor=1", "--no-first-run", "--no-default-browser-check",
                       "--disable-background-networking", "--disable-component-update", "--disable-sync", "--disable-extensions",
                       "--hide-scrollbars", "--allow-file-access-from-files", f"--user-data-dir={profile}",
                       f"--window-size={width},{height}", "--virtual-time-budget=2000", "--dump-dom",
                       f"--screenshot={out / (name + '.png')}", checked.as_uri()]
            result = subprocess.run(command, capture_output=True, timeout=60,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            dom = result.stdout.decode("utf-8", errors="replace")
            (out / (name + ".html")).write_text(dom, encoding="utf-8")
            passed = 'data-qa="PASS"' in dom and (out / (name + ".png")).is_file()
            print(f"{name}: {'PASS' if passed else 'FAIL'}; screenshot: {out / (name + '.png')}")
            if not passed:
                print(result.stderr.decode("utf-8", errors="replace")[-2000:])
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
