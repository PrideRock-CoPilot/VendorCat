(() => {
  const bindTypeahead = ({ selector, endpoint, valueKey }) => {
    const inputs = Array.from(document.querySelectorAll(selector));
    inputs.forEach((input) => {
      if (!(input instanceof HTMLInputElement)) {
        return;
      }
      if (input.dataset.adminSearchBound === "1") {
        return;
      }
      const results = input.parentElement?.querySelector(".typeahead-results");
      if (!(results instanceof HTMLElement)) {
        input.dataset.adminSearchBound = "1";
        return;
      }

      let timer = 0;
      let seq = 0;
      const hide = () => {
        results.innerHTML = "";
        results.classList.add("hidden");
      };

      const render = (items) => {
        results.innerHTML = "";
        const safeItems = Array.isArray(items) ? items : [];
        safeItems.forEach((item) => {
          const label = String(item.label || item[valueKey] || "").trim();
          const value = String(item[valueKey] || "").trim();
          const displayName = String(item.display_name || "").trim();
          if (!value) {
            return;
          }
          const option = document.createElement("button");
          option.type = "button";
          option.className = "typeahead-option";
          option.textContent = label || value;
          option.addEventListener("click", () => {
            input.value = value;
            if (displayName) {
              input.dataset.displayName = displayName;
            } else {
              delete input.dataset.displayName;
            }
            input.dispatchEvent(new Event("input", { bubbles: true }));
            hide();
          });
          results.appendChild(option);
        });
        if (!results.children.length) {
          hide();
          return;
        }
        results.classList.remove("hidden");
      };

      const search = async () => {
        const query = String(input.value || "").trim();
        if (!query) {
          hide();
          return;
        }
        const nextSeq = seq + 1;
        seq = nextSeq;
        try {
          const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}&limit=20`);
          if (!response.ok) {
            hide();
            return;
          }
          const payload = await response.json();
          if (nextSeq !== seq) {
            return;
          }
          render(payload.items || []);
        } catch {
          hide();
        }
      };

      input.addEventListener("input", () => {
        if (timer) {
          window.clearTimeout(timer);
        }
        timer = window.setTimeout(search, 150);
      });

      document.addEventListener("click", (event) => {
        if (!results.contains(event.target) && event.target !== input) {
          hide();
        }
      });

      input.dataset.adminSearchBound = "1";
    });
  };

  const initTabs = () => {
    const tabRoot = document.querySelector("[data-admin-tabs]");
    if (!(tabRoot instanceof HTMLElement)) {
      return;
    }
    const tabs = Array.from(tabRoot.querySelectorAll("[data-admin-tab]"));
    const panels = Array.from(tabRoot.querySelectorAll("[data-admin-tab-panel]"));
    const activeTab = tabs.find((tab) => tab.classList.contains("is-active"));
    const activeTabValue = String(activeTab?.getAttribute("data-admin-tab") || "users").trim().toLowerCase();
    const param = new URLSearchParams(window.location.search).get("tab");

    const activate = (tabKey) => {
      const selected = String(tabKey || "users").trim().toLowerCase();
      tabs.forEach((tab) => {
        const tabValue = String(tab.getAttribute("data-admin-tab") || "").trim().toLowerCase();
        const isActive = tabValue === selected;
        tab.classList.toggle("is-active", isActive);
        tab.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      panels.forEach((panel) => {
        const panelValue = String(panel.getAttribute("data-admin-tab-panel") || "").trim().toLowerCase();
        panel.hidden = panelValue !== selected;
      });
    };

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const tabValue = String(tab.getAttribute("data-admin-tab") || "users").trim().toLowerCase();
        activate(tabValue);
        const url = new URL(window.location.href);
        url.searchParams.set("tab", tabValue);
        window.history.replaceState({}, "", url.toString());
      });
    });

    activate(param || activeTabValue || "users");
  };

  const initSortableFilterTable = ({
    tableSelector,
    rowSelector,
    searchSelector,
    clearSelector,
    sortButtonAttribute,
    sortIndicatorAttribute,
    defaultSortKey,
    defaultSortDir,
  }) => {
    const table = document.querySelector(tableSelector);
    if (!(table instanceof HTMLTableElement)) {
      return;
    }
    const tbody = table.tBodies[0];
    if (!(tbody instanceof HTMLTableSectionElement)) {
      return;
    }
    const rows = Array.from(tbody.querySelectorAll(rowSelector));
    if (!rows.length) {
      return;
    }

    const searchInput = document.querySelector(searchSelector);
    const clearButton = document.querySelector(clearSelector);
    const sortButtons = Array.from(table.querySelectorAll(`[${sortButtonAttribute}]`));
    const indicators = Array.from(table.querySelectorAll(`[${sortIndicatorAttribute}]`));
    const indicatorByKey = {};
    indicators.forEach((el) => {
      const key = String(el.getAttribute(sortIndicatorAttribute) || "").trim().toLowerCase();
      if (key) {
        indicatorByKey[key] = el;
      }
    });

    const state = {
      key: String(defaultSortKey || "updated").trim().toLowerCase(),
      dir: String(defaultSortDir || "desc").trim().toLowerCase(),
    };

    const dataValue = (row, key) => {
      const prop = `sort${String(key || "").charAt(0).toUpperCase()}${String(key || "").slice(1)}`;
      return String(row.dataset[prop] || "");
    };

    const parseDate = (value) => {
      const parsed = Date.parse(String(value || "").trim());
      return Number.isNaN(parsed) ? 0 : parsed;
    };

    const compareRows = (left, right) => {
      const key = state.key;
      const leftValue = dataValue(left, key);
      const rightValue = dataValue(right, key);
      let result = 0;
      if (key === "updated") {
        result = parseDate(leftValue) - parseDate(rightValue);
      } else if (key === "active") {
        result = Number.parseInt(leftValue || "0", 10) - Number.parseInt(rightValue || "0", 10);
      } else {
        result = leftValue.localeCompare(rightValue);
      }
      if (result === 0) {
        result = dataValue(left, key).localeCompare(dataValue(right, key));
      }
      return state.dir === "desc" ? -result : result;
    };

    const updateIndicators = () => {
      Object.keys(indicatorByKey).forEach((key) => {
        const node = indicatorByKey[key];
        if (!(node instanceof HTMLElement)) {
          return;
        }
        if (key !== state.key) {
          node.textContent = "";
          return;
        }
        node.textContent = state.dir === "asc" ? "▲" : "▼";
      });
    };

    const apply = () => {
      const query = String(searchInput instanceof HTMLInputElement ? searchInput.value : "").trim().toLowerCase();
      const visible = [];
      rows.forEach((row) => {
        const haystack = String(row.dataset.search || "").toLowerCase();
        const match = !query || haystack.includes(query);
        row.classList.toggle("hidden", !match);
        if (match) {
          visible.push(row);
        }
      });
      visible.sort(compareRows);
      visible.forEach((row) => tbody.appendChild(row));
      updateIndicators();
    };

    sortButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const key = String(button.getAttribute(sortButtonAttribute) || "").trim().toLowerCase();
        if (!key) {
          return;
        }
        if (state.key === key) {
          state.dir = state.dir === "asc" ? "desc" : "asc";
        } else {
          state.key = key;
          state.dir = key === "updated" ? "desc" : "asc";
        }
        apply();
      });
    });

    if (searchInput instanceof HTMLInputElement) {
      searchInput.addEventListener("input", apply);
    }
    if (clearButton instanceof HTMLElement && searchInput instanceof HTMLInputElement) {
      clearButton.addEventListener("click", () => {
        searchInput.value = "";
        apply();
        searchInput.focus();
      });
    }

    apply();
  };

  const initUserDrawer = () => {
    const openButton = document.getElementById("open-add-user-drawer");
    const closeButton = document.getElementById("close-add-user-drawer");
    const cancelButton = document.getElementById("cancel-add-user-drawer");
    const drawer = document.getElementById("admin-user-drawer");
    const backdrop = document.getElementById("admin-user-drawer-backdrop");
    const title = document.getElementById("admin-user-drawer-title");
    const subtitle = document.getElementById("admin-user-drawer-subtitle");
    const form = document.getElementById("admin-user-access-form");
    const userInput = document.getElementById("admin-drawer-target-user");
    const hiddenUserInput = document.getElementById("admin-drawer-target-user-hidden");
    const loginPreview = document.getElementById("admin-drawer-login-preview");
    const roleSelect = document.getElementById("admin-drawer-role");
    const scopeSelect = document.getElementById("admin-drawer-scope-level");
    const editButtons = Array.from(document.querySelectorAll(".admin-edit-user-button"));
    const lobActionButtons = Array.from(document.querySelectorAll("[data-lob-action]"));
    const lobCheckboxes = Array.from(document.querySelectorAll("input[data-lob-checkbox]"));

    if (!(drawer instanceof HTMLElement) || !(backdrop instanceof HTMLElement)) {
      return;
    }
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    if (!(userInput instanceof HTMLInputElement)) {
      return;
    }
    if (!(hiddenUserInput instanceof HTMLInputElement)) {
      return;
    }
    if (!(roleSelect instanceof HTMLSelectElement) || !(scopeSelect instanceof HTMLSelectElement)) {
      return;
    }

    const setSelectedLobs = (lobValues) => {
      const selected = new Set((lobValues || []).map((item) => String(item || "").trim()));
      lobCheckboxes.forEach((checkbox) => {
        checkbox.checked = selected.has(String(checkbox.value || "").trim());
      });
    };

    const updateLoginPreview = () => {
      if (!(loginPreview instanceof HTMLInputElement)) {
        return;
      }
      const selectedValue = String(userInput.value || "").trim();
      if (!selectedValue) {
        loginPreview.value = "";
        return;
      }
      const displayName = String(userInput.dataset.displayName || "").trim();
      loginPreview.value = displayName ? `${displayName} (${selectedValue})` : selectedValue;
    };

    const setUserLocked = (locked) => {
      if (locked) {
        userInput.disabled = true;
        userInput.classList.add("admin-locked-input");
        hiddenUserInput.name = "target_user";
        hiddenUserInput.value = String(userInput.value || "");
      } else {
        userInput.disabled = false;
        userInput.classList.remove("admin-locked-input");
        hiddenUserInput.name = "";
        hiddenUserInput.value = "";
      }
    };

    const openDrawer = () => {
      drawer.classList.add("is-open");
      drawer.setAttribute("aria-hidden", "false");
      backdrop.classList.remove("hidden");
      document.body.style.overflow = "hidden";
    };

    const closeDrawer = () => {
      drawer.classList.remove("is-open");
      drawer.setAttribute("aria-hidden", "true");
      backdrop.classList.add("hidden");
      document.body.style.overflow = "";
    };

    const setAddMode = () => {
      form.reset();
      userInput.dataset.displayName = "";
      setUserLocked(false);
      scopeSelect.value = "edit";
      setSelectedLobs([]);
      if (title) {
        title.textContent = "Add User Access";
      }
      if (subtitle) {
        subtitle.textContent = "Select one user, one role, then apply Line of Business access in one save.";
      }
      updateLoginPreview();
    };

    const setEditMode = (button) => {
      const targetUser = String(button.getAttribute("data-target-user") || "").trim();
      const displayName = String(button.getAttribute("data-target-display-name") || "").trim();
      const roleCode = String(button.getAttribute("data-target-role") || "").trim();
      const scopeLevel = String(button.getAttribute("data-target-scope-level") || "edit").trim().toLowerCase();
      const lobCsv = String(button.getAttribute("data-target-lobs") || "").trim();
      const lobValues = lobCsv ? lobCsv.split(",").map((item) => item.trim()).filter((item) => item) : [];

      userInput.value = targetUser;
      userInput.dataset.displayName = displayName;
      roleSelect.value = roleCode;
      scopeSelect.value = ["none", "read", "edit", "full"].includes(scopeLevel) ? scopeLevel : "edit";
      setSelectedLobs(lobValues);
      setUserLocked(true);
      if (title) {
        title.textContent = "Edit User Access";
      }
      if (subtitle) {
        subtitle.textContent = "Login information is locked while editing this user.";
      }
      updateLoginPreview();
    };

    if (openButton instanceof HTMLElement) {
      openButton.addEventListener("click", () => {
        setAddMode();
        openDrawer();
      });
    }
    editButtons.forEach((button) => {
      button.addEventListener("click", () => {
        setEditMode(button);
        openDrawer();
      });
    });
    [closeButton, cancelButton].forEach((button) => {
      if (button instanceof HTMLElement) {
        button.addEventListener("click", closeDrawer);
      }
    });
    backdrop.addEventListener("click", closeDrawer);

    userInput.addEventListener("input", () => {
      if (!userInput.disabled) {
        userInput.dataset.displayName = "";
      }
      updateLoginPreview();
      if (userInput.disabled) {
        hiddenUserInput.value = String(userInput.value || "");
      }
    });

    lobActionButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const action = String(button.getAttribute("data-lob-action") || "").trim().toLowerCase();
        if (action === "all") {
          lobCheckboxes.forEach((checkbox) => {
            checkbox.checked = true;
          });
        } else if (action === "clear") {
          lobCheckboxes.forEach((checkbox) => {
            checkbox.checked = false;
          });
        }
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && drawer.classList.contains("is-open")) {
        closeDrawer();
      }
    });
  };

  const initGroupDrawer = () => {
    const openButton = document.getElementById("open-add-group-drawer");
    const closeButton = document.getElementById("close-add-group-drawer");
    const cancelButton = document.getElementById("cancel-add-group-drawer");
    const drawer = document.getElementById("admin-group-drawer");
    const backdrop = document.getElementById("admin-group-drawer-backdrop");
    const title = document.getElementById("admin-group-drawer-title");
    const subtitle = document.getElementById("admin-group-drawer-subtitle");
    const form = document.getElementById("admin-group-access-form");
    const groupInput = document.getElementById("admin-drawer-target-group");
    const hiddenGroupInput = document.getElementById("admin-drawer-target-group-hidden");
    const roleSelect = document.getElementById("admin-drawer-group-role");
    const editButtons = Array.from(document.querySelectorAll(".admin-edit-group-button"));

    if (!(drawer instanceof HTMLElement) || !(backdrop instanceof HTMLElement)) {
      return;
    }
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    if (!(groupInput instanceof HTMLInputElement) || !(hiddenGroupInput instanceof HTMLInputElement)) {
      return;
    }
    if (!(roleSelect instanceof HTMLSelectElement)) {
      return;
    }

    const setGroupLocked = (locked) => {
      if (locked) {
        groupInput.disabled = true;
        groupInput.classList.add("admin-locked-input");
        hiddenGroupInput.name = "target_group";
        hiddenGroupInput.value = String(groupInput.value || "").trim();
      } else {
        groupInput.disabled = false;
        groupInput.classList.remove("admin-locked-input");
        hiddenGroupInput.name = "";
        hiddenGroupInput.value = "";
      }
    };

    const openDrawer = () => {
      drawer.classList.add("is-open");
      drawer.setAttribute("aria-hidden", "false");
      backdrop.classList.remove("hidden");
      document.body.style.overflow = "hidden";
    };

    const closeDrawer = () => {
      drawer.classList.remove("is-open");
      drawer.setAttribute("aria-hidden", "true");
      backdrop.classList.add("hidden");
      document.body.style.overflow = "";
    };

    const setAddMode = () => {
      form.reset();
      setGroupLocked(false);
      if (title) {
        title.textContent = "Add Group Access";
      }
      if (subtitle) {
        subtitle.textContent = "Assign one role per group using a single save.";
      }
    };

    const setEditMode = (button) => {
      const groupPrincipal = String(button.getAttribute("data-target-group") || "").trim();
      const roleCode = String(button.getAttribute("data-target-role") || "").trim();
      groupInput.value = groupPrincipal;
      roleSelect.value = roleCode;
      setGroupLocked(true);
      if (title) {
        title.textContent = "Edit Group Access";
      }
      if (subtitle) {
        subtitle.textContent = "Group principal is locked while editing this group.";
      }
    };

    if (openButton instanceof HTMLElement) {
      openButton.addEventListener("click", () => {
        setAddMode();
        openDrawer();
      });
    }
    editButtons.forEach((button) => {
      button.addEventListener("click", () => {
        setEditMode(button);
        openDrawer();
      });
    });
    [closeButton, cancelButton].forEach((button) => {
      if (button instanceof HTMLElement) {
        button.addEventListener("click", closeDrawer);
      }
    });
    backdrop.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && drawer.classList.contains("is-open")) {
        closeDrawer();
      }
    });
  };

  const initRevokeUserModal = () => {
    const buttons = Array.from(document.querySelectorAll(".admin-revoke-user-button"));
    const backdrop = document.getElementById("admin-revoke-backdrop");
    const modal = document.getElementById("admin-revoke-modal");
    const cancelButton = document.getElementById("admin-revoke-cancel");
    const userInput = document.getElementById("admin-revoke-target-user");
    const roleInput = document.getElementById("admin-revoke-role-code");
    const message = document.getElementById("admin-revoke-message");
    const reasonInput = document.getElementById("admin-revoke-reason");
    if (!(backdrop instanceof HTMLElement) || !(modal instanceof HTMLElement)) {
      return;
    }
    if (!(userInput instanceof HTMLInputElement) || !(roleInput instanceof HTMLInputElement)) {
      return;
    }

    const open = (button) => {
      const targetUser = String(button.getAttribute("data-target-user") || "").trim();
      const targetDisplay = String(button.getAttribute("data-target-display-name") || targetUser).trim();
      const roleCode = String(button.getAttribute("data-target-role") || "").trim();
      userInput.value = targetUser;
      roleInput.value = roleCode;
      if (message instanceof HTMLElement) {
        message.textContent = `Revoke role ${roleCode} for ${targetDisplay}. A reason is required.`;
      }
      if (reasonInput instanceof HTMLTextAreaElement) {
        reasonInput.value = "";
      }
      backdrop.classList.remove("hidden");
      modal.classList.remove("hidden");
      modal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
      if (reasonInput instanceof HTMLTextAreaElement) {
        window.setTimeout(() => reasonInput.focus(), 0);
      }
    };
    const close = () => {
      backdrop.classList.add("hidden");
      modal.classList.add("hidden");
      modal.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    };

    buttons.forEach((button) => button.addEventListener("click", () => open(button)));
    backdrop.addEventListener("click", close);
    if (cancelButton instanceof HTMLElement) {
      cancelButton.addEventListener("click", close);
    }
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.classList.contains("hidden")) {
        close();
      }
    });
  };

  const initRevokeGroupModal = () => {
    const buttons = Array.from(document.querySelectorAll(".admin-revoke-group-button"));
    const backdrop = document.getElementById("admin-revoke-group-backdrop");
    const modal = document.getElementById("admin-revoke-group-modal");
    const cancelButton = document.getElementById("admin-revoke-group-cancel");
    const groupInput = document.getElementById("admin-revoke-group-target");
    const roleInput = document.getElementById("admin-revoke-group-role-code");
    const message = document.getElementById("admin-revoke-group-message");
    const reasonInput = document.getElementById("admin-revoke-group-reason");
    if (!(backdrop instanceof HTMLElement) || !(modal instanceof HTMLElement)) {
      return;
    }
    if (!(groupInput instanceof HTMLInputElement) || !(roleInput instanceof HTMLInputElement)) {
      return;
    }

    const open = (button) => {
      const targetGroup = String(button.getAttribute("data-target-group") || "").trim();
      const roleCode = String(button.getAttribute("data-target-role") || "").trim();
      groupInput.value = targetGroup;
      roleInput.value = roleCode;
      if (message instanceof HTMLElement) {
        message.textContent = `Revoke role ${roleCode} for ${targetGroup}.`;
      }
      if (reasonInput instanceof HTMLTextAreaElement) {
        reasonInput.value = "";
      }
      backdrop.classList.remove("hidden");
      modal.classList.remove("hidden");
      modal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    };
    const close = () => {
      backdrop.classList.add("hidden");
      modal.classList.add("hidden");
      modal.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    };

    buttons.forEach((button) => button.addEventListener("click", () => open(button)));
    backdrop.addEventListener("click", close);
    if (cancelButton instanceof HTMLElement) {
      cancelButton.addEventListener("click", close);
    }
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.classList.contains("hidden")) {
        close();
      }
    });
  };

  bindTypeahead({ selector: "input[data-admin-user-search]", endpoint: "/admin/users/search", valueKey: "login_identifier" });
  bindTypeahead({ selector: "input[data-admin-group-search]", endpoint: "/admin/groups/search", valueKey: "group_principal" });
  initTabs();
  initSortableFilterTable({
    tableSelector: "[data-admin-users-table]",
    rowSelector: "tr[data-user-row]",
    searchSelector: "[data-admin-users-filter]",
    clearSelector: "#admin-users-clear-filter",
    sortButtonAttribute: "data-sort-key",
    sortIndicatorAttribute: "data-sort-indicator",
    defaultSortKey: "updated",
    defaultSortDir: "desc",
  });
  initSortableFilterTable({
    tableSelector: "[data-admin-groups-table]",
    rowSelector: "tr[data-group-row]",
    searchSelector: "[data-admin-groups-filter]",
    clearSelector: "#admin-groups-clear-filter",
    sortButtonAttribute: "data-group-sort-key",
    sortIndicatorAttribute: "data-group-sort-indicator",
    defaultSortKey: "updated",
    defaultSortDir: "desc",
  });
  initUserDrawer();
  initGroupDrawer();
  initRevokeUserModal();
  initRevokeGroupModal();
})();
