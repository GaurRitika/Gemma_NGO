# 🌍 Gemma for Good: Democratizing Data Dignity

> **"Data is a human right, but cleaning it shouldn't be a human burden."**  
> *Submission for the **Gemma 4 Good Hackathon***  
> **Impact Tracks:** Digital Equity & Inclusivity | Safety & Trust  
> **Technology Track:** Ollama

---

## 🎥 The Pitch & Demo
[![Watch the Demo Video](https://img.shields.io/badge/🎥-Watch_Video_Pitch-FF0000?style=for-the-badge&logo=youtube)](VIDEO_LINK_HERE)

---

## 📖 The "Silent" Global Challenge: A Story of Fragmented Hope

Every day, frontline workers in refugee camps, remote clinics, and grassroots NGOs are forced to choose between **helping a human** and **managing a spreadsheet**. 

They sit on goldmines of impact data—volunteer lists, donor portals, and disaster response forms—but this data is broken, duplicated, and messy. Enterprise giants solve this with million-dollar data engineering teams. **Grassroots NGOs do not have that luxury.** 

Worse, they face a dangerous trap:
1. **The Privacy Paradox**: Uploading sensitive beneficiary data to a centralized cloud AI violates the very trust and safety of the vulnerable communities they protect.
2. **The Skills Gap**: Sophisticated data cleaning requires coding skills that most social workers simply don't have.

**Data inequality is a barrier to global resilience.** We believe that frontier intelligence shouldn't be a privilege of the rich; it should be a tool for the brave.

---

## 💡 The Solution: Gemma for Good

We didn't just build a tool; we built a **local-first data engineering partner**. 

**Gemma for Good** brings world-class intelligence to the front lines. By leveraging **Gemma 4 via Ollama**, we created an autonomous agent that runs entirely on local hardware. 

**Zero cloud tracking. Zero data leakage. 100% Data Dignity.**

---

## 🛠 Technical Architecture: Agentic Intelligence at the Edge

### 🧠 The Agentic Batch Planner (Digital Equity)
We are closing the AI skills gap by abstracting complex data engineering behind an intuitive, human-centric interface.
- **Natural Language Schema Mapping**: Gemma 4 profiles messy CSVs and understands the *intent* behind columns (e.g., recognizing that "phn_no" in one table and "Contact" in another are the same).
- **High-Speed Batch Planning**: Our backend asks Gemma 4 once to plan an entire multi-step cleaning strategy. This reduces the latency and resource load, making frontier AI accessible on standard local hardware.

### 🛡️ Safety & Trust: Grounded, Explainable AI
Pioneering frameworks for transparency in NGO tech.
- **Local-First PII Protection**: By running exclusively on Ollama, sensitive donor and beneficiary names never leave the local machine. This is non-negotiable for safety.
- **Hybrid Intelligence System**: To ensure 100% reliability, we implemented a deterministic rule-based engine that takes over if local resources time out. The AI remains grounded in mathematical reality.
- **Explainable Pipeline**: Every action Gemma takes is logged and visualized for the user, ensuring the "black box" of AI is replaced by a transparent, auditable trail.

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
3.  Click **"Start Cleaning Data"** and watch Gemma for Good autonomously restore order to the chaos.

---

## 🔮 Future Vision: Edge Intelligence for Human Stories
Our roadmap involves optimizing this pipeline using **Google AI Edge's LiteRT**. We want this to run on a $20 smartphone in an offline environment, empowering a social worker in the field to tell a clearer story of impact.

**By empowering the front lines with local frontier intelligence, we ensure that every hour saved on a spreadsheet is an hour spent on a human life.**

---

**Lead Developer:** Ritika Gaur ([GaurRitika](https://github.com/GaurRitika))  
**Contact:** [devritika.gaur@gmail.com](mailto:devritika.gaur@gmail.com) | +91 7905636064  
*Built with ❤️ for NGO workers and donors worldwide.*
