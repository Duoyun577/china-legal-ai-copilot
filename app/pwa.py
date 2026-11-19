"""PWA 支持：向主文档注入 manifest 并注册 Service Worker，使应用可「添加到主屏幕」。

Streamlit 的 iframe 内容运行在同源 iframe 中，脚本通过 window.parent.document
把 <link rel="manifest"> 等注入到主文档 head，浏览器才能识别 PWA。所有注入均幂等，
失败不影响主功能。静态资源由 Streamlit app static 服务于 /app/static/ 路径。

兼容性：Streamlit >= 1.61 提供 st.iframe（无弃用警告）；< 1.61 需回退到
components.v1.html（requirements 允许 1.60.x）。两条路径都能让内联脚本以 srcdoc
方式执行并同源访问主文档，因此 PWA 注入行为一致。
"""

from __future__ import annotations

import streamlit as st


_BOOTSTRAP = """
<script>
(function () {
  var doc = window.parent.document;
  var head = doc.head;
  var BASE = '/app/static/';
  if (!doc.querySelector('link[rel="manifest"]')) {
    var link = doc.createElement('link');
    link.rel = 'manifest';
    link.href = BASE + 'manifest.json';
    head.appendChild(link);
  }
  if (!doc.querySelector('link[data-pwa-icon]')) {
    var icon = doc.createElement('link');
    icon.rel = 'icon';
    icon.type = 'image/png';
    icon.href = BASE + 'icon-192.png';
    icon.setAttribute('data-pwa-icon', '1');
    head.appendChild(icon);
  }
  if (!doc.querySelector('meta[name="mobile-web-app-capable"]')) {
    var m1 = doc.createElement('meta');
    m1.name = 'mobile-web-app-capable'; m1.content = 'yes'; head.appendChild(m1);
    var m2 = doc.createElement('meta');
    m2.name = 'apple-mobile-web-app-capable'; m2.content = 'yes'; head.appendChild(m2);
    var m3 = doc.createElement('meta');
    m3.name = 'apple-mobile-web-app-status-bar-style'; m3.content = 'default'; head.appendChild(m3);
    var m4 = doc.createElement('meta');
    m4.name = 'theme-color'; m4.content = '#12203b'; head.appendChild(m4);
  }
  // 本脚本运行在 srcdoc iframe 中（opaque origin，location=about:srcdoc），
  // 直接用其 navigator 注册 SW 会抛 SecurityError 并被静默吞掉。必须经由
  // 主文档（window.parent）的 navigator 在顶层上下文注册，SW 才会真正生效。
  try {
    var parentWin = window.parent || window;
    var swNav = parentWin.navigator || navigator;
    var base = parentWin.location.href;  // 顶层正常页面（非 about:srcdoc）
    if ('serviceWorker' in swNav) {
      swNav.serviceWorker.register(new URL(BASE + 'sw.js', base).href,
                                   { scope: new URL(BASE, base).href })
        .catch(function () {});
    }
  } catch (e) {}
})();
</script>
"""


def enable_pwa() -> None:
    """启用「添加到主屏幕」能力；无副作用，可安全重复调用。"""
    try:
        iframe_fn = getattr(st, "iframe", None)
        if iframe_fn is not None:
            # Streamlit >= 1.61：新 API，不产生 components.v1.html 弃用警告。
            # height 必须为正整数（0 非法），1px 视觉上不可见。
            iframe_fn(_BOOTSTRAP, height=1)
        else:
            # Streamlit 1.60.x：回退到旧的 components.v1.html（会打印弃用警告，
            # 但功能一致，且在 <1.62 范围内该 API 仍可用）。
            from streamlit.components.v1 import html
            html(_BOOTSTRAP, height=0, scrolling=False)
    except Exception:
        # PWA 是增强能力，任何环境下失败都不应影响主功能
        pass
