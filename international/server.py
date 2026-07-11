# -*- coding: utf-8 -*-
"""国际象棋残局研究器 - 本地服务
运行: python server.py [端口]   默认 http://127.0.0.1:8766
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

NAME = {'K': '王', 'Q': '后', 'R': '车', 'B': '象', 'N': '马', 'P': '兵'}
COUNTS = {'K': 1, 'Q': 9, 'R': 10, 'B': 10, 'N': 10, 'P': 8}


def validate_setup(board):
    cnt = Counter(p for p in board if p != E.EMPTY)
    if cnt.get('K', 0) != 1:
        return '白方必须有且只有一个王'
    if cnt.get('k', 0) != 1:
        return '黑方必须有且只有一个王'
    for up, mx in COUNTS.items():
        if cnt.get(up, 0) > mx:
            return '白方%s数量超过上限(%d)' % (NAME[up], mx)
        if cnt.get(up.lower(), 0) > mx:
            return '黑方%s数量超过上限(%d)' % (NAME[up], mx)
    for i, p in enumerate(board):
        if p in ('P', 'p') and (i < 8 or i >= 56):
            return '兵不能放在第一或第八横排'
    wk, bk = board.index('K'), board.index('k')
    if abs(wk // 8 - bk // 8) <= 1 and abs(wk % 8 - bk % 8) <= 1:
        return '两王不能相邻'
    if E.in_check(board, E.BLACK):
        return '白方先行：开始时黑方不能已处于被将军状态'
    if not E.legal_moves(board, E.WHITE, -1):
        return '白方无棋可走，无法开始'
    return None


def parse_board(data):
    b = data.get('board', '')
    if not isinstance(b, str) or len(b) != 64 or any(ch not in '.KQRBNPkqrbnp' for ch in b):
        raise ValueError('棋盘数据格式错误')
    return list(b)


def parse_ep(data):
    try:
        ep = int(data.get('ep', -1))
    except (TypeError, ValueError):
        ep = -1
    return ep if 0 <= ep < 64 else -1


def clamp_time(data):
    try:
        t = float(data.get('time', 16))
    except (TypeError, ValueError):
        t = 16.0
    return min(max(t, 0.3), 300.0)


def side_param(data):
    return E.BLACK if data.get('side') == 'b' else E.WHITE


def api_start(data):
    board = parse_board(data)
    err = validate_setup(board)
    if err:
        return {'ok': False, 'error': err}
    return {'ok': True}


def api_moves(data):
    board = parse_board(data)
    ep = parse_ep(data)
    side = side_param(data)
    return {'ok': True,
            'moves': E.legal_moves(board, side, ep),
            'check': E.in_check(board, side)}


def api_hint(data):
    board = parse_board(data)
    ep = parse_ep(data)
    history = data.get('history', []) or []
    side = side_param(data)
    pen = E.repetition_penalties(board, side, ep, history)
    dm = E.draw_moves_of(board, side, ep, history)
    mv, score, depth = E.search_best(board, side, ep, clamp_time(data), pen, dm, history)
    if mv is None:
        return {'ok': False, 'error': '当前没有可走的棋'}
    return {'ok': True, 'from': mv[0], 'to': mv[1], 'score': score, 'depth': depth}


def _game_end_after(board, ep, mover_side, gave_check):
    """走完一步后的终局判定。国际象棋：无子可动且被将=将死，否则逼和(和棋)。"""
    if not E.legal_moves(board, -mover_side, ep):
        if gave_check:
            winner = 'white' if mover_side == E.WHITE else 'black'
            return winner, ('白方' if winner == 'white' else '黑方') + '获胜！对方被将死'
        return 'draw', '逼和（对方无子可动且未被将军），和棋'
    if E.insufficient_material(board):
        return 'draw', '子力不足以将死，和棋'
    return None, ''


def _apply_user_move(board, ep, history, side, frm, to):
    """校验并执行一步棋。返回 (错误信息或None, 新ep)。"""
    sname = '白方' if side == E.WHITE else '黑方'
    if E.side_of(board[frm]) != side:
        return '请移动%s棋子' % sname, ep
    if (frm, to) not in E.legal_moves(board, side, ep):
        return '不符合走棋规则', ep
    _, new_ep = E.make(board, (frm, to), ep)
    return None, new_ep


def _ai_reply(board, ep, history, tl):
    pen = E.repetition_penalties(board, E.BLACK, ep, history)
    dm = E.draw_moves_of(board, E.BLACK, ep, history)
    mv, score, depth = E.search_best(board, E.BLACK, ep, tl, pen, dm, history)
    _, new_ep = E.make(board, mv, ep)
    ai_key = E.key_of(board, E.WHITE, new_ep)
    check_w = E.in_check(board, E.WHITE)
    over, msg = _game_end_after(board, new_ep, E.BLACK, check_w)
    if not over and history.count(ai_key) >= 2:
        over, msg = 'draw', '同一局面第三次出现，判和'
    if not over and check_w:
        msg = '黑方将军！请应将'
    return {'aiMove': {'from': mv[0], 'to': mv[1]}, 'aiKey': ai_key,
            'checkWhite': check_w, 'depth': depth, 'board': ''.join(board),
            'ep': new_ep, 'gameOver': over, 'message': msg}


def api_move(data):
    """白方走一步 + 本机 AI 应招"""
    board = parse_board(data)
    ep = parse_ep(data)
    history = data.get('history', []) or []
    frm, to = int(data['from']), int(data['to'])
    err, new_ep = _apply_user_move(board, ep, history, E.WHITE, frm, to)
    if err:
        return {'ok': False, 'error': err}
    player_key = E.key_of(board, E.BLACK, new_ep)
    check_b = E.in_check(board, E.BLACK)
    resp = {'ok': True, 'playerKey': player_key, 'checkBlack': check_b,
            'aiMove': None, 'board': ''.join(board), 'ep': new_ep}
    over, msg = _game_end_after(board, new_ep, E.WHITE, check_b)
    if not over and history.count(player_key) >= 2:
        over, msg = 'draw', '同一局面第三次出现，判和'
    if over:
        resp['gameOver'] = over
        resp['message'] = msg
        return resp
    resp.update(_ai_reply(board, new_ep, history + [player_key], clamp_time(data)))
    return resp


def api_usermove(data):
    """单独走一步（白或黑），不触发 AI——用于手动代走外部对手"""
    board = parse_board(data)
    ep = parse_ep(data)
    history = data.get('history', []) or []
    side = side_param(data)
    frm, to = int(data['from']), int(data['to'])
    err, new_ep = _apply_user_move(board, ep, history, side, frm, to)
    if err:
        return {'ok': False, 'error': err}
    chk = E.in_check(board, -side)
    key = E.key_of(board, -side, new_ep)
    over, msg = _game_end_after(board, new_ep, side, chk)
    if not over and history.count(key) >= 2:
        over, msg = 'draw', '同一局面第三次出现，判和'
    return {'ok': True, 'board': ''.join(board), 'key': key, 'ep': new_ep,
            'check': chk, 'gameOver': over, 'message': msg}


def api_aimove(data):
    board = parse_board(data)
    ep = parse_ep(data)
    history = data.get('history', []) or []
    if not E.legal_moves(board, E.BLACK, ep):
        return {'ok': False, 'error': '黑方无棋可走'}
    resp = {'ok': True}
    resp.update(_ai_reply(board, ep, history, clamp_time(data)))
    return resp


# ---------------- 任务化（与象棋版一致：断线后服务器继续计算） ----------------
JOBS = {}
JOBS_LOCK = threading.Lock()
JOB_TTL = 900


def _chain_after(path, data, result, chain):
    """链式预思考：move 完成→预算"求助"；求助出来→预算"照提示走后的应招"。"""
    if chain >= 2 or not isinstance(result, dict) or not result.get('ok'):
        return
    try:
        if path in ('/api/move', '/api/aimove'):
            if result.get('gameOver') or not result.get('aiMove'):
                return
            hist = list(data.get('history') or [])
            if path == '/api/move':
                hist += [result['playerKey'], result['aiKey']]
            else:
                hist += [result['aiKey']]
            submit_job('/api/hint', api_hint,
                       {'board': result['board'], 'ep': result['ep'], 'history': hist,
                        'time': data.get('time', 16), 'side': 'w'}, chain + 1)
        elif path == '/api/hint' and data.get('side', 'w') == 'w':
            submit_job('/api/move', api_move,
                       {'board': data['board'], 'ep': data.get('ep', -1),
                        'history': list(data.get('history') or []),
                        'from': result['from'], 'to': result['to'],
                        'time': data.get('time', 16)}, chain + 1)
    except Exception:
        pass


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
            path, chain = job['path'], job['chain']
        else:
            path, chain = '', 9
    _chain_after(path, data, result, chain)


def submit_job(path, fn, data, chain=0):
    """任务按请求内容哈希去重；玩家照提示走棋会命中链式预思考已算好的任务。
    短暂等待：快棋直接随提交响应同步返回，免去轮询延迟。"""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    jid = hashlib.md5((path + '|' + raw).encode('utf-8')).hexdigest()
    th = None
    with JOBS_LOCK:
        now = time.time()
        for k in [k for k, v in JOBS.items() if now - v['t'] > JOB_TTL]:
            del JOBS[k]
        job = JOBS.get(jid)
        if job is None:
            JOBS[jid] = {'t': now, 'done': False, 'result': None,
                         'path': path, 'chain': chain}
            th = threading.Thread(target=_run_job, args=(jid, fn, data), daemon=True)
        elif chain < job['chain']:
            job['chain'] = chain
    if th:
        th.start()
        th.join(0.35)
    with JOBS_LOCK:
        job = JOBS.get(jid)
        done = job and job['done']
        result = job['result'] if done else None
        cur_chain = job['chain'] if job else chain
    if done:
        _chain_after(path, data, result, cur_chain)
        return {'ok': True, 'job': jid, 'status': 'done', 'result': result}
    return {'ok': True, 'job': jid}


def api_job(data):
    """支持长轮询：wait>0 时由服务器抱着请求直到任务完成或超时。"""
    jid = str(data.get('id', ''))
    try:
        wait = min(float(data.get('wait', 0)), 30.0)
    except (TypeError, ValueError):
        wait = 0.0
    t_end = time.time() + wait
    while True:
        with JOBS_LOCK:
            job = JOBS.get(jid)
            if job is None:
                return {'ok': False, 'error': '任务已过期，请重新操作'}
            if job['done']:
                return {'ok': True, 'status': 'done', 'result': job['result']}
        if time.time() >= t_end:
            return {'ok': True, 'status': 'running'}
        time.sleep(0.15)


ROUTES = {
    '/api/start': api_start,
    '/api/moves': api_moves,
    '/api/usermove': api_usermove,
    '/api/job': api_job,
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
        except Exception as e:  # noqa: BLE001
            self._send(200, {'ok': False, 'error': '服务出错: %s' % e})

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print('国际象棋残局研究器已启动 (Ctrl+C 退出)')
    print('  AI 搜索进程数: %d' % E.pool_workers())
    print('  本机访问:   http://127.0.0.1:%d' % port)
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('223.5.5.5', 80))
        lan_ip = s.getsockname()[0]
        s.close()
        print('  局域网访问: http://%s:%d' % (lan_ip, port))
    except OSError:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
