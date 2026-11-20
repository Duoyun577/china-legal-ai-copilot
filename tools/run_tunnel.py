# -*- coding: utf-8 -*-
"""Start Cloudflare quick tunnel; write the assigned public URL to a fixed file
so the user never has to copy it from a scrolling console window.

Mainland-China note: --protocol http2 is required because UDP/QUIC is blocked.
"""
import os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "tools", "cloudflared.exe")
LOG = os.path.join(ROOT, "tools", "tunnel_latest.log")
ADDR = os.path.join(ROOT, "当前公网地址.txt")

# Clear stale URL / log from any previous run.
for p in (ADDR, LOG):
    try:
        os.remove(p)
    except OSError:
        pass

cmd = [CF, "tunnel", "--protocol", "http2", "--no-autoupdate",
       "--edge-ip-version", "4",  # mainland networks: IPv6 edge dials time out on 7844
       "--url", "http://127.0.0.1:8501"]
print("正在建立公网隧道，请稍候（最多约 60 秒）...", flush=True)

with open(LOG, "w", encoding="utf-8", errors="replace") as lf:
    proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
    url = None
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with open(LOG, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = ""
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", text)
        if m:
            url = m.group(0)
            break
        if proc.poll() is not None:
            break
        time.sleep(1)

    if url:
        with open(ADDR, "w", encoding="utf-8") as f:
            f.write(url + "\n")
        print("\n" + "=" * 56, flush=True)
        print("  ★ 本次公网地址：", url, flush=True)
        print("  已自动保存到项目目录的『当前公网地址.txt』", flush=True)
        print("  手机/外网打开这个网址即可使用工作台。", flush=True)
        print("=" * 56 + "\n", flush=True)
    else:
        print("\n✗ 未能取得公网地址，请查看 tools\\tunnel_latest.log", flush=True)
        print("  常见原因：网络限制或 Cloudflare 临时隧道限流，稍后重试。\n", flush=True)

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
