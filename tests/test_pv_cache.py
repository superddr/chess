# -*- coding: utf-8 -*-
"""主变例缓存：深算一次后，沿 PV 线的求助与应招应即问即答（不依赖后台预算时间）"""
import sys, time
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine as E
import server as SV

def main():
    # 双兵对双士残局（搜索深度高, PV 长）
    b = ['.'] * 90
    def put(r_, c, p): b[r_*9+c] = p
    put(9, 3, 'K'); put(3, 3, 'P'); put(3, 5, 'P')
    put(0, 4, 'k'); put(0, 3, 'a'); put(0, 5, 'a')
    board = ''.join(b)
    hist = [board + 'r']
    # 红兵进一，黑 AI 深算 8 秒（此过程会把整条主变例缓存）
    r = SV.api_move({'board': board, 'history': hist, 'from': 30, 'to': 21, 'time': 8})
    assert r['ok']
    hist2 = hist + [r['playerKey'], r['aiKey']]
    b2 = r['board']
    print('AI应招深度%d, PV缓存条目数: %d' % (r['depth'], len(SV.PV_CACHE)))
    assert len(SV.PV_CACHE) >= 2, 'PV 缓存未建立'

    # ① 立刻求助（后台预算不可能已完成）——应命中 PV 缓存
    t0 = time.time()
    h = SV.api_hint({'board': b2, 'history': hist2, 'time': 8, 'side': 'r'})
    el1 = time.time() - t0
    print('① 立刻求助: %.2fs cached=%s 深度%d' % (el1, h.get('cached'), h['depth']))
    assert h.get('cached') and el1 < 1.0, '求助未命中PV缓存'

    # ② 立刻照提示走——AI 应招也应命中 PV 缓存
    t0 = time.time()
    r2 = SV.api_move({'board': b2, 'history': hist2,
                      'from': h['from'], 'to': h['to'], 'time': 8})
    el2 = time.time() - t0
    print('② 立刻照提示走: %.2fs AI应招%s 深度%d' % (el2, r2['aiMove'], r2['depth']))
    assert r2['ok'] and el2 < 1.5, '照提示走未秒回'
    print('ALL OK')

if __name__ == '__main__':
    main()
