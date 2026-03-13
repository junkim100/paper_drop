/* ============================================
   Paper Drop — App JS
   Vanilla JS, no dependencies
   ============================================ */

(function () {
  "use strict";

  // --- Config ---
  const BASE_PATH = getBasePath();
  const SPEEDS = [0.75, 1, 1.25, 1.5, 2];
  const KEEP_STORAGE_KEY = "paper_drop_kept";

  function getBasePath() {
    const path = window.location.pathname;
    if (path.includes("/paper_drop")) {
      return "/paper_drop/";
    }
    return "/";
  }

  // --- State ---
  let currentAudio = null;
  let currentPlayBtn = null;
  let keptItems = loadKept();

  // --- Theme ---
  function initTheme() {
    const saved = localStorage.getItem("paper_drop_theme");
    if (saved) {
      document.documentElement.setAttribute("data-theme", saved);
    }
    document.getElementById("theme-toggle").addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme");
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("paper_drop_theme", next);
    });
  }

  // --- Tabs ---
  function initTabs() {
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => {
          b.classList.remove("active");
          b.setAttribute("aria-selected", "false");
        });
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        btn.setAttribute("aria-selected", "true");
        document.getElementById(btn.dataset.tab).classList.add("active");
      });
    });
  }

  // --- Keep Checkbox ---
  function loadKept() {
    try {
      return JSON.parse(localStorage.getItem(KEEP_STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveKept() {
    localStorage.setItem(KEEP_STORAGE_KEY, JSON.stringify(keptItems));
  }

  function toggleKeep(id, checked) {
    if (checked && !keptItems.includes(id)) {
      keptItems.push(id);
    } else if (!checked) {
      keptItems = keptItems.filter((k) => k !== id);
    }
    saveKept();
    const entry = document.querySelector(`[data-keep-id="${id}"]`);
    if (entry) {
      entry.classList.toggle("kept", checked);
    }
  }

  function isKept(id) {
    return keptItems.includes(id);
  }

  // --- Markdown Rendering (lightweight) ---
  function renderMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);

    // Headings
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

    // Bold and italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

    // Inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Links
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>'
    );

    // Blockquotes
    html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");

    // Horizontal rules
    html = html.replace(/^---$/gm, "<hr>");

    // Unordered lists
    html = html.replace(/^[\-\*] (.+)$/gm, "<li>$1</li>");
    html = html.replace(/((<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");

    // Paragraphs
    html = html
      .split("\n\n")
      .map((block) => {
        block = block.trim();
        if (!block) return "";
        if (/^<[houb]/.test(block) || /^<li/.test(block)) return block;
        return `<p>${block.replace(/\n/g, "<br>")}</p>`;
      })
      .join("\n");

    return html;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // --- Time Formatting ---
  function formatTime(seconds) {
    if (isNaN(seconds) || !isFinite(seconds)) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  function formatDate(dateStr) {
    const date = new Date(dateStr + "T00:00:00");
    return date.toLocaleDateString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }

  // --- Audio Player ---
  function createAudioPlayer(paper, dropType, date) {
    const container = document.createElement("div");
    container.className = "audio-player";

    const audioSrc = BASE_PATH + paper.audio;

    container.innerHTML = `
      <div class="player-controls">
        <button class="play-btn" aria-label="Play">
          <span class="play-icon-play">&#9654;</span>
          <span class="play-icon-pause">&#10074;&#10074;</span>
        </button>
        <div class="player-track-area">
          <div class="player-progress-bar">
            <div class="player-progress-fill"></div>
          </div>
          <div class="player-time-row">
            <span class="player-current">0:00</span>
            <span class="player-duration">0:00</span>
          </div>
        </div>
        <button class="speed-btn" aria-label="Playback speed">1x</button>
      </div>
    `;

    const playBtn = container.querySelector(".play-btn");
    const progressBar = container.querySelector(".player-progress-bar");
    const progressFill = container.querySelector(".player-progress-fill");
    const currentTime = container.querySelector(".player-current");
    const durationEl = container.querySelector(".player-duration");
    const speedBtn = container.querySelector(".speed-btn");

    let speedIndex = 1; // default 1x
    let audio = null;

    function getOrCreateAudio() {
      if (!audio) {
        audio = new Audio(audioSrc);
        audio.preload = "metadata";
        audio.playbackRate = SPEEDS[speedIndex];

        audio.addEventListener("loadedmetadata", () => {
          durationEl.textContent = formatTime(audio.duration);
        });

        audio.addEventListener("timeupdate", () => {
          if (audio.duration) {
            const pct = (audio.currentTime / audio.duration) * 100;
            progressFill.style.width = pct + "%";
            currentTime.textContent = formatTime(audio.currentTime);
          }
        });

        audio.addEventListener("ended", () => {
          playBtn.classList.remove("playing");
          playBtn.setAttribute("aria-label", "Play");
          progressFill.style.width = "0%";
          currentTime.textContent = "0:00";
          audio.currentTime = 0;
          if (currentAudio === audio) {
            currentAudio = null;
            currentPlayBtn = null;
          }
        });
      }
      return audio;
    }

    playBtn.addEventListener("click", () => {
      const a = getOrCreateAudio();

      // Stop any other playing audio
      if (currentAudio && currentAudio !== a) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        if (currentPlayBtn) currentPlayBtn.classList.remove("playing");
      }

      if (a.paused) {
        a.play().then(() => {
          playBtn.classList.add("playing");
          playBtn.setAttribute("aria-label", "Pause");
          currentAudio = a;
          currentPlayBtn = playBtn;
          updateMediaSession(paper.title);
        }).catch(() => {});
      } else {
        a.pause();
        playBtn.classList.remove("playing");
        playBtn.setAttribute("aria-label", "Play");
      }
    });

    progressBar.addEventListener("click", (e) => {
      const a = getOrCreateAudio();
      if (a.duration) {
        const rect = progressBar.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        a.currentTime = pct * a.duration;
      }
    });

    speedBtn.addEventListener("click", () => {
      speedIndex = (speedIndex + 1) % SPEEDS.length;
      const speed = SPEEDS[speedIndex];
      speedBtn.textContent = speed + "x";
      if (audio) {
        audio.playbackRate = speed;
      }
    });

    return container;
  }

  // --- Media Session API ---
  function updateMediaSession(title) {
    if ("mediaSession" in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: title,
        artist: "Paper Drop",
        album: "Daily AI Paper Digest",
      });

      navigator.mediaSession.setActionHandler("play", () => {
        if (currentAudio) {
          currentAudio.play();
          if (currentPlayBtn) currentPlayBtn.classList.add("playing");
        }
      });
      navigator.mediaSession.setActionHandler("pause", () => {
        if (currentAudio) {
          currentAudio.pause();
          if (currentPlayBtn) currentPlayBtn.classList.remove("playing");
        }
      });
      navigator.mediaSession.setActionHandler("seekbackward", () => {
        if (currentAudio) currentAudio.currentTime = Math.max(0, currentAudio.currentTime - 10);
      });
      navigator.mediaSession.setActionHandler("seekforward", () => {
        if (currentAudio) currentAudio.currentTime = Math.min(currentAudio.duration, currentAudio.currentTime + 10);
      });
    }
  }

  // --- Script Dropdown ---
  function createScriptDropdown(paper) {
    const container = document.createElement("div");
    container.className = "script-toggle";

    const btn = document.createElement("button");
    btn.className = "script-btn";
    btn.innerHTML = `<span class="script-chevron">▶</span> View Script`;

    const content = document.createElement("div");
    content.className = "script-content";
    content.textContent = "Loading...";

    let loaded = false;

    btn.addEventListener("click", () => {
      container.classList.toggle("open");
      if (!loaded) {
        loaded = true;
        fetch(BASE_PATH + paper.script)
          .then((r) => {
            if (!r.ok) throw new Error("Not found");
            return r.text();
          })
          .then((text) => {
            content.textContent = text;
          })
          .catch(() => {
            content.textContent = "Script not available.";
          });
      }
    });

    container.appendChild(btn);
    container.appendChild(content);
    return container;
  }

  // --- Age Check ---
  function isOlderThanDays(dateStr, days) {
    const entryDate = new Date(dateStr + "T00:00:00");
    const now = new Date();
    const diffMs = now - entryDate;
    return diffMs > days * 24 * 60 * 60 * 1000;
  }

  // --- Render Paper Entry ---
  function renderPaperEntry(paper, dropType, date) {
    const keepId = `${dropType}-${date}-${paper.number}`;
    const kept = isKept(keepId);
    const expired = isOlderThanDays(date, 10);

    const entry = document.createElement("div");
    entry.className = "paper-entry" + (kept ? " kept" : "");
    entry.dataset.keepId = keepId;

    const header = document.createElement("div");
    header.className = "paper-header";

    let actionHtml;
    if (expired && kept) {
      // Kept but past 10 days: show delete button only
      actionHtml = `
        <div class="keep-toggle">
          <button class="delete-btn" data-keep-id="${keepId}" aria-label="Delete">
            <span>🗑️</span>
            <span>Delete</span>
          </button>
        </div>
      `;
    } else if (!expired) {
      // Within 10 days: show keep checkbox
      actionHtml = `
        <div class="keep-toggle">
          <input type="checkbox" class="keep-checkbox" id="keep-${keepId}" ${kept ? "checked" : ""}>
          <label class="keep-label" for="keep-${keepId}">
            <span class="keep-star">⭐</span>
            <span>Keep</span>
          </label>
        </div>
      `;
    } else {
      // Expired and not kept: no action (shouldn't normally appear, but just in case)
      actionHtml = "";
    }

    header.innerHTML = `
      <span class="paper-number">#${paper.number}</span>
      <div class="paper-info">
        <div class="paper-title">${escapeHtml(paper.title)}</div>
        ${paper.headline ? `<div class="paper-headline">${escapeHtml(paper.headline)}</div>` : ""}
      </div>
      ${actionHtml}
    `;

    const checkbox = header.querySelector(".keep-checkbox");
    if (checkbox) {
      checkbox.addEventListener("change", () => {
        toggleKeep(keepId, checkbox.checked);
      });
    }

    const deleteBtn = header.querySelector(".delete-btn");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", () => {
        toggleKeep(keepId, false);
        // Remove the entire day card if no more kept items in it
        entry.remove();
      });
    }

    entry.appendChild(header);

    // Only show audio player if the file actually exists
    if (paper.audio) {
      const audioUrl = BASE_PATH + paper.audio;
      fetch(audioUrl, { method: "HEAD" }).then((r) => {
        if (r.ok) {
          entry.appendChild(createAudioPlayer(paper, dropType, date));
        }
      }).catch(() => {});
    }

    // Only show script dropdown if the file actually exists
    if (paper.script) {
      const scriptUrl = BASE_PATH + paper.script;
      fetch(scriptUrl, { method: "HEAD" }).then((r) => {
        if (r.ok) {
          // Insert after audio player if it exists, otherwise after header
          entry.appendChild(createScriptDropdown(paper));
        }
      }).catch(() => {});
    }

    return entry;
  }

  // --- Render Day Card ---
  function renderDayCard(drop, dropType) {
    const card = document.createElement("div");
    card.className = "day-card";

    const header = document.createElement("div");
    header.className = "day-header";
    header.innerHTML = `
      <span class="day-date">${formatDate(drop.date)}</span>
      <span class="day-paper-count">${drop.papers.length} paper${drop.papers.length !== 1 ? "s" : ""}</span>
    `;
    card.appendChild(header);

    if (drop.markdown) {
      const digest = document.createElement("div");
      digest.className = "day-digest";
      const mdContent = document.createElement("div");
      mdContent.className = "markdown-content";
      mdContent.innerHTML = renderMarkdown(drop.markdown);
      digest.appendChild(mdContent);
      card.appendChild(digest);
    }

    drop.papers.forEach((paper) => {
      card.appendChild(renderPaperEntry(paper, dropType, drop.date));
    });

    return card;
  }

  // --- Load Data ---
  async function loadDrops(type) {
    const listEl = document.getElementById(`${type}-list`);
    try {
      const resp = await fetch(`${BASE_PATH}data/${type.replace("-", "_")}s.json`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const drops = await resp.json();

      listEl.innerHTML = "";

      if (!drops || drops.length === 0) {
        listEl.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <p>No drops yet. Check back soon!</p>
          </div>
        `;
        return;
      }

      // Sort newest first
      drops.sort((a, b) => b.date.localeCompare(a.date));

      drops.forEach((drop) => {
        listEl.appendChild(renderDayCard(drop, type));
      });
    } catch (err) {
      listEl.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📭</div>
          <p>No drops yet. Check back soon!</p>
        </div>
      `;
    }
  }

  // --- Init ---
  function init() {
    initTheme();
    initTabs();
    loadDrops("paper-drop");
    loadDrops("eval-drop");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
