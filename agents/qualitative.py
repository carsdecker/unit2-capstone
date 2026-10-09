# agents/qualitative.py
import chromadb
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
load_dotenv()

# The SDK does NOT retry by default (one attempt only). Gemini returned frequent
# 503 "high demand" errors in testing, and a "both" query needs 5 calls to succeed
# in a row. Retry server errors up to 4 attempts with backoff (~1s, 2s, 4s).
# 429 (quota) is excluded: on the free tier it means the daily limit is used up,
# so retrying only adds delay.
client = genai.Client(http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(
    attempts=4,
    http_status_codes=[500, 502, 503, 504]
)))
model = SentenceTransformer("all-MiniLM-L6-v2")

# System prompt: fixed developer rules, sent via system_instruction rather than
# mixed into the user message. Retrieved chunks and the user's query are text we
# don't control; keeping the rules in a separate, higher-priority channel makes
# them harder to override with injected instructions (indirect prompt injection).
# Role line: frames the model as a documentation assistant, not a general chatbot.
# "ONLY the context": the core anti-hallucination instruction.
# Exact refusal sentence: gives the validator a fixed phrase ("cannot find") to detect.
# Citation instruction: makes grounding checkable by the validator.
SYSTEM_PROMPT = """You are a helpful enterprise documentation assistant.
Answer the question using ONLY the context provided.
If the answer is not in the context, say "I cannot find this information in the provided documents."
Always cite the source number(s) you used."""

def retrieve(query: str, top_k: int = 5) -> list[dict]:
    chroma = chromadb.PersistentClient(path="./data/chroma")
    collection = chroma.get_collection("enterprise-docs")
    embedding = model.encode([query]).tolist()
    results = collection.query(query_embeddings=embedding, n_results=top_k)
    return [
        {
            "content": doc,
            "source": meta["source"],
            "chunk": meta["chunk"]
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]

def build_prompt(query: str, chunks: list[dict]) -> str:
    context = ""
    for i, chunk in enumerate(chunks):
        # Number each chunk so the model can cite "Source N" and the validator
        # can match those citations back to a real file.
        context += f"[Source {i+1}: {chunk['source']}]\n{chunk['content']}\n\n"

    # Rules live in SYSTEM_PROMPT; this message carries only data.
    # Context before question: the model reads the evidence before the task.
    return f"""CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""

def run(query: str) -> dict:
    chunks = retrieve(query)
    prompt = build_prompt(query, chunks)
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=1024,
            # Thinking tokens count against max_output_tokens and are billed as
            # output; answering from supplied context doesn't need deep reasoning.
            thinking_config=types.ThinkingConfig(thinking_level="minimal")
        )
    )
    return {
        "answer": response.text,
        "chunks": chunks,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count
    }
