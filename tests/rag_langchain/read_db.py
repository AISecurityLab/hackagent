import os
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
import warnings


# --- CONFIGURATION ---
# You must use the EXACT SAME API key and Model used during ingestion
DB_FOLDER = "db_index"
EMBEDDING_MODEL_NAME = "text-embedding-3-small" # Or "text-embedding-3-large" if you changed it

def read_vector_db():
    print(f"--- Loading Vector Database from '{DB_FOLDER}' ---")

    # 1. Initialize Embedding Model
    # (Required to load the FAISS index structure, even if we are just reading text)
    embeddings = OpenAIEmbeddings(
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        model=EMBEDDING_MODEL_NAME
    )

    # 2. Load the Database
    try:
        # allow_dangerous_deserialization is needed because we are loading a local pickle file
        vectorstore = FAISS.load_local(
            DB_FOLDER, 
            embeddings, 
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        print(f"Error loading database: {e}")
        print("Did you run ingest.py first?")
        return

    # 3. Access the internal document store
    # The 'docstore' object holds the actual text chunks mapped to IDs
    all_documents = vectorstore.docstore._dict

    total_chunks = len(all_documents)
    print(f"Successfully loaded. Total chunks found: {total_chunks}\n")

    # 4. Print Content
    print("--- CONTENT PREVIEW ---")
    
    # Iterate through all stored chunks
    for doc_id, document in all_documents.items():
        print(f"ID: {doc_id}")
        print(f"Source Metadata: {document.metadata}")
        
        # Print the first 200 characters of the content to keep it readable
        preview_text = document.page_content[:200].replace("\n", " ")
        print(f"Content Preview: {preview_text}...") 
        print("-" * 50)

read_vector_db()