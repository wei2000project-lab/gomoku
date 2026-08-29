import tkinter as tk
from ui import Gomoku

def main():
    root = tk.Tk()
    app = Gomoku(root)
    root.mainloop()

if __name__ == '__main__':
    main()
