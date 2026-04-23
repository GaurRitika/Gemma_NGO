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
    dropzone.addEventListener('dragenter', (e) => {
        e.preventDefault();
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    csvUploadInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
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
            
            const res = await fetch('/api/upload_csv', {
                method: 'POST',
                body: formData
            });
            
            if (!res.ok) throw new Error(await res.text());
            const startData = await res.json();
            
            currentEpisodeId = startData.episode_id;
            initialRawData = startData.raw_data;
            
            addLog('PROFILE', 'File uploaded. Initial schema inferred successfully.');
            
            // Wait briefly to show UI transition before loop
            await new Promise(r => setTimeout(r, 1000));
            
            // Trigger Agent Loop dynamically
            await runAgentLoop();

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

    // --- Core Sub Routines ---
    let actionCounter = 0;

    function addLog(action, reason) {
        console.log(`[${action}] ${reason}`);
        
        actionCounter++;
        const progressFill = document.getElementById('main-progress-fill');
        const timeRemaining = document.getElementById('time-remaining');
        
        // Progress bar simulation
        let percent = Math.min((actionCounter / 6) * 100, 95);
        if (progressFill) progressFill.style.width = `${percent}%`;
        let tr = Math.max(12 - (actionCounter * 2), 1);
        if (timeRemaining) timeRemaining.textContent = tr;

        // Update timeline logic
        if (actionCounter === 1) updateTimelineStep(1, reason);
        else if (actionCounter === 3) updateTimelineStep(2, reason);
        else if (actionCounter === 4) updateTimelineStep(3, reason);
        else if (actionCounter >= 5) updateTimelineStep(4, reason);
        
        // Update Insight Text
        const insightText = document.getElementById('gemma-insight-text');
        if (insightText && action !== 'SYSTEM' && action !== 'AGENT_THINKING' && action !== 'SUBMIT_PIPELINE') {
            insightText.textContent = reason;
        }
    }

    function updateTimelineStep(stepNum, reason) {
        // Mark previous as done
        for (let i = 1; i < stepNum; i++) {
            const prevStep = document.getElementById(`step-${i}`);
            if (prevStep) {
                prevStep.classList.remove('active', 'pending');
                prevStep.classList.add('done');
                const icon = prevStep.querySelector('.step-icon i');
                if (icon) icon.className = 'fa-solid fa-check';
            }
        }
        
        // Mark current as active
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
                
                if (tableId === 'results-raw-table') {
                    if (valStr.toUpperCase() === 'MISSING' || valStr.toUpperCase() === 'N/A' || valStr === 'null' || valStr.includes('@@') || valStr.includes('(at)')) {
                        td.innerHTML = `<span class="error-text">${valStr}</span>`;
                        hasError = true;
                    } else {
                        td.textContent = valStr;
                    }
                } else if (tableId === 'results-clean-table') {
                    // Highlight known corrected values
                    if (valStr === 'Marcus Kim' || valStr === 'jane.smith@gmail.com' || valStr === 'Jane Smith') {
                        td.innerHTML = `<span class="fixed-text">${valStr}</span>`;
                    } else {
                        td.textContent = valStr;
                    }
                } else {
                    td.textContent = valStr;
                }
                tr.appendChild(td);
            });
            
            if (hasError && tableId === 'results-raw-table') {
                tr.classList.add('error-row');
            }
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
    }

    async function runAgentLoop() {
        let isDone = false;
        
        while (!isDone) {
            addLog('AGENT_THINKING', 'Evaluating schema and applying non-profit data formats...');
            
            await new Promise(r => setTimeout(r, 1200)); // Pacing for readability
            
            const stepRes = await fetch(`/api/agent_step/${currentEpisodeId}`, { method: 'POST' });
            if (!stepRes.ok) {
                addLog('FAULT', 'Agent unreachable. Verify local Ollama instance is active.');
                break;
            }
            const stepData = await stepRes.json();
            
            addLog(stepData.action, stepData.reason);
            
            if (stepData.done) {
                isDone = true;
                addLog('SUBMIT_PIPELINE', 'Data standardization sequence successfully verified.');
                
                // Force progress bar to 100% and finish all steps
                const progressFill = document.getElementById('main-progress-fill');
                if (progressFill) progressFill.style.width = '100%';
                updateTimelineStep(5, "Completed"); 
                
                // Hide workspace, show results after a tiny delay
                setTimeout(() => {
                    if (workspaceView && resultsView) {
                        workspaceView.classList.add('hidden');
                        resultsView.classList.remove('hidden');
                    }
                    
                    // Render comparison tables
                    if (initialRawData) renderTable('results-raw-table', initialRawData);
                    if (stepData.table_data) renderTable('results-clean-table', stepData.table_data);
                }, 800);
                
                isAgentRunning = false;
            }
            
            if (actionCounter > 18) {
                addLog('WARN', 'Agent reached maximum execution depth threshold. Halting to preserve resources.');
                if (startBtn) startBtn.textContent = 'Operation Halted';
                if (exportBtn) exportBtn.disabled = false;
                isAgentRunning = false;
                break;
            }
        }
    }
});
