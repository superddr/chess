# -*- coding: utf-8 -*-
"""国际象棋规则引擎 + AI 搜索（与中国象棋版同架构：
迭代加深 α-β + 静态搜索 + 置换表 + 空着裁剪 + LMR + 树内重复判和 + 多核根分裂）

棋盘：长度 64 列表，index = row*8 + col。row 0 为黑方底线(第8横排)，row 7 为白方底线。
白方大写 KQRBNP，黑方小写。空格 '.'。
额外状态：ep = 可吃过路兵的目标格 index（无则 -1）。
残局工具约定：不支持王车易位；兵升变自动成后。
"""
import time

WHITE, BLACK = 1, -1
EMPTY = '.'
INF = 10 ** 8

VALUES = {'K': 20000, 'Q': 900, 'R': 500, 'B': 330, 'N': 320, 'P': 100}

N_OFF = ((-2, -1), (-2, 1), (2, -1), (2, 1), (-1, -2), (1, -2), (-1, 2), (1, 2))
K_OFF = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
B_DIRS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
R_DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def rc(i):
    return i // 8, i % 8


def idx(r, c):
    return r * 8 + c


def in_board(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def side_of(p):
    if p == EMPTY:
        return 0
    return WHITE if p.isupper() else BLACK


# ---------------- 走法生成 ----------------

def gen_pseudo(board, side, ep):
    moves = []
    for i, p in enumerate(board):
        if p == EMPTY or (p.isupper()) != (side == WHITE):
            continue
        r, c = rc(i)
        up = p.upper()
        if up == 'P':
            fwd = -1 if side == WHITE else 1
            start = 6 if side == WHITE else 1
            nr = r + fwd
            if in_board(nr, c) and board[idx(nr, c)] == EMPTY:
                moves.append((i, idx(nr, c)))
                if r == start and board[idx(nr + fwd, c)] == EMPTY:
                    moves.append((i, idx(nr + fwd, c)))
            for nc in (c - 1, c + 1):
                if not in_board(nr, nc):
                    continue
                j = idx(nr, nc)
                if side_of(board[j]) == -side or (j == ep and board[j] == EMPTY):
                    moves.append((i, j))
        elif up == 'N':
            for dr, dc in N_OFF:
                nr, nc = r + dr, c + dc
                if in_board(nr, nc) and side_of(board[idx(nr, nc)]) != side:
                    moves.append((i, idx(nr, nc)))
        elif up == 'K':
            for dr, dc in K_OFF:
                nr, nc = r + dr, c + dc
                if in_board(nr, nc) and side_of(board[idx(nr, nc)]) != side:
                    moves.append((i, idx(nr, nc)))
        else:
            dirs = B_DIRS if up == 'B' else R_DIRS if up == 'R' else B_DIRS + R_DIRS
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                while in_board(nr, nc):
                    j = idx(nr, nc)
                    t = board[j]
                    if t == EMPTY:
                        moves.append((i, j))
                    else:
                        if side_of(t) != side:
                            moves.append((i, j))
                        break
                    nr += dr
                    nc += dc
    return moves


def make(board, m, ep):
    """执行走法，返回 (undo信息, 新ep)。自动升后、吃过路兵。"""
    f, t = m
    p = board[f]
    cap = board[t]
    board[t] = p
    board[f] = EMPTY
    ecap_i, ecap_p = -1, EMPTY
    new_ep = -1
    if p == 'P':
        if t == ep and cap == EMPTY:
            ecap_i = t + 8
            ecap_p = board[ecap_i]
            board[ecap_i] = EMPTY
        if f - t == 16:
            new_ep = f - 8
        if t < 8:
            board[t] = 'Q'
    elif p == 'p':
        if t == ep and cap == EMPTY:
            ecap_i = t - 8
            ecap_p = board[ecap_i]
            board[ecap_i] = EMPTY
        if t - f == 16:
            new_ep = f + 8
        if t >= 56:
            board[t] = 'q'
    return (p, cap, ecap_i, ecap_p), new_ep


def unmake(board, m, undo):
    f, t = m
    p, cap, ecap_i, ecap_p = undo
    board[f] = p
    board[t] = cap
    if ecap_i >= 0:
        board[ecap_i] = ecap_p


def find_king(board, side):
    k = 'K' if side == WHITE else 'k'
    try:
        return board.index(k)
    except ValueError:
        return -1


def is_attacked(board, sq, aside):
    r, c = rc(sq)
    if aside == WHITE:
        pawn, knight, king, bq, rq = 'P', 'N', 'K', ('B', 'Q'), ('R', 'Q')
        pr = r + 1  # 白兵从下往上攻击
    else:
        pawn, knight, king, bq, rq = 'p', 'n', 'k', ('b', 'q'), ('r', 'q')
        pr = r - 1
    if 0 <= pr < 8:
        for nc in (c - 1, c + 1):
            if 0 <= nc < 8 and board[idx(pr, nc)] == pawn:
                return True
    for dr, dc in N_OFF:
        nr, nc = r + dr, c + dc
        if in_board(nr, nc) and board[idx(nr, nc)] == knight:
            return True
    for dr, dc in K_OFF:
        nr, nc = r + dr, c + dc
        if in_board(nr, nc) and board[idx(nr, nc)] == king:
            return True
    for dr, dc in B_DIRS:
        nr, nc = r + dr, c + dc
        while in_board(nr, nc):
            t = board[idx(nr, nc)]
            if t != EMPTY:
                if t in bq:
                    return True
                break
            nr += dr
            nc += dc
    for dr, dc in R_DIRS:
        nr, nc = r + dr, c + dc
        while in_board(nr, nc):
            t = board[idx(nr, nc)]
            if t != EMPTY:
                if t in rq:
                    return True
                break
            nr += dr
            nc += dc
    return False


def in_check(board, side):
    kp = find_king(board, side)
    if kp < 0:
        return True
    return is_attacked(board, kp, -side)


def legal_moves(board, side, ep):
    res = []
    for m in gen_pseudo(board, side, ep):
        undo, _ = make(board, m, ep)
        if not in_check(board, side):
            res.append(m)
        unmake(board, m, undo)
    return res


def has_legal_move(board, side, ep):
    for m in gen_pseudo(board, side, ep):
        undo, _ = make(board, m, ep)
        ok = not in_check(board, side)
        unmake(board, m, undo)
        if ok:
            return True
    return False


# ---------------- 局面评估 ----------------

PST_P = (0, 0, 0, 0, 0, 0, 0, 0,
         70, 70, 70, 70, 70, 70, 70, 70,
         35, 35, 45, 50, 50, 45, 35, 35,
         14, 16, 24, 32, 32, 24, 16, 14,
         6, 8, 14, 24, 24, 14, 8, 6,
         2, 4, 6, 10, 10, 6, 4, 2,
         0, 0, 0, -6, -6, 0, 0, 0,
         0, 0, 0, 0, 0, 0, 0, 0)
PST_N = (-40, -25, -15, -10, -10, -15, -25, -40,
         -25, -10, 0, 5, 5, 0, -10, -25,
         -15, 0, 10, 15, 15, 10, 0, -15,
         -10, 5, 15, 20, 20, 15, 5, -10,
         -10, 5, 15, 20, 20, 15, 5, -10,
         -15, 0, 10, 15, 15, 10, 0, -15,
         -25, -10, 0, 5, 5, 0, -10, -25,
         -40, -25, -15, -10, -10, -15, -25, -40)
PST_B = (-15, -8, -5, -3, -3, -5, -8, -15,
         -8, 2, 3, 5, 5, 3, 2, -8,
         -5, 3, 8, 10, 10, 8, 3, -5,
         -3, 5, 10, 12, 12, 10, 5, -3,
         -3, 5, 10, 12, 12, 10, 5, -3,
         -5, 3, 8, 10, 10, 8, 3, -5,
         -8, 2, 3, 5, 5, 3, 2, -8,
         -15, -8, -5, -3, -3, -5, -8, -15)
PST_R = (4, 4, 4, 6, 6, 4, 4, 4,
         12, 14, 14, 14, 14, 14, 14, 12,
         0, 2, 4, 6, 6, 4, 2, 0,
         0, 2, 4, 6, 6, 4, 2, 0,
         0, 2, 4, 6, 6, 4, 2, 0,
         0, 2, 4, 6, 6, 4, 2, 0,
         0, 2, 4, 6, 6, 4, 2, 0,
         2, 2, 4, 8, 8, 4, 2, 2)
PST_Q = (-8, -4, -2, 0, 0, -2, -4, -8,
         -4, 0, 2, 4, 4, 2, 0, -4,
         -2, 2, 4, 6, 6, 4, 2, -2,
         0, 4, 6, 8, 8, 6, 4, 0,
         0, 4, 6, 8, 8, 6, 4, 0,
         -2, 2, 4, 6, 6, 4, 2, -2,
         -4, 0, 2, 4, 4, 2, 0, -4,
         -8, -4, -2, 0, 0, -2, -4, -8)
# 残局王表：鼓励入中协助
PST_K = (-40, -25, -15, -10, -10, -15, -25, -40,
         -25, -10, 0, 8, 8, 0, -10, -25,
         -15, 0, 12, 18, 18, 12, 0, -15,
         -10, 8, 18, 24, 24, 18, 8, -10,
         -10, 8, 18, 24, 24, 18, 8, -10,
         -15, 0, 12, 18, 18, 12, 0, -15,
         -25, -10, 0, 8, 8, 0, -10, -25,
         -40, -25, -15, -10, -10, -15, -25, -40)

_PSTS = {'P': PST_P, 'N': PST_N, 'B': PST_B, 'R': PST_R, 'Q': PST_Q, 'K': PST_K}
PV = {}
for _up, _tbl in _PSTS.items():
    _mat = VALUES[_up] if _up != 'K' else 0
    PV[_up] = [_mat + _tbl[_i] for _i in range(64)]
    PV[_up.lower()] = [-(_mat + _tbl[idx(7 - _i // 8, _i % 8)]) for _i in range(64)]


def evaluate(board, side):
    s = 0
    wk = bk = -1
    wmat = bmat = 0  # 除王外子力
    for i, p in enumerate(board):
        if p == EMPTY:
            continue
        s += PV[p][i]
        if p == 'K':
            wk = i
        elif p == 'k':
            bk = i
        elif p.isupper():
            wmat += VALUES[p]
        else:
            bmat += VALUES[p.upper()]
    if wk >= 0 and bk >= 0:
        # 强侧驱王入角（KQ/KR 对孤王等基本杀法需要的梯度）
        if bmat <= 330 and wmat - bmat >= 400:
            r, c = rc(bk)
            edge = min(r, 7 - r, c, 7 - c)
            dist = abs(wk // 8 - bk // 8) + abs(wk % 8 - bk % 8)
            s += (3 - edge) * 14 + (14 - dist) * 5
        if wmat <= 330 and bmat - wmat >= 400:
            r, c = rc(wk)
            edge = min(r, 7 - r, c, 7 - c)
            dist = abs(wk // 8 - bk // 8) + abs(wk % 8 - bk % 8)
            s -= (3 - edge) * 14 + (14 - dist) * 5
    # 光王一方最好结果只是和棋
    if wmat == 0:
        s = min(s, 0)
    if bmat == 0:
        s = max(s, 0)
    return s if side == WHITE else -s


def insufficient_material(board):
    """王对王 / 王单象或单马对王 → 和棋"""
    minor = 0
    for p in board:
        if p in '.Kk':
            continue
        if p.upper() in ('B', 'N'):
            minor += 1
            if minor > 1:
                return False
        else:
            return False
    return True


# ---------------- 搜索 ----------------

class Timeout(Exception):
    pass


def _null_ok(board, side):
    pieces = 'QRBN' if side == WHITE else 'qrbn'
    return any(p in pieces for p in board)


class Searcher:
    def __init__(self, deadline, seed_path=(), histcnt=None):
        self.deadline = deadline
        self.nodes = 0
        self.tt = {}
        self.path = list(seed_path)   # [(局面串, ep, 行棋方, 是否被将)]
        self.histcnt = histcnt or {}
        # killer/history 启发：加速安静着法排序
        self.killers = [[None, None] for _ in range(128)]
        self.hist = {}

    def tick(self):
        self.nodes += 1
        if (self.nodes & 511) == 0 and time.time() > self.deadline:
            raise Timeout

    def quiesce(self, board, side, ep, alpha, beta, ply):
        self.tick()
        if ('K' if side == WHITE else 'k') not in board:
            return -(INF - ply)
        stand = evaluate(board, side)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        caps = [m for m in gen_pseudo(board, side, ep)
                if board[m[1]] != EMPTY or m[1] == ep and board[m[0]].upper() == 'P']
        caps.sort(key=lambda m: VALUES[board[m[0]].upper()] -
                  10 * VALUES[board[m[1]].upper() if board[m[1]] != EMPTY else 'P'])
        for m in caps:
            victim = board[m[1]]
            if victim in 'Kk':
                return INF - ply
            vval = VALUES[victim.upper()] if victim != EMPTY else VALUES['P']
            if stand + vval + 200 < alpha:
                continue
            undo, nep = make(board, m, ep)
            sc = -self.quiesce(board, -side, nep, -beta, -alpha, ply + 1)
            unmake(board, m, undo)
            if sc > alpha:
                alpha = sc
                if alpha >= beta:
                    break
        return alpha

    def negamax(self, board, side, ep, depth, alpha, beta, ply, can_null=True):
        self.tick()
        if ('K' if side == WHITE else 'k') not in board:
            return -(INF - ply)
        in_chk = in_check(board, side)
        bstr = ''.join(board)
        # 树内重复 = 和棋（国际象棋无长将判负，长将自然归入重复和）
        for j in range(len(self.path) - 1, -1, -1):
            if self.path[j][2] == side and self.path[j][0] == bstr and self.path[j][1] == ep:
                return 0
        if self.histcnt and self.histcnt.get(
                bstr + ('w' if side == WHITE else 'b') + str(ep), 0) >= 2:
            return 0
        if in_chk and ply < 32:
            depth += 1  # 将军延伸
        if depth <= 0:
            return self.quiesce(board, side, ep, alpha, beta, ply)
        key = (bstr, side, ep)
        hit = self.tt.get(key)
        if hit is not None and hit[0] >= depth:
            hs, hf = hit[1], hit[2]
            if hf == 0:
                return hs
            if hf == 1 and hs >= beta:
                return hs
            if hf == 2 and hs <= alpha:
                return hs
        self.path.append((bstr, ep, side, in_chk))
        try:
            return self._body(board, side, ep, depth, alpha, beta, ply, can_null, in_chk, key, hit)
        finally:
            self.path.pop()

    def _body(self, board, side, ep, depth, alpha, beta, ply, can_null, in_chk, key, hit):
        # 空着裁剪（己方只剩王兵时关闭——防 zugzwang 漏算）
        if can_null and not in_chk and depth >= 3 and beta < INF - 1000 \
                and _null_ok(board, side):
            sc = -self.negamax(board, -side, -1, depth - 3, -beta, -beta + 1, ply + 1, False)
            if sc >= beta:
                return sc
        ttm = hit[3] if hit else None
        k1, k2 = self.killers[ply] if ply < 128 else (None, None)
        hist = self.hist

        def okey(m):
            if m == ttm:
                return -10 ** 7
            v = board[m[1]]
            if v != EMPTY:
                return min(VALUES[board[m[0]].upper()] - 10 * VALUES[v.upper()], 80000)
            if m == k1:
                return 90000
            if m == k2:
                return 91000
            return 10 ** 6 - min(hist.get((board[m[0]], m[1]), 0), 800000)

        moves = gen_pseudo(board, side, ep)
        moves.sort(key=okey)
        best, bestm, a0 = -INF, None, alpha
        mi = 0
        for m in moves:
            if board[m[1]] in 'Kk':
                return INF - ply
            undo, nep = make(board, m, ep)
            quiet = undo[1] == EMPTY and undo[2] < 0   # 非吃子（含吃过路兵判定）
            if mi >= 3 and depth >= 3 and quiet and not in_chk and alpha > -INF:
                sc = -self.negamax(board, -side, nep, depth - 2, -alpha - 1, -alpha, ply + 1)
                if sc > alpha:
                    sc = -self.negamax(board, -side, nep, depth - 1, -beta, -alpha, ply + 1)
            else:
                sc = -self.negamax(board, -side, nep, depth - 1, -beta, -alpha, ply + 1)
            unmake(board, m, undo)
            mi += 1
            if sc > best:
                best, bestm = sc, m
                if best > alpha:
                    alpha = best
                    if alpha >= beta:
                        if quiet and ply < 128:   # 记录 killer / history
                            ks = self.killers[ply]
                            if ks[0] != m:
                                ks[1] = ks[0]
                                ks[0] = m
                            hk = (board[m[0]], m[1])
                            hist[hk] = hist.get(hk, 0) + depth * depth
                        break
        if bestm is None:
            best = -(INF - ply) if in_chk else 0  # 无伪着：将死 / 逼和
        elif best <= -(INF - ply - 4) and not in_chk:
            # 所有走法都丢王且当前未被将 → 可能是逼和（和棋），精确复核
            if not has_legal_move(board, side, ep):
                return 0
        flag = 1 if best >= beta else (2 if best <= a0 else 0)
        self.tt[key] = (depth, best, flag, bestm)
        return best


# ---------------- 多核并行：根节点分裂 ----------------
_POOL = None
_POOL_FAILED = False
_TT_WORKER = {}


def _get_pool():
    global _POOL, _POOL_FAILED
    if _POOL is not None or _POOL_FAILED:
        return _POOL
    try:
        import multiprocessing as mp
        n = (mp.cpu_count() or 2) - 1
        if n < 2:
            _POOL_FAILED = True
            return None
        _POOL = mp.Pool(n)
    except Exception:
        _POOL_FAILED = True
    return _POOL


def pool_workers():
    pool = _get_pool()
    return pool._processes if pool else 1


def _search_root_move(args):
    """alpha0 为根下界：明显更差的走法快速失败，节省节点"""
    board_str, side, ep, m, depth, deadline, histcnt, alpha0 = args
    if len(_TT_WORKER) > 2_000_000:
        _TT_WORKER.clear()
    board = list(board_str)
    seed = [(board_str, ep, side, in_check(board, side))]
    undo, nep = make(board, m, ep)
    S = Searcher(deadline, seed, histcnt)
    S.tt = _TT_WORKER
    try:
        return m, -S.negamax(board, -side, nep, depth - 1, -INF, -alpha0, 1)
    except Timeout:
        return m, None


def _stable_min_depth(budget):
    """提前收工的最低深度：时限越长要求算得越深"""
    if budget >= 192:
        return 13
    if budget >= 48:
        return 11
    return 9


def _search_parallel(board, allowed, side, ep, penalty, deadline, histcnt=None):
    bstr = ''.join(board)
    pool = _get_pool()
    min_d = _stable_min_depth(deadline - time.time())
    best, best_sc, reached = allowed[0], -INF, 0
    scores = {}
    stable = 0
    raw_best = -INF
    depth = 1
    while depth < 26:
        if time.time() >= deadline:
            break
        alpha0 = raw_best - 150 if depth >= 6 and raw_best > -(INF - 1000) else -INF
        args = [(bstr, side, ep, m, depth, deadline, histcnt, alpha0) for m in allowed]
        try:
            results = pool.map(_search_root_move, args)
        except Exception:
            break
        if any(sc is None for _, sc in results):
            break
        cur_raw = max(sc for _, sc in results)
        if alpha0 > -INF and cur_raw <= alpha0:
            raw_best = -INF   # 全体低于下界，本层全窗口重搜
            continue
        raw_best = cur_raw
        cur_best, cur_sc = None, -INF
        for m, sc in results:
            sc -= penalty.get(m, 0)
            scores[m] = sc
            if sc > cur_sc:
                cur_sc, cur_best = sc, m
        stable = stable + 1 if cur_best == best else 1
        best, best_sc, reached = cur_best, cur_sc, depth
        allowed.sort(key=lambda m: -scores[m])
        if abs(best_sc) > INF - 1000 and depth >= 4:
            break  # 强制杀/被杀已定
        if depth >= min_d and stable >= 3:
            second = max((s for m, s in scores.items() if m != best), default=-INF)
            if best_sc - second > 250 or stable >= 5:
                break
        depth += 1
    return best, best_sc, reached


def _search_serial(board, allowed, side, ep, penalty, deadline, histcnt=None):
    seed = [(''.join(board), ep, side, in_check(board, side))]
    S = Searcher(deadline, seed, histcnt)
    min_d = _stable_min_depth(deadline - time.time())
    scores = {m: 0 for m in allowed}
    best, best_sc, reached = allowed[0], -INF, 0
    stable = 0
    for depth in range(1, 26):
        cur_best, cur_sc = None, -INF
        try:
            for m in allowed:
                undo, nep = make(board, m, ep)
                sc = -S.negamax(board, -side, nep, depth - 1, -INF, -cur_sc, 1) - penalty.get(m, 0)
                unmake(board, m, undo)
                scores[m] = sc
                if sc > cur_sc:
                    cur_sc, cur_best = sc, m
            stable = stable + 1 if cur_best == best else 1
            best, best_sc, reached = cur_best, cur_sc, depth
            allowed.sort(key=lambda m: -scores[m])
            if abs(best_sc) > INF - 1000 and depth >= 4:
                break
            if depth >= min_d and stable >= 3:
                second = max((s for m, s in scores.items() if m != best), default=-INF)
                if best_sc - second > 250 or stable >= 5:
                    break
        except Timeout:
            break
    return best, best_sc, reached


def search_best(board, side, ep, time_limit=2.0, penalty=None, draw_moves=(), history=None):
    """迭代加深搜索最佳走法。draw_moves 构成三次重复判和，按精确 0 分处理；
    history 供树内三次重复检测。返回 (move, score, depth)。"""
    deadline = time.time() + time_limit
    moves = legal_moves(board, side, ep)
    if not moves:
        return None, -INF, 0
    board = list(board)
    penalty = penalty or {}
    histcnt = {}
    for k in (history or []):
        histcnt[k] = histcnt.get(k, 0) + 1
    draws = [m for m in moves if m in draw_moves]
    rest = [m for m in moves if m not in draw_moves]
    if not rest:
        return draws[0], 0, 1
    if len(rest) == 1 and not draws:
        return rest[0], 0, 1
    rest.sort(key=lambda m: VALUES[board[m[0]].upper()] - 10 * VALUES[board[m[1]].upper()]
              if board[m[1]] != EMPTY else 10 ** 6)
    if len(rest) <= 3:
        # 应法寥寥（如被将军只能退），按候选数缩减时限
        deadline = min(deadline, time.time() + time_limit * 0.25 * len(rest))
    if len(rest) == 1:
        seed = [(''.join(board), ep, side, in_check(board, side))]
        S = Searcher(deadline, seed, histcnt)
        best, reached = rest[0], 6
        undo, nep = make(board, rest[0], ep)
        try:
            best_sc = -S.negamax(board, -side, nep, 6, -INF, INF, 1)
        except Timeout:
            best_sc = -evaluate(board, -side)
        unmake(board, rest[0], undo)
    elif _get_pool() is not None:
        best, best_sc, reached = _search_parallel(board, rest, side, ep, penalty, deadline, histcnt)
    else:
        best, best_sc, reached = _search_serial(board, rest, side, ep, penalty, deadline, histcnt)
    if draws and best_sc < 0:
        return draws[0], 0, reached
    return best, best_sc, reached


# ---------------- 重复局面 ----------------

def key_of(board, side, ep):
    return ''.join(board) + ('w' if side == WHITE else 'b') + str(ep)


def repetition_penalties(board, side, ep, history, weight=45):
    pen = {}
    if not history:
        return pen
    for m in legal_moves(board, side, ep):
        undo, nep = make(board, m, ep)
        cnt = history.count(key_of(board, -side, nep))
        unmake(board, m, undo)
        if cnt:
            pen[m] = weight
    return pen


def draw_moves_of(board, side, ep, history):
    dm = set()
    for m in legal_moves(board, side, ep):
        undo, nep = make(board, m, ep)
        if history.count(key_of(board, -side, nep)) >= 2:
            dm.add(m)
        unmake(board, m, undo)
    return dm
