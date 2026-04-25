# 🌍 Gemma_NGO

> **Submission for the Gemma 4 Good Hackathon**  
> **Impact Track:** Safety & Trust / Digital Equity & Inclusivity  
> **Technology Track:** Ollama

A privacy-first, local AI agent powered by **Gemma 4 (via Ollama)** that autonomously cleans, standardizes, and reconciles messy NGO donor and beneficiary data—without ever sending sensitive Personally Identifiable Information (PII) to the cloud.

---

## 📖 The Problem

Non-Governmental Organizations (NGOs) and grassroots community groups operate on the front lines of social impact. They collect vital data—donor lists, volunteer registries, and beneficiary tracking—often in chaotic, disconnected, and non-standard formats (Excel, CSVs, handwritten transcripts). 

While AI data-cleaning tools exist, **NGOs cannot use them**. Uploading vulnerable community data or sensitive donor PII to a centralized cloud AI API violates strict privacy policies, GDPR, and basic operational security. As a result, impact workers spend hundreds of hours manually formatting spreadsheets instead of helping people.

## 💡 Our Solution: Dignity-First Data Engineering

The **Gemma 4 CRM Cleanup Copilot** bridges the gap between humans and data by bringing the intelligence to the edge. By leveraging the **Ollama** implementation of the new Gemma 4 model, we built an autonomous data pipeline that runs entirely on local hardware. 

**Zero cloud tracking. Zero data leakage. 100% Data Dignity.**

### Key Features
- **Local Agentic Loop:** Gemma 4 acts as an autonomous agent, inferring the schema of raw uploads, identifying duplicates via fuzzy matching, and imputing missing values (like standardizing geographical coordinates or repairing malformed emails) using contextual AI inference.
- **Privacy by Design:** Because Gemma 4 runs locally via Ollama, the entire processing pipeline is air-gapped from external servers.
- **Premium, Human-Centric UI:** We built a gorgeous, accessible frontend designed for non-technical users. It features an interactive drag-and-drop upload, a live-animated "Processing Pipeline", and a visually striking "Cleaning Results" comparison dashboard.
- **AI Intelligence Hub:** The system doesn't just clean data; it explains *why* it made changes, fostering trust and transparency between the AI and the human operator.

---

## 🏗 Architecture & Technical Depth

Our application is built to demonstrate real-world utility and robust engineering, perfectly aligning with the "Source of Truth" requirement for the hackathon.

1. **The Brain (Gemma 4 + Ollama):** We utilize the native function-calling and deep linguistic understanding of Gemma 4. The model iteratively evaluates the "dirtiness" of the dataset, selecting standardizations (UTF-8 normalization, ISO-3166 naming, Title Case) dynamically.
2. **The Backend (FastAPI + Pandas):** A lightweight, asynchronous Python FastAPI server orchestrates the agent loop. It manages the file ingestion, chunks the data to respect local context windows, and drives the conversational state with the Ollama API.
3. **The Frontend (Vanilla HTML/CSS/JS):** To ensure maximum accessibility and lowest overhead (digital equity), the UI is built without heavy frameworks. It uses a custom CSS design system featuring micro-animations, dynamic state transitions (Upload → Workspace → Results), and a completely responsive layout.

---

## 🚀 Getting Started (Live Demo Instructions)

You can run this entire stack locally to verify the technical execution. 

### Prerequisites
1. Install [Ollama](https://ollama.com/).
2. Pull the Gemma model: `ollama run gemma` (Ensure the model server is running).
3. Install Python 3.10+.

### Installation
```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/Gemma-4-CRM-Cleanup-Copilot.git
cd Gemma-4-CRM-Cleanup-Copilot

# 2. Install Python dependencies
pip install fastapi uvicorn pandas python-multipart requests

# 3. Start the application
python -m server.app
```

### Experiencing the App
1. Open `http://localhost:8080/ui/index.html` in your browser.
2. Click **Start Cleaning Data** (or navigate to the Upload dashboard).
3. Drag and drop the provided `SUPER_MESSY_NGO_DONORS.csv` (located in the root directory) into the dropzone.
4. Watch the **Processing Pipeline** UI animate as the backend Gemma 4 agent reasons through the dataset.
5. Review the final **Cleaning Results** and click "Export CSV" to see the sanitized output.

> *Note: For a quick visual showcase of the final output, click the **Impact** link in the top navigation bar!*

---

## 🎥 Hackathon Video Pitch

*(Video Link will be added here prior to the submission deadline)*

## 🔮 Future Work & Impact

Our next step is to optimize this pipeline using **Google AI Edge's LiteRT** to allow this entire workflow to run on mobile devices in offline, field-based environments (e.g., refugee camps or remote clinics). By empowering frontline workers with local frontier intelligence, we can ensure that every hour saved on data entry is an hour spent changing lives.

---
*Built with ❤️ for the Gemma 4 Good Hackathon.*
