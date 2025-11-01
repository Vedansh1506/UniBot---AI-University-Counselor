# knowledge_base/build_vector_db.py
import os
import pickle
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA_SOURCE_DIR = os.path.join(os.path.dirname(__file__), 'data')
DB_DIR = os.path.join(os.path.dirname(__file__), 'chroma_db')
CORPUS_FILE = os.path.join(DB_DIR, "corpus.pkl") # We still save the corpus here

def build_corpus():
    print("--- Building corpus for keyword search ---")
    
    loader = DirectoryLoader(
        DATA_SOURCE_DIR, 
        glob="**/*.md", 
        loader_cls=TextLoader, 
        loader_kwargs={'encoding': 'utf-8'}
    )
    documents = loader.load()

    # We still split the docs so the keyword search returns small chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=200
    )
    docs = text_splitter.split_documents(documents)

    # Save the documents for the BM25 keyword search
    os.makedirs(DB_DIR, exist_ok=True)
    with open(CORPUS_FILE, "wb") as f:
        pickle.dump(docs, f)

    print(f"--- Corpus built successfully with {len(docs)} chunks. ---")
    print(f"Corpus saved to {CORPUS_FILE}")

if __name__ == "__main__":
    build_corpus()