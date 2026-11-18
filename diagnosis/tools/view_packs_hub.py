"""One web viewer for many pre/post pack pairs, with a pack sidebar.

Wraps view_pack_web.py (imported, not modified) in a single server:

  * Sidebar lists every pack pair found under the pre and post roots,
    with "changed / total" counts (computed in the background at startup).
  * Click a pack to open it; no need to restart the server per pack.
  * "Only changed" checkbox  = view_pack_web.py --changed-only
    "Random next" checkbox   = view_pack_web.py --random
    Press "Apply" to reload the current pack with the chosen options
    (options also apply to the next pack you click).
  * Each pack pair saves its notes to its own CSV in --labels-dir, and
    unsaved edits are kept per pack in the browser (localStorage), so
    switching packs does not lose work.

Pairing rule
    pre : <pre-root>/<pack>/Part_N/<file>.parquet
    post: <post-root>/<pack>/<file>.parquet
Packs whose name starts with any --exclude prefix are left out (default: none;
e.g. --exclude ind to hide the Indic packs).

Usage
    python view_packs_hub.py
    python view_packs_hub.py --pre-root ../../../Cap1-packs \\
        --post-root ../../../tokenizer_sample_v0_clean/train --port 8000

Then open http://127.0.0.1:8000.
"""
import argparse
import glob
import hashlib
import json
import os
import random
import secrets
import threading
from http.server import ThreadingHTTPServer

import pyarrow.parquet as pq

import view_pack_web as vpw

AUDIT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


class Hub:
    pairs = []            # list of dicts: key, pack, part, pre, post, out, changed, total
    by_key = {}
    current = None        # key of the loaded pair
    changed_only = True
    random_nav = True
    note = ""            # shown in the sidebar, e.g. when a 0-change pack falls back to all docs
    lock = threading.RLock()
    generation = secrets.token_hex(16)


def discover(pre_root, post_root, labels_dir, exclude):
    pairs = []
    files = sorted(glob.glob(os.path.join(pre_root, "*", "Part_*", "*.parquet")))
    groups = {}
    outputs = set()
    for pre in files:
        groups[os.path.dirname(pre)] = groups.get(os.path.dirname(pre), 0) + 1
    for pre in files:
        rel = os.path.relpath(pre, pre_root).split(os.sep)
        pack, part, fname = rel[0], rel[1], rel[2]
        if any(pack.startswith(x) for x in exclude):
            continue
        post = os.path.join(post_root, pack, fname)
        if not os.path.exists(post):
            print(f"skip (no post file): {pre}")
            continue
        key = f"{pack}/{part}/{fname}"
        suffix = "" if groups[os.path.dirname(pre)] == 1 else "_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        out = os.path.join(labels_dir, f"{pack}_{part}{suffix}.csv")
        if out in outputs:
            raise ValueError(f"ambiguous label output path: {out}")
        outputs.add(out)
        pairs.append(dict(key=key, pack=pack, part=part, file=fname, pre=pre, post=post,
                          out=out,
                          changed=None, total=None))
    return pairs


def count_changes():
    """Background: fill changed/total for every pair (doc_id + text only)."""
    for p in Hub.pairs:
        try:
            a = pq.read_table(p["pre"], columns=["doc_id", "text"]).to_pylist()
            b = {r["doc_id"]: r["text"] for r in
                 pq.read_table(p["post"], columns=["doc_id", "text"]).to_pylist()}
            p["changed"] = sum(1 for r in a if r["doc_id"] not in b
                               or (b[r["doc_id"]] or "") != (r["text"] or ""))
            p["total"] = len(a)
        except Exception as exc:  # keep going; show the error in the sidebar
            p["changed"], p["total"] = "error", str(exc)


def select(key, changed_only, random_nav):
    """Load a pair into view_pack_web's State. Raises ValueError on failure."""
    p = Hub.by_key.get(key)
    if p is None:
        raise ValueError(f"unknown pack {key!r}")
    with Hub.lock:
        old = (vpw.State.docs, vpw.State.doc_index, vpw.State.comparison,
               vpw.State.primary_name, vpw.State.comparison_name, vpw.State.out_path, vpw.State.total_docs)
        note = ""
        try:
            try:
                vpw.load_packs(p["pre"], p["post"], changed_only)
            except vpw.NoChangedDocs:
                # nothing changed in this pack: show every doc instead of refusing to open
                vpw.load_packs(p["pre"], p["post"], False)
                note = (f"No changed docs in {key}: showing all "
                        f"{len(vpw.State.docs)} (pre and post are identical).")
        except Exception:
            (vpw.State.docs, vpw.State.doc_index, vpw.State.comparison,
             vpw.State.primary_name, vpw.State.comparison_name, vpw.State.out_path, vpw.State.total_docs) = old
            raise
        vpw.State.primary_name = f"{key} (pre)"
        vpw.State.comparison_name = f"{p['pack']} (post)"
        vpw.State.out_path = p["out"]
        Hub.current, Hub.changed_only, Hub.random_nav = key, changed_only, random_nav
        Hub.note = note
        Hub.generation = secrets.token_hex(16)
    print(f"[{key}] {len(vpw.State.docs)} docs shown"
          f"{' (changed only)' if changed_only else ''}{' (random next)' if random_nav else ''}"
          f"  ->  saves to {p['out']}{'  [' + note + ']' if note else ''}")


def build_page():
    p = Hub.by_key[Hub.current]
    storage_id = hashlib.sha256(json.dumps([
        os.path.realpath(p["pre"]), os.path.realpath(p["out"]),
    ]).encode("utf-8")).hexdigest()
    n = len(vpw.State.docs)
    start = random.randrange(n) if (Hub.random_nav and n) else 0
    page = (vpw.PAGE.replace("__START__", str(start))
            .replace("__VISIBLE__", json.dumps(vpw.VISIBLE))
            .replace("__STORAGE_ID__", storage_id)
            .replace("__RANDOM_NAV__", "true" if Hub.random_nav else "false"))
    page = page.replace("</style>", SIDEBAR_CSS + "</style>", 1)
    page = page.replace("<body>", "<body>\n" + SIDEBAR_HTML, 1)
    # Every API call is tied to the exact loaded view, including filter changes.
    # Inject before the viewer script so bootstrap requests carry the token too.
    guard = """<script>
(() => {
  const originalFetch = window.fetch.bind(window);
  const generation = __GENERATION__;
  window.fetch = (input, options) => {
    const request = new Request(input, options);
    const url = new URL(request.url);
    if(url.origin === location.origin && url.pathname.startsWith('/api/'))
      request.headers.set('X-Pack-Generation', generation);
    return originalFetch(request);
  };
})();
</script>
""".replace("__GENERATION__", json.dumps(Hub.generation))
    page = page.replace("<script>", guard + "<script>", 1)
    page = page.replace("</body>", SIDEBAR_JS + "</body>", 1)
    return page


class HubHandler(vpw.Handler):
    def do_GET(self):
        with Hub.lock:
            if not self.check_generation():
                return
            return self.get_locked()

    def check_generation(self):
        if self.path.partition('?')[0].startswith('/api/') and self.headers.get('X-Pack-Generation') != Hub.generation:
            self._json({"error": "Pack changed in another tab or view. Reload this page; unsaved drafts are retained."}, 409)
            return False
        return True

    def get_locked(self):
        path = self.path.partition("?")[0]
        if path == "/":
            return self._send(200, build_page(), "text/html; charset=utf-8")
        if path == "/api/packs":
            return self._json({
                "current": Hub.current, "changed_only": Hub.changed_only,
                "random": Hub.random_nav, "note": Hub.note,
                "packs": [{k: p[k] for k in ("key", "pack", "part", "file", "changed", "total")}
                          for p in Hub.pairs],
            })
        return super().do_GET()

    def do_POST(self):
        with Hub.lock:
            if not self.check_generation():
                return
            return self.post_locked()

    def post_locked(self):
        path = self.path.partition("?")[0]
        if path != "/api/select":
            return super().do_POST()
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 16 * 1024 * 1024:
                raise ValueError("invalid request length")
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("expected an object")
            select(data.get("key", Hub.current), bool(data.get("changed_only")),
                   bool(data.get("random")))
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            return self._json({"error": str(exc)}, 400)
        self._json({"ok": True, "count": len(vpw.State.docs)})


SIDEBAR_CSS = r"""
  body { padding-left:260px; }
  #hub { position:fixed; left:0; top:0; bottom:0; width:260px; overflow:auto;
         background:var(--panel); border-right:1px solid var(--border);
         padding:10px; z-index:20; font-size:13px; }
  #hub h2 { font-size:14px; margin:0 0 8px; color:var(--accent); }
  #hub .opts { border:1px solid var(--border); border-radius:4px; padding:8px;
               margin-bottom:10px; display:flex; flex-direction:column; gap:6px; }
  #hub .group { margin:10px 0 2px; color:var(--muted); font-size:11px;
                text-transform:uppercase; letter-spacing:.05em; }
  #hub .pk { display:flex; justify-content:space-between; gap:6px; width:100%;
             text-align:left; margin:1px 0; padding:4px 6px; border-radius:4px;
             background:transparent; border:1px solid transparent; }
  #hub .pk:hover { background:#333; }
  #hub .pk.cur { border-color:var(--accent); background:#203a35; }
  #hub .pk.zero { opacity:.45; }
  #hub .cnt { color:var(--muted); font-size:11px; white-space:nowrap; }
  #hubMsg { color:#f48771; font-size:12px; min-height:1em; }
  #hubNote { color:#d7ba7d; font-size:12px; margin:4px 0; }
  #hubBusy[hidden] { display:none; }
  #hubBusy { position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:50;
             display:flex; align-items:center; justify-content:center; font-size:18px; }
"""

SIDEBAR_HTML = r"""
<aside id="hub">
  <h2>Packs</h2>
  <div class="opts">
    <label><input type="checkbox" id="optChanged"> Only changed docs</label>
    <label><input type="checkbox" id="optRandom"> Random next (far jumps)</label>
    <button id="optApply">Apply</button>
    <div id="hubNote" hidden></div>
    <div id="hubMsg"></div>
  </div>
  <div id="hubList">loading…</div>
</aside>
<div id="hubBusy" hidden>Loading pack…</div>
"""

SIDEBAR_JS = r"""
<script>
(function(){
  const el = id => document.getElementById(id);
  let state = null;
  const fmt = v => (typeof v === 'number') ? v.toLocaleString() : v;

  function render(){
    const list = el('hubList'); list.innerHTML = '';
    let group = null;
    for(const p of state.packs){
      if(p.pack !== group){
        group = p.pack;
        const g = document.createElement('div'); g.className='group'; g.textContent=p.pack;
        list.appendChild(g);
      }
      const b = document.createElement('button');
      b.className = 'pk' + (p.key===state.current ? ' cur' : '') + (p.changed===0 ? ' zero' : '');
      const cnt = p.changed===null ? '…' : (p.changed==='error' ? 'error' : fmt(p.changed)+' / '+fmt(p.total));
      b.innerHTML = '<span></span><span class="cnt"></span>';
      b.firstChild.textContent = p.part+' / '+p.file;
      b.lastChild.textContent = cnt;
      b.title = p.changed==='error' ? p.total : (p.changed===null ? 'counting…' : 'changed / total documents');
      b.onclick = () => choose(p.key);
      list.appendChild(b);
    }
    const cur = list.querySelector('.cur');
    if(cur && !render.scrolled){ cur.scrollIntoView({block:'center'}); render.scrolled = true; }
  }

  async function refresh(first){
    const response=await fetch('/api/packs');
    const data=await response.json();
    if(!response.ok){ el('hubMsg').textContent=data.error || 'Could not load packs'; return; }
    state = data;
    if(first){ el('optChanged').checked = state.changed_only; el('optRandom').checked = state.random; }
    el('hubNote').textContent = state.note || ''; el('hubNote').hidden = !state.note;
    render();
    if(state.packs.some(p => p.changed===null)) setTimeout(refresh, 3000);
  }

  async function choose(key){
    el('hubMsg').textContent = '';
    try { if(typeof commitCurrent === 'function') commitCurrent(); } catch(e){}
    el('hubBusy').hidden = false;
    try {
      const res = await fetch('/api/select', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({key, changed_only: el('optChanged').checked, random: el('optRandom').checked})});
      const data = await res.json();
      if(!res.ok){ el('hubBusy').hidden = true; el('hubMsg').textContent = data.error || 'could not load'; return; }
      location.reload();
    } catch(e){ el('hubBusy').hidden = true; el('hubMsg').textContent = e.message; }
  }

  el('optApply').onclick = () => choose(state ? state.current : null);
  refresh(true);
})();
</script>
"""


def main():
    ap = argparse.ArgumentParser(description="Pre/post pack viewer with a pack sidebar.")
    ap.add_argument("--pre-root", default=os.path.join(AUDIT, "Cap1-packs"))
    ap.add_argument("--post-root", default=os.path.join(AUDIT, "tokenizer_sample_v0_clean", "train"))
    ap.add_argument("--labels-dir", default=os.path.join(AUDIT, "audit_labels"))
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="Skip packs whose name starts with any of these prefixes, e.g. --exclude ind")
    ap.add_argument("--all-docs", action="store_true",
                    help="Start with 'Only changed' unticked")
    ap.add_argument("--sequential", action="store_true",
                    help="Start with 'Random next' unticked")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()

    os.makedirs(a.labels_dir, exist_ok=True)
    Hub.pairs = discover(a.pre_root, a.post_root, a.labels_dir, a.exclude)
    if not Hub.pairs:
        ap.error(f"no pack pairs found under {a.pre_root} and {a.post_root}")
    Hub.by_key = {p["key"]: p for p in Hub.pairs}
    print(f"Found {len(Hub.pairs)} pack pairs (excluding prefixes: {', '.join(a.exclude) or 'none'})")

    # Open the first pair that has something to show with the chosen options.
    for p in Hub.pairs:
        try:
            select(p["key"], not a.all_docs, not a.sequential)
            break
        except ValueError as exc:
            print(f"  skipping {p['key']} at startup: {exc}")
    else:
        ap.error("no pack could be opened; try --all-docs")

    threading.Thread(target=count_changes, daemon=True).start()

    srv = ThreadingHTTPServer((a.host, a.port), HubHandler)
    shown = "127.0.0.1" if a.host == "0.0.0.0" else a.host
    print(f"Serving on {a.host}:{a.port}  ->  open http://{shown}:{a.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
