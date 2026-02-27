(() => {
  const root = document.querySelector("[data-imports-guided]");
  if (!root) {
    return;
  }

  const toBool = (value) => String(value || "").toLowerCase() === "true";
  const hasPreview = toBool(root.dataset.hasPreview);
  const hasResults = toBool(root.dataset.hasResults);
  const guidedEnabled = toBool(root.dataset.guidedEnabled);
  const showTourOnLoad = toBool(root.dataset.showTour);
  const requiresProfileConfirmation = toBool(root.dataset.requiresProfileConfirmation);
  const eventUrl = String(root.dataset.eventUrl || "").trim();
  const tourDismissUrl = String(root.dataset.tourDismissUrl || "").trim();
  const csrfToken = String(document.querySelector("meta[name='csrf-token']")?.getAttribute("content") || "").trim();

  const sendEvent = (eventType, payload) => {
    if (!eventUrl) return;
    const body = {
      event_type: String(eventType || "").trim(),
      payload: payload && typeof payload === "object" ? payload : {},
    };
    fetch(eventUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "x-csrf-token": csrfToken } : {}),
      },
      body: JSON.stringify(body),
      credentials: "same-origin",
    }).catch(() => undefined);
  };

  const stepNames = {
    1: "upload_file",
    2: "system_check",
    3: "fix_matches",
    4: "review_confirm",
    5: "stage_import_complete",
  };
  const absoluteMaxStep = 5;
  const maxStep = hasResults ? 5 : (hasPreview ? 4 : 2);
  const minStep = 1;
  let currentStep = Number.parseInt(String(root.dataset.initialStep || "1"), 10);
  if (!Number.isFinite(currentStep)) currentStep = 1;
  currentStep = Math.max(minStep, Math.min(maxStep, currentStep));

  const stepButtons = Array.from(root.querySelectorAll("[data-step-jump]"));
  const stepPanels = Array.from(root.querySelectorAll(".guided-step-panel[data-step-panel]"));
  const backButton = document.getElementById("guided-step-back");
  const nextButton = document.getElementById("guided-step-next");

  const filesInput = document.getElementById("ingestion-files-input");
  const layoutSelect = document.getElementById("layout-select");
  const flowModeInput = document.getElementById("flow-mode-input");
  const modeQuickButton = document.getElementById("mode-quick-button");
  const modeWizardButton = document.getElementById("mode-wizard-button");
  const modeLabel = document.getElementById("mode-label");
  const formatSelect = document.getElementById("format-hint-select");
  const expertToggle = document.getElementById("expert-mode-toggle");
  const expertPanel = document.getElementById("expert-mode-panel");
  const delimiterBlock = root.querySelector("[data-format-option='delimiter']");
  const jsonBlock = root.querySelector("[data-format-option='json']");
  const xmlBlock = root.querySelectorAll("[data-format-option='xml']");

  const canAdvanceFrom = (step) => {
    if (step === 1) {
      if (hasPreview) return true;
      const hasLayout = !!String(layoutSelect?.value || "").trim();
      const fileCount = filesInput?.files?.length || 0;
      return hasLayout && fileCount > 0;
    }
    if (step === 2) return hasPreview;
    if (step === 3) return hasPreview;
    if (step === 4) return hasResults;
    return true;
  };

  const setModeLabel = (mode) => {
    if (!modeLabel) return;
    if (mode === "quick") {
      modeLabel.textContent = "Strict template mode: headers must match the approved layout.";
      return;
    }
    modeLabel.textContent = "Flexible wizard mode: parser options and remap controls enabled.";
  };

  const setFlowMode = (mode) => {
    const resolved = String(mode || "").toLowerCase() === "wizard" ? "wizard" : "quick";
    if (flowModeInput) {
      flowModeInput.value = resolved;
    }
    if (modeQuickButton) {
      modeQuickButton.classList.toggle("active", resolved === "quick");
    }
    if (modeWizardButton) {
      modeWizardButton.classList.toggle("active", resolved === "wizard");
    }
    setModeLabel(resolved);
  };

  const toggleFormatBlocks = () => {
    if (!formatSelect) return;
    const value = String(formatSelect.value || "auto").toLowerCase();
    const showDelimiter = value === "auto" || value === "csv" || value === "tsv" || value === "delimited";
    const showJson = value === "auto" || value === "json";
    const showXml = value === "auto" || value === "xml";
    if (delimiterBlock) delimiterBlock.style.display = showDelimiter ? "" : "none";
    if (jsonBlock) jsonBlock.style.display = showJson ? "" : "none";
    xmlBlock.forEach((item) => {
      item.style.display = showXml ? "" : "none";
    });
  };

  const extension = (fileName) => {
    const value = String(fileName || "").trim().toLowerCase();
    const idx = value.lastIndexOf(".");
    if (idx <= -1 || idx >= value.length - 1) return "";
    return value.slice(idx + 1);
  };

  const inferModeFromUpload = () => {
    if (!filesInput || !filesInput.files || !filesInput.files.length) return;
    const ext = extension(filesInput.files[0].name || "");
    if (ext === "csv" || ext === "tsv") {
      setFlowMode("quick");
    } else {
      setFlowMode("wizard");
    }
    if (formatSelect && ["csv", "tsv", "json", "xml", "delimited"].includes(ext)) {
      formatSelect.value = ext;
    }
    toggleFormatBlocks();
  };

  const showStep = (stepNumber, options = {}) => {
    const force = !!options.force;
    const effectiveMaxStep = force ? absoluteMaxStep : maxStep;
    currentStep = Math.max(minStep, Math.min(effectiveMaxStep, stepNumber));
    root.setAttribute("data-current-step", String(currentStep));

    stepPanels.forEach((panel) => {
      const panelStep = Number.parseInt(String(panel.getAttribute("data-step-panel") || "0"), 10);
      panel.hidden = panelStep !== currentStep;
      panel.classList.toggle("is-active", panelStep === currentStep);
    });

    stepButtons.forEach((button) => {
      const step = Number.parseInt(String(button.getAttribute("data-step-jump") || "0"), 10);
      const disabled = force ? false : step > maxStep;
      button.disabled = disabled;
      button.classList.toggle("is-active", step === currentStep);
      button.classList.toggle("is-complete", step < currentStep && !disabled);
    });

    if (backButton) {
      backButton.disabled = currentStep <= minStep;
    }
    if (nextButton) {
      const canForward = force ? currentStep < absoluteMaxStep : currentStep < maxStep && canAdvanceFrom(currentStep);
      nextButton.disabled = !canForward;
      nextButton.textContent = currentStep === effectiveMaxStep ? "Complete" : "Next";
    }

    sendEvent("imports_guided_step_view", { step: stepNames[currentStep] || "upload_file" });
  };

  if (backButton) {
    backButton.addEventListener("click", () => {
      if (currentStep > minStep) {
        showStep(currentStep - 1);
      }
    });
  }
  if (nextButton) {
    nextButton.addEventListener("click", () => {
      if (currentStep < maxStep && canAdvanceFrom(currentStep)) {
        showStep(currentStep + 1);
      }
    });
  }

  stepButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = Number.parseInt(String(button.getAttribute("data-step-jump") || "0"), 10);
      if (!Number.isFinite(target)) return;
      if (target > maxStep || target < minStep) return;
      showStep(target);
    });
  });

  Array.from(root.querySelectorAll("[data-continue-step]")).forEach((button) => {
    button.addEventListener("click", () => {
      const next = Number.parseInt(String(button.getAttribute("data-continue-step") || "0"), 10);
      if (!Number.isFinite(next)) return;
      showStep(next);
    });
  });

  if (modeQuickButton) {
    modeQuickButton.addEventListener("click", () => {
      setFlowMode("quick");
    });
  }
  if (modeWizardButton) {
    modeWizardButton.addEventListener("click", () => {
      setFlowMode("wizard");
    });
  }
  if (filesInput) {
    filesInput.addEventListener("change", inferModeFromUpload);
  }
  if (formatSelect) {
    formatSelect.addEventListener("change", toggleFormatBlocks);
  }

  if (expertToggle && expertPanel) {
    expertToggle.addEventListener("click", () => {
      const opening = !!expertPanel.hidden;
      expertPanel.hidden = !expertPanel.hidden;
      expertToggle.textContent = expertPanel.hidden ? "Open Expert Mode" : "Close Expert Mode";
      expertToggle.setAttribute("aria-expanded", expertPanel.hidden ? "false" : "true");
      if (opening) {
        sendEvent("imports_guided_expert_mode_opened", {});
      }
    });
  }

  const mappingSelects = Array.from(root.querySelectorAll(".mapping-target-select"));
  const mappingSearchInput = document.getElementById("mapping-target-search");
  let requiredTargets = [];
  try {
    const raw = String(root.querySelector("[data-mapping-progress]")?.getAttribute("data-required-targets") || "[]");
    requiredTargets = JSON.parse(raw);
  } catch (_err) {
    requiredTargets = [];
  }

  const refreshMappingMetrics = () => {
    if (!mappingSelects.length) return;
    const selectedValues = mappingSelects
      .map((select) => String(select.value || "").trim())
      .filter((value) => !!value);
    const selectedSet = new Set(selectedValues);
    const mappedCount = selectedValues.length;
    const unmappedCount = Math.max(0, mappingSelects.length - mappedCount);
    const requiredRemaining = requiredTargets.reduce((count, value) => {
      const key = String(value || "").trim();
      if (!key) return count;
      return selectedSet.has(key) ? count : count + 1;
    }, 0);
    const mappedEl = document.getElementById("mapped-count");
    const unmappedEl = document.getElementById("unmapped-count");
    const requiredEl = document.getElementById("required-remaining-count");
    if (mappedEl) mappedEl.textContent = String(mappedCount);
    if (unmappedEl) unmappedEl.textContent = String(unmappedCount);
    if (requiredEl) requiredEl.textContent = String(requiredRemaining);
  };

  const applyTargetFilter = (query) => {
    const text = String(query || "").trim().toLowerCase();
    mappingSelects.forEach((select) => {
      Array.from(select.querySelectorAll("optgroup")).forEach((group) => {
        let hasVisible = false;
        Array.from(group.querySelectorAll("option")).forEach((option) => {
          const label = String(option.dataset.optionLabel || option.textContent || "").toLowerCase();
          const area = String(option.dataset.optionGroup || "").toLowerCase();
          const visible = !text || label.includes(text) || area.includes(text);
          option.hidden = !visible;
          if (visible) hasVisible = true;
        });
        group.hidden = !hasVisible;
      });
    });
  };

  mappingSelects.forEach((select) => {
    select.addEventListener("change", refreshMappingMetrics);
  });
  if (mappingSearchInput) {
    mappingSearchInput.addEventListener("input", () => {
      applyTargetFilter(mappingSearchInput.value || "");
    });
  }
  refreshMappingMetrics();

  const validationRows = Array.from(root.querySelectorAll("[data-validation-row]"));
  const filterButtons = Array.from(root.querySelectorAll("[data-status-filter]"));
  const applyValidationFilter = (filterKey) => {
    const selected = String(filterKey || "problem").toLowerCase();
    validationRows.forEach((row) => {
      const status = String(row.getAttribute("data-status") || "").toLowerCase();
      let visible = true;
      if (selected === "problem") {
        visible = status === "error" || status === "blocked" || status === "review";
      } else if (selected !== "all") {
        visible = status === selected;
      }
      row.hidden = !visible;
    });
  };

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      applyValidationFilter(button.getAttribute("data-status-filter") || "problem");
    });
  });
  applyValidationFilter("problem");

  Array.from(root.querySelectorAll(".go-map")).forEach((button) => {
    button.addEventListener("click", () => {
      showStep(3);
    });
  });

  const previewRows = Array.from(root.querySelectorAll("tr[data-row-index]"));
  const allRows = () => previewRows.map((row) => ({
    row,
    action: row.querySelector("[data-import-action-select]"),
  })).filter((item) => !!item.row && !!item.action);

  const syncMergeHiddenTarget = (row) => {
    const labelInput = row.querySelector("[data-merge-target-label-input]");
    const hiddenInput = row.querySelector("[data-merge-target-hidden]");
    if (!(labelInput instanceof HTMLInputElement) || !(hiddenInput instanceof HTMLInputElement)) return;
    const listId = String(labelInput.getAttribute("list") || "").trim();
    if (!listId) return;
    const list = document.getElementById(listId);
    if (!(list instanceof HTMLDataListElement)) return;
    const entered = String(labelInput.value || "").trim();
    const options = Array.from(list.querySelectorAll("option"));
    const matched = options.find((option) => String(option.value || "").trim() === entered);
    hiddenInput.value = matched ? String(matched.getAttribute("data-target-id") || "").trim() : "";
  };

  const refreshMergeTargetAvailability = (row) => {
    const actionSelect = row.querySelector("[data-import-action-select]");
    const labelInput = row.querySelector("[data-merge-target-label-input]");
    if (!(actionSelect instanceof HTMLSelectElement) || !(labelInput instanceof HTMLInputElement)) return;
    const mergeEnabled = String(actionSelect.value || "").toLowerCase() === "merge";
    labelInput.disabled = !mergeEnabled;
  };

  const setAllActions = (value, noErrorsOnly) => {
    allRows().forEach((item) => {
      const status = String(item.row.getAttribute("data-row-status") || "").toLowerCase();
      if (noErrorsOnly && status === "error") return;
      item.action.value = value;
      item.action.dispatchEvent(new Event("change", { bubbles: true }));
    });
  };

  const bulkDefaultSelect = document.getElementById("bulk-action-default");
  if (bulkDefaultSelect instanceof HTMLSelectElement) {
    bulkDefaultSelect.addEventListener("change", () => {
      const value = String(bulkDefaultSelect.value || "").trim().toLowerCase();
      if (!value) return;
      setAllActions(value, true);
    });
  }
  const allNewButton = document.getElementById("bulk-action-all-new");
  const allMergeButton = document.getElementById("bulk-action-all-merge");
  const allSkipButton = document.getElementById("bulk-action-all-skip");
  if (allNewButton) allNewButton.addEventListener("click", () => setAllActions("new", false));
  if (allMergeButton) allMergeButton.addEventListener("click", () => setAllActions("merge", false));
  if (allSkipButton) allSkipButton.addEventListener("click", () => setAllActions("skip", false));

  previewRows.forEach((row) => {
    const actionSelect = row.querySelector("[data-import-action-select]");
    const labelInput = row.querySelector("[data-merge-target-label-input]");
    refreshMergeTargetAvailability(row);
    if (actionSelect) {
      actionSelect.addEventListener("change", () => refreshMergeTargetAvailability(row));
    }
    if (labelInput) {
      labelInput.addEventListener("input", () => syncMergeHiddenTarget(row));
      labelInput.addEventListener("change", () => syncMergeHiddenTarget(row));
      labelInput.addEventListener("blur", () => syncMergeHiddenTarget(row));
    }
  });

  const applyForm = document.getElementById("apply-form");
  if (applyForm instanceof HTMLFormElement) {
    applyForm.addEventListener("submit", (event) => {
      const finalConfirm = document.getElementById("guided-final-confirm");
      if (finalConfirm instanceof HTMLInputElement && !finalConfirm.checked) {
        event.preventDefault();
        window.alert("Final confirmation is required before apply.");
        return;
      }
      if (requiresProfileConfirmation) {
        const lowConfidenceConfirm = document.getElementById("guided-profile-continue-confirm");
        if (lowConfidenceConfirm instanceof HTMLInputElement && !lowConfidenceConfirm.checked) {
          event.preventDefault();
          window.alert("Low-confidence apply requires explicit confirmation.");
          return;
        }
      }
    });
  }

  const lowConfidenceCheckbox = document.getElementById("guided-profile-continue-confirm");
  if (lowConfidenceCheckbox instanceof HTMLInputElement) {
    lowConfidenceCheckbox.addEventListener("change", () => {
      if (lowConfidenceCheckbox.checked) {
        sendEvent("imports_guided_low_confidence_continue", { source: "review_confirm_checkbox" });
      }
    });
  }

  const tourOverlay = root.querySelector("[data-tour-overlay]");
  const replayButton = root.querySelector("[data-replay-tour]");
  const tourDemoBoard = root.querySelector("[data-tour-demo-board]");
  const tourDemoCards = Array.from(root.querySelectorAll("[data-tour-example]"));

  const showTourExample = (exampleId) => {
    if (!(tourDemoBoard instanceof HTMLElement)) return;
    const targetId = String(exampleId || "").trim();
    tourDemoBoard.hidden = false;
    tourDemoCards.forEach((card) => {
      if (!(card instanceof HTMLElement)) return;
      card.hidden = String(card.getAttribute("data-tour-example") || "").trim() !== targetId;
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

  const tourStepToPanel = {
    imports_upload: 1,
    imports_mapping_profile: 1,
    imports_expert_mode: 1,
    imports_confidence: 2,
    imports_problem_rows: 4,
    imports_final_confirm: 4,
  };
  const activateWalkthroughStep = (stepId) => {
    const panelStep = Number.parseInt(String(tourStepToPanel[String(stepId || "").trim()] || "1"), 10);
    showStep(panelStep, { force: true });
    showTourExample(stepId);
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
            id: "imports_upload",
            selector: "[data-tour-example='imports_upload']",
            title: "Upload File",
            body: "Start here with your file and layout. The wizard opens with only required controls.",
            placement: "bottom",
            padding: 12,
            optional: true,
            beforeEnter: () => {
              activateWalkthroughStep("imports_upload");
            },
          },
          {
            id: "imports_mapping_profile",
            selector: "[data-tour-example='imports_mapping_profile']",
            title: "Pick A Mapping Profile",
            body: "Use a saved profile when available to reduce manual field mapping.",
            placement: "bottom",
            padding: 10,
            optional: true,
            beforeEnter: () => {
              activateWalkthroughStep("imports_mapping_profile");
            },
          },
          {
            id: "imports_expert_mode",
            selector: "[data-tour-example='imports_expert_mode']",
            title: "Expert Controls",
            body: "Advanced parser options stay hidden unless you open Expert Mode.",
            placement: "bottom",
            padding: 10,
            optional: true,
            beforeEnter: () => {
              activateWalkthroughStep("imports_expert_mode");
            },
          },
          {
            id: "imports_confidence",
            selector: "[data-tour-example='imports_confidence']",
            title: "System Check Confidence",
            body: "Review confidence and reasons before moving into mapping and review.",
            placement: "bottom",
            padding: 12,
            optional: true,
            beforeEnter: () => {
              activateWalkthroughStep("imports_confidence");
            },
          },
          {
            id: "imports_problem_rows",
            selector: "[data-tour-example='imports_problem_rows']",
            title: "Problem Rows First",
            body: "These filters focus your review on rows that need attention before apply.",
            placement: "bottom",
            padding: 10,
            optional: true,
            beforeEnter: () => {
              activateWalkthroughStep("imports_problem_rows");
            },
          },
          {
            id: "imports_final_confirm",
            selector: "[data-tour-example='imports_final_confirm']",
            title: "Final Safety Confirmation",
            body: "Apply remains blocked until you explicitly confirm the final review checkbox.",
            placement: "top",
            padding: 10,
            optional: true,
            beforeEnter: () => {
              activateWalkthroughStep("imports_final_confirm");
            },
          },
        ],
        onPersistDismiss: () => persistTourDismiss(),
        onEnd: () => {
          clearTourExamples();
          if (currentStep > maxStep) {
            showStep(maxStep);
          }
        },
        onStepChange: ({ stepId }) => {
          sendEvent("imports_guided_step_view", {
            step: "tour",
            tour_step_id: String(stepId || ""),
            surface: "imports",
          });
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

  const initialMode = String(flowModeInput?.value || "quick").toLowerCase() === "wizard" ? "wizard" : "quick";
  setFlowMode(initialMode);
  toggleFormatBlocks();
  showStep(hasResults ? 5 : currentStep);
  if (guidedEnabled && showTourOnLoad) {
    openTour(replayButton instanceof HTMLElement ? replayButton : null);
  }
})();
