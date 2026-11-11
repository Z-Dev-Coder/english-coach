# 🎓 English Coach — Adaptive AI Language Learning Platform

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5.0-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-000000?style=for-the-badge&logo=ollama&logoColor=white)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

A personal, adaptive English-learning application that translates real-world content into a tailored daily curriculum shaped by your measured skill weaknesses — running at **$0 recurring cost** using local language models.

---

## 🌟 Key Architecture & Principles

1. 🎯 **Independent Multi-Skill Profiling**: Instead of assigning a flat "B1" or "B2" label, learners maintain 8 distinct skill scores (Reading, Speaking, Listening, Grammar, Vocabulary, Pronunciation, Writing, Comprehension). Daily tasks target specific weak areas.
2. 🤖 **Zero-Cost Local AI Engine**: All generative features route through an extensible `AIProvider` abstraction backed by local Ollama models.
3. 🛡️ **Graceful Degradation**: Planners, streak tracking, and interactive exercises function reliably off the database even if the local AI service is offline.
4. 🎙️ **Speaking Script Studio**: Generates dynamic conversational scripts for pronunciation and verbal cadence drills.

---

## 🛠️ Project Structure

```
english-coach/
├── backend/                  # Django REST backend
│   ├── apps/
│   │   ├── ai/               # AI Provider abstraction & prompt templates
│   │   ├── accounts/         # Learner auth & independent proficiency profiles
│   │   ├── lessons/          # Daily curriculum planner & exercise generator
│   │   └── speaking/         # Speaking Script Studio
│   ├── config/               # Django settings & routing
│   └── manage.py
├── frontend/                 # React 18 + Vite frontend
│   ├── src/
│   │   ├── components/       # Lesson cards, speech recorder, skill graphs
│   │   └── pages/            # Dashboard, practice rooms, script studio
│   └── vite.config.js
├── docs/                     # Architectural documentation & ROADMAP.md
├── start.bat                 # One-click Windows launch script
├── stop.bat                  # Safe shutdown script
└── requirements.txt
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- [Ollama](https://ollama.com) *(Optional, for AI content generation)*

### 1. One-Click Launch (Windows)
Double-click **`start.bat`**. It automatically sets up dependencies, runs migrations, verifies both servers, and opens the application in your browser.

To safely terminate both processes, double-click **`stop.bat`**.

### 2. Manual Setup

**Backend**:
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
