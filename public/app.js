document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-btn');
    const exportBtn = document.getElementById('export-btn');
    const logsContainer = document.getElementById('logs-container');
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
        rawTableContainer.innerHTML = '<table id="raw-table"></table>';
        cleanTableContainer.innerHTML = '<table id="clean-table"></table>';
        logsContainer.innerHTML = '';
        exportBtn.disabled = true;

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
            renderTable('raw-table', startData.raw_data);
            
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
    exportBtn.addEventListener('click', () => {
        if (!currentEpisodeId) return;
        window.location.href = `/api/download_csv/${currentEpisodeId}`;
    });

    if (exportResultsBtn) {
        exportResultsBtn.addEventListener('click', () => {
            if (!currentEpisodeId) return;
            window.location.href = `/api/download_csv/${currentEpisodeId}`;
        });
    }

    // --- Core Sub Routines ---
    function addLog(action, reason) {
        const logDiv = document.createElement('div');
        logDiv.className = 'log-item';
        
        const actionDiv = document.createElement('div');
        actionDiv.className = 'action';
        actionDiv.textContent = `[${action}]`;
        
        const reasonDiv = document.createElement('div');
        reasonDiv.className = 'reason';
        reasonDiv.textContent = reason;
        
        logDiv.appendChild(actionDiv);
        logDiv.appendChild(reasonDiv);
        
        logsContainer.appendChild(logDiv);
        logsContainer.scrollTop = logsContainer.scrollHeight;
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
            Object.values(row).forEach(val => {
                const td = document.createElement('td');
                const valStr = (val === null || val === undefined) ? "null" : String(val);
                if (valStr.toUpperCase() === 'MISSING' || valStr.toUpperCase() === 'N/A' || valStr === 'null') {
                    td.innerHTML = `<span class="error-text">${valStr}</span>`;
                } else {
                    td.textContent = valStr;
                }
                tr.appendChild(td);
            });
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
            
            if (stepData.table_data && stepData.table_data.length > 0) {
                 renderTable('clean-table', stepData.table_data);
            }
            
            if (stepData.done) {
                isDone = true;
                addLog('SUBMIT_PIPELINE', 'Data standardization sequence successfully verified.');
                
                // Hide workspace, show results
                if (workspaceView && resultsView) {
                    workspaceView.classList.add('hidden');
                    resultsView.classList.remove('hidden');
                }
                
                // Render comparison tables
                if (initialRawData) renderTable('results-raw-table', initialRawData);
                if (stepData.table_data) renderTable('results-clean-table', stepData.table_data);
                
                isAgentRunning = false;
            }
            
            if (document.querySelectorAll('.log-item').length > 18) {
                addLog('WARN', 'Agent reached maximum execution depth threshold. Halting to preserve resources.');
                startBtn.textContent = 'Operation Halted';
                exportBtn.disabled = false;
                isAgentRunning = false;
                break;
            }
        }
    }
});
