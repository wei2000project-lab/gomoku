import tkinter as tk
import time
import threading
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import os
from datetime import datetime

try:
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False

from state import (
    BOARD_SIZE, CELL, PAD, CANVAS_W, PLAYER, AI, LANG, LANG_OPTS, DIFF_KEYS,
    BG, BOARD_CLR, LINE_CLR, STAR_CLR, BTN_DARK, BTN_TEXT, ACT_GREEN, ACT_BLUE,
    WIN_GOLD, RED_SOFT, YEL_SOFT, _check_win_cells, export_sgf, import_sgf, GameState
)
import ai


class Gomoku:
    def __init__(self, master):
        self.root   = master
        self.state  = GameState()
        self.hover_rc  = None
        self.show_move_numbers = False  # 新增：是否顯示編號
        self._ai_thinking = False       # AI 是否正在思考中
        self.t0        = time.time()

        self.root.title(self._('title'))
        self.root.configure(bg=BG)
        self.root.resizable(True, True)  # 允許調整大小
        
        # 設置最小視窗大小
        self.root.minsize(700, 750)
        
        # 綁定視窗大小改變事件
        self.root.bind('<Configure>', self._on_resize)
        
        self._build_ui()
        self._reset_board()  # 初始重置棋盤但不開始
        self.root.after(1000, self._tick)

    # ─── 屬性代理 (Property Delegation to GameState) ──────────────────────────────
    @property
    def board(self): return self.state.board
    @board.setter
    def board(self, v): self.state.board = v

    @property
    def history(self): return self.state.history
    @history.setter
    def history(self, v): self.state.history = v

    @property
    def turn(self): return self.state.turn
    @turn.setter
    def turn(self, v): self.state.turn = v

    @property
    def game_over(self): return self.state.game_over
    @game_over.setter
    def game_over(self, v): self.state.game_over = v

    @property
    def game_started(self): return self.state.game_started
    @game_started.setter
    def game_started(self, v): self.state.game_started = v

    @property
    def win_cells(self): return self.state.win_cells
    @win_cells.setter
    def win_cells(self, v): self.state.win_cells = v

    @property
    def elapsed(self): return self.state.elapsed
    @elapsed.setter
    def elapsed(self, v): self.state.elapsed = v

    @property
    def ticking(self): return self.state.ticking
    @ticking.setter
    def ticking(self, v): self.state.ticking = v

    @property
    def player_color(self): return self.state.player_color
    @player_color.setter
    def player_color(self, v): self.state.player_color = v

    @property
    def diff(self): return self.state.diff
    @diff.setter
    def diff(self, v): self.state.diff = v

    @property
    def lang(self): return self.state.lang
    @lang.setter
    def lang(self, v): self.state.lang = v

    @property
    def ai_enabled(self): return self.state.ai_enabled
    @ai_enabled.setter
    def ai_enabled(self, v): self.state.ai_enabled = v

    @property
    def _review_history(self): return self.state._review_history
    @_review_history.setter
    def _review_history(self, v): self.state._review_history = v

    @property
    def _review_step(self): return self.state._review_step
    @_review_step.setter
    def _review_step(self, v): self.state._review_step = v

    @property
    def _review_mode(self): return self.state._review_mode
    @_review_mode.setter
    def _review_mode(self, v): self.state._review_mode = v

    def _(self, key):
        return LANG[self.lang].get(key, key)

    def _build_ui(self):
        # 上方控制區
        top_bar = tk.Frame(self.root, bg=BG)
        top_bar.pack(side='top', fill='x', pady=8)

        # 語言切換
        lang_fr = tk.Frame(top_bar, bg=BG)
        lang_fr.pack(side='left', padx=18)
        self.lang_btns = {}
        for lbl, code in LANG_OPTS:
            b = tk.Button(lang_fr, text=lbl, bg=BTN_DARK, fg=BTN_TEXT,
                          relief='flat', font=('Arial', 9, 'bold'),
                          padx=8, pady=4, cursor='hand2',
                          command=lambda c=code: self._set_lang(c))
            b.pack(side='left', padx=2)
            self.lang_btns[code] = b

        # 難度選擇
        diff_fr = tk.Frame(top_bar, bg=BG)
        diff_fr.pack(side='left', padx=18)
        self.diff_lbl = tk.Label(diff_fr, text='', bg=BG, fg=BTN_TEXT,
                                 font=('Arial', 10))
        self.diff_lbl.pack(side='left', padx=8)
        self.diff_btns = {}
        for k in DIFF_KEYS:
            b = tk.Button(diff_fr, text='', bg=BTN_DARK, fg=BTN_TEXT,
                          relief='flat', font=('Arial', 9, 'bold'),
                          padx=10, pady=4, cursor='hand2',
                          command=lambda kk=k: self._set_diff(kk))
            b.pack(side='left', padx=2)
            self.diff_btns[k] = b

        # 執子顏色選擇
        color_fr = tk.Frame(top_bar, bg=BG)
        color_fr.pack(side='left', padx=18)
        self.color_lbl = tk.Label(color_fr, text='', bg=BG, fg=BTN_TEXT,
                                  font=('Arial', 10))
        self.color_lbl.pack(side='left', padx=8)
        self.color_btns = {}
        for color_val, color_key in [(PLAYER, 'black'), (AI, 'white')]:
            b = tk.Button(color_fr, text='', bg=BTN_DARK, fg=BTN_TEXT,
                          relief='flat', font=('Arial', 9, 'bold'),
                          padx=10, pady=4, cursor='hand2',
                          command=lambda cv=color_val: self._set_color(cv))
            b.pack(side='left', padx=2)
            self.color_btns[color_val] = b

        # 計時器
        timer_fr = tk.Frame(top_bar, bg=BG)
        timer_fr.pack(side='right', padx=18)
        self.timer_title_lbl = tk.Label(timer_fr, text='', bg=BG,
                                        fg=BTN_TEXT, font=('Arial', 10))
        self.timer_title_lbl.pack(side='left')
        self.timer_var = tk.StringVar(value='00:00')
        tk.Label(timer_fr, textvariable=self.timer_var, bg=BG, fg=ACT_BLUE,
                 font=('Arial', 12, 'bold')).pack(side='left')

        # 畫布容器（用於響應式布局）
        self.canvas_container = tk.Frame(self.root, bg=BG)
        self.canvas_container.pack(side='top', fill='both', expand=True)
        
        # 棋盤畫布
        self.cv = tk.Canvas(self.canvas_container, bg=BOARD_CLR,
                           width=CANVAS_W, height=CANVAS_W,
                           highlightthickness=0)
        self.cv.pack(expand=True)
        self.cv.bind('<Motion>', self._hover)
        self.cv.bind('<Leave>',  self._leave)

        # 狀態列（包含回合計數）
        status_bar = tk.Frame(self.root, bg=BG)
        status_bar.pack(side='top', fill='x', pady=5)
        
        # 回合數顯示
        self.round_var = tk.StringVar(value='')
        self.round_lbl = tk.Label(status_bar, textvariable=self.round_var,
                                  bg=BG, fg=YEL_SOFT,
                                  font=('Arial', 11, 'bold'))
        self.round_lbl.pack(side='left', padx=20)
        
        # 遊戲狀態
        self.status_var = tk.StringVar(value='')
        self.status_lbl = tk.Label(status_bar, textvariable=self.status_var,
                                   bg=BG, fg=BTN_TEXT,
                                   font=('Arial', 12, 'bold'))
        self.status_lbl.pack(side='left', expand=True)

        # 下方按鈕區
        bot_bar = tk.Frame(self.root, bg=BG)
        bot_bar.pack(side='bottom', fill='x', pady=10)
        
        # 開始遊戲按鈕（大按鈕，放在左側）
        self.start_btn = tk.Button(bot_bar, text='', bg=WIN_GOLD, fg='#1e1e2e',
                                   relief='flat', font=('Arial', 11, 'bold'),
                                   padx=30, pady=10, cursor='hand2',
                                   command=self._start_game)
        self.start_btn.pack(side='left', padx=15)
        
        # 顯示編號按鈕
        self.number_btn = tk.Button(bot_bar, text='', bg=BTN_DARK, fg=BTN_TEXT,
                                   relief='flat', font=('Arial', 10, 'bold'),
                                   padx=20, pady=8, cursor='hand2',
                                   command=self._toggle_numbers)
        self.number_btn.pack(side='left', padx=10)
        
        # 新遊戲按鈕
        self.new_btn = tk.Button(bot_bar, text='', bg=ACT_GREEN, fg='#1e1e2e',
                                relief='flat', font=('Arial', 10, 'bold'),
                                padx=22, pady=8, cursor='hand2',
                                command=self._new_game)
        self.new_btn.pack(side='left', padx=10)
        
        # 悔棋按鈕
        self.undo_btn = tk.Button(bot_bar, text='', bg=ACT_BLUE, fg='#1e1e2e',
                                 relief='flat', font=('Arial', 10, 'bold'),
                                 padx=22, pady=8, cursor='hand2',
                                 command=self._undo)
        self.undo_btn.pack(side='left', padx=10)

        # AI 開關按鈕
        self.ai_toggle_btn = tk.Button(bot_bar, text='', bg=ACT_GREEN, fg='#1e1e2e',
                                       relief='flat', font=('Arial', 10, 'bold'),
                                       padx=16, pady=8, cursor='hand2',
                                       command=self._toggle_ai)
        self.ai_toggle_btn.pack(side='left', padx=10)

        # SGF 匯出按鈕
        self.export_btn = tk.Button(bot_bar, text='', bg=BTN_DARK, fg=BTN_TEXT,
                                    relief='flat', font=('Arial', 10, 'bold'),
                                    padx=14, pady=8, cursor='hand2',
                                    command=self._export_sgf)
        self.export_btn.pack(side='left', padx=5)

        # SGF 匯入按鈕
        self.import_btn = tk.Button(bot_bar, text='', bg=BTN_DARK, fg=BTN_TEXT,
                                    relief='flat', font=('Arial', 10, 'bold'),
                                    padx=14, pady=8, cursor='hand2',
                                    command=self._import_sgf)
        self.import_btn.pack(side='left', padx=5)

        # 複盤控制列（預設隱藏）
        self.review_bar = tk.Frame(self.root, bg=BG)
        # 不 pack，等進入複盤模式才顯示
        self.review_prev_btn = tk.Button(self.review_bar, text='', bg=BTN_DARK, fg=BTN_TEXT,
                                         relief='flat', font=('Arial', 10, 'bold'),
                                         padx=16, pady=6, cursor='hand2',
                                         command=self._review_prev)
        self.review_prev_btn.pack(side='left', padx=8)
        self.review_step_var = tk.StringVar(value='')
        tk.Label(self.review_bar, textvariable=self.review_step_var,
                 bg=BG, fg=YEL_SOFT, font=('Arial', 11, 'bold')).pack(side='left', padx=12)
        self.review_next_btn = tk.Button(self.review_bar, text='', bg=BTN_DARK, fg=BTN_TEXT,
                                         relief='flat', font=('Arial', 10, 'bold'),
                                         padx=16, pady=6, cursor='hand2',
                                         command=self._review_next)
        self.review_next_btn.pack(side='left', padx=8)
        self.review_exit_btn = tk.Button(self.review_bar, text='', bg=RED_SOFT, fg='#1e1e2e',
                                         relief='flat', font=('Arial', 10, 'bold'),
                                         padx=16, pady=6, cursor='hand2',
                                         command=self._exit_review)
        self.review_exit_btn.pack(side='left', padx=16)

        # 跳手數：標籤 + 輸入框 + 確認按鈕
        self.review_jump_lbl = tk.Label(self.review_bar, text='', bg=BG, fg=BTN_TEXT,
                                        font=('Arial', 10))
        self.review_jump_lbl.pack(side='left', padx=(20, 2))
        self.review_jump_var = tk.StringVar()
        self.review_jump_entry = tk.Entry(self.review_bar, textvariable=self.review_jump_var,
                                          bg=BTN_DARK, fg=BTN_TEXT, insertbackground=BTN_TEXT,
                                          font=('Arial', 10, 'bold'), width=4,
                                          relief='flat', justify='center')
        self.review_jump_entry.pack(side='left', padx=2)
        self.review_jump_lbl2 = tk.Label(self.review_bar, text='', bg=BG, fg=BTN_TEXT,
                                         font=('Arial', 10))
        self.review_jump_lbl2.pack(side='left', padx=(0, 6))
        self.review_jump_btn = tk.Button(self.review_bar, text='→', bg=ACT_BLUE, fg='#1e1e2e',
                                         relief='flat', font=('Arial', 10, 'bold'),
                                         padx=8, pady=6, cursor='hand2',
                                         command=self._review_jump)
        self.review_jump_btn.pack(side='left', padx=4)
        self.review_jump_entry.bind('<Return>', lambda e: self._review_jump())

        # 復刻接著下按鈕
        self.review_resume_btn = tk.Button(self.review_bar, text='', bg=WIN_GOLD, fg='#1e1e2e',
                                           relief='flat', font=('Arial', 10, 'bold'),
                                           padx=14, pady=6, cursor='hand2',
                                           command=self._review_resume)
        self.review_resume_btn.pack(side='left', padx=12)
        
        self._refresh_labels()

    def _on_resize(self, event=None):
        """處理視窗大小改變，保持棋盤方形且不變形"""
        if not hasattr(self, 'cv'):
            return
        
        # 獲取容器大小
        container_width = self.canvas_container.winfo_width()
        container_height = self.canvas_container.winfo_height()
        
        # 計算正方形的最大邊長（留一些邊距）
        max_size = min(container_width, container_height) - 20
        
        if max_size > 100:  # 確保有合理的最小尺寸
            self.cv.config(width=max_size, height=max_size)
            self._draw()

    def _refresh_labels(self):
        self.root.title(self._('title'))
        self.diff_lbl.configure(text=self._('difficulty') + '：')
        self.color_lbl.configure(text=self._('your_color') + '：')
        
        # 難度按鈕
        for k, btn in self.diff_btns.items():
            active = (k == self.diff)
            # 遊戲進行中時鎖定難度選擇
            state = 'disabled' if self.game_started else 'normal'
            btn.configure(text=self._(k),
                          bg=RED_SOFT  if active else BTN_DARK,
                          fg='#1e1e2e' if active else BTN_TEXT,
                          state=state)
        
        # 執子顏色按鈕
        for color_val, btn in self.color_btns.items():
            active = (color_val == self.player_color)
            # 遊戲進行中時鎖定顏色選擇
            state = 'disabled' if self.game_started else 'normal'
            color_key = 'black' if color_val == PLAYER else 'white'
            btn.configure(text=self._(color_key),
                          bg='#45475a' if active else BTN_DARK,
                          fg='#f5c2e7' if active else BTN_TEXT,
                          state=state)
        
        # 語言按鈕
        for code, btn in self.lang_btns.items():
            active = (code == self.lang)
            btn.configure(bg='#45475a' if active else BTN_DARK,
                          fg='#f5c2e7' if active else BTN_TEXT)
        
        self.new_btn.configure(text=self._('new_game'))
        self.undo_btn.configure(text=self._('undo'))
        self.timer_title_lbl.configure(text=self._('total_time') + '  ')
        self.number_btn.configure(text=self._('show_numbers') if not self.show_move_numbers 
                                 else self._('hide_numbers'))
        self.start_btn.configure(text=self._('start_game'))
        # AI 開關按鈕
        if self.ai_enabled:
            self.ai_toggle_btn.configure(text=self._('ai_on'), bg=ACT_GREEN, fg='#1e1e2e')
        else:
            self.ai_toggle_btn.configure(text=self._('ai_off'), bg='#45475a', fg=YEL_SOFT)
        self.export_btn.configure(text=self._('export_sgf'))
        self.import_btn.configure(text=self._('import_sgf'))
        # 複盤列按鈕文字
        self.review_prev_btn.configure(text=self._('review_prev'))
        self.review_next_btn.configure(text=self._('review_next'))
        self.review_exit_btn.configure(text=self._('review_exit'))
        self.review_jump_lbl.configure(text=self._('review_jump'))
        self.review_jump_lbl2.configure(text=self._('review_jump_unit'))
        self.review_resume_btn.configure(text=self._('review_resume'))
        
        # 更新回合數
        self._update_round_display()
        
        # 更新狀態文字
        if hasattr(self, 'game_over'):
            if not self.game_started:
                self.status_var.set(self._('waiting'))
            elif not self.game_over:
                self.status_var.set(
                    self._('your_turn') if self.turn == self.player_color else self._('ai_turn'))

    def _update_round_display(self):
        """更新回合數顯示"""
        round_num = (len(self.history) + 1) // 2
        self.round_var.set(f"{self._('round')} {round_num}")

    def _reset_board(self):
        """重置棋盤但不開始遊戲"""
        ai.clear_table()
        self.state.reset()
        
        self.hover_rc  = None
        self._ai_thinking = False   # 中止舊 AI 計算結果
        self.status_lbl.configure(fg=BTN_TEXT)
        self.status_var.set(self._('waiting'))
        self._update_round_display()
        self.cv.unbind('<Button-1>')
        self._draw()

    def _start_game(self):
        """開始遊戲按鈕"""
        if self.game_started:
            return
        
        self.game_started = True
        self.t0 = time.time()
        self.ticking = True
        self._refresh_labels()  # 刷新按鈕狀態（鎖定難度和顏色選擇）
        
        # 如果 AI 開啟且玩家選擇白棋，AI 先手執黑
        if self.ai_enabled and self.player_color == AI:
            self.status_var.set(self._('ai_first'))
            self.root.after(300, self._ai_first_move)
        else:  # 玩家執黑，或者 AI 關閉時由人手動先手執黑
            self.status_var.set(self._('your_turn'))
            self.cv.bind('<Button-1>', self._click)

    def _ai_first_move(self):
        """AI 先手時的第一步"""
        # 玩家執白時，AI 用黑子（PLAYER）先下
        ai_color = PLAYER if self.player_color == AI else AI
        center = BOARD_SIZE // 2
        r, c = center, center
        self._place(r, c, ai_color)
        self._sound('place')
        self.turn = self.player_color
        self.status_var.set(self._('your_turn'))
        self._update_round_display()
        self.cv.bind('<Button-1>', self._click)

    def _new_game(self):
        """新遊戲按鈕 - 重置並允許重新設置"""
        self._reset_board()
        self._refresh_labels()

    def _set_diff(self, k):
        if not self.game_started:  # 只有未開始時才能切換
            self.diff = k
            self._refresh_labels()

    def _set_lang(self, code):
        self.lang = code
        self._refresh_labels()

    def _set_color(self, color_val):
        """設置玩家執子顏色"""
        if not self.game_started:  # 只有未開始時才能切換
            self.player_color = color_val
            self._refresh_labels()

    def _toggle_numbers(self):
        """切換顯示/隱藏落子編號"""
        self.show_move_numbers = not self.show_move_numbers
        self.number_btn.configure(text=self._('show_numbers') if not self.show_move_numbers 
                                 else self._('hide_numbers'))
        self._draw()

    def _xy(self, r, c):
        """根據當前畫布大小計算坐標"""
        canvas_size = self.cv.winfo_width()
        if canvas_size <= 1:  # 畫布還未渲染
            canvas_size = CANVAS_W
        
        # 計算實際的格子大小和邊距
        cell_size = (canvas_size - 2 * PAD) / (BOARD_SIZE - 1)
        return PAD + c * cell_size, PAD + r * cell_size

    def _draw(self):
        cv = self.cv
        cv.delete('all')
        
        canvas_size = self.cv.winfo_width()
        if canvas_size <= 1:
            canvas_size = CANVAS_W
        
        cell_size = (canvas_size - 2 * PAD) / (BOARD_SIZE - 1)
        end = PAD + (BOARD_SIZE - 1) * cell_size
        
        # 繪製棋盤線
        for i in range(BOARD_SIZE):
            x, y = PAD + i * cell_size, PAD + i * cell_size
            cv.create_line(PAD, y, end, y, fill=LINE_CLR, width=1)
            cv.create_line(x, PAD, x, end, fill=LINE_CLR, width=1)
        
        # 繪製星位
        star_size = max(3, int(cell_size / 10))
        for ri in [3, 7, 11]:
            for ci in [3, 7, 11]:
                x, y = self._xy(ri, ci)
                cv.create_oval(x-star_size, y-star_size, x+star_size, y+star_size,
                              fill=STAR_CLR, outline='')
        
        # 繪製懸停提示
        # AI 開：只在玩家回合顯示，顏色固定為玩家顏色
        # AI 關：任何回合都顯示，顏色跟著 self.turn（輪到誰就顯示誰的顏色）
        _hover_ok = (self.hover_rc and not self.game_over and self.game_started
                     and ((self.ai_enabled and self.turn == self.player_color)
                          or (not self.ai_enabled)))
        if _hover_ok:
            hr, hc = self.hover_rc
            if self.board[hr][hc] == 0:
                x, y = self._xy(hr, hc)
                rad = cell_size / 2 - 3
                hover_color = self.turn  # 跟著當前輪次顏色
                if hover_color == PLAYER:
                    hover_fill, hover_outline = '#1c1c1c', '#555555'
                else:
                    hover_fill, hover_outline = '#f4f4f4', '#aaaaaa'
                cv.create_oval(x-rad, y-rad, x+rad, y+rad,
                              fill=hover_fill, outline=hover_outline, stipple='gray50')
        
        # 繪製棋子
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                p = self.board[r][c]
                if p:
                    # 找到這顆棋子在歷史中的索引
                    move_index = None
                    if self.show_move_numbers:
                        for idx, (hr, hc, _) in enumerate(self.history):
                            if hr == r and hc == c:
                                move_index = idx + 1
                                break
                    
                    self._draw_piece(r, c, p, (r, c) in self.win_cells, 
                                   cell_size, move_index)
        
        # 標記最後一步
        if self.history:
            lr, lc, _ = self.history[-1]
            x, y = self._xy(lr, lc)
            mark_size = max(4, int(cell_size / 8))
            cv.create_rectangle(x-mark_size, y-mark_size, x+mark_size, y+mark_size,
                              outline=RED_SOFT, width=2)

    def _draw_piece(self, r, c, player, highlight=False, cell_size=CELL, move_index=None):
        x, y = self._xy(r, c)
        rad = cell_size / 2 - 3
        
        if player == PLAYER:
            fill, outline, spec = '#1c1c1c', '#000000', '#555555'
            text_color = '#ffffff'
        else:
            fill, outline, spec = '#f4f4f4', '#cccccc', '#ffffff'
            text_color = '#000000'
        
        self.cv.create_oval(x-rad, y-rad, x+rad, y+rad,
                           fill=fill,
                           outline=WIN_GOLD if highlight else outline,
                           width=3 if highlight else 1)
        
        # 繪製高光
        sr = max(rad / 3, 3)
        self.cv.create_oval(x-rad+4, y-rad+4, x-rad+4+sr, y-rad+4+sr,
                           fill=spec, outline='')
        
        # 繪製編號
        if move_index is not None:
            font_size = max(8, int(cell_size / 3.5))
            self.cv.create_text(x, y, text=str(move_index),
                              fill=text_color, font=('Arial', font_size, 'bold'))

    def _hover(self, e):
        # 複盤模式不顯示懸停
        if self._review_mode:
            return
        # AI 開時只在玩家回合顯示；AI 關時任何回合都顯示
        is_player_turn = (not self.ai_enabled) or (self.turn == self.player_color)
        if not self.game_started or not is_player_turn or self.game_over:
            if self.hover_rc:
                self.hover_rc = None
                self._draw()
            return
        
        canvas_size = self.cv.winfo_width()
        if canvas_size <= 1:
            canvas_size = CANVAS_W
        cell_size = (canvas_size - 2 * PAD) / (BOARD_SIZE - 1)
        
        c = round((e.x - PAD) / cell_size)
        r = round((e.y - PAD) / cell_size)
        pos = (r, c) if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE else None
        if pos != self.hover_rc:
            self.hover_rc = pos
            self._draw()

    def _leave(self, _):
        if self.hover_rc:
            self.hover_rc = None
            self._draw()

    def _click(self, e):
        if self.game_over or not self.game_started:
            return
        # 複盤模式不允許落子
        if self._review_mode:
            return
        # AI 開啟時只允許玩家顏色落子；AI 關閉時任何顏色都可由人下
        if self.ai_enabled and self.turn != self.player_color:
            return
        
        canvas_size = self.cv.winfo_width()
        if canvas_size <= 1:
            canvas_size = CANVAS_W
        cell_size = (canvas_size - 2 * PAD) / (BOARD_SIZE - 1)
        
        c = round((e.x - PAD) / cell_size)
        r = round((e.y - PAD) / cell_size)
        
        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == 0:
            self._place(r, c, self.turn)
            self._sound('place')
            cells = _check_win_cells(self.board, r, c, self.turn)
            if cells:
                self._end(self.turn, cells)
                return
            if self._is_full():
                self._end(0, [])
                return

            # 切換到下一方
            next_color = (AI if self.turn == PLAYER else PLAYER)
            self.turn = next_color

            if self.ai_enabled and next_color != self.player_color:
                # AI 回合
                self.status_var.set(self._('ai_turn'))
                self._update_round_display()
                self.cv.unbind('<Button-1>')
                self.root.after(60, self._ai_turn)
            else:
                # 人類回合（AI 關閉或輪到玩家）
                self.status_var.set(self._('your_turn'))
                self._update_round_display()
                self.cv.bind('<Button-1>', self._click)

    def _ai_turn(self):
        """啟動 AI 計算（Thread，避免 UI 凍結）"""
        self._ai_thinking = True
        ai_color = AI if self.player_color == PLAYER else PLAYER
        board_copy = [row[:] for row in self.board]

        def compute():
            move = self._get_ai_move(ai_color, board_copy)
            self.root.after(0, lambda: self._ai_place(move, ai_color))

        threading.Thread(target=compute, daemon=True).start()

    def _ai_place(self, move, ai_color):
        """AI 計算完畢後在主線程落子"""
        self._ai_thinking = False
        if self.game_over or not self.game_started:
            return
        r, c = move
        self._place(r, c, ai_color)
        self._sound('place')
        cells = _check_win_cells(self.board, r, c, ai_color)
        if cells:
            self._end(ai_color, cells)
            return
        if self._is_full():
            self._end(0, [])
            return
        self.turn = self.player_color
        self.status_var.set(self._('your_turn'))
        self._update_round_display()
        self.cv.bind('<Button-1>', self._click)

    def _get_ai_move(self, ai_color, board):
        """依難度呼叫對應策略（在 thread 中執行）"""
        return ai.get_ai_move(board, self.diff, ai_color)

    def _toggle_ai(self):
        """切換 AI 開/關（關閉後雙方都由人手動落子）"""
        self.ai_enabled = not self.ai_enabled
        self._refresh_labels()
        if not self.game_started or self.game_over:
            return
        ai_color = AI if self.player_color == PLAYER else PLAYER
        if not self.ai_enabled:
            # AI 被關掉：若現在輪到 AI，直接交回玩家手動操作
            if self.turn == ai_color:
                self.turn = self.player_color
                self.status_var.set(self._('your_turn'))
                self.cv.bind('<Button-1>', self._click)
            else:
                # 輪到玩家，確保點擊有綁定
                self.cv.bind('<Button-1>', self._click)
        else:
            # AI 被開回來：若現在輪到 AI，立刻觸發 AI 計算
            if self.turn == ai_color:
                self.status_var.set(self._('ai_turn'))
                self.cv.unbind('<Button-1>')
                self.root.after(60, self._ai_turn)
            else:
                self.cv.bind('<Button-1>', self._click)

    # ── SGF 匯出 ────────────────────────────────────────────────────────────────
    def _export_sgf(self):
        if not self.history:
            return
        # 判斷結果字串
        if self.game_over:
            last_player = self.history[-1][2] if self.history else 0
            if self.win_cells:
                result = 'B+' if last_player == PLAYER else 'W+'
            else:
                result = '0'
        else:
            result = '*'

        sgf_text = export_sgf(self.history, self.player_color, self.diff, result)
        path = filedialog.asksaveasfilename(
            defaultextension='.sgf',
            filetypes=[('SGF files', '*.sgf'), ('All files', '*.*')],
            initialfile=f'gomoku_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sgf',
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(sgf_text)
            messagebox.showinfo(self._('export_sgf'), self._('sgf_export_ok') + f'\n{os.path.basename(path)}')

    # ── SGF 匯入 & 複盤 ─────────────────────────────────────────────────────────
    def _import_sgf(self):
        path = filedialog.askopenfilename(
            filetypes=[('SGF files', '*.sgf'), ('All files', '*.*')]
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                sgf_text = f.read()
            history, board_size, result = import_sgf(sgf_text)
            if not history or board_size != BOARD_SIZE:
                raise ValueError('empty or wrong board size')
        except Exception:
            messagebox.showerror(self._('import_sgf'), self._('sgf_import_err'))
            return

        # 進入複盤模式
        self._review_history = history
        self._review_step = 0
        self._review_mode = True
        self._reset_board()               # 清空棋盤
        self.game_started = True          # 標記已開始（但不走棋）
        self.game_over = True             # 凍結遊戲操作
        self.cv.unbind('<Button-1>')
        self._refresh_labels()
        self._review_render()
        # 顯示複盤工具列
        self.review_bar.pack(side='bottom', fill='x', pady=4, before=self.canvas_container)
        self._refresh_review_buttons()
        messagebox.showinfo(self._('import_sgf'), self._('sgf_import_ok'))

    def _review_render(self):
        """根據 _review_step 重建棋盤並繪製"""
        self.state.review_render()
        total = len(self._review_history)
        self.review_step_var.set(
            f'{self._("review_info")}  {self._review_step} / {total}'
        )
        self.status_var.set(f'{self._("review_mode")}  {self._review_step}/{total}')
        self._draw()

    def _review_prev(self):
        if self._review_step > 0:
            self._review_step -= 1
            self._review_render()
            self._refresh_review_buttons()

    def _review_next(self):
        if self._review_step < len(self._review_history):
            self._review_step += 1
            self._review_render()
            self._refresh_review_buttons()

    def _refresh_review_buttons(self):
        total = len(self._review_history)
        self.review_prev_btn.configure(
            state='normal' if self._review_step > 0 else 'disabled')
        self.review_next_btn.configure(
            state='normal' if self._review_step < total else 'disabled')

    def _exit_review(self):
        """結束複盤，回到待機狀態"""
        self._review_mode = False
        self._review_history = []
        self._review_step = 0
        self.review_bar.pack_forget()
        self._new_game()

    def _review_jump(self):
        """跳至指定手數"""
        try:
            step = int(self.review_jump_var.get())
        except ValueError:
            return
        total = len(self._review_history)
        step = max(0, min(step, total))
        self._review_step = step
        self._review_render()
        self._refresh_review_buttons()
        self.review_jump_var.set('')

    def _review_resume(self):
        """復刻：把複盤當前局面貼到真實棋盤，讓 AI 接著下"""
        self.review_bar.pack_forget()
        self.state.review_resume()
        
        self.hover_rc     = None
        self.t0           = time.time() - self.elapsed

        next_player = self.turn
        player_color = self.player_color

        self._refresh_labels()
        self._draw()

        if next_player == player_color:
            # 輪到玩家
            self.status_var.set(self._('your_turn'))
            self.cv.bind('<Button-1>', self._click)
        else:
            # 輪到 AI
            self.status_var.set(self._('ai_turn'))
            self.cv.unbind('<Button-1>')
            self.root.after(100, self._ai_turn)

    def _place(self, r, c, player):
        self.state.place(r, c, player)
        self._draw()

    def _undo(self):
        if self.state.undo():
            self.status_lbl.configure(fg=BTN_TEXT)
            self.status_var.set(self._('your_turn'))
            self._update_round_display()
            self.cv.bind('<Button-1>', self._click)
            self._draw()

    def _end(self, winner, cells):
        self.game_over = True
        self.ticking   = False
        self.win_cells = set(map(tuple, cells))
        self.cv.unbind('<Button-1>')
        if winner == self.player_color:
            self.status_var.set(self._('you_win'))
            self.status_lbl.configure(fg=ACT_GREEN)
            self._sound('win')
        elif winner != 0:  # AI 獲勝
            self.status_var.set(self._('ai_win'))
            self.status_lbl.configure(fg=RED_SOFT)
            self._sound('lose')
        else:
            self.status_var.set(self._('draw'))
            self.status_lbl.configure(fg=YEL_SOFT)
        self._draw()

    def _is_full(self):
        return self.state.is_full()

    def _tick(self):
        if self.ticking:
            self.elapsed = int(time.time() - self.t0)
        m, s = divmod(self.elapsed, 60)
        self.timer_var.set(f'{m:02d}:{s:02d}')
        self.root.after(1000, self._tick)

    def _sound(self, kind):
        if not HAS_SOUND: return
        def _play():
            try:
                if   kind == 'place': winsound.Beep(880, 55)
                elif kind == 'win':
                    for f in [523, 659, 784, 1047]: winsound.Beep(f, 110)
                elif kind == 'lose':
                    for f in [400, 340, 280]: winsound.Beep(f, 140)
            except Exception: pass
        threading.Thread(target=_play, daemon=True).start()
