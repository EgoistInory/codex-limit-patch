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
    if (account.provider_id === "anthropic") {
      account.account_kind = "local_estimate";
      account.source_label = "Claude Code local logs example";
      account.message = "Local usage only; subscription limits are not available.";
    }
    if (account.provider_id === "deepseek") {
      account.source_label = "DeepSeek balance API example";
      account.message = null;
      account.quotas = [
        {
          id: "balance-cny",
          label: "CNY API balance",
          unit: "CNY",
          used: null,
          limit: null,
          remaining: 42.6,
          remaining_percent: null,
          resets_at: null,
          period_label: null,
          accuracy: "exact",
          components: [
            { label: "Granted", value: 12.6, unit: "CNY" },
            { label: "Paid", value: 30, unit: "CNY" }
          ]
        }
      ];
    }
  });
})();
