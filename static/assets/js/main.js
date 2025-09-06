document.addEventListener("DOMContentLoaded", () => {
  const audio = document.querySelector("[data-audio]");
  const playBtn = document.querySelector("[data-play-toggle]");
  const range = document.querySelector("[data-seek]");
  const cur = document.querySelector("[data-current-time]");
  const left = document.querySelector("[data-remaining-time]");

  if (!audio || !playBtn || !range) return;

  playBtn.addEventListener("click", () => {
    if (audio.paused) {
      audio.play();
      playBtn.dataset.state = "pause";
    } else {
      audio.pause();
      playBtn.dataset.state = "";
    }
  });

  audio.addEventListener("timeupdate", () => {
    range.value = audio.currentTime;
    range.max = audio.duration;
  });

  range.addEventListener("input", () => {
    audio.currentTime = range.value;
  });

  const updateProgress = () => {
    const percent = (audio.currentTime / audio.duration) * 100 || 0;
    range.style.background = `linear-gradient(90deg, #422B23 ${percent}%, #F1DED0 ${percent}%)`;
  };

  audio.addEventListener("timeupdate", updateProgress);
  audio.addEventListener("loadedmetadata", updateProgress);

  if (!cur || !left) return;

  function formatTime(t) {
    if (!isFinite(t) || t < 0) t = 0;
    t = Math.floor(t);
    const h = Math.floor(t / 3600);
    const m = Math.floor((t % 3600) / 60);
    const s = t % 60;
    const mm = String(m).padStart(2, "0");
    const ss = String(s).padStart(2, "0");
    return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
  }

  function paint() {
    const dur = isFinite(audio.duration) ? audio.duration : 0;
    const ct = isFinite(audio.currentTime) ? audio.currentTime : 0;


    cur.textContent = formatTime(ct);
    left.textContent = "-" + formatTime(Math.max(0, dur - ct));

    if (dur > 0) {
      range.max = String(dur);
      range.value = String(ct);
      const pct = (ct / dur) * 100;
      range.style.background = `linear-gradient(90deg, #422B23 ${pct}%, #F1DED0 ${pct}%)`;
    } else {
      range.max = "0";
      range.value = "0";
      range.style.background = `linear-gradient(90deg, #422B23 0%, #F1DED0 0%)`;
    }
  }

  range.addEventListener("input", () => {
    const val = Number(range.value);
    if (isFinite(val)) audio.currentTime = val;
    paint();
  });

  audio.addEventListener("loadedmetadata", paint);
  audio.addEventListener("timeupdate", paint);
  audio.addEventListener("seeked", paint);
  audio.addEventListener("ended", () => {

    paint();
  });

  paint();




  function seekByPointerEvent(e) {
    if (!isFinite(audio.duration) || audio.duration <= 0) return;

    const rect = range.getBoundingClientRect();
    const x = (e.clientX ?? (e.touches && e.touches[0]?.clientX)) - rect.left;
    const clampedX = Math.max(0, Math.min(rect.width, x));
    const pct = clampedX / rect.width;
    const newTime = pct * audio.duration;

    audio.currentTime = newTime;


    paint();
  }

  range.addEventListener("click", (e) => {
    if (e.detail === 0) return;
    seekByPointerEvent(e);
  });

  range.addEventListener("pointerdown", (e) => {
    seekByPointerEvent(e);
  });
});

const items = document.querySelectorAll('.subscription-item');

if (items.length > 0) {
  items.forEach(item => {
    item.addEventListener('click', () => {
      items.forEach(el => el.classList.remove('active'));
      item.classList.add('active');
    });
  });
}

// Telegram initData auth hook
try {
  if (window.Telegram && window.Telegram.WebApp) {
    const initData = window.Telegram.WebApp.initData || '';
    // send initData once per session
    const sentKey = 'tg_init_sent';
    if (!sessionStorage.getItem(sentKey)) {
      const body = new URLSearchParams({ init_data: initData }).toString();
      // client debug logger
      fetch('/api/debug/log', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
          hint: 'before_auth', hasWebApp: true, hasInitData: !!initData, initDataLen: (initData || '').length,
          ua: navigator.userAgent, ref: document.referrer
        })
      }).catch(() => { });
      fetch('/api/telegram/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body
      }).then(r => r.json()).then((j) => {
        fetch('/api/debug/log', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
            hint: 'after_auth', resp: j
          })
        }).catch(() => { });
        try {
          if (j && j.ok) {
            // refresh to let server-side routes see session telegram_id
            window.location.replace('/');
          }
        } catch (e) { }
      }).catch((e) => { console.log('tg auth err', e); });
      sessionStorage.setItem(sentKey, '1');
    }
  }
} catch (e) { }

// External links in Telegram Mini App: open via WebApp API
document.addEventListener("click", (event) => {
  const anchor = event.target && event.target.closest ? event.target.closest('a[href]') : null;
  if (!anchor) return;
  const href = anchor.getAttribute('href') || '';
  if (!href) return;
  if (href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) return;

  // Only absolute http(s) links
  const isHttp = /^https?:\/\//i.test(href);
  if (!isHttp) return;

  let url;
  try { url = new URL(href, window.location.href); } catch (_) { return; }

  // Same-origin -> let default navigation
  if (url.origin === window.location.origin) return;

  if (window.Telegram && window.Telegram.WebApp) {
    event.preventDefault();
    if (/^https?:\/\/t\.me\//i.test(url.href)) {
      window.Telegram.WebApp.openTelegramLink(url.href);
    } else {
      window.Telegram.WebApp.openLink(url.href, { try_instant_view: true });
    }
  }
});

// Telegram BackButton integration for mini app
try {
  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.BackButton) {
    const BB = window.Telegram.WebApp.BackButton;
    // Show back button on pages that are not root
    const isRoot = window.location.pathname === '/' || window.location.pathname === '';
    if (!isRoot) {
      BB.show();
      BB.onClick(() => {
        if (document.referrer && document.referrer !== window.location.href) {
          history.back();
        } else {
          window.location.href = '/';
        }
      });
    } else {
      BB.hide();
    }
  }
} catch (_) { }