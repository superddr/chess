# -*- coding: utf-8 -*-
"""中国象棋残局研究器 - 本地服务
运行: python server.py [端口]   默认 http://127.0.0.1:8000
"""
import hashlib
import json
import os
import sys
import threading
import time
from collections import Counter
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import engine as E

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------- 对局监控日志 ----------------
LOG_PATH = os.path.join(ROOT, 'game_log.jsonl')
LOG_LOCK = threading.Lock()


def log_event(kind, payload):
    rec = dict(payload)
    rec['event'] = kind
    rec['t'] = time.strftime('%H:%M:%S')
    try:
        with LOG_LOCK:
            with open(LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except OSError:
        pass


NAME_RED ={'K': '帅', 'A': '仕', 'B': '相', 'N': '马', 'R': '车', 'C': '炮', 'P': '兵'}
NAME_BLACK = {'K': '将', 'A': '士', 'B': '象', 'N': '马', 'R': '车', 'C': '炮', 'P': '卒'}
COUNTS = {'K': 1, 'A': 2, 'B': 2, 'N': 2, 'R': 2, 'C': 2, 'P': 5}

ADV_RED = {(9, 3), (9, 5), (8, 4), (7, 3), (7, 5)}
ADV_BLACK = {(0, 3), (0, 5), (1, 4), (2, 3), (2, 5)}
ELE_RED = {(9, 2), (9, 6), (7, 0), (7, 4), (7, 8), (5, 2), (5, 6)}
ELE_BLACK = {(0, 2), (0, 6), (2, 0), (2, 4), (2, 8), (4, 2), (4, 6)}


def validate_setup(board):
    """返回错误信息字符串；合法则返回 None。board 为 list。"""
    cnt = Counter(p for p in board if p != E.EMPTY)
    if cnt.get('K', 0) != 1:
        return '红方必须有且只有一个帅'
    if cnt.get('k', 0) != 1:
        return '黑方必须有且只有一个将'
    for up, mx in COUNTS.items():
        if cnt.get(up, 0) > mx:
            return '红方%s数量超过上限(%d)' % (NAME_RED[up], mx)
        if cnt.get(up.lower(), 0) > mx:
            return '黑方%s数量超过上限(%d)' % (NAME_BLACK[up], mx)
    for i, p in enumerate(board):
        if p == E.EMPTY:
            continue
        r, c = divmod(i, 9)
        if p == 'K' and not (3 <= c <= 5 and 7 <= r <= 9):
            return '帅必须在红方九宫内'
        if p == 'k' and not (3 <= c <= 5 and 0 <= r <= 2):
            return '将必须在黑方九宫内'
        if p == 'A' and (r, c) not in ADV_RED:
            return '仕只能放在红方九宫的斜线交点上'
        if p == 'a' and (r, c) not in ADV_BLACK:
            return '士只能放在黑方九宫的斜线交点上'
        if p == 'B' and (r, c) not in ELE_RED:
            return '相只能放在红方的七个象位上'
        if p == 'b' and (r, c) not in ELE_BLACK:
            return '象只能放在黑方的七个象位上'
        if p == 'P' and (r > 6 or (r >= 5 and c % 2 == 1)):
            return '兵的位置不合法（未过河的兵只能在己方兵线的起始纵线上）'
        if p == 'p' and (r < 3 or (r <= 4 and c % 2 == 1)):
            return '卒的位置不合法（未过河的卒只能在己方卒线的起始纵线上）'
    if E.in_check(board, E.BLACK):
        return '红方先行：开始时黑方不能已处于被将军状态'
    if E.in_check(board, E.RED) and not E.legal_moves(board, E.RED):
        return '红方开局即被将死，无法开始'
    if not E.legal_moves(board, E.RED):
        return '红方无棋可走，无法开始'
    return None


def parse_board(data):
    b = data.get('board', '')
    if not isinstance(b, str) or len(b) != 90 or any(ch not in '.KABNRCPkabnrcp' for ch in b):
        raise ValueError('棋盘数据格式错误')
    return list(b)


def clamp_time(data):
    try:
        t = float(data.get('time', 16))
    except (TypeError, ValueError):
        t = 16.0
    return min(max(t, 0.3), 300.0)


def api_start(data):
    board = parse_board(data)
    err = validate_setup(board)
    if err:
        return {'ok': False, 'error': err}
    log_event('start', {'board': ''.join(board)})
    return {'ok': True}


def side_param(data):
    return E.BLACK if data.get('side') == 'b' else E.RED


def api_moves(data):
    board = parse_board(data)
    side = side_param(data)
    return {'ok': True,
            'moves': E.legal_moves(board, side),
            'check': E.in_check(board, side)}


def api_hint(data):
    board = parse_board(data)
    history = data.get('history', []) or []
    side = side_param(data)
    banned = E.perpetual_banned(board, side, history)
    pen = E.repetition_penalties(board, side, history)
    dm = E.draw_moves_of(board, side, history)
    out = {}
    mv, score, depth = E.search_best(board, side, clamp_time(data), banned, pen, dm,
                                     history, out)
    if mv is None:
        return {'ok': False, 'error': '当前没有可走的棋'}
    log_event('hint', {'side': 'r' if side == E.RED else 'b',
                       'board': ''.join(board), 'move': [mv[0], mv[1]],
                       'score': score, 'depth': depth,
                       'scores_top': out.get('scores', [])[:10]})
    return {'ok': True, 'from': mv[0], 'to': mv[1], 'score': score, 'depth': depth}


def adjudicate_repetition(history, new_key):
    """同一局面第三次出现时的裁决：重复循环若由单方长将造成，长将方判负；
    双方均无长将才判和。history 不含 new_key。"""
    try:
        last = len(history) - 1 - history[::-1].index(new_key)
    except ValueError:
        return 'draw', '同一局面第三次出现，判和'
    cycle = history[last:] + [new_key]
    red_all = black_all = True   # red_all: 循环内红方行棋时始终被将（即黑方在长将）
    for k in cycle:
        bd = list(k[:90])
        stm = E.RED if k[90] == 'r' else E.BLACK
        chk = E.in_check(bd, stm)
        if stm == E.RED and not chk:
            red_all = False
        if stm == E.BLACK and not chk:
            black_all = False
    if red_all and not black_all:
        return 'red', '黑方长将不变，判负——红方获胜！'
    if black_all and not red_all:
        return 'black', '红方长将不变，判负——黑方获胜！'
    return 'draw', '同一局面第三次出现（双方均无长将），判和'


def _game_end_after(board, mover_side, gave_check):
    """某方走完一步后的终局判定，返回 (gameOver, message)。"""
    if not E.legal_moves(board, -mover_side):
        winner = 'red' if mover_side == E.RED else 'black'
        wname, lname = ('红方', '黑方') if winner == 'red' else ('黑方', '红方')
        return winner, '%s获胜！%s' % (wname, lname + ('被将死' if gave_check else '困毙（无子可动）'))
    if not E.has_attacker(board, E.RED) and not E.has_attacker(board, E.BLACK):
        return 'draw', '双方均无进攻子力，和棋'
    return None, ''


def _apply_user_move(board, history, side, frm, to):
    """校验并执行 side 方的一步棋。合法返回 None，否则返回错误信息。"""
    sname = '红方' if side == E.RED else '黑方'
    if E.side_of(board[frm]) != side:
        return '请移动%s棋子' % sname
    if (frm, to) not in E.legal_moves(board, side):
        return '不符合走棋规则'
    E.make(board, (frm, to))
    if E.in_check(board, -side) and history.count(E.key_of(board, -side)) >= 2:
        return '禁止长将！同一将军局面不得反复出现（%s违规），请更换走法' % sname
    return None


def _ai_reply(board, history, tl):
    """黑方 AI 在当前局面走一步，返回结果字段（board 会被修改）。"""
    board_before = ''.join(board)
    # 走回头路（重现任何历史局面）的着法一律禁止，除非无路可走——
    # 败势下也必须走新变化，不许无聊地来回拖延
    seen = E.draw_moves_of(board, E.BLACK, history, 1)
    banned = E.perpetual_banned(board, E.BLACK, history) | seen
    pen = E.repetition_penalties(board, E.BLACK, history)
    dm = E.draw_moves_of(board, E.BLACK, history)
    out = {}
    mv, score, depth = E.search_best(board, E.BLACK, tl, banned, pen, dm, history, out)
    E.make(board, mv)
    ai_key = E.key_of(board, E.RED)
    check_red = E.in_check(board, E.RED)
    over, msg = _game_end_after(board, E.BLACK, check_red)
    if not over and history.count(ai_key) >= 2:
        over, msg = adjudicate_repetition(history, ai_key)
    if not over and check_red:
        msg = '黑方将军！请应将'
    log_event('ai_move', {
        'board_before': board_before, 'move': [mv[0], mv[1]], 'score': score,
        'depth': depth, 'time_limit': tl, 'checkRed': check_red,
        'gameOver': over, 'histLen': len(history),
        'scores_top': out.get('scores', [])[:10],
        'banned': out.get('banned', []), 'drawMoves': out.get('draws', []),
        'note': out.get('note', ''),
    })
    return {'aiMove': {'from': mv[0], 'to': mv[1]}, 'aiKey': ai_key,
            'checkRed': check_red, 'depth': depth, 'board': ''.join(board),
            'gameOver': over, 'message': msg}


def api_move(data):
    """红方走一步 + 本机 AI 应招"""
    board = parse_board(data)
    history = data.get('history', []) or []
    frm, to = int(data['from']), int(data['to'])
    err = _apply_user_move(board, history, E.RED, frm, to)
    if err:
        return {'ok': False, 'error': err}
    player_key = E.key_of(board, E.BLACK)
    check_black = E.in_check(board, E.BLACK)
    resp = {'ok': True, 'playerKey': player_key, 'checkBlack': check_black,
            'aiMove': None, 'board': ''.join(board)}
    over, msg = _game_end_after(board, E.RED, check_black)
    if not over and history.count(player_key) >= 2:
        over, msg = adjudicate_repetition(history, player_key)
    log_event('player_move', {'move': [frm, to], 'board_after': ''.join(board),
                              'checkBlack': check_black, 'gameOver': over,
                              'histLen': len(history)})
    if over:
        resp['gameOver'] = over
        resp['message'] = msg
        return resp
    resp.update(_ai_reply(board, history + [player_key], clamp_time(data)))
    return resp


def api_usermove(data):
    """单独走一步（红或黑），不触发 AI 应招——用于手动代走外部对手的黑棋"""
    board = parse_board(data)
    history = data.get('history', []) or []
    side = side_param(data)
    frm, to = int(data['from']), int(data['to'])
    err = _apply_user_move(board, history, side, frm, to)
    if err:
        return {'ok': False, 'error': err}
    chk = E.in_check(board, -side)
    key = E.key_of(board, -side)
    over, msg = _game_end_after(board, side, chk)
    if not over and history.count(key) >= 2:
        over, msg = adjudicate_repetition(history, key)
    log_event('user_move', {'side': 'r' if side == E.RED else 'b', 'move': [frm, to],
                            'board_after': ''.join(board), 'check': chk,
                            'gameOver': over, 'histLen': len(history)})
    return {'ok': True, 'board': ''.join(board), 'key': key,
            'check': chk, 'gameOver': over, 'message': msg}


def api_aimove(data):
    """让本机 AI 立即代走当前的黑棋"""
    board = parse_board(data)
    history = data.get('history', []) or []
    if not E.legal_moves(board, E.BLACK):
        return {'ok': False, 'error': '黑方无棋可走'}
    resp = {'ok': True}
    resp.update(_ai_reply(board, history, clamp_time(data)))
    return resp


# ---------------- 耗时接口任务化：断线后服务器继续计算，重连轮询即可取回 ----------------
JOBS = {}          # job_id -> {'t': 创建时间, 'done': bool, 'result': dict}
JOBS_LOCK = threading.Lock()
JOB_TTL = 900      # 结果保留 15 分钟


def _run_job(jid, fn, data):
    try:
        result = fn(data)
    except Exception as e:  # noqa: BLE001
        result = {'ok': False, 'error': '服务出错: %s' % e}
    with JOBS_LOCK:
        job = JOBS.get(jid)
        if job is not None:
            job['result'] = result
            job['done'] = True


def submit_job(path, fn, data):
    """任务 id 由请求内容哈希而来：断线后客户端重发同一请求会命中同一个
    正在计算的任务，而不是重新起一个。
    短暂等待一下：快棋（唯一应法等）直接随提交响应同步返回，免去轮询延迟。"""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    jid = hashlib.md5((path + '|' + raw).encode('utf-8')).hexdigest()
    th = None
    with JOBS_LOCK:
        now = time.time()
        for k in [k for k, v in JOBS.items() if now - v['t'] > JOB_TTL]:
            del JOBS[k]
        if jid not in JOBS:
            JOBS[jid] = {'t': now, 'done': False, 'result': None}
            th = threading.Thread(target=_run_job, args=(jid, fn, data), daemon=True)
    if th:
        th.start()
        th.join(0.35)
    with JOBS_LOCK:
        job = JOBS.get(jid)
        if job and job['done']:
            return {'ok': True, 'job': jid, 'status': 'done', 'result': job['result']}
    return {'ok': True, 'job': jid}


def api_job(data):
    jid = str(data.get('id', ''))
    with JOBS_LOCK:
        job = JOBS.get(jid)
        if job is None:
            return {'ok': False, 'error': '任务已过期，请重新操作'}
        if not job['done']:
            return {'ok': True, 'status': 'running'}
        return {'ok': True, 'status': 'done', 'result': job['result']}


ROUTES = {
    '/api/start': api_start,
    '/api/moves': api_moves,
    '/api/usermove': api_usermove,
    '/api/job': api_job,
    # 三个可能长时间计算的接口走任务队列
    '/api/move': lambda d: submit_job('/api/move', api_move, d),
    '/api/aimove': lambda d: submit_job('/api/aimove', api_aimove, d),
    '/api/hint': lambda d: submit_job('/api/hint', api_hint, d),
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            with open(os.path.join(ROOT, 'index.html'), 'rb') as f:
                self._send(200, f.read(), 'text/html; charset=utf-8')
        elif self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        else:
            self._send(404, {'ok': False, 'error': 'not found'})

    def do_POST(self):
        fn = ROUTES.get(self.path)
        if fn is None:
            self._send(404, {'ok': False, 'error': 'not found'})
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length) or b'{}')
            self._send(200, fn(data))
        except Exception as e:  # noqa: BLE001 本地工具，出错直接回传信息
            self._send(200, {'ok': False, 'error': '服务出错: %s' % e})

    def log_message(self, fmt, *args):
        pass  # 安静模式


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print('中国象棋残局研究器已启动 (Ctrl+C 退出)')
    print('  AI 搜索进程数: %d' % E.pool_workers())
    print('  本机访问:   http://127.0.0.1:%d' % port)
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('223.5.5.5', 80))  # 不实际发包，仅用于确定本机局域网 IP
        lan_ip = s.getsockname()[0]
        s.close()
        print('  局域网访问: http://%s:%d  (手机与电脑需连同一网络)' % (lan_ip, port))
    except OSError:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
