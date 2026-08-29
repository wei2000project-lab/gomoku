import random
import time
from state import BOARD_SIZE, PLAYER, AI, DIRS, SHAPE_SCORE, _check_win_fast

# 置換表
transposition_table = {}

# Zobrist Hashing 隨機數表 (15 * 15 * 2，其中 2 代表 0=黑子/PLAYER-1, 1=白子/AI-1)
ZOBRIST_TABLE = [[[random.getrandbits(64) for _ in range(2)] for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

def _get_initial_hash(board):
    h = 0
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            p = board[r][c]
            if p != 0:
                h ^= ZOBRIST_TABLE[r][c][p - 1]
    return h

# 難度設定
DIFF_CONFIG = {
    'easy':   dict(sort_atk=0.7, depth=1, cand=20, time_limit=None, use_atk_precheck=False),
    'normal': dict(sort_atk=1.0, depth=3, cand=20, time_limit=2.0, use_atk_precheck=True),
    'hard':   dict(sort_atk=1.1, depth=5, cand=20, time_limit=4.0,  use_atk_precheck=False),
    'expert': dict(sort_atk=1.15,depth=7, cand=22, time_limit=4.0,  use_atk_precheck=False),
}

_deadline = None


# Convert SHAPE_SCORE to a 2D list for fast lookup
SHAPE_SCORE_TABLE = [[0] * 3 for _ in range(6)]
for (cnt, _op), _sc in SHAPE_SCORE.items():
    if cnt <= 5 and _op <= 2:
        SHAPE_SCORE_TABLE[cnt][_op] = _sc

def _line_score(board, r, c, player):
    total = 0
    for dr, dc in DIRS:
        cnt, opens = 1, 0
        for sign in (1, -1):
            nr, nc = r + dr * sign, c + dc * sign
            step = 0
            while (0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE
                   and board[nr][nc] == player and step < 4):
                cnt += 1; step += 1
                nr += dr * sign; nc += dc * sign
            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == 0:
                opens += 1
        cnt = min(cnt, 5)
        total += SHAPE_SCORE_TABLE[cnt][opens]
    return total



def _find_immediate(board, player):
    """全盤掃描找即時致勝點，不依賴候選排序"""
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] != 0:
                continue
            board[r][c] = player
            win = _check_win_fast(board, r, c, player)
            board[r][c] = 0
            if win:
                return r, c
    return None


def _count_shape(board, r, c, player, dr, dc):
    cnt, opens = 1, 0
    for sign in (1, -1):
        nr, nc = r + dr * sign, c + dc * sign
        step = 0
        while (0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE
               and board[nr][nc] == player and step < 4):
            cnt += 1; step += 1; nr += dr * sign; nc += dc * sign
        if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == 0:
            opens += 1
    if cnt >= 5:                     return 'five'
    if cnt == 4 and opens == 2:      return 'live4'
    if cnt == 4 and opens == 1:      return 'sleep4'
    if cnt == 3 and opens == 2:      return 'live3'
    if cnt == 3 and opens == 1:      return 'sleep3'
    if cnt == 2 and opens == 2:      return 'live2'
    return 'other'


def _find_multi_threat(board, player):
    """找 player 的活四 / 雙活三位置"""
    threat_pts = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] != 0:
                continue
            board[r][c] = player
            cnt_l4 = cnt_l3 = 0
            for dr, dc in DIRS:
                sh = _count_shape(board, r, c, player, dr, dc)
                if sh == 'live4':   cnt_l4 += 1
                elif sh == 'live3': cnt_l3 += 1
            sc = _line_score(board, r, c, player)
            board[r][c] = 0
            if cnt_l4 >= 1 or cnt_l3 >= 2:
                threat_pts.append((sc, r, c))
    if not threat_pts:
        return None
    threat_pts.sort(reverse=True)
    return threat_pts[0][1], threat_pts[0][2]


# 預先計算鄰近座標偏移，避免在迴圈中重複計算
RADIUS_OFFSETS = {
    1: [(dr, dc) for dr in range(-1, 2) for dc in range(-1, 2) if dr != 0 or dc != 0],
    2: [(dr, dc) for dr in range(-2, 3) for dc in range(-2, 3) if dr != 0 or dc != 0]
}

def _candidates(board, max_count=20, sort_atk=1.0,
                ai_color=AI, player_color=PLAYER, radius=2):
    """
    候選點排序：sort_atk 只影響搜尋順序（讓進攻點排前面以改善 alpha-beta 效率），
    不影響 eval，所以不會讓 AI 忘記防守。
    """
    seen = set()
    offsets = RADIUS_OFFSETS.get(radius, RADIUS_OFFSETS[2])
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c]:
                for dr, dc in offsets:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == 0:
                        seen.add((nr, nc))
    if not seen:
        seen.add((BOARD_SIZE // 2, BOARD_SIZE // 2))

    def priority(rc):
        rr, cc = rc
        # _line_score 不需要 board[rr][cc] 設值即可正確評估
        sa = _line_score(board, rr, cc, ai_color)
        sp = _line_score(board, rr, cc, player_color)
        # sort_atk 影響搜尋順序，不影響實際 eval 評分
        return sa * sort_atk + sp * 1.0

    return sorted(seen, key=priority, reverse=True)[:max_count]


def _init_eval(board, ai_color=AI, player_color=PLAYER):
    score_matrix = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    current_eval = 0
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            p = board[r][c]
            if p == ai_color:
                board[r][c] = 0
                sc = _line_score(board, r, c, ai_color)
                board[r][c] = ai_color
                score_matrix[r][c] = sc
                current_eval += sc
            elif p == player_color:
                board[r][c] = 0
                sc = _line_score(board, r, c, player_color)
                board[r][c] = player_color
                score_matrix[r][c] = sc
                current_eval -= sc
    return score_matrix, current_eval


def _make_move_incremental(board, r, c, player, score_matrix, current_eval, ai_color=AI, player_color=PLAYER):
    affected = []
    for dr, dc in DIRS:
        for step in range(-4, 5):
            if step == 0:
                continue
            nr, nc = r + step * dr, c + step * dc
            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
                p = board[nr][nc]
                if p != 0:
                    affected.append((nr, nc, p))
    
    rollback_log = []
    for ar, ac, ap in affected:
        old_score = score_matrix[ar][ac]
        rollback_log.append((ar, ac, ap, old_score))
        if ap == ai_color:
            current_eval -= old_score
        else:
            current_eval += old_score
            
    board[r][c] = player
    
    board[r][c] = 0
    new_move_score = _line_score(board, r, c, player)
    board[r][c] = player
    score_matrix[r][c] = new_move_score
    if player == ai_color:
        current_eval += new_move_score
    else:
        current_eval -= new_move_score
    rollback_log.append((r, c, 0, 0))
    
    for ar, ac, ap in affected:
        board[ar][ac] = 0
        new_score = _line_score(board, ar, ac, ap)
        board[ar][ac] = ap
        score_matrix[ar][ac] = new_score
        if ap == ai_color:
            current_eval += new_score
        else:
            current_eval -= new_score
            
    return rollback_log, current_eval


def _rollback_move_incremental(board, r, c, rollback_log, score_matrix):
    board[r][c] = 0
    for ar, ac, ap, old_score in rollback_log:
        score_matrix[ar][ac] = old_score


def _eval_board(board, ai_color=AI, player_color=PLAYER):
    """
    備用評估函數（保留原全盤掃描做為防禦性設計）
    """
    ai_s = pl_s = 0
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == ai_color:
                board[r][c] = 0
                ai_s += _line_score(board, r, c, ai_color)
                board[r][c] = ai_color
            elif board[r][c] == player_color:
                board[r][c] = 0
                pl_s += _line_score(board, r, c, player_color)
                board[r][c] = player_color
    return ai_s - pl_s   # 永遠 1:1，不偏攻不偏守


def _minimax(board, score_matrix, current_eval, current_hash, depth, maximizing, alpha, beta,
             sort_atk, cand_count, ai_color, player_color):
    global _deadline, transposition_table
    if _deadline and time.time() > _deadline:
        return current_eval

    if current_hash in transposition_table:
        cached_depth, cached_val = transposition_table[current_hash]
        if cached_depth >= depth:
            return cached_val

    cands = _candidates(board, max_count=cand_count,
                        sort_atk=sort_atk,
                        ai_color=ai_color, player_color=player_color)
    if not cands:
        return 0

    if maximizing:
        val = -(10 ** 9)
        for r, c in cands:
            saved_eval = current_eval
            log, current_eval = _make_move_incremental(board, r, c, ai_color, score_matrix, current_eval, ai_color, player_color)
            
            if _check_win_fast(board, r, c, ai_color):
                _rollback_move_incremental(board, r, c, log, score_matrix)
                return 9_000_000 + depth * 10
                
            nv = (current_eval
                  if depth <= 1 else
                  _minimax(board, score_matrix, current_eval, current_hash ^ ZOBRIST_TABLE[r][c][ai_color - 1], depth - 1, False, alpha, beta,
                           sort_atk, cand_count, ai_color, player_color))
                           
            _rollback_move_incremental(board, r, c, log, score_matrix)
            current_eval = saved_eval
            
            val = max(val, nv); alpha = max(alpha, val)
            if beta <= alpha: break
    else:
        val = 10 ** 9
        for r, c in cands:
            saved_eval = current_eval
            log, current_eval = _make_move_incremental(board, r, c, player_color, score_matrix, current_eval, ai_color, player_color)
            
            if _check_win_fast(board, r, c, player_color):
                _rollback_move_incremental(board, r, c, log, score_matrix)
                return -9_000_000 - depth * 10
                
            nv = (current_eval
                  if depth <= 1 else
                  _minimax(board, score_matrix, current_eval, current_hash ^ ZOBRIST_TABLE[r][c][player_color - 1], depth - 1, True, alpha, beta,
                           sort_atk, cand_count, ai_color, player_color))
                           
            _rollback_move_incremental(board, r, c, log, score_matrix)
            current_eval = saved_eval
            
            val = min(val, nv); beta = min(beta, val)
            if beta <= alpha: break

    if len(transposition_table) > 500000:
        transposition_table.clear()
    transposition_table[current_hash] = (depth, val)
    return val


def _ai_best_move(board, depth, sort_atk, cand_count, time_limit,
                  use_atk_precheck, ai_color, player_color):
    """
    優先順序（硬規則，不受攻守係數影響）：
      1. AI 可立刻贏
      2. 對手下一步贏 → 必堵
      3. [僅 easy/normal] AI 自己有雙重威脅 → 主動進攻
      4. 對手有雙重威脅 → 堵截
      5. Minimax（使用增量評估與 Zobrist Hashing 加速搜尋）

    hard/expert 跳過步驟 3，讓 minimax 的深度搜尋自行找進攻機會，
    確保不會因為搶進攻而錯失深層防守。
    """
    global transposition_table, _deadline

    # 1. 我能立刻贏
    m = _find_immediate(board, ai_color)
    if m: return m

    # 2. 對手即時必勝 → 堵
    m = _find_immediate(board, player_color)
    if m: return m

    # 3. AI 主動進攻（僅 easy/normal）
    if use_atk_precheck:
        m = _find_multi_threat(board, ai_color)
        if m: return m

    # 4. 對手雙重威脅 → 堵（hard/expert 也要堵，作為 minimax 的安全網）
    m = _find_multi_threat(board, player_color)
    if m: return m

    # 5. Minimax
    _deadline = (time.time() + time_limit) if time_limit else None
    
    # 初始化增量評估結構與 Zobrist Hash
    score_matrix, current_eval = _init_eval(board, ai_color, player_color)
    current_hash = _get_initial_hash(board)
    
    cands = _candidates(board, max_count=cand_count,
                        sort_atk=sort_atk,
                        ai_color=ai_color, player_color=player_color)
    if not cands:
        return BOARD_SIZE // 2, BOARD_SIZE // 2

    best_val, best_mv = -(10 ** 9), cands[0]
    alpha, beta = -(10 ** 9), 10 ** 9
    for r, c in cands:
        saved_eval = current_eval
        log, current_eval = _make_move_incremental(board, r, c, ai_color, score_matrix, current_eval, ai_color, player_color)
        
        if _check_win_fast(board, r, c, ai_color):
            _rollback_move_incremental(board, r, c, log, score_matrix)
            return r, c
            
        val = _minimax(board, score_matrix, current_eval, current_hash ^ ZOBRIST_TABLE[r][c][ai_color - 1], depth - 1, False, alpha, beta,
                       sort_atk, cand_count, ai_color, player_color)
                       
        _rollback_move_incremental(board, r, c, log, score_matrix)
        current_eval = saved_eval
        
        if val > best_val:
            best_val, best_mv = val, (r, c)
        alpha = max(alpha, val)

    return best_mv


def clear_table():
    global transposition_table
    transposition_table.clear()


def get_ai_move(board, diff, ai_color):
    """依難度呼叫對應策略"""
    cfg = DIFF_CONFIG[diff]
    player_color = PLAYER if ai_color == AI else AI

    if diff == 'easy':
        return _ai_easy(board, ai_color, player_color, cfg)
    elif diff == 'normal':
        return _ai_normal(board, ai_color, player_color, cfg)
    else:
        return _ai_best_move(
            board,
            depth=cfg['depth'],
            sort_atk=cfg['sort_atk'],
            cand_count=cfg['cand'],
            time_limit=cfg['time_limit'],
            use_atk_precheck=cfg['use_atk_precheck'],
            ai_color=ai_color,
            player_color=player_color,
        )


def _ai_easy(board, ai_color, player_color, cfg):
    """簡單：堵即時必敗/搶即時勝，其餘 40% 隨機 + 貪心"""
    m = _find_immediate(board, ai_color)
    if m: return m
    m = _find_immediate(board, player_color)
    if m: return m
    if random.random() < 0.4:
        empty = [(r, c) for r in range(BOARD_SIZE)
                 for c in range(BOARD_SIZE) if board[r][c] == 0]
        return random.choice(empty)
    cands = _candidates(board, max_count=cfg['cand'],
                        sort_atk=cfg['sort_atk'],
                        ai_color=ai_color, player_color=player_color)
    if not cands: return BOARD_SIZE // 2, BOARD_SIZE // 2
    best_s, best_mv = -1, cands[0]
    for r, c in cands:
        board[r][c] = ai_color
        sa = _line_score(board, r, c, ai_color)
        board[r][c] = player_color
        sp = _line_score(board, r, c, player_color)
        board[r][c] = 0
        s = sa * cfg['sort_atk'] + sp
        if s > best_s: best_s, best_mv = s, (r, c)
    return best_mv


def _ai_normal(board, ai_color, player_color, cfg):
    """普通：必勝必堵 + AI 主動進攻預搜 + 貪心（攻守等權）"""
    m = _find_immediate(board, ai_color)
    if m: return m
    m = _find_immediate(board, player_color)
    if m: return m
    m = _find_multi_threat(board, ai_color)     # 普通模式主動找進攻
    if m: return m
    m = _find_multi_threat(board, player_color)
    if m: return m
    cands = _candidates(board, max_count=cfg['cand'],
                        sort_atk=cfg['sort_atk'],
                        ai_color=ai_color, player_color=player_color)
    if not cands: return BOARD_SIZE // 2, BOARD_SIZE // 2
    best_s, best_mv = -1, cands[0]
    for r, c in cands:
        board[r][c] = ai_color
        sa = _line_score(board, r, c, ai_color)
        board[r][c] = player_color
        sp = _line_score(board, r, c, player_color)
        board[r][c] = 0
        s = sa + sp   # 等權
        if s > best_s: best_s, best_mv = s, (r, c)
    return best_mv
