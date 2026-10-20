"""Build deploy/: a small copy of the UI with only the stores inside DEPLOY_BBOX.

Reads the full UI build in ui/ (run `python -m src.build_ui` first), so no spaCy re-run.
Stores are re-numbered 0..n-1 because the page looks stores up by position.

Run from the project root:  python -m src.deploy
"""
import json
import re
import shutil

import config


def _read_js(path, prefix):
    text = path.read_text(encoding="utf-8")
    return json.loads(text.split(prefix, 1)[1].split(";\n")[0].rstrip(";"))


def build_deploy(verbose=True):
    src_data = config.UI_DIR / "data"
    meta = _read_js(src_data / "stores.js", "window.META=")
    stores = _read_js(src_data / "stores.js", "window.STORES=")

    (lat_lo, lat_hi), (lon_lo, lon_hi) = config.DEPLOY_BBOX["lat"], config.DEPLOY_BBOX["lon"]
    keep = [s for s in stores if lat_lo <= s["la"] <= lat_hi and lon_lo <= s["lo"] <= lon_hi]
    if not keep:
        raise SystemExit("no stores inside DEPLOY_BBOX")

    if config.DEPLOY_DIR.exists():
        shutil.rmtree(config.DEPLOY_DIR)  # generated folder; rebuilt from scratch every run
    out_data = config.DEPLOY_DIR / "data"
    (out_data / "s").mkdir(parents=True)
    shutil.copy(config.UI_DIR / "index.html", config.DEPLOY_DIR / "index.html")

    for new_i, s in enumerate(keep):
        detail = (src_data / "s" / f"{s['i']}.js").read_text(encoding="utf-8")
        detail = re.sub(r"^window\.__store\(\d+,", f"window.__store({new_i},", detail)
        (out_data / "s" / f"{new_i}.js").write_text(detail, encoding="utf-8")
        s["i"] = new_i

    meta["scope"] = config.DEPLOY_SCOPE
    dump = lambda o: json.dumps(o, ensure_ascii=True, separators=(",", ":"))
    (out_data / "stores.js").write_text(f"window.META={dump(meta)};\nwindow.STORES={dump(keep)};", encoding="utf-8")

    if verbose:
        size_mb = sum(f.stat().st_size for f in config.DEPLOY_DIR.rglob("*") if f.is_file()) / 1e6
        print("=== deploy: sanity summary ===")
        print(f"scope                   : {config.DEPLOY_SCOPE}  (box lat {lat_lo}-{lat_hi}, lon {lon_lo}-{lon_hi})")
        print(f"stores                  : {len(keep)} of {len(stores)}")
        print(f"written                 : {config.DEPLOY_DIR}  ({size_mb:.2f} MB)")


if __name__ == "__main__":
    build_deploy()
