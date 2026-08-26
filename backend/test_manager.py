from jarvis.features.apps.manager import ApplicationManager

manager = ApplicationManager()

apps = manager.applications()

brave = next(
    app for app in apps
    if app.name.lower() == "brave"
)

relationship = manager.confirm_relationship(
    "browser",
    brave,
)

print(relationship)

result = manager.resolve_detailed(
    "browser"
)

print(result)