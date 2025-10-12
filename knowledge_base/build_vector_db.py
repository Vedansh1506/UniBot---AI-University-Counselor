# In knowledge_base/build_vector_db.py
import os
import pickle
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader

DATA_SOURCE_DIR = "data"
# --- THIS IS THE FIX ---
# We now use an absolute path to a writable temporary directory
DB_PERSIST_DIR = "/tmp/chroma_db"
CORPUS_FILE = "/tmp/corpus.pkl" # Also move the corpus to /tmp

def build_vector_database():
    print(f"Loading documents from the '{DATA_SOURCE_DIR}' directory...")
    loader = DirectoryLoader(
        os.path.join(os.path.dirname(__file__), DATA_SOURCE_DIR), 
        glob="**/*.md", 
        loader_cls=TextLoader, 
        loader_kwargs={'encoding': 'utf-8'}
    )
    documents = loader.load()
    if not documents:
        print("No .md documents found."); return

    for doc in documents:
        file_name = os.path.basename(doc.metadata['source'])
        university_name = os.path.splitext(file_name)[0].replace('_', ' ').title()
        doc.metadata['university'] = university_name
    
    print(f"Loaded {len(documents)} university files.")
    
    print(f"Saving raw documents to '{CORPUS_FILE}'...")
    with open(CORPUS_FILE, "wb") as f:
        pickle.dump(documents, f)

    print("Creating vector embeddings for semantic search...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_db = Chroma.from_documents(
        documents=documents, embedding=embedding_model, persist_directory=DB_PERSIST_DIR
    )
    
    print(f"--- SUCCESS ---: Vector DB and Corpus file have been built.")

if __name__ == "__main__":
    build_vector_database()