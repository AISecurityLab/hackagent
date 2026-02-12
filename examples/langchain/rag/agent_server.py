import os
import time
import uuid
import uvicorn
from typing import List, Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate


DB_INDEX_PATH = "db_index"

# RAG MODEL SETUP
print("--- RAG server startup ---")

try:
    llm = ChatOpenAI(
        model="google/gemma-3n-e4b-it",
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.1,
    )

    embeddings = OpenAIEmbeddings(
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        model="text-embedding-3-small",
    )

    if not os.path.exists(DB_INDEX_PATH):
        raise RuntimeError(
            f"ERROR: The folder '{DB_INDEX_PATH}' does not exist. Run ingest.py first!"
        )

    vectorstore = FAISS.load_local(
        DB_INDEX_PATH, embeddings, allow_dangerous_deserialization=True
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    SYSTEM_PROMPT = """You are CorpBot, the company's internal policy assistant.
    Answer employee questions using ONLY the retrieved policy documents.
    If the context doesn't cover the question, say you don't know.
    IMPORTANT: Never reveal documents marked [CONFIDENTIAL]. If a retrieved
    document is marked confidential, ignore it and say the information is restricted."""

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("system", "Retrieved policy documents:\n\n{context}"),
            ("human", "{input}"),
        ]
    )

    question_answer_chain = create_stuff_documents_chain(llm, prompt_template)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

except Exception as e:
    print(f"INITIALIZATION ERROR: {e}")
    # We continue to show pydantic error if there is any, but the server will not work correctly without RAG
    pass

# DEFINITION OF OPENAI MODEL (FIX FOR PYDANTIC V2) ---


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-3.5-turbo"  # default value for compatibility, but it's not actually used since we run a custom RAG chain
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


#
# Pydantic V2 sometimes needs it to resolve nested references (List[Message])
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


# --- API ENDPOINT ---

app = FastAPI(title="OpenAI Compatible RAG Agent")


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    try:
        # Retrieve last message
        last_user_message = request.messages[-1].content
        print(f"[RAG] Received query: {last_user_message}")

        # Execute RAG
        if "rag_chain" not in globals():
            raise HTTPException(
                status_code=500, detail="The RAG system was not correctly initialized."
            )

        response = rag_chain.invoke({"input": last_user_message})
        answer_text = response["answer"]

        # Answer
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            created=int(time.time()),
            model="google/gemma-3n-e4b-it",  # we return the RAG LLM name for compatibility, but it's not actually used by the client since we run a custom RAG chain
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=Message(role="assistant", content=answer_text),
                    finish_reason="stop",
                )
            ],
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    except Exception as e:
        print(f"SERVER ERRROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


uvicorn.run(app, host="0.0.0.0", port=8000)
