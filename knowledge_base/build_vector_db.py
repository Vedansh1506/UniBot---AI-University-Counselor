import os
import pickle
import re
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- CRITICAL FIX: Use Absolute Docker Paths ---
# In Docker, our app lives in the folder '/app'
DATA_SOURCE_DIR = '/app/knowledge_base/data'
DB_DIR = '/app/knowledge_base/chroma_db'
CORPUS_FILE = os.path.join(DB_DIR, "corpus.pkl")

def build_corpus():
    print(f"--- STARTING BUILD ---")
    print(f"Looking for data in: {DATA_SOURCE_DIR}")
    
    # Ensure the output directory exists
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        print(f"Created directory: {DB_DIR}")

    try:
        loader = DirectoryLoader(
            DATA_SOURCE_DIR, 
            glob="**/*.md", 
            loader_cls=TextLoader, 
            loader_kwargs={'encoding': 'utf-8'}
        )
        documents = loader.load()
        
        if not documents:
            print("!!! ERROR: No documents found. Check your folder structure!")
            return

        print(f"Found {len(documents)} documents.")

        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n## ", "\n# ", "\n\n"],
            chunk_size=1000,
            chunk_overlap=200
        )
        docs = text_splitter.split_documents(documents)

        # Add metadata for the router
        for doc in docs:
            source_path = doc.metadata.get("source", "")
            filename = os.path.basename(source_path)
            match = re.search(r'\d*-(.*?)\.md', filename.lower())
            university_key = match.group(1) if match else os.path.splitext(filename)[0].lower()
            doc.metadata["university"] = university_key
        
        # Save the file
        with open(CORPUS_FILE, "wb") as f:
            pickle.dump(docs, f)

        print(f"--- SUCCESS: Corpus saved to {CORPUS_FILE} ---")

    except Exception as e:
        print(f"!!! CRITICAL FAILURE IN BUILD SCRIPT: {str(e)}")

if __name__ == "__main__":
    build_corpus()