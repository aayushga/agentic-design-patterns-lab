"""Show explicit preference storage, session state, and context-aware replies."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

if __package__:
    from ..app import MemoryStore, Session, chat
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import MemoryStore, Session, chat


def main() -> None:
    with TemporaryDirectory() as directory, MemoryStore(Path(directory) / "memory.sqlite3") as store:
        session = Session("demo-user", "chat-1", max_turns=2)
        for query in ["remember reply_style = concise", "issue: The app crashes during upload.",
                      "What issue did I mention?", "What did I say last?"]:
            result = chat(query, session, store)
            print("\nUser:", query)
            print("Assistant:", result.response)
            print("Recent turns:", result.short_term_turns)
            print("Session state:", result.session_state)
            print("Saved preferences:", result.long_term_facts)


if __name__ == "__main__":
    main()
