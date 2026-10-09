# test_retrieval.py — Step 3 check: are retrieved chunks relevant? (no LLM calls, free)
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
collection = chromadb.PersistentClient(path="./data/chroma").get_collection("enterprise-docs")

queries = [
    "What is our company's security policy?",
    "Explain the code review process",
    "How do we handle customer complaints?",
    "How long must passwords be?",                  # fact buried in the 2-chunk security doc
    "What is the refund approval limit for agents?",
    "What is the capital of France?",               # off-topic: nothing should match well
]

for q in queries:
    results = collection.query(query_embeddings=model.encode([q]).tolist(), n_results=3)
    print(f"\nQUERY: {q}")
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        # Lower distance = more similar
        print(f"  {dist:.3f}  {meta['source']} (chunk {meta['chunk']})")
