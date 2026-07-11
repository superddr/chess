# -*- coding: utf-8 -*-
"""测试：提前收工提速 + 禁走回头路"""
import sys, time
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine as E

def B(*rows):
    return list(''.join(rows))

def main():
    # 回归
    op = B('rnbakabnr', '.........', '.c.....c.', 'p.p.p.p.p', '.........',
           '.........', 'P.P.P.P.P', '.C.....C.', '.........', 'RNBAKABNR')
    print('[reg] 开局44步:', 'OK' if len(E.legal_moves(op, E.RED)) == 44 else 'FAIL')
    mate1 = B('....k....', '.........', '....N....', '.........', 'C........',
              '.........', '....p....', '.........', '.........', '....K....')
    t0 = time.time()
    mv, sc, d = E.search_best(mate1, E.RED, 30.0)
    el = time.time() - t0
    print('[speed] 必胜杀棋 30s预算 实际%.1fs' % el, 'OK' if mv == (36, 40) and el < 5 else 'FAIL')

    # 被杀方也应快速认命：兵梯杀网中的黑方(轮黑走,黑被强制将死)
    doomed = B('.....k...', '....PP...', '....P....', '.........', '.........',
               '.....r...', '.........', '.........', '....K....', '...r.....')
    t0 = time.time()
    mv, sc, d = E.search_best(doomed, E.BLACK, 30.0)
    el = time.time() - t0
    print('[speed] 被杀方 30s预算 实际%.1fs 评分%+d' % (el, sc),
          'OK' if el < 12 and sc < -(E.INF - 10000) else ('OK(未成杀局面)' if el < 12 else 'FAIL'))

    # 禁走回头路：黑车曾在 (4,4)，历史里已有"车回(4,4)"局面 → 不再走回去
    pos = B('...k.....', '.........', '.........', '.........', '.....r...',
            '.........', '.........', '.........', '.........', '....K....')
    b2 = pos[:]
    E.make(b2, (E.idx(4, 5), E.idx(4, 4)))
    seen_key = E.key_of(b2, E.RED)
    hist = [seen_key]  # 该局面出现过一次
    seen = E.draw_moves_of(pos, E.BLACK, hist, 1)
    print('[回头路] 识别出的回头走法:', [(m[0]//9, m[0]%9, m[1]//9, m[1]%9) for m in seen],
          'OK' if (E.idx(4, 5), E.idx(4, 4)) in seen else 'FAIL')
    banned = E.perpetual_banned(pos, E.BLACK, hist) | seen
    mv, sc, d = E.search_best(pos[:], E.BLACK, 5.0, banned, {}, (), hist)
    print('[回头路] 黑选 (%d,%d)->(%d,%d)' % (mv[0]//9, mv[0]%9, mv[1]//9, mv[1]%9),
          '不走回头:', 'OK' if mv != (E.idx(4, 5), E.idx(4, 4)) else 'FAIL')

if __name__ == '__main__':
    main()
