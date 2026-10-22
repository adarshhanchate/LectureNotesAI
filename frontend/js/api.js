/**
 * LectureNotes AI — API Client Wrapper
 * 
 * Typed API client matching backend/main.py and backend/models.py endpoints.
 * Includes dev-only mock backend simulation (?mock=1).
 */

class ApiClient {
    constructor() {
        this.baseUrl = window.location.origin;
        this.isMock = new URLSearchParams(window.location.search).get("mock") === "1";
        this.mockJobs = new Map();
    }

    isMockMode() {
        return this.isMock;
    }

    /**
     * GET /api/health
     * @returns {Promise<{
     *   status: string,
     *   service: string,
     *   llm_provider: string,
     *   gemini_configured: boolean,
     *   gemini_model: string,
     *   ollama_url: string,
     *   ollama_model: string,
     *   demo_mode: boolean,
     *   whisper_model: string,
     *   whisper_device: string,
     *   whisper_compute_type: string,
     *   max_upload_size_mb: number,
     *   allowed_extensions: string[]
     * }>}
     */
    async getHealth() {
        if (this.isMock) {
            return {
                status: "ok",
                service: "LectureNotes AI (Mock)",
                llm_provider: "gemini",
                gemini_configured: true,
                gemini_model: "gemini-2.0-flash",
                ollama_url: "http://localhost:11434",
                ollama_model: "qwen2.5:7b",
                demo_mode: true,
                whisper_model: "small",
                whisper_device: "cpu",
                whisper_compute_type: "int8",
                max_upload_size_mb: 500,
                allowed_extensions: [".mp4", ".mkv", ".webm", ".mov", ".mp3", ".wav", ".m4a", ".ogg", ".flac"],
            };
        }

        const res = await fetch(`${this.baseUrl}/api/health`);
        if (!res.ok) {
            throw new Error(`Health check failed: HTTP ${res.status}`);
        }
        return await res.json();
    }

    /**
     * GET /api/jobs
     * @returns {Promise<Array<JobStatus>>}
     */
    async listJobs() {
        if (this.isMock) {
            return Array.from(this.mockJobs.values());
        }

        const res = await fetch(`${this.baseUrl}/api/jobs`);
        if (!res.ok) {
            throw new Error(`Failed to list jobs: HTTP ${res.status}`);
        }
        return await res.json();
    }

    /**
     * POST /api/jobs (Link submission)
     * @param {Object} options
     * @returns {Promise<{job_id: string, status: string}>}
     */
    async createJobFromUrl(options) {
        if (this.isMock) {
            return this._createMockJob(options.url || "https://example.com/lecture", options);
        }

        const res = await fetch(`${this.baseUrl}/api/jobs`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                url: options.url,
                ai_engine: options.ai_engine || "gemini",
                theme: options.theme || "indigo",
                fast_mode: options.fast_mode ?? true,
                detail_level: options.detail_level || "detailed",
                question_count: options.question_count || 12,
                title: options.title || null,
                subject: options.subject || null,
                lecture_type: options.lecture_type || "auto",
                whisper_model: options.whisper_model || "small",
            }),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            throw new Error(err.detail || "Failed to submit lecture link.");
        }
        return await res.json();
    }

    /**
     * POST /api/jobs (File upload with real upload progress tracking)
     * @param {File} file
     * @param {Object} options
     * @param {Function} onProgress - Callback (percent: number)
     * @returns {Promise<{job_id: string, status: string}>}
     */
    async createJobFromUpload(file, options, onProgress = null) {
        if (this.isMock) {
            if (onProgress) {
                onProgress(50);
                await new Promise((r) => setTimeout(r, 400));
                onProgress(100);
            }
            return this._createMockJob(file.name, options);
        }

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("POST", `${this.baseUrl}/api/jobs`);

            if (xhr.upload && onProgress) {
                xhr.upload.onprogress = (evt) => {
                    if (evt.lengthComputable) {
                        const pct = Math.round((evt.loaded / evt.total) * 100);
                        onProgress(pct);
                    }
                };
            }

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        resolve(data);
                    } catch (e) {
                        reject(new Error("Invalid server response format."));
                    }
                } else {
                    try {
                        const err = JSON.parse(xhr.responseText);
                        reject(new Error(err.detail || `Upload failed: HTTP ${xhr.status}`));
                    } catch {
                        reject(new Error(`Upload failed: HTTP ${xhr.status}`));
                    }
                }
            };

            xhr.onerror = () => reject(new Error("Network connection error during file upload."));
            xhr.onabort = () => reject(new Error("File upload aborted."));

            const formData = new FormData();
            formData.append("file", file);
            formData.append("ai_engine", options.ai_engine || "gemini");
            formData.append("theme", options.theme || "indigo");
            formData.append("fast_mode", String(options.fast_mode ?? true));
            formData.append("detail_level", options.detail_level || "detailed");
            formData.append("question_count", String(options.question_count || 12));
            if (options.title) formData.append("title", options.title);
            if (options.subject) formData.append("subject", options.subject);
            if (options.lecture_type) formData.append("lecture_type", options.lecture_type);
            if (options.whisper_model) formData.append("whisper_model", options.whisper_model);

            xhr.send(formData);
        });
    }

    /**
     * GET /api/jobs/{job_id}
     * @param {string} jobId
     * @returns {Promise<JobStatus>}
     */
    async getJobStatus(jobId) {
        if (this.isMock) {
            return this._getMockJobStatus(jobId);
        }

        const res = await fetch(`${this.baseUrl}/api/jobs/${jobId}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            const error = new Error(err.detail || "Failed to retrieve job status.");
            error.status = res.status;
            throw error;
        }
        return await res.json();
    }

    /**
     * POST /api/jobs/{job_id}/cancel
     * @param {string} jobId
     * @returns {Promise<{status: string, message: string}>}
     */
    async cancelJob(jobId) {
        if (this.isMock) {
            const job = this.mockJobs.get(jobId);
            if (job) {
                job.status = "cancelled";
                job.stage_label = "Job cancelled by user.";
                job.can_resume = true;
            }
            return { status: "cancelled", message: "Job cancelled successfully." };
        }

        const res = await fetch(`${this.baseUrl}/api/jobs/${jobId}/cancel`, { method: "POST" });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            throw new Error(err.detail || "Failed to cancel job.");
        }
        return await res.json();
    }

    /**
     * POST /api/jobs/{job_id}/resume
     * @param {string} jobId
     * @returns {Promise<{status: string, message: string}>}
     */
    async resumeJob(jobId) {
        if (this.isMock) {
            const job = this.mockJobs.get(jobId);
            if (job) {
                job.status = "transcribing";
                job.stage_label = "Resuming mock pipeline...";
                job.progress = Math.max(job.progress, 35);
                job.mockStartTime = Date.now() - (job.progress / 100) * 12000;
            }
            return { status: "resumed", message: "Mock pipeline resumed." };
        }

        const res = await fetch(`${this.baseUrl}/api/jobs/${jobId}/resume`, { method: "POST" });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            throw new Error(err.detail || "Failed to resume job.");
        }
        return await res.json();
    }

    /**
     * GET /api/jobs/{job_id}/transcript
     * @param {string} jobId
     * @returns {Promise<{job_id: string, language: string, segments: Array<{start: number, end: number, text: string}>}>}
     */
    async getJobTranscript(jobId) {
        if (this.isMock) {
            return {
                job_id: jobId,
                language: "en",
                raw_text: "Welcome to this lecture on knowledge-based agents and Wumpus World...",
                cleaned_text: "Welcome to this lecture on knowledge-based agents and Wumpus World...",
                segments: [
                    { start: 0.0, end: 4.5, text: "Welcome back. In this video I will discuss how an agent finds a path in Wumpus World." },
                    { start: 4.5, end: 12.0, text: "The agent is initially placed in square [1,1] which is guaranteed safe." },
                    { start: 12.0, end: 18.5, text: "Adjacent squares with a breeze indicate a nearby pit." },
                    { start: 18.5, end: 25.0, text: "Adjacent squares with a stench indicate the Wumpus monster is nearby." },
                    { start: 25.0, end: 32.0, text: "When reaching the gold, the glitter sensor activates." },
                ],
            };
        }

        const res = await fetch(`${this.baseUrl}/api/jobs/${jobId}/transcript`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            throw new Error(err.detail || "Transcript not ready yet.");
        }
        return await res.json();
    }

    getPdfDownloadUrl(jobId) {
        return `${this.baseUrl}/api/jobs/${jobId}/download`;
    }

    getPdfPreviewUrl(jobId) {
        return `${this.baseUrl}/api/jobs/${jobId}/preview`;
    }

    getTranscriptTextUrl(jobId) {
        return `${this.baseUrl}/api/jobs/${jobId}/transcript?format=text`;
    }

    // ── Mock Backend Internal Helper ───────────────────────────────────────────
    _createMockJob(sourceName, options) {
        const jobId = "mock_" + Math.random().toString(36).substring(2, 9);
        const job = {
            job_id: jobId,
            status: "downloading",
            stage_label: "Downloading lecture media...",
            progress: 10,
            current_chunk: 1,
            total_chunks: 1,
            error: null,
            title: options.title || sourceName.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " "),
            duration_seconds: 490,
            word_count: 1575,
            concept_count: 3,
            example_count: 2,
            numerical_count: 2,
            formula_count: 4,
            question_count: options.question_count || 12,
            created_at: new Date().toISOString(),
            pdf_ready: false,
            transcript_ready: false,
            is_demo: true,
            can_resume: false,
            ai_engine: options.ai_engine || "gemini",
            theme: options.theme || "indigo",
            mockStartTime: Date.now(),
        };
        this.mockJobs.set(jobId, job);
        return { job_id: jobId, status: "queued" };
    }

    _getMockJobStatus(jobId) {
        const job = this.mockJobs.get(jobId);
        if (!job) throw new Error("Mock job not found.");

        if (job.status === "cancelled" || job.status === "failed") {
            return job;
        }

        const elapsed = (Date.now() - job.mockStartTime) / 1000;
        if (elapsed < 2) {
            job.status = "downloading";
            job.progress = 12;
            job.stage_label = "Downloading lecture media...";
        } else if (elapsed < 4) {
            job.status = "extracting_audio";
            job.progress = 25;
            job.stage_label = "Extracting 16kHz audio...";
        } else if (elapsed < 7) {
            job.status = "transcribing";
            job.progress = 48;
            job.stage_label = "Transcribing with Whisper (CPU int8)...";
            job.transcript_ready = true;
        } else if (elapsed < 10) {
            job.status = "structuring_notes";
            job.progress = 72;
            job.stage_label = "Structuring notes with AI...";
        } else if (elapsed < 13) {
            job.status = "generating_questions";
            job.progress = 88;
            job.stage_label = "Generating categorized exam questions...";
        } else if (elapsed < 15) {
            job.status = "building_pdf";
            job.progress = 95;
            job.stage_label = "Rendering math formulas & compiling PDF...";
        } else {
            job.status = "completed";
            job.progress = 100;
            job.stage_label = "Done! Your study book is ready.";
            job.pdf_ready = true;
        }
        return job;
    }
}

// Export singleton
window.apiClient = new ApiClient();
