from tkinter import *
from tkinter import ttk


class MainWindow:
    root = None
    mainframe = None
    stream_frame = None

    def __init__(self):
        self.root = Tk()
        self.root.title('YARD')
        self.mainframe = ttk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid()
        self.stream_frame = Label(self.mainframe, bg="black")
        self.stream_frame.grid(column=0, row=0)

    def start(self):
        self.root.mainloop()
