# -*- coding: utf-8 -*-
"""速度基准：冷缓存 vs 暖缓存（预料中应招）"""
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

    START = B('..rr.k...', '....P....', '....P....', '....P....', '....P....',
               '.........', '.........', '.........', '.........', '....K....')
    hist = [E.key_of(START, E.RED)]

    # 冷缓存: 红方首搜 (60s 预算)
    t0 = time.time()
    mv, sc, d = E.search_best(START[:], E.RED, 60.0, history=hist)
    print('[冷] 红首搜: %.1fs/60s 深%d 分%+d 走(%d,%d)->(%d,%d)'
          % (time.time() - t0, d, sc, mv[0]//9, mv[0]%9, mv[1]//9, mv[1]%9))

    # 模拟对弈流: 红走 (2,4)->(2,5)，黑搜索(这一步会暖热缓存)
    bd = START[:]
    E.make(bd, (E.idx(2, 4), E.idx(2, 5)))
    hist.append(E.key_of(bd, E.BLACK))
    t0 = time.time()
    bmv, bsc, bd_ = E.search_best(bd[:], E.BLACK, 60.0, history=hist)
    print('[冷] 黑首搜: %.1fs/60s 深%d 分%+d 走(%d,%d)->(%d,%d)'
          % (time.time() - t0, bd_, bsc, bmv[0]//9, bmv[0]%9, bmv[1]//9, bmv[1]%9))
    # 黑走它选的棋, 红走"预料之中"的应招(黑搜索时算出的红方最佳=无从得知,
    # 用典型应招 帅平/上), 再让黑搜索 → 暖缓存效果
    E.make(bd, bmv)
    hist.append(E.key_of(bd, E.RED))
    rmoves = E.legal_moves(bd, E.RED)
    rmv = rmoves[0]
    E.make(bd, rmv)
    hist.append(E.key_of(bd, E.BLACK))
    t0 = time.time()
    bmv2, bsc2, d2 = E.search_best(bd[:], E.BLACK, 60.0, history=hist)
    el = time.time() - t0
    print('[暖] 黑二搜: %.1fs/60s 深%d 分%+d' % (el, d2, bsc2),
          '(缓存命中提前收工)' if el < 25 else '(仍用满时限)')

if __name__ == '__main__':
    main()
