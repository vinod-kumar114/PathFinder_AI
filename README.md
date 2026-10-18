# 🚀 PathFinder AI — Autonomous Career & Scholarship Agent

> An autonomous, tool-augmented AI agent designed to streamline and democratize the scholarship, fellowship, and career-hunting process for students.

---

## 📌 Overview

**PathFinder AI** replaces tedious, fragmented opportunity searching with a single intelligent reasoning loop (**ReAct framework**). Instead of acting as a simple Q&A chatbot, the agent autonomously executes a complete discovery-to-application workflow using external tools:

* 📄 **Profile & Resume Parsing:** Reads CVs/resumes to extract GPA, major skills, academic history, and target fields into structured data.
* 🔎 **Autonomous Opportunity Sourcing:** Triggers live web search APIs to find relevant local and international scholarships, fellowships, and internships.
* 📊 **Eligibility & Gap Auditing:** Cross-references candidate profiles against official program requirements, calculating a match score and flagging missing prerequisites (e.g., IELTS, recommendation letters).
* 📝 **SOP & Roadmap Drafting:** Generates tailored Statements of Purpose (SOPs) aligned with program rubrics alongside a deadline-driven preparation checklist.

---

## 🛠️ Tech Stack & Tools

* **Agent Logic:** Python, LangChain / LlamaIndex (ReAct Loop)
* **LLM Engine:** Google Gemini 1.5/2.0 Flash / OpenAI GPT-4o
* **Search Tool:** Tavily Search API / Serper API
* **Frontend UI:** Streamlit / Chainlit
