(function () {
  "use strict";

  const payload = window.USAGE_MONITOR_DEMO;
  const summaryRoot = document.getElementById("summary");
  const alertRoot = document.getElementById("alerts");
  const providerRoot = document.getElementById("providers");
  const snapshotTime = document.getElementById("snapshot-time");
  const numberFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
  const compactFormatter = new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  });

  if (!payload || !Array.isArray(payload.accounts)) {
    renderFatalState();
    return;
  }

  snapshotTime.textContent = `Snapshot ${formatDate(payload.generated_at)}`;
  renderSummary(payload.accounts, payload.alerts || []);
  renderAlerts(payload.alerts || []);
  renderProviders(payload.accounts, payload.alerts || []);
  bindFilters();

  function createElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function renderSummary(accounts, alerts) {
    const active = accounts.filter((account) => account.status === "available").length;
    const critical = alerts.filter((alert) => alert.severity === "critical").length;
    const requests = sumKnown(accounts, "requests_today");
    const tokens = sumKnown(accounts, "tokens_today");
    const metrics = [
      [`${active}/${accounts.length}`, "Active sources"],
      [critical, "Critical signals"],
      [numberFormatter.format(requests), "Requests today"],
      [compactFormatter.format(tokens), "Tokens today"],
    ];
    summaryRoot.replaceChildren();
    metrics.forEach(([value, label]) => {
      const item = createElement("div", "summary-metric");
      item.append(createElement("strong", "summary-value", value));
      item.append(createElement("span", "summary-label", label));
      summaryRoot.append(item);
    });
  }

  function renderAlerts(alerts) {
    alertRoot.replaceChildren();
    const visible = alerts.slice(0, 3);
    if (!visible.length) {
      alertRoot.append(createElement("div", "empty-state", "No limit signals in this snapshot."));
      return;
    }
    visible.forEach((alert) => {
      const item = createElement("article", "alert-item");
      item.dataset.severity = alert.severity;
      item.append(createElement("strong", "", alert.title));
      item.append(createElement("span", "", alert.message));
      alertRoot.append(item);
    });
  }

  function renderProviders(accounts, alerts) {
    providerRoot.replaceChildren();
    accounts.forEach((account, index) => {
      const accountAlerts = alerts.filter((alert) => alert.account_id === account.id);
      const card = createElement("article", "provider-card");
      card.dataset.provider = account.provider_id;
      card.dataset.status = account.status;
      card.dataset.demo = String(account.demo === true);
      card.dataset.attention = accountAlerts.length ? "true" : "false";
      card.style.animationDelay = `${index * 38}ms`;
      card.append(renderIdentity(account));
      card.append(renderQuotas(account));
      card.append(renderActivity(account, accountAlerts));
      providerRoot.append(card);
    });
  }

  function renderIdentity(account) {
    const identity = createElement("div", "provider-identity");
    const head = createElement("div", "provider-head");
    const glyph = account.client_name || account.provider_name;
    head.append(createElement("span", "provider-glyph", initials(glyph)));
    const names = createElement("div", "");
    names.append(createElement("h3", "provider-name", account.provider_name));
    const identityParts = [
      account.client_name || humanize(account.account_kind),
      account.plan_name,
    ].filter(Boolean);
    names.append(
      createElement("p", "client-name", identityParts.join(" · ")),
    );
    head.append(names);
    identity.append(head);

    const meta = createElement("div", "provider-meta");
    const status = createElement("span", "status-chip", humanize(account.status));
    status.dataset.status = account.status;
    meta.append(status);
    const isDemo = account.demo === true || (account.demo === undefined && payload.demo);
    if (isDemo) {
      meta.append(createElement("span", "demo-chip", "Demo"));
    }
    meta.append(createElement("span", "source-chip", account.source_label));
    identity.append(meta);
    return identity;
  }

  function renderQuotas(account) {
    const stack = createElement("div", "quota-stack");
    if (!account.quotas.length) {
      stack.append(createElement("div", "empty-state", "No quota metrics reported."));
      return stack;
    }
    account.quotas.forEach((quota) => stack.append(renderQuota(quota)));
    return stack;
  }

  function renderQuota(quota) {
    const block = createElement("div", "quota-block");
    const known = quota.remaining_percent !== null && quota.remaining_percent !== undefined;
    block.dataset.known = String(known);
    block.dataset.level = quotaLevel(quota.remaining_percent);

    const title = createElement("div", "quota-title-row");
    title.append(createElement("span", "quota-label", quota.label));
    title.append(createElement("strong", "quota-value", quotaValue(quota)));
    block.append(title);

    const track = createElement("div", "quota-track");
    track.setAttribute("role", "meter");
    track.setAttribute("aria-label", quota.label);
    const fill = createElement("div", "quota-fill");
    if (known) {
      const percent = clamp(Number(quota.remaining_percent), 0, 100);
      track.setAttribute("aria-valuemin", "0");
      track.setAttribute("aria-valuemax", "100");
      track.setAttribute("aria-valuenow", String(percent));
      fill.style.width = `${percent}%`;
    }
    track.append(fill);
    block.append(track);

    const foot = createElement("div", "quota-foot");
    foot.append(createElement("span", "", quota.resets_at ? `Resets ${formatDate(quota.resets_at)}` : "No reset window"));
    if (quota.accuracy === "estimated") {
      foot.append(createElement("span", "accuracy-chip", "Estimated"));
    } else {
      foot.append(createElement("span", "", quota.period_label || humanize(quota.accuracy)));
    }
    block.append(foot);
    if (Array.isArray(quota.components) && quota.components.length) {
      const components = createElement("div", "quota-components");
      quota.components.forEach((component) => {
        const value = `${component.label} ${numberFormatter.format(component.value)} ${component.unit}`;
        components.append(createElement("span", "quota-component", value));
      });
      block.append(components);
    }
    return block;
  }

  function renderActivity(account, alerts) {
    const panel = createElement("div", "activity-panel");
    panel.append(activityRow("Requests", formatKnown(account.requests_today, numberFormatter)));
    panel.append(activityRow("Tokens", formatKnown(account.tokens_today, compactFormatter)));
    panel.append(activityRow("Today", formatCost(account.cost_today, account.currency)));
    if (account.models.length) {
      panel.append(activityRow("Models", account.models.map((model) => model.display_name).join(", ")));
    }
    if (alerts.length) {
      panel.append(activityRow("Signals", String(alerts.length)));
    }
    if (account.message) {
      panel.append(createElement("p", "provider-message", account.message));
    }
    return panel;
  }

  function activityRow(label, value) {
    const row = createElement("div", "activity-row");
    row.append(createElement("span", "", label));
    row.append(createElement("strong", "", value));
    return row;
  }

  function bindFilters() {
    document.querySelectorAll(".filter-button").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".filter-button").forEach((item) => {
          item.classList.toggle("is-active", item === button);
        });
        const filter = button.dataset.filter;
        document.querySelectorAll(".provider-card").forEach((card) => {
          const hidden = filter === "attention" && card.dataset.attention !== "true";
          card.classList.toggle("is-hidden", hidden);
        });
      });
    });
  }

  function renderFatalState() {
    const message = createElement("div", "empty-state", "Demo data is missing or invalid.");
    providerRoot.replaceChildren(message);
  }

  function sumKnown(items, key) {
    return items.reduce((total, item) => total + (Number(item[key]) || 0), 0);
  }

  function formatKnown(value, formatter) {
    return value === null || value === undefined ? "Unknown" : formatter.format(value);
  }

  function formatCost(value, currency) {
    if (value === null || value === undefined || !currency) return "Not reported";
    return `${numberFormatter.format(value)} ${currency}`;
  }

  function quotaValue(quota) {
    if (quota.remaining_percent !== null && quota.remaining_percent !== undefined) {
      return `${numberFormatter.format(quota.remaining_percent)}% left`;
    }
    if (quota.remaining !== null && quota.remaining !== undefined) {
      return `${numberFormatter.format(quota.remaining)} ${quota.unit}`;
    }
    return "Unknown";
  }

  function quotaLevel(percent) {
    if (percent === null || percent === undefined) return "unknown";
    if (percent <= 10) return "critical";
    if (percent <= 20) return "warning";
    return "healthy";
  }

  function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Unknown";
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function initials(value) {
    return String(value)
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0].toUpperCase())
      .join("");
  }

  function humanize(value) {
    return String(value || "unknown")
      .replace(/[_-]+/g, " ")
      .replace(/^./, (letter) => letter.toUpperCase());
  }

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }
})();
