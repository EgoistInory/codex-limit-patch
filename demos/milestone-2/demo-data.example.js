(function () {
  "use strict";

  const payload = window.USAGE_MONITOR_DEMO;
  if (!payload || !Array.isArray(payload.accounts)) return;

  payload.mixed_sources = false;
  payload.live_provider_ids = [];
  payload.accounts.forEach((account) => {
    account.demo = true;
    if (account.provider_id === "openai") {
      account.plan_name = "plus";
      account.source_label = "Codex app-server example";
    }
  });
})();
