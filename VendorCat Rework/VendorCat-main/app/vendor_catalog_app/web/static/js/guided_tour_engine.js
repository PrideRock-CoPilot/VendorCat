(() => {
  const globalScope = window;
  if (globalScope.VendorGuidedTour && typeof globalScope.VendorGuidedTour.createSpotlightTour === "function") {
    return;
  }

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const safeText = (value) => String(value || "").trim();
  const isVisible = (element) =>
    element instanceof HTMLElement &&
    element.getClientRects().length > 0 &&
    element.offsetWidth > 0 &&
    element.offsetHeight > 0;

  const createElement = (tag, className) => {
    const element = document.createElement(tag);
    if (className) {
      element.className = className;
    }
    return element;
  };

  const getStepId = (step, index) => safeText(step?.id) || `step_${index + 1}`;

  const createSpotlightTour = (config) => {
    const options = config && typeof config === "object" ? config : {};
    const steps = Array.isArray(options.steps) ? options.steps.filter((step) => !!step) : [];
    if (!steps.length) {
      return {
        start: () => undefined,
        end: () => undefined,
        isOpen: () => false,
      };
    }

    const mountHost = options.mount instanceof HTMLElement ? options.mount : document.body;
    let overlay = options.overlay instanceof HTMLElement ? options.overlay : mountHost.querySelector("[data-tour-overlay]");
    if (!(overlay instanceof HTMLElement)) {
      overlay = createElement("div", "guided-tour-overlay is-spotlight");
      overlay.setAttribute("data-tour-overlay", "");
      overlay.hidden = true;
      mountHost.appendChild(overlay);
    }
    overlay.classList.add("guided-tour-overlay", "is-spotlight");
    overlay.hidden = true;
    overlay.replaceChildren();

    const backdrop = createElement("div", "guided-tour-backdrop");
    backdrop.setAttribute("data-tour-backdrop", "");

    const spotlight = createElement("div", "guided-tour-spotlight");
    spotlight.setAttribute("data-tour-spotlight", "");

    const card = createElement("section", "guided-tour-card guided-tour-popover");
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
    card.tabIndex = -1;

    const titleId = `guided-tour-title-${Math.random().toString(36).slice(2, 10)}`;
    const title = createElement("h3", "guided-tour-title");
    title.id = titleId;
    const body = createElement("p", "guided-tour-body");
    const stepLabel = createElement("p", "guided-tour-step-label");
    card.setAttribute("aria-labelledby", titleId);

    const actions = createElement("div", "guided-tour-actions");
    const backButton = createElement("button", "button-link subtle");
    backButton.type = "button";
    backButton.textContent = "Back";
    backButton.setAttribute("data-tour-back", "");
    const nextButton = createElement("button");
    nextButton.type = "button";
    nextButton.textContent = "Next";
    nextButton.setAttribute("data-tour-next", "");
    const dismissButton = createElement("button", "button-link subtle");
    dismissButton.type = "button";
    dismissButton.textContent = "Dismiss";
    dismissButton.setAttribute("data-tour-dismiss", "");
    actions.append(backButton, nextButton, dismissButton);

    card.append(title, body, stepLabel, actions);
    overlay.append(backdrop, spotlight, card);

    let tourIndex = 0;
    let activeTarget = null;
    let active = false;
    let restoreFocusTarget = null;
    let replayTrigger = null;
    const margin = 12;
    const gap = 12;

    const clearActiveTarget = () => {
      if (activeTarget instanceof HTMLElement) {
        activeTarget.classList.remove("guided-tour-target-active");
      }
      activeTarget = null;
    };

    const resolveTarget = (selector) => {
      const query = safeText(selector);
      if (!query) return null;
      try {
        return document.querySelector(query);
      } catch (_error) {
        return null;
      }
    };

    const placeCardAt = (top, left) => {
      const rect = card.getBoundingClientRect();
      const maxTop = Math.max(margin, window.innerHeight - rect.height - margin);
      const maxLeft = Math.max(margin, window.innerWidth - rect.width - margin);
      card.style.top = `${Math.round(clamp(top, margin, maxTop))}px`;
      card.style.left = `${Math.round(clamp(left, margin, maxLeft))}px`;
    };

    const positionCard = (targetRect, placement) => {
      if (!targetRect) {
        const rect = card.getBoundingClientRect();
        placeCardAt((window.innerHeight - rect.height) / 2, (window.innerWidth - rect.width) / 2);
        return;
      }

      const cardRect = card.getBoundingClientRect();
      const preferred = safeText(placement).toLowerCase() || "bottom";
      const candidates = preferred === "center" ? ["center"] : [preferred, "bottom", "top", "right", "left", "center"];

      for (const candidate of candidates) {
        if (candidate === "center") {
          placeCardAt((window.innerHeight - cardRect.height) / 2, (window.innerWidth - cardRect.width) / 2);
          return;
        }
        if (candidate === "bottom") {
          const top = targetRect.bottom + gap;
          if (top + cardRect.height + margin <= window.innerHeight) {
            placeCardAt(top, targetRect.left + (targetRect.width - cardRect.width) / 2);
            return;
          }
          continue;
        }
        if (candidate === "top") {
          const top = targetRect.top - cardRect.height - gap;
          if (top >= margin) {
            placeCardAt(top, targetRect.left + (targetRect.width - cardRect.width) / 2);
            return;
          }
          continue;
        }
        if (candidate === "right") {
          const left = targetRect.right + gap;
          if (left + cardRect.width + margin <= window.innerWidth) {
            placeCardAt(targetRect.top + (targetRect.height - cardRect.height) / 2, left);
            return;
          }
          continue;
        }
        if (candidate === "left") {
          const left = targetRect.left - cardRect.width - gap;
          if (left >= margin) {
            placeCardAt(targetRect.top + (targetRect.height - cardRect.height) / 2, left);
            return;
          }
        }
      }

      placeCardAt((window.innerHeight - cardRect.height) / 2, (window.innerWidth - cardRect.width) / 2);
    };

    const positionSpotlight = (step, target) => {
      clearActiveTarget();
      if (!isVisible(target)) {
        spotlight.hidden = true;
        positionCard(null, "center");
        return;
      }

      activeTarget = target;
      activeTarget.classList.add("guided-tour-target-active");
      const padding = Number.parseInt(String(step?.padding ?? "10"), 10);
      const safePadding = Number.isFinite(padding) ? Math.max(4, padding) : 10;
      const rect = activeTarget.getBoundingClientRect();
      const top = Math.max(margin, rect.top - safePadding);
      const left = Math.max(margin, rect.left - safePadding);
      const width = Math.min(window.innerWidth - left - margin, rect.width + safePadding * 2);
      const height = Math.min(window.innerHeight - top - margin, rect.height + safePadding * 2);
      spotlight.hidden = false;
      spotlight.style.top = `${Math.round(top)}px`;
      spotlight.style.left = `${Math.round(left)}px`;
      spotlight.style.width = `${Math.round(width)}px`;
      spotlight.style.height = `${Math.round(height)}px`;
      positionCard(rect, step?.placement);
    };

    const renderStep = () => {
      if (!active) return;
      const step = steps[tourIndex] || {};
      if (typeof step.beforeEnter === "function") {
        try {
          step.beforeEnter({ index: tourIndex, step });
        } catch (_error) {
          // Keep the tour resilient if step hooks fail.
        }
      }

      title.textContent = safeText(step.title) || "Guided Tour";
      body.textContent = safeText(step.body) || "";
      stepLabel.textContent = `${tourIndex + 1} of ${steps.length}`;
      backButton.disabled = tourIndex <= 0;
      nextButton.textContent = tourIndex >= steps.length - 1 ? "Finish" : "Next";

      const target = resolveTarget(step.selector);
      if (isVisible(target)) {
        target.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
      }
      window.requestAnimationFrame(() => {
        positionSpotlight(step, target);
      });

      if (typeof options.onStepChange === "function") {
        try {
          options.onStepChange({
            index: tourIndex,
            step,
            stepId: getStepId(step, tourIndex),
          });
        } catch (_error) {
          // Ignore logging callback failures.
        }
      }
    };

    const onViewportChange = () => {
      if (!active) return;
      renderStep();
    };

    const detachGlobalListeners = () => {
      document.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onViewportChange, true);
    };

    const attachGlobalListeners = () => {
      document.addEventListener("keydown", onKeyDown, true);
      window.addEventListener("resize", onViewportChange);
      window.addEventListener("scroll", onViewportChange, true);
    };

    const endTour = (reason = "dismiss", persist = false) => {
      if (!active) return;
      active = false;
      overlay.hidden = true;
      detachGlobalListeners();
      clearActiveTarget();

      if (persist && typeof options.onPersistDismiss === "function") {
        try {
          options.onPersistDismiss({
            reason,
            index: tourIndex,
            step: steps[tourIndex] || {},
            stepId: getStepId(steps[tourIndex], tourIndex),
          });
        } catch (_error) {
          // Ignore persistence callback failures.
        }
      }

      if (typeof options.onEnd === "function") {
        try {
          options.onEnd({
            reason,
            persisted: persist,
            index: tourIndex,
            step: steps[tourIndex] || {},
            stepId: getStepId(steps[tourIndex], tourIndex),
          });
        } catch (_error) {
          // Ignore end callback failures.
        }
      }

      const focusTarget =
        replayTrigger instanceof HTMLElement
          ? replayTrigger
          : restoreFocusTarget instanceof HTMLElement
            ? restoreFocusTarget
            : null;
      if (focusTarget) {
        focusTarget.focus({ preventScroll: true });
      }
    };

    const moveStep = (delta) => {
      const nextIndex = tourIndex + delta;
      if (nextIndex < 0) return;
      if (nextIndex >= steps.length) {
        endTour("finish", true);
        return;
      }
      tourIndex = nextIndex;
      renderStep();
    };

    const onKeyDown = (event) => {
      if (!active) return;
      if (event.key === "Escape") {
        event.preventDefault();
        endTour("escape", true);
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        moveStep(1);
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        moveStep(-1);
      }
    };

    const onOverlayClick = (event) => {
      if (!active) return;
      if (event.target === backdrop || event.target === overlay) {
        endTour("backdrop", true);
      }
    };

    backdrop.addEventListener("click", onOverlayClick);
    overlay.addEventListener("click", onOverlayClick);
    backButton.addEventListener("click", () => moveStep(-1));
    nextButton.addEventListener("click", () => moveStep(1));
    dismissButton.addEventListener("click", () => endTour("dismiss", true));

    const startTour = ({ trigger } = {}) => {
      replayTrigger = trigger instanceof HTMLElement ? trigger : null;
      restoreFocusTarget =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : replayTrigger instanceof HTMLElement
            ? replayTrigger
            : null;
      tourIndex = 0;
      active = true;
      overlay.hidden = false;
      attachGlobalListeners();
      renderStep();
      window.requestAnimationFrame(() => {
        nextButton.focus({ preventScroll: true });
      });
    };

    return {
      start: startTour,
      end: endTour,
      isOpen: () => active,
    };
  };

  globalScope.VendorGuidedTour = {
    createSpotlightTour,
  };
})();
