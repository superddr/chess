# -*- coding: utf-8 -*-
"""规则感知搜索后的决定性测试"""
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
    mv, sc, d = E.search_best(mate1, E.RED, 3.0)
    print('[reg] 马后炮杀:', 'OK' if mv == (36, 40) and sc > E.INF - 1000 else 'FAIL')
    conv = B('...ak....', '....a....', '.........', '...P.P...', '.........',
             '.........', '.........', '.........', '.........', '...K.....')
    bd, side, hist = conv[:], E.RED, [E.key_of(conv, E.RED)]
    res = 'unfinished'
    for ply in range(60):
        banned = E.perpetual_banned(bd, side, hist)
        pen = E.repetition_penalties(bd, side, hist)
        dmv = E.draw_moves_of(bd, side, hist)
        mv, sc, d = E.search_best(bd, side, 1.5, banned, pen, dmv, hist)
        if mv is None:
            res = 'red_win' if side == E.BLACK else 'black_win'; break
        E.make(bd, mv); hist.append(E.key_of(bd, -side)); side = -side
        if not E.legal_moves(bd, side):
            res = 'red_win' if side == E.BLACK else 'black_win'; break
    print('[reg] 双兵胜双士:', 'OK' if res == 'red_win' else 'FAIL(%s)' % res)

    # 决定性测试：四兵对双车
    START = B('..rr.k...', '....P....', '....P....', '....P....', '....P....',
              '.........', '.........', '.........', '.........', '....K....')
    for tl in (30, 90):
        t0 = time.time()
        mv, sc, d = E.search_best(START[:], E.RED, tl, history=[E.key_of(START, E.RED)])
        tag = '红方绝杀!' if sc > E.INF - 10000 else ('红优' if sc > 200 else ('黑优' if sc < -200 else '接近均势/和'))
        print('[关键] 四兵对双车 红先 %ds: (%d,%d)->(%d,%d) 评分%+d 深度%d [%s] %.0fs'
              % (tl, mv[0]//9, mv[0]%9, mv[1]//9, mv[1]%9, sc, d, tag, time.time()-t0))

if __name__ == '__main__':
    main()
