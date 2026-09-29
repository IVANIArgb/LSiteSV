/**
 * Страница /logs — текстовый вывод как в PyCharm, фильтр по типу [LEVEL]-CATEGORY.
 */
(function () {
  var PAGE_SIZE = 500;
  var AUTO_REFRESH_MS = 30000;
  var state = {
    offset: 0,
    total: 0,
    loading: false,
    autoTimer: null,
  };

  function el(id) {
    return document.getElementById(id);
  }

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  var LOG_LINE_RE =
    /^\[([A-Z]+)\]-([A-Z]+) \| (.+?) \| ([^ ]+) - (.*)$/;

  function highlightSearch(text, query) {
    var safe = escapeHtml(text);
    if (!query) return safe;
    var re = new RegExp("(" + query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
    return safe.replace(re, '<mark class="hl-search">$1</mark>');
  }

  function formatStructuredLine(line, search) {
    var m = LOG_LINE_RE.exec(line);
    if (!m) return null;
    return (
      '<span class="tok-bracket">[</span>' +
      '<span class="tok-level tok-level-' +
      m[1] +
      '">' +
      escapeHtml(m[1]) +
      "</span>" +
      '<span class="tok-bracket">]</span>' +
      '<span class="tok-sep">-</span>' +
      '<span class="tok-category tok-cat-' +
      m[2] +
      '">' +
      escapeHtml(m[2]) +
      "</span>" +
      '<span class="tok-pipe"> | </span>' +
      '<span class="tok-time">' +
      highlightSearch(m[3], search) +
      "</span>" +
      '<span class="tok-pipe"> | </span>' +
      '<span class="tok-logger">' +
      highlightSearch(m[4], search) +
      "</span>" +
      '<span class="tok-dash"> - </span>' +
      '<span class="tok-message">' +
      highlightSearch(m[5], search) +
      "</span>"
    );
  }

  function formatContinuationLine(line, level, search) {
    if (/^Traceback \(most recent call last\):/.test(line)) {
      return (
        '<span class="tok-traceback">' + highlightSearch(line, search) + "</span>"
      );
    }
    var fileMatch = line.match(/^(\s+File )(".*?")(, line .+)$/);
    if (fileMatch) {
      return (
        escapeHtml(fileMatch[1]) +
        '<span class="tok-string">' +
        highlightSearch(fileMatch[2], search) +
        "</span>" +
        '<span class="tok-line-no">' +
        highlightSearch(fileMatch[3], search) +
        "</span>"
      );
    }
    if (/^\s+\^/.test(line)) {
      return '<span class="tok-caret">' + highlightSearch(line, search) + "</span>";
    }
    if (/Error:|Exception:|Warning:/.test(line)) {
      return '<span class="tok-exception">' + highlightSearch(line, search) + "</span>";
    }
    if (/^\s+at /.test(line) || /^\s+in /.test(line)) {
      return '<span class="tok-stack">' + highlightSearch(line, search) + "</span>";
    }
    return '<span class="tok-cont">' + highlightSearch(line, search) + "</span>";
  }

  function formatLine(line, level, search) {
    var parsed = LOG_LINE_RE.exec(line);
    var structured = parsed ? formatStructuredLine(line, search) : null;
    var inner = structured || formatContinuationLine(line, level, search);
    var lineKind = structured ? "log-line--main" : "log-line--cont";
    var entryLevel = (parsed && parsed[1]) || level || "DEFAULT";
    return (
      '<span class="log-line ' +
      lineKind +
      " log-level-" +
      entryLevel +
      '" data-level="' +
      escapeHtml(entryLevel) +
      '">' +
      inner +
      "\n</span>"
    );
  }

  function setStatus(text, isError) {
    var node = el("logs-status");
    if (!node) return;
    node.textContent = text || "";
    node.classList.toggle("logs-status--error", !!isError);
  }

  function tagToLabel(tagKey) {
    var dash = tagKey.indexOf("-");
    if (dash === -1) return tagKey;
    return "[" + tagKey.slice(0, dash) + "]-" + tagKey.slice(dash + 1);
  }

  function checkedValues(containerId) {
    var root = el(containerId);
    if (!root) return [];
    return Array.prototype.slice
      .call(root.querySelectorAll('input[type="checkbox"]:checked'))
      .map(function (input) {
        return input.value;
      });
  }

  function updateFiltersFromStats(stats) {
    var root = el("logs-tags");
    if (!root) return;
    var byTag = (stats && stats.by_tag) || {};
    var selected = checkedValues("logs-tags");
    var keys = Object.keys(byTag).sort(function (a, b) {
      if (byTag[b] !== byTag[a]) return byTag[b] - byTag[a];
      return a.localeCompare(b);
    });
    if (!keys.length) {
      root.innerHTML = '<span class="logs-filter-empty">в файле нет записей</span>';
      return;
    }
    root.innerHTML = keys
      .map(function (key) {
        var checked = selected.indexOf(key) !== -1 ? " checked" : "";
        return (
          '<label class="logs-filter-chip">' +
          '<input type="checkbox" value="' +
          escapeHtml(key) +
          '"' +
          checked +
          " />" +
          "<code>" +
          escapeHtml(tagToLabel(key)) +
          "</code>" +
          '<span class="logs-filter-count">' +
          byTag[key] +
          "</span>" +
          "</label>"
        );
      })
      .join("");
  }

  function buildQueryParams() {
    var params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(state.offset));
    params.set("sort", (el("logs-sort") && el("logs-sort").value) || "time_desc");

    var file = el("logs-file") && el("logs-file").value;
    var search = el("logs-search") && el("logs-search").value.trim();
    if (file) params.set("file", file);
    if (search) params.set("search", search);

    checkedValues("logs-tags").forEach(function (value) {
      params.append("tags", value);
    });
    return params;
  }

  function updatePagination(data) {
    state.total = data.total || 0;
    var countEl = el("logs-count");
    var pageInfo = el("logs-page-info");
    var prevBtn = el("logs-prev");
    var nextBtn = el("logs-next");
    var from = state.total === 0 ? 0 : state.offset + 1;
    var to = Math.min(state.offset + PAGE_SIZE, state.total);
    if (countEl) countEl.textContent = "Строк записей: " + from + "–" + to + " из " + state.total;
    if (pageInfo) {
      var page = Math.floor(state.offset / PAGE_SIZE) + 1;
      var pages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
      pageInfo.textContent = "Стр. " + page + " / " + pages;
    }
    if (prevBtn) prevBtn.disabled = state.offset <= 0;
    if (nextBtn) nextBtn.disabled = state.offset + PAGE_SIZE >= state.total;
  }

  function renderEntries(entries) {
    var consoleNode = el("logs-console");
    if (!consoleNode) return;
    var search = (el("logs-search") && el("logs-search").value.trim()) || "";

    if (!entries || !entries.length) {
      consoleNode.innerHTML = '<span class="logs-empty">Записей не найдено</span>';
      return;
    }

    var html = "";
    entries.forEach(function (entry) {
      var lines = String(entry.raw || entry.message || "").split("\n");
      lines.forEach(function (line, idx) {
        if (!line && idx === lines.length - 1) return;
        html += formatLine(line, entry.level, search);
      });
    });
    consoleNode.innerHTML = html;
  }

  function populateFileSelect(files, current) {
    var select = el("logs-file");
    if (!select) return;
    var prev = select.value;
    select.innerHTML = "";
    (files || ["app.log"]).forEach(function (name) {
      var opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      select.appendChild(opt);
    });
    if (current && files && files.indexOf(current) !== -1) {
      select.value = current;
    } else if (prev && files && files.indexOf(prev) !== -1) {
      select.value = prev;
    }
  }

  async function loadLogs() {
    if (state.loading) return;
    state.loading = true;
    setStatus("Загрузка логов…", false);
    var refreshBtn = el("logs-refresh");
    if (refreshBtn) refreshBtn.disabled = true;

    try {
      var params = buildQueryParams();
      var resp = await fetch("/api/admin/logs?" + params.toString(), { credentials: "include" });
      var data = await resp.json().catch(function () {
        return {};
      });

      if (resp.status === 401) {
        setStatus("Войдите в систему с правами администратора.", true);
        renderEntries([]);
        return;
      }
      if (resp.status === 403) {
        setStatus("Доступ только для администраторов.", true);
        renderEntries([]);
        return;
      }
      if (!resp.ok) {
        setStatus((data && data.error) || "Не удалось загрузить логи.", true);
        return;
      }

      populateFileSelect(data.files, data.file);
      updateFiltersFromStats(data.stats);
      renderEntries(data.entries);
      updatePagination(data);

      var tags = checkedValues("logs-tags");
      var filterNote = "";
      if (tags.length) {
        filterNote = " · тип: " + tags.map(tagToLabel).join(", ");
      }
      setStatus("Файл: " + (data.file || "app.log") + filterNote, false);
    } catch (e) {
      setStatus("Ошибка сети при загрузке логов.", true);
    } finally {
      state.loading = false;
      if (refreshBtn) refreshBtn.disabled = false;
    }
  }

  function scheduleAutoRefresh() {
    if (state.autoTimer) {
      clearInterval(state.autoTimer);
      state.autoTimer = null;
    }
    var checkbox = el("logs-auto-refresh");
    if (checkbox && checkbox.checked) {
      state.autoTimer = setInterval(loadLogs, AUTO_REFRESH_MS);
    }
  }

  function clearFilters() {
    var root = el("logs-tags");
    if (root) {
      root.querySelectorAll('input[type="checkbox"]').forEach(function (input) {
        input.checked = false;
      });
    }
    state.offset = 0;
    loadLogs();
  }

  function bindCheckboxFilters(containerId) {
    var root = el(containerId);
    if (!root) return;
    root.addEventListener("change", function (e) {
      if (!e.target || e.target.type !== "checkbox") return;
      state.offset = 0;
      loadLogs();
    });
  }

  function bindEvents() {
    var refreshBtn = el("logs-refresh");
    if (refreshBtn) refreshBtn.addEventListener("click", loadLogs);

    ["logs-file", "logs-sort"].forEach(function (id) {
      var node = el(id);
      if (node) {
        node.addEventListener("change", function () {
          state.offset = 0;
          loadLogs();
        });
      }
    });

    bindCheckboxFilters("logs-tags");

    var clearBtn = el("logs-clear-filters");
    if (clearBtn) clearBtn.addEventListener("click", clearFilters);

    var search = el("logs-search");
    if (search) {
      var debounceTimer;
      search.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
          state.offset = 0;
          loadLogs();
        }, 350);
      });
    }

    var prevBtn = el("logs-prev");
    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        state.offset = Math.max(0, state.offset - PAGE_SIZE);
        loadLogs();
      });
    }

    var nextBtn = el("logs-next");
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        if (state.offset + PAGE_SIZE < state.total) {
          state.offset += PAGE_SIZE;
          loadLogs();
        }
      });
    }

    var autoCb = el("logs-auto-refresh");
    if (autoCb) autoCb.addEventListener("change", scheduleAutoRefresh);
  }

  function init() {
    bindEvents();
    loadLogs();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
