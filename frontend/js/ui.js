/**
 * LectureNotes AI — UI View Controller
 * 
 * Handles DOM manipulation, stage stepper animation, modals,
 * system status pill, toast alerts, and theme swatches.
 */

class UIController {
    constructor() {
        this.STAGES_ORDER = [
            "downloading",
            "extracting_audio",
            "transcribing",
            "cleaning",
            "structuring_notes",
            "generating_questions",
            "building_pdf",
        ];
    }

    // ── System Status Pill ─────────────────────────────────────────────────────
    updateSystemStatus(health, isOffline = false) {
        const pill = document.getElementById("system-status-pill");
        const dot = document.getElementById("status-dot");
        const text = document.getElementById("status-text");
        const tooltip = document.getElementById("status-tooltip");
        if (!pill || !dot || !text) return;

        pill.className = "system-status-pill";

        if (isOffline) {
            pill.classList.add("status-offline");
            text.textContent = "Backend Offline";
            if (tooltip) {
                tooltip.innerHTML = `
                    <strong>Connection Error</strong><br>
                    FastAPI server unreachable at localhost:8000.<br>
                    Run <code>start.bat</code> to launch backend.
                `;
            }
            return;
        }

        const isGeminiReady = health.gemini_configured;
        const isOllama = health.llm_provider === "ollama";
        const isReady = isGeminiReady || isOllama || health.demo_mode;

        if (isReady) {
            pill.classList.add("status-ready");
            text.textContent = "System Ready";
        } else {
            pill.classList.add("status-warning");
            text.textContent = "Setup Needed";
        }

        if (tooltip) {
            tooltip.innerHTML = `
                <div class="tooltip-row"><span>Engine:</span> <strong>${health.llm_provider}</strong></div>
                <div class="tooltip-row"><span>Gemini:</span> <strong>${health.gemini_configured ? "Configured" : "Missing API Key"}</strong></div>
                <div class="tooltip-row"><span>Ollama:</span> <strong>${health.ollama_model || "localhost:11434"}</strong></div>
                <div class="tooltip-row"><span>Whisper:</span> <strong>${health.whisper_model} (${health.whisper_device} ${health.whisper_compute_type})</strong></div>
                <div class="tooltip-row"><span>Demo Mode:</span> <strong>${health.demo_mode ? "ON" : "OFF"}</strong></div>
            `;
        }
    }

    // ── Setup Error Banner ─────────────────────────────────────────────────────
    setSetupBanner(visible, message = "") {
        const banner = document.getElementById("setup-alert");
        const text = document.getElementById("setup-text");
        if (!banner) return;

        if (visible) {
            banner.style.display = "block";
            if (text && message) text.innerHTML = message;
        } else {
            banner.style.display = "none";
        }
    }

    // ── Toasts ─────────────────────────────────────────────────────────────────
    showToast(message, type = "info", duration = 4000) {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.className = "toast-container";
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.className = `toast toast-${type} toast-enter`;
        toast.innerHTML = `
            <span class="toast-icon">${type === "error" ? "❌" : type === "success" ? "✅" : type === "warning" ? "⚠️" : "ℹ️"}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" aria-label="Close">✕</button>
        `;

        toast.querySelector(".toast-close").addEventListener("click", () => {
            toast.classList.replace("toast-enter", "toast-exit");
            setTimeout(() => toast.remove(), 250);
        });

        container.appendChild(toast);

        setTimeout(() => {
            if (toast.parentElement) {
                toast.classList.replace("toast-enter", "toast-exit");
                setTimeout(() => toast.remove(), 250);
            }
        }, duration);
    }

    // ── View Switching: Input vs Progress vs Result ────────────────────────────
    showInputView() {
        document.getElementById("input-card").style.display = "block";
        document.getElementById("progress-card").style.display = "none";
        document.getElementById("result-card").style.display = "none";
    }

    showProgressView() {
        document.getElementById("input-card").style.display = "none";
        document.getElementById("progress-card").style.display = "block";
        document.getElementById("result-card").style.display = "none";
    }

    showResultView() {
        document.getElementById("input-card").style.display = "none";
        document.getElementById("progress-card").style.display = "none";
        document.getElementById("result-card").style.display = "block";
    }

    // ── Stage Stepper ──────────────────────────────────────────────────────────
    updateProgress(statusData, elapsedSec = 0) {
        const { status, progress, stage_label, current_chunk, total_chunks, error, can_resume } = statusData;

        // Progress bar and percent
        const bar = document.getElementById("progress-bar");
        const percent = document.getElementById("progress-percent");
        const stageText = document.getElementById("progress-stage");
        const elapsedText = document.getElementById("progress-elapsed");
        const chunkIndicator = document.getElementById("chunk-indicator");

        if (bar) bar.style.width = `${progress}%`;
        if (percent) percent.textContent = `${progress}%`;
        if (stageText) stageText.textContent = stage_label || "Processing...";

        if (elapsedText) {
            const mins = Math.floor(elapsedSec / 60);
            const secs = elapsedSec % 60;
            elapsedText.textContent = `Elapsed: ${mins}m ${secs < 10 ? "0" : ""}${secs}s`;
        }

        if (chunkIndicator) {
            if (total_chunks > 1 && current_chunk > 0) {
                chunkIndicator.style.display = "inline-block";
                chunkIndicator.textContent = `Processing Chunk ${current_chunk} of ${total_chunks}`;
            } else {
                chunkIndicator.style.display = "none";
            }
        }

        // Stepper dots
        const stageIndex = this.STAGES_ORDER.indexOf(status);
        const stageElements = document.querySelectorAll(".stage-item");

        stageElements.forEach((el) => {
            const stageName = el.getAttribute("data-stage");
            const idx = this.STAGES_ORDER.indexOf(stageName);

            el.classList.remove("completed", "active", "failed", "cancelled");

            if (status === "cancelled") {
                if (idx < stageIndex) el.classList.add("completed");
                else if (idx === stageIndex) el.classList.add("cancelled");
            } else if (status === "failed") {
                if (idx < stageIndex) el.classList.add("completed");
                else if (idx === stageIndex) el.classList.add("failed");
            } else if (status === "completed") {
                el.classList.add("completed");
            } else {
                if (idx < stageIndex) el.classList.add("completed");
                else if (idx === stageIndex) el.classList.add("active");
            }
        });

        // Cancel / Resume buttons
        const btnCancel = document.getElementById("btn-cancel-job");
        const btnResume = document.getElementById("btn-resume-job");
        const btnViewTrans = document.getElementById("btn-progress-transcript");

        if (btnCancel) {
            btnCancel.style.display = (status === "completed" || status === "failed" || status === "cancelled") ? "none" : "inline-flex";
        }

        if (btnResume) {
            btnResume.style.display = (can_resume || status === "cancelled" || status === "failed") ? "inline-flex" : "none";
        }

        if (btnViewTrans) {
            btnViewTrans.style.display = statusData.transcript_ready ? "inline-flex" : "none";
        }

        // Error banner in progress card
        const errBox = document.getElementById("progress-error-box");
        const errText = document.getElementById("progress-error-text");
        if (errBox && errText) {
            if (error || status === "failed") {
                errBox.style.display = "block";
                errText.textContent = error || "Pipeline encountered an error.";
            } else {
                errBox.style.display = "none";
            }
        }
    }

    // ── Result Card ────────────────────────────────────────────────────────────
    renderResult(jobData) {
        document.getElementById("result-lecture-title").textContent = jobData.title || "Lecture Notes";

        const duration = jobData.duration_seconds
            ? `${Math.floor(jobData.duration_seconds / 60)}m ${jobData.duration_seconds % 60}s`
            : "Completed";
        document.getElementById("result-duration").textContent = duration;
        document.getElementById("result-words").textContent = jobData.word_count ? jobData.word_count.toLocaleString() : "-";

        // Structured counts
        document.getElementById("result-concepts").textContent = jobData.concept_count ?? (jobData.section_count ?? "-");
        document.getElementById("result-examples").textContent = jobData.example_count ?? "-";
        document.getElementById("result-numericals").textContent = jobData.numerical_count ?? "-";
        document.getElementById("result-formulas").textContent = jobData.formula_count ?? "-";
        document.getElementById("result-questions").textContent = jobData.question_count ?? "12";

        // Download and preview links
        const downloadPdf = document.getElementById("btn-download-pdf");
        if (downloadPdf) {
            downloadPdf.href = window.apiClient.getPdfDownloadUrl(jobData.job_id);
            downloadPdf.setAttribute("download", `${(jobData.title || "Lecture").replace(/\s+/g, "_")}_Notes.pdf`);
        }

        const downloadTxt = document.getElementById("btn-download-transcript");
        if (downloadTxt) {
            downloadTxt.href = window.apiClient.getTranscriptTextUrl(jobData.job_id);
            downloadTxt.setAttribute("download", `${(jobData.title || "Lecture").replace(/\s+/g, "_")}_transcript.txt`);
        }

        // Demo badge
        const demoBadge = document.getElementById("demo-tag");
        if (demoBadge) {
            demoBadge.style.display = (jobData.is_demo || window.apiClient.isMockMode()) ? "inline-block" : "none";
        }
    }

    // ── PDF Preview Modal ──────────────────────────────────────────────────────
    openPdfModal(jobId, title = "Lecture Study Book") {
        const modal = document.getElementById("pdf-modal");
        const iframe = document.getElementById("pdf-frame");
        const titleEl = document.getElementById("pdf-modal-title");
        const dlBtn = document.getElementById("pdf-modal-download");

        if (!modal || !iframe) return;

        titleEl.textContent = `${title} — PDF Preview`;
        iframe.src = window.apiClient.getPdfPreviewUrl(jobId);
        if (dlBtn) dlBtn.href = window.apiClient.getPdfDownloadUrl(jobId);

        modal.style.display = "flex";
        document.body.style.overflow = "hidden";
    }

    // ── Transcript Modal ───────────────────────────────────────────────────────
    openTranscriptModal(transcriptData) {
        const modal = document.getElementById("transcript-modal");
        const content = document.getElementById("transcript-content");
        const searchInput = document.getElementById("transcript-search");

        if (!modal || !content) return;

        modal.style.display = "flex";
        document.body.style.overflow = "hidden";

        const segments = transcriptData.segments || [];
        this._renderedSegments = segments;

        this.renderTranscriptSegments(segments);

        if (searchInput) {
            searchInput.value = "";
            searchInput.focus();
        }
    }

    renderTranscriptSegments(segments, filterQuery = "") {
        const content = document.getElementById("transcript-content");
        if (!content) return;

        if (!segments || segments.length === 0) {
            content.innerHTML = `<div class="empty-state">No transcript segments available.</div>`;
            return;
        }

        const query = filterQuery.toLowerCase().trim();
        const filtered = query
            ? segments.filter((s) => s.text.toLowerCase().includes(query))
            : segments;

        if (filtered.length === 0) {
            content.innerHTML = `<div class="empty-state">No matches found for "${filterQuery}".</div>`;
            return;
        }

        const html = filtered
            .map((s) => {
                const startMins = Math.floor(s.start / 60);
                const startSecs = Math.floor(s.start % 60);
                const timeStr = `${startMins}:${startSecs < 10 ? "0" : ""}${startSecs}`;

                let text = s.text;
                if (query) {
                    const regex = new RegExp(`(${query})`, "gi");
                    text = text.replace(regex, `<mark>$1</mark>`);
                }

                return `
                <div class="transcript-row">
                    <span class="transcript-time">${timeStr}</span>
                    <span class="transcript-text">${text}</span>
                </div>
            `;
            })
            .join("");

        content.innerHTML = html;
    }

    closeModals() {
        const modals = document.querySelectorAll(".modal-overlay");
        modals.forEach((m) => (m.style.display = "none"));
        const pdfFrame = document.getElementById("pdf-frame");
        if (pdfFrame) pdfFrame.src = "";
        document.body.style.overflow = "";
    }

    // ── Recent Conversions List ────────────────────────────────────────────────
    renderRecentJobs(jobs) {
        const section = document.getElementById("recent-section");
        const container = document.getElementById("recent-jobs-list");
        if (!section || !container) return;

        if (!jobs || jobs.length === 0) {
            section.style.display = "none";
            return;
        }

        section.style.display = "block";
        container.innerHTML = jobs
            .map((j) => {
                const dateStr = new Date(j.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                });
                const isExpired = j.is_expired;
                const statusClass = isExpired
                    ? "status-pill-expired"
                    : j.status === "completed"
                    ? "status-pill-completed"
                    : "status-pill-incomplete";

                return `
                <div class="recent-job-card">
                    <div class="recent-job-header">
                        <div class="recent-job-title" title="${j.title}">${j.title}</div>
                        <span class="recent-status-pill ${statusClass}">
                            ${isExpired ? "Expired (>24h)" : j.status}
                        </span>
                    </div>
                    <div class="recent-job-meta">
                        <span>📅 ${dateStr}</span>
                        <span>🎨 ${j.theme || "indigo"}</span>
                        <span>🤖 ${j.ai_engine || "gemini"}</span>
                    </div>
                    <div class="recent-job-actions">
                        ${
                            !isExpired && j.status === "completed"
                                ? `
                            <a href="${window.apiClient.getPdfDownloadUrl(j.job_id)}" class="btn btn-sm btn-primary" download>
                                📥 PDF
                            </a>
                            <button class="btn btn-sm btn-secondary" onclick="window.appController.openPreview('${j.job_id}', '${j.title.replace(/'/g, "\\'")}')">
                                👁️ Preview
                            </button>
                        `
                                : `
                            <span class="expired-note">${isExpired ? "Auto-deleted" : "Incomplete"}</span>
                        `
                        }
                    </div>
                </div>
            `;
            })
            .join("");
    }
}

window.uiController = new UIController();
