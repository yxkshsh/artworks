/* =========================================================
   作品集交互：入场动效 / 视频内嵌播放 / 图像灯箱
   无依赖，约 3KB
   ========================================================= */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* ---------- 1. 滚动入场 ---------- */

  const revealables = $$('.reveal');
  if ('IntersectionObserver' in window && revealables.length) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        });
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.06 },
    );
    revealables.forEach((el, i) => {
      el.style.transitionDelay = `${Math.min(i % 3, 2) * 70}ms`;
      io.observe(el);
    });
  } else {
    revealables.forEach((el) => el.classList.add('in'));
  }

  /* ---------- 2. 影像：点击后原位播放 ---------- */

  const stopAll = (except) => {
    $$('.frame video').forEach((v) => {
      if (v === except) return;
      v.pause();
      v.closest('.film')?.classList.remove('is-playing');
    });
  };

  $$('.film').forEach((film) => {
    const frame = $('.frame', film);
    if (!frame) return;
    const btn = frame.tagName === 'BUTTON' ? frame : null;

    const play = () => {
      if (frame.classList.contains('is-playing')) return;
      stopAll();
      const src = frame.dataset.video;
      if (!src) return;

      const video = document.createElement('video');
      video.src = src;
      video.controls = true;
      video.autoplay = true;
      video.playsInline = true;
      video.preload = 'metadata';
      video.setAttribute('playsinline', '');
      if (frame.dataset.poster) video.poster = frame.dataset.poster;
      video.setAttribute('aria-label', film.dataset.title || '作品视频');

      frame.classList.add('is-playing');
      film.classList.add('is-playing');
      frame.textContent = '';
      frame.appendChild(video);
      video.play().catch(() => { /* 浏览器拦截自动播放时保留控制条 */ });
    };

    if (btn) btn.addEventListener('click', play);
    else frame.addEventListener('click', play);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    stopAll();
  });

  /* ---------- 3. 图像灯箱 ---------- */

  const figures = $$('.still').map((fig) => {
    const img = $('img', fig);
    return {
      el: fig,
      full: $('button', fig)?.dataset.full || img?.currentSrc || img?.src || '',
      title: $('h3', fig)?.textContent.trim() || '',
      sub: $('.sub', fig)?.textContent.trim() || '',
      alt: img?.alt || '',
    };
  });

  const box = $('#lightbox');
  if (!box || !figures.length) return;

  const boxImg = $('img', box);
  const boxTitle = $('strong', box);
  const boxSub = $('.lb-sub', box);
  const btnPrev = $('.lb-prev', box);
  const btnNext = $('.lb-next', box);
  let current = 0;
  let lastFocus = null;

  const render = (i) => {
    current = (i + figures.length) % figures.length;
    const item = figures[current];
    boxImg.src = item.full;
    boxImg.alt = item.alt;
    boxTitle.textContent = item.title;
    if (boxSub) boxSub.textContent = item.sub ? `${item.sub} · ${current + 1}/${figures.length}` : `${current + 1}/${figures.length}`;
    btnPrev.hidden = figures.length < 2;
    btnNext.hidden = figures.length < 2;
  };

  const open = (i) => {
    lastFocus = document.activeElement;
    render(i);
    box.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    $('.lb-close', box)?.focus({ preventScroll: true });
  };

  const close = () => {
    box.classList.remove('is-open');
    document.body.style.overflow = '';
    boxImg.removeAttribute('src');
    if (lastFocus instanceof HTMLElement) lastFocus.focus({ preventScroll: true });
  };

  figures.forEach((item, i) => {
    $('button', item.el)?.addEventListener('click', () => open(i));
  });

  $('.lb-close', box)?.addEventListener('click', close);
  btnPrev?.addEventListener('click', () => render(current - 1));
  btnNext?.addEventListener('click', () => render(current + 1));

  box.addEventListener('click', (e) => {
    if (e.target.closest('.lb-btn')) return;
    if (e.target.closest('figcaption')) return;
    if (e.target.tagName === 'IMG') return;
    close();
  });

  document.addEventListener('keydown', (e) => {
    if (!box.classList.contains('is-open')) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft') render(current - 1);
    if (e.key === 'ArrowRight') render(current + 1);
  });
})();
