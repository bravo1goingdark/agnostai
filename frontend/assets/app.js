const STORAGE_KEY = "agnost.dashboard.config";

const els = {
  apiBaseUrl: document.getElementById("api-base-url"),
  projectId: document.getElementById("project-id"),
  refreshInterval: document.getElementById("refresh-interval"),
  autoRefresh: document.getElementById("auto-refresh"),
  denseMode: document.getElementById("dense-mode"),
  refreshButton: document.getElementById("refresh-button"),
  bootstrapButton: document.getElementById("bootstrap-button"),
  copyReportButton: document.getElementById("copy-report-button"),
  connectionStatus: document.getElementById("connection-status"),
  footerStatus: document.getElementById("footer-status"),
  latestRun: document.getElementById("latest-run"),
  totalMessages: document.getElementById("total-messages"),
  totalTopics: document.getElementById("total-topics"),
  generatedAt: document.getElementById("generated-at"),
  topicsCount: document.getElementById("topics-count"),
  sentimentTotal: document.getElementById("sentiment-total"),
  statsGrid: document.getElementById("stats-grid"),
  sentimentBars: document.getElementById("sentiment-bars"),
  topicMiniList: document.getElementById("topic-mini-list"),
  topicList: document.getElementById("topic-list"),
  detailTitle: document.getElementById("detail-title"),
  detailLabel: document.getElementById("detail-label"),
  detailBody: document.getElementById("detail-body"),
  reportOutput: document.getElementById("report-output"),
};

const defaultConfig = {
  apiBaseUrl: window.location.origin,
  projectId: "project-1",
  refreshInterval: 30,
  autoRefresh: true,
  denseMode: true,
};

const state = {
  config: loadConfig(),
  insights: null,
  topics: [],
  topicDetail: null,
  reportText: "No report yet.",
  selectedTopicId: null,
  timer: null,
};

function loadConfig() {
  try {
    return { ...defaultConfig, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") };
  } catch {
    return { ...defaultConfig };
  }
}

function saveConfig() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.config));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
}

function formatPercent(value) {
  if (value == null) {
    return "n/a";
  }
  return `${formatNumber(value * 100)}%`;
}

function setStatus(message, tone = "idle") {
  els.footerStatus.textContent = message;
  els.connectionStatus.textContent = tone;
}

function apiUrl(path) {
  return `${state.config.apiBaseUrl.replace(/\/$/, "")}${path}`;
}

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response;
}

async function fetchJson(path, options = {}) {
  const response = await request(path, options);
  return response.json();
}

function syncForm() {
  els.apiBaseUrl.value = state.config.apiBaseUrl;
  els.projectId.value = state.config.projectId;
  els.refreshInterval.value = state.config.refreshInterval;
  els.autoRefresh.checked = state.config.autoRefresh;
  els.denseMode.checked = state.config.denseMode;
  document.documentElement.dataset.dense = state.config.denseMode ? "true" : "false";
}

function bindForm() {
  const update = () => {
    state.config.apiBaseUrl = els.apiBaseUrl.value.trim() || defaultConfig.apiBaseUrl;
    state.config.projectId = els.projectId.value.trim() || defaultConfig.projectId;
    state.config.refreshInterval = Math.max(0, Number(els.refreshInterval.value) || 0);
    state.config.autoRefresh = els.autoRefresh.checked;
    state.config.denseMode = els.denseMode.checked;
    document.documentElement.dataset.dense = state.config.denseMode ? "true" : "false";
    saveConfig();
    scheduleRefresh();
  };

  ["change", "input"].forEach((eventName) => {
    els.apiBaseUrl.addEventListener(eventName, update);
    els.projectId.addEventListener(eventName, update);
    els.refreshInterval.addEventListener(eventName, update);
    els.autoRefresh.addEventListener(eventName, update);
    els.denseMode.addEventListener(eventName, update);
  });
}

function scheduleRefresh() {
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
  if (state.config.autoRefresh && state.config.refreshInterval > 0) {
    state.timer = setInterval(() => {
      refreshDashboard().catch((error) => {
        setStatus(error.message, "error");
      });
    }, state.config.refreshInterval * 1000);
  }
}

function renderStats() {
  const insights = state.insights;
  const stats = insights
    ? [
        { label: "Messages", value: insights.total_messages },
        { label: "Topics", value: insights.total_topics },
        { label: "Latest run", value: insights.latest_cluster_run_id || "none" },
        {
          label: "Negative share",
          value: insights.top_topics?.[0]?.negative_sentiment_share ?? null,
          percent: true,
        },
      ]
    : [
        { label: "Messages", value: 0 },
        { label: "Topics", value: 0 },
        { label: "Latest run", value: "none" },
        { label: "Negative share", value: "n/a" },
      ];

  els.statsGrid.innerHTML = stats
    .map((item) => {
      const value =
        item.percent && typeof item.value === "number"
          ? `${formatNumber(item.value * 100)}%`
          : item.value;
      return `
        <div class="stat">
          <div class="metric-label">${escapeHtml(item.label)}</div>
          <div class="stat-value">${escapeHtml(value)}</div>
        </div>
      `;
    })
    .join("");

  els.latestRun.textContent = insights?.latest_cluster_run_id || "none";
  els.totalMessages.textContent = String(insights?.total_messages ?? 0);
  els.totalTopics.textContent = String(insights?.total_topics ?? 0);
  els.generatedAt.textContent = insights?.generated_at
    ? `Generated ${new Date(insights.generated_at).toLocaleString()}`
    : "Waiting for data";
  els.topicsCount.textContent = `${state.topics.length} items`;
}

function renderSentimentBars() {
  const counts = state.insights?.sentiment_distribution || {};
  const ordered = [
    ["negative", counts.negative || 0],
    ["neutral", counts.neutral || 0],
    ["positive", counts.positive || 0],
  ];
  const total = ordered.reduce((sum, [, value]) => sum + value, 0);
  els.sentimentTotal.textContent = total ? `${total} messages` : "No messages";
  els.sentimentBars.innerHTML = ordered
    .map(([label, value]) => {
      const width = total ? Math.max(4, Math.round((value / total) * 100)) : 0;
      return `
        <div class="bar-row">
          <span>${escapeHtml(label)}</span>
          <div class="bar-track">
            <div class="bar-fill" data-tone="${escapeHtml(label)}" style="width:${width}%"></div>
          </div>
          <span>${value}</span>
        </div>
      `;
    })
    .join("");
}

function renderTopicMiniList() {
  els.topicMiniList.innerHTML = state.topics
    .slice(0, 5)
    .map(
      (topic) => `
        <div class="bar-row">
          <span>${escapeHtml(topic.label)}</span>
          <div class="bar-track">
            <div class="bar-fill" style="width:${Math.min(100, Math.max(10, topic.member_count * 10))}%"></div>
          </div>
          <span>${topic.member_count}</span>
        </div>
      `,
    )
    .join("");
}

function renderTopics() {
  if (!state.topics.length) {
    els.topicList.innerHTML = `
      <div class="detail-body empty">
        No topics yet. Use <strong>Bootstrap sample</strong> to seed conversations and generate clusters.
      </div>
    `;
    return;
  }

  els.topicList.innerHTML = state.topics
    .map((topic) => {
      const active = topic.id === state.selectedTopicId;
      const terms = (topic.terms || []).slice(0, 3).join(" · ");
      const growth = topic.growth_24h == null ? "n/a" : `${formatNumber(topic.growth_24h)}`;
      return `
        <button class="topic-button" type="button" aria-pressed="${active}" data-topic-id="${escapeHtml(topic.id)}">
          <div class="topic-topline">
            <strong>${escapeHtml(topic.label)}</strong>
            <span class="topic-meta">${topic.member_count} msgs</span>
          </div>
          <div class="topic-meta">Growth 24h: ${escapeHtml(growth)} · Sentiment: ${escapeHtml(
            topic.sentiment_mean == null ? "n/a" : formatNumber(topic.sentiment_mean),
          )}</div>
          <div class="topic-terms">${escapeHtml(terms || "No terms yet")}</div>
        </button>
      `;
    })
    .join("");

  document.querySelectorAll("[data-topic-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const topicId = button.getAttribute("data-topic-id");
      if (topicId) {
        loadTopic(topicId).catch((error) => {
          setStatus(error.message, "error");
        });
      }
    });
  });
}

function renderTopicDetail() {
  const detail = state.topicDetail;
  if (!detail) {
    els.detailTitle.textContent = "Select a topic";
    els.detailLabel.textContent = "none";
    els.detailBody.className = "detail-body empty";
    els.detailBody.textContent = "Pick a topic to inspect its messages and source conversations.";
    return;
  }

  els.detailTitle.textContent = detail.label;
  els.detailLabel.textContent = `${detail.member_count} messages`;
  els.detailBody.className = "detail-body";
  const conversations = [...new Set(detail.source_conversation_ids || [])];
  els.detailBody.innerHTML = `
    <div class="topic-meta">
      Terms: ${(detail.terms || []).join(" · ") || "n/a"}<br>
      Growth 24h: ${detail.growth_24h == null ? "n/a" : formatNumber(detail.growth_24h)}<br>
      Negative share: ${formatPercent(detail.negative_sentiment_share)}
    </div>
    ${detail.messages
      .map(
        (message) => `
          <article class="message">
            <div class="message-header">
              <span class="message-role">${escapeHtml(message.role)}</span>
              <span>${escapeHtml(message.sentiment_label || "unknown")}</span>
            </div>
            <div class="message-text">${escapeHtml(message.content)}</div>
            <div class="topic-meta">Conversation ${escapeHtml(message.conversation_id)} · Similarity ${message.similarity == null ? "n/a" : formatNumber(message.similarity)}</div>
          </article>
        `,
      )
      .join("")}
    <div class="topic-meta">Source conversations: ${escapeHtml(conversations.join(" · ") || "n/a")}</div>
  `;
}

function renderReport() {
  els.reportOutput.textContent = state.reportText || "No report yet.";
}

async function loadTopicsOnly() {
  const data = await fetchJson(`/v1/topics?project_id=${encodeURIComponent(state.config.projectId)}`);
  state.topics = data.topics || [];
  if (!state.selectedTopicId && state.topics.length) {
    state.selectedTopicId = state.topics[0].id;
  }
  renderTopics();
  renderTopicDetail();
}

async function loadTopic(topicId) {
  const detail = await fetchJson(`/v1/topics/${encodeURIComponent(topicId)}`);
  state.selectedTopicId = topicId;
  state.topicDetail = detail;
  renderTopics();
  renderTopicDetail();
}

async function refreshDashboard() {
  setStatus("Refreshing...", "loading");
  const [insights, topics, report] = await Promise.all([
    fetchJson(`/v1/insights?project_id=${encodeURIComponent(state.config.projectId)}`),
    fetchJson(`/v1/topics?project_id=${encodeURIComponent(state.config.projectId)}`),
    fetchJson(`/v1/reports/current?project_id=${encodeURIComponent(state.config.projectId)}`),
  ]);

  state.insights = insights;
  state.topics = topics.topics || [];
  state.reportText = report.report_text || "No report yet.";
  if (!state.selectedTopicId && state.topics.length) {
    state.selectedTopicId = state.topics[0].id;
  }

  renderStats();
  renderSentimentBars();
  renderTopicMiniList();
  renderTopics();
  renderReport();
  if (state.selectedTopicId) {
    await loadTopic(state.selectedTopicId);
  }
  setStatus(`Loaded ${state.config.projectId}`, "ok");
}

async function bootstrapSample() {
  setStatus("Bootstrapping sample project...", "loading");
  const result = await fetchJson("/v1/demo/bootstrap", {
    method: "POST",
    body: JSON.stringify({ project_id: state.config.projectId }),
  });
  state.insights = result.insights;
  state.reportText = result.report_text;
  state.topics = result.topics || [];
  state.selectedTopicId = state.topics[0]?.id || null;
  renderStats();
  renderSentimentBars();
  renderTopicMiniList();
  renderTopics();
  renderReport();
  if (state.selectedTopicId) {
    await loadTopic(state.selectedTopicId);
  }
  setStatus(
    `Bootstrapped ${result.accepted} conversations, ${result.topic_count} topics`,
    "ok",
  );
}

async function copyReport() {
  await navigator.clipboard.writeText(state.reportText || "");
  setStatus("Report copied.", "ok");
}

function boot() {
  syncForm();
  bindForm();

  els.refreshButton.addEventListener("click", () => {
    refreshDashboard().catch((error) => setStatus(error.message, "error"));
  });
  els.bootstrapButton.addEventListener("click", () => {
    bootstrapSample().catch((error) => setStatus(error.message, "error"));
  });
  els.copyReportButton.addEventListener("click", () => {
    copyReport().catch((error) => setStatus(error.message, "error"));
  });

  renderStats();
  renderSentimentBars();
  renderTopicMiniList();
  renderTopics();
  renderTopicDetail();
  renderReport();
  scheduleRefresh();
  refreshDashboard().catch((error) => setStatus(error.message, "error"));
}

boot();
