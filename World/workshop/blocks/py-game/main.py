"""A small 2D game: move with the arrow keys, collect the yellow squares."""
import random
import sys
import tkinter as tk
# archie:imports

W, H, FPS = 640, 480, 60


class Game:
    def __init__(self, root):
        self.c = tk.Canvas(root, width=W, height=H, bg="#14161a", highlightthickness=0)
        self.c.pack()
        self.keys = set()
        root.bind("<KeyPress>", lambda e: self.keys.add(e.keysym))
        root.bind("<KeyRelease>", lambda e: self.keys.discard(e.keysym))
        self.x, self.y, self.speed = W / 2, H / 2, 4
        self.score = 0
        self.coin = self.new_coin()
        self.frames = 0

    def new_coin(self):
        return (random.randint(20, W - 20), random.randint(40, H - 20))

    def update(self):
        """Game rules: runs every frame."""
        dx = ("Right" in self.keys) - ("Left" in self.keys)
        dy = ("Down" in self.keys) - ("Up" in self.keys)
        self.x = min(W - 12, max(12, self.x + dx * self.speed))
        self.y = min(H - 12, max(12, self.y + dy * self.speed))
        if abs(self.x - self.coin[0]) < 20 and abs(self.y - self.coin[1]) < 20:   # touching the coin
            self.score += 1
            self.coin = self.new_coin()

    def draw(self):
        c = self.c
        c.delete("all")
        cx, cy = self.coin
        c.create_rectangle(cx - 8, cy - 8, cx + 8, cy + 8, fill="#f5d142", outline="")
        c.create_rectangle(self.x - 12, self.y - 12, self.x + 12, self.y + 12, fill="#c6f432", outline="")
        c.create_text(10, 10, anchor="nw", fill="white", font=("Segoe UI", 14), text="Score: %d" % self.score)

    def tick(self):
        self.update()
        self.draw()
        self.frames += 1
        self.c.after(int(1000 / FPS), self.tick)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("My Game")
    root.resizable(False, False)
    g = Game(root)
    g.tick()
    if "--selftest" in sys.argv:
        g.keys.add("Right")
        root.after(500, lambda: (print("selftest ok" if g.x > W / 2 and g.frames > 5 else "selftest FAILED"), root.destroy()))
    root.mainloop()
