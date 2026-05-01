document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-btn');
    const exportBtn = document.getElementById('export-btn');
    const rawTableContainer = document.getElementById('raw-table-container');
    const cleanTableContainer = document.getElementById('clean-table-container');

    // File UI Elements
    const dropzone = document.getElementById('dropzone');
    const csvUploadInput = document.getElementById('csv-upload');
    const dropzoneText = document.getElementById('dropzone-text');
    const dropzoneTitle = document.getElementById('dropzone-title');
    const startActionContainer = document.getElementById('start-action-container');
    const uploadView = document.getElementById('upload-view');
    const workspaceView = document.getElementById('workspace-view');
    const resultsView = document.getElementById('results-view');
    const exportResultsBtn = document.getElementById('export-results-btn');

    if (!startBtn || !dropzone) return; // Exit if not on dashboard page

    let isAgentRunning = false;
    let currentEpisodeId = null;
    let uploadedFile = null;
    let initialRawData = null;

    // --- Drag and Drop Logic ---
    dropzone.addEventListener('dragenter', (e) => { e.preventDefault(); });
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => { dropzone.classList.remove('dragover'); });
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]);
    });
    csvUploadInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFileUpload(e.target.files[0]);
    });

    function handleFileUpload(file) {
        if (!file.name.endsWith('.csv') && !file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
            alert("Please upload a valid CSV or Excel file.");
            return;
        }
        uploadedFile = file;
        if (dropzoneTitle) dropzoneTitle.innerHTML = `✅ ${file.name} ready to process.`;
        if (dropzoneText) dropzoneText.innerHTML = "Click the button below to begin AI analysis.";
        if (startActionContainer) startActionContainer.classList.remove('hidden');
        startBtn.classList.remove('hidden');
    }

    // --- Core Agent Start Logic ---
    startBtn.addEventListener('click', async () => {
        if (isAgentRunning || !uploadedFile) return;

        isAgentRunning = true;
        startBtn.textContent = 'Agent Analyzing...';
        startBtn.disabled = true;

        // Switch views
        if (uploadView && workspaceView) {
            uploadView.classList.add('hidden');
            workspaceView.classList.remove('hidden');
        }

        // Clear placeholders
        if (rawTableContainer) rawTableContainer.innerHTML = '<table id="raw-table"></table>';
        if (cleanTableContainer) cleanTableContainer.innerHTML = '<table id="clean-table"></table>';
        if (exportBtn) exportBtn.disabled = true;

        try {
            addLog('SYSTEM', 'Connecting to secure local workspace and interpreting file...');

            // Upload dataset to backend
            const formData = new FormData();
            formData.append('file', uploadedFile);

            const res = await fetch('/api/upload_csv', { method: 'POST', body: formData });
            if (!res.ok) throw new Error(await res.text());
            const startData = await res.json();

            currentEpisodeId = startData.episode_id;
            initialRawData = startData.raw_data;

            // Render the initial messy data
            renderTable('live-table', initialRawData);
            addLog('PROFILE', 'File uploaded. Initial schema inferred successfully.');

            await sleep(800);

            // ⚡ FAST BATCH MODE — one call, full plan
            await runBatchPipeline();

        } catch (error) {
            console.error(error);
            addLog('ERROR', `Failed to initialize: ${error.message}`);
            isAgentRunning = false;
            startBtn.disabled = false;
            startBtn.textContent = 'Start Cleaning Data';
        }
    });

    // --- Data Download Export ---
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            if (!currentEpisodeId) return;
            window.location.href = `/api/download_csv/${currentEpisodeId}`;
        });
    }
    if (exportResultsBtn) {
        exportResultsBtn.addEventListener('click', () => {
            if (!currentEpisodeId) return;
            window.location.href = `/api/download_csv/${currentEpisodeId}`;
        });
    }

    // ─────────────────────────────────────────────────────────────────────────
    // ⚡ FAST BATCH PIPELINE — calls /api/run_full_pipeline once,
    //    then animates the step log at 120ms per step (no more waiting for LLM)
    // ─────────────────────────────────────────────────────────────────────────
    async function runBatchPipeline() {
        addLog('AGENT_THINKING', 'Gemma 4 is planning the full cleaning pipeline...');
        updateTimelineStep(1, 'Gemma 4 is planning the full pipeline...');

        const batchRes = await fetch(`/api/run_full_pipeline/${currentEpisodeId}`, { method: 'POST' });
        if (!batchRes.ok) {
            const errText = await batchRes.text();
            addLog('ERROR', `Batch pipeline failed: ${errText}. Falling back to step mode...`);
            await runAgentLoop(); // graceful fallback
            return;
        }

        const batchData = await batchRes.json();
        const steps = batchData.steps_log || [];
        const totalSteps = batchData.total_steps || steps.length;

        addLog('PROFILE', `Gemma 4 generated a ${totalSteps}-step cleaning plan. Executing now...`);
        updateTimelineStep(2, `Executing ${totalSteps} cleaning actions...`);

        // ── Animate each step at 120ms intervals (fast visual feedback) ──
        for (let i = 0; i < steps.length; i++) {
            const step = steps[i];
            const actionLabel = formatAction(step.action, step.source, step.column);

            addLog(step.action, step.feedback || actionLabel);

            // Update progress bar continuously
            const pct = Math.round(((i + 1) / totalSteps) * 85) + 5;
            setProgress(pct);

            // Update live table at intervals (every 3rd step or last) for speed
            if (batchData.table_data && (i % 3 === 0 || i === steps.length - 1)) {
                renderTable('live-table', batchData.table_data);
            }

            // Update insight text
            const insightText = document.getElementById('gemma-insight-text');
            if (insightText) insightText.textContent = step.feedback || actionLabel;

            await sleep(120); // 120ms between steps — fast but visible
        }

        // ── Pipeline complete ──
        setProgress(100);
        updateTimelineStep(4, 'All tables cleaned and verified!');
        addLog('SUBMIT_PIPELINE', `Pipeline complete! ${totalSteps} actions executed. Total reward: ${batchData.total_reward}`);

        // Show results
        setTimeout(() => {
            if (workspaceView && resultsView) {
                workspaceView.classList.add('hidden');
                resultsView.classList.remove('hidden');
            }
            if (initialRawData) renderTable('results-raw-table', initialRawData);
            if (batchData.table_data) renderTable('results-clean-table', batchData.table_data);
            if (exportBtn) exportBtn.disabled = false;
        }, 800);

        isAgentRunning = false;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // FALLBACK: original step-by-step loop (now with already_done tracking)
    // ─────────────────────────────────────────────────────────────────────────
    async function runAgentLoop() {
        let isDone = false;
        let safetyCounter = 0;
        const MAX_STEPS = 30;

        while (!isDone && safetyCounter < MAX_STEPS) {
            safetyCounter++;
            addLog('AGENT_THINKING', 'Evaluating schema and applying non-profit data formats...');
            await sleep(400);

            const stepRes = await fetch(`/api/agent_step/${currentEpisodeId}`, { method: 'POST' });
            if (!stepRes.ok) {
                addLog('FAULT', 'Agent unreachable. Verify local Ollama instance is active.');
                break;
            }
            const stepData = await stepRes.json();
            addLog(stepData.action, stepData.reason);

            if (stepData.table_data && stepData.table_data.length > 0) {
                renderTable('live-table', stepData.table_data);
            }

            if (stepData.done) {
                isDone = true;
                addLog('SUBMIT_PIPELINE', 'Data standardization sequence successfully verified.');
                setProgress(100);
                updateTimelineStep(5, "Completed");

                setTimeout(() => {
                    if (workspaceView && resultsView) {
                        workspaceView.classList.add('hidden');
                        resultsView.classList.remove('hidden');
                    }
                    if (initialRawData) renderTable('results-raw-table', initialRawData);
                    if (stepData.table_data) renderTable('results-clean-table', stepData.table_data);
                    if (exportBtn) exportBtn.disabled = false;
                }, 800);

                isAgentRunning = false;
            }
        }

        if (safetyCounter >= MAX_STEPS) {
            addLog('WARN', 'Agent reached maximum step limit. Halting.');
            if (exportBtn) exportBtn.disabled = false;
            isAgentRunning = false;
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // HELPERS
    // ─────────────────────────────────────────────────────────────────────────

    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    let actionCounter = 0;

    function setProgress(pct) {
        const progressFill = document.getElementById('main-progress-fill');
        const timeRemaining = document.getElementById('time-remaining');
        if (progressFill) progressFill.style.width = `${pct}%`;
        if (timeRemaining) timeRemaining.textContent = Math.max(0, Math.round((100 - pct) / 10));
    }

    function addLog(action, reason) {
        console.log(`[${action}] ${reason}`);
        actionCounter++;

        const pct = Math.min((actionCounter / 6) * 100, 95);
        setProgress(pct);

        if (actionCounter === 1) updateTimelineStep(1, reason);
        else if (actionCounter === 3) updateTimelineStep(2, reason);
        else if (actionCounter === 4) updateTimelineStep(3, reason);
        else if (actionCounter >= 5) updateTimelineStep(4, reason);

        const insightText = document.getElementById('gemma-insight-text');
        if (insightText && action !== 'SYSTEM' && action !== 'AGENT_THINKING' && action !== 'SUBMIT_PIPELINE') {
            insightText.textContent = reason;
        }
    }

    function formatAction(action, source, column) {
        if (column) return `${action} → ${source}.${column}`;
        if (source) return `${action} → ${source}`;
        return action;
    }

    function updateTimelineStep(stepNum, reason) {
        for (let i = 1; i < stepNum; i++) {
            const prevStep = document.getElementById(`step-${i}`);
            if (prevStep) {
                prevStep.classList.remove('active', 'pending');
                prevStep.classList.add('done');
                const icon = prevStep.querySelector('.step-icon i');
                if (icon) icon.className = 'fa-solid fa-check';
            }
        }

        const currStep = document.getElementById(`step-${stepNum}`);
        if (currStep) {
            currStep.classList.remove('pending', 'done');
            currStep.classList.add('active');
            const p = currStep.querySelector('p');
            if (p) p.textContent = reason;
            const icon = currStep.querySelector('.step-icon i');
            if (icon) icon.className = 'fa-solid fa-circle-notch fa-spin';
        }
    }

    function renderTable(tableId, data) {
        if (!data || data.length === 0) return;
        const table = document.getElementById(tableId);
        if (!table) return;

        table.innerHTML = '';

        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        Object.keys(data[0]).forEach(key => {
            const th = document.createElement('th');
            th.textContent = key;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement('tbody');
        data.forEach(row => {
            const tr = document.createElement('tr');
            let hasError = false;

            Object.values(row).forEach(val => {
                const td = document.createElement('td');
                const valStr = (val === null || val === undefined) ? "null" : String(val);

                if (tableId === 'results-raw-table' || tableId === 'live-table') {
                    if (
                        valStr.toUpperCase() === 'MISSING' ||
                        valStr.toUpperCase() === 'N/A' ||
                        valStr === 'null' ||
                        valStr.includes('@@') ||
                        valStr.includes('(at)')
                    ) {
                        td.innerHTML = `<span class="error-text">${valStr}</span>`;
                        hasError = true;
                    } else {
                        td.textContent = valStr;
                    }
                } else {
                    td.textContent = valStr;
                }
                tr.appendChild(td);
            });

            if (hasError && (tableId === 'results-raw-table' || tableId === 'live-table')) {
                tr.classList.add('error-row');
            }
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
    }
});
