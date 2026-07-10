# -*- coding: utf-8 -*-
"""中国象棋规则引擎 + AI 搜索（迭代加深 α-β 剪枝 + 静态搜索 + 置换表）

棋盘表示：长度 90 的列表，index = row*9 + col。
row 0 为黑方底线（上方），row 9 为红方底线（下方）。
红方大写字母，黑方小写：K帅 A仕 B相 N马 R车 C炮 P兵。空点 '.'。
"""
import time

RED, BLACK = 1, -1
EMPTY = '.'
INF = 10 ** 8

VALUES = {'K': 10000, 'R': 900, 'C': 450, 'N': 400, 'P': 100, 'A': 110, 'B': 110}

K_DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))
A_DIRS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
# 马：(走子行偏移, 列偏移, 马腿行偏移, 马腿列偏移)，均相对起点
N_OFF = ((-2, -1, -1, 0), (-2, 1, -1, 0), (2, -1, 1, 0), (2, 1, 1, 0),
         (-1, -2, 0, -1), (1, -2, 0, -1), (-1, 2, 0, 1), (1, 2, 0, 1))
# 相：(走子偏移, 象眼偏移)
B_OFF = ((-2, -2, -1, -1), (-2, 2, -1, 1), (2, -2, 1, -1), (2, 2, 1, 1))


def rc(i):
    return i // 9, i % 9


def idx(r, c):
    return r * 9 + c


def in_board(r, c):
    return 0 <= r < 10 and 0 <= c < 9


def in_palace(r, c, side):
    if not (3 <= c <= 5):
        return False
    return 7 <= r <= 9 if side == RED else 0 <= r <= 2


def side_of(p):
    if p == EMPTY:
        return 0
    return RED if p.isupper() else BLACK


# ---------------- 走法生成 ----------------

def gen_pseudo(board, side):
    """伪合法走法（含照面飞将吃王，用于搜索中判定王的安全）"""
    moves = []
    for i, p in enumerate(board):
        if p == EMPTY or (p.isupper()) != (side == RED):
            continue
        r, c = rc(i)
        up = p.upper()
        if up == 'K':
            for dr, dc in K_DIRS:
                nr, nc = r + dr, c + dc
                if in_palace(nr, nc, side) and side_of(board[idx(nr, nc)]) != side:
                    moves.append((i, idx(nr, nc)))
            for dr in (-1, 1):  # 飞将照面
                nr = r + dr
                while 0 <= nr <= 9:
                    t = board[idx(nr, c)]
                    if t != EMPTY:
                        if t.upper() == 'K':
                            moves.append((i, idx(nr, c)))
                        break
                    nr += dr
        elif up == 'A':
            for dr, dc in A_DIRS:
                nr, nc = r + dr, c + dc
                if in_palace(nr, nc, side) and side_of(board[idx(nr, nc)]) != side:
                    moves.append((i, idx(nr, nc)))
        elif up == 'B':
            for dr, dc, er, ec in B_OFF:
                nr, nc = r + dr, c + dc
                if not in_board(nr, nc):
                    continue
                if (side == RED and nr < 5) or (side == BLACK and nr > 4):
                    continue  # 相不过河
                if board[idx(r + er, c + ec)] != EMPTY:
                    continue  # 塞象眼
                if side_of(board[idx(nr, nc)]) != side:
                    moves.append((i, idx(nr, nc)))
        elif up == 'N':
            for dr, dc, lr, lc in N_OFF:
                nr, nc = r + dr, c + dc
                if not in_board(nr, nc):
                    continue
                if board[idx(r + lr, c + lc)] != EMPTY:
                    continue  # 蹩马腿
                if side_of(board[idx(nr, nc)]) != side:
                    moves.append((i, idx(nr, nc)))
        elif up == 'R':
            for dr, dc in K_DIRS:
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
        elif up == 'C':
            for dr, dc in K_DIRS:
                nr, nc = r + dr, c + dc
                jumped = False
                while in_board(nr, nc):
                    j = idx(nr, nc)
                    t = board[j]
                    if not jumped:
                        if t == EMPTY:
                            moves.append((i, j))
                        else:
                            jumped = True  # 炮架
                    elif t != EMPTY:
                        if side_of(t) != side:
                            moves.append((i, j))
                        break
                    nr += dr
                    nc += dc
        else:  # P
            fwd = -1 if side == RED else 1
            crossed = r <= 4 if side == RED else r >= 5
            cand = [(r + fwd, c)]
            if crossed:
                cand += [(r, c - 1), (r, c + 1)]
            for nr, nc in cand:
                if in_board(nr, nc) and side_of(board[idx(nr, nc)]) != side:
                    moves.append((i, idx(nr, nc)))
    return moves


def make(board, m):
    f, t = m
    cap = board[t]
    board[t] = board[f]
    board[f] = EMPTY
    return cap


def unmake(board, m, cap):
    f, t = m
    board[f] = board[t]
    board[t] = cap


def find_king(board, side):
    k = 'K' if side == RED else 'k'
    try:
        return board.index(k)
    except ValueError:
        return -1


def is_attacked(board, sq, aside):
    """sq 是否被 aside 方攻击（含王照面：同列首个子为对方王）"""
    r, c = rc(sq)
    if aside == RED:
        rook, cannon, knight, king = 'R', 'C', 'N', 'K'
        if r + 1 <= 9 and board[idx(r + 1, c)] == 'P':
            return True
        if r <= 4:  # 过河红兵可横吃
            for nc in (c - 1, c + 1):
                if 0 <= nc < 9 and board[idx(r, nc)] == 'P':
                    return True
    else:
        rook, cannon, knight, king = 'r', 'c', 'n', 'k'
        if r - 1 >= 0 and board[idx(r - 1, c)] == 'p':
            return True
        if r >= 5:
            for nc in (c - 1, c + 1):
                if 0 <= nc < 9 and board[idx(r, nc)] == 'p':
                    return True
    for dr, dc, _, _ in N_OFF:
        nr, nc = r + dr, c + dc
        if not in_board(nr, nc) or board[idx(nr, nc)] != knight:
            continue
        if abs(dr) == 2:
            lr, lc = r + dr + (-dr) // 2, c + dc
        else:
            lr, lc = r + dr, c + dc + (-dc) // 2
        if board[idx(lr, lc)] == EMPTY:
            return True
    for dr, dc in K_DIRS:
        nr, nc = r + dr, c + dc
        blocked = False
        while in_board(nr, nc):
            t = board[idx(nr, nc)]
            if t != EMPTY:
                if not blocked:
                    if t == rook:
                        return True
                    if t == king and dc == 0:
                        return True  # 王照面
                    blocked = True
                else:
                    if t == cannon:
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


def legal_moves(board, side):
    res = []
    for m in gen_pseudo(board, side):
        cap = make(board, m)
        if not in_check(board, side):
            res.append(m)
        unmake(board, m, cap)
    return res


# ---------------- 局面评估 ----------------

def _pv(up, r, c):
    """红方视角的子力+位置分（r=9 为红方底线）"""
    v = VALUES[up]
    if up == 'P':
        if r <= 4:  # 过河兵
            v += 40 + (4 - r) * 12
            if 3 <= c <= 5 and r <= 3:
                v += 15
            if r == 0:
                v -= 20  # 老兵
    elif up == 'R':
        if 3 <= c <= 5:
            v += 8
    elif up == 'C':
        if c == 4:
            v += 12
    elif up == 'N':
        v += (9 - r) * 2
        if c in (0, 8):
            v -= 12
    return v


PV = {}
for _up in VALUES:
    PV[_up] = [0] * 90
    PV[_up.lower()] = [0] * 90
    for _i in range(90):
        _r, _c = rc(_i)
        PV[_up][_i] = _pv(_up, _r, _c)
        PV[_up.lower()][_i] = -_pv(_up, 9 - _r, _c)


# 进攻梯度权重：距对方将越近分越高（炮喜远射，不参与）
_PROX_W = {'R': 3, 'N': 4, 'P': 5}


def evaluate(board, side):
    s = 0
    rk = bk = -1
    red_att = []
    blk_att = []
    for i, p in enumerate(board):
        if p == EMPTY:
            continue
        s += PV[p][i]
        if p == 'K':
            rk = i
        elif p == 'k':
            bk = i
        elif p in 'RNCP':
            red_att.append((i, p))
        elif p in 'rncp':
            blk_att.append((i, p))
    if rk >= 0 and bk >= 0:
        bkr, bkc = divmod(bk, 9)
        rkr, rkc = divmod(rk, 9)
        for i, p in red_att:
            w = _PROX_W.get(p)
            if w:
                r, c = divmod(i, 9)
                s += max(0, 10 - abs(r - bkr) - abs(c - bkc)) * w
        for i, p in blk_att:
            w = _PROX_W.get(p.upper())
            if w:
                r, c = divmod(i, 9)
                s -= max(0, 10 - abs(r - rkr) - abs(c - rkc)) * w
    # 没有进攻子力的一方最好结果只是和棋：评分封顶为 0。
    # 这让 AI 不会换掉自己最后的攻击子，也懂得守方拼光对方攻击子即成和。
    if not red_att:
        s = min(s, 0)
    if not blk_att:
        s = max(s, 0)
    return s if side == RED else -s


# ---------------- 搜索 ----------------

class Timeout(Exception):
    pass


class Searcher:
    def __init__(self, deadline, seed_path=(), histcnt=None):
        self.deadline = deadline
        self.nodes = 0
        self.tt = {}
        # 搜索路径：[(局面串, 行棋方, 该方是否被将军)]，用于树内长将/循环检测
        self.path = list(seed_path)
        # 对局历史局面计数：用于树内三次重复判和
        self.histcnt = histcnt or {}
        # killer/history 启发：加速安静着法排序，减少节点
        self.killers = [[None, None] for _ in range(128)]
        self.hist = {}

    def tick(self):
        self.nodes += 1
        if (self.nodes & 511) == 0 and time.time() > self.deadline:
            raise Timeout

    def quiesce(self, board, side, alpha, beta, ply):
        self.tick()
        if ('K' if side == RED else 'k') not in board:
            return -(INF - ply)
        stand = evaluate(board, side)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        caps = [m for m in gen_pseudo(board, side) if board[m[1]] != EMPTY]
        caps.sort(key=lambda m: VALUES[board[m[0]].upper()] - 10 * VALUES[board[m[1]].upper()])
        for m in caps:
            victim = board[m[1]]
            if victim in 'Kk':
                return INF - ply
            if stand + VALUES[victim.upper()] + 200 < alpha:
                continue  # delta 剪枝
            cap = make(board, m)
            sc = -self.quiesce(board, -side, -beta, -alpha, ply + 1)
            unmake(board, m, cap)
            if sc > alpha:
                alpha = sc
                if alpha >= beta:
                    break
        return alpha

    def negamax(self, board, side, depth, alpha, beta, ply, can_null=True):
        self.tick()
        if ('K' if side == RED else 'k') not in board:
            return -(INF - ply)
        in_chk = in_check(board, side)
        bstr = ''.join(board)
        # —— 树内重复检测：让搜索理解"长将判负 / 循环判和"规则 ——
        for j in range(len(self.path) - 1, -1, -1):
            if self.path[j][1] == side and self.path[j][0] == bstr:
                cycle = self.path[j:]
                i_kept_checking = all(e[2] for e in cycle if e[1] == -side)
                they_kept_checking = in_chk and all(e[2] for e in cycle if e[1] == side)
                if i_kept_checking and not they_kept_checking:
                    return -(INF - ply)      # 我方长将 → 我方判负
                if they_kept_checking and not i_kept_checking:
                    return INF - ply         # 对方长将 → 对方判负
                return 0                     # 双方不变 → 和
        # 与真实对局历史构成三次重复：按裁决规则计分——
        # 长将方判负；双方均无长将才是和棋
        if self.histcnt and self.histcnt.get(bstr + ('r' if side == RED else 'b'), 0) >= 2:
            mine_all = in_chk and all(e[2] for e in self.path if e[1] == side)
            theirs_all = any(e[1] == -side for e in self.path) and \
                all(e[2] for e in self.path if e[1] == -side)
            if mine_all and not theirs_all:
                return INF - ply       # 对方一路长将逼出的重复 → 对方判负
            if theirs_all and not mine_all:
                return -(INF - ply)    # 我方一路长将 → 我方判负
            return 0
        if in_chk and ply < 32:
            depth += 1  # 将军延伸
        if depth <= 0:
            return self.quiesce(board, side, alpha, beta, ply)
        key = (bstr, side)
        hit = self.tt.get(key)
        if hit is not None and hit[0] >= depth:
            hs, hf = hit[1], hit[2]
            if hf == 0:
                return hs
            if hf == 1 and hs >= beta:
                return hs
            if hf == 2 and hs <= alpha:
                return hs
        self.path.append((bstr, side, in_chk))
        try:
            return self._negamax_body(board, side, depth, alpha, beta, ply,
                                      can_null, in_chk, key, hit)
        finally:
            self.path.pop()

    def _negamax_body(self, board, side, depth, alpha, beta, ply, can_null, in_chk, key, hit):
        # 空着裁剪：让对方连走两步仍打不穿 beta 则直接剪枝。
        # 被将军、浅深度、无攻击子（易困毙/无杀力）时不用，防止漏算。
        if can_null and not in_chk and depth >= 3 and beta < INF - 1000 \
                and has_attacker(board, side):
            sc = -self.negamax(board, -side, depth - 3, -beta, -beta + 1, ply + 1, False)
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

        moves = gen_pseudo(board, side)
        moves.sort(key=okey)
        best, bestm, a0 = -INF, None, alpha
        mi = 0
        for m in moves:
            if board[m[1]] in 'Kk':
                return INF - ply
            cap = make(board, m)
            # LMR：排序靠后的安静着法先用缩减深度零窗试探，超过 alpha 再全深度重搜
            if mi >= 3 and depth >= 3 and cap == EMPTY and not in_chk and alpha > -INF:
                sc = -self.negamax(board, -side, depth - 2, -alpha - 1, -alpha, ply + 1)
                if sc > alpha:
                    sc = -self.negamax(board, -side, depth - 1, -beta, -alpha, ply + 1)
            else:
                sc = -self.negamax(board, -side, depth - 1, -beta, -alpha, ply + 1)
            unmake(board, m, cap)
            mi += 1
            if sc > best:
                best, bestm = sc, m
                if best > alpha:
                    alpha = best
                    if alpha >= beta:
                        if cap == EMPTY and ply < 128:   # 记录 killer / history
                            ks = self.killers[ply]
                            if ks[0] != m:
                                ks[1] = ks[0]
                                ks[0] = m
                            hk = (board[m[0]], m[1])
                            hist[hk] = hist.get(hk, 0) + depth * depth
                        break
        if bestm is None:
            return -(INF - ply)
        flag = 1 if best >= beta else (2 if best <= a0 else 0)
        self.tt[key] = (depth, best, flag, bestm)
        return best


# ---------------- 多核并行：根节点分裂 ----------------
_POOL = None
_POOL_FAILED = False
_TT_WORKER = {}  # 每个 worker 进程自己的持久置换表


def _get_pool():
    """惰性创建进程池（CPU核数-1 个 worker）；失败或核数太少则回退单进程。"""
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
    """worker 进程：对单个根走法搜索。alpha0 为根下界（上一层最佳分-余量），
    明显更差的走法会快速失败返回上界，节省大量节点。超时返回 None 分数。"""
    board_str, side, m, depth, deadline, histcnt, alpha0 = args
    if len(_TT_WORKER) > 2_000_000:
        _TT_WORKER.clear()
    board = list(board_str)
    seed = [(board_str, side, in_check(board, side))]
    make(board, m)
    S = Searcher(deadline, seed, histcnt)
    S.tt = _TT_WORKER
    try:
        return m, -S.negamax(board, -side, depth - 1, -INF, -alpha0, 1)
    except Timeout:
        return m, None


def _stable_min_depth(budget):
    """提前收工的最低深度：时限越长要求算得越深，保留"长考=更深"的意义"""
    if budget >= 192:
        return 13
    if budget >= 48:
        return 11
    return 9


def _search_parallel(board, allowed, side, penalty, deadline, histcnt=None):
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
        # 根下界：明显低于上一层最佳分的走法快速失败（浅层不启用）
        alpha0 = raw_best - 150 if depth >= 6 and raw_best > -(INF - 1000) else -INF
        args = [(bstr, side, m, depth, deadline, histcnt, alpha0) for m in allowed]
        try:
            results = pool.map(_search_root_move, args)
        except Exception:
            break
        if any(sc is None for _, sc in results):
            break  # 该层未搜完，采用上一层结果
        cur_raw = max(sc for _, sc in results)
        if alpha0 > -INF and cur_raw <= alpha0:
            raw_best = -INF   # 全体低于下界（局势突变），本层全窗口重搜
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
        # 提前收工：强制杀/被杀已定，再想无益
        if abs(best_sc) > INF - 1000 and depth >= 4:
            break
        # 提前收工：最佳走法连续3层不变且明显领先，或连续5层雷打不动
        if depth >= min_d and stable >= 3:
            second = max((s for m, s in scores.items() if m != best), default=-INF)
            if best_sc - second > 250 or stable >= 5:
                break
        depth += 1
    return best, best_sc, reached, scores


def _search_serial(board, allowed, side, penalty, deadline, histcnt=None):
    seed = [(''.join(board), side, in_check(board, side))]
    S = Searcher(deadline, seed, histcnt)
    min_d = _stable_min_depth(deadline - time.time())
    scores = {m: 0 for m in allowed}
    best, best_sc, reached = allowed[0], -INF, 0
    stable = 0
    for depth in range(1, 26):
        cur_best, cur_sc = None, -INF
        try:
            for m in allowed:
                cap = make(board, m)
                # 注意窗口用扣分后的 cur_sc 仍然安全：扣分只会让走法更差
                sc = -S.negamax(board, -side, depth - 1, -INF, -cur_sc, 1) - penalty.get(m, 0)
                unmake(board, m, cap)
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
        except Timeout:
            break
    return best, best_sc, reached, scores


def search_best(board, side, time_limit=2.0, banned=(), penalty=None, draw_moves=(),
                history=None, out=None):
    """迭代加深搜索最佳走法。banned 中的走法（如长将）尽量不走；
    penalty 为 {走法: 扣分}，用于轻度惩罚首次重复局面的走法；
    draw_moves 中的走法会构成三次重复直接判和，其分值精确为 0：
    劣势时主动求和，优势时自然回避。
    history 为对局历史局面 key 列表，搜索树内部据此理解
    "长将判负 / 三次重复判和"规则。
    多核机器上自动用进程池并行搜索各根走法。
    返回 (move, score, depth)。无棋可走返回 (None, -INF, 0)。"""
    deadline = time.time() + time_limit
    moves = legal_moves(board, side)
    if not moves:
        return None, -INF, 0
    # 搜索超时会在 make/unmake 之间抛出异常，因此在副本上搜索，避免污染调用方棋盘
    board = list(board)
    penalty = penalty or {}
    histcnt = {}
    for k in (history or []):
        histcnt[k] = histcnt.get(k, 0) + 1
    allowed = [m for m in moves if m not in banned] or moves
    draws = [m for m in allowed if m in draw_moves]
    rest = [m for m in allowed if m not in draw_moves]
    if not rest:
        if out is not None:
            out.update({'scores': [], 'note': '只剩判和走法'})
        return draws[0], 0, 1
    if len(rest) == 1 and not draws:
        if out is not None:
            out.update({'scores': [[list(rest[0]), None]], 'note': '唯一应法'})
        return rest[0], 0, 1
    rest.sort(key=lambda m: VALUES[board[m[0]].upper()] - 10 * VALUES[board[m[1]].upper()]
              if board[m[1]] != EMPTY else 10 ** 6)
    if len(rest) <= 3:
        # 应法寥寥（如被将军只能退），按候选数缩减时限，不必想满
        deadline = min(deadline, time.time() + time_limit * 0.25 * len(rest))
    if len(rest) == 1:
        seed = [(''.join(board), side, in_check(board, side))]
        S = Searcher(deadline, seed, histcnt)
        best, reached = rest[0], 6
        cap = make(board, rest[0])
        try:
            best_sc = -S.negamax(board, -side, 6, -INF, INF, 1)
        except Timeout:
            best_sc = -evaluate(board, -side)
        unmake(board, rest[0], cap)
        scores_map = {rest[0]: best_sc}
    elif _get_pool() is not None:
        best, best_sc, reached, scores_map = _search_parallel(
            board, rest, side, penalty, deadline, histcnt)
    else:
        best, best_sc, reached, scores_map = _search_serial(
            board, rest, side, penalty, deadline, histcnt)
    if out is not None:
        out['scores'] = sorted(([list(m), s] for m, s in scores_map.items()),
                               key=lambda x: -(x[1] if x[1] is not None else -INF))
        out['banned'] = [list(m) for m in (set(moves) - set(allowed))]
        out['draws'] = [list(m) for m in draws]
        out['depth'] = reached
    # 有判和走法可选时：若最佳走法仍是负分（劣势），主动选择和棋
    if draws and best_sc < 0:
        if out is not None:
            out['note'] = '劣势主动求和'
        return draws[0], 0, reached
    return best, best_sc, reached


# ---------------- 长将（反复将军）判定 ----------------

def key_of(board, side_to_move):
    return ''.join(board) + ('r' if side_to_move == RED else 'b')


def perpetual_banned(board, side, history):
    """返回会构成长将的走法集合：走后将军对方，且该局面在历史中已出现 >= 2 次。"""
    banned = set()
    for m in legal_moves(board, side):
        cap = make(board, m)
        if in_check(board, -side):
            if history.count(key_of(board, -side)) >= 2:
                banned.add(m)
        unmake(board, m, cap)
    return banned


def repetition_penalties(board, side, history, weight=45):
    """对重现历史局面的走法轻度扣分：仅在近似等价的选择间引导走新变化，
    绝不该大到让 AI 为避重复而接受实质亏损（对方发起的重复，跟着回头是正当应法）。
    三次重复由 draw_moves 机制精确按和棋(0分)处理，不在此列。"""
    pen = {}
    if not history:
        return pen
    for m in legal_moves(board, side):
        cap = make(board, m)
        cnt = history.count(key_of(board, -side))
        unmake(board, m, cap)
        if cnt:
            pen[m] = weight
    return pen


def draw_moves_of(board, side, history, min_count=2):
    """返回会使局面在历史中出现次数达到 min_count+1 的走法集合。
    min_count=2 即"第三次出现"（判和裁决点）；min_count=1 可用来
    找出所有"走回头路"的走法。"""
    dm = set()
    for m in legal_moves(board, side):
        cap = make(board, m)
        if history.count(key_of(board, -side)) >= min_count:
            dm.add(m)
        unmake(board, m, cap)
    return dm


def has_attacker(board, side):
    pieces = 'RNCP' if side == RED else 'rncp'
    return any(p in pieces for p in board)
