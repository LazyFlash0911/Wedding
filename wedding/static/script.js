(() => {
  const root = document.documentElement;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const store = (storage) => ({
    get(key) { try { return storage().getItem(key); } catch (error) { return null; } },
    set(key, value) { try { storage().setItem(key, value); } catch (error) { /* storage unavailable */ } },
  });
  const local = store(() => window.localStorage);
  const session = store(() => window.sessionStorage);

  // Language toggle: elements carry their Hindi text in data-hi attributes.
  const STRINGS = {
    en: { musicOn: "Music on", musicOff: "Music off", turnMusicOn: "Turn music on", turnMusicOff: "Turn music off", otherLanguage: "हिंदी", opened: "Your invitation is open" },
    hi: { musicOn: "संगीत चालू", musicOff: "संगीत बंद", turnMusicOn: "संगीत चालू करें", turnMusicOff: "संगीत बंद करें", otherLanguage: "English", opened: "आपका निमंत्रण खुल गया है" },
  };
  let lang = local.get("lang") === "hi" ? "hi" : "en";
  const t = (key) => STRINGS[lang][key];
  const languageListeners = [];
  const englishTitle = document.title;

  function swap(selector, hiKey, enKey, read, write) {
    document.querySelectorAll(selector).forEach((element) => {
      if (element.dataset[enKey] === undefined) element.dataset[enKey] = read(element);
      write(element, lang === "hi" ? element.dataset[hiKey] : element.dataset[enKey]);
    });
  }

  function applyLanguage() {
    root.lang = lang;
    swap("[data-hi]", "hi", "en", (el) => el.textContent, (el, value) => { el.textContent = value; });
    swap("[data-hi-html]", "hiHtml", "enHtml", (el) => el.innerHTML, (el, value) => { el.innerHTML = value; });
    swap("[data-hi-placeholder]", "hiPlaceholder", "enPlaceholder", (el) => el.placeholder, (el, value) => { el.placeholder = value; });
    swap("[data-hi-aria-label]", "hiAriaLabel", "enAriaLabel", (el) => el.getAttribute("aria-label") || "", (el, value) => el.setAttribute("aria-label", value));
    document.title = lang === "hi" ? root.dataset.titleHi : englishTitle;
    document.querySelectorAll(".lang-toggle").forEach((button) => { button.textContent = t("otherLanguage"); });
    languageListeners.forEach((listener) => listener());
  }

  document.querySelectorAll(".lang-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      lang = lang === "hi" ? "en" : "hi";
      local.set("lang", lang);
      applyLanguage();
    });
  });

  // Background music: loaded only when the guest opens the invitation or presses the button.
  const musicButton = document.getElementById("music-toggle");
  const musicLabel = document.getElementById("music-label");
  let audio = null;

  function updateMusicButton() {
    if (!musicButton) return;
    const playing = Boolean(audio && !audio.paused);
    musicButton.setAttribute("aria-pressed", String(playing));
    musicLabel.textContent = playing ? t("musicOn") : t("musicOff");
    musicButton.title = playing ? t("turnMusicOff") : t("turnMusicOn");
  }

  async function startMusic() {
    if (!musicButton) return;
    if (!audio) {
      audio = new Audio(musicButton.dataset.src);
      audio.loop = true;
      audio.volume = 0.3;
      audio.addEventListener("play", updateMusicButton);
      audio.addEventListener("pause", updateMusicButton);
    }
    try {
      await audio.play();
    } catch (error) {
      // Playback was blocked or the file is missing; the button stays off.
    }
    updateMusicButton();
  }

  musicButton?.addEventListener("click", () => {
    if (audio && !audio.paused) audio.pause();
    else startMusic();
  });
  languageListeners.push(updateMusicButton);

  // Scroll reveal, started once the envelope intro is out of the way.
  function startReveal() {
    const items = document.querySelectorAll(".reveal");
    if (reducedMotion || !("IntersectionObserver" in window)) {
      items.forEach((item) => item.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.1 });
    items.forEach((item) => observer.observe(item));
  }

  // Envelope intro: open the flap, slide the letter up, then fade into the invitation.
  const intro = document.getElementById("intro");
  const openButton = document.getElementById("open-invite");
  const openLabel = document.getElementById("open-label");

  function closeIntro() {
    root.classList.add("intro-skipped");
    root.classList.remove("intro-leaving");
    if (intro) intro.hidden = true;
    window.scrollTo(0, 0);
    document.getElementById("top")?.focus({ preventScroll: true });
    startReveal();
  }

  if (!intro || root.classList.contains("intro-skipped")) {
    if (intro) intro.hidden = true;
    root.classList.add("intro-skipped");
    startReveal();
  } else {
    openButton?.addEventListener("click", () => {
      session.set("invite-opened", "1");
      startMusic();
      document.body.classList.add("invitation-open");
      openButton.setAttribute("aria-expanded", "true");
      openButton.disabled = true;
      openLabel.dataset.en = STRINGS.en.opened;
      openLabel.dataset.hi = STRINGS.hi.opened;
      openLabel.textContent = t("opened");
      window.setTimeout(() => {
        root.classList.add("intro-leaving");
        window.setTimeout(closeIntro, reducedMotion ? 0 : 750);
      }, reducedMotion ? 0 : 1500);
    });
  }

  // Mobile menu.
  const navToggle = document.getElementById("nav-toggle");
  const navLinks = document.getElementById("nav-links");
  function setMenu(open) {
    navToggle?.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("menu-open", open);
  }
  navToggle?.addEventListener("click", () => setMenu(navToggle.getAttribute("aria-expanded") !== "true"));
  navLinks?.addEventListener("click", (event) => { if (event.target.closest("a")) setMenu(false); });
  document.addEventListener("click", (event) => {
    if (document.body.classList.contains("menu-open") && !event.target.closest(".nav")) setMenu(false);
  });

  // Countdown to the wedding, replaced by a message once the day arrives.
  const countdown = document.getElementById("countdown");
  if (countdown) {
    const target = new Date(countdown.dataset.date).getTime();
    const fields = ["days", "hours", "minutes", "seconds"].map((id) => document.getElementById(id));
    let timer = null;
    function updateCountdown() {
      const remaining = target - Date.now();
      if (!Number.isFinite(target) || remaining <= 0) {
        document.getElementById("countdown-live").hidden = true;
        document.getElementById("countdown-done").hidden = false;
        if (timer) window.clearInterval(timer);
        return;
      }
      const values = [
        Math.floor(remaining / 86400000),
        Math.floor((remaining % 86400000) / 3600000),
        Math.floor((remaining % 3600000) / 60000),
        Math.floor((remaining % 60000) / 1000),
      ];
      fields.forEach((field, index) => { field.textContent = values[index]; });
    }
    updateCountdown();
    timer = window.setInterval(updateCountdown, 1000);
  }

  // Full-screen photo viewer with keyboard and swipe support.
  const lightbox = document.getElementById("lightbox");
  const lightboxImage = document.getElementById("lightbox-image");
  const lightboxCaption = document.getElementById("lightbox-caption");
  const lightboxPrev = document.getElementById("lightbox-prev");
  const lightboxNext = document.getElementById("lightbox-next");
  const lightboxClose = document.getElementById("lightbox-close");
  let lightboxItems = [];
  let lightboxIndex = 0;
  let lightboxReturnFocus = null;

  const captionFor = (item) => (lang === "hi" && item.captionHi ? item.captionHi : item.caption) || "";

  function showLightboxItem(index) {
    lightboxIndex = (index + lightboxItems.length) % lightboxItems.length;
    const item = lightboxItems[lightboxIndex];
    lightboxImage.src = item.src;
    lightboxImage.alt = captionFor(item);
    lightboxCaption.textContent = captionFor(item);
    lightboxPrev.hidden = lightboxNext.hidden = lightboxItems.length < 2;
  }

  function openLightbox(items, index, trigger) {
    if (!lightbox || !items.length) return;
    lightboxItems = items;
    lightboxReturnFocus = trigger;
    lightbox.hidden = false;
    document.body.classList.add("lightbox-open");
    showLightboxItem(index);
    lightboxClose.focus();
  }

  function closeLightbox() {
    lightbox.hidden = true;
    document.body.classList.remove("lightbox-open");
    lightboxImage.removeAttribute("src");
    lightboxReturnFocus?.focus();
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-lightbox]");
    if (!trigger) return;
    const group = Array.from(document.querySelectorAll(`[data-lightbox="${trigger.dataset.lightbox}"]`));
    const items = group.map((element) => ({
      src: element.dataset.src,
      caption: element.dataset.caption,
      captionHi: element.dataset.captionHi,
    }));
    openLightbox(items, group.indexOf(trigger), trigger);
  });

  if (lightbox) {
    lightboxClose.addEventListener("click", closeLightbox);
    lightboxPrev.addEventListener("click", () => showLightboxItem(lightboxIndex - 1));
    lightboxNext.addEventListener("click", () => showLightboxItem(lightboxIndex + 1));
    lightbox.addEventListener("click", (event) => { if (event.target === lightbox) closeLightbox(); });
    lightbox.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeLightbox();
      else if (event.key === "ArrowLeft") showLightboxItem(lightboxIndex - 1);
      else if (event.key === "ArrowRight") showLightboxItem(lightboxIndex + 1);
      else if (event.key === "Tab") {
        const focusable = Array.from(lightbox.querySelectorAll("button:not([hidden])"));
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
    addSwipe(lightbox, () => showLightboxItem(lightboxIndex + 1), () => showLightboxItem(lightboxIndex - 1));
    languageListeners.push(() => { if (!lightbox.hidden) showLightboxItem(lightboxIndex); });
  }

  function addSwipe(element, onLeft, onRight) {
    let startX = null;
    element.addEventListener("touchstart", (event) => { startX = event.touches[0].clientX; }, { passive: true });
    element.addEventListener("touchend", (event) => {
      if (startX === null) return;
      const distance = event.changedTouches[0].clientX - startX;
      startX = null;
      if (Math.abs(distance) < 50) return;
      event.preventDefault(); // A swipe should not also count as a tap.
      if (distance < 0) onLeft(); else onRight();
    });
  }

  // Memories carousel. Photos and captions come from the server as JSON.
  const memoriesData = document.getElementById("memories-data");
  const memories = memoriesData ? JSON.parse(memoriesData.textContent) : [];
  const memoryImage = document.getElementById("gallery-image");
  const memoryFrame = document.getElementById("memory-open");
  const memoryPrev = document.getElementById("gallery-prev");
  const memoryNext = document.getElementById("gallery-next");
  const memoryDots = Array.from(document.querySelectorAll("#gallery-dots button"));
  let currentMemory = 0;

  function memoryText(item, key) {
    return (lang === "hi" && item[`${key}_hi`]) || item[key] || "";
  }

  function showMemory(index) {
    if (!memories.length || !memoryImage) return;
    currentMemory = Math.max(0, Math.min(memories.length - 1, index));
    const item = memories[currentMemory];
    document.getElementById("memory-title").textContent = memoryText(item, "title");
    document.getElementById("memory-text").textContent = memoryText(item, "caption");
    document.getElementById("memory-index").textContent =
      `${String(currentMemory + 1).padStart(2, "0")} / ${String(memories.length).padStart(2, "0")}`;
    if (!memoryImage.src.endsWith(item.src)) {
      memoryImage.classList.remove("loaded");
      memoryImage.src = item.src;
    }
    memoryImage.alt = memoryText(item, "title") || "Priyanka and Ankoosh";
    memoryPrev.disabled = currentMemory === 0;
    memoryNext.disabled = currentMemory === memories.length - 1;
    memoryDots.forEach((dot, i) => dot.classList.toggle("active", i === currentMemory));
  }

  if (memoryImage) {
    memoryImage.addEventListener("load", () => memoryImage.classList.add("loaded"));
    if (memoryImage.complete) memoryImage.classList.add("loaded");
    memoryPrev.addEventListener("click", () => showMemory(currentMemory - 1));
    memoryNext.addEventListener("click", () => showMemory(currentMemory + 1));
    memoryDots.forEach((dot) => dot.addEventListener("click", () => showMemory(Number(dot.dataset.index))));
    memoryFrame.addEventListener("click", () => {
      const items = memories.map((item) => ({
        src: item.large,
        caption: [item.title, item.caption].filter(Boolean).join(" · "),
        captionHi: [item.title_hi, item.caption_hi].filter(Boolean).join(" · "),
      }));
      openLightbox(items, currentMemory, memoryFrame);
    });
    addSwipe(memoryFrame, () => showMemory(currentMemory + 1), () => showMemory(currentMemory - 1));
    languageListeners.push(() => showMemory(currentMemory));
    showMemory(0);
  }

  // Subtle falling petals. Respects reduced-motion preferences.
  const petalLayer = document.getElementById("petal-layer");
  if (petalLayer && !reducedMotion) {
    const symbols = ["✿", "❀", "✽"];
    let count = 0;
    window.setInterval(() => {
      if (document.hidden || count >= 12) return;
      const petal = document.createElement("span");
      petal.className = "petal";
      petal.textContent = symbols[Math.floor(Math.random() * symbols.length)];
      petal.style.left = `${Math.random() * 100}%`;
      petal.style.fontSize = `${10 + Math.random() * 10}px`;
      petal.style.setProperty("--drift", `${Math.random() * 160 - 80}px`);
      petal.style.animationDuration = `${8 + Math.random() * 7}s`;
      petalLayer.appendChild(petal);
      count++;
      petal.addEventListener("animationend", () => { petal.remove(); count--; });
    }, 1500);
  }

  applyLanguage();
})();
