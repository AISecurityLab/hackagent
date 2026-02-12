import os
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOC_PATH = os.path.join(SCRIPT_DIR, "policies.pdf")


def ingest():
    # Loading
    print("Loading document...")
    if DOC_PATH.endswith(".pdf"):
        loader = PyPDFLoader(DOC_PATH)
    else:
        loader = TextLoader(DOC_PATH)
    documents = loader.load()

    # Text chunking
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(documents)

    # Embedding
    embeddings = OpenAIEmbeddings(
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        model="text-embedding-3-small",
    )

    # Store
    print("Creating vector database...")
    db = FAISS.from_documents(docs, embeddings)
    db.save_local("db_index")
    print("Database saved to 'db_index'")


ingest()
