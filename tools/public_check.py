# -*- coding: utf-8 -*-
"""Generic CDP check: given a URL, verify Streamlit renders + PWA manifest injected.
Usage: public_check.py <URL> [cdp_port] [wait_seconds]
"""
import json, sys, time, urllib.request, websocket

URL = sys.argv[1]
PORT = sys.argv[2] if len(sys.argv) > 2 else "9551"
WAIT = int(sys.argv[3]) if len(sys.argv) > 3 else 30
res_file = r"C:\Users\duoyun\Documents\deepseek-harness\default-workspace\china-legal-ai-copilot\tools\public_check_result.json"

req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?" + URL, method="PUT")
tab = json.loads(urllib.request.urlopen(req, timeout=15).read())
ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=40, suppress_origin=True)

mid = [0]
def cmd(method, params=None):
    mid[0] += 1
    ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid[0]:
            return msg

cmd("Runtime.enable")
cmd("Page.enable")
time.sleep(WAIT)

r = cmd("Runtime.evaluate", {
    "expression": r"""(() => {
      const d=document, txt=(d.body&&d.body.innerText)?d.body.innerText:'';
      const mf=d.querySelector('link[rel="manifest"]');
      const root=document.querySelector('#root');
      return {title:d.title, url:location.href, readyState:d.readyState,
        hasManifest:!!mf, manifestHref:mf?mf.href:null,
        capable:(()=>{const e=d.querySelector('meta[name="mobile-web-app-capable"]');return e?e.content:null;})(),
        rootLen: root?root.innerHTML.length:-1,
        textLen:txt.length, hasChinese:/[\u4e00-\u9fff]/.test(txt),
        hasSidebar:txt.indexOf('律师')>=0, snippet:txt.slice(0,600)};
    })()""",
    "returnByValue": True
})
val = r.get("result", {}).get("result", {}).get("value", {})
with open(res_file, "w", encoding="utf-8") as f:
    json.dump(val, f, ensure_ascii=False, indent=2)
print(json.dumps(val, ensure_ascii=False))
ws.close()
