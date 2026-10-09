# main.py
from google.genai import errors
from agents.manager import run

def main():
    print("Spoonful Enterprise RAG System")
    print("Type 'exit' to quit.\n")
    while True:
        query = input("Ask a question: ").strip()
        if query.lower() in ["exit", "quit"]:
            break
        if not query:
            continue
        try:
            run(query)
        except errors.APIError as e:
            # Gemini service errors (503 overloaded, 429 quota) crashed the whole CLI
            # during testing. Report them and keep the session running instead.
            print(f"\n⚠️  Gemini request failed ({e.code} {e.status}): {e.message}")
            print("This question was not fully answered; any results above are incomplete. Please try again.\n")

if __name__ == "__main__":
    main()