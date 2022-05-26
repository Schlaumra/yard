from tkinter import *
from tkinter import ttk
from typing import Callable, Any

from objects.inputobj import Input, Key, Mouse


class MainWindow:
    root = None
    mainframe = None
    stream_frame = None
    stream_event_handler = None
    wait_release = None
    motion_cooldown_default = 10
    motion_cooldown = None

    def __init__(self, stream_event_handler: Callable[[Input], Any]):
        self.stream_event_handler = stream_event_handler
        self.root = Tk()
        self.root.title('YARD')
        self.mainframe = ttk.Frame(self.root)
        self.mainframe.grid()
        self.stream_frame = Label(self.mainframe, bg="black")
        self.stream_frame.grid(column=0, row=0)
        self.register_events()
        self.wait_release = {}
        self.reset_motion_cooldown()

    def register_events(self):
        self.root.bind("<KeyPress>", self.handle_keyboard_press_event)
        self.root.bind("<KeyRelease>", self.handle_keyboard_release_event)
        self.stream_frame.bind("<ButtonRelease>", self.handle_mouse_click_event)
        self.stream_frame.bind("<Motion>", self.handle_mouse_move_event)
        self.stream_frame.bind("<B1-Motion>", self.drag_handler_B1)
        self.stream_frame.bind("<B1-Motion>", self.drag_handler_B1)
        self.stream_frame.bind("<B2-Motion>", self.drag_handler_B2)

    def reset_motion_cooldown(self):
        self.motion_cooldown = self.motion_cooldown_default

    def drag_handler_B1(self, event):
        if not self.motion_cooldown:
            key = Mouse(coordinates=(event.x, event.y), code=1, drag=True)
            self.stream_event_handler(key)
            self.reset_motion_cooldown()
        else:
            self.motion_cooldown -= 1
        # print("drag B1", event.x, event.y)

    def drag_handler_B2(self, event):
        if not self.motion_cooldown:
            key = Mouse(coordinates=(event.x, event.y), code=3, drag=True)
            self.stream_event_handler(key)
            self.reset_motion_cooldown()
        else:
            self.motion_cooldown -= 1
        # print("drag B2", event.x, event.y)

    def handle_keyboard_press_event(self, event):
        self.wait_release[event.keysym_num] = event.char
        key = Key(1, (event.char, event.keysym, event.keycode))
        self.stream_event_handler(key)
        # print("keyboard Press", event.char, event.keysym, event.keycode)

    def handle_keyboard_release_event(self, event):
        char = self.wait_release[event.keysym_num] or event.char
        key = Key(0, (char, event.keysym, event.keycode))
        self.stream_event_handler(key)
        # print("keyboard Release", char, event.keysym, event.keycode)

    def handle_mouse_click_event(self, event):
        key = Mouse(coordinates=(event.x, event.y), code=event.num, drag_release=True)
        self.stream_event_handler(key)
        # print("mouse click", event.num, event.x, event.y)

    def handle_mouse_move_event(self, event):
        # print("mouse move", event.x, event.y)
        if not self.motion_cooldown:
            key = Mouse(coordinates=(event.x, event.y))
            self.stream_event_handler(key)
            self.reset_motion_cooldown()
        else:
            self.motion_cooldown -= 1
        # TODO: Check if positive

    def start(self):
        self.root.mainloop()
