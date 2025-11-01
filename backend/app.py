# import os
# import pickle
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import pandas as pd
# from langchain_chroma import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from langchain_ollama import ChatOllama
# import database
# import random
# from rank_bm25 import BM25Okapi # <-- The new keyword search library

# app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}})

# database.init_db()

# # --- Startup Code ---
# DB_PERSIST_DIR = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'chroma_db')
# CORPUS_FILE = os.path.join(DB_PERSIST_DIR, "corpus.pkl")
# embedding_model = None; vector_db = None; llm = None; UNIVERSITY_RATINGS = {}

# # --- NEW: Load corpus for keyword search ---
# corpus = []
# bm25 = None
# try:
#     print("Loading local embedding model...")
#     embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
#     print("Loading vector database for semantic search...")
#     vector_db = Chroma(persist_directory=DB_PERSIST_DIR, embedding_function=embedding_model)
    
#     print("Loading corpus for keyword search...")
#     with open(CORPUS_FILE, "rb") as f:
#         corpus = pickle.load(f)
    
#     tokenized_corpus = [doc.page_content.split(" ") for doc in corpus]
#     bm25 = BM25Okapi(tokenized_corpus)
    
#     print("Initializing local LLM (Phi-3)...")
#     llm = ChatOllama(model="phi3")
#     # ... (rest of the startup code is the same)
#     print("Loading university QS Rankings data...")
#     path = os.path.join(os.path.dirname(__file__), '..', 'data', 'qs_rankings.csv')
#     df = pd.read_csv(path, encoding='latin-1')
#     df = df[df['Location'].str.contains("United States", na=False)].copy()
#     df['RANK'] = df['RANK_2025'].astype(str).str.extract(r'(\d+)').astype(int)
#     for _, row in df.iterrows():
#         uni_name = row['Institution_Name'].lower().strip()
#         rank = row['RANK']; rating = 1
#         if rank > 50: rating = 2
#         if rank > 150: rating = 3
#         if rank > 300: rating = 4
#         if rank > 500: rating = 5
#         UNIVERSITY_RATINGS[uni_name] = rating
#     print(f"--- System Ready. Hybrid Search pipeline is active. ---")
# except Exception as e:
#     print(f"--- FATAL ERROR: Could not initialize. Error: {e} ---")

# # --- THIS IS THE NEW HYBRID SEARCH RAG FUNCTION ---
# def get_rag_response(user_question):
#     # 1. Semantic Search (finds by meaning)
#     semantic_results = vector_db.similarity_search_with_score(user_question, k=5)
    
#     # 2. Keyword Search (finds by exact words)
#     query_tokens = user_question.split(" ")
#     keyword_scores = bm25.get_scores(query_tokens)
    
#     # 3. Hybrid Fusion (Reciprocal Rank Fusion - combines results)
#     fused_scores = {}
#     for i, (doc, _) in enumerate(semantic_results):
#         doc_id = doc.metadata['source']
#         if doc_id not in fused_scores:
#             fused_scores[doc_id] = 0
#         fused_scores[doc_id] += 1 / (i + 60) # RRF scoring

#     # Find the index of the corpus documents from their source
#     corpus_doc_map = {doc.metadata['source']: i for i, doc in enumerate(corpus)}

#     for i, score in enumerate(keyword_scores):
#         if score > 0:
#             doc_id = corpus[i].metadata['source']
#             if doc_id not in fused_scores:
#                 fused_scores[doc_id] = 0
#             # Find the rank of this doc in the keyword results to score it
#             keyword_rank = sorted(keyword_scores, reverse=True).index(score)
#             fused_scores[doc_id] += 1 / (keyword_rank + 60)

#     # Sort by the combined score to get the best documents
#     sorted_docs = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
    
#     # Get the top 3 documents from the fused results
#     top_docs_indices = []
#     for doc_id, _ in sorted_docs[:3]:
#         if doc_id in corpus_doc_map:
#             top_docs_indices.append(corpus_doc_map[doc_id])

#     if not top_docs_indices:
#         return "I could not find any information related to your question in my knowledge base."
    
#     # Create the context from the top hybrid search results
#     context = "\n\n---\n\n".join([corpus[i].page_content for i in top_docs_indices])
    
#     # The prompt remains the same, but the context it receives is much better
#     prompt_template = """
#     You are a Q&A assistant. Use the following context to answer the question.
#     **Rules:**
#     1. Answer the question directly and concisely.
#     2. Do NOT include any information that is not directly related to the question.
#     3. Include all relevant details for the question asked.
#     4. If the answer is not in the context, say "I could not find a specific answer in my knowledge base."
#     **Context:** {context}
#     **Question:** {question}
#     **Precise Answer:**
#     """
#     prompt = ChatPromptTemplate.from_template(prompt_template)
#     chain = prompt | llm | StrOutputParser()
#     return chain.invoke({"context": context, "question": user_question})

# @app.route('/chat', methods=['POST'])
# def chat():
#     if not llm or not vector_db: return jsonify({'error': 'The AI system is not ready.'}), 500
#     try:
#         data = request.get_json()
#         username = data.get('username')
#         user_message = data.get('question', '')
#         user_profile_update = data.get('profile', None)
#         if user_profile_update:
#             database.save_profile(username, user_profile_update)
#             current_profile = database.load_profile(username)
#             tier_1, tier_2, tier_3, tier_4, tier_5 = [], [], [], [], []
#             for name, rating in UNIVERSITY_RATINGS.items():
#                 if rating == 1: tier_1.append(name.title())
#                 elif rating == 2: tier_2.append(name.title())
#                 elif rating == 3: tier_3.append(name.title())
#                 elif rating == 4: tier_4.append(name.title())
#                 elif rating == 5: tier_5.append(name.title())
            
#             # This is the AI-powered prompt that guides reasoning
#             prompt_text = f"""
#             You are an expert AI university counselor. Your task is to generate a personalized list of university recommendations for a student.
#             **Here are your instructions:**
#             1. **Understand the Categories:**
#                - "Ambitious" universities are from Tier 1.
#                - "Target" universities are from Tier 2 and Tier 3.
#                - "Safe" universities are from Tiers 4 and 5.
#             2. **Your Task:**
#                - For the "Ambitious" category, select 7 universities from the Tier 1 list.
#                - For the "Target" category, select 7 universities from the Tier 2 and Tier 3 lists combined.
#                - For the "Safe" category, select 7 universities from the Tier 4 and Tier 5 lists combined.
#             3. **Output Format:**
#                - You MUST format the output with the markdown headings "## Ambitious", "## Target", and "## Safe".
#                - List the universities under each heading. Do not write anything else.
#             **Here is the data you must use:**
#             - Tier 1: {tier_1}
#             - Tier 2: {tier_2}
#             - Tier 3: {tier_3}
#             - Tier 4: {tier_4}
#             - Tier 5: {tier_5}
#             """
#             answer = llm.invoke(prompt_text).content.strip()
#             return jsonify({'answer': answer})
#         else:
#             answer = get_rag_response(user_message)
#             return jsonify({'answer': answer})
#     except Exception as e:
#         print(f"An error occurred in the chat endpoint: {e}")
#         return jsonify({'error': str(e)}), 500

# @app.route('/feedback', methods=['POST'])
# def handle_feedback():
#     try:
#         data = request.get_json()
#         username = data.get('username'); question = data.get('question')
#         answer = data.get('answer'); rating = data.get('rating')
#         if database.add_feedback(username, question, answer, rating):
#             return jsonify({'success': True, 'message': 'Feedback received.'})
#         else:
#             return jsonify({'success': False, 'message': 'Failed to save feedback.'}), 500
#     except Exception as e:
#         print(f"An error occurred in the feedback endpoint: {e}")
#         return jsonify({'error': str(e)}), 500

# @app.route('/register', methods=['POST'])
# def register():
#     data = request.get_json()
#     if database.register_user(data.get('username'), data.get('password')):
#         return jsonify({'success': True})
#     return jsonify({'success': False, 'message': 'Username already exists.'})

# @app.route('/login', methods=['POST'])
# def login():
#     data = request.get_json()
#     if database.check_user(data.get('username'), data.get('password')):
#         return jsonify({'success': True})
#     return jsonify({'success': False, 'message': 'Invalid credentials.'})

# @app.route('/get_profile', methods=['POST'])
# def get_profile():
#     data = request.get_json()
#     profile = database.load_profile(data.get('username'))
#     if profile:
#         return jsonify({'profile_found': True, 'profile': profile})
#     return jsonify({'profile_found': False})

# if __name__ == '__main__':
#     app.run(debug=True)
# backend/app.py
# backend/app.py
# backend/app.py
import os
import pickle
from flask import Flask, request, jsonify, send_from_directory # <-- Make sure send_from_directory is imported
from flask_cors import CORS
import pandas as pd
# --- REMOVED: Chroma and HuggingFaceEmbeddings ---
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
import database
import random
from rank_bm25 import BM25Okapi # <-- We are ONLY using this for search

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- THIS IS THE FIX ---
# This variable was missing, causing the 'serve' function to crash
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')


# --- DEPLOYMENT-READY database path ---
database.DATABASE_NAME = '/tmp/chatbot_memory.db'
database.init_db()

# --- Startup Code (Local paths are fine here) ---
DB_PERSIST_DIR = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'chroma_db')
CORPUS_FILE = os.path.join(DB_PERSIST_DIR, "corpus.pkl")
# --- REMOVED: embedding_model and vector_db ---
llm = None; UNIVERSITY_RATINGS = {}

corpus = []
bm25 = None
try:
    # --- REMOVED: All embedding and chroma loading ---
    
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
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'qs_rankings.csv')
    df = pd.read_csv(path, encoding='latin-1')
    # ... (rest of data loading is the same) ...
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
    
    # 1. Keyword Search
    query_tokens = user_question.split(" ")
    keyword_docs = bm25.get_top_n(query_tokens, corpus, n=3) # Get top 3 chunks

    if not keyword_docs:
        return "I'm sorry, that information is not in my knowledge base."

    # 2. Build Context
    context = "\n\n---\n\n".join([doc.page_content for doc in keyword_docs])
    
    # 3. Ask the LLM
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

# --- (All other routes: /chat, /feedback, /register, /login, /get_profile are PERFECT) ---
@app.route('/chat', methods=['POST'])
def chat():
    if not llm or not bm25: return jsonify({'error': 'The AI system is not ready.'}), 500
    try:
        data = request.get_json()
        username = data.get('username')
        user_message = data.get('question', '')
        user_profile_update = data.get('profile', None)
        
        if user_profile_update:
            # (This is your fast, Python-based recommendation logic - it's perfect)
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