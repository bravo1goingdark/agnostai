const els = {
  refreshButton: document.getElementById("refresh-button"),
  bootstrapButton: document.getElementById("bootstrap-button"),
  closeDetail: document.getElementById("close-detail"),
  footerStatus: document.getElementById("footer-status"),
  footerMeta: document.getElementById("footer-meta"),
  summaryStrip: document.getElementById("summary-strip"),
  topicsCount: document.getElementById("topics-count"),
  topicGrid: document.getElementById("topic-grid"),
  detailPanel: document.getElementById("detail-panel"),
  detailTitle: document.getElementById("detail-title"),
  detailMeta: document.getElementById("detail-meta"),
  conversationList: document.getElementById("conversation-list"),
  obsQueue: document.getElementById("obs-queue"),
  obsFailed: document.getElementById("obs-failed"),
  obsDuration: document.getElementById("obs-duration"),
  obsLastRun: document.getElementById("obs-last-run"),
};

const state = {
  insights: null,
  topics: [],
  topicDetail: null,
  selectedTopicId: null,
  timer: null,
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
}

function formatPercent(value) {
  if (value == null) return "—";
  return `${formatNumber(value * 100)}%`;
}

function setStatus(message, tone = "idle") {
  els.footerStatus.textContent = message;
}

function apiPath(path) {
  return `/v1/${path}`;
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(apiPath(path), {
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`${response.status}: ${body}`);
    }
    return response;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchJson(path, options = {}) {
  const response = await request(path, options);
  return response.json();
}

function scheduleRefresh() {
  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(() => {
    refreshDashboard().catch((error) => setStatus(error.message, "error"));
  }, 30000);
}

function sentimentTone(label) {
  if (label === "negative") return "bad";
  if (label === "positive") return "good";
  return "neutral";
}

function renderSummary() {
  const insights = state.insights;
  const negativeShare = insights?.top_topics?.[0]?.negative_sentiment_share ?? null;
  const topTopic = insights?.top_topics?.[0];
  const emerging = insights?.emerging_topics || [];

  els.summaryStrip.innerHTML = `
    <div class="summary-main">
      <div class="summary-hero">
        <span class="summary-value">${insights?.total_messages ?? 0}</span>
        <span class="summary-label">Messages analyzed</span>
      </div>
      <div class="summary-hero">
        <span class="summary-value">${insights?.total_topics ?? 0}</span>
        <span class="summary-label">Topics found</span>
      </div>
      ${negativeShare != null ? `
        <div class="summary-hero">
          <span class="summary-value tone-bad">${formatPercent(negativeShare)}</span>
          <span class="summary-label">Top topic negativity</span>
        </div>
      ` : `
        <div class="summary-hero">
          <span class="summary-value">—</span>
          <span class="summary-label">Top topic negativity</span>
        </div>
      `}
    </div>
    <div class="summary-insight">
      ${topTopic ? `
        <span class="insight-label">Key signal</span>
        <span class="insight-text">"${escapeHtml(topTopic.label)}" — ${topTopic.member_count} messages, sentiment ${formatNumber(topTopic.sentiment_mean)}</span>
      ` : `
        <span class="insight-label">Key signal</span>
        <span class="insight-text">No data yet. Click "Seed sample data" to generate topics.</span>
      `}
      ${emerging.length ? `
        <span class="insight-label" style="margin-top:8px">Growing</span>
        <span class="insight-text">${emerging.map(t => escapeHtml(t.label)).join(", ")}</span>
      ` : ""}
      ${(insights?.narrative_insights || []).length ? `
        <ul class="narrative-insights">
          ${insights.narrative_insights.map(s => `<li>${escapeHtml(s)}</li>`).join("")}
        </ul>
      ` : ""}
    </div>
  `;
}

function renderTopics() {
  const topics = state.topics;
  els.topicsCount.textContent = `${topics.length} topics`;

  if (!topics.length) {
    els.topicGrid.innerHTML = `
      <div class="empty-state">
        <p>No topics yet.</p>
        <p>Click <strong>Seed sample data</strong> to bootstrap conversations and generate clusters.</p>
      </div>
    `;
    return;
  }

  els.topicGrid.innerHTML = topics
    .map((topic) => {
      const tone = sentimentTone(topic.sentiment_mean != null
        ? (topic.sentiment_mean < -0.1 ? "negative" : topic.sentiment_mean > 0.1 ? "positive" : "neutral")
        : "neutral");
      const growth = topic.growth_24h != null
        ? (topic.growth_24h > 0 ? `↑${formatNumber(topic.growth_24h * 100)}%` : `↓${formatNumber(Math.abs(topic.growth_24h) * 100)}%`)
        : "new";
      return `
        <button class="topic-card" data-topic-id="${escapeHtml(topic.id)}">
          <div class="topic-card-header">
            <span class="topic-label">${escapeHtml(topic.label)}</span>
            <span class="topic-badge" data-tone="${tone}">${topic.member_count} msgs</span>
          </div>
          <div class="topic-card-stats">
            <span>Sentiment ${formatNumber(topic.sentiment_mean)}</span>
            <span>24h ${growth}</span>
          </div>
          <div class="topic-card-terms">${(topic.terms || []).slice(0, 3).join(" · ")}</div>
        </button>
      `;
    })
    .join("");

  document.querySelectorAll("[data-topic-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const topicId = button.getAttribute("data-topic-id");
      if (topicId) {
        loadTopic(topicId).catch((error) => setStatus(error.message, "error"));
      }
    });
  });
}

function renderTopicDetail() {
  const detail = state.topicDetail;
  if (!detail) {
    els.detailPanel.hidden = true;
    return;
  }

  els.detailPanel.hidden = false;
  els.detailTitle.textContent = detail.label;
  els.detailMeta.innerHTML = `
    <span>${detail.member_count} messages</span>
    <span>·</span>
    <span>Sentiment ${formatNumber(detail.sentiment_mean)}</span>
    <span>·</span>
    <span>${formatPercent(detail.negative_sentiment_share)} negative</span>
    <span>·</span>
    <span>${(detail.terms || []).slice(0, 3).join(", ")}</span>
  `;

  els.conversationList.innerHTML = (detail.messages || [])
    .map((message) => `
      <article class="conversation-bubble" data-role="${escapeHtml(message.role)}">
        <div class="bubble-header">
          <span class="bubble-role">${message.role === "user" ? "User" : "Agent"}</span>
          <span class="bubble-sentiment" data-tone="${sentimentTone(message.sentiment_label)}">${message.sentiment_label || "—"}</span>
        </div>
        <div class="bubble-text">${escapeHtml(message.content)}</div>
      </article>
    `)
    .join("");
}

function renderObservability(data) {
  els.obsQueue.textContent = data?.queue_depth ?? "—";
  els.obsFailed.textContent = data?.failed_job_count ?? "—";
  els.obsDuration.textContent = data?.latest_cluster_run_duration_ms != null
    ? `${formatNumber(data.latest_cluster_run_duration_ms / 1000)}s`
    : "—";
  els.obsLastRun.textContent = state.insights?.generated_at
    ? new Date(state.insights.generated_at).toLocaleString()
    : "—";
  els.footerMeta.textContent = state.insights?.project_id
    ? `Project: ${state.insights.project_id}`
    : "";
}

async function loadTopic(topicId) {
  state.topicDetail = null;
  try {
    const detail = await fetchJson(`topics/${encodeURIComponent(topicId)}`);
    state.selectedTopicId = topicId;
    state.topicDetail = detail;
    renderTopicDetail();
    window.scrollTo({ top: els.detailPanel.offsetTop - 24, behavior: "smooth" });
  } catch (error) {
    state.selectedTopicId = null;
    setStatus(error.message, "error");
  }
}

function closeTopicDetail() {
  state.selectedTopicId = null;
  state.topicDetail = null;
  els.detailPanel.hidden = true;
}

async function refreshDashboard() {
  els.refreshButton.classList.add("is-spinning");
  setStatus("Refreshing...");
  try {
    const [insights, topics, obs] = await Promise.all([
      fetchJson(`insights?project_id=project-1`),
      fetchJson(`topics?project_id=project-1`),
      fetchJson(`observability?project_id=project-1`),
    ]);

    state.insights = insights;
    state.topics = topics.topics || [];

    renderSummary();
    renderTopics();
    renderObservability(obs);
    if (state.selectedTopicId) {
      await loadTopic(state.selectedTopicId);
    }
    setStatus("Connected");
  } finally {
    els.refreshButton.classList.remove("is-spinning");
  }
}

async function bootstrapSample() {
  els.bootstrapButton.classList.add("is-spinning");
  setStatus("Generating sample data...");
  try {
    const result = await fetchJson("demo/bootstrap", {
      method: "POST",
      body: JSON.stringify({ project_id: "project-1" }),
    });
    state.insights = result.insights;
    state.topics = result.topics || [];
    state.selectedTopicId = null;
    state.topicDetail = null;
    closeTopicDetail();
    renderSummary();
    renderTopics();
    const obs = await fetchJson(`observability?project_id=project-1`);
    renderObservability(obs);
    setStatus(`Ready — ${result.accepted} conversations, ${result.topic_count} topics`);
  } finally {
    els.bootstrapButton.classList.remove("is-spinning");
  }
}

function boot() {
  els.refreshButton.addEventListener("click", () => {
    refreshDashboard().catch((error) => setStatus(error.message, "error"));
  });
  els.bootstrapButton.addEventListener("click", () => {
    bootstrapSample().catch((error) => setStatus(error.message, "error"));
  });
  els.closeDetail.addEventListener("click", closeTopicDetail);

  scheduleRefresh();
  refreshDashboard().catch((error) => setStatus(error.message, "error"));
}

boot();
