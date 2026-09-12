// AETHER AI Observability - Frontend Controller

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function initDashboard() {
  bindEvents();
  await refreshDashboard();
}

function bindEvents() {
  const datasetSelect = document.getElementById("datasetSelect");
  datasetSelect.addEventListener("change", async (e) => {
    await switchDataset(e.target.value);
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

  btnUploadModal.addEventListener("click", () => {
    uploadModal.style.display = "flex";
  });

  const closeModal = () => { uploadModal.style.display = "none"; };
  btnCloseModal.addEventListener("click", closeModal);
  btnCancelUpload.addEventListener("click", closeModal);

  btnSubmitUpload.addEventListener("click", handleFileUpload);

  // Benchmark
  const btnRunBenchmark = document.getElementById("btnRunBenchmark");
  btnRunBenchmark.addEventListener("click", runBenchmark);
}

async function refreshDashboard() {
  await Promise.all([
    fetchOverview(),
    fetchIncidents(),
    fetchTimeline(),
    fetchLogs()
  ]);
}

async function switchDataset(datasetName) {
  try {
    const linesCount = datasetName.endsWith("_big") ? 25000 : 400;
    const res = await fetch("/api/ingest/sample", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset: datasetName, max_lines: linesCount })
    });
    if (res.ok) {
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
    if (data.status === "active") {
      document.getElementById("kpiNoiseReduction").textContent = `${data.metrics.noise_reduction_ratio}%`;
      document.getElementById("kpiIncidents").textContent = data.metrics.incidents_count;
      document.getElementById("kpiAnomaliesSub").textContent = `from ${data.metrics.anomalies_count} raw anomalies`;
      document.getElementById("kpiSpeedup").textContent = `${data.metrics.triage_speedup_ratio}x`;
      document.getElementById("kpiDialect").textContent = (data.detected_format || "generic").toUpperCase();
      document.getElementById("kpiLogsCount").textContent = `${data.total_logs} logs parsed (${data.templates_count} templates)`;
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
  try {
    const res = await fetch("/api/analysis/incidents");
    const data = await res.json();
    const incidents = data.incidents || [];

    countBadge.textContent = `${incidents.length} incidents detected`;
    container.innerHTML = "";

    if (incidents.length === 0) {
      container.innerHTML = `<div style="grid-column: 1/-1; padding: 2rem; text-align: center; color: var(--text-muted);">No critical incidents detected in this log slice.</div>`;
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
          <div style="font-size: 0.7rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.3rem;">Correlated Entities:</div>
          <div class="evidence-tags">${evidenceTags || '<span style="color: var(--text-muted); font-size: 0.75rem;">None</span>'}</div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error fetching incidents:", err);
  }
}

async function fetchTimeline() {
  const container = document.getElementById("timelineBars");
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
      tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-muted);">No logs match the current filters.</td></tr>`;
      return;
    }

    logs.forEach(l => {
      const row = document.createElement("tr");
      if (l.is_anomaly) row.className = "row-anomaly";

      const timeStr = l.timestamp ? l.timestamp.replace("T", " ") : "-";
      const lvlClass = `lvl-${l.level}`;

      row.innerHTML = `
        <td class="log-id">#${l.id}</td>
        <td class="log-ts">${escapeHtml(timeStr)}</td>
        <td><span class="badge-level ${lvlClass}">${l.level}</span></td>
        <td style="color: #93c5fd; font-family: var(--font-mono); font-size: 0.78rem;">${escapeHtml(l.service || '-')}</td>
        <td style="word-break: break-all;">${escapeHtml(l.message)}</td>
        <td><span class="tag">${l.template_id}</span></td>
        <td>
          <span style="color: ${l.is_anomaly ? 'var(--accent-crimson)' : 'var(--text-muted)'}; font-family: var(--font-mono); font-weight: 700;">
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
        <div class="tag" style="background: rgba(0, 229, 255, 0.1); border-color: var(--accent-cyan); color: #fff; cursor: pointer;"
             title="${escapeHtml(ev.message)}">
          Line #${ev.log_id} [${ev.service}]
        </div>
      `).join("");
    } else {
      evidenceList.innerHTML = `<span style="color: var(--text-muted); font-size: 0.75rem;">None</span>`;
    }
  } catch (err) {
    answerText.textContent = "Investigation query failed. Please try again.";
    console.error("Copilot error:", err);
  }
}

async function handleFileUpload() {
  const fileInput = document.getElementById("fileInput");
  if (!fileInput.files.length) {
    alert("Please choose a log file first.");
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/ingest/upload", {
      method: "POST",
      body: formData
    });
    if (res.ok) {
      document.getElementById("uploadModal").style.display = "none";
      await refreshDashboard();
    } else {
      alert("Failed to ingest file.");
    }
  } catch (err) {
    console.error("Upload error:", err);
  }
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
