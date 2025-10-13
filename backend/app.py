import os
import pickle
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import time
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
import database
import random
from rank_bm25 import BM25Okapi # <-- The new keyword search library

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')

database.init_db()

# --- Startup Code ---
DB_PERSIST_DIR = "/tmp/chroma_db"
CORPUS_FILE = "/tmp/corpus.pkl"
DATA_SOURCE_DIR = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'data')

embedding_model = None; vector_db = None; llm = None; UNIVERSITY_RATINGS = {}

# --- NEW: Load corpus for keyword search ---
corpus = []
bm25 = None
try:
    if not os.path.exists(DB_PERSIST_DIR):
        print("Vector database not found. Building a new one...")
        start_time = time.time()
        
        # 1. Load the documents
        loader = DirectoryLoader(
            DATA_SOURCE_DIR, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'}
        )
        documents = loader.load()
        
        # 2. Save the corpus for keyword search
        with open(CORPUS_FILE, "wb") as f:
            pickle.dump(documents, f)
        
        # 3. Create and persist the vector database
        embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vector_db = Chroma.from_documents(
            documents=documents, embedding=embedding_model, persist_directory=DB_PERSIST_DIR
        )
        end_time = time.time()
        print(f"--- Vector DB built successfully in {end_time - start_time:.2f} seconds. ---")
    else:
        print("Existing vector database found. Loading...")

    # --- Load all components as before ---
    print("Loading embedding model...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    print("Loading vector database...")
    vector_db = Chroma(persist_directory=DB_PERSIST_DIR, embedding_function=embedding_model)
    
    print("Loading corpus for keyword search...")
    with open(CORPUS_FILE, "rb") as f:
        corpus = pickle.load(f)
    tokenized_corpus = [doc.page_content.split(" ") for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    
    print("Initializing LLM via Hugging Face Inference API...")
    repo_id = "microsoft/Phi-3-mini-4k-instruct"
    llm = HuggingFaceEndpoint(
        repo_id=repo_id,
        huggingfacehub_api_token=os.environ.get('HF_TOKEN'), # Reads the secret token
        temperature=0.7,
        max_new_tokens=512
    )
    # ... (rest of the startup code is the same)
    print("Loading university QS Rankings data...")
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'qs_rankings.csv')
    df = pd.read_csv(path, encoding='latin-1')
    df = df[df['Location'].str.contains("United States", na=False)].copy()
    df['RANK'] = df['RANK_2025'].astype(str).str.extract(r'(\d+)').astype(int)
    for _, row in df.iterrows():
        uni_name = row['Institution_Name'].lower().strip()
        rank = row['RANK']; rating = 1
        if rank > 50: rating = 2
        if rank > 150: rating = 3
        if rank > 300: rating = 4
        if rank > 500: rating = 5
        UNIVERSITY_RATINGS[uni_name] = rating
    print(f"--- System Ready. Hybrid Search pipeline is active. ---")
except Exception as e:
    print(f"--- FATAL ERROR: Could not initialize. Error: {e} ---")

# --- THIS IS THE NEW HYBRID SEARCH RAG FUNCTION ---
def get_rag_response(user_question):
    # 1. Semantic Search (finds by meaning)
    semantic_results = vector_db.similarity_search_with_score(user_question, k=5)
    
    # 2. Keyword Search (finds by exact words)
    query_tokens = user_question.split(" ")
    keyword_scores = bm25.get_scores(query_tokens)
    
    # 3. Hybrid Fusion (Reciprocal Rank Fusion - combines results)
    fused_scores = {}
    for i, (doc, _) in enumerate(semantic_results):
        doc_id = doc.metadata['source']
        if doc_id not in fused_scores:
            fused_scores[doc_id] = 0
        fused_scores[doc_id] += 1 / (i + 60) # RRF scoring

    # Find the index of the corpus documents from their source
    corpus_doc_map = {doc.metadata['source']: i for i, doc in enumerate(corpus)}

    for i, score in enumerate(keyword_scores):
        if score > 0:
            doc_id = corpus[i].metadata['source']
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0
            # Find the rank of this doc in the keyword results to score it
            keyword_rank = sorted(keyword_scores, reverse=True).index(score)
            fused_scores[doc_id] += 1 / (keyword_rank + 60)

    # Sort by the combined score to get the best documents
    sorted_docs = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
    
    # Get the top 3 documents from the fused results
    top_docs_indices = []
    for doc_id, _ in sorted_docs[:3]:
        if doc_id in corpus_doc_map:
            top_docs_indices.append(corpus_doc_map[doc_id])

    if not top_docs_indices:
        return "I could not find any information related to your question in my knowledge base."
    
    # Create the context from the top hybrid search results
    context = "\n\n---\n\n".join([corpus[i].page_content for i in top_docs_indices])
    
    # The prompt remains the same, but the context it receives is much better
    prompt_template = """
    You are a Q&A assistant. Use the following context to answer the question.
    **Rules:**
    1. Answer the question directly and concisely.
    2. Do NOT include any information that is not directly related to the question.
    3. Include all relevant details for the question asked.
    4. If the answer is not in the context, say "I could not find a specific answer in my knowledge base."
    **Context:** {context}
    **Question:** {question}
    **Precise Answer:**
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": context, "question": user_question})

@app.route('/chat', methods=['POST'])
def chat():
    if not llm or not vector_db: return jsonify({'error': 'The AI system is not ready.'}), 500
    try:
        data = request.get_json()
        username = data.get('username')
        user_message = data.get('question', '')
        user_profile_update = data.get('profile', None)
        if user_profile_update:
            database.save_profile(username, user_profile_update)
            current_profile = database.load_profile(username)
            tier_1, tier_2, tier_3, tier_4, tier_5 = [], [], [], [], []
            for name, rating in UNIVERSITY_RATINGS.items():
                if rating == 1: tier_1.append(name.title())
                elif rating == 2: tier_2.append(name.title())
                elif rating == 3: tier_3.append(name.title())
                elif rating == 4: tier_4.append(name.title())
                elif rating == 5: tier_5.append(name.title())
            
            # This is the AI-powered prompt that guides reasoning
            prompt_text = f"""
            You are an expert AI university counselor. Your task is to generate a personalized list of university recommendations for a student.
            **Here are your instructions:**
            1. **Understand the Categories:**
               - "Ambitious" universities are from Tier 1.
               - "Target" universities are from Tier 2 and Tier 3.
               - "Safe" universities are from Tiers 4 and 5.
            2. **Your Task:**
               - For the "Ambitious" category, select 7 universities from the Tier 1 list.
               - For the "Target" category, select 7 universities from the Tier 2 and Tier 3 lists combined.
               - For the "Safe" category, select 7 universities from the Tier 4 and Tier 5 lists combined.
            3. **Output Format:**
               - You MUST format the output with the markdown headings "## Ambitious", "## Target", and "## Safe".
               - List the universities under each heading. Do not write anything else.
            **Here is the data you must use:**
            - Tier 1: {tier_1}
            - Tier 2: {tier_2}
            - Tier 3: {tier_3}
            - Tier 4: {tier_4}
            - Tier 5: {tier_5}
            """
            answer = llm.invoke(prompt_text).content.strip()
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
        username = data.get('username'); question = data.get('question')
        answer = data.get('answer'); rating = data.get('rating')
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

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """
    This function serves the frontend files. It handles the homepage (index.html)
    and any other files like style.css, script.js, etc.
    """
    if path != "" and os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    else:
        return send_from_directory(FRONTEND_DIR, 'index.html')


if __name__ == '__main__':
    # Get the port from the environment variable set by Hugging Face, default to 5000 for local
    port = int(os.environ.get("PORT", 5000))
    # Run the app on host 0.0.0.0 to make it publicly accessible
    app.run(host='0.0.0.0', port=port, debug=False)