# In knowledge_base/build_vector_db.py
import os
import pickle
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader

DATA_SOURCE_DIR = "data"
DB_PERSIST_DIR = "chroma_db"
CORPUS_FILE = "corpus.pkl" # File to save raw documents for keyword search

def build_vector_database():
    print(f"Loading documents from the '{DATA_SOURCE_DIR}' directory...")
    
    loader = DirectoryLoader(
        DATA_SOURCE_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf-8'}
    )
    documents = loader.load()

    if not documents:
        print("No .md documents found.")
        return

    # Add university name as metadata
    for doc in documents:
        file_name = os.path.basename(doc.metadata['source'])
        university_name = os.path.splitext(file_name)[0].replace('_', ' ').title()
        doc.metadata['university'] = university_name
    
    print(f"Loaded {len(documents)} complete university files.")
    
    # --- NEW: Save the raw documents for keyword search ---
    print(f"Saving raw documents to '{CORPUS_FILE}'...")
    with open(os.path.join(os.path.dirname(__file__), DB_PERSIST_DIR, CORPUS_FILE), "wb") as f:
        pickle.dump(documents, f)

    print("Creating vector embeddings for semantic search...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vector_db = Chroma.from_documents(
        documents=documents,
        embedding=embedding_model,
        persist_directory=DB_PERSIST_DIR
    )
    
    print(f"--- SUCCESS ---")
    print(f"Vector DB and Corpus file have been built.")

if __name__ == "__main__":
    build_vector_database()