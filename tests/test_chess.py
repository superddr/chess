# -*- coding: utf-8 -*-
"""国际象棋引擎测试"""
import sys, time
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "international"))
import engine as E

def B(*rows):
    assert len(rows) == 8 and all(len(r) == 8 for r in rows)
    return list(''.join(rows))

def perft(board, side, ep, depth):
    if depth == 0:
        return 1
    n = 0
    for m in E.legal_moves(board, side, ep):
        undo, nep = E.make(board, m, ep)
        n += perft(board, -side, nep, depth - 1)
        E.unmake(board, m, undo)
    return n

def main():
    start = B('rnbqkbnr', 'pppppppp', '........', '........',
              '........', '........', 'PPPPPPPP', 'RNBQKBNR')
    # 标准 perft（无王车易位影响前两层: d1=20, d2=400, d3=8902）
    for d, expect in ((1, 20), (2, 400), (3, 8902)):
        n = perft(start[:], E.WHITE, -1, d)
        print('[perft%d] %d expect %d' % (d, n, expect), 'OK' if n == expect else 'FAIL')

    # 后翼底线杀 mate in 1: 白 Ra1-a8#
    m1 = B('......k.', '.....ppp', '........', '........',
           '........', '........', '........', 'R.....K.')
    mv, sc, d = E.search_best(m1, E.WHITE, -1, 3.0)
    print('[mate1] move', mv, 'score', sc,
          'OK' if mv == (56, 0) and sc > E.INF - 1000 else 'FAIL')

    # 逼和检测：白 Qc7 黑Ka8 白Kc8?? 换个标准逼和局面
    # 黑王 a8, 白后 b6, 白王 c6 → 黑无子可动且未被将 = 逼和
    stale = B('k.......', '........', '.QK.....', '........',
              '........', '........', '........', '........')
    lm = E.legal_moves(stale, E.BLACK, -1)
    chk = E.in_check(stale, E.BLACK)
    print('[stalemate] black moves =', len(lm), 'in_check =', chk,
          'OK' if not lm and not chk else 'FAIL')
    # 搜索应避免走出逼和: 白先, 后在 b5 王 c5, 黑king a7...构造:白方评分应视逼和为0
    # 直接验证负号: 白走 Qb6+?? 假设吃光.. 简化: 搜索在必胜局面不应选逼和着法
    pre = B('k.......', '........', '..K.....', '.Q......',
            '........', '........', '........', '........')
    mv, sc, d = E.search_best(pre, E.WHITE, -1, 5.0)
    bd2 = pre[:]
    undo, _ = E.make(bd2, mv, -1)
    ok = E.legal_moves(bd2, E.BLACK, -1) or not E.in_check(bd2, E.BLACK) is False
    stale_after = (not E.legal_moves(bd2, E.BLACK, -1)) and (not E.in_check(bd2, E.BLACK))
    print('[avoid stalemate] white best', mv, 'score', sc,
          'produces stalemate:', stale_after, 'OK' if not stale_after else 'FAIL')

    # 吃过路兵：白兵 e5, 黑兵 d7 走 d5, 白 exd6
    epb = B('....k...', '...p....', '........', '....P...',
            '........', '........', '........', '....K...')
    # 黑 d7-d5
    undo, nep = E.make(epb, (E.idx(1,3), E.idx(3,3)), -1)
    print('[ep] ep square after d7d5 =', nep, '(expect %d)' % E.idx(2,3),
          'OK' if nep == E.idx(2,3) else 'FAIL')
    wmoves = E.legal_moves(epb, E.WHITE, nep)
    epcap = (E.idx(3,4), E.idx(2,3))
    print('[ep] exd6 available:', epcap in wmoves, 'OK' if epcap in wmoves else 'FAIL')
    undo2, _ = E.make(epb, epcap, nep)
    print('[ep] black d5 pawn removed:', epb[E.idx(3,3)] == '.',
          'OK' if epb[E.idx(3,3)] == '.' else 'FAIL')

    # 升变：白兵 a7 -> a8 自动成后
    pro = B('....k...', 'P.......', '........', '........',
            '........', '........', '........', '....K...')
    undo, _ = E.make(pro, (E.idx(1,0), E.idx(0,0)), -1)
    print('[promo] a8 piece =', pro[0], 'OK' if pro[0] == 'Q' else 'FAIL')

    # KQK 基本杀法转换：15回合内将死
    kqk = B('....k...', '........', '........', '........',
            '........', '........', '...Q....', '....K...')
    bd, side, ep = kqk[:], E.WHITE, -1
    hist = [E.key_of(bd, side, ep)]
    res = 'unfinished'
    t0 = time.time()
    for ply in range(60):
        pen = E.repetition_penalties(bd, side, ep, hist)
        dm = E.draw_moves_of(bd, side, ep, hist)
        mv, sc, d = E.search_best(bd, side, ep, 2.0, pen, dm, hist)
        if mv is None:
            res = 'white_win' if side == E.BLACK and E.in_check(bd, side) else 'end'
            break
        undo, ep = E.make(bd, mv, ep)
        hist.append(E.key_of(bd, -side, ep))
        side = -side
        if not E.legal_moves(bd, side, ep):
            res = ('WHITE WIN(mate)' if E.in_check(bd, side) else 'draw(stalemate!)') \
                  if side == E.BLACK else 'black?!'
            break
    print('[KQK] result:', res, 'plies=%d %.0fs' % (ply + 1, time.time() - t0),
          'OK' if res == 'WHITE WIN(mate)' else 'FAIL')

if __name__ == '__main__':
    main()
