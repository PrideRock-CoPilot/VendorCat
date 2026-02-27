(() => {
  const root = document.querySelector("[data-merge-guided]");
  if (!root) {
    return;
  }

  const toBool = (value) => String(value || "").toLowerCase() === "true";
  const guidedEnabled = toBool(root.dataset.guidedEnabled);
  const showTourOnLoad = toBool(root.dataset.showTour);
  const tourDismissUrl = String(root.dataset.tourDismissUrl || "").trim();
  const csrfToken = String(document.querySelector("meta[name='csrf-token']")?.getAttribute("content") || "").trim();

  const survivorHidden = document.getElementById("survivor-vendor-id");
  const sourceHidden = document.getElementById("source-vendor-id");
  const survivorLabel = document.getElementById("survivor-vendor-label");
  const sourceLabel = document.getElementById("source-vendor-label");
  const manualIdInput = document.getElementById("merge-id-manual");
  const candidateForm = document.getElementById("merge-candidate-form");
  const executeForm = document.getElementById("merge-execute-form");
  const finalAck = document.getElementById("merge-final-ack");

  const safeValue = (value) => String(value || "").trim();
  const looksLikeVendorId = (value) => /^vnd-[a-z0-9-]+$/i.test(safeValue(value));

  const applyManualIdInput = () => {
    if (!(manualIdInput instanceof HTMLInputElement)) return;
    const raw = safeValue(manualIdInput.value);
    if (!raw) return;
    const parts = raw.split(",").map((item) => safeValue(item));
    const map = {};
    parts.forEach((part) => {
      const [key, value] = part.split("=").map((item) => safeValue(item));
      if (!key || !value) return;
      map[key.toLowerCase()] = value;
    });
    if (survivorHidden instanceof HTMLInputElement && map.survivor) {
      survivorHidden.value = map.survivor;
      if (survivorLabel instanceof HTMLInputElement && !safeValue(survivorLabel.value)) {
        survivorLabel.value = map.survivor;
      }
    }
    if (sourceHidden instanceof HTMLInputElement && map.source) {
      sourceHidden.value = map.source;
      if (sourceLabel instanceof HTMLInputElement && !safeValue(sourceLabel.value)) {
        sourceLabel.value = map.source;
      }
    }
  };

  if (manualIdInput instanceof HTMLInputElement) {
    manualIdInput.addEventListener("change", applyManualIdInput);
    manualIdInput.addEventListener("blur", applyManualIdInput);
  }

  const searchVendors = (query) => {
    const q = encodeURIComponent(safeValue(query));
    if (!q) return Promise.resolve([]);
    return fetch(`/api/vendors/search?q=${q}&limit=8`, {
      method: "GET",
      credentials: "same-origin",
    })
      .then((response) => {
        if (!response.ok) return [];
        return response.json();
      })
      .then((payload) => {
        const items = Array.isArray(payload?.items) ? payload.items : [];
        return items.map((item) => ({
          id: safeValue(item.vendor_id),
          label: safeValue(item.label || item.display_name || item.legal_name || item.vendor_id),
        })).filter((item) => item.id && item.label);
      })
      .catch(() => []);
  };

  const bindTypeahead = (container) => {
    const input = container.querySelector("[data-typeahead-input]");
    const results = container.querySelector("[data-typeahead-results]");
    const targetSelector = safeValue(container.getAttribute("data-target-input"));
    const targetInput = targetSelector ? document.querySelector(targetSelector) : null;
    if (!(input instanceof HTMLInputElement) || !(results instanceof HTMLElement) || !(targetInput instanceof HTMLInputElement)) {
      return;
    }

    let lastRequest = 0;
    const closeResults = () => {
      results.hidden = true;
      results.innerHTML = "";
    };

    input.addEventListener("input", () => {
      const current = safeValue(input.value);
      if (looksLikeVendorId(current)) {
        targetInput.value = current;
      }
      if (current.length < 2) {
        closeResults();
        return;
      }
      lastRequest += 1;
      const requestId = lastRequest;
      searchVendors(current).then((items) => {
        if (requestId !== lastRequest) return;
        results.innerHTML = "";
        if (!items.length) {
          closeResults();
          return;
        }
        items.forEach((item) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "typeahead-option";
          button.textContent = item.label;
          button.dataset.targetId = item.id;
          button.addEventListener("click", () => {
            input.value = item.label;
            targetInput.value = item.id;
            closeResults();
          });
          results.appendChild(button);
        });
        results.hidden = false;
      });
    });

    input.addEventListener("blur", () => {
      window.setTimeout(() => {
        const current = safeValue(input.value);
        if (looksLikeVendorId(current)) {
          targetInput.value = current;
        }
        closeResults();
      }, 140);
    });
  };

  Array.from(root.querySelectorAll("[data-vendor-typeahead]")).forEach((container) => {
    if (container instanceof HTMLElement) {
      bindTypeahead(container);
    }
  });

  if (candidateForm instanceof HTMLFormElement) {
    candidateForm.addEventListener("submit", (event) => {
      applyManualIdInput();
      const survivor = safeValue(survivorHidden instanceof HTMLInputElement ? survivorHidden.value : "");
      const source = safeValue(sourceHidden instanceof HTMLInputElement ? sourceHidden.value : "");
      if (!survivor || !source) {
        event.preventDefault();
        window.alert("Select both survivor and source vendors before preview.");
        return;
      }
      if (survivor.toLowerCase() === source.toLowerCase()) {
        event.preventDefault();
        window.alert("Survivor and source vendor must be different.");
      }
    });
  }

  if (executeForm instanceof HTMLFormElement && finalAck instanceof HTMLInputElement) {
    executeForm.addEventListener("submit", (event) => {
      if (!finalAck.checked) {
        event.preventDefault();
        window.alert("Final acknowledgement is required before merge execute.");
      }
    });
  }

  const offeringRows = Array.from(root.querySelectorAll(".merge-offering-row"));
  const refreshOfferingRow = (row) => {
    const decision = row.querySelector("[data-offering-decision]");
    const target = row.querySelector("[data-offering-target]");
    const rename = row.querySelector("[data-offering-rename]");
    if (!(decision instanceof HTMLSelectElement) || !(target instanceof HTMLSelectElement) || !(rename instanceof HTMLInputElement)) {
      return;
    }
    const mergeMode = safeValue(decision.value).toLowerCase() === "merge";
    target.disabled = !mergeMode;
    target.required = mergeMode;
    rename.disabled = mergeMode;
    rename.required = false;
  };
  offeringRows.forEach((row) => {
    const decision = row.querySelector("[data-offering-decision]");
    refreshOfferingRow(row);
    if (decision instanceof HTMLSelectElement) {
      decision.addEventListener("change", () => refreshOfferingRow(row));
    }
  });

  const stepButtons = Array.from(root.querySelectorAll("[data-merge-step]"));
  const stepTargetMap = {
    candidate: root.querySelector("[data-merge-panel='candidate']"),
    conflicts: root.querySelector("[data-merge-panel='conflicts']"),
    confirm: root.querySelector("[data-merge-panel='confirm']"),
  };
  stepButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = safeValue(button.getAttribute("data-merge-step")).toLowerCase();
      const target = stepTargetMap[key];
      if (target instanceof HTMLElement) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  const tourOverlay = root.querySelector("[data-tour-overlay]");
  const replayButton = root.querySelector("[data-replay-tour]");
  const tourDemoBoard = root.querySelector("[data-tour-demo-board]");
  const tourDemoCards = Array.from(root.querySelectorAll("[data-tour-example]"));

  const showTourExample = (exampleId) => {
    if (!(tourDemoBoard instanceof HTMLElement)) return;
    const targetId = safeValue(exampleId);
    tourDemoBoard.hidden = false;
    tourDemoCards.forEach((card) => {
      if (!(card instanceof HTMLElement)) return;
      card.hidden = safeValue(card.getAttribute("data-tour-example")) !== targetId;
    });
  };

  const clearTourExamples = () => {
    if (!(tourDemoBoard instanceof HTMLElement)) return;
    tourDemoCards.forEach((card) => {
      if (card instanceof HTMLElement) {
        card.hidden = true;
      }
    });
    tourDemoBoard.hidden = true;
  };

  const focusMergePanel = (panelKey) => {
    const target = stepTargetMap[panelKey];
    if (target instanceof HTMLElement) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const persistTourDismiss = () => {
    if (!tourDismissUrl) return;
    fetch(tourDismissUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "x-csrf-token": csrfToken } : {}),
      },
      body: JSON.stringify({ dismissed: true, version: "v2" }),
      credentials: "same-origin",
    }).catch(() => undefined);
  };

  const spotlightFactory =
    window.VendorGuidedTour && typeof window.VendorGuidedTour.createSpotlightTour === "function"
      ? window.VendorGuidedTour.createSpotlightTour
      : null;

  const guidedTour = spotlightFactory
    ? spotlightFactory({
        mount: root,
        overlay: tourOverlay instanceof HTMLElement ? tourOverlay : null,
        steps: [
          {
            id: "merge_candidates",
            selector: "[data-tour-example='merge_candidates']",
            title: "Step A: Candidate Check",
            body: "Use typeahead search to select survivor and source vendors instead of typing raw IDs.",
            placement: "bottom",
            padding: 12,
            optional: true,
            beforeEnter: () => {
              focusMergePanel("candidate");
              showTourExample("merge_candidates");
            },
          },
          {
            id: "merge_conflicts",
            selector: "[data-tour-example='merge_conflicts']",
            title: "Step B: Conflict Decisions",
            body: "Review each field conflict and choose how values should be retained.",
            placement: "bottom",
            padding: 12,
            optional: true,
            beforeEnter: () => {
              focusMergePanel("conflicts");
              showTourExample("merge_conflicts");
            },
          },
          {
            id: "merge_offering_collisions",
            selector: "[data-tour-example='merge_offering_collisions']",
            title: "Offering Collisions",
            body: "Handle offering collisions explicitly to merge into a target or keep both with rename behavior.",
            placement: "bottom",
            padding: 12,
            optional: true,
            beforeEnter: () => {
              focusMergePanel("conflicts");
              showTourExample("merge_offering_collisions");
            },
          },
          {
            id: "merge_final_ack",
            selector: "[data-tour-example='merge_final_ack']",
            title: "Step C: Final Confirmation",
            body: "Execution requires this acknowledgement before merge can proceed.",
            placement: "top",
            padding: 10,
            optional: true,
            beforeEnter: () => {
              focusMergePanel("confirm");
              showTourExample("merge_final_ack");
            },
          },
        ],
        onPersistDismiss: () => persistTourDismiss(),
        onEnd: () => {
          clearTourExamples();
        },
      })
    : null;

  const endTour = (reason, persist) => {
    if (!guidedTour) return;
    guidedTour.end(reason, persist);
  };

  const openTour = (trigger) => {
    if (!guidedTour) return;
    clearTourExamples();
    guidedTour.start({ trigger: trigger instanceof HTMLElement ? trigger : null });
  };

  if (replayButton instanceof HTMLButtonElement) {
    replayButton.addEventListener("click", () => {
      if (guidedTour && guidedTour.isOpen()) {
        endTour("replay", false);
      }
      openTour(replayButton);
    });
  }

  if (guidedEnabled && showTourOnLoad) {
    openTour(replayButton instanceof HTMLElement ? replayButton : null);
  }
})();
