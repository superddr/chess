import sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "international"))
import engine as E

def setup(pairs):
    b = ['.'] * 64
    for sq, p in pairs:
        c = 'abcdefgh'.index(sq[0]); r = 8 - int(sq[1])
        b[r*8+c] = p
    return b

SQ = lambda i: 'abcdefgh'[i%8] + str(8 - i//8)

def selfplay(name, bd, tl=8.0):
    side, ep = E.WHITE, -1
    hist = [E.key_of(bd, side, ep)]
    moves = []
    for ply in range(90):
        pen = E.repetition_penalties(bd, side, ep, hist)
        dm = E.draw_moves_of(bd, side, ep, hist)
        mv, sc, d = E.search_best(bd, side, ep, tl, pen, dm, hist)
        if mv is None:
            print('%s: %d步后 %s' % (name, ply,
                  ('白胜(将死)' if E.in_check(bd, side) else '逼和=和棋') if side == E.BLACK
                  else ('黑胜' if E.in_check(bd, side) else '逼和=和棋')))
            return
        p = bd[mv[0]]
        moves.append('%s%s-%s' % (p, SQ(mv[0]), SQ(mv[1])))
        undo, ep = E.make(bd, mv, ep)
        k = E.key_of(bd, -side, ep)
        if hist.count(k) >= 2:
            print('%s: %d步后 三次重复判和 | %s' % (name, ply+1, ' '.join(moves[-6:])))
            return
        hist.append(k)
        side = -side
        if not E.legal_moves(bd, side, ep):
            print('%s: %d步后 %s | 末几步: %s' % (name, ply+1,
                  '白胜(将死)' if (side == E.BLACK and E.in_check(bd, side)) else
                  ('黑胜(将死)' if E.in_check(bd, side) else '逼和=和棋'),
                  ' '.join(moves[-6:])))
            return
        if E.insufficient_material(bd):
            print('%s: %d步后 子力不足判和(兵被吃) | %s' % (name, ply+1, ' '.join(moves[-6:])))
            return
    print('%s: 90步未分출 (和棋倾向)' % name)

def main():
    selfplay('[现预设 Ke5/Pe4 vs Ke7 白先]', setup([('e5','K'),('e4','P'),('e7','k')]))
    selfplay('[修正版 Ke6/Pe4 vs Ke8 白先]', setup([('e6','K'),('e4','P'),('e8','k')]))

if __name__ == '__main__':
    main()
