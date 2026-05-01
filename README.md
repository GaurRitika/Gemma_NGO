# 🌍 Gemma for Good: Democratizing Data Dignity

> **"Data is a human right, but cleaning it shouldn't be a human burden."**  
> *Submission for the **Gemma 4 Good Hackathon** | **Impact Track:** Digital Equity & Inclusivity | **Technology Track:** Ollama*

---

## 🎥 The Pitch & Demo
[![Watch the Demo Video](https://img.shields.io/badge/🎥-Watch_Video_Pitch-FF0000?style=for-the-badge&logo=youtube)](VIDEO_LINK_HERE)

---

## 📖 The "Silent" Global Challenge: A Story of Fragmented Hope

Imagine a field volunteer in a remote clinic, working on three hours of sleep, manually typing names into a donated laptop with a flickering screen. Or an NGO director trying to merge three different volunteer lists from three different years just to know how many families they actually helped.

Enterprise giants solve this with million-dollar data engineering teams. **Grassroots NGOs do not have that luxury.** They face a heartbreaking choice:
1. **The Cloud Privacy Trap**: Upload sensitive beneficiary data to a centralized AI API—violating the very trust and safety of the vulnerable communities they serve.
2. **The Manual Burden**: Spend hundreds of hours on soul-crushing spreadsheet cleaning instead of being in the field saving lives.

**Data inequality is a barrier to global resilience.** We believe that frontier intelligence shouldn't be a privilege of the rich; it should be a tool for the brave.

---

## 💡 The Solution: Gemma 4 CRM Cleanup Copilot

We didn't just build a tool; we built a **local-first data engineering partner**. 

The **Gemma 4 CRM Cleanup Copilot** brings world-class intelligence to the very edge of the map. By leveraging **Gemma 4 via Ollama**, we created an autonomous agent that runs entirely on local hardware. 

**Zero cloud tracking. Zero data leakage. 100% Data Dignity.**

---

## 🛠 Technical Architecture: Agentic Intelligence at the Edge

### 🧠 The Agentic Batch Planner (Ollama Native)
Unlike traditional "one-row-at-a-time" LLM wrappers that are slow and expensive, our system uses a **High-Speed Batch Planner**. 
- **Multi-Step Reasoning**: Gemma 4 is prompted once to analyze the entire dataset's quality report. It then generates a complex, ordered JSON cleaning plan.
- **Autonomous Execution**: The backend translates Gemma's linguistic logic into optimized Python/Pandas operations.
- **Self-Correcting Loop**: If a step fails, the agent observes the error and adjusts its strategy in real-time.

### 🛡️ Deterministic Safety & Fallback
In field environments, hardware can be unpredictable. We implemented a **Hybrid Intelligence System**:
- **Ollama Probe**: A 2-second heart-beat check ensures Ollama is alive before every call.
- **Rule-Based Fallback Engine**: If local resources are low or the model times out (8s limit), our deterministic engine takes over instantly. The cleaning **never stops**, ensuring the user is never left hanging.

### 🎨 Human-Centric Design
- **Glassmorphic UI**: A premium, "Alive" interface that feels responsive and transparent.
- **Live Pipeline Visualization**: Users watch Gemma's "Chain of Thought" as it moves through steps like `Standardize`, `Handle Missing`, and `Deduplicate`.

---

## 🚀 Test the Impact (Try the Demo)

Experience the "Wow" factor yourself. We have provided a **Super Messy Dataset** specifically designed to test Gemma's reasoning limits.

### 📥 Step 1: Download the Test Data
[![Download Test Dataset](https://img.shields.io/badge/📥-Download_Messy_Test_Data-1E8E3E?style=for-the-badge&logo=csv)](./SUPER_MESSY_NGO_DONORS.csv)
*This file contains duplicate emails, broken phone formats, and missing signup dates—the perfect stress test.*

### 🛠 Step 2: Local Setup
1.  **Install [Ollama](https://ollama.com/)** and pull the model: `ollama pull gemma`.
2.  **Clone & Install**:
    ```bash
    git clone https://github.com/GaurRitika/Gemma_NGO.git
    cd Gemma_NGO
    pip install fastapi uvicorn pandas python-multipart requests
    ```
3.  **Run the Backend**:
    ```bash
    python -m server.app
    ```

### 🧪 Step 3: Run the Test
1.  Open `http://localhost:8080/ui/dashboard.html`.
2.  **Upload** the `SUPER_MESSY_NGO_DONORS.csv` you just downloaded.
3.  Click **"Start Cleaning Data"** and watch Gemma 4 autonomously restore order to the chaos.

---

## 🔮 Future Vision: Beyond the Desktop
Our roadmap involves optimizing this pipeline using **Google AI Edge's LiteRT**. We want this to run on a $20 smartphone in a refugee camp, offline, with the same level of intelligence. 

By empowering frontline workers with local frontier intelligence, we ensure that **every hour saved on a spreadsheet is an hour spent on a human story.**

---

**Lead Developer:** Ritika Gaur ([GaurRitika](https://github.com/GaurRitika))  
**Contact:** [devritika.gaur@gmail.com](mailto:devritika.gaur@gmail.com) | +91 7905636064  
*Built with ❤️ for the Gemma 4 Good Hackathon.*
