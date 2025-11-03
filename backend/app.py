# backend/app.py
import os
import pickle
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
import database
import random
from rank_bm25 import BM25Okapi

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')
database.DATABASE_NAME = '/tmp/chatbot_memory.db'
database.init_db()

# --- FIX: Use absolute paths based on the Docker WORKDIR /app ---
DB_PERSIST_DIR = '/app/knowledge_base/chroma_db'
CORPUS_FILE = os.path.join(DB_PERSIST_DIR, "corpus.pkl")

llm = None; UNIVERSITY_RATINGS = {}
corpus = []; bm25 = None
try:
    print("Loading corpus for keyword search...")
    with open(CORPUS_FILE, "rb") as f:
        corpus = pickle.load(f)
    
    print("Tokenizing corpus for BM25...")
    tokenized_corpus = [doc.page_content.split(" ") for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    
    print("Initializing Groq LLM (Llama-3.1-8B-Instant)...")
    llm = ChatGroq(
        model_name="llama-3.1-8b-instant", 
        temperature=0.7,
        groq_api_key=os.environ.get("GROQ_API_KEY")
    )
    
    print("Loading university QS Rankings data...")
    # This path is relative to the app.py file, so it's correct
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'qs_rankings.csv')
    df = pd.read_csv(path, encoding='latin-1')
    df = df[df['Location'].str.contains("United States", na=False)].copy()
    df['RANK'] = df['RANK_2025'].astype(str).str.extract(r'(\d+)').astype(int)
    for _, row in df.iterrows():
        uni_name = row['Institution_Name'].lower().strip()
        rank = row['RANK']; rating = 1;
        if rank > 50: rating = 2;
        if rank > 150: rating = 3;
        if rank > 300: rating = 4;
        if rank > 500: rating = 5;
        UNIVERSITY_RATINGS[uni_name] = rating
    print(f"--- System Ready. Keyword-Only RAG is active. ---")
except Exception as e:
    print(f"--- FATAL ERROR: Could not initialize. Error: {e} ---")

# --- RAG function (Now Keyword-Only) ---
def get_rag_response(user_question):
    print(f"--- RAG: Searching (Keyword-Only) for '{user_question}' ---")
    query_tokens = user_question.split(" ")
    keyword_docs = bm25.get_top_n(query_tokens, corpus, n=3) 
    if not keyword_docs:
        return "I'm sorry, that information is not in my knowledge base."
    context = "\n\n---\n\n".join([doc.page_content for doc in keyword_docs])
    prompt_template = """
    <|begin_of_text|><|start_header_id|>system<|end_header_id|>
    You are a Q&A assistant. Use the following context to answer the question.
    **Rules:**
    1. Answer the question directly and concisely.
    2. Do NOT include any information that is not directly related to the question.
    3. Include all relevant details for the question asked.
    4. If the answer is not in the context, say "I'm sorry, that information is not in my knowledge base."
    **Context:** {context}<|eot_id|><|start_header_id|>user<|end_header_id|>
    **Question:** {question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
    **Precise Answer:**
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm | StrOutputParser()
    print("--- RAG: Context found. Asking Groq LLM... ---")
    answer = chain.invoke({"context": context, "question": user_question})
    print("--- RAG: LLM answer received. ---")
    return answer

# --- (All other routes are unchanged and correct) ---
@app.route('/chat', methods=['POST'])
def chat():
    if not llm or not bm25: return jsonify({'error': 'The AI system is not ready.'}), 500
    try:
        data = request.get_json()
        username = data.get('username')
        user_message = data.get('question', '')
        user_profile_update = data.get('profile', None)
        
        if user_profile_update:
            print("--- Received profile update. Generating recommendations with Python logic. ---")
            database.save_profile(username, user_profile_update)
            gre = user_profile_update.get('gre_score', 300); cgpa = user_profile_update.get('cgpa', 7.0)
            research = user_profile_update.get('research', 0); sop = user_profile_update.get('sop', 'Average')
            user_score = (min(gre, 340) / 340.0) * 0.5 + (min(cgpa, 10.0) / 10.0) * 0.5 
            if research > 0: user_score += 0.05
            if sop.lower() == 'good': user_score += 0.02
            if sop.lower() == 'excellent': user_score += 0.04
            user_score = min(user_score, 1.0)
            rating_map = { 1: 0.90, 2: 0.80, 3: 0.70, 4: 0.60, 5: 0.50 } 
            ambitious, target, safe = [], [], []
            for uni, rating in UNIVERSITY_RATINGS.items():
                uni_required_score = rating_map.get(rating, 0)
                if uni_required_score > user_score and (uni_required_score - user_score) < 0.15:
                    ambitious.append(uni.title())
                elif abs(uni_required_score - user_score) <= 0.07:
                    target.append(uni.title())
                elif uni_required_score < (user_score - 0.07):
                    safe.append(uni.title())
            answer = "Here are your personalized recommendations based on your profile:\n\n"
            answer += "## Ambitious\n" + ("".join(f"- {uni}\n" for uni in ambitious[:7]) if ambitious else "- (None found)\n")
            answer += "\n## Target\n" + ("".join(f"- {uni}\n" for uni in target[:7]) if target else "- (None found)\n")
            answer += "\n## Safe\n" + ("".join(f"- {uni}\n" for uni in safe[:7]) if safe else "- (None found)\n")
            return jsonify({'answer': answer})
        else:
            answer = get_rag_response(user_message)
            return jsonify({'answer': answer})
            
    except Exception as e:
        print(f"An error occurred in the chat endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/feedback', methods=['POST'])
def handle_feedback():
    try:
        data = request.get_json()
        username = data.get('username')
        question = data.get('question')
        answer = data.get('answer')
        rating = data.get('rating')
        if database.add_feedback(username, question, answer, rating):
            return jsonify({'success': True, 'message': 'Feedback received.'})
        else:
            return jsonify({'success': False, 'message': 'Failed to save feedback.'}), 500
    except Exception as e:
        print(f"An error occurred in the feedback endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if database.register_user(data.get('username'), data.get('password')):
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Username already exists.'})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if database.check_user(data.get('username'), data.get('password')):
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid credentials.'})

@app.route('/get_profile', methods=['POST'])
def get_profile():
    data = request.get_json()
    profile = database.load_profile(data.get('username'))
    if profile:
        return jsonify({'profile_found': True, 'profile': profile})
    return jsonify({'profile_found': False})

# --- Serve Frontend (deployment-ready) ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    else:
        return send_from_directory(FRONTEND_DIR, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)