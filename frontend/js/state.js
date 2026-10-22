/**
 * LectureNotes AI — State & LocalStorage Manager
 * 
 * Handles theme persistence, active job recovery across reloads,
 * and recent conversions history (with 24h expiration marker).
 */

class StateManager {
    constructor() {
        this.STORAGE_KEYS = {
            THEME: "lecturenotes_theme",
            ACTIVE_JOB: "lecturenotes_active_job_id",
            RECENT_JOBS: "lecturenotes_recent_jobs",
            SETTINGS: "lecturenotes_settings",
        };
    }

    // ── Theme State ────────────────────────────────────────────────────────────
    getTheme() {
        const stored = localStorage.getItem(this.STORAGE_KEYS.THEME);
        if (stored === "light" || stored === "dark") return stored;
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light";
    }

    setTheme(theme) {
        localStorage.setItem(this.STORAGE_KEYS.THEME, theme);
        document.documentElement.setAttribute("data-theme", theme);
    }

    toggleTheme() {
        const current = this.getTheme();
        const next = current === "dark" ? "light" : "dark";
        this.setTheme(next);
        return next;
    }

    // ── Active Job Recovery ────────────────────────────────────────────────────
    getActiveJobId() {
        return localStorage.getItem(this.STORAGE_KEYS.ACTIVE_JOB);
    }

    setActiveJobId(jobId) {
        if (jobId) {
            localStorage.setItem(this.STORAGE_KEYS.ACTIVE_JOB, jobId);
        } else {
            localStorage.removeItem(this.STORAGE_KEYS.ACTIVE_JOB);
        }
    }

    clearActiveJobId() {
        localStorage.removeItem(this.STORAGE_KEYS.ACTIVE_JOB);
    }

    // ── Recent Conversions (Last 10) ───────────────────────────────────────────
    getRecentJobs() {
        try {
            const raw = localStorage.getItem(this.STORAGE_KEYS.RECENT_JOBS);
            if (!raw) return [];
            const list = JSON.parse(raw);
            const now = Date.now();
            const ONE_DAY_MS = 24 * 60 * 60 * 1000;

            return list.map((job) => {
                const age = now - new Date(job.created_at || now).getTime();
                return {
                    ...job,
                    is_expired: age > ONE_DAY_MS,
                };
            });
        } catch {
            return [];
        }
    }

    saveRecentJob(jobData) {
        try {
            const existing = this.getRecentJobs().filter((j) => j.job_id !== jobData.job_id);
            const updated = [
                {
                    job_id: jobData.job_id,
                    title: jobData.title || "Lecture Notes",
                    created_at: jobData.created_at || new Date().toISOString(),
                    status: jobData.status || "completed",
                    ai_engine: jobData.ai_engine || "gemini",
                    theme: jobData.theme || "indigo",
                    duration_seconds: jobData.duration_seconds || null,
                },
                ...existing,
            ].slice(0, 10);

            localStorage.setItem(this.STORAGE_KEYS.RECENT_JOBS, JSON.stringify(updated));
        } catch (e) {
            console.warn("Could not save recent job to localStorage:", e);
        }
    }

    // ── User Settings Persistence ──────────────────────────────────────────────
    getSavedSettings() {
        try {
            const raw = localStorage.getItem(this.STORAGE_KEYS.SETTINGS);
            return raw ? JSON.parse(raw) : {};
        } catch {
            return {};
        }
    }

    saveSettings(settings) {
        try {
            const current = this.getSavedSettings();
            localStorage.setItem(
                this.STORAGE_KEYS.SETTINGS,
                JSON.stringify({ ...current, ...settings })
            );
        } catch (e) {
            console.warn("Could not save settings:", e);
        }
    }
}

window.stateManager = new StateManager();
