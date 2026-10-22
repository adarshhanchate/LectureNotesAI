/**
 * LectureNotes AI — Main Application Controller
 * 
 * Orchestrates API communication, view states, event handling,
 * drag-and-drop, validation, polling loop, and modal interactions.
 */

class AppController {
    constructor() {
        this.activeJobId = null;
        this.pollTimer = null;
        this.elapsedTimer = null;
        this.jobStartTime = null;
        this.selectedFile = null;
        this.isSubmitting = false;
        this.currentTranscript = null;
    }

    async init() {
        // 1. Initialize Theme
        const theme = window.stateManager.getTheme();
        window.stateManager.setTheme(theme);
        this._bindThemeToggle();

        // 2. Dev Mock Mode Ribbon
        if (window.apiClient.isMockMode()) {
            this._showMockRibbon();
        }

        // 3. Bind UI Events & Interactions
        this._bindNavigation();
        this._bindInputTabs();
        this._bindLinkInputs();
        this._bindFileUpload();
        this._bindCollapsibles();
        this._bindAdvancedOptions();
        this._bindModals();
        this._bindProgressControls();

        // 4. Fetch System Health Status
        await this._checkHealth();

        // 5. Restore Recent Conversions
        this._refreshRecentJobs();

        // 6. Restore Active Job across Page Reloads
        const savedJobId = window.stateManager.getActiveJobId();
        if (savedJobId) {
            console.info("Restoring active job from localStorage:", savedJobId);
            this.startTrackingJob(savedJobId, true);
        }
    }

    // ── System Health ──────────────────────────────────────────────────────────
    async _checkHealth() {
        try {
            const health = await window.apiClient.getHealth();
            window.uiController.updateSystemStatus(health, false);

            // Setup Warning Banner
            const needsSetup = !health.gemini_configured && !health.demo_mode && health.llm_provider === "gemini";
            if (needsSetup) {
                window.uiController.setSetupBanner(
                    true,
                    `<strong>AI Setup Required:</strong> No Gemini API key detected in <code>.env</code>. Add your key, switch to <strong>Local Ollama</strong> in Advanced Options, or set <code>DEMO_MODE=true</code>. See <a href="#faq" style="text-decoration:underline;">README instructions</a>.`
                );
            } else {
                window.uiController.setSetupBanner(false);
            }

            // Sync max upload limit
            if (health.max_upload_size_mb) {
                this.maxUploadMb = health.max_upload_size_mb;
            }
        } catch (err) {
            console.error("Health check error:", err);
            window.uiController.updateSystemStatus(null, true);
            window.uiController.showToast("Cannot reach backend server at http://localhost:8000. Is start.bat running?", "error", 6000);
        }
    }

    // ── Theme Switcher ─────────────────────────────────────────────────────────
    _bindThemeToggle() {
        const btn = document.getElementById("theme-toggle");
        if (!btn) return;
        btn.addEventListener("click", () => {
            const newTheme = window.stateManager.toggleTheme();
            window.uiController.showToast(`Switched to ${newTheme} mode`, "info", 1500);
        });
    }

    _showMockRibbon() {
        const ribbon = document.createElement("div");
        ribbon.className = "demo-ribbon";
        ribbon.innerHTML = "<span>DEMO MODE (?mock=1)</span>";
        document.body.appendChild(ribbon);
    }

    // ── Navigation & Smooth Scroll ─────────────────────────────────────────────
    _bindNavigation() {
        document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
            anchor.addEventListener("click", function (e) {
                const targetId = this.getAttribute("href");
                if (targetId === "#") return;
                const target = document.querySelector(targetId);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: "smooth" });
                }
            });
        });

        // Hamburger Menu (Mobile)
        const hamburger = document.getElementById("nav-hamburger");
        const navLinks = document.getElementById("nav-links");
        if (hamburger && navLinks) {
            hamburger.addEventListener("click", () => {
                navLinks.classList.toggle("open");
                hamburger.classList.toggle("active");
            });
        }
    }

    // ── Input Card Tabs ────────────────────────────────────────────────────────
    _bindInputTabs() {
        const tabLink = document.getElementById("tab-link");
        const tabUpload = document.getElementById("tab-upload");
        const contentLink = document.getElementById("content-link");
        const contentUpload = document.getElementById("content-upload");

        if (tabLink && tabUpload) {
            tabLink.addEventListener("click", () => {
                tabLink.classList.add("active");
                tabUpload.classList.remove("active");
                contentLink.classList.add("active");
                contentUpload.classList.remove("active");
                this._clearInputErrors();
            });

            tabUpload.addEventListener("click", () => {
                tabUpload.classList.add("active");
                tabLink.classList.remove("active");
                contentUpload.classList.add("active");
                contentLink.classList.remove("active");
                this._clearInputErrors();
            });
        }
    }

    // ── Link Input Flow ────────────────────────────────────────────────────────
    _bindLinkInputs() {
        const urlInput = document.getElementById("video-url");
        const btnPaste = document.getElementById("btn-paste-url");
        const btnConvert = document.getElementById("btn-convert-link");

        if (btnPaste && urlInput) {
            btnPaste.addEventListener("click", async () => {
                try {
                    const text = await navigator.clipboard.readText();
                    if (text) {
                        urlInput.value = text.trim();
                        this._validateUrl(urlInput.value);
                    }
                } catch {
                    window.uiController.showToast("Could not access clipboard. Please paste manually.", "warning");
                }
            });
        }

        if (urlInput) {
            urlInput.addEventListener("input", () => this._validateUrl(urlInput.value));
            urlInput.addEventListener("keypress", (e) => {
                if (e.key === "Enter") this.submitLinkJob();
            });
        }

        if (btnConvert) {
            btnConvert.addEventListener("click", () => this.submitLinkJob());
        }
    }

    _validateUrl(url) {
        const errEl = document.getElementById("link-error-text");
        const urlInput = document.getElementById("video-url");
        if (!errEl || !urlInput) return false;

        const val = url.trim();
        if (!val) {
            errEl.textContent = "";
            errEl.style.display = "none";
            urlInput.classList.remove("is-invalid");
            return false;
        }

        const isValid = /^(https?:\/\/)([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?(\?.*)?$/i.test(val);
        if (!isValid) {
            errEl.textContent = "Please enter a valid lecture link starting with http:// or https://";
            errEl.style.display = "block";
            urlInput.classList.add("is-invalid");
            return false;
        }

        errEl.textContent = "";
        errEl.style.display = "none";
        urlInput.classList.remove("is-invalid");
        return true;
    }

    async submitLinkJob() {
        if (this.isSubmitting) return;
        const urlInput = document.getElementById("video-url");
        if (!urlInput || !this._validateUrl(urlInput.value)) {
            window.uiController.showToast("Please provide a valid lecture video URL.", "warning");
            urlInput?.focus();
            return;
        }

        const options = this._gatherJobOptions();
        options.url = urlInput.value.trim();

        try {
            this._setSubmitting(true);
            const res = await window.apiClient.createJobFromUrl(options);
            window.uiController.showToast("Lecture link submitted. Starting conversion...", "success");
            this.startTrackingJob(res.job_id);
        } catch (err) {
            window.uiController.showToast(err.message || "Failed to create job.", "error");
        } finally {
            this._setSubmitting(false);
        }
    }

    // ── File Upload Flow ───────────────────────────────────────────────────────
    _bindFileUpload() {
        const dropZone = document.getElementById("upload-zone");
        const fileInput = document.getElementById("file-input");
        const btnRemove = document.getElementById("file-remove");
        const btnConvert = document.getElementById("btn-convert-upload");

        if (!dropZone || !fileInput) return;

        // Browse click
        dropZone.addEventListener("click", (e) => {
            if (e.target.id !== "file-remove") fileInput.click();
        });

        // Drag & drop
        ["dragenter", "dragover"].forEach((name) => {
            dropZone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add("drag-over");
            });
        });

        ["dragleave", "drop"].forEach((name) => {
            dropZone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove("drag-over");
            });
        });

        dropZone.addEventListener("drop", (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                this._handleFileSelection(files[0]);
            }
        });

        fileInput.addEventListener("change", () => {
            if (fileInput.files && fileInput.files.length > 0) {
                this._handleFileSelection(fileInput.files[0]);
            }
        });

        const btnLoadSample = document.getElementById("btn-load-sample");
        if (btnLoadSample) {
            btnLoadSample.addEventListener("click", async (e) => {
                e.stopPropagation();
                btnLoadSample.disabled = true;
                btnLoadSample.textContent = "Loading sample file...";
                try {
                    const resp = await fetch("/api/sample-file");
                    if (!resp.ok) throw new Error("Could not fetch sample lecture file from server");
                    const blob = await resp.blob();
                    const file = new File([blob], "sample_5min_lecture.mp4", { type: "video/mp4" });
                    this._handleFileSelection(file);
                    window.uiController.showToast("Loaded tests/sample_5min_lecture.mp4 (9.3 MB) into upload queue", "success");
                } catch (err) {
                    window.uiController.showToast(err.message, "error");
                } finally {
                    btnLoadSample.disabled = false;
                    btnLoadSample.innerHTML = "📁 Load test lecture: <code>sample_5min_lecture.mp4</code>";
                }
            });
        }

        if (btnRemove) {
            btnRemove.addEventListener("click", (e) => {
                e.stopPropagation();
                this._clearSelectedFile();
            });
        }

        if (btnConvert) {
            btnConvert.addEventListener("click", () => this.submitUploadJob());
        }
    }

    _handleFileSelection(file) {
        const errEl = document.getElementById("upload-error-text");
        const dropPrompt = document.getElementById("upload-prompt");
        const selectedInfo = document.getElementById("upload-selected");
        const fileName = document.getElementById("file-name");
        const fileSize = document.getElementById("file-size");

        const allowedExts = [".mp4", ".mkv", ".webm", ".mov", ".mp3", ".wav", ".m4a", ".ogg", ".flac"];
        const ext = "." + file.name.split(".").pop().toLowerCase();

        if (!allowedExts.includes(ext)) {
            errEl.textContent = `Unsupported file format '${ext}'. Supported: ${allowedExts.join(", ")}`;
            errEl.style.display = "block";
            return;
        }

        const maxBytes = (this.maxUploadMb || 500) * 1024 * 1024;
        if (file.size > maxBytes) {
            errEl.textContent = `File exceeds the maximum upload limit of ${this.maxUploadMb || 500} MB.`;
            errEl.style.display = "block";
            return;
        }

        errEl.textContent = "";
        errEl.style.display = "none";

        this.selectedFile = file;
        fileName.textContent = file.name;
        fileSize.textContent = `(${(file.size / (1024 * 1024)).toFixed(1)} MB)`;

        dropPrompt.style.display = "none";
        selectedInfo.style.display = "flex";
    }

    _clearSelectedFile() {
        this.selectedFile = null;
        const fileInput = document.getElementById("file-input");
        if (fileInput) fileInput.value = "";

        const dropPrompt = document.getElementById("upload-prompt");
        const selectedInfo = document.getElementById("upload-selected");
        const uploadProgress = document.getElementById("upload-progress-box");

        if (dropPrompt) dropPrompt.style.display = "block";
        if (selectedInfo) selectedInfo.style.display = "none";
        if (uploadProgress) uploadProgress.style.display = "none";
    }

    async submitUploadJob() {
        if (this.isSubmitting) return;
        if (!this.selectedFile) {
            window.uiController.showToast("Please select or drop a lecture file first.", "warning");
            return;
        }

        const options = this._gatherJobOptions();
        const progressBox = document.getElementById("upload-progress-box");
        const progressBar = document.getElementById("upload-progress-bar");
        const progressText = document.getElementById("upload-progress-text");

        try {
            this._setSubmitting(true);
            if (progressBox) progressBox.style.display = "block";

            const res = await window.apiClient.createJobFromUpload(
                this.selectedFile,
                options,
                (pct) => {
                    if (progressBar) progressBar.style.width = `${pct}%`;
                    if (progressText) progressText.textContent = `Uploading file... ${pct}%`;
                }
            );

            window.uiController.showToast("File uploaded successfully. Initializing pipeline...", "success");
            this.startTrackingJob(res.job_id);
        } catch (err) {
            window.uiController.showToast(err.message || "Failed to upload file.", "error");
        } finally {
            this._setSubmitting(false);
            if (progressBox) progressBox.style.display = "none";
        }
    }

    _setSubmitting(submitting) {
        this.isSubmitting = submitting;
        document.querySelectorAll(".btn-convert").forEach((btn) => {
            btn.disabled = submitting;
            if (submitting) btn.classList.add("loading");
            else btn.classList.remove("loading");
        });
    }

    // ── Collapsibles & Advanced Options ────────────────────────────────────────
    _bindCollapsibles() {
        const toggleDetails = document.getElementById("details-toggle");
        const panelDetails = document.getElementById("details-panel");
        if (toggleDetails && panelDetails) {
            toggleDetails.addEventListener("click", () => {
                const isOpen = panelDetails.classList.toggle("open");
                toggleDetails.querySelector(".accordion-arrow").style.transform = isOpen ? "rotate(180deg)" : "rotate(0deg)";
            });
        }

        const toggleAdv = document.getElementById("advanced-toggle");
        const panelAdv = document.getElementById("advanced-panel");
        if (toggleAdv && panelAdv) {
            toggleAdv.addEventListener("click", () => {
                const isOpen = panelAdv.classList.toggle("open");
                toggleAdv.querySelector(".accordion-arrow").style.transform = isOpen ? "rotate(180deg)" : "rotate(0deg)";
            });
        }
    }

    _bindAdvancedOptions() {
        // AI Engine pills
        const enginePills = document.querySelectorAll("#engine-pills .pill");
        const timeWarning = document.getElementById("time-warning-box");
        const localModelGroup = document.getElementById("local-model-group");

        enginePills.forEach((pill) => {
            pill.addEventListener("click", () => {
                enginePills.forEach((p) => p.classList.remove("active"));
                pill.classList.add("active");
                const engine = pill.getAttribute("data-engine");

                if (engine === "ollama") {
                    if (timeWarning) timeWarning.style.display = "block";
                    if (localModelGroup) localModelGroup.style.display = "block";
                } else {
                    if (timeWarning) timeWarning.style.display = "none";
                    if (localModelGroup) localModelGroup.style.display = "none";
                }
            });
        });

        // Fast mode pills
        document.querySelectorAll("#fast-mode-pills .pill").forEach((pill) => {
            pill.addEventListener("click", () => {
                document.querySelectorAll("#fast-mode-pills .pill").forEach((p) => p.classList.remove("active"));
                pill.classList.add("active");
            });
        });

        // PDF Theme swatches
        document.querySelectorAll(".swatch-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".swatch-btn").forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
            });
        });

        // Question count slider
        const qSlider = document.getElementById("question-count");
        const qVal = document.getElementById("question-count-value");
        if (qSlider && qVal) {
            qSlider.addEventListener("input", () => {
                qVal.textContent = `${qSlider.value} questions`;
            });
        }
    }

    _gatherJobOptions() {
        const title = document.getElementById("lecture-title")?.value?.trim() || null;
        const subject = document.getElementById("lecture-subject")?.value?.trim() || null;
        const lectureType = document.getElementById("lecture-type")?.value || "auto";

        const activeEngine = document.querySelector("#engine-pills .pill.active")?.getAttribute("data-engine") || "gemini";
        const fastMode = document.querySelector("#fast-mode-pills .pill.active")?.getAttribute("data-fast") === "true";
        const whisperModel = document.getElementById("whisper-model-select")?.value || "small";
        const activeTheme = document.querySelector(".swatch-btn.active")?.getAttribute("data-theme") || "indigo";
        const questionCount = parseInt(document.getElementById("question-count")?.value || "12", 10);

        return {
            title,
            subject,
            lecture_type: lectureType,
            ai_engine: activeEngine,
            fast_mode: fastMode,
            whisper_model: whisperModel,
            theme: activeTheme,
            question_count: questionCount,
            detail_level: "detailed",
        };
    }

    _clearInputErrors() {
        const linkErr = document.getElementById("link-error-text");
        const uploadErr = document.getElementById("upload-error-text");
        if (linkErr) linkErr.style.display = "none";
        if (uploadErr) uploadErr.style.display = "none";
    }

    // ── Job Tracking & Polling Loop ────────────────────────────────────────────
    startTrackingJob(jobId, isRestored = false) {
        this.activeJobId = jobId;
        window.stateManager.setActiveJobId(jobId);
        window.uiController.showProgressView();

        if (!isRestored) {
            this.jobStartTime = Date.now();
        } else {
            this.jobStartTime = Date.now() - 10000;
        }

        this._startElapsedTimer();
        this._pollJob();
    }

    _startElapsedTimer() {
        if (this.elapsedTimer) clearInterval(this.elapsedTimer);
        this.elapsedTimer = setInterval(() => {
            if (!this.jobStartTime) return;
            const elapsed = Math.floor((Date.now() - this.jobStartTime) / 1000);
            const el = document.getElementById("progress-elapsed");
            if (el) {
                const m = Math.floor(elapsed / 60);
                const s = elapsed % 60;
                el.textContent = `Elapsed: ${m}m ${s < 10 ? "0" : ""}${s}s`;
            }
        }, 1000);
    }

    _stopElapsedTimer() {
        if (this.elapsedTimer) {
            clearInterval(this.elapsedTimer);
            this.elapsedTimer = null;
        }
    }

    async _pollJob() {
        if (this.pollTimer) clearTimeout(this.pollTimer);
        if (!this.activeJobId) return;

        try {
            const status = await window.apiClient.getJobStatus(this.activeJobId);
            const elapsed = this.jobStartTime ? Math.floor((Date.now() - this.jobStartTime) / 1000) : 0;
            window.uiController.updateProgress(status, elapsed);

            if (status.status === "completed") {
                this._stopElapsedTimer();
                window.stateManager.clearActiveJobId();
                window.stateManager.saveRecentJob(status);
                this._refreshRecentJobs();

                window.uiController.renderResult(status);
                window.uiController.showResultView();
                window.uiController.showToast("Study book PDF generated successfully!", "success");
                return;
            }

            if (status.status === "failed") {
                this._stopElapsedTimer();
                window.uiController.showToast(status.error || "Job failed.", "error", 6000);
                return;
            }

            if (status.status === "cancelled") {
                this._stopElapsedTimer();
                window.uiController.showToast("Job was cancelled.", "info");
                return;
            }

            // Normal polling cadence: 1.5 seconds
            this.pollTimer = setTimeout(() => this._pollJob(), 1500);
        } catch (err) {
            if (err.status === 404 || (err.message && err.message.toLowerCase().includes("job not found"))) {
                console.warn(`Job ${this.activeJobId} not found on server (server may have restarted). Resetting view.`);
                this._stopElapsedTimer();
                if (this.pollTimer) clearTimeout(this.pollTimer);
                this.activeJobId = null;
                window.stateManager.clearActiveJobId();
                window.uiController.showInputView();
                window.uiController.showToast("Previous job expired or server was restarted. Ready for a new lecture.", "info", 5000);
                return;
            }
            console.warn("Polling error, retrying in 3s:", err);
            // Backoff on network transient error
            this.pollTimer = setTimeout(() => this._pollJob(), 3000);
        }
    }

    _bindProgressControls() {
        const btnCancel = document.getElementById("btn-cancel-job");
        const btnResume = document.getElementById("btn-resume-job");
        const btnTrans = document.getElementById("btn-progress-transcript");
        const btnNew = document.getElementById("btn-new-conversion");

        if (btnCancel) {
            btnCancel.addEventListener("click", async () => {
                if (!this.activeJobId) return;
                btnCancel.disabled = true;
                try {
                    await window.apiClient.cancelJob(this.activeJobId);
                    window.uiController.showToast("Cancellation requested.", "info");
                    this._pollJob();
                } catch (err) {
                    window.uiController.showToast(err.message || "Failed to cancel job.", "error");
                } finally {
                    btnCancel.disabled = false;
                }
            });
        }

        if (btnResume) {
            btnResume.addEventListener("click", async () => {
                if (!this.activeJobId) return;
                btnResume.disabled = true;
                try {
                    await window.apiClient.resumeJob(this.activeJobId);
                    window.uiController.showToast("Resuming pipeline from checkpoint...", "success");
                    this._startElapsedTimer();
                    this._pollJob();
                } catch (err) {
                    window.uiController.showToast(err.message || "Cannot resume job.", "error");
                } finally {
                    btnResume.disabled = false;
                }
            });
        }

        if (btnTrans) {
            btnTrans.addEventListener("click", () => this.openTranscriptModal());
        }

        if (btnNew) {
            btnNew.addEventListener("click", () => {
                this.activeJobId = null;
                window.stateManager.clearActiveJobId();
                this._clearSelectedFile();
                const urlInput = document.getElementById("video-url");
                if (urlInput) urlInput.value = "";
                window.uiController.showInputView();
            });
        }

        // Result Card actions
        const btnResultTrans = document.getElementById("btn-view-transcript");
        const btnResultPreview = document.getElementById("btn-preview-pdf");

        if (btnResultTrans) {
            btnResultTrans.addEventListener("click", () => this.openTranscriptModal());
        }

        if (btnResultPreview) {
            btnResultPreview.addEventListener("click", () => {
                const title = document.getElementById("result-lecture-title")?.textContent || "Lecture";
                window.uiController.openPdfModal(this.activeJobId, title);
            });
        }
    }

    // ── Transcript & Preview Modals ────────────────────────────────────────────
    async openTranscriptModal() {
        if (!this.activeJobId) return;
        try {
            window.uiController.showToast("Loading transcript...", "info", 1000);
            const data = await window.apiClient.getJobTranscript(this.activeJobId);
            this.currentTranscript = data;
            window.uiController.openTranscriptModal(data);
        } catch (err) {
            window.uiController.showToast(err.message || "Transcript not available.", "error");
        }
    }

    openPreview(jobId, title) {
        window.uiController.openPdfModal(jobId, title);
    }

    _bindModals() {
        // Close modal buttons
        document.querySelectorAll(".modal-close").forEach((btn) => {
            btn.addEventListener("click", () => window.uiController.closeModals());
        });

        // Close on background overlay click
        document.querySelectorAll(".modal-overlay").forEach((overlay) => {
            overlay.addEventListener("click", (e) => {
                if (e.target === overlay) window.uiController.closeModals();
            });
        });

        // Close on Esc key
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") window.uiController.closeModals();
        });

        // Transcript search filter
        const searchInput = document.getElementById("transcript-search");
        if (searchInput) {
            searchInput.addEventListener("input", (e) => {
                const q = e.target.value;
                if (this.currentTranscript && this.currentTranscript.segments) {
                    window.uiController.renderTranscriptSegments(this.currentTranscript.segments, q);
                }
            });
        }

        // Transcript copy button
        const copyBtn = document.getElementById("btn-copy-transcript");
        if (copyBtn) {
            copyBtn.addEventListener("click", async () => {
                if (!this.currentTranscript || !this.currentTranscript.segments) return;
                const fullText = this.currentTranscript.segments.map((s) => s.text).join(" ");
                try {
                    await navigator.clipboard.writeText(fullText);
                    window.uiController.showToast("Full transcript copied to clipboard!", "success");
                } catch {
                    window.uiController.showToast("Failed to copy transcript to clipboard.", "error");
                }
            });
        }
    }

    // ── Recent Jobs ────────────────────────────────────────────────────────────
    _refreshRecentJobs() {
        const jobs = window.stateManager.getRecentJobs();
        window.uiController.renderRecentJobs(jobs);
    }
}

// Bootstrap on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    window.appController = new AppController();
    window.appController.init();
});
