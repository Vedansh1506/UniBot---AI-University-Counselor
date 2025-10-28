# backend/app.py

import os
import pickle
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
# --- This is the self-contained AI model ---
from langchain_huggingface import HuggingFacePipeline 
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import database
from rank_bm25 import BM25Okapi
from langchain_community.document_loaders import DirectoryLoader, TextLoader

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')

# --- Initialize the database ---
database.init_db()

# --- Deployment-ready paths (Corrected Spelling) ---
DB_PERSIST_DIR = "/tmp/chroma_db"
CORPUS_FILE = "/tmp/corpus.pkl"
DATA_SOURCE_DIR = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'data')

embedding_model = None; vector_db = None; llm = None; UNIVERSITY_RATINGS = {}
corpus = []; bm25 = None

try:
    if not os.path.exists(DB_PERSIST_DIR):
        print("Vector database not found. Building a new one...")
        start_time = time.time()
        loader = DirectoryLoader(DATA_SOURCE_DIR, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
        documents = loader.load()
        with open(CORPUS_FILE, "wb") as f: pickle.dump(documents, f)
        embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vector_db = Chroma.from_documents(documents=documents, embedding=embedding_model, persist_directory=DB_PERSIST_DIR)
        end_time = time.time()
        print(f"--- Vector DB built successfully in {end_time - start_time:.2f} seconds. ---")
    else:
        print("Existing vector database found. Loading...")

    print("Loading embedding model...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    print("Loading vector database...")
    vector_db = Chroma(persist_directory=DB_PERSIST_DIR, embedding_function=embedding_model)
    print("Loading corpus for keyword search...")
    with open(CORPUS_FILE, "rb") as f: corpus = pickle.load(f)
    tokenized_corpus = [doc.page_content.split(" ") for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    
    print("Initializing local LLM pipeline (flan-t5-small)...")
    # This downloads the small model onto the server's disk
    llm = HuggingFacePipeline.from_model_id(
        model_id="google/flan-t5-small",
        task="text2text-generation",
        pipeline_kwargs={"max_new_tokens": 512},
    )
    
    print("Loading university QS Rankings data...")
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'qs_rankings.csv')
    df = pd.read_csv(path, encoding='latin-1')
    df = df[df['Location'].str.contains("United States", na=False)].copy()
    df['RANK'] = df['RANK_2025'].astype(str).str.extract(r'(\d+)').astype(int)
    for _, row in df.iterrows():
        uni_name = row['Institution_Name'].lower().strip()
        rank = row['RANK']; rating = 1;
        if rank > 50: rating = 2
        if rank > 150: rating = 3
        if rank > 300: rating = 4
        if rank > 500: rating = 5
        UNIVERSITY_RATINGS[uni_name] = rating
    print(f"--- System Ready. Hybrid Search pipeline is active. ---")

except Exception as e:
    print(f"--- FATAL ERROR: Could not initialize. Error: {e} ---")


# --- RAG Response Function ---
def get_rag_response(question):
    print(f"Processing RAG for question: {question}")
    # 1. Keyword search
    tokenized_query = question.lower().split(" ")
    keyword_docs = bm25.get_top_n(tokenized_query, corpus, n=3)
    
    # 2. Semantic search
    semantic_docs = vector_db.similarity_search(question, k=3)
    
    # 3. Combine and deduplicate
    combined_docs = {doc.metadata['source']: doc for doc in keyword_docs + semantic_docs}.values()
    context = "\n\n".join([doc.page_content for doc in combined_docs])
    
    # 4. Generate prompt
    template = """
    You are an expert university admissions counselor. Answer the user's question based ONLY on the context provided.
    If the context does not contain the answer, say "I'm sorry, that information is not in my knowledge base."
    
    CONTEXT:
    {context}
    
    QUESTION:
    {question}
    
    ANSWER:
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | StrOutputParser()
    
    return chain.invoke({"context": context, "question": question})

# --- All API Routes ---

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required.'}), 400
    if database.register_user(username, password):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Username already exists.'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if database.check_user(username, password):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401

@app.route('/get_profile', methods=['POST'])
def get_profile():
    username = request.json.get('username')
    profile = database.load_profile(username)
    if profile:
        return jsonify({'profile_found': True, 'profile': profile})
    else:
        return jsonify({'profile_found': False})

@app.route('/chat', methods=['POST'])
def chat():
    if not llm or not vector_db: 
        return jsonify({'error': 'The AI system is not ready.'}), 503
        
    try:
        data = request.get_json()
        username = data.get('username')
        user_message = data.get('question', '')
        user_profile_update = data.get('profile', None)

        if user_profile_update:
            database.save_profile(username, user_profile_update)
            tier_1, tier_2, tier_3, tier_4, tier_5 = [], [], [], [], []
            for name, rating in UNIVERSITY_RATINGS.items():
                if rating == 1: tier_1.append(name.title())
                elif rating == 2: tier_2.append(name.title())
                elif rating == 3: tier_3.append(name.title())
                elif rating == 4: tier_4.append(name.title())
                elif rating == 5: tier_5.append(name.title())
            
            prompt_text = f"""
            You are an expert AI university counselor. Your task is to generate a personalized list of university recommendations.
            Your instructions:
            1. For "Ambitious", select 7 universities from Tier 1.
            2. For "Target", select 7 universities from Tier 2 and Tier 3.
            3. For "Safe", select 7 universities from Tiers 4 and 5.
            4. Format the output with markdown headings "## Ambitious", "## Target", and "## Safe".
            5. List the universities under each heading. Do not write anything else.
            
            Here is the data:
            - Tier 1: {tier_1}
            - Tier 2: {tier_2}
            - Tier 3: {tier_3}
            - Tier 4: {tier_4}
            - Tier 5: {tier_5}
            """
            # --- THIS IS THE FIX: No .content.strip() ---
            answer = llm.invoke(prompt_text) 
            return jsonify({'answer': answer})
        else:
            answer = get_rag_response(user_message)
            return jsonify({'answer': answer})

    except Exception as e:
        print(f"!!! ERROR during /chat endpoint: {e}")
        error_message = "The AI model is busy or had an error. Please try again."
        return jsonify({"error": error_message}), 503

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.json
    username = data.get('username')
    question = data.get('question')
    answer = data.get('answer')
    rating = data.get('rating')
    
    if database.save_feedback(username, question, answer, rating):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Could not save feedback.'}), 500

# --- Routes to serve the frontend ---
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