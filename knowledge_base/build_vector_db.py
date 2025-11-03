# knowledge_base/build_vector_db.py
import os
import pickle
import re
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Use absolute paths based on the Docker WORKDIR /app ---
DATA_SOURCE_DIR = '/app/knowledge_base/data'
DB_DIR = '/app/knowledge_base/chroma_db'
CORPUS_FILE = os.path.join(DB_DIR, "corpus.pkl")

def build_corpus():
    print(f"--- Building corpus from: {DATA_SOURCE_DIR} ---")
    
    loader = DirectoryLoader(
        DATA_SOURCE_DIR, 
        glob="**/*.md", 
        loader_cls=TextLoader, 
        loader_kwargs={'encoding': 'utf-8'}
    )
    documents = loader.load()

    if not documents:
        print(f"--- ERROR: No documents found in {DATA_SOURCE_DIR}. Corpus will not be built. ---")
        return 

    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n## ", "\n# ", "\n\n"],
        chunk_size=1000,
        chunk_overlap=200
    )
    docs = text_splitter.split_documents(documents)

    for doc in docs:
        source_path = doc.metadata.get("source", "")
        filename = os.path.basename(source_path)
        match = re.search(r'\d*-(.*?)\.md', filename.lower())
        university_key = match.group(1) if match else os.path.splitext(filename)[0].lower()
        doc.metadata["university"] = university_key
    
    os.makedirs(DB_DIR, exist_ok=True)
    with open(CORPUS_FILE, "wb") as f:
        pickle.dump(docs, f)

    print(f"--- Corpus built successfully with {len(docs)} chunks. ---")
    print(f"Corpus saved to {CORPUS_FILE}")

if __name__ == "__main__":
    build_corpus()