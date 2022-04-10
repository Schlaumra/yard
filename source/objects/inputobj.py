from pynput.keyboard import Key as pynput_key
from pynput.mouse import Button as pynput_button
# Final>> Mouse(1) Move(0) X Y
# Final>> Mouse(1) Button(1) Press(1)/Release(0) Code
from typing import Literal, Tuple
from abc import abstractmethod, ABC

mouse_mapping = {
    1: pynput_button.left,
    2: pynput_button.middle,
    3: pynput_button.right
}

key_mapping = {
    'F1': pynput_key.f1,
    'F2': pynput_key.f2,
    'F3': pynput_key.f3,
    'F4': pynput_key.f4,
    'F5': pynput_key.f5,
    'F6': pynput_key.f6,
    'F7': pynput_key.f7,
    'F8': pynput_key.f8,
    'F9': pynput_key.f9,
    'F10': pynput_key.f10,
    'F11': pynput_key.f11,
    'F12': pynput_key.f12,
    'F13': pynput_key.f13,
    'F14': pynput_key.f14,
    'F15': pynput_key.f15,
    'F16': pynput_key.f16,
    'F17': pynput_key.f17,
    'F18': pynput_key.f18,
    'F19': pynput_key.f19,
    'F20': pynput_key.f20,
    'Alt': pynput_key.alt,
    'ISO_Level3_Shift': pynput_key.alt_gr,
    'Alt_L': pynput_key.alt_l,
    'Alt_R': pynput_key.alt_r,
    'BackSpace': pynput_key.backspace,
    'Caps_Lock': pynput_key.caps_lock,
    'Super': pynput_key.cmd,
    'Super_L': pynput_key.cmd_l,
    'Super_R': pynput_key.cmd_r,
    'Control': pynput_key.ctrl,
    'Control_L': pynput_key.ctrl_l,
    'Control_R': pynput_key.ctrl_r,
    'Delete': pynput_key.delete,
    'Down': pynput_key.down,
    'End': pynput_key.end,
    'Return': pynput_key.enter,
    'Escape': pynput_key.esc,
    'Home': pynput_key.home,
    'Insert': pynput_key.insert,
    'Left': pynput_key.left,
    'Num_Lock': pynput_key.num_lock,
    'Next': pynput_key.page_down,
    'Prior': pynput_key.page_up,
    'Pause': pynput_key.pause,
    'Print': pynput_key.print_screen,
    'Right': pynput_key.right,
    'Shift': pynput_key.shift,
    'Shift_L': pynput_key.shift_l,
    'Shift_R': pynput_key.shift_r,
    'space': pynput_key.space,
    'Tab': pynput_key.tab,
    'Up': pynput_key.up
}


class Input(ABC):
    @abstractmethod
    def get_command(self):
        ...


class Key(Input):
    state = None
    special: bool = None
    code = None

    def __init__(self, state: Literal[0, 1] = None, code: Tuple[str, str, int] = None):
        self.state = state
        if key_mapping.get(code[1], None):
            self.code = code[1]
            self.special = True
        elif code[0]:
            self.code = code[0]
            self.special = False
        else:
            self.code = code[1]
            self.special = False

    def get_command(self):
        if self.special:
            return key_mapping[self.code]
        else:
            return self.code


class Mouse(Input):
    coordinates: Tuple[int, int] = None
    code = None
    scroll = None
    drag = None
    drag_release = None

    def __init__(self,
                 coordinates: Tuple[int, int] = None,
                 code: int = None,
                 drag: bool = False,
                 drag_release: bool = False):
        if coordinates:
            self.coordinates = coordinates
            self.drag = drag
            self.drag_release = drag_release
            if code:
                if code == 4:
                    self.scroll = (1, 1)
                elif code == 5:
                    self.scroll = (-1, -1)
                else:
                    self.code = code

    def get_command(self):
        if mouse_mapping.get(self.code, None):
            return mouse_mapping[self.code]
