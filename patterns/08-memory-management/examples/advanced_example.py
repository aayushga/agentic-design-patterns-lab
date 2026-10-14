"""Demonstrate reopening the database, new sessions/users, updates, and forgetting."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

if __package__:
    from ..app import MemoryStore, Session, chat
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import MemoryStore, Session, chat


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "memory.sqlite3"
        with MemoryStore(path) as store:
            first = Session("alice", "chat-1")
            chat("remember reply_style = concise", first, store)
            chat("issue: Upload fails.", first, store)
            print("First session:", first.state)
        # Reopen from disk, with fresh session objects: only preferences survive.
        with MemoryStore(path) as store:
            alice = Session("alice", "chat-2")
            print("\nAfter reopening:", chat("recall reply_style", alice, store).response)
            print("New session issue:", chat("What issue did I mention?", alice, store).response)
            bob = Session("bob", "chat-2")
            print("Other user:", chat("recall reply_style", bob, store).response)
            print("Update:", chat("remember reply_style = detailed", alice, store).response)
            print("Forget:", chat("forget reply_style", alice, store).response)
            print("After forgetting:", chat("recall reply_style", alice, store).response)
            chat("remember preferred_language = spanish", alice, store)
            print("Reset:", chat("reset session", alice, store).response)
            print("Preferences after reset:", chat("recall preferred_language", alice, store).response)
        print("\nTemporary demo database cleaned up on exit.")


if __name__ == "__main__":
    main()
