from jarvis.features.apps.manager import ApplicationManager

manager = ApplicationManager()

for query in [
    "vscode",
    "vs code",
    "chrome",
    "brave browser",
    "vs code",
]:
    result = manager.resolve_detailed(query)

    print()
    print("QUERY:", query)
    print("RESULT:", result.application)
    print("CONFIDENCE:", result.confidence)
    print("REASON:", result.reason)
    print("CANDIDATES:", [a.name for a in result.candidates])