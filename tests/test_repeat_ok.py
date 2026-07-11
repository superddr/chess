# -*- coding: utf-8 -*-
"""回头路是唯一好棋时，AI 应当敢走（即使重现历史局面）"""
import sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine as E

def main():
    # 局面（黑走）：红帅(9,5) 兵(1,4)(2,4)(2,5)成杀网；黑将(0,5) 黑车(4,4)。
    # 唯一防御=車回四路线(4,4)->(4,5)（兵四进一后可吃兵解杀）。
    # 历史中"車在(4,5)、红走"的局面已出现过一次——回头即重现。
    b = ['.'] * 90
    def put(r, c, p): b[r*9+c] = p
    put(0, 5, 'k'); put(4, 4, 'r')
    put(9, 5, 'K'); put(1, 4, 'P'); put(2, 4, 'P'); put(2, 5, 'P')
    board = b[:]
    # 构造历史：車在(4,5)的局面(红方行棋)出现过一次
    prev = board[:]
    E.make(prev, (E.idx(4, 4), E.idx(4, 5)))
    seen_key = E.key_of(prev, E.RED)
    hist = [seen_key, E.key_of(board, E.BLACK)]

    # 验证：其它走法确实致命（抽查兵四进一杀）
    b2 = board[:]
    E.make(b2, (E.idx(4, 4), E.idx(4, 0)))    # 黑车跑远
    E.make(b2, (E.idx(2, 5), E.idx(1, 5)))    # 红兵四进一
    print('黑车走开后红兵四进一，黑方应法数:', len(E.legal_moves(b2, E.BLACK)),
          '(0=绝杀)')

    # 新策略：不再把回头路加入禁着，只用罚分+判和着法
    banned = E.perpetual_banned(board, E.BLACK, hist)
    pen = E.repetition_penalties(board, E.BLACK, hist)
    dm = E.draw_moves_of(board, E.BLACK, hist)
    mv, sc, d = E.search_best(board[:], E.BLACK, 8.0, banned, pen, dm, hist)
    back = (E.idx(4, 4), E.idx(4, 5))
    print('黑选 (%d,%d)->(%d,%d) 评分%+d 深度%d' %
          (mv[0]//9, mv[0]%9, mv[1]//9, mv[1]%9, sc, d))
    print('敢走唯一正解的回头路:', 'OK' if mv == back else 'FAIL')

if __name__ == '__main__':
    main()
