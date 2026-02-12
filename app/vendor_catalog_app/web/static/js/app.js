document.addEventListener("DOMContentLoaded", () => {
  const prettifyToken = (raw) =>
    String(raw || "")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, (m) => m.toUpperCase());

  const labelTextForControl = (control) => {
    if (!control) return "";
    if (control.id) {
      const byFor = document.querySelector(`label[for="${control.id}"]`);
      if (byFor) return byFor.textContent || "";
    }
    const wrapped = control.closest("label");
    if (!wrapped) return "";
    const clone = wrapped.cloneNode(true);
    clone.querySelectorAll("input,select,textarea,button").forEach((el) => el.remove());
    return clone.textContent || "";
  };

  const deriveTooltip = (el) => {
    if (!el || el.hasAttribute("title")) return "";

    const ariaLabel = el.getAttribute("aria-label");
    if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();

    if (el.matches("input, select, textarea")) {
      const labelText = labelTextForControl(el).trim();
      if (labelText) return labelText;
      const placeholder = el.getAttribute("placeholder");
      if (placeholder && placeholder.trim()) return placeholder.trim();
      const name = el.getAttribute("name");
      if (name && name.trim()) return prettifyToken(name);
      return "";
    }

    if (el.matches("a, button, .button-link")) {
      const text = (el.textContent || "").trim();
      if (text) return text;
    }

    return "";
  };

  const applyTooltips = (scope = document) => {
    const selector = [
      "a",
      "button",
      ".button-link",
      "input",
      "select",
      "textarea",
    ].join(", ");

    scope.querySelectorAll(selector).forEach((el) => {
      if (!(el instanceof HTMLElement)) return;
      if (el.dataset.tooltipAutoApplied === "1") return;
      const tooltip = deriveTooltip(el);
      if (tooltip) {
        el.setAttribute("title", tooltip);
      }
      el.dataset.tooltipAutoApplied = "1";
    });
  };

  const csrfToken = (() => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? String(meta.getAttribute("content") || "").trim() : "";
  })();

  const initCsrfForms = (scope = document) => {
    if (!csrfToken) return;
    scope.querySelectorAll("form").forEach((form) => {
      if (!(form instanceof HTMLFormElement)) return;
      const method = String(form.getAttribute("method") || "get").toLowerCase();
      if (!["post", "put", "patch", "delete"].includes(method)) return;

      let field = form.querySelector('input[name="csrf_token"]');
      if (!(field instanceof HTMLInputElement)) {
        field = document.createElement("input");
        field.type = "hidden";
        field.name = "csrf_token";
        form.appendChild(field);
      }
      field.value = csrfToken;
    });
  };

  const hideTypeahead = (results) => {
    if (!(results instanceof HTMLElement)) return;
    results.innerHTML = "";
    results.classList.add("hidden");
  };

  const wireTypeaheadKeyboard = (input, results) => {
    if (!(input instanceof HTMLInputElement) || !(results instanceof HTMLElement)) return;
    if (input.dataset.typeaheadKeyboardInit === "1") return;

    let activeIndex = -1;
    const options = () => Array.from(results.querySelectorAll("button.typeahead-option"));
    const clearActive = () => {
      activeIndex = -1;
      options().forEach((option) => option.classList.remove("active"));
    };
    const setActive = (nextIndex) => {
      const rows = options();
      if (!rows.length) {
        clearActive();
        return;
      }
      const bounded = ((nextIndex % rows.length) + rows.length) % rows.length;
      activeIndex = bounded;
      rows.forEach((option, idx) => {
        option.classList.toggle("active", idx === bounded);
      });
      rows[bounded].scrollIntoView({ block: "nearest" });
    };

    input.addEventListener("keydown", (event) => {
      const rows = options();
      if (!rows.length || results.classList.contains("hidden")) return;

      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActive(activeIndex + 1);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActive(activeIndex - 1);
        return;
      }
      if (event.key === "Enter" && activeIndex >= 0) {
        event.preventDefault();
        rows[activeIndex].click();
        clearActive();
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        hideTypeahead(results);
        clearActive();
      }
    });

    results.addEventListener("mousemove", (event) => {
      const option = event.target instanceof HTMLElement
        ? event.target.closest("button.typeahead-option")
        : null;
      if (!option) return;
      const rows = options();
      const idx = rows.indexOf(option);
      if (idx >= 0) setActive(idx);
    });

    results.addEventListener("mousedown", (event) => {
      if (event.target instanceof HTMLElement && event.target.closest("button.typeahead-option")) {
        event.preventDefault();
      }
    });

    const syncObserver = new MutationObserver(() => {
      const rows = options();
      if (results.classList.contains("hidden") || !rows.length || activeIndex >= rows.length) {
        clearActive();
      }
    });
    syncObserver.observe(results, { childList: true, attributes: true, attributeFilter: ["class"] });

    input.dataset.typeaheadKeyboardInit = "1";
  };

  const resultsForInput = (input) => {
    if (!(input instanceof HTMLInputElement)) return null;
    const inBlock = input.closest(".typeahead-block");
    if (inBlock instanceof HTMLElement) {
      const node = inBlock.querySelector(".typeahead-results");
      if (node instanceof HTMLElement) return node;
    }
    const sibling = input.nextElementSibling;
    if (sibling instanceof HTMLElement && sibling.classList.contains("typeahead-results")) {
      return sibling;
    }
    return null;
  };

  const initTypeaheadKeyboard = (scope = document) => {
    scope.querySelectorAll("input").forEach((input) => {
      if (!(input instanceof HTMLInputElement)) return;
      if (input.dataset.typeaheadKeyboardInit === "1") return;
      const results = resultsForInput(input);
      if (results instanceof HTMLElement) {
        wireTypeaheadKeyboard(input, results);
      }
    });
  };

  const initUserDirectoryTypeahead = (scope = document) => {
    scope.querySelectorAll("input[data-user-search]").forEach((input) => {
      if (!(input instanceof HTMLInputElement)) return;
      if (input.dataset.userSearchInitialized === "1") return;

      const results = resultsForInput(input);
      if (!(results instanceof HTMLElement)) {
        input.dataset.userSearchInitialized = "1";
        return;
      }

      wireTypeaheadKeyboard(input, results);
      let timer = null;
      let requestSeq = 0;

      const hideResults = () => hideTypeahead(results);
      const renderResults = (items) => {
        results.innerHTML = "";
        if (!items.length) {
          hideResults();
          return;
        }
        items.forEach((item) => {
          const login = String(item.login_identifier || "").trim();
          if (!login) return;
          const label = String(item.label || `${item.display_name || login} (${login})`).trim();
          const option = document.createElement("button");
          option.type = "button";
          option.className = "typeahead-option";
          option.textContent = label;
          option.addEventListener("click", () => {
            input.value = login;
            hideResults();
          });
          results.appendChild(option);
        });
        if (!results.children.length) {
          hideResults();
          return;
        }
        results.classList.remove("hidden");
      };

      const search = async () => {
        const query = String(input.value || "").trim();
        if (!query) {
          hideResults();
          return;
        }
        const seq = requestSeq + 1;
        requestSeq = seq;
        try {
          const response = await fetch(`/api/users/search?q=${encodeURIComponent(query)}&limit=15`);
          if (!response.ok) {
            hideResults();
            return;
          }
          const payload = await response.json();
          if (seq !== requestSeq) return;
          const items = Array.isArray(payload.items) ? payload.items : [];
          renderResults(items);
        } catch {
          hideResults();
        }
      };

      input.addEventListener("input", () => {
        if (timer) window.clearTimeout(timer);
        timer = window.setTimeout(search, 180);
      });

      document.addEventListener("click", (event) => {
        if (!results.contains(event.target) && event.target !== input) {
          hideResults();
        }
      });

      input.dataset.userSearchInitialized = "1";
    });
  };

  const initDocLinkForms = (scope = document) => {
    scope.querySelectorAll("[data-doc-link-form]").forEach((form) => {
      if (!(form instanceof HTMLFormElement)) return;
      if (form.dataset.docLinkInitialized === "1") return;

      const urlInput = form.querySelector("[data-doc-url]");
      const typeSelect = form.querySelector("[data-doc-type]");
      const tagsSelect = form.querySelector("[data-doc-tags]");
      if (!(urlInput instanceof HTMLInputElement) || !(typeSelect instanceof HTMLSelectElement)) {
        form.dataset.docLinkInitialized = "1";
        return;
      }

      const selectExistingOption = (select, value) => {
        if (!(select instanceof HTMLSelectElement)) return null;
        const normalized = String(value || "").trim();
        if (!normalized) return null;
        let match = [...select.options].find((option) => String(option.value).toLowerCase() === normalized.toLowerCase());
        if (!match) return null;
        match.selected = true;
        return match;
      };

      const suggestType = (url) => {
        const v = String(url || "").toLowerCase();
        if (v.includes("sharepoint.com") || v.includes("/sites/") || v.includes("/teams/")) return "sharepoint";
        if (v.includes("onedrive.live.com") || v.includes("1drv.ms")) return "onedrive";
        if (v.includes("atlassian.net/wiki") || v.includes("/confluence")) return "confluence";
        if (v.includes("docs.google.com") || v.includes("drive.google.com")) return "google_drive";
        if (v.includes("box.com")) return "box";
        if (v.includes("dropbox.com")) return "dropbox";
        if (v.includes("github.com")) return "github";
        return "other";
      };

      const isFolderLike = (url) => {
        const value = String(url || "").trim().toLowerCase();
        if (!value) return false;
        if (value.endsWith("/") || value.endsWith("\\")) return true;
        if (value.includes("/folders/")) return true;
        const compact = value.split("?")[0].split("#")[0];
        const parts = compact.split(/[\\/]/).filter(Boolean);
        if (parts.length < 2) return false;
        const tail = parts[parts.length - 1];
        return !tail.includes(".");
      };

      const applyDerivedTags = (url, explicitType) => {
        if (isFolderLike(url)) {
          selectExistingOption(tagsSelect, "folder");
        }
      };

      const syncDerived = () => {
        const inferredType = suggestType(urlInput.value);
        if (!typeSelect.value || typeSelect.value === "") {
          const matched = [...typeSelect.options].find(
            (option) => String(option.value).toLowerCase() === inferredType.toLowerCase(),
          );
          if (matched) {
            typeSelect.value = matched.value;
          }
        }
        applyDerivedTags(urlInput.value, typeSelect.value || inferredType);
      };

      urlInput.addEventListener("input", syncDerived);
      typeSelect.addEventListener("change", syncDerived);
      syncDerived();

      form.dataset.docLinkInitialized = "1";
    });
  };

  const initClickableRows = (scope = document) => {
    scope.querySelectorAll(".clickable-row[data-href]").forEach((row) => {
      if (!(row instanceof HTMLElement)) return;
      if (row.dataset.clickableRowInit === "1") return;

      row.setAttribute("tabindex", "0");
      row.setAttribute("role", "link");
      row.addEventListener("click", (event) => {
        if (event.target && event.target.closest("a, button, input, select, textarea, label")) {
          return;
        }
        const href = row.getAttribute("data-href");
        if (href) {
          window.location.href = href;
        }
      });
      row.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        const href = row.getAttribute("data-href");
        if (href) {
          window.location.href = href;
        }
      });
      row.dataset.clickableRowInit = "1";
    });
  };

  const initResponsiveTables = (scope = document) => {
    scope.querySelectorAll("table").forEach((table) => {
      if (!(table instanceof HTMLTableElement)) return;
      if (table.closest(".table-wrap")) return;
      const parent = table.parentElement;
      if (!parent) return;
      const wrapper = document.createElement("div");
      wrapper.className = "table-wrap";
      parent.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });
  };

  applyTooltips(document);
  initCsrfForms(document);
  initDocLinkForms(document);
  initUserDirectoryTypeahead(document);
  initTypeaheadKeyboard(document);
  initClickableRows(document);
  initResponsiveTables(document);

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node instanceof HTMLElement) {
          applyTooltips(node);
          initCsrfForms(node);
          initDocLinkForms(node);
          initUserDirectoryTypeahead(node);
          initTypeaheadKeyboard(node);
          initClickableRows(node);
          initResponsiveTables(node);
        }
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
});
