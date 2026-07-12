(() => {
  "use strict";

  const STORAGE_KEY = "aio-workstation-preferences-v1";
  const viewCommands = [
    ["overview", "Overview", "Decision queue, market map, and setup radar", "Alt+1"],
    ["compare", "Compare sectors", "Relative performance and benchmark comparison", "Alt+2"],
    ["sector", "Sector explorer", "Sector constituents, ranks, and diagnostics", "Alt+3"],
    ["tickers", "Candidate ranker", "MRR ranking, distribution, and metric controls", "Alt+4"],
    ["portfolio-review", "Portfolio review", "Portfolio-level analysis and recommendations", "Alt+5"],
    ["setup", "Run & Universe", "Analysis dates, refresh controls, and ticker intake", "Alt+6"],
    ["data", "Data coverage", "Source health, QA warnings, and provenance", "Alt+7"],
  ];

  function readDashboardData() {
    try {
      return JSON.parse(document.getElementById("dashboard-data")?.textContent || "{}");
    } catch {
      return {};
    }
  }

  function readPreferences() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch {
      return {};
    }
  }

  function writePreferences(update) {
    const next = { ...readPreferences(), ...update };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // The workstation remains fully usable when storage is unavailable.
    }
  }

  function activateView(view) {
    const target = document.querySelector(`.nav [data-action="view"][data-view="${view}"]`);
    if (target instanceof HTMLButtonElement) target.click();
  }

  function activateLens(lens) {
    const target = document.querySelector(`[data-action="lens"][data-lens="${lens}"]`);
    if (target instanceof HTMLButtonElement) target.click();
  }

  function createStatusStrip(data) {
    const nav = document.querySelector(".nav");
    if (!nav || document.querySelector(".workspace-strip")) return;

    const tickerCount = Array.isArray(data.tickers) ? data.tickers.length : "—";
    const sectorCount = Array.isArray(data.metrics) ? data.metrics.length : "—";
    const endDate = data.methodology?.endDate || "unknown";
    const qaStatus = data.qa?.status || "unknown";
    const strip = document.createElement("div");
    strip.className = "workspace-strip";
    strip.innerHTML = `
      <div class="workspace-strip__group" aria-label="Workspace status">
        <span class="runtime-badge"><i></i>LOCAL ANALYTICS</span>
        <span><b>DATA</b>${endDate}</span>
        <span><b>UNIVERSE</b>${tickerCount} tickers</span>
        <span><b>SECTORS</b>${sectorCount}</span>
        <span class="qa-inline ${String(qaStatus).toLowerCase()}"><b>QA</b>${qaStatus}</span>
      </div>
      <button class="command-trigger" type="button" aria-label="Open workspace command menu">
        <span>Navigate workspace</span><kbd>⌘ K</kbd>
      </button>
    `;
    nav.insertAdjacentElement("afterend", strip);
  }

  function createCommandMenu(commands) {
    const overlay = document.createElement("div");
    overlay.className = "command-overlay";
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="command-dialog" role="dialog" aria-modal="true" aria-label="Workspace command menu">
        <div class="command-search">
          <span class="command-search__glyph">⌘</span>
          <input type="search" autocomplete="off" spellcheck="false" placeholder="Navigate, change lens, or find a workspace…" aria-label="Search workspace commands">
          <kbd>ESC</kbd>
        </div>
        <div class="command-results" role="listbox"></div>
        <div class="command-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> select</span>
          <span><kbd>↵</kbd> open</span>
          <span><kbd>Alt</kbd><kbd>1–7</kbd> direct navigation</span>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const input = overlay.querySelector("input");
    const results = overlay.querySelector(".command-results");
    let visible = commands;
    let selected = 0;

    function renderResults() {
      results.innerHTML = visible.length
        ? visible.map((command, index) => `
            <button type="button" class="command-item ${index === selected ? "selected" : ""}" data-command-index="${index}" role="option" aria-selected="${index === selected}">
              <span class="command-item__icon">${command.icon}</span>
              <span class="command-item__copy"><strong>${command.label}</strong><small>${command.description}</small></span>
              ${command.shortcut ? `<kbd>${command.shortcut}</kbd>` : ""}
            </button>
          `).join("")
        : '<div class="command-empty">No matching workspace command</div>';
    }

    function filterResults() {
      const query = input.value.trim().toLowerCase();
      visible = query
        ? commands.filter(command => `${command.label} ${command.description} ${command.keywords}`.toLowerCase().includes(query))
        : commands;
      selected = 0;
      renderResults();
    }

    function close() {
      overlay.hidden = true;
      document.body.classList.remove("command-open");
      input.value = "";
      filterResults();
    }

    function open() {
      overlay.hidden = false;
      document.body.classList.add("command-open");
      filterResults();
      requestAnimationFrame(() => input.focus());
    }

    function runSelected(index = selected) {
      const command = visible[index];
      if (!command) return;
      close();
      command.run();
    }

    input.addEventListener("input", filterResults);
    input.addEventListener("keydown", event => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        selected = Math.min(selected + 1, visible.length - 1);
        renderResults();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        selected = Math.max(selected - 1, 0);
        renderResults();
      } else if (event.key === "Enter") {
        event.preventDefault();
        runSelected();
      } else if (event.key === "Escape") {
        close();
      }
    });
    results.addEventListener("click", event => {
      const item = event.target.closest("[data-command-index]");
      if (item) runSelected(Number(item.dataset.commandIndex));
    });
    overlay.addEventListener("click", event => {
      if (event.target === overlay) close();
    });
    document.querySelector(".command-trigger")?.addEventListener("click", open);

    return { open, close };
  }

  function createToastRegion() {
    const region = document.createElement("div");
    region.className = "workspace-toast";
    region.setAttribute("aria-live", "polite");
    document.body.appendChild(region);
    let timeout;
    return message => {
      region.textContent = message;
      region.classList.add("show");
      window.clearTimeout(timeout);
      timeout = window.setTimeout(() => region.classList.remove("show"), 1600);
    };
  }

  function installActionGuards(toast) {
    const overlay = document.createElement("div");
    overlay.className = "action-overlay";
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="action-dialog" role="alertdialog" aria-modal="true" aria-labelledby="action-dialog-title" aria-describedby="action-dialog-copy">
        <div class="action-dialog__eyebrow">CONFIRM WRITE ACTION</div>
        <h2 id="action-dialog-title"></h2>
        <p id="action-dialog-copy"></p>
        <div class="action-dialog__impact"></div>
        <div class="action-dialog__buttons">
          <button type="button" class="small-btn action-cancel">Cancel</button>
          <button type="button" class="primary-btn action-confirm"></button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const title = overlay.querySelector("#action-dialog-title");
    const copy = overlay.querySelector("#action-dialog-copy");
    const impact = overlay.querySelector(".action-dialog__impact");
    const cancel = overlay.querySelector(".action-cancel");
    const confirm = overlay.querySelector(".action-confirm");
    let pendingTarget = null;

    function refreshOptions() {
      const labels = Array.from(document.querySelectorAll('[data-action="toggle-refresh"].active'))
        .map(button => button.textContent.trim())
        .filter(Boolean);
      return labels.length ? labels.join(", ") : "Automatic freshness checks only";
    }

    const guardDetails = {
      "setup-run": () => ({
        title: "Run the full analysis pipeline?",
        copy: "This rebuilds the bundled market universe and publishes new local analysis outputs.",
        impact: `Start date: ${document.getElementById("setup-start-date")?.value || "configured value"} · Refresh: ${refreshOptions()}`,
        confirm: "Run Full Analysis",
      }),
      "setup-save-start": () => ({
        title: "Change the analysis start date?",
        copy: "This updates the local methodology configuration. The new date takes effect on the next full analysis run.",
        impact: `New start date: ${document.getElementById("setup-start-date")?.value || "not set"}`,
        confirm: "Save Start Date",
      }),
      "setup-add": target => ({
        title: `Add ${target.dataset.ticker || "this ticker"} to the basket?`,
        copy: "This changes the local basket configuration. A later full analysis run will publish updated rankings.",
        impact: "Configuration write · No analysis run is started automatically",
        confirm: "Add Ticker",
      }),
      "setup-remove": target => ({
        title: `Remove ${target.dataset.ticker || "this ticker"} from the basket?`,
        copy: "This changes the local basket configuration. Existing published outputs remain until the next full analysis run.",
        impact: "Configuration write · Existing analysis remains available",
        confirm: "Remove Ticker",
      }),
      "intake-add": () => ({
        title: "Add the selected ticker classifications?",
        copy: "Selected intake rows will be written into their approved local basket configurations.",
        impact: "Configuration write · Review selected rows before continuing",
        confirm: "Add Selected",
      }),
      "portfolio-review-run": () => ({
        title: "Run the portfolio review?",
        copy: "This creates a new local portfolio-review result using the current inputs and refresh settings.",
        impact: "Creates local review output · Does not place trades",
        confirm: "Run Portfolio Review",
      }),
      "portfolio-import-csv": () => ({
        title: "Import this portfolio CSV?",
        copy: "The pasted holdings will be parsed and stored as a local portfolio input for review.",
        impact: "Creates a local portfolio input · Does not contact a broker",
        confirm: "Import Portfolio",
      }),
    };

    function close() {
      overlay.hidden = true;
      pendingTarget = null;
    }

    function open(target, details) {
      pendingTarget = target;
      title.textContent = details.title;
      copy.textContent = details.copy;
      impact.textContent = details.impact;
      confirm.textContent = details.confirm;
      overlay.hidden = false;
      requestAnimationFrame(() => cancel.focus());
    }

    document.addEventListener("click", event => {
      const target = event.target.closest("[data-action]");
      const detailFactory = target && guardDetails[target.dataset.action];
      if (!detailFactory) return;
      if (target.dataset.actionConfirmed === "true") {
        delete target.dataset.actionConfirmed;
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      open(target, detailFactory(target));
    }, true);

    cancel.addEventListener("click", close);
    confirm.addEventListener("click", () => {
      const target = pendingTarget;
      const message = confirm.textContent;
      close();
      if (!target) return;
      target.dataset.actionConfirmed = "true";
      target.click();
      toast(`${message} started`);
    });
    overlay.addEventListener("click", event => {
      if (event.target === overlay) close();
    });
    document.addEventListener("keydown", event => {
      if (!overlay.hidden && event.key === "Escape") close();
    });
  }

  function initialize() {
    const data = readDashboardData();
    createStatusStrip(data);
    const toast = createToastRegion();
    installActionGuards(toast);

    const commands = viewCommands.map(([view, label, description, shortcut], index) => ({
      icon: String(index + 1).padStart(2, "0"),
      label,
      description,
      shortcut,
      keywords: `page view screen ${view}`,
      run: () => {
        activateView(view);
        toast(`${label} opened`);
      },
    }));
    [
      ["balanced", "Balanced lens", "Blend leadership, risk, sponsorship, and quality"],
      ["leadership", "Leadership lens", "Emphasize absolute and recent performance"],
      ["rebound", "Rebound lens", "Find recovering groups near prior highs"],
      ["squeeze", "Squeeze lens", "Emphasize short positioning and volatility"],
      ["sponsor", "Sponsor lens", "Emphasize institutional ownership changes"],
      ["quality", "Quality lens", "Emphasize cash generation and operating quality"],
      ["torque", "Torque lens", "Emphasize rebound potential and volatility"],
    ].forEach(([lens, label, description]) => commands.push({
      icon: "L",
      label,
      description,
      shortcut: "",
      keywords: `capital lens ${lens}`,
      run: () => {
        activateView("overview");
        requestAnimationFrame(() => activateLens(lens));
        toast(`${label} applied`);
      },
    }));

    const menu = createCommandMenu(commands);
    document.addEventListener("keydown", event => {
      const target = event.target;
      const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        menu.open();
        return;
      }
      if (!typing && event.altKey && /^[1-7]$/.test(event.key)) {
        event.preventDefault();
        const command = commands[Number(event.key) - 1];
        command?.run();
      }
    });

    document.addEventListener("click", event => {
      const view = event.target.closest('[data-action="view"][data-view]');
      if (view) writePreferences({ view: view.dataset.view });
      const lens = event.target.closest('[data-action="lens"][data-lens]');
      if (lens) writePreferences({ lens: lens.dataset.lens });
    }, true);

    viewCommands.forEach(([view, , , shortcut]) => {
      const button = document.querySelector(`.nav [data-view="${view}"]`);
      if (button) button.title = shortcut;
    });

    const preferences = readPreferences();
    if (preferences.view && viewCommands.some(([view]) => view === preferences.view)) {
      activateView(preferences.view);
    }
    if (preferences.lens) {
      requestAnimationFrame(() => activateLens(preferences.lens));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
