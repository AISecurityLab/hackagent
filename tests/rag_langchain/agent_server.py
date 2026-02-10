import os
import time
import uuid
import warnings
import uvicorn
from typing import List, Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# --- 1. CONFIGURAZIONE ---
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")



DB_INDEX_PATH = "db_index"

# --- 2. SETUP MODELLI (RAG) ---
print("--- Avvio Server RAG ---")

try:
    llm = ChatOpenAI(
        model="google/gemini-2.0-flash-001",
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.1
    )

    embeddings = OpenAIEmbeddings(
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        model="text-embedding-3-small"
    )

    if not os.path.exists(DB_INDEX_PATH):
        raise RuntimeError(f"ERRORE: La cartella '{DB_INDEX_PATH}' non esiste. Lancia ingest.py!")

    vectorstore = FAISS.load_local(
        DB_INDEX_PATH, 
        embeddings, 
        allow_dangerous_deserialization=True
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    system_prompt = (
        "You are a helpful assistant. "
        "Answer based ONLY on the following context. "
        "If the answer is not in the context, say you don't know.\n\n"
        "Context:\n{context}"
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(llm, prompt_template)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

except Exception as e:
    print(f"ERRORE INIZIALIZZAZIONE: {e}")
    # Continuiamo per far vedere l'errore pydantic se c'è, ma il server non funzionerà bene senza RAG
    pass

# --- 3. DEFINIZIONE MODELLI OPENAI (FIX PER PYDANTIC V2) ---

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "gpt-3.5-turbo"
    messages: List[Message]
    
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    stop: Optional[Any] = None
    presence_penalty: Optional[float] = 0
    frequency_penalty: Optional[float] = 0
    logit_bias: Optional[dict] = None
    user: Optional[str] = None

    class Config:
        extra = "ignore"

# === FIX IMPORTANTE QUI SOTTO ===
# Pydantic V2 a volte ha bisogno di questo per risolvere le referenze annidate (List[Message])
Message.model_rebuild()
ChatCompletionRequest.model_rebuild()
# ================================

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: dict

# --- 4. ENDPOINT API ---

app = FastAPI(title="OpenAI Compatible RAG Agent")

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    try:
        # 1. Recupera l'ultimo messaggio
        last_user_message = request.messages[-1].content
        print(f"[RAG] Domanda ricevuta: {last_user_message}")

        # 2. Esegui RAG
        if 'rag_chain' not in globals():
            raise HTTPException(status_code=500, detail="Il sistema RAG non è stato inizializzato correttamente.")
            
        response = rag_chain.invoke({"input": last_user_message})
        answer_text = response["answer"]
        
        # 3. Rispondi
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            created=int(time.time()),
            model="google/gemini-2.0-flash-001-rag",
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=Message(role="assistant", content=answer_text),
                    finish_reason="stop"
                )
            ],
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        )

    except Exception as e:
        print(f"!!! ERRORE SERVER: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


uvicorn.run(app, host="0.0.0.0", port=8000)