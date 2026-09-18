"""Manettes USB : clones Super Nintendo et pads Switch / PowerA.

Les clones SNES apparaissent souvent comme de simples joysticks DirectInput
(croix = axes ou hat, 8 a 10 boutons). Les PowerA Switch ont sticks, hat,
ZL/ZR et un autre ordre de boutons (Y B A X). On lit joystick et Controller
SDL, et on choisit le mapping d'apres le nom du peripherique.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

import arcade

import settings

ActionSet = set[str]
_NAV_ACTIONS = ("left", "right", "up", "down")
_POV_CENTER = 36000


def _button(buttons: Sequence[object], index: int) -> bool:
    if not 0 <= index < len(buttons):
        return False
    value = buttons[index]
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _any_button(buttons: Sequence[object], indices: int | tuple[int, ...]) -> bool:
    if isinstance(indices, int):
        return _button(buttons, indices)
    return any(_button(buttons, index) for index in indices)


def direction_from_axes(
    x: float,
    y: float,
    hat_x: float,
    hat_y: float,
    deadzone: float = settings.PAD_DEADZONE,
) -> tuple[int, int]:
    """Convertit axes + hat en (-1, 0, 1).

    Sur un joystick pyglet, `y` vaut -1 en haut ; le hat a +1 en haut.
    """
    dx = 0
    dy = 0
    if hat_x <= -0.5:
        dx = -1
    elif hat_x >= 0.5:
        dx = 1
    if hat_y <= -0.5:
        dy = -1
    elif hat_y >= 0.5:
        dy = 1
    if dx == 0:
        if x <= -deadzone:
            dx = -1
        elif x >= deadzone:
            dx = 1
    if dy == 0:
        if y <= -deadzone:
            dy = 1
        elif y >= deadzone:
            dy = -1
    return dx, dy


def hat_from_pov(raw: object) -> tuple[float, float]:
    """Decode le POV DirectInput Windows (0-36000 centiemes de degre, sinon centre)."""
    if raw is None:
        return 0.0, 0.0
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0.0, 0.0
    if value < 0 or value > _POV_CENTER:
        return 0.0, 0.0
    if value <= 8:
        table = (
            (0.0, 1.0),
            (1.0, 1.0),
            (1.0, 0.0),
            (1.0, -1.0),
            (0.0, -1.0),
            (-1.0, -1.0),
            (-1.0, 0.0),
            (-1.0, 1.0),
            (0.0, 0.0),
        )
        return table[value]
    sector = int((value + 2250) / 4500) % 8
    table = (
        (0.0, 1.0),
        (1.0, 1.0),
        (1.0, 0.0),
        (1.0, -1.0),
        (0.0, -1.0),
        (-1.0, -1.0),
        (-1.0, 0.0),
        (-1.0, 1.0),
    )
    return table[sector]


def _pump_device(device: object) -> None:
    """Force la lecture DirectInput : Arcade ne reveille pas toujours l'event wait."""
    dispatch = getattr(device, "_dispatch_events", None)
    if not callable(dispatch):
        return
    try:
        dispatch()
    except Exception:
        return


def _joystick_hat(joystick: object) -> tuple[float, float]:
    hat_x = float(getattr(joystick, "hat_x", 0.0) or 0.0)
    hat_y = float(getattr(joystick, "hat_y", 0.0) or 0.0)
    if abs(hat_x) >= 0.5 or abs(hat_y) >= 0.5:
        return hat_x, hat_y
    control = getattr(joystick, "hat_x_control", None)
    raw = getattr(control, "value", None) if control is not None else None
    return hat_from_pov(raw)


def _joystick_buttons(joystick: object) -> list:
    buttons = list(getattr(joystick, "buttons", None) or ())
    if any(value not in (0, False, None) for value in buttons):
        return buttons
    controls = getattr(joystick, "button_controls", None) or ()
    if not controls:
        return buttons
    return [getattr(control, "value", False) for control in controls]


def layout_for_pad(name: str, button_count: int = 0) -> str:
    """Choisit le mapping DirectInput : SNES 8 boutons, ou Switch / PowerA."""
    lowered = name.lower()
    if "xbox" in lowered or "x-box" in lowered or "xinput" in lowered:
        return settings.PAD_LAYOUT_SNES
    if any(token in lowered for token in settings.PAD_SWITCH_NAME_TOKENS):
        return settings.PAD_LAYOUT_SWITCH
    if button_count >= settings.PAD_SWITCH_MIN_BUTTONS:
        return settings.PAD_LAYOUT_SWITCH
    return settings.PAD_LAYOUT_SNES


def actions_from_buttons(
    buttons: Sequence[bool],
    *,
    name: str = "",
    layout: str | None = None,
) -> ActionSet:
    """Mapping DirectInput selon le type de pad."""
    kind = layout or layout_for_pad(name, len(buttons))
    if kind == settings.PAD_LAYOUT_SWITCH:
        return _actions_switch(buttons)
    return _actions_snes(buttons)


def _actions_snes(buttons: Sequence[bool]) -> ActionSet:
    """Clones USB Super Nintendo : B saut, A attaque, Y dash, X projection."""
    actions: ActionSet = set()
    if _button(buttons, settings.PAD_BTN_B):
        actions.add("jump")
    if _button(buttons, settings.PAD_BTN_A):
        actions.add("attack")
        actions.add("confirm")
    if _button(buttons, settings.PAD_BTN_Y) or _button(buttons, settings.PAD_BTN_L):
        actions.add("dash")
    if _button(buttons, settings.PAD_BTN_X):
        actions.add("project")
    if _button(buttons, settings.PAD_BTN_R):
        actions.add("attack")
    if _any_button(buttons, settings.PAD_BTN_SELECT):
        actions.add("back")
    if _any_button(buttons, settings.PAD_BTN_START):
        actions.add("start")
    return actions


def _actions_switch(buttons: Sequence[bool]) -> ActionSet:
    """PowerA / Switch : B bas = saut, stick + croix, ZL/ZR ne pausent pas."""
    actions: ActionSet = set()
    if _button(buttons, settings.PAD_SWITCH_BTN_B):
        actions.add("jump")
    if _button(buttons, settings.PAD_SWITCH_BTN_A):
        actions.add("attack")
        actions.add("confirm")
    if _any_button(
        buttons,
        (settings.PAD_SWITCH_BTN_Y, settings.PAD_SWITCH_BTN_L, settings.PAD_SWITCH_BTN_ZL),
    ):
        actions.add("dash")
    if _button(buttons, settings.PAD_SWITCH_BTN_X):
        actions.add("project")
    if _button(buttons, settings.PAD_SWITCH_BTN_R) or _button(
        buttons, settings.PAD_SWITCH_BTN_ZR
    ):
        actions.add("attack")
    if _button(buttons, settings.PAD_SWITCH_BTN_MINUS):
        actions.add("back")
    if _any_button(
        buttons, (settings.PAD_SWITCH_BTN_PLUS, settings.PAD_SWITCH_BTN_HOME)
    ):
        actions.add("start")
    return actions


def _controller_down(controller: object, names: tuple[str, ...]) -> bool:
    return any(bool(getattr(controller, name, False)) for name in names)


def actions_from_controller(controller: object) -> ActionSet:
    """Mapping SDL / Xbox : A sud = saut (B Nintendo sur un pad SNES)."""
    actions: ActionSet = set()
    if _controller_down(controller, settings.PAD_CTRL_JUMP):
        actions.add("jump")
        actions.add("confirm")
    if _controller_down(controller, settings.PAD_CTRL_ATTACK):
        actions.add("attack")
        actions.add("confirm")
    if _controller_down(controller, settings.PAD_CTRL_DASH):
        actions.add("dash")
    if _controller_down(controller, settings.PAD_CTRL_PROJECT):
        actions.add("project")
    if _controller_down(controller, settings.PAD_CTRL_START):
        actions.add("start")
    if _controller_down(controller, settings.PAD_CTRL_BACK):
        actions.add("back")
    left_trigger = float(getattr(controller, "lefttrigger", 0.0) or 0.0)
    right_trigger = float(getattr(controller, "righttrigger", 0.0) or 0.0)
    if left_trigger >= settings.PAD_CTRL_TRIGGER_ON:
        actions.add("dash")
    if right_trigger >= settings.PAD_CTRL_TRIGGER_ON:
        actions.add("attack")
    return actions


def _device_key(device: object) -> str:
    guid = ""
    getter = getattr(device, "get_guid", None)
    if callable(getter):
        try:
            guid = str(getter() or "")
        except Exception:
            guid = ""
    name = str(getattr(device, "name", "") or "")
    return f"{id(device)}|{name}|{guid}"


def _list_joysticks() -> list:
    getter = getattr(arcade, "get_joysticks", None)
    if getter is None:
        try:
            from pyglet import input as pyglet_input
        except Exception:
            return []
        getter = pyglet_input.get_joysticks
    try:
        return list(getter() or [])
    except Exception:
        return []


def _list_controllers() -> list:
    getter = getattr(arcade, "get_controllers", None)
    if getter is None:
        return []
    try:
        return list(getter() or [])
    except Exception:
        return []


class PadHub:
    """Ouvre les pads branches et les relit chaque frame."""

    def __init__(self) -> None:
        self.held: frozenset[str] = frozenset()
        self.pressed: frozenset[str] = frozenset()
        self.released: frozenset[str] = frozenset()
        self.repeats: frozenset[str] = frozenset()
        self.axis_x = 0
        self.axis_y = 0
        self._joysticks: list = []
        self._controllers: list = []
        self._opened: set[str] = set()
        self._next_scan = 0.0
        self._prev: set[str] = set()
        self._calm = True
        self._nav_time = {name: 0.0 for name in _NAV_ACTIONS}
        self._nav_repeat = {name: 0.0 for name in _NAV_ACTIONS}
        self.scan_notes: tuple[str, ...] = ()
        self.using_pad = False

    def note_keyboard(self) -> None:
        """Le clavier reprend : les invites HUD redeviennent des touches."""
        self.using_pad = False

    @property
    def connected(self) -> bool:
        return bool(self._joysticks or self._controllers)

    def device_names(self) -> tuple[str, ...]:
        names: list[str] = []
        for joystick in self._joysticks:
            device = getattr(joystick, "device", None)
            names.append(str(getattr(device, "name", None) or "Joystick"))
        for controller in self._controllers:
            names.append(str(getattr(controller, "name", None) or "Controller"))
        return tuple(names)

    def status_line(self) -> str:
        names = self.device_names()
        if not names:
            note = self.scan_notes[0] if self.scan_notes else "aucune detectee"
            return f"Manette : {note}"
        held = ",".join(sorted(self.held)) if self.held else "-"
        return f"Manette : {', '.join(names)}  [{held}]"

    def debug_lines(self) -> list[str]:
        """Etat brut pour l'ecran de test : axes, indices de boutons, actions."""
        lines = [self.status_line()]
        if self.scan_notes:
            lines.extend(self.scan_notes)
        for joystick in self._joysticks:
            device = getattr(joystick, "device", None)
            _pump_device(device)
            name = str(getattr(device, "name", None) or "Joystick")
            buttons = list(_joystick_buttons(joystick))
            down = [index for index, value in enumerate(buttons) if value not in (0, False, None)]
            layout = layout_for_pad(name, len(buttons))
            hat_x, hat_y = _joystick_hat(joystick)
            pov_raw = getattr(getattr(joystick, "hat_x_control", None), "value", None)
            lines.append(
                f"{name}  layout={layout}  x={float(getattr(joystick, 'x', 0) or 0):+.2f} "
                f"y={float(getattr(joystick, 'y', 0) or 0):+.2f} "
                f"hat={hat_x:+.0f},{hat_y:+.0f}  pov={pov_raw}"
            )
            lines.append(
                f"  boutons {len(buttons)}  enfonces {down or '-'}  "
                f"actions {sorted(self.held) or '-'}"
            )
        for controller in self._controllers:
            name = str(getattr(controller, "name", None) or "Controller")
            lines.append(
                f"{name}  stick={float(getattr(controller, 'leftx', 0) or 0):+.2f},"
                f"{float(getattr(controller, 'lefty', 0) or 0):+.2f} "
                f"dpad={float(getattr(controller, 'dpadx', 0) or 0):+.0f},"
                f"{float(getattr(controller, 'dpady', 0) or 0):+.0f}"
            )
            lines.append(f"  actions {sorted(self.held) or '-'}")
        if not self._joysticks and not self._controllers:
            lines.append("Windows : Win+R puis joy.cpl  |  play.py --pad pour ce test")
        return lines

    def calm(self) -> None:
        """Ignore les boutons deja enfonces jusqu'au prochain relachement."""
        self._calm = True

    def poll(self, window: arcade.Window | None, delta_time: float = 0.0) -> None:
        self._scan(window)
        held, axis_x, axis_y = self._read()
        if self._calm:
            self._prev = set(held)
            self._calm = False
            self.held = frozenset(held)
            self.pressed = frozenset()
            self.released = frozenset()
            self.repeats = frozenset()
            self.axis_x = axis_x
            self.axis_y = axis_y
            if held or axis_x or axis_y:
                self.using_pad = True
            return
        self.pressed = frozenset(held - self._prev)
        self.released = frozenset(self._prev - held)
        self._prev = set(held)
        self.held = frozenset(held)
        self.axis_x = axis_x
        self.axis_y = axis_y
        if self.pressed or self.held or axis_x or axis_y:
            self.using_pad = True
        self._tick_repeat(delta_time)

    def menu_symbols(
        self, *, allow_back: bool = True, start_is_back: bool = False
    ) -> tuple[int, ...]:
        """Touches clavier equivalentes a envoyer a `on_key_press` des menus."""
        symbols: list[int] = []
        nav = self.pressed | self.repeats
        if "left" in nav:
            symbols.append(arcade.key.LEFT)
        if "right" in nav:
            symbols.append(arcade.key.RIGHT)
        if "up" in nav:
            symbols.append(arcade.key.UP)
        if "down" in nav:
            symbols.append(arcade.key.DOWN)
        confirm = "confirm" in self.pressed or "jump" in self.pressed
        if start_is_back:
            if "start" in self.pressed or (allow_back and "back" in self.pressed):
                symbols.append(arcade.key.ESCAPE)
            elif confirm:
                symbols.append(arcade.key.ENTER)
        else:
            if confirm or "start" in self.pressed:
                symbols.append(arcade.key.ENTER)
            if allow_back and "back" in self.pressed:
                symbols.append(arcade.key.ESCAPE)
        return tuple(symbols)

    def _tick_repeat(self, delta_time: float) -> None:
        repeats: set[str] = set()
        delay = settings.PAD_REPEAT_DELAY
        rate = settings.PAD_REPEAT_RATE
        for name in _NAV_ACTIONS:
            if name in self.pressed:
                repeats.add(name)
                self._nav_time[name] = 0.0
                self._nav_repeat[name] = 0.0
            elif name in self.held:
                self._nav_time[name] += max(0.0, delta_time)
                if self._nav_time[name] >= delay:
                    self._nav_repeat[name] += max(0.0, delta_time)
                    if self._nav_repeat[name] >= rate:
                        repeats.add(name)
                        self._nav_repeat[name] = 0.0
            else:
                self._nav_time[name] = 0.0
                self._nav_repeat[name] = 0.0
        self.repeats = frozenset(repeats)

    def _scan(self, window: arcade.Window | None) -> None:
        if window is None:
            return
        t = time.perf_counter()
        if t < self._next_scan:
            return
        interval = (
            settings.PAD_RESCAN_INTERVAL
            if (self._joysticks or self._controllers)
            else settings.PAD_RESCAN_EMPTY
        )
        self._next_scan = t + interval
        notes: list[str] = []
        joysticks = _list_joysticks()
        controllers = _list_controllers()
        if not controllers and not joysticks:
            notes.append("Windows ne voit aucun pad (joy.cpl)")
        for joystick in joysticks:
            device = getattr(joystick, "device", None)
            key = _device_key(device) if device is not None else _device_key(joystick)
            if key in self._opened:
                continue
            try:
                joystick.open(window)
            except Exception as error:
                notes.append(f"echec ouverture : {error}")
                continue
            self._joysticks.append(joystick)
            self._opened.add(key)
        for controller in controllers:
            device = getattr(controller, "device", None)
            key = _device_key(device) if device is not None else _device_key(controller)
            if key in self._opened:
                continue
            try:
                controller.open(window)
            except Exception as error:
                notes.append(f"echec ouverture : {error}")
                continue
            self._controllers.append(controller)
            self._opened.add(key)
        self.scan_notes = tuple(notes)

    def _read(self) -> tuple[set[str], int, int]:
        actions: set[str] = set()
        dirs: list[tuple[int, int]] = []
        for joystick in self._joysticks:
            try:
                _pump_device(getattr(joystick, "device", None))
                buttons = _joystick_buttons(joystick)
                device = getattr(joystick, "device", None)
                name = str(getattr(device, "name", None) or "")
                actions.update(actions_from_buttons(buttons, name=name))
                hat_x, hat_y = _joystick_hat(joystick)
                dx, dy = direction_from_axes(
                    float(getattr(joystick, "x", 0.0) or 0.0),
                    float(getattr(joystick, "y", 0.0) or 0.0),
                    hat_x,
                    hat_y,
                )
                dirs.append((dx, dy))
            except Exception:
                continue
        for controller in self._controllers:
            try:
                _pump_device(getattr(controller, "device", None))
                actions.update(actions_from_controller(controller))
                dx, dy = direction_from_axes(
                    float(getattr(controller, "leftx", 0.0) or 0.0),
                    float(getattr(controller, "lefty", 0.0) or 0.0),
                    float(getattr(controller, "dpadx", 0.0) or 0.0),
                    float(getattr(controller, "dpady", 0.0) or 0.0),
                )
                dirs.append((dx, dy))
            except Exception:
                continue
        axis_x = 0
        axis_y = 0
        if dirs:
            sx = sum(item[0] for item in dirs)
            sy = sum(item[1] for item in dirs)
            axis_x = 1 if sx > 0 else (-1 if sx < 0 else 0)
            axis_y = 1 if sy > 0 else (-1 if sy < 0 else 0)
        if axis_x < 0:
            actions.add("left")
        elif axis_x > 0:
            actions.add("right")
        if axis_y < 0:
            actions.add("down")
        elif axis_y > 0:
            actions.add("up")
        return actions, axis_x, axis_y


_HUB: PadHub | None = None


def get_pad() -> PadHub:
    global _HUB
    if _HUB is None:
        _HUB = PadHub()
    return _HUB


def dispatch_menu_pad(
    view: object,
    delta_time: float = 0.0,
    *,
    allow_back: bool = True,
    start_is_back: bool = False,
) -> None:
    """Traduit la manette en appels `on_key_press` pour un ecran de menu."""
    handler = getattr(view, "on_key_press", None)
    if not callable(handler):
        return
    window = getattr(view, "window", None)
    pad = get_pad()
    pad.poll(window, delta_time)
    for symbol in pad.menu_symbols(allow_back=allow_back, start_is_back=start_is_back):
        _invoke_key(handler, view, symbol)


def _invoke_key(handler: Callable, view: object, symbol: int) -> None:
    window = getattr(view, "window", None)
    try:
        handler(symbol, 0)
        return
    except TypeError:
        pass
    if window is not None:
        handler(window, symbol, 0)
