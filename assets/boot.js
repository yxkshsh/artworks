/* =========================================================
   版本自检
   GitHub Pages 会给 HTML 加 10 分钟缓存，改完文案刷新页面常常还是旧的。
   这里在加载时问一下服务器上的 build 号：比本页新就自动刷新一次。
   每个 build 只尝试一次（sessionStorage），不会来回刷。
   ========================================================= */
(() => {
  const current = document.currentScript?.dataset.build || '';
  if (!current) return;

  let stored = null;
  try {
    stored = sessionStorage.getItem('site-build');
  } catch {
    /* 隐私模式下 sessionStorage 可能不可用，忽略 */
  }

  if (stored === current) return;

  fetch(`version.json?t=${Date.now()}`, { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : null))
    .then((v) => {
      if (!v || !v.build) return;

      if (v.build === current) {
        // 页面已是最新，记下来，避免每次加载都多问一次
        try {
          sessionStorage.setItem('site-build', current);
        } catch {}
        return;
      }

      if (stored) return; // 已经试过一次，别刷个没完

      try {
        sessionStorage.setItem('site-build', v.build);
      } catch {}
      location.reload();
    })
    .catch(() => {
      /* 离线或请求失败：保持现状 */
    });
})();
