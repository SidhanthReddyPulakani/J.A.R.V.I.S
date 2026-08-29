import keyboard


class HotkeyController:
    def __init__(self, agent) -> None:
        self.agent = agent
        self._registered = False

    def _toggle(self) -> None:
        enabled = self.agent.toggle()
        print(f"\n[Jarvis {'ENABLED' if enabled else 'DISABLED'}]")

    def start(self) -> None:
        if self._registered:
            return

        keyboard.add_hotkey(
            "ctrl+alt+j",
            self._toggle,
            suppress=False
        )

        self._registered = True

    def stop(self) -> None:
        if self._registered:
            keyboard.unhook_all_hotkeys()
            self._registered = False