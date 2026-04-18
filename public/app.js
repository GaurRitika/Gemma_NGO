document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-btn');
    const exportBtn = document.getElementById('export-btn');
    const logsContainer = document.getElementById('logs-container');
    const rawTableContainer = document.getElementById('raw-table-container');
    const cleanTableContainer = document.getElementById('clean-table-container');
    
    // Mode Toggle Elements
    const modeSwitch = document.getElementById('mode-switch');
    const labelDemo = document.getElementById('label-demo');
    const labelReal = document.getElementById('label-real');
    const dropzone = document.getElementById('dropzone');
    const csvUploadInput = document.getElementById('csv-upload');
    
    let isAgentRunning = false;
    let currentEpisodeId = null;
    let isRealMode = false;
    let uploadedFile = null;

    // --- Mode Toggling ---
    modeSwitch.addEventListener('change', (e) => {
        isRealMode = e.target.checked;
        if (isRealMode) {
            labelReal.classList.add('active');
            labelDemo.classList.remove('active');
            dropzone.classList.remove('hidden');
            startBtn.classList.add('hidden'); // hidden until file is dropped
        } else {
            labelDemo.classList.add('active');
            labelReal.classList.remove('active');
            dropzone.classList.add('hidden');
            startBtn.classList.remove('hidden');
            startBtn.textContent = 'Initialize Cleaning Agent';
            uploadedFile = null;
        }
    });

    labelDemo.classList.add('active'); // Default

    // --- Drag and Drop Logic ---
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
        if (!file.name.endsWith('.csv')) {
            alert("Please upload a valid CSV file.");
            return;
        }
        uploadedFile = file;
        dropzone.querySelector('p').innerHTML = `✅ ${file.name} ready.`;
        startBtn.classList.remove('hidden');
        startBtn.textContent = 'Clean Uploaded Data';
    }

    // --- Core Agent Start Logic ---
    startBtn.addEventListener('click', async () => {
        if (isAgentRunning) return;
        
        isAgentRunning = true;
        startBtn.textContent = 'Agent Running...';
        startBtn.style.opacity = '0.7';
        
        // Clear placeholders
        rawTableContainer.innerHTML = '<table id="raw-table"></table>';
        cleanTableContainer.innerHTML = '<table id="clean-table"></table>';
        logsContainer.innerHTML = '';
        exportBtn.disabled = true;

        try {
            let startData;
            
            if (isRealMode && uploadedFile) {
                // REAL MODE - File Upload
                addLog('SYSTEM', 'Uploading custom dataset and booting Gemma 4 Copilot in Real Mode...');
                const formData = new FormData();
                formData.append('file', uploadedFile);
                
                const res = await fetch('/api/upload_csv', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) throw new Error(await res.text());
                startData = await res.json();
                
            } else {
                // DEMO MODE - Core Env Testbed
                addLog('SYSTEM', 'Initializing OpenEnv synthetic NGO dataset and booting Gemma 4 planner...');
                const res = await fetch('/api/start_demo', { method: 'POST' });
                if (!res.ok) throw new Error(await res.text());
                startData = await res.json();
            }

            currentEpisodeId = startData.episode_id;
            
            addLog('PROFILE_SOURCE', 'Environment instantiated and messy schema discovered.');
            renderTable('raw-table', startData.raw_data);
            
            // Loop the Agent dynamically
            await runAgentLoop();

        } catch (error) {
            console.error(error);
            addLog('SYSTEM_ERROR', `Failed to initialize: ${error.message}`);
            isAgentRunning = false;
            startBtn.style.opacity = '1';
            startBtn.textContent = isRealMode ? 'Clean Uploaded Data' : 'Initialize Cleaning Agent';
        }
    });

    // --- Data Download Export ---
    exportBtn.addEventListener('click', () => {
        if (!currentEpisodeId) return;
        window.location.href = `/api/download_csv/${currentEpisodeId}`;
    });

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
                td.textContent = (val === null || val === undefined) ? "null" : String(val);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
    }

    async function runAgentLoop() {
        let isDone = false;
        
        while (!isDone) {
            addLog('AGENT_THINKING', 'Gemma evaluating observation space...');
            
            await new Promise(r => setTimeout(r, 1000)); // Visual spacing
            
            const stepRes = await fetch(`/api/agent_step/${currentEpisodeId}`, { method: 'POST' });
            if (!stepRes.ok) {
                addLog('SERVER_FAULT', 'Gemma unreachable or backend crashed.');
                break;
            }
            const stepData = await stepRes.json();
            
            addLog(stepData.action, stepData.reason);
            
            if (stepData.table_data && stepData.table_data.length > 0) {
                 renderTable('clean-table', stepData.table_data);
            }
            
            if (stepData.done) {
                isDone = true;
                addLog('SUBMIT_PIPELINE', 'Gemma 4 has confidently finished data standardization.');
                startBtn.textContent = 'Cleanup Complete';
                startBtn.style.opacity = '1';
                exportBtn.disabled = false;
                isAgentRunning = false;
            }
            
            if (document.querySelectorAll('.log-item').length > 15) {
                addLog('SYSTEM_WARN', 'Agent reached maximum execution depth threshold. Halting.');
                isAgentRunning = false;
                startBtn.style.opacity = '1';
                break;
            }
        }
    }
});
