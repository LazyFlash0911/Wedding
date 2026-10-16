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
    en: {
      musicOn: "Music on", musicOff: "Music off", turnMusicOn: "Turn music on", turnMusicOff: "Turn music off",
      otherLanguage: "हिंदी", otherLanguageLong: "हिंदी में पढ़ें", opened: "Your invitation is open",
      today: "Today", now: "Happening now", completed: "Completed", linkCopied: "Link copied. Paste it in WhatsApp to share.",
    },
    hi: {
      musicOn: "संगीत चालू", musicOff: "संगीत बंद", turnMusicOn: "संगीत चालू करें", turnMusicOff: "संगीत बंद करें",
      otherLanguage: "English", otherLanguageLong: "Read in English", opened: "आपका निमंत्रण खुल गया है",
      today: "आज", now: "अभी चल रहा है", completed: "संपन्न", linkCopied: "लिंक कॉपी हो गया। साझा करने के लिए व्हाट्सऐप में पेस्ट करें।",
    },
  };
  const savedLang = local.get("lang");
  let lang = savedLang === "hi" || (!savedLang && /^hi\b/i.test(navigator.language || "")) ? "hi" : "en";
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
    document.querySelectorAll(".lang-toggle").forEach((button) => {
      button.textContent = button.classList.contains("intro-lang") ? t("otherLanguageLong") : t("otherLanguage");
    });
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

  if (musicButton) musicButton.addEventListener("click", () => {
    if (audio && !audio.paused) audio.pause();
    else startMusic();
  });
  languageListeners.push(updateMusicButton);

  // Pause when the guest switches to another app (e.g. back to WhatsApp), resume when they return.
  let pausedByHiding = false;
  document.addEventListener("visibilitychange", () => {
    if (!audio) return;
    if (document.hidden && !audio.paused) {
      audio.pause();
      pausedByHiding = true;
    } else if (!document.hidden && pausedByHiding) {
      pausedByHiding = false;
      startMusic();
    }
  });

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
    document.getElementById("top").focus({ preventScroll: true });
    startReveal();
  }

  if (!intro || root.classList.contains("intro-skipped")) {
    if (intro) intro.hidden = true;
    root.classList.add("intro-skipped");
    startReveal();
  } else {
    if (openButton) openButton.addEventListener("click", () => {
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
    if (navToggle) navToggle.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("menu-open", open);
  }
  if (navToggle) navToggle.addEventListener("click", () => setMenu(navToggle.getAttribute("aria-expanded") !== "true"));
  if (navLinks) navLinks.addEventListener("click", (event) => { if (event.target.closest("a")) setMenu(false); });
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

  // "Add to calendar": iPhones and Macs open the .ics file in Apple Calendar; everyone else gets Google Calendar.
  const isApple = /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent) && !/Android/.test(navigator.userAgent);
  if (isApple) {
    document.querySelectorAll(".calendar-link[data-ics]").forEach((link) => {
      link.href = link.dataset.ics;
      link.removeAttribute("target");
    });
  }

  // Event-day status: "Today" / "Happening now" badges, and a banner at the top of the page.
  const eventCards = Array.from(document.querySelectorAll(".event-card[data-start]"));
  const todayBanner = document.getElementById("today-banner");
  const istDate = (time) => new Date(time).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

  function updateEventStatus() {
    const now = Date.now();
    let bannerEvent = null;
    eventCards.forEach((card) => {
      const start = new Date(card.dataset.start).getTime();
      const end = new Date(card.dataset.end).getTime();
      const status = card.querySelector(".event-status");
      let label = "";
      if (now >= start && now < end) label = "now";
      else if (now < start && istDate(now) === istDate(start)) label = "today";
      else if (now >= end) label = "completed";
      card.classList.toggle("is-live", label === "now" || label === "today");
      card.classList.toggle("is-past", label === "completed");
      status.hidden = !label;
      status.textContent = label ? t(label) : "";
      if (!bannerEvent && (label === "now" || label === "today")) bannerEvent = { card, label };
    });

    if (!todayBanner) return;
    todayBanner.hidden = !bannerEvent;
    if (!bannerEvent) return;
    const { card, label } = bannerEvent;
    const venue = card.querySelector(".event-details dd b");
    todayBanner.href = `#${card.id}`;
    document.getElementById("today-badge").textContent = t(label);
    document.getElementById("today-name").textContent = card.querySelector("h4").textContent;
    document.getElementById("today-detail").textContent =
      `${card.querySelector(".event-time").textContent} · ${venue ? venue.textContent : ""}`;
  }

  if (eventCards.length) {
    updateEventStatus();
    window.setInterval(updateEventStatus, 60000);
    languageListeners.push(updateEventStatus);
  }

  // Share: the phone's share sheet where available, otherwise WhatsApp, otherwise copy the link.
  const shareElement = document.getElementById("share-data");
  const shareData = shareElement ? JSON.parse(shareElement.textContent) : {};
  const toast = document.getElementById("toast");
  let toastTimer = null;

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => { toast.hidden = true; }, 3500);
  }

  async function shareInvitation() {
    const text = shareData[lang] || shareData.en;
    if (navigator.share) {
      try {
        await navigator.share({ title: shareData.title, text, url: shareData.url });
        return;
      } catch (error) {
        if (error.name === "AbortError") return; // The guest closed the share sheet.
      }
    }
    if (/Android|iPhone|iPad|iPod/.test(navigator.userAgent)) {
      window.location.href = `https://wa.me/?text=${encodeURIComponent(`${text} ${shareData.url}`)}`;
      return;
    }
    try {
      await navigator.clipboard.writeText(`${text} ${shareData.url}`);
      showToast(t("linkCopied"));
    } catch (error) {
      window.open(`https://wa.me/?text=${encodeURIComponent(`${text} ${shareData.url}`)}`, "_blank", "noopener");
    }
  }

  document.querySelectorAll(".share-button").forEach((button) => button.addEventListener("click", shareInvitation));

  // Highlight the bottom-bar item for the section on screen.
  const bottomLinks = Array.from(document.querySelectorAll(".bottom-nav a[data-section]"));
  if (bottomLinks.length) {
    const sectionIds = { celebrations: "celebrations", "getting-there": "getting-there", memories: "memories", photos: "memories", wishes: "wishes" };
    const sections = Array.from(document.querySelectorAll("main > section[id]"));
    const updateActive = () => {
      const middle = window.innerHeight / 2;
      const current = sections.find((section) => {
        const rect = section.getBoundingClientRect();
        return rect.top <= middle && rect.bottom > middle;
      });
      const active = current ? sectionIds[current.id] : null;
      bottomLinks.forEach((link) => link.classList.toggle("active", link.dataset.section === active));
    };
    window.addEventListener("scroll", updateActive, { passive: true });
    updateActive();
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
    document.getElementById("lightbox-count").textContent =
      lightboxItems.length > 1 ? `${lightboxIndex + 1} / ${lightboxItems.length}` : "";
  }

  function openLightbox(items, index, trigger) {
    if (!lightbox || !items.length) return;
    lightboxItems = items;
    lightboxReturnFocus = trigger;
    lightbox.hidden = false;
    document.body.classList.add("lightbox-open");
    showLightboxItem(index);
    lightboxClose.focus();
    // A history entry lets the phone's Back button close the photo instead of leaving the site.
    try { history.pushState({ lightbox: true }, ""); } catch (error) { /* history unavailable */ }
  }

  function hideLightbox() {
    lightbox.hidden = true;
    document.body.classList.remove("lightbox-open");
    lightboxImage.removeAttribute("src");
    if (lightboxReturnFocus) lightboxReturnFocus.focus();
  }

  function closeLightbox() {
    if (history.state && history.state.lightbox) history.back(); // popstate below hides it
    else hideLightbox();
  }

  window.addEventListener("popstate", () => {
    if (lightbox && !lightbox.hidden) hideLightbox();
  });

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
  window.inviteReady = true; // Set last, so any earlier error falls back to the plain page.
})();
