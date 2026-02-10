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

    if (el.matches("th, td, span, div, p, h1, h2, h3, small")) {
      const text = (el.textContent || "").replace(/\s+/g, " ").trim();
      if (text && text.length <= 160) return text;
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
      "label",
      "th",
      "td",
      "span",
      "small",
      "h1",
      "h2",
      "h3",
      "p",
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

  const rows = document.querySelectorAll(".clickable-row[data-href]");
  rows.forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target && event.target.closest("a, button, input, select, textarea, label")) {
        return;
      }
      const href = row.getAttribute("data-href");
      if (href) {
        window.location.href = href;
      }
    });
  });

  applyTooltips(document);
  initDocLinkForms(document);

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node instanceof HTMLElement) {
          applyTooltips(node);
          initDocLinkForms(node);
        }
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
});
