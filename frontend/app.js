// Rivyn - Frontend Controller

const INCIDENT_PAGE_SIZE = 12;
let incidentOffset = 0;
let dashboardHasData = false;
let activeUploadJobId = null;
let uploadStartedAt = null;
let uploadTimerId = null;
let uploadPollId = null;

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function initDashboard() {
  initTheme();
  bindEvents();
  await refreshDashboard();
}

/**
 * Light/dark theming. An explicit choice is stored in localStorage and wins;
 * with no stored choice the page follows the OS preference via CSS media query.
 */
function initTheme() {
  const toggle = document.getElementById("btnThemeToggle");
  if (!toggle) return;

  toggle.addEventListener("click", () => {
    const root = document.documentElement;
    const explicit = root.getAttribute("data-theme");
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const currentlyDark = explicit ? explicit === "dark" : systemDark;
    const next = currentlyDark ? "light" : "dark";

    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem("rivyn-theme", next);
    } catch (e) {
      /* storage blocked (private mode) — theme still applies for this session */
    }
  });
}

function bindEvents() {
  const datasetSelect = document.getElementById("datasetSelect");

  // Load the explicitly selected presentation dataset; startup stays empty.
  const btnUpdate = document.getElementById("btnUpdateDataset");
  btnUpdate.addEventListener("click", async () => {
    btnUpdate.disabled = true;
    btnUpdate.textContent = "Updating…";
    try {
      await switchDataset(datasetSelect.value);
    } finally {
      btnUpdate.disabled = false;
      btnUpdate.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Load sample`;
    }
  });

  const searchInput = document.getElementById("logSearch");
  searchInput.addEventListener("input", debounce(fetchLogs, 300));

  const severityFilter = document.getElementById("severityFilter");
  severityFilter.addEventListener("change", fetchLogs);

  const anomaliesOnlyCheck = document.getElementById("anomaliesOnlyCheck");
  anomaliesOnlyCheck.addEventListener("change", fetchLogs);

  const btnAskCopilot = document.getElementById("btnAskCopilot");
  btnAskCopilot.addEventListener("click", askCopilot);

  const copilotInput = document.getElementById("copilotInput");
  copilotInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") askCopilot();
  });

  document.querySelectorAll(".pill-btn").forEach((pill) => {
    pill.addEventListener("click", (e) => {
      copilotInput.value = e.target.getAttribute("data-query");
      askCopilot();
    });
  });

  // Upload Modal
  const btnUploadModal = document.getElementById("btnUploadModal");
  const uploadModal = document.getElementById("uploadModal");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const btnCancelUpload = document.getElementById("btnCancelUpload");
  const btnSubmitUpload = document.getElementById("btnSubmitUpload");
  const fileInput = document.getElementById("fileInput");

  fileInput.addEventListener("change", previewUploadFile);

  btnUploadModal.addEventListener("click", () => {
    resetUploadUi();
    document.getElementById("uploadStatus").textContent = "";
    uploadModal.style.display = "flex";
  });

  const closeModal = () => {
    if (activeUploadJobId) return;
    resetUploadUi();
    uploadModal.style.display = "none";
  };
  btnCloseModal.addEventListener("click", closeModal);
  btnCancelUpload.addEventListener("click", closeModal);

  btnSubmitUpload.addEventListener("click", handleFileUpload);

  // Benchmark
  const btnRunBenchmark = document.getElementById("btnRunBenchmark");
  btnRunBenchmark.addEventListener("click", runBenchmark);
}

async function refreshDashboard() {
  await fetchOverview();
  await Promise.all([
    fetchIncidents(),
    fetchTimeline(),
    fetchLogs()
  ]);
}

async function switchDataset(datasetName) {
  try {
    const demoLineCounts = { openstack: 207820, spark: 100000, hdfs: 100000 };
    const linesCount = demoLineCounts[datasetName];
    if (!linesCount) return;

    const res = await fetch("/api/ingest/sample", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset: datasetName, max_lines: linesCount })
    });
    if (res.ok) {
    incidentOffset = 0;
    await refreshDashboard();
    }
  } catch (err) {
    console.error("Failed to switch dataset:", err);
  }
}

async function fetchOverview() {
  try {
    const res = await fetch("/api/analysis/overview");
    const data = await res.json();
    dashboardHasData = data.status === "active";
    if (data.status === "active") {
      document.getElementById("kpiNoiseReduction").textContent = `${data.metrics.noise_reduction_ratio}%`;
      document.getElementById("kpiIncidents").textContent = data.metrics.incidents_count;
      document.getElementById("kpiAnomaliesSub").textContent = `from ${data.metrics.anomalies_count} raw anomalies`;
      document.getElementById("kpiSpeedup").textContent = `${data.metrics.triage_speedup_ratio}x`;
      document.getElementById("kpiDialect").textContent = (data.detected_format || "generic").toUpperCase();
      document.getElementById("kpiLogsCount").textContent = `${data.total_logs} logs parsed (${data.templates_count} templates)`;
    } else {
      document.getElementById("kpiNoiseReduction").textContent = "--%";
      document.getElementById("kpiIncidents").textContent = "--";
      document.getElementById("kpiAnomaliesSub").textContent = "Upload a log to begin";
      document.getElementById("kpiSpeedup").textContent = "--x";
      document.getElementById("kpiDialect").textContent = "--";
      document.getElementById("kpiLogsCount").textContent = "No logs loaded";
    }

    // Fetch Binary Storage Engine Stats
    const binRes = await fetch("/api/storage/binary-stats");
    const binData = await binRes.json();
    if (binData.binary_engine) {
      const b = binData.binary_engine;
      document.getElementById("kpiBinaryFormat").textContent = `${b.storage_reduction_factor} Smaller`;
      document.getElementById("kpiBinarySub").textContent = `${b.compression_ratio_pct}% compressed (${b.scan_latency_ms}ms scan)`;
    }
  } catch (err) {
    console.error("Error fetching overview:", err);
  }
}

async function fetchIncidents() {
  const container = document.getElementById("incidentGrid");
  const countBadge = document.getElementById("incidentCountBadge");
  if (!dashboardHasData) {
    countBadge.textContent = "Awaiting a log upload";
    container.innerHTML = `<div class="empty-state">Upload a presentation log or load one of the three demo datasets to begin analysis.</div>`;
    document.getElementById("incidentPagination").innerHTML = "";
    return;
  }
  try {
    const res = await fetch(`/api/analysis/incidents?limit=${INCIDENT_PAGE_SIZE}&offset=${incidentOffset}`);
    const data = await res.json();
    const incidents = data.incidents || [];
    const total = data.total || 0;

    countBadge.textContent = `Top ${incidents.length} of ${total} · ranked by severity and confidence`;
    container.innerHTML = "";

    if (incidents.length === 0) {
      container.innerHTML = `<div class="empty-state">No critical incidents detected in this log slice.</div>`;
      return;
    }

    incidents.forEach((inc) => {
      const badgeClass = inc.severity === "CRITICAL" ? "badge-critical" : (inc.severity === "HIGH" ? "badge-high" : "badge-medium");
      const card = document.createElement("div");
      card.className = "incident-card";

      let evidenceTags = "";
      if (inc.affected_entities && inc.affected_entities.length > 0) {
        evidenceTags = inc.affected_entities.map(e => `<span class="tag">${escapeHtml(e)}</span>`).join("");
      }

      card.innerHTML = `
        <div class="incident-card-top">
          <span class="badge ${badgeClass}">${inc.severity}</span>
          <span class="confidence-chip">${Math.round(inc.confidence * 100)}% Confidence</span>
        </div>
        <div class="incident-title">${escapeHtml(inc.title)}</div>
        <div class="incident-summary">${escapeHtml(inc.summary)}</div>

        <div class="root-cause-box">
          <div class="root-cause-label">Probable Root Cause</div>
          <div class="root-cause-text">${escapeHtml(inc.probable_root_cause)}</div>
        </div>

        <div class="action-box">
          <div class="action-label">Recommended Remediation</div>
          <div class="action-text">${escapeHtml(inc.recommended_action)}</div>
        </div>

        <div>
          <div class="field-label">Correlated Entities</div>
          <div class="evidence-tags">${evidenceTags || '<span class="section-meta">None</span>'}</div>
        </div>
      `;
      container.appendChild(card);
    });
    renderIncidentPagination(total, data.offset || 0, data.limit || INCIDENT_PAGE_SIZE);
  } catch (err) {
    console.error("Error fetching incidents:", err);
  }
}

function renderIncidentPagination(total, offset, limit) {
  const pagination = document.getElementById("incidentPagination");
  pagination.innerHTML = "";
  if (total <= limit) return;

  const start = offset + 1;
  const end = Math.min(offset + limit, total);
  const pageLabel = document.createElement("span");
  pageLabel.className = "section-meta";
  pageLabel.textContent = `Showing ${start}–${end} of ${total}`;

  const previous = document.createElement("button");
  previous.type = "button";
  previous.className = "btn btn-secondary pagination-btn";
  previous.textContent = "Previous";
  previous.disabled = offset === 0;
  previous.addEventListener("click", () => {
    incidentOffset = Math.max(0, offset - limit);
    fetchIncidents();
  });

  const next = document.createElement("button");
  next.type = "button";
  next.className = "btn btn-secondary pagination-btn";
  next.textContent = "Next";
  next.disabled = offset + limit >= total;
  next.addEventListener("click", () => {
    incidentOffset = offset + limit;
    fetchIncidents();
  });

  pagination.append(previous, pageLabel, next);
}

async function fetchTimeline() {
  const container = document.getElementById("timelineBars");
  if (!dashboardHasData) {
    container.innerHTML = "";
    return;
  }
  try {
    const res = await fetch("/api/analysis/timeline?buckets=35");
    const data = await res.json();
    const buckets = data.buckets || [];

    container.innerHTML = "";
    if (buckets.length === 0) return;

    const maxCount = Math.max(...buckets.map(b => b.total_count), 1);

    buckets.forEach(b => {
      const wrapper = document.createElement("div");
      wrapper.className = "bar-wrapper";
      wrapper.title = `${b.timestamp_label || 'T'}: ${b.total_count} logs (${b.anomaly_count} anomalies)`;

      const totalH = Math.max(4, Math.round((b.total_count / maxCount) * 85));
      const anomalyH = Math.round((b.anomaly_count / maxCount) * 85);

      wrapper.innerHTML = `
        <div class="bar-total" style="height: ${totalH}px;">
          ${b.anomaly_count > 0 ? `<div class="bar-anomaly" style="height: ${anomalyH}px;"></div>` : ''}
        </div>
      `;
      container.appendChild(wrapper);
    });
  } catch (err) {
    console.error("Error fetching timeline:", err);
  }
}

async function fetchLogs() {
  const tableBody = document.getElementById("logTableBody");
  const countLabel = document.getElementById("logTableCount");
  if (!dashboardHasData) {
    countLabel.textContent = "Awaiting a log upload";
    tableBody.innerHTML = `<tr><td colspan="7" class="empty-state">Upload a log to view parsed events here.</td></tr>`;
    return;
  }
  const search = document.getElementById("logSearch").value;
  const severity = document.getElementById("severityFilter").value;
  const anomaliesOnly = document.getElementById("anomaliesOnlyCheck").checked;

  const params = new URLSearchParams({ limit: 100, offset: 0 });
  if (search) params.append("search", search);
  if (severity) params.append("severity", severity);
  if (anomaliesOnly) params.append("anomalies_only", "true");

  try {
    const res = await fetch(`/api/analysis/logs?${params.toString()}`);
    const data = await res.json();
    const logs = data.logs || [];

    countLabel.textContent = `Showing ${logs.length} of ${data.total} matching logs`;
    tableBody.innerHTML = "";

    if (logs.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" class="empty-state">No logs match the current filters.</td></tr>`;
      return;
    }

    logs.forEach(l => {
      const row = document.createElement("tr");
      if (l.is_anomaly) row.className = "row-anomaly";

      const timeStr = l.timestamp ? l.timestamp.replace("T", " ") : "-";
      const lvlClass = `lvl-${l.level}`;

      row.innerHTML = `
        <td class="log-id" data-label="Log">#${l.id}</td>
        <td class="log-ts" data-label="Timestamp">${escapeHtml(timeStr)}</td>
        <td data-label="Level"><span class="badge-level ${lvlClass}">${l.level}</span></td>
        <td class="log-service" data-label="Service">${escapeHtml(l.service || '-')}</td>
        <td data-label="Message">${escapeHtml(l.message)}</td>
        <td data-label="Template"><span class="tag">${l.template_id}</span></td>
        <td data-label="Anomaly">
          <span class="log-score ${l.is_anomaly ? 'is-anomaly' : 'is-normal'}">
            ${l.anomaly_score.toFixed(2)}
          </span>
        </td>
      `;
      tableBody.appendChild(row);
    });
  } catch (err) {
    console.error("Error fetching logs:", err);
  }
}

async function askCopilot() {
  const input = document.getElementById("copilotInput");
  const query = input.value.trim();
  if (!query) return;

  const answerBox = document.getElementById("copilotAnswerBox");
  const answerText = document.getElementById("copilotAnswerText");
  const confidence = document.getElementById("copilotConfidence");
  const evidenceList = document.getElementById("copilotEvidenceList");

  answerBox.style.display = "block";
  answerText.textContent = "Retrieving relevant log chunks and analyzing evidence...";
  confidence.textContent = "Analyzing...";
  evidenceList.innerHTML = "";

  try {
    const res = await fetch("/api/investigate/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query })
    });
    const data = await res.json();

    answerText.textContent = data.answer;
    confidence.textContent = `Confidence: ${Math.round(data.confidence * 100)}%`;

    if (data.evidence && data.evidence.length > 0) {
      evidenceList.innerHTML = data.evidence.map(ev => `
        <div class="tag evidence-tag-link" title="${escapeHtml(ev.message)}">
          Line #${ev.log_id} [${escapeHtml(ev.service || '-')}]
        </div>
      `).join("");
    } else {
      evidenceList.innerHTML = `<span class="section-meta">None</span>`;
    }
  } catch (err) {
    answerText.textContent = "Investigation query failed. Please try again.";
    console.error("Copilot error:", err);
  }
}

async function handleFileUpload() {
  const fileInput = document.getElementById("fileInput");
  const status = document.getElementById("uploadStatus");
  if (!fileInput.files.length) {
    status.textContent = "Choose a log file before ingesting.";
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  prepareUploadUi(file);
  try {
    const res = await fetch("/api/ingest/upload", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to start analysis.");
    activeUploadJobId = data.job_id;
    document.getElementById("uploadEstimatedTime").textContent = formatDuration(data.estimated_seconds);
    document.getElementById("uploadRemainingTime").textContent = formatDuration(data.estimated_seconds);
    updateUploadProgress("Queued for analysis", 4);
    pollUploadJob();
  } catch (err) {
    console.error("Upload error:", err);
    showUploadFailure(err.message || "Upload failed. Please try again.");
  }
}

function previewUploadFile() {
  const file = document.getElementById("fileInput").files[0];
  const preview = document.getElementById("uploadFilePreview");
  if (!file) {
    preview.hidden = true;
    return;
  }
  const estimate = estimateClientSeconds(file.size);
  document.getElementById("uploadFileName").textContent = file.name;
  document.getElementById("uploadFileMeta").textContent = `${formatBytes(file.size)} · analysis estimate`;
  document.getElementById("uploadClientEstimate").textContent = `~${formatDuration(estimate)}`;
  preview.hidden = false;
}

function prepareUploadUi(file) {
  activeUploadJobId = null;
  uploadStartedAt = Date.now();
  const progress = document.getElementById("uploadProgress");
  progress.hidden = false;
  document.getElementById("btnSubmitUpload").disabled = true;
  document.getElementById("btnSubmitUpload").textContent = "Analyzing…";
  document.getElementById("btnCancelUpload").disabled = true;
  document.getElementById("btnCloseModal").disabled = true;
  document.getElementById("uploadResult").textContent = "";
  document.getElementById("uploadEstimatedTime").textContent = formatDuration(estimateClientSeconds(file.size));
  document.getElementById("uploadRemainingTime").textContent = "Calculating…";
  updateUploadProgress("Uploading file", 2);
  clearInterval(uploadTimerId);
  uploadTimerId = setInterval(() => {
    document.getElementById("uploadElapsedTime").textContent = formatDuration((Date.now() - uploadStartedAt) / 1000);
  }, 250);
}

async function pollUploadJob() {
  if (!activeUploadJobId) return;
  try {
    const res = await fetch(`/api/ingest/jobs/${activeUploadJobId}`);
    const job = await res.json();
    if (!res.ok) throw new Error(job.detail || "Could not read analysis progress.");

    updateUploadProgress(job.stage, job.progress);
    document.getElementById("uploadElapsedTime").textContent = formatDuration(job.elapsed_seconds);
    document.getElementById("uploadEstimatedTime").textContent = formatDuration(job.estimated_seconds);
    document.getElementById("uploadRemainingTime").textContent = job.status === "complete"
      ? "Done"
      : formatDuration(job.remaining_seconds);

    if (job.status === "complete") {
      clearInterval(uploadTimerId);
      const lines = Number(job.lines_processed || 0).toLocaleString();
      await refreshDashboard();
      document.getElementById("uploadStatus").textContent = job.duplicate
        ? "No new log lines were added because this file was already ingested."
        : `Processed ${lines} log lines.`;
      activeUploadJobId = null;
      resetUploadUi();
      document.getElementById("uploadModal").style.display = "none";
      return;
    }
    if (job.status === "failed") throw new Error(job.error || "Analysis failed.");
    uploadPollId = setTimeout(pollUploadJob, 550);
  } catch (err) {
    console.error("Upload progress error:", err);
    showUploadFailure(err.message || "Analysis failed. Please try again.");
  }
}

function updateUploadProgress(stage, progress) {
  const safeProgress = Math.max(0, Math.min(100, Number(progress) || 0));
  document.getElementById("uploadStage").textContent = stage;
  document.getElementById("uploadPercent").textContent = `${safeProgress}%`;
  document.getElementById("uploadProgressBar").style.width = `${safeProgress}%`;
}

function finishUploadUi() {
  activeUploadJobId = null;
  clearTimeout(uploadPollId);
  document.getElementById("btnSubmitUpload").disabled = false;
  document.getElementById("btnSubmitUpload").textContent = "Analyze another file";
  document.getElementById("btnCancelUpload").disabled = false;
  document.getElementById("btnCancelUpload").textContent = "Close";
  document.getElementById("btnCloseModal").disabled = false;
}

function showUploadFailure(message) {
  activeUploadJobId = null;
  clearInterval(uploadTimerId);
  clearTimeout(uploadPollId);
  document.getElementById("uploadProgress").hidden = false;
  updateUploadProgress("Upload failed", 0);
  document.getElementById("uploadRemainingTime").textContent = "--";
  document.getElementById("uploadResult").textContent = message;
  finishUploadUi();
}

function resetUploadUi() {
  clearInterval(uploadTimerId);
  clearTimeout(uploadPollId);
  uploadStartedAt = null;
  document.getElementById("fileInput").value = "";
  document.getElementById("uploadFilePreview").hidden = true;
  document.getElementById("uploadProgress").hidden = true;
  document.getElementById("btnSubmitUpload").disabled = false;
  document.getElementById("btnCancelUpload").disabled = false;
  document.getElementById("btnCloseModal").disabled = false;
  document.getElementById("btnCancelUpload").textContent = "Cancel";
  document.getElementById("btnSubmitUpload").textContent = "Ingest & Analyze";
}

function estimateClientSeconds(bytes) {
  return Math.max(5, Math.ceil(bytes / 650000) + 4);
}

function formatDuration(seconds) {
  if (!Number.isFinite(Number(seconds))) return "--";
  const total = Math.max(0, Math.round(Number(seconds)));
  const minutes = Math.floor(total / 60);
  const remaining = String(total % 60).padStart(2, "0");
  return minutes ? `${minutes}m ${remaining}s` : `${remaining}s`;
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function runBenchmark() {
  alert("Running automated evaluation benchmark across HDFS, BGL, Linux, and OpenStack. Results will open in a report dialog.");
  try {
    const res = await fetch("/api/metrics/benchmark");
    const data = await res.json();
    console.log("Benchmark results:", data);
    let summary = "LogHub Benchmark Results:\n\n";
    for (const [k, v] of Object.entries(data.benchmark_results)) {
      summary += `Dataset: ${v.dataset} (${v.detected_dialect})\n` +
                 `  - Noise Reduction: ${v.noise_reduction_pct}%\n` +
                 `  - Speedup Factor: ${v.speedup_factor}\n` +
                 `  - Precision@20: ${v.precision_at_20}\n` +
                 `  - Top Root Cause: ${v.top_incident_root_cause.slice(0, 70)}...\n\n`;
    }
    alert(summary);
  } catch (err) {
    console.error("Benchmark error:", err);
  }
}

function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
