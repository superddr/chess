# -*- coding: utf-8 -*-
"""标准长将循环裁决测试"""
import sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine as E
import server as SV

def main():
    # P(黑走): 黑车(4,4) 红帅(9,5) 黑将(0,3)
    b = ['.'] * 90
    b[E.idx(0, 3)] = 'k'
    b[E.idx(4, 4)] = 'r'
    b[E.idx(9, 5)] = 'K'
    P = E.key_of(b, E.BLACK)
    E.make(b, (E.idx(4, 4), E.idx(4, 5)))          # 黑车平六将军
    Q1 = E.key_of(b, E.RED)
    assert E.in_check(b, E.RED)
    E.make(b, (E.idx(9, 5), E.idx(9, 4)))          # 红帅被迫平五
    Q2 = E.key_of(b, E.BLACK)
    Q2_board = b[:]
    E.make(b, (E.idx(4, 5), E.idx(4, 4)))          # 黑车平五又将
    Q3 = E.key_of(b, E.RED)
    assert E.in_check(b, E.RED)
    E.make(b, (E.idx(9, 4), E.idx(9, 5)))          # 红帅被迫平六 → 回到 P
    assert E.key_of(b, E.BLACK) == P
    print('长将循环构造 OK')

    over, msg = SV.adjudicate_repetition([P, Q1, Q2, Q3], P)
    print('[裁决-黑长将]', over, '-', msg, 'OK' if over == 'red' else 'FAIL')

    # 红方长将镜像：交换角色——红车长将黑将
    b2 = ['.'] * 90
    b2[E.idx(9, 3)] = 'K'
    b2[E.idx(4, 4)] = 'R'
    b2[E.idx(0, 5)] = 'k'
    P2 = E.key_of(b2, E.RED)
    E.make(b2, (E.idx(4, 4), E.idx(4, 5)))
    W1 = E.key_of(b2, E.BLACK)
    assert E.in_check(b2, E.BLACK)
    E.make(b2, (E.idx(0, 5), E.idx(0, 4)))
    W2 = E.key_of(b2, E.RED)
    E.make(b2, (E.idx(4, 5), E.idx(4, 4)))
    W3 = E.key_of(b2, E.BLACK)
    assert E.in_check(b2, E.BLACK)
    E.make(b2, (E.idx(0, 4), E.idx(0, 5)))
    assert E.key_of(b2, E.RED) == P2
    over2, msg2 = SV.adjudicate_repetition([P2, W1, W2, W3], P2)
    print('[裁决-红长将]', over2, '-', msg2, 'OK' if over2 == 'black' else 'FAIL')

    # 树内: 黑在 Q2 决策（历史已含两轮循环），继续长将应视为必输
    hist = [P, Q1, Q2, Q3, P, Q1]
    banned = E.perpetual_banned(Q2_board, E.BLACK, hist)
    pen = E.repetition_penalties(Q2_board, E.BLACK, hist)
    dm = E.draw_moves_of(Q2_board, E.BLACK, hist)
    mv, sc, d = E.search_best(Q2_board[:], E.BLACK, 10.0, banned, pen, dm, hist)
    check_move = (E.idx(4, 5), E.idx(4, 4))
    print('[树内] 黑选 (%d,%d)->(%d,%d) 评分%+d 禁着%d 和着%d' %
          (mv[0]//9, mv[0]%9, mv[1]//9, mv[1]%9, sc, len(banned), len(dm)),
          '| 不再靠长将洗和:', 'OK' if mv != check_move else 'FAIL')

if __name__ == '__main__':
    main()
