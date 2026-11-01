// ExamAI - AI Paper Generator Frontend Logic (Version 5 - Resilient & Observable)
// Guarantees: Never-dead button, immediate validation feedback, safe event delegation,
// centralized API routes, draft persistence, live progress, and diagnostics.

(function () {
    "use strict";

    // ==========================================
    // 1. CENTRAL API CONSTANTS & AUTH HELPERS
    // ==========================================
    const API_ROUTES = {
        GENERATE: "/api/ai-generator/generate/",
        STATUS: (id) => `/api/ai-generator/jobs/${id}/status/`,
        DETAIL: (id) => `/api/ai-generator/jobs/${id}/`,
        CANCEL: (id) => `/api/ai-generator/jobs/${id}/cancel/`,
        ACTIVE_JOB: "/api/ai-generator/jobs/active/",
        MODELS: "/api/ai-generator/models/",
        DRAFT: "/api/ai-generator/draft/",
        BLUEPRINT_SUGGEST: "/api/ai-generator/blueprint/suggest/",
        EXPORT: (id, fmt) => `/api/ai-generator/jobs/${id}/export/?format=${fmt}`
    };

    const DRAFT_STORAGE_KEY = "examai_ai_paper_generator_draft_v1";

    const questionTypes = [
        { type: "MCQ", count: 10, marks: 1 },
        { type: "True/False", count: 5, marks: 1 },
        { type: "Fill in the Blank", count: 5, marks: 1 },
        { type: "Short Answer", count: 5, marks: 3 },
        { type: "Long Answer", count: 3, marks: 5 }
    ];

    let uploadedFiles = [];
    let savedUploadedFiles = [];
    let activeJobId = null;
    let pollInterval = null;
    let isSubmitting = false;
    let autoSaveTimer = null;
    let lastApiError = null;
    let loadedQuestions = [];

    // Diagnostic state tracker
    const pageDiagnostics = {
        jsLoaded: true,
        jsLoadTime: new Date().toISOString(),
        modelsLoaded: false,
        modelsCount: 0,
        modelsOllamaOnline: false,
        lastError: null
    };

    function getAuthToken() {
        if (window.EXAMAI_CONFIG && window.EXAMAI_CONFIG.authToken) {
            return window.EXAMAI_CONFIG.authToken;
        }
        try {
            const authRaw = sessionStorage.getItem("exam_ai_auth") || localStorage.getItem("exam_ai_auth");
            if (authRaw) {
                const parsed = JSON.parse(authRaw);
                if (parsed && parsed.access) return parsed.access;
            }
        } catch {}
        return localStorage.getItem("access_token") || localStorage.getItem("token") || "";
    }

    function getCsrfToken() {
        if (window.EXAMAI_CONFIG && window.EXAMAI_CONFIG.csrfToken) {
            return window.EXAMAI_CONFIG.csrfToken;
        }
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : "";
    }

    function getAuthHeaders(includeContentType = true) {
        const headers = {};
        const token = getAuthToken();
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        const csrf = getCsrfToken();
        if (csrf) {
            headers["X-CSRFToken"] = csrf;
        }
        if (includeContentType) {
            headers["Content-Type"] = "application/json";
        }
        return headers;
    }

    // ==========================================
    // 2. DOM ELEMENT SELECTORS
    // ==========================================
    const examTitleInput = document.getElementById("exam-title");
    const subjectNameInput = document.getElementById("subject-name");
    const classSemInput = document.getElementById("class-sem");
    const examTypeSelect = document.getElementById("exam-type");
    const durationInput = document.getElementById("duration-mins");
    const totalMarksInput = document.getElementById("total-marks");
    const topicsInput = document.getElementById("topics-input");

    const allocatedMarksNum = document.getElementById("allocated-marks-num");
    const targetMarksNum = document.getElementById("target-marks-num");
    const marksMatchStatus = document.getElementById("marks-match-status");
    const blueprintRows = document.getElementById("blueprint-rows");
    const btnAutoDistribute = document.getElementById("btn-auto-distribute");

    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");
    const fileList = document.getElementById("file-list");

    const selectGenerator = document.getElementById("select-generator");
    const selectValidator = document.getElementById("select-validator");
    const selectFallback = document.getElementById("select-fallback");

    const btnGenerate = document.getElementById("btn-generate-paper");
    const generateButtonHint = document.getElementById("generate-button-hint");
    const btnStickyGenerate = document.getElementById("btn-sticky-generate");
    const stickyHint = document.getElementById("sticky-hint");
    const stickyMarksPill = document.getElementById("sticky-marks-pill");
    const stickyQuestionsCount = document.getElementById("sticky-questions-count");

    const btnClearDraft = document.getElementById("btn-clear-draft");
    const continueReviewCard = document.getElementById("continue-review-card");
    const btnContinueReview = document.getElementById("btn-continue-review");

    const validationAlert = document.getElementById("validation-alert");
    const alertMessage = document.getElementById("alert-message");
    const progressSection = document.getElementById("progress-section");
    const progressBarFill = document.getElementById("progress-bar-fill");
    const progressPercentLabel = document.getElementById("progress-percent-label");
    const progressSlotLabel = document.getElementById("progress-slot-label");
    const progressMessage = document.getElementById("progress-message");
    const progressTitle = document.getElementById("progress-title");
    const btnCancelGeneration = document.getElementById("btn-cancel-generation");
    const wizardFormSection = document.getElementById("wizard-form-section");
    const reviewSection = document.getElementById("review-section");
    const questionsList = document.getElementById("questions-list");
    const filterType = document.getElementById("filter-type");

    // ==========================================
    // 3. BLUEPRINT & MARKS COMPUTATION
    // ==========================================
    function renderBlueprintRows(savedRows) {
        if (!blueprintRows) return;
        blueprintRows.innerHTML = "";
        questionTypes.forEach((qt, idx) => {
            const saved = savedRows ? savedRows[idx] : null;
            const isChecked = saved !== null && saved !== undefined ? Boolean(saved.enabled) : true;
            const countVal = saved && typeof saved.count === "number" ? saved.count : qt.count;
            const marksVal = saved && typeof saved.marks_per_question === "number" ? saved.marks_per_question : qt.marks;

            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><input type="checkbox" ${isChecked ? "checked" : ""} data-idx="${idx}" class="bp-enable cursor-pointer"></td>
                <td><strong>${qt.type}</strong></td>
                <td><input type="number" min="0" value="${countVal}" data-idx="${idx}" class="form-control bp-count" style="width: 80px;"></td>
                <td><input type="number" min="1" value="${marksVal}" data-idx="${idx}" class="form-control bp-marks" style="width: 80px;"></td>
                <td class="font-bold bp-subtotal">${isChecked ? (countVal * marksVal) : 0}M</td>
            `;
            blueprintRows.appendChild(tr);
        });
        recalcMarks();
    }

    function getBlueprintState() {
        let totalAllocated = 0;
        let totalQuestions = 0;
        let activeSectionsCount = 0;
        const rows = blueprintRows ? blueprintRows.querySelectorAll("tr") : [];
        const list = [];

        rows.forEach((tr, idx) => {
            const enableEl = tr.querySelector(".bp-enable");
            const countEl = tr.querySelector(".bp-count");
            const marksEl = tr.querySelector(".bp-marks");
            const subtotalEl = tr.querySelector(".bp-subtotal");

            const enabled = enableEl ? enableEl.checked : false;
            const count = countEl ? (parseInt(countEl.value, 10) || 0) : 0;
            const marks = marksEl ? (parseInt(marksEl.value, 10) || 0) : 0;
            const subtotal = enabled ? (count * marks) : 0;

            if (subtotalEl) subtotalEl.textContent = subtotal + "M";
            totalAllocated += subtotal;

            const secData = {
                type: questionTypes[idx] ? questionTypes[idx].type : `Type-${idx}`,
                count: count,
                marks_per_question: marks,
                section_name: questionTypes[idx] ? questionTypes[idx].type : "",
                enabled: enabled
            };

            if (enabled && count > 0) {
                totalQuestions += count;
                activeSectionsCount += 1;
            }
            list.push(secData);
        });

        const target = totalMarksInput ? (Number(totalMarksInput.value) || 0) : 0;
        return { totalAllocated, target, totalQuestions, activeSectionsCount, list };
    }

    function recalcMarks() {
        const { totalAllocated, target, totalQuestions } = getBlueprintState();

        if (allocatedMarksNum) allocatedMarksNum.textContent = totalAllocated;
        if (targetMarksNum) targetMarksNum.textContent = target;

        const isExactMatch = Math.abs(Number(totalAllocated) - Number(target)) < 0.001 && Number(target) > 0;

        if (marksMatchStatus) {
            if (isExactMatch) {
                marksMatchStatus.textContent = "Matches Target Marks Exactly";
                marksMatchStatus.className = "status-match text-emerald";
            } else {
                marksMatchStatus.textContent = `Mismatch: Allocated ${totalAllocated}M != Target ${target}M`;
                marksMatchStatus.className = "status-match text-rose";
            }
        }

        if (stickyMarksPill) {
            stickyMarksPill.textContent = `Allocated: ${totalAllocated} / ${target} M`;
            stickyMarksPill.className = isExactMatch ? "sticky-pill pill-match" : "sticky-pill pill-mismatch";
        }
        if (stickyQuestionsCount) {
            stickyQuestionsCount.textContent = `${totalQuestions} Questions Planned`;
        }

        updateGenerateButtonState();
        scheduleAutoSave();
    }

    // ==========================================
    // 4. FORM VALIDATION & SCROLL-TO-ERROR
    // ==========================================
    function validateForm() {
        const bpState = getBlueprintState();
        const subject = subjectNameInput ? subjectNameInput.value.trim() : "";
        const hasFiles = uploadedFiles.length > 0 || savedUploadedFiles.length > 0;
        const topics = (topicsInput ? topicsInput.value : "").split(",").map(s => s.trim()).filter(Boolean);
        const hasSyllabusOrTopics = hasFiles || topics.length > 0;
        const isExactMatch = Math.abs(Number(bpState.totalAllocated) - Number(bpState.target)) < 0.001 && Number(bpState.target) > 0;
        const hasSections = Number(bpState.activeSectionsCount) > 0;

        if (activeJobId || isSubmitting) {
            return {
                valid: false,
                field: null,
                message: "A generation job is currently in progress. Please wait or cancel the active job."
            };
        }

        if (!subject) {
            return {
                valid: false,
                field: subjectNameInput,
                message: "Please enter a Subject / Course Name."
            };
        }

        if (!hasSyllabusOrTopics) {
            return {
                valid: false,
                field: dropzone || topicsInput,
                message: "Please upload at least one syllabus document or enter curriculum topics."
            };
        }

        if (!hasSections) {
            return {
                valid: false,
                field: blueprintRows,
                message: "Please enable at least one question section with count > 0 in the blueprint."
            };
        }

        if (!isExactMatch) {
            return {
                valid: false,
                field: totalMarksInput,
                message: `Allocated marks (${bpState.totalAllocated}) must match target marks (${bpState.target}) exactly.`
            };
        }

        return { valid: true, bpState, subject, topics };
    }

    function highlightAndScrollTo(element, message) {
        if (validationAlert && alertMessage) {
            alertMessage.textContent = message;
            validationAlert.style.display = "flex";
        }

        if (!element) return;

        // Clear existing highlights
        document.querySelectorAll(".field-highlight-error").forEach(el => el.classList.remove("field-highlight-error"));

        element.classList.add("field-highlight-error");
        element.scrollIntoView({ behavior: "smooth", block: "center" });

        if (typeof element.focus === "function") {
            try { element.focus(); } catch {}
        }

        // Remove highlight animation after 3 seconds
        setTimeout(() => {
            element.classList.remove("field-highlight-error");
        }, 3000);
    }

    // ==========================================
    // 5. BUTTON STATE (ALWAYS CLICKABLE, NEVER SILENTLY DEAD)
    // ==========================================
    function updateGenerateButtonState() {
        if (!btnGenerate) return;

        // Never set btnGenerate.disabled = true; keep it always clickable!
        btnGenerate.disabled = false;
        if (btnStickyGenerate) btnStickyGenerate.disabled = false;

        const val = validateForm();
        const canGenerate = val.valid && !isSubmitting;

        if (canGenerate) {
            btnGenerate.classList.remove("btn-dimmed");
            if (btnStickyGenerate) btnStickyGenerate.classList.remove("btn-dimmed");
            if (generateButtonHint) generateButtonHint.style.display = "none";
            if (stickyHint) stickyHint.textContent = "";
        } else {
            btnGenerate.classList.add("btn-dimmed");
            if (btnStickyGenerate) btnStickyGenerate.classList.add("btn-dimmed");
            if (generateButtonHint) {
                generateButtonHint.textContent = val.message || "";
                generateButtonHint.style.display = isSubmitting ? "none" : "block";
            }
            if (stickyHint) {
                stickyHint.textContent = isSubmitting ? "" : (val.message || "");
            }
        }

        if (isSubmitting) {
            btnGenerate.innerHTML = `<span class="spin-inline">&#9696;</span> Generating Paper...`;
            if (btnStickyGenerate) btnStickyGenerate.innerHTML = `<span class="spin-inline">&#9696;</span> Generating...`;
        } else {
            btnGenerate.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
                Generate Examination Paper (AI)
            `;
            if (btnStickyGenerate) btnStickyGenerate.textContent = "Generate with AI";
        }
    }

    // ==========================================
    // 6. SINGLE SUBMIT FUNCTION (handleGenerateClick)
    // ==========================================
    async function handleGenerateClick() {
        // Double-click guard
        if (isSubmitting) {
            console.log("Submission already in progress, ignoring duplicate click.");
            return;
        }

        // Validate form: on failure, scroll & highlight immediately
        const val = validateForm();
        if (!val.valid) {
            highlightAndScrollTo(val.field, val.message);
            return;
        }

        try {
            isSubmitting = true;
            updateGenerateButtonState();

            if (validationAlert) validationAlert.style.display = "none";
            document.querySelectorAll(".field-error").forEach(el => el.textContent = "");

            const sections = val.bpState.list.filter(s => s.enabled && Number(s.count) > 0);
            const formData = new FormData();
            formData.append("title", examTitleInput ? examTitleInput.value : "Exam Paper");
            formData.append("subject", val.subject);
            formData.append("class_semester", classSemInput ? classSemInput.value : "");
            formData.append("exam_type", examTypeSelect ? examTypeSelect.value : "Final Examination");
            formData.append("duration", durationInput ? String(Number(durationInput.value) || 60) : "60");
            formData.append("total_marks", String(val.bpState.target));
            formData.append("sections", JSON.stringify(sections));
            formData.append("topics", JSON.stringify(val.topics));
            formData.append("model_generator", selectGenerator ? selectGenerator.value : "");
            formData.append("model_validator", selectValidator ? selectValidator.value : "");
            formData.append("model_fallback", selectFallback ? selectFallback.value : "");

            uploadedFiles.forEach(f => formData.append("files", f));

            console.log("Sending POST to /api/ai-generator/generate/ ...");
            const res = await fetch(API_ROUTES.GENERATE, {
                method: "POST",
                headers: getAuthHeaders(false), // Do not set Content-Type; browser handles multipart boundary
                body: formData
            });

            const data = await res.json().catch(() => ({ error: "Invalid response from server." }));

            if (!res.ok) {
                lastApiError = data.error || `HTTP ${res.status}`;
                pageDiagnostics.lastError = lastApiError;
                console.error("Generate API returned error:", res.status, data);

                if (validationAlert && alertMessage) {
                    alertMessage.textContent = data.error || "Failed to initiate generation.";
                    validationAlert.style.display = "flex";
                }
                if (data.fields) {
                    Object.entries(data.fields).forEach(([fld, msgs]) => {
                        const errSpan = document.getElementById(`err-${fld}`);
                        if (errSpan) errSpan.textContent = Array.isArray(msgs) ? msgs.join(", ") : String(msgs);
                    });
                }
                return;
            }

            // Success: store job ID, switch to progress view, start polling
            activeJobId = data.job_id;
            console.log(`Job #${activeJobId} started successfully.`);
            if (wizardFormSection) wizardFormSection.style.display = "none";
            if (progressSection) progressSection.style.display = "block";
            startPolling(activeJobId);

        } catch (err) {
            console.error("Generate paper request exception:", err);
            lastApiError = err.message || String(err);
            pageDiagnostics.lastError = lastApiError;
            if (validationAlert && alertMessage) {
                alertMessage.textContent = "Network error connecting to backend: " + (err.message || err);
                validationAlert.style.display = "flex";
            }
        } finally {
            isSubmitting = false;
            updateGenerateButtonState();
        }
    }

    // ==========================================
    // 7. POLLING & PROGRESS VIEW
    // ==========================================
    function startPolling(jobId) {
        if (pollInterval) clearInterval(pollInterval);
        console.log(`Polling status for job #${jobId} every 2 seconds...`);

        pollInterval = setInterval(async () => {
            try {
                const res = await fetch(API_ROUTES.STATUS(jobId), {
                    headers: getAuthHeaders(true)
                });
                if (res.ok) {
                    const job = await res.json();
                    if (progressBarFill) progressBarFill.style.width = `${job.progress_percent}%`;
                    if (progressPercentLabel) progressPercentLabel.textContent = `${job.progress_percent}%`;
                    if (progressSlotLabel) progressSlotLabel.textContent = `Slot ${job.current_slot_index} / ${job.total_slots}`;
                    if (progressMessage) progressMessage.textContent = job.progress_message;

                    if (job.status === "completed") {
                        clearInterval(pollInterval);
                        console.log(`Job #${jobId} completed! Loading review...`);
                        loadReview(jobId);
                    } else if (job.status === "failed" || job.status === "cancelled") {
                        clearInterval(pollInterval);
                        if (progressTitle) progressTitle.textContent = job.status === "cancelled" ? "Generation Cancelled" : "Generation Failed";
                        if (progressMessage) progressMessage.textContent = job.error_message || "Operation terminated.";
                        setTimeout(() => {
                            activeJobId = null;
                            if (progressSection) progressSection.style.display = "none";
                            if (wizardFormSection) wizardFormSection.style.display = "block";
                            updateGenerateButtonState();
                        }, 2500);
                    }
                } else if (res.status === 404 || res.status === 401) {
                    console.warn(`Polling error status: ${res.status}`);
                }
            } catch (err) {
                console.warn("Polling network error:", err);
            }
        }, 2000);
    }

    // Cancel Job Action
    async function cancelActiveJob() {
        if (!activeJobId) return;
        try {
            await fetch(API_ROUTES.CANCEL(activeJobId), {
                method: "POST",
                headers: getAuthHeaders(true)
            });
        } catch {}
        if (pollInterval) clearInterval(pollInterval);
        activeJobId = null;
        if (progressSection) progressSection.style.display = "none";
        if (wizardFormSection) wizardFormSection.style.display = "block";
        updateGenerateButtonState();
    }

    // ==========================================
    // 8. REVIEW SCREEN
    // ==========================================
    async function loadReview(jobId) {
        if (progressSection) progressSection.style.display = "none";
        if (reviewSection) reviewSection.style.display = "block";
        try {
            const res = await fetch(API_ROUTES.DETAIL(jobId), {
                headers: getAuthHeaders(true)
            });
            if (res.ok) {
                const job = await res.json();
                loadedQuestions = job.generated_questions || [];
                renderQuestions(loadedQuestions);
            }
        } catch (err) {
            console.error("Failed to load review questions:", err);
        }
    }

    function renderQuestions(questions) {
        if (!questionsList) return;
        questionsList.innerHTML = "";

        const selectedType = filterType ? filterType.value : "ALL";
        const filtered = selectedType === "ALL"
            ? questions
            : questions.filter(q => q.type === selectedType);

        if (filtered.length === 0) {
            questionsList.innerHTML = `<p class="text-muted p-4 text-center">No questions match filter "${selectedType}".</p>`;
            return;
        }

        filtered.forEach(q => {
            const card = document.createElement("div");
            card.className = "card question-card mt-2 animate-fade-in";
            card.innerHTML = `
                <div class="flex-between">
                    <div>
                        <span class="card-badge">Q${q.question_number} &bull; ${q.type}</span>
                        <span class="role-badge ml-2">${q.difficulty}</span>
                    </div>
                    <span class="font-bold text-primary">${q.marks} Marks</span>
                </div>
                <p class="mt-2 text-base font-semibold text-slate-900">${q.question}</p>
                ${q.options && q.options.length ? `
                    <ul class="options-list mt-2">
                        ${q.options.map(opt => `<li>${opt}</li>`).join("")}
                    </ul>
                ` : ""}
                <div class="answer-box mt-2">
                    <strong>Model Answer / Solution:</strong> ${q.answer}
                </div>
            `;
            questionsList.appendChild(card);
        });
    }

    // ==========================================
    // 9. FILE UPLOAD & LIST MANAGEMENT
    // ==========================================
    function handleFilesAdded(files) {
        for (const file of files) {
            uploadedFiles.push(file);
            savedUploadedFiles.push({
                name: file.name,
                size: file.size,
                type: file.type || "application/octet-stream"
            });
        }
        updateFileList();
        updateGenerateButtonState();
        scheduleAutoSave();
    }

    function updateFileList() {
        if (!fileList) return;
        fileList.innerHTML = "";

        const allFiles = [];
        uploadedFiles.forEach((file, idx) => {
            allFiles.push({ name: file.name, size: file.size, isLive: true, index: idx });
        });
        savedUploadedFiles.forEach((f, idx) => {
            if (!uploadedFiles.some(uf => uf.name === f.name)) {
                allFiles.push({ name: f.name, size: f.size, isLive: false, index: idx });
            }
        });

        allFiles.forEach(item => {
            const li = document.createElement("li");
            li.className = "file-list-item";
            li.innerHTML = `
                <div class="file-info">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span class="file-name">${item.name}</span>
                    <span class="file-size text-muted">(${(item.size / 1024).toFixed(1)} KB)</span>
                    ${!item.isLive ? `<span class="badge badge-saved">Saved Document</span>` : ""}
                </div>
                <button type="button" class="btn-remove-file" title="Remove file">&times;</button>
            `;

            li.querySelector(".btn-remove-file").addEventListener("click", () => {
                if (item.isLive) {
                    uploadedFiles = uploadedFiles.filter((_, i) => i !== item.index);
                }
                savedUploadedFiles = savedUploadedFiles.filter(sf => sf.name !== item.name);
                updateFileList();
                updateGenerateButtonState();
                scheduleAutoSave();
            });

            fileList.appendChild(li);
        });
    }

    // ==========================================
    // 10. AUTOSAVE & RESTORE DRAFTS
    // ==========================================
    function scheduleAutoSave() {
        if (autoSaveTimer) clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(saveDraftData, 500);
    }

    function saveDraftData() {
        try {
            const bpState = getBlueprintState();
            const draft = {
                version: 4,
                updatedAt: new Date().toISOString(),
                title: examTitleInput ? examTitleInput.value : "",
                subject: subjectNameInput ? subjectNameInput.value : "",
                class_semester: classSemInput ? classSemInput.value : "",
                exam_type: examTypeSelect ? examTypeSelect.value : "Final Examination",
                duration: durationInput ? durationInput.value : "60",
                total_marks: totalMarksInput ? totalMarksInput.value : "50",
                topics: topicsInput ? topicsInput.value : "",
                generator_model: selectGenerator ? selectGenerator.value : "",
                validator_model: selectValidator ? selectValidator.value : "",
                fallback_model: selectFallback ? selectFallback.value : "",
                blueprint: bpState.list,
                uploadedFiles: savedUploadedFiles
            };

            localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));

            fetch(API_ROUTES.DRAFT, {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify({ draft, version: 4 })
            }).catch(() => {});
        } catch (err) {
            console.warn("Autosave draft failed:", err);
        }
    }

    async function loadSavedDraft() {
        let draft = null;

        try {
            const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
            if (raw) draft = JSON.parse(raw);
        } catch (e) {
            localStorage.removeItem(DRAFT_STORAGE_KEY);
        }

        if (!draft) {
            try {
                const res = await fetch(API_ROUTES.DRAFT, { headers: getAuthHeaders(true) });
                if (res.ok) {
                    const data = await res.json();
                    if (data && data.draft) draft = data.draft;
                }
            } catch {}
        }

        if (!draft) {
            renderBlueprintRows();
            return;
        }

        if (draft.title && examTitleInput) examTitleInput.value = draft.title;
        if (draft.subject && subjectNameInput) subjectNameInput.value = draft.subject;
        if (draft.class_semester && classSemInput) classSemInput.value = draft.class_semester;
        if (draft.exam_type && examTypeSelect) examTypeSelect.value = draft.exam_type;
        if (draft.duration && durationInput) durationInput.value = draft.duration;
        if (draft.total_marks && totalMarksInput) totalMarksInput.value = draft.total_marks;
        if (draft.topics && topicsInput) topicsInput.value = draft.topics;

        if (Array.isArray(draft.uploadedFiles)) {
            savedUploadedFiles = draft.uploadedFiles;
            updateFileList();
        }

        renderBlueprintRows(draft.blueprint);

        if (draft.generator_model && selectGenerator) selectGenerator.value = draft.generator_model;
        if (draft.validator_model && selectValidator) selectValidator.value = draft.validator_model;
        if (draft.fallback_model && selectFallback) selectFallback.value = draft.fallback_model;

        recalcMarks();
    }

    // ==========================================
    // 11. OLLAMA MODELS & ACTIVE JOB RECOVERY
    // ==========================================
    async function loadModels() {
        const pillText = document.getElementById("model-pill-text");
        try {
            const res = await fetch(API_ROUTES.MODELS, { headers: getAuthHeaders(true) });
            if (res.ok) {
                const data = await res.json();
                const count = (data.installed_models || data.models || []).length;
                pageDiagnostics.modelsLoaded = true;
                pageDiagnostics.modelsCount = count;
                pageDiagnostics.modelsOllamaOnline = data.ollama_running !== false && count > 0;

                if (pillText) {
                    pillText.textContent = pageDiagnostics.modelsOllamaOnline
                        ? `Ollama Online (${count} Models)`
                        : "Ollama Standby";
                }

                const modelsList = data.installed_models || (data.models ? data.models.map(m => m.name || m) : []);
                [selectGenerator, selectValidator, selectFallback].forEach(sel => {
                    if (!sel) return;
                    const prevVal = sel.value;
                    sel.innerHTML = "";
                    modelsList.forEach(m => {
                        const opt = document.createElement("option");
                        opt.value = m;
                        opt.textContent = m;
                        sel.appendChild(opt);
                    });
                    if (prevVal && modelsList.includes(prevVal)) {
                        sel.value = prevVal;
                    }
                });

                if (data.assigned_roles) {
                    if (selectGenerator && !selectGenerator.value) selectGenerator.value = data.assigned_roles.generator || "";
                    if (selectValidator && !selectValidator.value) selectValidator.value = data.assigned_roles.validator || "";
                    if (selectFallback && !selectFallback.value) selectFallback.value = data.assigned_roles.fallback || "";
                }
            }
        } catch (err) {
            if (pillText) pillText.textContent = "Ollama Offline";
            pageDiagnostics.modelsLoaded = false;
            pageDiagnostics.lastError = "Models fetch error: " + (err.message || err);
        }
    }

    async function checkActiveJobOnInit() {
        try {
            const res = await fetch(API_ROUTES.ACTIVE_JOB, { headers: getAuthHeaders(true) });
            if (res.ok) {
                const data = await res.json();
                if (data && data.active_job) {
                    activeJobId = data.active_job.id;
                    console.log(`Resuming active generation job #${activeJobId} on page load.`);
                    if (wizardFormSection) wizardFormSection.style.display = "none";
                    if (progressSection) progressSection.style.display = "block";
                    startPolling(activeJobId);
                }
            }
        } catch {}
    }

    // ==========================================
    // 12. RUN DIAGNOSTICS MODAL (RULE 8)
    // ==========================================
    function openDiagnosticsModal() {
        const modal = document.getElementById("diagnostics-modal");
        const content = document.getElementById("diagnostics-content");
        if (!modal || !content) return;

        const bpState = getBlueprintState();
        const subject = subjectNameInput ? subjectNameInput.value.trim() : "";
        const token = getAuthToken();
        const marksMatch = Math.abs(bpState.totalAllocated - bpState.target) < 0.001 && bpState.target > 0;
        const totalFiles = uploadedFiles.length + savedUploadedFiles.length;

        content.innerHTML = `
            <div class="diag-item">
                <span class="diag-label">JavaScript Loaded:</span>
                <span class="diag-badge-ok">YES (Ready)</span>
            </div>
            <div class="diag-item">
                <span class="diag-label">Auth Token:</span>
                <span class="${token ? 'diag-badge-ok' : 'diag-badge-warn'}">
                    ${token ? 'Authenticated (Bearer ' + token.substring(0, 10) + '...)' : 'Anonymous / Session'}
                </span>
            </div>
            <div class="diag-item">
                <span class="diag-label">Local Ollama Status:</span>
                <span class="${pageDiagnostics.modelsOllamaOnline ? 'diag-badge-ok' : 'diag-badge-warn'}">
                    ${pageDiagnostics.modelsOllamaOnline ? `Online (${pageDiagnostics.modelsCount} models installed)` : 'Standby / Offline'}
                </span>
            </div>
            <div class="diag-item">
                <span class="diag-label">Selected Subject:</span>
                <span class="${subject ? 'diag-badge-ok' : 'diag-badge-warn'}">
                    ${subject ? subject : 'None (Required)'}
                </span>
            </div>
            <div class="diag-item">
                <span class="diag-label">Syllabus Files Uploaded:</span>
                <span class="${totalFiles > 0 ? 'diag-badge-ok' : 'diag-badge-warn'}">
                    ${totalFiles > 0 ? `${totalFiles} file(s) available` : '0 files (Required or topics)'}
                </span>
            </div>
            <div class="diag-item">
                <span class="diag-label">Marks Allocation:</span>
                <span class="${marksMatch ? 'diag-badge-ok' : 'diag-badge-err'}">
                    ${bpState.totalAllocated} / ${bpState.target} Marks (${marksMatch ? 'Exact Match' : 'Mismatch'})
                </span>
            </div>
            <div class="diag-item">
                <span class="diag-label">Active Generation Job:</span>
                <span class="${activeJobId ? 'diag-badge-warn' : 'diag-badge-ok'}">
                    ${activeJobId ? `Job #${activeJobId} Running` : 'None (Ready to Generate)'}
                </span>
            </div>
            <div class="diag-item">
                <span class="diag-label">Last API Error:</span>
                <span class="${lastApiError ? 'diag-badge-err' : 'diag-badge-ok'}">
                    ${lastApiError ? lastApiError : 'None'}
                </span>
            </div>
        `;

        modal.style.display = "flex";
    }

    function closeDiagnosticsModal() {
        const modal = document.getElementById("diagnostics-modal");
        if (modal) modal.style.display = "none";
    }

    // ==========================================
    // 13. SAFE EVENT DELEGATION & ATTACHMENT (RULE 3)
    // ==========================================
    document.addEventListener("click", (e) => {
        // Generate with AI buttons (Primary or Sticky)
        const genBtn = e.target.closest("#btn-generate-paper, #btn-sticky-generate");
        if (genBtn) {
            e.preventDefault();
            handleGenerateClick();
            return;
        }

        // Cancel generation
        const cancelBtn = e.target.closest("#btn-cancel-generation");
        if (cancelBtn) {
            e.preventDefault();
            cancelActiveJob();
            return;
        }

        // Run diagnostics button
        const diagBtn = e.target.closest("#btn-run-diagnostics");
        if (diagBtn) {
            e.preventDefault();
            openDiagnosticsModal();
            return;
        }

        // Close diagnostics modal
        const closeDiagBtn = e.target.closest("#btn-close-diagnostics");
        if (closeDiagBtn) {
            e.preventDefault();
            closeDiagnosticsModal();
            return;
        }
        if (e.target.classList.contains("diagnostics-modal-backdrop")) {
            closeDiagnosticsModal();
            return;
        }

        // Dismiss validation alert
        const dismissAlertBtn = e.target.closest("#btn-dismiss-alert");
        if (dismissAlertBtn && validationAlert) {
            validationAlert.style.display = "none";
            return;
        }
    });

    // Dropzone listeners
    if (dropzone && fileInput) {
        dropzone.addEventListener("click", () => fileInput.click());
        dropzone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        });
        dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
        dropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
            if (e.dataTransfer && e.dataTransfer.files) {
                handleFilesAdded(e.dataTransfer.files);
            }
        });

        fileInput.addEventListener("change", (e) => {
            if (e.target.files) {
                handleFilesAdded(e.target.files);
            }
        });
    }

    // Auto-distribute blueprint button
    if (btnAutoDistribute) {
        btnAutoDistribute.addEventListener("click", async () => {
            const target = totalMarksInput ? (parseInt(totalMarksInput.value, 10) || 50) : 50;
            try {
                const res = await fetch(`${API_ROUTES.BLUEPRINT_SUGGEST}?total_marks=${target}`, {
                    headers: getAuthHeaders(true)
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.sections) {
                        data.sections.forEach(s => {
                            const found = questionTypes.find(q => q.type === s.type);
                            if (found) {
                                found.count = s.count;
                                found.marks = s.marks_per_question;
                            }
                        });
                        renderBlueprintRows();
                    }
                }
            } catch (err) {
                console.error("Auto distribute failed:", err);
            }
        });
    }

    // Clear Draft handler
    if (btnClearDraft) {
        btnClearDraft.addEventListener("click", () => {
            if (confirm("Are you sure you want to clear this form and start fresh? All unsaved inputs will be reset.")) {
                localStorage.removeItem(DRAFT_STORAGE_KEY);
                fetch(API_ROUTES.DRAFT, {
                    method: "DELETE",
                    headers: getAuthHeaders(true)
                }).catch(() => {});

                if (examTitleInput) examTitleInput.value = "End-Semester Examination";
                if (subjectNameInput) subjectNameInput.value = "";
                if (classSemInput) classSemInput.value = "Semester 6";
                if (examTypeSelect) examTypeSelect.value = "Final Examination";
                if (durationInput) durationInput.value = "60";
                if (totalMarksInput) totalMarksInput.value = "50";
                if (topicsInput) topicsInput.value = "";

                uploadedFiles = [];
                savedUploadedFiles = [];
                updateFileList();

                renderBlueprintRows();
                updateGenerateButtonState();
            }
        });
    }

    // Input change listeners
    [examTitleInput, subjectNameInput, classSemInput, examTypeSelect, durationInput, totalMarksInput, topicsInput].forEach(el => {
        if (!el) return;
        el.addEventListener("input", () => {
            recalcMarks();
            scheduleAutoSave();
        });
        el.addEventListener("change", () => {
            recalcMarks();
            scheduleAutoSave();
        });
    });

    if (blueprintRows) {
        blueprintRows.addEventListener("input", recalcMarks);
        blueprintRows.addEventListener("change", recalcMarks);
    }

    const btnRefreshModels = document.getElementById("btn-refresh-models");
    if (btnRefreshModels) btnRefreshModels.addEventListener("click", loadModels);

    if (filterType) {
        filterType.addEventListener("change", () => renderQuestions(loadedQuestions));
    }

    // Export Handlers
    const btnExportDocx = document.getElementById("btn-export-docx");
    if (btnExportDocx) {
        btnExportDocx.addEventListener("click", () => {
            if (activeJobId) window.location.href = API_ROUTES.EXPORT(activeJobId, "docx");
        });
    }
    const btnExportPdf = document.getElementById("btn-export-pdf");
    if (btnExportPdf) {
        btnExportPdf.addEventListener("click", () => {
            if (activeJobId) window.location.href = API_ROUTES.EXPORT(activeJobId, "pdf");
        });
    }

    // ==========================================
    // 14. INITIALIZATION SEQUENCE
    // ==========================================
    async function init() {
        console.log("Initializing AI Paper Generator app.js...");
        await loadSavedDraft();
        await loadModels();
        await checkActiveJobOnInit();
        updateGenerateButtonState();
        console.log("AI Paper Generator app.js ready.");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
