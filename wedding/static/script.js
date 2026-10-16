(() => {
  // Pre-wedding, engagement, and wedding photos are loaded from Google Drive.
  const driveCategory = document.getElementById("drive-category");
  const drivePhotos = document.getElementById("drive-photo-grid");
  const driveStatus = document.getElementById("drive-gallery-status");
  const uploadCategory = document.getElementById("drive-upload-category");

  async function loadDrivePhotos() {
    if (!driveCategory || !drivePhotos || !driveStatus) return;

    const category = driveCategory.value;
    if (uploadCategory) uploadCategory.value = category;
    drivePhotos.replaceChildren();
    driveStatus.textContent = "Loading photos…";

    try {
      const response = await fetch(`/api/drive/photos/${encodeURIComponent(category)}`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not load Google Drive photos.");

      const photos = result.photos || [];
      if (photos.length === 0) {
        driveStatus.textContent = "No photos have been added to this album yet.";
        return;
      }

      driveStatus.textContent = `${photos.length} photo${photos.length === 1 ? "" : "s"}`;
      photos.forEach((photo) => {
        const card = document.createElement("article");
        card.className = "drive-photo-card";
        const image = document.createElement("img");
        image.src = photo.url;
        image.alt = photo.name || "Wedding memory";
        image.loading = "lazy";
        const caption = document.createElement("p");
        caption.textContent = photo.name || "Wedding memory";
        card.append(image, caption);
        drivePhotos.append(card);
      });
    } catch (error) {
      driveStatus.textContent = error.message || "Could not load Google Drive photos.";
      const message = document.createElement("p");
      message.className = "drive-empty-state";
      message.textContent = driveStatus.textContent;
      drivePhotos.replaceChildren(message);
    }
  }

  driveCategory?.addEventListener("change", loadDrivePhotos);
  loadDrivePhotos();

  // Countdown to the wedding; event navigation and gallery work without a backend.
  const countdown = document.getElementById("countdown");
  if (countdown) {
    const target = new Date(countdown.dataset.date).getTime();
    const fields = {
      days: document.getElementById("days"),
      hours: document.getElementById("hours"),
      minutes: document.getElementById("minutes"),
      seconds: document.getElementById("seconds"),
    };
    function updateCountdown() {
      let remaining = target - Date.now();
      if (!Number.isFinite(target) || remaining <= 0) {
        Object.values(fields).forEach((node) => node.textContent = "0");
        return;
      }
      fields.days.textContent = Math.floor(remaining / 86400000);
      fields.hours.textContent = Math.floor((remaining % 86400000) / 3600000);
      fields.minutes.textContent = Math.floor((remaining % 3600000) / 60000);
      fields.seconds.textContent = Math.floor((remaining % 60000) / 1000);
    }
    updateCountdown();
    window.setInterval(updateCountdown, 1000);
  }

  // Envelope opening: reveal the invitation and send the guest to the details.
  const openButton = document.getElementById("open-invite");
  if (openButton) {
    openButton.addEventListener("click", () => {
      document.body.classList.add("invitation-open");
      openButton.setAttribute("aria-expanded", "true");
      const label = document.getElementById("open-label");
      if (label) label.textContent = "Your invitation is open";
      window.setTimeout(() => {
        document.getElementById("our-story")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
      }, 450);
    });
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Clickable event timeline: update selected tab and the matching detail panel.
  const tabs = Array.from(document.querySelectorAll(".event-tab"));
  const panels = Array.from(document.querySelectorAll(".event-panel"));
  function selectEvent(id) {
    tabs.forEach((tab) => {
      const selected = tab.dataset.event === id;
      tab.classList.toggle("active", selected);
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    panels.forEach((panel) => {
      const selected = panel.id === `panel-${id}`;
      panel.hidden = !selected;
      panel.classList.toggle("active", selected);
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectEvent(tab.dataset.event));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft"].includes(event.key)) return;
      event.preventDefault();
      const nextIndex = (index + (["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1) + tabs.length) % tabs.length;
      tabs[nextIndex].focus();
      selectEvent(tabs[nextIndex].dataset.event);
    });
  });
  if (tabs.length) tabs.forEach((tab, i) => tab.tabIndex = i === 0 ? 0 : -1);

  // Photo gallery. If a file hasn't been added yet, show the designed placeholder.
  const memories = [
    { title: "A little bit of magic", text: "Replace this card with one of your favourite couple photos.", image: "/static/images/couple-1.JPG", file: "couple-1.JPG" },
    { title: "Our favourite memories", text: "Add a candid, a favourite trip, or a special moment.", image: "/static/images/couple-2.JPG", file: "couple-2.JPG" },
    { title: "The beginning of forever", text: "One more photo to make this invitation yours.", image: "/static/images/couple-3.JPG", file: "couple-3.JPG" },
  ];
  let currentMemory = 0;
  const img = document.getElementById("gallery-image");
  const placeholder = document.getElementById("photo-placeholder");
  const prev = document.getElementById("gallery-prev");
  const next = document.getElementById("gallery-next");
  const dots = Array.from(document.querySelectorAll("#gallery-dots button"));
  function showMemory(index) {
    currentMemory = Math.max(0, Math.min(memories.length - 1, index));
    const item = memories[currentMemory];
    document.getElementById("memory-title").textContent = item.title;
    document.getElementById("memory-text").textContent = item.text;
    document.getElementById("memory-index").textContent = `${String(currentMemory + 1).padStart(2, "0")} / ${String(memories.length).padStart(2, "0")}`;
    img.classList.remove("loaded");
    placeholder.hidden = false;
    placeholder.querySelector("small").textContent = `Add ${item.file} to static/images`;
    img.onload = () => { img.classList.add("loaded"); placeholder.hidden = true; };
    img.onerror = () => { img.classList.remove("loaded"); placeholder.hidden = false; };
    img.src = item.image;
    prev.disabled = currentMemory === 0;
    next.disabled = currentMemory === memories.length - 1;
    dots.forEach((dot, i) => dot.classList.toggle("active", i === currentMemory));
  }
  prev?.addEventListener("click", () => showMemory(currentMemory - 1));
  next?.addEventListener("click", () => showMemory(currentMemory + 1));
  dots.forEach((dot) => dot.addEventListener("click", () => showMemory(Number(dot.dataset.index))));
  if (img) showMemory(0);

  // Optional music toggle. Add static/music.mp3 to enable it; otherwise give a clear message.

  /* Wedding background music */
  const musicButton = document.getElementById("music-toggle");
  const musicLabel = document.getElementById("music-label");

  const audio = new Audio("/static/music.mp3");
  audio.loop = true;
  audio.volume = 0.3;
  audio.preload = "auto";

  let musicStarted = false;

  function updateMusicButton() {
    const playing = !audio.paused;

    musicButton.setAttribute("aria-pressed", String(playing));
    musicLabel.textContent = playing ? "Music on" : "Music off";
    musicButton.title = playing ? "Turn music off" : "Turn music on";
  }

  async function startMusic() {
    try {
      await audio.play();
      musicStarted = true;
      updateMusicButton();
    } catch (error) {
      // The browser may require a user interaction first.
      updateMusicButton();
    }
  }

  // Try to start music when the page loads.
  startMusic();

  // Start or stop music using the visible button.
  musicButton.addEventListener("click", async () => {
    if (audio.paused) {
      await startMusic();
    } else {
      audio.pause();
      updateMusicButton();
    }
  });

  // The invitation-opening click is also a user gesture.
  // This is a reliable opportunity to start playback.
  document.getElementById("open-invite")
    ?.addEventListener("click", () => {
      if (!musicStarted) {
        startMusic();
      }
    });

  audio.addEventListener("play", updateMusicButton);
  audio.addEventListener("pause", updateMusicButton);


  // Subtle falling petals. Respects reduced-motion preferences.
  const petalLayer = document.getElementById("petal-layer");
  if (petalLayer && !reducedMotion) {
    const symbols = ["✿", "❀", "✽"];
    let count = 0;
    function dropPetal() {
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
    }
    window.setInterval(dropPetal, 1500);
  }
})();
