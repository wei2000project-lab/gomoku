import re
import os
from datetime import datetime

# ─── 常數 ─────────────────────────────────────────────────────────────────────
BOARD_SIZE = 15
CELL       = 40
PAD        = 38
CANVAS_W   = CELL * (BOARD_SIZE - 1) + PAD * 2

PLAYER = 1
AI     = 2

# ─── 多語言 ───────────────────────────────────────────────────────────────────
LANG = {
    'zh_tw': dict(
        title='五子棋', difficulty='難度', easy='簡單', normal='普通',
        hard='困難', expert='專家', new_game='新遊戲', undo='悔棋',
        total_time='總時間', your_turn='⚫ 你的回合', ai_turn='⚪ AI 思考中…',
        you_win='🎉 你贏了！', ai_win='😢 AI 獲勝！', draw='🤝 平局！',
        show_numbers='顯示編號', hide_numbers='隱藏編號', round='回合',
        your_color='執子', black='執黑', white='執白',
        start_game='開始遊戲', waiting='請按開始遊戲', ai_first='AI 先手中…',
        ai_on='AI：開', ai_off='AI：關',
        export_sgf='匯出 SGF', import_sgf='匯入 SGF',
        sgf_export_ok='棋譜已匯出', sgf_import_ok='棋譜已匯入，可開始複盤',
        sgf_import_err='SGF 格式錯誤，無法匯入',
        review_mode='複盤模式', review_prev='◀ 上一手', review_next='▶ 下一手',
        review_exit='結束複盤', review_info='複盤',
        review_jump='跳至第', review_jump_unit='手',
        review_resume='復刻接著下',
    ),
    'zh_cn': dict(
        title='五子棋', difficulty='难度', easy='简单', normal='普通',
        hard='困难', expert='专家', new_game='新游戏', undo='悔棋',
        total_time='总时间', your_turn='⚫ 你的回合', ai_turn='⚪ AI 思考中…',
        you_win='🎉 你赢了！', ai_win='😢 AI 获胜！', draw='🤝 平局！',
        show_numbers='显示编号', hide_numbers='隐藏编号', round='回合',
        your_color='执子', black='执黑', white='执白',
        start_game='开始游戏', waiting='请按开始游戏', ai_first='AI 先手中…',
        ai_on='AI：开', ai_off='AI：关',
        export_sgf='导出 SGF', import_sgf='导入 SGF',
        sgf_export_ok='棋谱已导出', sgf_import_ok='棋谱已导入，可开始复盘',
        sgf_import_err='SGF 格式错误，无法导入',
        review_mode='复盘模式', review_prev='◀ 上一手', review_next='▶ 下一手',
        review_exit='结束复盘', review_info='复盘',
        review_jump='跳至第', review_jump_unit='手',
        review_resume='复刻接着下',
    ),
    'en': dict(
        title='Gomoku', difficulty='Level', easy='Easy', normal='Normal',
        hard='Hard', expert='Expert', new_game='New Game', undo='Undo',
        total_time='Time', your_turn='⚫ Your Turn', ai_turn='⚪ AI Thinking…',
        you_win='🎉 You Win!', ai_win='😢 AI Wins!', draw='🤝 Draw!',
        show_numbers='Show Numbers', hide_numbers='Hide Numbers', round='Round',
        your_color='Color', black='Black', white='White',
        start_game='Start Game', waiting='Press Start to Begin', ai_first='AI First Move…',
        ai_on='AI: ON', ai_off='AI: OFF',
        export_sgf='Export SGF', import_sgf='Import SGF',
        sgf_export_ok='Game exported', sgf_import_ok='Game imported, ready to review',
        sgf_import_err='Invalid SGF format',
        review_mode='Review Mode', review_prev='◀ Prev', review_next='▶ Next',
        review_exit='Exit Review', review_info='Review',
        review_jump='Jump to move', review_jump_unit='',
        review_resume='Resume with AI',
    ),
}

DIFF_KEYS = ['easy', 'normal', 'hard', 'expert']
LANG_OPTS = [('繁中', 'zh_tw'), ('简中', 'zh_cn'), ('EN', 'en')]

BG        = '#1e1e2e'
BOARD_CLR = '#c8a45e'
LINE_CLR  = '#7a5c10'
STAR_CLR  = '#6b4f0e'
BTN_DARK  = '#313244'
BTN_TEXT  = '#cdd6f4'
ACT_GREEN = '#a6e3a1'
ACT_BLUE  = '#89b4fa'
WIN_GOLD  = '#f1fa8c'
RED_SOFT  = '#f38ba8'
YEL_SOFT  = '#f9e2af'

DIRS = [(0, 1), (1, 0), (1, 1), (1, -1)]

# ─── 棋型評分 ─────────────────────────────────────────────────────────────────
SHAPE_SCORE = {
    (5, 0): 10_000_000, (5, 1): 10_000_000, (5, 2): 10_000_000,
    (4, 2):    500_000,
    (4, 1):     50_000,
    (3, 2):     10_000,
    (3, 1):      1_000,
    (2, 2):        200,
    (2, 1):         20,
    (1, 2):          5,
    (1, 1):          1,
}

def _check_win_fast(board, r, c, player):
    for dr, dc in DIRS:
        cnt = 1
        for sign in (1, -1):
            nr, nc = r + dr * sign, c + dc * sign
            while (0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE
                   and board[nr][nc] == player):
                cnt += 1; nr += dr * sign; nc += dc * sign
        if cnt >= 5:
            return True
    return False


def _check_win_cells(board, r, c, player):
    for dr, dc in DIRS:
        cells = [(r, c)]
        for sign in (1, -1):
            nr, nc = r + dr * sign, c + dc * sign
            while (0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE
                   and board[nr][nc] == player):
                cells.append((nr, nc)); nr += dr * sign; nc += dc * sign
        if len(cells) >= 5:
            return cells
    return []


def _coord_to_sgf(r, c):
    """(row, col) → SGF 座標字母，例如 (0,0)→'aa'"""
    return chr(ord('a') + c) + chr(ord('a') + r)


def _sgf_to_coord(s):
    """SGF 座標 'xy' → (row, col)"""
    c = ord(s[0]) - ord('a')
    r = ord(s[1]) - ord('a')
    return r, c


def export_sgf(history, player_color, diff, result=''):
    """
    將 history [(r, c, player), ...] 匯出為 SGF 字串。
    player_color=1 代表玩家執黑(PLAYER=1)，history 第一手為黑。
    """
    date_str = datetime.now().strftime('%Y-%m-%d')
    black_name = f'Player (diff={diff})' if player_color == PLAYER else f'AI (diff={diff})'
    white_name = f'AI (diff={diff})' if player_color == PLAYER else f'Player (diff={diff})'

    header = (
        f'(;GM[4]FF[4]CA[UTF-8]'
        f'SZ[{BOARD_SIZE}]'
        f'DT[{date_str}]'
        f'PB[{black_name}]'
        f'PW[{white_name}]'
        f'RE[{result}]'
        f'KM[0]'
    )
    moves = ''
    for r, c, player in history:
        tag = 'B' if player == PLAYER else 'W'
        moves += f';{tag}[{_coord_to_sgf(r, c)}]'

    return header + moves + ')'


def import_sgf(sgf_text):
    """
    解析 SGF 字串，回傳 (history, board_size, result)。
    history = [(r, c, player), ...]  player: 1=黑 2=白
    """
    sz_match = re.search(r'SZ\[(\d+)\]', sgf_text)
    board_size = int(sz_match.group(1)) if sz_match else 15

    re_match = re.search(r'RE\[([^\]]*)\]', sgf_text)
    result = re_match.group(1) if re_match else ''

    history = []
    for m in re.finditer(r';([BW])\[([a-z]{2})\]', sgf_text):
        tag, coord = m.group(1), m.group(2)
        player = PLAYER if tag == 'B' else AI
        r, c = _sgf_to_coord(coord)
        if 0 <= r < board_size and 0 <= c < board_size:
            history.append((r, c, player))

    return history, board_size, result


class GameState:
    def __init__(self):
        self.lang   = 'zh_tw'
        self.diff   = 'normal'
        self.player_color = PLAYER  # 玩家執子顏色（1=黑，2=白）
        self.game_started = False   # 遊戲是否已開始
        self.board  = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.history = []
        self.turn   = PLAYER
        self.game_over = False
        self.win_cells = set()
        self.elapsed   = 0
        self.ticking   = False  # 初始不計時
        self.ai_enabled = True          # AI 開關
        
        # 複盤狀態
        self._review_history = []       # 匯入的完整棋譜
        self._review_step = 0           # 當前複盤步數
        self._review_mode = False       # 是否在複盤模式

    def reset(self):
        self.board     = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.history   = []
        self.turn      = PLAYER  # 黑子先行
        self.game_over = False
        self.game_started = False
        self.win_cells = set()
        self.elapsed   = 0
        self.ticking   = False
        
    def place(self, r, c, player):
        self.board[r][c] = player
        self.history.append((r, c, player))

    def undo(self):
        if self.game_over or len(self.history) < 2:
            return False
        for _ in range(2):
            if self.history:
                r, c, _ = self.history.pop()
                self.board[r][c] = 0
        self.turn      = self.player_color
        self.game_over = False
        self.win_cells = set()
        return True

    def is_full(self):
        return all(self.board[r][c]
                   for r in range(BOARD_SIZE) for c in range(BOARD_SIZE))

    def review_render(self):
        self.board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.history = []
        for i in range(self._review_step):
            r, c, player = self._review_history[i]
            self.board[r][c] = player
            self.history.append((r, c, player))

    def review_resume(self):
        resume_history = list(self._review_history[:self._review_step])
        resume_board   = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        for r, c, player in resume_history:
            resume_board[r][c] = player

        self._review_mode = False
        self._review_history = []
        self._review_step = 0

        self.board        = resume_board
        self.history      = resume_history
        self.game_over    = False
        self.win_cells    = set()
        self.game_started = True
        self.ai_enabled   = True
        self.ticking      = True
        self.turn         = PLAYER if len(resume_history) % 2 == 0 else AI
