// Telegram Mini App API
let tg = window.Telegram?.WebApp;

// Состояние пользователя
const userState = {
  hasUsedFreePodcast: false,
  freePodcastId: null,
  purchasedPodcasts: [],
  hasSubscription: false
};

// Инициализация Telegram Mini App
function initTelegramApp() {
  if (tg) {
    tg.ready();
    tg.expand();

    // Получаем данные пользователя из Telegram
    const user = tg.initDataUnsafe?.user;
    if (user) {
      // В реальном приложении здесь был бы запрос к серверу
      loadUserState(user.id);
    }
  }
}

// Загрузка состояния пользователя
function loadUserState(userId) {
  // В реальном приложении здесь был бы запрос к серверу
  const savedState = localStorage.getItem(`user_${userId}`);
  if (savedState) {
    Object.assign(userState, JSON.parse(savedState));
  }
}

// Сохранение состояния пользователя
function saveUserState() {
  if (tg?.initDataUnsafe?.user?.id) {
    localStorage.setItem(`user_${tg.initDataUnsafe.user.id}`, JSON.stringify(userState));
  }
}

// Проверка, может ли пользователь слушать подкаст
function canListenPodcast(podcastId) {
  if (userState.hasSubscription) return true;
  if (userState.purchasedPodcasts.includes(podcastId)) return true;
  if (!userState.hasUsedFreePodcast) return true;
  return false;
}

// Показать модальное окно покупки
function showPurchaseModal(podcastId, podcastTitle) {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h3>Доступ к подкасту</h3>
        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
      </div>
      <div class="modal-content">
        <p>Бесплатный выпуск вы уже получили. Чтобы слушать этот подкаст — купите выпуск или подписку.</p>
        <div class="purchase-options">
          <button class="btn-secondary" onclick="useFreePreview('${podcastId}')">
            Бесплатно - 5 минут
          </button>
          <button class="btn-primary" onclick="purchasePodcast('${podcastId}')">
            Купить выпуск — 200 ₽
          </button>
          <button class="btn-secondary" onclick="purchaseSubscription()">
            Подписка — 1500 ₽
          </button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}

// Использовать бесплатный предпросмотр
function useFreePreview(podcastId) {
  // Показать уведомление о предпросмотре
  showToast('Включен предпросмотр на 5 минут');

  // В реальном приложении здесь был бы переход к preview версии
  // Сейчас просто закрываем модальное окно
  document.querySelector('.modal-overlay')?.remove();
}

// Покупка подкаста
function purchasePodcast(podcastId) {
  // В реальном приложении здесь был бы переход к экрану оплаты
  window.location.href = `checkout.html?type=podcast&id=${podcastId}`;
}

// Покупка подписки
function purchaseSubscription() {
  // В реальном приложении здесь был бы переход к экрану оплаты
  window.location.href = `checkout.html?type=subscription`;
}

// Показать toast уведомление
function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3000);
}

document.addEventListener("DOMContentLoaded", () => {
  const audio = document.querySelector("[data-audio]");
  const playBtn = document.querySelector("[data-play-toggle]");
  const range = document.querySelector("[data-seek]");
  const cur = document.querySelector("[data-current-time]");
  const left = document.querySelector("[data-remaining-time]");

  if (!audio || !playBtn || !range) return;

  // Получаем ID подкаста из URL или data-атрибута
  const podcastId = new URLSearchParams(window.location.search).get('id') || 'default';

  // Проверяем, может ли пользователь слушать этот подкаст
  if (!canListenPodcast(podcastId)) {
    // Показываем модальное окно покупки
    showPurchaseModal(podcastId, document.querySelector('h2')?.textContent || 'Подкаст');

    // Блокируем воспроизведение
    playBtn.disabled = true;
    playBtn.style.opacity = '0.5';

    // Обновляем тег
    if (podcastTag) {
      podcastTag.textContent = 'Требуется покупка';
      podcastTag.style.background = '#ff6b6b';
    }
  } else {
    // Если это первый бесплатный подкаст, отмечаем его
    if (!userState.hasUsedFreePodcast && !userState.hasSubscription && !userState.purchasedPodcasts.includes(podcastId)) {
      userState.hasUsedFreePodcast = true;
      userState.freePodcastId = podcastId;
      saveUserState();

      if (podcastTag) {
        podcastTag.textContent = 'Это ваш бесплатный подкаст';
        podcastTag.style.background = '#4CAF50';
      }
    }
  }

  playBtn.addEventListener("click", () => {
    // Проверяем доступ перед воспроизведением
    if (!canListenPodcast(podcastId)) {
      showPurchaseModal(podcastId, document.querySelector('h2')?.textContent || 'Подкаст');
      return;
    }

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
