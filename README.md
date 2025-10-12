# 🎓 AI University Counselor Chatbot

A super-advanced, fully local AI chatbot designed to assist students with university admissions. This B.Tech project features a dual-function AI that provides personalized university recommendations and answers specific questions about admissions criteria using a Retrieval-Augmented Generation (RAG) system.

## ✨ Features

- **User Authentication**: Secure login and registration system with password hashing.
- **Personalized Recommendations**: A guided flow collects a user's academic profile (GRE, TOEFL, CGPA, etc.) to generate "Ambitious," "Target," and "Safe" university suggestions.
- **Expert Q&A System**: Users can ask specific questions about 20+ top US universities. The AI uses a knowledge base of expert-curated documents to provide accurate answers.
- **Hybrid Search Engine**: Combines semantic and keyword search for highly accurate information retrieval.
- **User Feedback Loop**: Users can rate the AI's Q&A responses, and this feedback is logged for future analysis and model improvement.
- **Dark/Light Mode Theme**: A modern UI with a theme toggle for user preference.

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **AI/ML**: LangChain, Ollama, ChromaDB (Vector Store), `rank-bm25` (Keyword Search)
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite

## 🚀 Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone [Your-Repository-URL]
    cd university-predictor
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    venv\Scripts\activate  # On Windows
    source venv/bin/activate # On macOS/Linux
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Download a local LLM via Ollama** (e.g., `phi3`):
    ```bash
    ollama run phi3
    ```
5.  **Build the knowledge base:**
    ```bash
    cd knowledge_base
    python build_vector_db.py
    cd ..
    ```
6.  **Run the backend server:**
    ```bash
    cd backend
    python app.py
    ```
7.  **Open the frontend:** Open the `frontend/index.html` file in your browser.

## Usage

After logging in, you can either ask a direct question about a university or click the "Get Personalised Recommendations" button to start the guided flow.