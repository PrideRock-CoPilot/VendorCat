document.addEventListener("DOMContentLoaded", () => {
  // Theme controls
  const themeToggle = document.getElementById("theme-toggle");
  const themeSelect = document.getElementById("theme-select");
  const body = document.body;
  const themeKey = "vendor-catalog-theme";

  const setTheme = (isDark) => {
    if (isDark) {
      body.classList.add("dark-mode");
      localStorage.setItem(themeKey, "dark");
    } else {
      body.classList.remove("dark-mode");
      localStorage.setItem(themeKey, "light");
    }
    if (themeSelect instanceof HTMLSelectElement) {
      themeSelect.value = isDark ? "dark" : "light";
    }
    if (themeToggle instanceof HTMLElement) {
      themeToggle.textContent = isDark ? "Light" : "Dark";
    }
  };

  const toggleTheme = () => {
    const isDark = body.classList.contains("dark-mode");
    setTheme(!isDark);
  };

  // Load saved theme or default to light
  const savedTheme = localStorage.getItem(themeKey);
  if (savedTheme === "dark") {
    setTheme(true);
  } else {
    setTheme(false);
  }

  if (themeToggle) {
    themeToggle.addEventListener("click", toggleTheme);
  }
  if (themeSelect instanceof HTMLSelectElement) {
    themeSelect.addEventListener("change", () => {
      setTheme(themeSelect.value === "dark");
    });
  }

  const userMenuButton = document.getElementById("user-menu-button");
  const userMenuDropdown = document.getElementById("user-menu-dropdown");
  const closeUserMenu = () => {
    if (!(userMenuButton instanceof HTMLButtonElement) || !(userMenuDropdown instanceof HTMLElement)) return;
    userMenuDropdown.classList.add("hidden");
    userMenuButton.setAttribute("aria-expanded", "false");
  };
  const openUserMenu = () => {
    if (!(userMenuButton instanceof HTMLButtonElement) || !(userMenuDropdown instanceof HTMLElement)) return;
    userMenuDropdown.classList.remove("hidden");
    userMenuButton.setAttribute("aria-expanded", "true");
  };
  const toggleUserMenu = () => {
    if (!(userMenuDropdown instanceof HTMLElement)) return;
    if (userMenuDropdown.classList.contains("hidden")) {
      openUserMenu();
      return;
    }
    closeUserMenu();
  };

  if (userMenuButton instanceof HTMLButtonElement && userMenuDropdown instanceof HTMLElement) {
    userMenuButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleUserMenu();
    });
    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      const clickedInButton = userMenuButton.contains(target);
      const clickedInDropdown = userMenuDropdown.contains(target);
      if (!clickedInButton && !clickedInDropdown) closeUserMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeUserMenu();
      }
    });
  }

  // Utility functions
  window.VendorCatalogUtils = {
    formatDate: (dateString) => {
      if (!dateString) return '';
      const date = new Date(dateString);
      return date.toLocaleDateString();
    },
    formatCurrency: (amount) => {
      return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
    },
    debounce: (func, wait) => {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout);
          func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    }
  };

  const loadingOverlay = document.getElementById("loading-overlay");
  const loadingOverlayStatus = document.getElementById("loading-overlay-status");
  let loadingTimer = null;
  let loadingSafetyTimer = null;
  let loadingStatusTimer = null;

  const parseDelayMs = (rawValue, fallback) => {
    const parsed = Number.parseInt(String(rawValue || "").trim(), 10);
    if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
    return parsed;
  };

  const overlayMinDelayMs = parseDelayMs(loadingOverlay?.dataset?.minDelayMs, 2000);
  const overlayMaxDelayMs = parseDelayMs(loadingOverlay?.dataset?.maxDelayMs, 5000);
  const maxDelayMs = Math.max(overlayMinDelayMs, overlayMaxDelayMs);
  const overlayShowDelayMs = parseDelayMs(loadingOverlay?.dataset?.showDelayMs, 220);
  const overlaySlowStatusMs = parseDelayMs(loadingOverlay?.dataset?.slowStatusMs, 5000);
  const overlaySafetyMs = parseDelayMs(
    loadingOverlay?.dataset?.safetyMs,
    Math.max(8000, maxDelayMs + 3000),
  );

  const setLoadingStatus = (message) => {
    if (!(loadingOverlayStatus instanceof HTMLElement)) return;
    const text = String(message || "").trim();
    if (!text) return;
    loadingOverlayStatus.textContent = text;
  };

  const showLoadingOverlay = (delayMs = 120, message = "Loading...") => {
    if (!(loadingOverlay instanceof HTMLElement)) return;
    if (loadingTimer) window.clearTimeout(loadingTimer);
    if (loadingSafetyTimer) {
      window.clearTimeout(loadingSafetyTimer);
      loadingSafetyTimer = null;
    }
    if (loadingStatusTimer) {
      window.clearTimeout(loadingStatusTimer);
      loadingStatusTimer = null;
    }
    loadingTimer = window.setTimeout(() => {
      setLoadingStatus(message);
      loadingOverlay.classList.add("visible");
      loadingSafetyTimer = window.setTimeout(() => {
        hideLoadingOverlay(true);
      }, overlaySafetyMs);
      loadingStatusTimer = window.setTimeout(() => {
        setLoadingStatus("Still loading. Waiting on database response...");
      }, overlaySlowStatusMs);
    }, delayMs);
  };

  const hideLoadingOverlay = (_force = false) => {
    if (!(loadingOverlay instanceof HTMLElement)) return;
    if (loadingTimer) {
      window.clearTimeout(loadingTimer);
      loadingTimer = null;
    }
    if (loadingSafetyTimer) {
      window.clearTimeout(loadingSafetyTimer);
      loadingSafetyTimer = null;
    }
    if (loadingStatusTimer) {
      window.clearTimeout(loadingStatusTimer);
      loadingStatusTimer = null;
    }
    loadingOverlay.classList.remove("visible");
  };

  const workspaceOverlay = document.getElementById("workspace-overlay");
  const workspaceOverlayPanel = document.getElementById("workspace-overlay-panel");
  const workspaceOverlayTitle = document.getElementById("workspace-overlay-title");
  const workspaceOverlaySubtitle = document.getElementById("workspace-overlay-subtitle");
  const workspaceOverlayContent = document.getElementById("workspace-overlay-content");
  const workspaceOverlayFooter = document.getElementById("workspace-overlay-footer");
  const workspaceOverlayCloseButtons = workspaceOverlay
    ? Array.from(workspaceOverlay.querySelectorAll("[data-overlay-close]"))
    : [];
  const workspaceOverlayState = {
    open: false,
    dirty: false,
    dirtyGuardEnabled: true,
    restoreFocusElement: null,
  };

  const getFocusableElements = (root) => {
    if (!(root instanceof HTMLElement)) return [];
    const selector = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(", ");
    return Array.from(root.querySelectorAll(selector)).filter((el) => {
      if (!(el instanceof HTMLElement)) return false;
      return !el.hasAttribute("hidden") && el.offsetParent !== null;
    });
  };

  const setWorkspaceDirty = (dirty = true) => {
    workspaceOverlayState.dirty = Boolean(dirty);
  };

  const closeWorkspaceOverlay = (force = false) => {
    if (!(workspaceOverlay instanceof HTMLElement) || !(workspaceOverlayPanel instanceof HTMLElement)) return true;
    if (!workspaceOverlayState.open) return true;
    if (!force && workspaceOverlayState.dirtyGuardEnabled && workspaceOverlayState.dirty) {
      const shouldDiscard = window.confirm("You have unsaved changes. Close this workspace?");
      if (!shouldDiscard) return false;
    }
    workspaceOverlay.classList.remove("open");
    workspaceOverlay.setAttribute("aria-hidden", "true");
    window.setTimeout(() => {
      workspaceOverlay.setAttribute("hidden", "hidden");
      workspaceOverlayContent.innerHTML = "";
      workspaceOverlayFooter.innerHTML = "";
      workspaceOverlayFooter.classList.add("hidden");
      workspaceOverlayPanel.classList.remove("workspace-overlay-panel-drawer", "workspace-overlay-panel-fullscreen");
      document.body.classList.remove("workspace-overlay-body-lock");
      workspaceOverlayState.open = false;
      workspaceOverlayState.dirty = false;
      workspaceOverlayState.restoreFocusElement?.focus?.();
      workspaceOverlayState.restoreFocusElement = null;
    }, 190);
    return true;
  };

  const applyWorkspaceActions = (actions) => {
    if (!(workspaceOverlayFooter instanceof HTMLElement)) return;
    workspaceOverlayFooter.innerHTML = "";
    if (!Array.isArray(actions) || !actions.length) {
      workspaceOverlayFooter.classList.add("hidden");
      return;
    }
    workspaceOverlayFooter.classList.remove("hidden");
    actions.forEach((action, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = String(action?.label || `Action ${index + 1}`);
      if (action?.className) button.className = String(action.className);
      if (action?.close) {
        button.dataset.overlayClose = "true";
      }
      button.addEventListener("click", () => {
        const actionId = String(action?.actionId || `action_${index}`);
        workspaceOverlay.dispatchEvent(new CustomEvent("workspace-overlay-action", { detail: { actionId } }));
        if (action?.close) {
          closeWorkspaceOverlay();
        }
      });
      workspaceOverlayFooter.appendChild(button);
    });
  };

  const openWorkspaceOverlay = (options = {}) => {
    if (!(workspaceOverlay instanceof HTMLElement) || !(workspaceOverlayPanel instanceof HTMLElement)) return null;
    const mode = String(options.mode || "drawer-right").trim().toLowerCase();
    const title = String(options.title || "Workspace").trim();
    const subtitle = String(options.subtitle || "").trim();
    const templateId = String(options.templateId || "").trim();
    const html = String(options.html || "").trim();
    const dirtyGuardEnabled = options.dirtyGuard !== false;
    const triggerElement = options.triggerElement instanceof HTMLElement
      ? options.triggerElement
      : document.activeElement;

    workspaceOverlayState.restoreFocusElement = triggerElement instanceof HTMLElement ? triggerElement : null;
    workspaceOverlayState.dirty = false;
    workspaceOverlayState.dirtyGuardEnabled = dirtyGuardEnabled;

    workspaceOverlayTitle.textContent = title || "Workspace";
    if (subtitle) {
      workspaceOverlaySubtitle.textContent = subtitle;
      workspaceOverlaySubtitle.classList.remove("hidden");
    } else {
      workspaceOverlaySubtitle.textContent = "";
      workspaceOverlaySubtitle.classList.add("hidden");
    }

    workspaceOverlayContent.innerHTML = "";
    if (templateId) {
      const sourceTemplate = document.getElementById(templateId);
      if (sourceTemplate instanceof HTMLTemplateElement) {
        workspaceOverlayContent.appendChild(sourceTemplate.content.cloneNode(true));
      } else if (sourceTemplate instanceof HTMLElement) {
        workspaceOverlayContent.appendChild(sourceTemplate.cloneNode(true));
      }
    } else if (html) {
      workspaceOverlayContent.innerHTML = html;
    } else if (options.content instanceof HTMLElement) {
      workspaceOverlayContent.appendChild(options.content);
    }

    workspaceOverlayPanel.classList.remove("workspace-overlay-panel-drawer", "workspace-overlay-panel-fullscreen");
    if (mode === "fullscreen") {
      workspaceOverlayPanel.classList.add("workspace-overlay-panel-fullscreen");
    } else {
      workspaceOverlayPanel.classList.add("workspace-overlay-panel-drawer");
    }

    applyWorkspaceActions(options.actions);

    workspaceOverlay.removeAttribute("hidden");
    workspaceOverlay.classList.add("open");
    workspaceOverlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("workspace-overlay-body-lock");

    const focusable = getFocusableElements(workspaceOverlayPanel);
    const autofocusTarget = workspaceOverlayContent.querySelector("[autofocus]");
    if (autofocusTarget instanceof HTMLElement) {
      autofocusTarget.focus();
    } else if (focusable.length) {
      focusable[0].focus();
    } else {
      workspaceOverlayPanel.focus();
    }

    workspaceOverlayState.open = true;
    workspaceOverlayContent.querySelectorAll("form").forEach((formNode) => {
      if (!(formNode instanceof HTMLFormElement)) return;
      const watchDirty = String(formNode.dataset.overlayDirtyWatch || "true").toLowerCase() !== "false";
      if (!watchDirty) return;
      formNode.addEventListener("input", () => setWorkspaceDirty(true));
      formNode.addEventListener("change", () => setWorkspaceDirty(true));
      formNode.addEventListener("submit", () => setWorkspaceDirty(false));
    });

    applyTooltips(workspaceOverlayContent);
    initCsrfForms(workspaceOverlayContent);
    initTypeaheadKeyboard(workspaceOverlayContent);
    initUserDirectoryTypeahead(workspaceOverlayContent);

    workspaceOverlay.dispatchEvent(
      new CustomEvent("workspace-overlay-opened", {
        detail: {
          mode,
          title: workspaceOverlayTitle.textContent,
          contentRoot: workspaceOverlayContent,
        },
      }),
    );
    return workspaceOverlayContent;
  };

  const onWorkspaceKeyDown = (event) => {
    if (!workspaceOverlayState.open || !(workspaceOverlayPanel instanceof HTMLElement)) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeWorkspaceOverlay();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = getFocusableElements(workspaceOverlayPanel);
    if (!focusable.length) {
      event.preventDefault();
      workspaceOverlayPanel.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
      return;
    }
    if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  window.VendorOverlay = {
    open: openWorkspaceOverlay,
    close: closeWorkspaceOverlay,
    setDirty: setWorkspaceDirty,
    clearDirty: () => setWorkspaceDirty(false),
    isOpen: () => workspaceOverlayState.open,
  };

  if (workspaceOverlay instanceof HTMLElement) {
    workspaceOverlay.addEventListener("keydown", onWorkspaceKeyDown);
    workspaceOverlayCloseButtons.forEach((button) => {
      if (!(button instanceof HTMLElement)) return;
      button.addEventListener("click", () => {
        closeWorkspaceOverlay();
      });
    });
    workspaceOverlay.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.hasAttribute("data-overlay-close")) {
        closeWorkspaceOverlay();
      }
    });
  }

  document.addEventListener("click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target.closest("[data-workspace-open]") : null;
    if (!(target instanceof HTMLElement)) return;
    event.preventDefault();
    const templateId = String(target.dataset.workspaceTemplate || "").trim();
    const mode = String(target.dataset.workspaceMode || "drawer-right").trim().toLowerCase();
    const title = String(target.dataset.workspaceTitle || "Workspace").trim();
    const subtitle = String(target.dataset.workspaceSubtitle || "").trim();
    const dirtyGuard = String(target.dataset.workspaceDirtyGuard || "true").trim().toLowerCase() !== "false";
    const contentRoot = openWorkspaceOverlay({
      mode,
      title,
      subtitle,
      templateId,
      dirtyGuard,
      triggerElement: target,
    });
    if (contentRoot instanceof HTMLElement) {
      workspaceOverlay?.dispatchEvent(
        new CustomEvent("workspace-overlay-template-opened", {
          detail: {
            templateId,
            trigger: target,
            contentRoot,
          },
        }),
      );
    }
  });

  const shouldShowLoadingForLink = (link) => {
    if (!(link instanceof HTMLAnchorElement)) return false;
    if (link.dataset.noLoading === "true") return false;
    const href = String(link.getAttribute("href") || "").trim();
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) return false;
    if (href.startsWith("mailto:") || href.startsWith("tel:")) return false;
    if (link.hasAttribute("download")) return false;
    const target = String(link.getAttribute("target") || "").trim().toLowerCase();
    if (target && target !== "_self") return false;
    try {
      const resolved = new URL(link.href, window.location.href);
      if (resolved.origin !== window.location.origin) return false;
    } catch {
      return false;
    }
    return true;
  };

  const shouldShowLoadingForForm = (form) => {
    if (!(form instanceof HTMLFormElement)) return false;
    if (form.dataset.noLoading === "true") return false;
    const method = String(form.getAttribute("method") || "get").toLowerCase();
    return ["get", "post", "put", "patch", "delete"].includes(method);
  };

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    form.classList.add("validation-attempted");
    if (!form.checkValidity()) {
      return;
    }
    if (shouldShowLoadingForForm(form)) {
      showLoadingOverlay(overlayShowDelayMs, "Saving changes...");
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const link = target.closest("a");
    if (link instanceof HTMLAnchorElement && shouldShowLoadingForLink(link)) {
      showLoadingOverlay(overlayShowDelayMs, "Loading next screen...");
    }
  });

  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      hideLoadingOverlay(true);
    }
  });
  window.addEventListener("popstate", () => {
    hideLoadingOverlay(true);
  });
  window.addEventListener("load", () => {
    hideLoadingOverlay(true);
  });
  window.addEventListener("beforeunload", () => {
    showLoadingOverlay(overlayShowDelayMs, "Loading next screen...");
  });

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
    const getPickerFields = (input) => {
      if (!(input instanceof HTMLInputElement)) {
        return { emailInput: null, displayInput: null };
      }
      const pairKey = String(input.dataset.userSearchPair || "").trim();
      const pickerRoot = input.closest("[data-user-picker]");
      const formRoot = input.closest("form");
      if (!pairKey) {
        return { emailInput: null, displayInput: null };
      }

      const resolveFromRoot = (root) => {
        if (!(root instanceof HTMLElement)) return { emailInput: null, displayInput: null };
        const pairedInputs = Array.from(root.querySelectorAll("input[data-user-search]")).filter((node) => {
          if (!(node instanceof HTMLInputElement)) return false;
          return String(node.dataset.userSearchPair || "").trim() === pairKey;
        });
        let emailInput = null;
        let displayInput = null;
        pairedInputs.forEach((node) => {
          const mode = String(node.dataset.userSearchMode || "").trim().toLowerCase();
          if (mode === "email" || node.name === pairKey) {
            emailInput = node;
          } else if (mode === "display_name") {
            displayInput = node;
          }
        });

        if (!(emailInput instanceof HTMLInputElement)) {
          const fallbackEmail = root.querySelector(`input[name="${pairKey}"]`);
          if (fallbackEmail instanceof HTMLInputElement) emailInput = fallbackEmail;
        }
        if (!(displayInput instanceof HTMLInputElement)) {
          const fallbackDisplay = root.querySelector(`input[name="${pairKey}_display_name"]`);
          if (fallbackDisplay instanceof HTMLInputElement) displayInput = fallbackDisplay;
        }
        return { emailInput, displayInput };
      };

      const fromPicker = resolveFromRoot(pickerRoot);
      if (fromPicker.emailInput || fromPicker.displayInput) {
        return fromPicker;
      }
      return resolveFromRoot(formRoot);
    };

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
      const getLivePair = () => getPickerFields(input);

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
          const rawDisplayName = String(item.display_name || "").trim();
          const email = String(item.email || login).trim() || login;
          const fallbackLabel = rawDisplayName ? `${rawDisplayName} (${email})` : email;
          const label = String(item.label || fallbackLabel).trim() || fallbackLabel;
          let displayName = rawDisplayName;
          if (!displayName && label.includes("(")) {
            displayName = label.split("(")[0].trim();
          }
          if (!displayName) {
            displayName = login;
          }
          const option = document.createElement("button");
          option.type = "button";
          option.className = "typeahead-option";
          option.textContent = label;
          option.addEventListener("click", () => {
            const { emailInput, displayInput } = getLivePair();
            if (emailInput instanceof HTMLInputElement) {
              emailInput.value = login;
              emailInput.dispatchEvent(new Event("change", { bubbles: true }));
            } else {
              input.value = login;
              input.dispatchEvent(new Event("change", { bubbles: true }));
            }
            if (displayInput instanceof HTMLInputElement) {
              displayInput.value = displayName;
              displayInput.dispatchEvent(new Event("change", { bubbles: true }));
            }
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
        const currentValue = String(input.value || "").trim();
        const { displayInput, emailInput } = getLivePair();
        if (displayInput instanceof HTMLInputElement && emailInput instanceof HTMLInputElement) {
          if (input === displayInput && !String(emailInput.value || "").trim()) {
            emailInput.value = currentValue;
          }
        }
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

  const initContactDirectoryTypeahead = (scope = document) => {
    const getPickerFields = (input) => {
      if (!(input instanceof HTMLInputElement)) {
        return { nameInput: null, emailInput: null, phoneInput: null };
      }
      const pairKey = String(input.dataset.contactSearchPair || "").trim();
      if (!pairKey) {
        return { nameInput: null, emailInput: null, phoneInput: null };
      }
      const pickerRoot = input.closest("[data-contact-picker]");
      const formRoot = input.closest("form");

      const resolveFromRoot = (root) => {
        if (!(root instanceof HTMLElement)) return { nameInput: null, emailInput: null, phoneInput: null };
        const pairedInputs = Array.from(root.querySelectorAll("input[data-contact-search]")).filter((node) => {
          if (!(node instanceof HTMLInputElement)) return false;
          return String(node.dataset.contactSearchPair || "").trim() === pairKey;
        });
        let nameInput = null;
        let emailInput = null;
        pairedInputs.forEach((node) => {
          const mode = String(node.dataset.contactSearchMode || "").trim().toLowerCase();
          if (mode === "name" || node.name === "full_name") {
            nameInput = node;
          } else if (mode === "email" || node.name === "email") {
            emailInput = node;
          }
        });
        const phoneInput = root.querySelector(`input[data-contact-phone][data-contact-search-pair="${pairKey}"]`);
        return {
          nameInput: nameInput instanceof HTMLInputElement ? nameInput : null,
          emailInput: emailInput instanceof HTMLInputElement ? emailInput : null,
          phoneInput: phoneInput instanceof HTMLInputElement ? phoneInput : null,
        };
      };

      const fromPicker = resolveFromRoot(pickerRoot);
      if (fromPicker.nameInput || fromPicker.emailInput || fromPicker.phoneInput) {
        return fromPicker;
      }
      return resolveFromRoot(formRoot);
    };

    scope.querySelectorAll("input[data-contact-search]").forEach((input) => {
      if (!(input instanceof HTMLInputElement)) return;
      if (input.dataset.contactSearchInitialized === "1") return;

      const results = resultsForInput(input);
      if (!(results instanceof HTMLElement)) {
        input.dataset.contactSearchInitialized = "1";
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
          const fullName = String(item.full_name || "").trim();
          const email = String(item.email || "").trim();
          const phone = String(item.phone || "").trim();
          if (!fullName && !email) return;
          const fallbackLabel = [fullName || "(No Name)", email ? `(${email})` : "", phone ? `- ${phone}` : ""]
            .filter(Boolean)
            .join(" ")
            .trim();
          const label = String(item.label || fallbackLabel).trim() || fallbackLabel;
          const option = document.createElement("button");
          option.type = "button";
          option.className = "typeahead-option";
          option.textContent = label;
          option.addEventListener("click", () => {
            const { nameInput, emailInput, phoneInput } = getPickerFields(input);
            if (nameInput instanceof HTMLInputElement) {
              nameInput.value = fullName || nameInput.value;
              nameInput.dispatchEvent(new Event("change", { bubbles: true }));
            }
            if (emailInput instanceof HTMLInputElement) {
              emailInput.value = email || emailInput.value;
              emailInput.dispatchEvent(new Event("change", { bubbles: true }));
            }
            if (phoneInput instanceof HTMLInputElement) {
              phoneInput.value = phone || "";
              phoneInput.dispatchEvent(new Event("change", { bubbles: true }));
            }
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
          const response = await fetch(`/api/contacts/search?q=${encodeURIComponent(query)}&limit=15`);
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

      input.dataset.contactSearchInitialized = "1";
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
          showLoadingOverlay(overlayShowDelayMs, "Loading next screen...");
          window.location.href = href;
        }
      });
      row.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        const href = row.getAttribute("data-href");
        if (href) {
          showLoadingOverlay(overlayShowDelayMs, "Loading next screen...");
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

  const initHelpCenter = (scope = document) => {
    const copyButtons = Array.from(scope.querySelectorAll("[data-help-copy-link]"));
    if (!copyButtons.length) return;

    const copyText = async (text) => {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return;
      }
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "readonly");
      textarea.style.position = "absolute";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    };

    copyButtons.forEach((button) => {
      if (!(button instanceof HTMLElement)) return;
      if (button.dataset.helpCopyInit === "1") return;
      button.dataset.helpCopyInit = "1";
      button.addEventListener("click", async () => {
        const rawLink = String(button.getAttribute("data-help-link") || "").trim();
        const link = rawLink || window.location.pathname;
        const url = link.startsWith("http") ? link : `${window.location.origin}${link}`;
        try {
          await copyText(url);
          const original = button.textContent || "Copy link";
          button.textContent = "Link copied";
          window.setTimeout(() => {
            button.textContent = original;
          }, 1800);
        } catch {
          window.alert("Copy failed. Please copy the URL from the address bar.");
        }
      });
    });
  };

  const _dashboardPalette = [
    "#0f766e",
    "#1d4ed8",
    "#14b8a6",
    "#0b5a7f",
    "#334155",
    "#7c3aed",
    "#ea580c",
    "#16a34a",
  ];

  const parseDashboardSeries = (sourceId) => {
    const source = document.getElementById(String(sourceId || ""));
    if (!(source instanceof HTMLScriptElement)) return [];
    try {
      const parsed = JSON.parse(source.textContent || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const formatDashboardValue = (value, prefix = "") => {
    const number = Number(value || 0);
    if (!Number.isFinite(number)) return `${prefix}0`;
    return `${prefix}${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(number)}`;
  };

  const renderDashboardDonut = (target) => {
    if (!(target instanceof HTMLElement)) return;
    const sourceId = target.dataset.sourceId || "";
    const labelField = target.dataset.labelField || "label";
    const valueField = target.dataset.valueField || "value";
    const prefix = target.dataset.prefix || "";
    const emptyText = target.dataset.emptyText || "No data";
    const series = parseDashboardSeries(sourceId)
      .map((row) => ({
        label: String(row?.[labelField] ?? "Unknown"),
        value: Number(row?.[valueField] ?? 0),
      }))
      .filter((row) => Number.isFinite(row.value) && row.value > 0);

    target.innerHTML = "";
    if (!series.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = emptyText;
      target.appendChild(empty);
      return;
    }

    const total = series.reduce((acc, item) => acc + item.value, 0);
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 220 220");
    svg.setAttribute("class", "dashboard-chart-svg");
    const radius = 80;
    const cx = 110;
    const cy = 110;
    const circumference = 2 * Math.PI * radius;
    let offset = 0;

    series.forEach((item, index) => {
      const pct = item.value / total;
      const segment = document.createElementNS(ns, "circle");
      segment.setAttribute("cx", String(cx));
      segment.setAttribute("cy", String(cy));
      segment.setAttribute("r", String(radius));
      segment.setAttribute("fill", "none");
      segment.setAttribute("stroke", _dashboardPalette[index % _dashboardPalette.length]);
      segment.setAttribute("stroke-width", "24");
      segment.setAttribute("stroke-dasharray", `${(pct * circumference).toFixed(2)} ${circumference.toFixed(2)}`);
      segment.setAttribute("stroke-dashoffset", `${(-offset).toFixed(2)}`);
      segment.setAttribute("transform", `rotate(-90 ${cx} ${cy})`);
      segment.setAttribute("title", `${item.label}: ${formatDashboardValue(item.value, prefix)} (${(pct * 100).toFixed(1)}%)`);
      svg.appendChild(segment);
      offset += pct * circumference;
    });

    const centerValue = document.createElementNS(ns, "text");
    centerValue.setAttribute("x", String(cx));
    centerValue.setAttribute("y", "106");
    centerValue.setAttribute("text-anchor", "middle");
    centerValue.setAttribute("class", "dashboard-chart-center-value");
    centerValue.textContent = formatDashboardValue(total, prefix);
    svg.appendChild(centerValue);

    const centerLabel = document.createElementNS(ns, "text");
    centerLabel.setAttribute("x", String(cx));
    centerLabel.setAttribute("y", "126");
    centerLabel.setAttribute("text-anchor", "middle");
    centerLabel.setAttribute("class", "dashboard-chart-center-label");
    centerLabel.textContent = "total";
    svg.appendChild(centerLabel);

    target.appendChild(svg);
  };

  const renderDashboardLine = (target) => {
    if (!(target instanceof HTMLElement)) return;
    const sourceId = target.dataset.sourceId || "";
    const labelField = target.dataset.labelField || "label";
    const valueField = target.dataset.valueField || "value";
    const prefix = target.dataset.prefix || "";
    const emptyText = target.dataset.emptyText || "No data";
    const series = parseDashboardSeries(sourceId)
      .map((row) => ({
        label: String(row?.[labelField] ?? ""),
        value: Number(row?.[valueField] ?? 0),
      }))
      .filter((row) => Number.isFinite(row.value));

    target.innerHTML = "";
    if (!series.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = emptyText;
      target.appendChild(empty);
      return;
    }

    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 520 220");
    svg.setAttribute("class", "dashboard-chart-svg dashboard-chart-svg-line");
    const max = Math.max(...series.map((point) => point.value), 1);
    const min = Math.min(...series.map((point) => point.value), 0);
    const span = Math.max(max - min, 1);
    const left = 36;
    const right = 12;
    const top = 16;
    const bottom = 34;
    const width = 520 - left - right;
    const height = 220 - top - bottom;

    const points = series.map((point, index) => {
      const x = left + (series.length === 1 ? width / 2 : (index / (series.length - 1)) * width);
      const y = top + (1 - (point.value - min) / span) * height;
      return { ...point, x, y };
    });

    const axis = document.createElementNS(ns, "line");
    axis.setAttribute("x1", String(left));
    axis.setAttribute("x2", String(left + width));
    axis.setAttribute("y1", String(top + height));
    axis.setAttribute("y2", String(top + height));
    axis.setAttribute("class", "dashboard-chart-axis");
    svg.appendChild(axis);

    const polyline = document.createElementNS(ns, "polyline");
    polyline.setAttribute("fill", "none");
    polyline.setAttribute("class", "dashboard-chart-line");
    polyline.setAttribute(
      "points",
      points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" "),
    );
    svg.appendChild(polyline);

    points.forEach((point, index) => {
      const dot = document.createElementNS(ns, "circle");
      dot.setAttribute("cx", point.x.toFixed(2));
      dot.setAttribute("cy", point.y.toFixed(2));
      dot.setAttribute("r", "3.5");
      dot.setAttribute("class", "dashboard-chart-dot");
      dot.setAttribute("title", `${point.label}: ${formatDashboardValue(point.value, prefix)}`);
      svg.appendChild(dot);

      if (index === 0 || index === points.length - 1 || index % 2 === 0) {
        const tick = document.createElementNS(ns, "text");
        tick.setAttribute("x", point.x.toFixed(2));
        tick.setAttribute("y", String(top + height + 16));
        tick.setAttribute("text-anchor", "middle");
        tick.setAttribute("class", "dashboard-chart-tick");
        tick.textContent = point.label;
        svg.appendChild(tick);
      }
    });

    const peak = points.reduce((acc, point) => (point.value > acc.value ? point : acc), points[0]);
    const peakLabel = document.createElementNS(ns, "text");
    peakLabel.setAttribute("x", peak.x.toFixed(2));
    peakLabel.setAttribute("y", String(Math.max(peak.y - 10, top + 10)));
    peakLabel.setAttribute("text-anchor", "middle");
    peakLabel.setAttribute("class", "dashboard-chart-peak");
    peakLabel.textContent = formatDashboardValue(peak.value, prefix);
    svg.appendChild(peakLabel);

    target.appendChild(svg);
  };

  const initDashboardCharts = (scope = document) => {
    scope.querySelectorAll("[data-dashboard-donut]").forEach((node) => {
      renderDashboardDonut(node);
    });
    scope.querySelectorAll("[data-dashboard-line]").forEach((node) => {
      renderDashboardLine(node);
    });
  };

  applyTooltips(document);
  initCsrfForms(document);
  initDocLinkForms(document);
  initUserDirectoryTypeahead(document);
  initContactDirectoryTypeahead(document);
  initTypeaheadKeyboard(document);
  initClickableRows(document);
  initResponsiveTables(document);
  initHelpCenter(document);
  initDashboardCharts(document);

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node instanceof HTMLElement) {
          applyTooltips(node);
          initCsrfForms(node);
          initDocLinkForms(node);
          initUserDirectoryTypeahead(node);
          initContactDirectoryTypeahead(node);
          initTypeaheadKeyboard(node);
          initClickableRows(node);
          initResponsiveTables(node);
          initHelpCenter(node);
          initDashboardCharts(node);
        }
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
});

