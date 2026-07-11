'use strict';
/* 国际象棋规则引擎 + AI（Web Worker 版，移植自 international/engine.py+server.py）
   走法编码 m = from*64 + to；ep 为可吃过路兵目标格（-1 无） */

const WHITE = 1, BLACK = -1, EMPTY = '.';
const INF = 1e8;
const VALUES = { K: 20000, Q: 900, R: 500, B: 330, N: 320, P: 100 };
const N_OFF = [[-2, -1], [-2, 1], [2, -1], [2, 1], [-1, -2], [1, -2], [-1, 2], [1, 2]];
const K_OFF = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
const B_DIRS = [[-1, -1], [-1, 1], [1, -1], [1, 1]];
const R_DIRS = [[-1, 0], [1, 0], [0, -1], [0, 1]];
const Q_DIRS = B_DIRS.concat(R_DIRS);

const idx = (r, c) => r * 8 + c;
const inBoard = (r, c) => r >= 0 && r < 8 && c >= 0 && c < 8;
const isUpper = p => p >= 'A' && p <= 'Z';
const sideOf = p => p === EMPTY ? 0 : (isUpper(p) ? WHITE : BLACK);
const MV = (f, t) => f * 64 + t;
const MF = m => (m / 64) | 0;
const MT = m => m % 64;

function genPseudo(board, side, ep) {
  const moves = [];
  for (let i = 0; i < 64; i++) {
    const p = board[i];
    if (p === EMPTY || isUpper(p) !== (side === WHITE)) continue;
    const r = (i / 8) | 0, c = i % 8, up = p.toUpperCase();
    if (up === 'P') {
      const fwd = side === WHITE ? -1 : 1;
      const start = side === WHITE ? 6 : 1;
      const nr = r + fwd;
      if (inBoard(nr, c) && board[idx(nr, c)] === EMPTY) {
        moves.push(MV(i, idx(nr, c)));
        if (r === start && board[idx(nr + fwd, c)] === EMPTY)
          moves.push(MV(i, idx(nr + fwd, c)));
      }
      for (const nc of [c - 1, c + 1]) {
        if (!inBoard(nr, nc)) continue;
        const j = idx(nr, nc);
        if (sideOf(board[j]) === -side || (j === ep && board[j] === EMPTY))
          moves.push(MV(i, j));
      }
    } else if (up === 'N') {
      for (const [dr, dc] of N_OFF) {
        const nr = r + dr, nc = c + dc;
        if (inBoard(nr, nc) && sideOf(board[idx(nr, nc)]) !== side)
          moves.push(MV(i, idx(nr, nc)));
      }
    } else if (up === 'K') {
      for (const [dr, dc] of K_OFF) {
        const nr = r + dr, nc = c + dc;
        if (inBoard(nr, nc) && sideOf(board[idx(nr, nc)]) !== side)
          moves.push(MV(i, idx(nr, nc)));
      }
    } else {
      const dirs = up === 'B' ? B_DIRS : up === 'R' ? R_DIRS : Q_DIRS;
      for (const [dr, dc] of dirs) {
        let nr = r + dr, nc = c + dc;
        while (inBoard(nr, nc)) {
          const j = idx(nr, nc), t = board[j];
          if (t === EMPTY) moves.push(MV(i, j));
          else { if (sideOf(t) !== side) moves.push(MV(i, j)); break; }
          nr += dr; nc += dc;
        }
      }
    }
  }
  return moves;
}

/* make 返回 [undo, newEp]; undo = [原子, 被吃子, 过路兵格, 过路兵子] */
function make(board, m, ep) {
  const f = MF(m), t = MT(m);
  const p = board[f], cap = board[t];
  board[t] = p; board[f] = EMPTY;
  let ecapI = -1, ecapP = EMPTY, newEp = -1;
  if (p === 'P') {
    if (t === ep && cap === EMPTY) { ecapI = t + 8; ecapP = board[ecapI]; board[ecapI] = EMPTY; }
    if (f - t === 16) newEp = f - 8;
    if (t < 8) board[t] = 'Q';
  } else if (p === 'p') {
    if (t === ep && cap === EMPTY) { ecapI = t - 8; ecapP = board[ecapI]; board[ecapI] = EMPTY; }
    if (t - f === 16) newEp = f + 8;
    if (t >= 56) board[t] = 'q';
  }
  return [[p, cap, ecapI, ecapP], newEp];
}
function unmake(board, m, undo) {
  const f = MF(m), t = MT(m);
  board[f] = undo[0]; board[t] = undo[1];
  if (undo[2] >= 0) board[undo[2]] = undo[3];
}

function findKing(board, side) {
  return board.indexOf(side === WHITE ? 'K' : 'k');
}

function isAttacked(board, sq, aside) {
  const r = (sq / 8) | 0, c = sq % 8;
  let pawn, knight, king, bq, rq, pr;
  if (aside === WHITE) { pawn = 'P'; knight = 'N'; king = 'K'; bq = 'BQ'; rq = 'RQ'; pr = r + 1; }
  else { pawn = 'p'; knight = 'n'; king = 'k'; bq = 'bq'; rq = 'rq'; pr = r - 1; }
  if (pr >= 0 && pr < 8)
    for (const nc of [c - 1, c + 1])
      if (nc >= 0 && nc < 8 && board[idx(pr, nc)] === pawn) return true;
  for (const [dr, dc] of N_OFF) {
    const nr = r + dr, nc = c + dc;
    if (inBoard(nr, nc) && board[idx(nr, nc)] === knight) return true;
  }
  for (const [dr, dc] of K_OFF) {
    const nr = r + dr, nc = c + dc;
    if (inBoard(nr, nc) && board[idx(nr, nc)] === king) return true;
  }
  for (const [dr, dc] of B_DIRS) {
    let nr = r + dr, nc = c + dc;
    while (inBoard(nr, nc)) {
      const t = board[idx(nr, nc)];
      if (t !== EMPTY) { if (bq.includes(t)) return true; break; }
      nr += dr; nc += dc;
    }
  }
  for (const [dr, dc] of R_DIRS) {
    let nr = r + dr, nc = c + dc;
    while (inBoard(nr, nc)) {
      const t = board[idx(nr, nc)];
      if (t !== EMPTY) { if (rq.includes(t)) return true; break; }
      nr += dr; nc += dc;
    }
  }
  return false;
}

function inCheck(board, side) {
  const kp = findKing(board, side);
  if (kp < 0) return true;
  return isAttacked(board, kp, -side);
}

function legalMoves(board, side, ep) {
  const res = [];
  for (const m of genPseudo(board, side, ep)) {
    const [undo] = make(board, m, ep);
    if (!inCheck(board, side)) res.push(m);
    unmake(board, m, undo);
  }
  return res;
}
function hasLegalMove(board, side, ep) {
  for (const m of genPseudo(board, side, ep)) {
    const [undo] = make(board, m, ep);
    const ok = !inCheck(board, side);
    unmake(board, m, undo);
    if (ok) return true;
  }
  return false;
}

/* ---------------- 评估 ---------------- */
const PST = {
  P: [0,0,0,0,0,0,0,0, 70,70,70,70,70,70,70,70, 35,35,45,50,50,45,35,35,
      14,16,24,32,32,24,16,14, 6,8,14,24,24,14,8,6, 2,4,6,10,10,6,4,2,
      0,0,0,-6,-6,0,0,0, 0,0,0,0,0,0,0,0],
  N: [-40,-25,-15,-10,-10,-15,-25,-40, -25,-10,0,5,5,0,-10,-25, -15,0,10,15,15,10,0,-15,
      -10,5,15,20,20,15,5,-10, -10,5,15,20,20,15,5,-10, -15,0,10,15,15,10,0,-15,
      -25,-10,0,5,5,0,-10,-25, -40,-25,-15,-10,-10,-15,-25,-40],
  B: [-15,-8,-5,-3,-3,-5,-8,-15, -8,2,3,5,5,3,2,-8, -5,3,8,10,10,8,3,-5,
      -3,5,10,12,12,10,5,-3, -3,5,10,12,12,10,5,-3, -5,3,8,10,10,8,3,-5,
      -8,2,3,5,5,3,2,-8, -15,-8,-5,-3,-3,-5,-8,-15],
  R: [4,4,4,6,6,4,4,4, 12,14,14,14,14,14,14,12, 0,2,4,6,6,4,2,0, 0,2,4,6,6,4,2,0,
      0,2,4,6,6,4,2,0, 0,2,4,6,6,4,2,0, 0,2,4,6,6,4,2,0, 2,2,4,8,8,4,2,2],
  Q: [-8,-4,-2,0,0,-2,-4,-8, -4,0,2,4,4,2,0,-4, -2,2,4,6,6,4,2,-2, 0,4,6,8,8,6,4,0,
      0,4,6,8,8,6,4,0, -2,2,4,6,6,4,2,-2, -4,0,2,4,4,2,0,-4, -8,-4,-2,0,0,-2,-4,-8],
  K: [-40,-25,-15,-10,-10,-15,-25,-40, -25,-10,0,8,8,0,-10,-25, -15,0,12,18,18,12,0,-15,
      -10,8,18,24,24,18,8,-10, -10,8,18,24,24,18,8,-10, -15,0,12,18,18,12,0,-15,
      -25,-10,0,8,8,0,-10,-25, -40,-25,-15,-10,-10,-15,-25,-40],
};
const PV = {};
for (const up of Object.keys(PST)) {
  const mat = up === 'K' ? 0 : VALUES[up];
  PV[up] = new Int32Array(64);
  PV[up.toLowerCase()] = new Int32Array(64);
  for (let i = 0; i < 64; i++) {
    PV[up][i] = mat + PST[up][i];
    PV[up.toLowerCase()][i] = -(mat + PST[up][idx(7 - ((i / 8) | 0), i % 8)]);
  }
}

function evaluate(board, side) {
  let s = 0, wk = -1, bk = -1, wmat = 0, bmat = 0;
  for (let i = 0; i < 64; i++) {
    const p = board[i];
    if (p === EMPTY) continue;
    s += PV[p][i];
    if (p === 'K') wk = i;
    else if (p === 'k') bk = i;
    else if (isUpper(p)) wmat += VALUES[p];
    else bmat += VALUES[p.toUpperCase()];
  }
  if (wk >= 0 && bk >= 0) {
    const dist = Math.abs(((wk / 8) | 0) - ((bk / 8) | 0)) + Math.abs(wk % 8 - bk % 8);
    if (bmat <= 330 && wmat - bmat >= 400) {
      const r = (bk / 8) | 0, c = bk % 8;
      s += (3 - Math.min(r, 7 - r, c, 7 - c)) * 14 + (14 - dist) * 5;
    }
    if (wmat <= 330 && bmat - wmat >= 400) {
      const r = (wk / 8) | 0, c = wk % 8;
      s -= (3 - Math.min(r, 7 - r, c, 7 - c)) * 14 + (14 - dist) * 5;
    }
  }
  if (wmat === 0) s = Math.min(s, 0);
  if (bmat === 0) s = Math.max(s, 0);
  return side === WHITE ? s : -s;
}

function insufficientMaterial(board) {
  let minor = 0;
  for (const p of board) {
    if (p === EMPTY || p === 'K' || p === 'k') continue;
    const up = p.toUpperCase();
    if (up === 'B' || up === 'N') { if (++minor > 1) return false; }
    else return false;
  }
  return true;
}
function nullOk(board, side) {
  const pieces = side === WHITE ? 'QRBN' : 'qrbn';
  return board.some(p => pieces.includes(p));
}

/* ---------------- 搜索 ---------------- */
class Timeout extends Error {}
let TT = new Map();

class Searcher {
  constructor(deadline, seedPath, histcnt) {
    this.deadline = deadline;
    this.nodes = 0;
    this.path = seedPath ? seedPath.slice() : [];
    this.histcnt = histcnt || new Map();
    this.killers = Array.from({ length: 128 }, () => [0, 0]);
    this.hist = new Map();
  }
  tick() {
    if ((++this.nodes & 511) === 0 && Date.now() > this.deadline) throw new Timeout();
  }
  quiesce(board, side, ep, alpha, beta, ply) {
    this.tick();
    if (board.indexOf(side === WHITE ? 'K' : 'k') < 0) return -(INF - ply);
    const stand = evaluate(board, side);
    if (stand >= beta) return stand;
    if (stand > alpha) alpha = stand;
    const caps = genPseudo(board, side, ep).filter(m =>
      board[MT(m)] !== EMPTY || (MT(m) === ep && board[MF(m)].toUpperCase() === 'P'));
    const vval = m => board[MT(m)] !== EMPTY ? VALUES[board[MT(m)].toUpperCase()] : VALUES.P;
    caps.sort((a, b) =>
      (VALUES[board[MF(a)].toUpperCase()] - 10 * vval(a)) -
      (VALUES[board[MF(b)].toUpperCase()] - 10 * vval(b)));
    for (const m of caps) {
      const victim = board[MT(m)];
      if (victim === 'K' || victim === 'k') return INF - ply;
      if (stand + vval(m) + 200 < alpha) continue;
      const [undo, nep] = make(board, m, ep);
      const sc = -this.quiesce(board, -side, nep, -beta, -alpha, ply + 1);
      unmake(board, m, undo);
      if (sc > alpha) { alpha = sc; if (alpha >= beta) break; }
    }
    return alpha;
  }
  negamax(board, side, ep, depth, alpha, beta, ply, canNull) {
    this.tick();
    if (board.indexOf(side === WHITE ? 'K' : 'k') < 0) return -(INF - ply);
    const inChk = inCheck(board, side);
    const bstr = board.join('');
    // 树内重复 = 和棋（国际象棋无长将判负）
    for (let j = this.path.length - 1; j >= 0; j--) {
      const e = this.path[j];
      if (e[2] === side && e[0] === bstr && e[1] === ep) return 0;
    }
    if (this.histcnt.size &&
        (this.histcnt.get(bstr + (side === WHITE ? 'w' : 'b') + ep) || 0) >= 2) return 0;
    let d = depth;
    if (inChk && ply < 32) d += 1;
    if (d <= 0) return this.quiesce(board, side, ep, alpha, beta, ply);
    const key = bstr + side + ',' + ep;
    const hit = TT.get(key);
    if (hit && hit[0] >= d) {
      const hs = hit[1], hf = hit[2];
      if (hf === 0) return hs;
      if (hf === 1 && hs >= beta) return hs;
      if (hf === 2 && hs <= alpha) return hs;
    }
    this.path.push([bstr, ep, side, inChk]);
    try {
      return this._body(board, side, ep, d, alpha, beta, ply, canNull, inChk, key, hit);
    } finally {
      this.path.pop();
    }
  }
  _body(board, side, ep, depth, alpha, beta, ply, canNull, inChk, key, hit) {
    if (canNull && !inChk && depth >= 3 && beta < INF - 1000 && nullOk(board, side)) {
      const sc = -this.negamax(board, -side, -1, depth - 3, -beta, -beta + 1, ply + 1, false);
      if (sc >= beta) return sc;
    }
    const ttm = hit ? hit[3] : 0;
    const ks = ply < 128 ? this.killers[ply] : [0, 0];
    const hist = this.hist;
    const okey = m => {
      if (m === ttm) return -1e7;
      const v = board[MT(m)];
      if (v !== EMPTY)
        return Math.min(VALUES[board[MF(m)].toUpperCase()] - 10 * VALUES[v.toUpperCase()], 80000);
      if (m === ks[0]) return 90000;
      if (m === ks[1]) return 91000;
      return 1e6 - Math.min(hist.get(board[MF(m)] + MT(m)) || 0, 800000);
    };
    const moves = genPseudo(board, side, ep);
    moves.sort((a, b) => okey(a) - okey(b));
    let best = -INF, bestm = 0;
    const a0 = alpha;
    let mi = 0;
    for (const m of moves) {
      const vict = board[MT(m)];
      if (vict === 'K' || vict === 'k') return INF - ply;
      const [undo, nep] = make(board, m, ep);
      const quiet = undo[1] === EMPTY && undo[2] < 0;
      let sc;
      if (mi >= 3 && depth >= 3 && quiet && !inChk && alpha > -INF) {
        sc = -this.negamax(board, -side, nep, depth - 2, -alpha - 1, -alpha, ply + 1, true);
        if (sc > alpha)
          sc = -this.negamax(board, -side, nep, depth - 1, -beta, -alpha, ply + 1, true);
      } else {
        sc = -this.negamax(board, -side, nep, depth - 1, -beta, -alpha, ply + 1, true);
      }
      unmake(board, m, undo);
      mi++;
      if (sc > best) {
        best = sc; bestm = m;
        if (best > alpha) {
          alpha = best;
          if (alpha >= beta) {
            if (quiet && ply < 128) {
              if (ks[0] !== m) { ks[1] = ks[0]; ks[0] = m; }
              const hk = board[MF(m)] + MT(m);
              hist.set(hk, (hist.get(hk) || 0) + depth * depth);
            }
            break;
          }
        }
      }
    }
    if (!bestm) return inChk ? -(INF - ply) : 0;   // 将死 / 逼和
    if (best <= -(INF - ply - 4) && !inChk && !hasLegalMove(board, side, ep)) return 0;
    const flag = best >= beta ? 1 : (best <= a0 ? 2 : 0);
    if (TT.size > 1500000) TT.clear();
    TT.set(key, [depth, best, flag, bestm]);
    return best;
  }
}

function pvWalk(board, side, ep, limit) {
  const pv = [];
  const b = board.slice();
  let s = side, e = ep;
  const seen = new Set();
  for (let i = 0; i < (limit || 24); i++) {
    const key = b.join('') + s + ',' + e;
    if (seen.has(key)) break;
    seen.add(key);
    const hit = TT.get(key);
    if (!hit || !hit[3]) break;
    const m = hit[3];
    if (!genPseudo(b, s, e).includes(m)) break;
    const [, nep] = make(b, m, e);
    e = nep;
    pv.push(m);
    s = -s;
  }
  return pv;
}

function stableMinDepth(budget) {
  if (budget >= 192000) return 13;
  if (budget >= 48000) return 11;
  return 9;
}

function searchBest(board0, side, ep, timeMs, penalty, drawMoves, history) {
  let deadline = Date.now() + timeMs;
  const board = board0.slice();
  const moves = legalMoves(board, side, ep);
  if (!moves.length) return null;
  penalty = penalty || new Map();
  drawMoves = drawMoves || new Set();
  const histcnt = new Map();
  for (const k of (history || [])) histcnt.set(k, (histcnt.get(k) || 0) + 1);
  const draws = moves.filter(m => drawMoves.has(m));
  const rest = moves.filter(m => !drawMoves.has(m));
  if (!rest.length) return { move: draws[0], score: 0, depth: 1, pv: [] };
  if (rest.length === 1 && !draws.length)
    return { move: rest[0], score: 0, depth: 1, pv: [] };
  if (rest.length <= 3)
    deadline = Math.min(deadline, Date.now() + timeMs * 0.25 * rest.length);
  const vord = m => board[MT(m)] === EMPTY ? 1e6 :
    VALUES[board[MF(m)].toUpperCase()] - 10 * VALUES[board[MT(m)].toUpperCase()];
  rest.sort((a, b) => vord(a) - vord(b));
  const seed = [[board.join(''), ep, side, inCheck(board, side)]];
  const S = new Searcher(deadline, seed, histcnt);
  const minD = stableMinDepth(deadline - Date.now());
  const scores = new Map();
  let best = rest[0], bestSc = -INF, reached = 0, stable = 0;
  for (let depth = 1; depth < 26; depth++) {
    let curBest = 0, curSc = -INF;
    try {
      for (const m of rest) {
        const [undo, nep] = make(board, m, ep);
        const sc = -S.negamax(board, -side, nep, depth - 1, -INF, -curSc, 1, true)
                   - (penalty.get(m) || 0);
        unmake(board, m, undo);
        scores.set(m, sc);
        if (sc > curSc) { curSc = sc; curBest = m; }
      }
      stable = curBest === best ? stable + 1 : 1;
      best = curBest; bestSc = curSc; reached = depth;
      rest.sort((a, b) => (scores.get(b) || -INF) - (scores.get(a) || -INF));
      if (Math.abs(bestSc) > INF - 1000 && depth >= 4) break;
      if (depth >= minD && stable >= 3) {
        let second = -INF;
        for (const [m, s] of scores) if (m !== best && s > second) second = s;
        if (bestSc - second > 250 || stable >= 5) break;
      }
    } catch (e) {
      if (!(e instanceof Timeout)) throw e;
      break;
    }
  }
  if (draws.length && bestSc < 0)
    return { move: draws[0], score: 0, depth: reached, pv: [] };
  const bb = board.slice();
  const [, nep] = make(bb, best, ep);
  return { move: best, score: bestSc, depth: reached,
           pv: [best].concat(pvWalk(bb, -side, nep)) };
}

/* ---------------- 规则辅助 ---------------- */
const keyOf = (board, side, ep) => board.join('') + (side === WHITE ? 'w' : 'b') + ep;
const countIn = (arr, x) => { let n = 0; for (const v of arr) if (v === x) n++; return n; };

function repetitionPenalties(board, side, ep, history) {
  const pen = new Map();
  if (!history.length) return pen;
  for (const m of legalMoves(board, side, ep)) {
    const [undo, nep] = make(board, m, ep);
    if (countIn(history, keyOf(board, -side, nep)) >= 1) pen.set(m, 45);
    unmake(board, m, undo);
  }
  return pen;
}
function drawMovesOf(board, side, ep, history) {
  const dm = new Set();
  for (const m of legalMoves(board, side, ep)) {
    const [undo, nep] = make(board, m, ep);
    if (countIn(history, keyOf(board, -side, nep)) >= 2) dm.add(m);
    unmake(board, m, undo);
  }
  return dm;
}
function gameEndAfter(board, ep, moverSide, gaveCheck) {
  if (!legalMoves(board, -moverSide, ep).length) {
    if (gaveCheck) {
      const winner = moverSide === WHITE ? 'white' : 'black';
      return [winner, (winner === 'white' ? '白方' : '黑方') + '获胜！对方被将死'];
    }
    return ['draw', '逼和（对方无子可动且未被将军），和棋'];
  }
  if (insufficientMaterial(board)) return ['draw', '子力不足以将死，和棋'];
  return [null, ''];
}

/* ---------------- 主变例缓存 ---------------- */
const PV_CACHE = new Map();
function storePv(boardStr, side, ep, pv, reached) {
  if (!pv || !pv.length) return;
  const b = boardStr.split('');
  let s = side, e = ep;
  if (PV_CACHE.size > 2000) PV_CACHE.clear();
  for (let i = 0; i < pv.length; i++) {
    const backing = reached - i;
    if (backing < 6) break;
    PV_CACHE.set(keyOf(b, s, e), [pv[i], backing]);
    const [, nep] = make(b, pv[i], e);
    e = nep;
    s = -s;
  }
}
function probePv(board, side, ep, history) {
  const hit = PV_CACHE.get(keyOf(board, side, ep));
  if (!hit) return null;
  const [mv, backing] = hit;
  if (!legalMoves(board, side, ep).includes(mv)) return null;
  const [undo, nep] = make(board, mv, ep);
  const key2 = keyOf(board, -side, nep);
  unmake(board, mv, undo);
  if (countIn(history, key2) >= 2) return null;
  return [mv, backing];
}

/* ---------------- 摆盘校验 ---------------- */
const NAME = { K: '王', Q: '后', R: '车', B: '象', N: '马', P: '兵' };
const COUNTS = { K: 1, Q: 9, R: 10, B: 10, N: 10, P: 8 };

function validateSetup(board) {
  const cnt = {};
  for (const p of board) if (p !== EMPTY) cnt[p] = (cnt[p] || 0) + 1;
  if ((cnt['K'] || 0) !== 1) return '白方必须有且只有一个王';
  if ((cnt['k'] || 0) !== 1) return '黑方必须有且只有一个王';
  for (const up of Object.keys(COUNTS)) {
    if ((cnt[up] || 0) > COUNTS[up]) return '白方' + NAME[up] + '数量超过上限(' + COUNTS[up] + ')';
    if ((cnt[up.toLowerCase()] || 0) > COUNTS[up]) return '黑方' + NAME[up] + '数量超过上限(' + COUNTS[up] + ')';
  }
  for (let i = 0; i < 64; i++)
    if ((board[i] === 'P' || board[i] === 'p') && (i < 8 || i >= 56))
      return '兵不能放在第一或第八横排';
  const wk = board.indexOf('K'), bk = board.indexOf('k');
  if (Math.abs(((wk / 8) | 0) - ((bk / 8) | 0)) <= 1 && Math.abs(wk % 8 - bk % 8) <= 1)
    return '两王不能相邻';
  if (inCheck(board, BLACK)) return '白方先行：开始时黑方不能已处于被将军状态';
  if (!legalMoves(board, WHITE, -1).length) return '白方无棋可走，无法开始';
  return null;
}

/* ---------------- 接口处理 ---------------- */
function parseBoard(data) {
  const b = data.board;
  if (typeof b !== 'string' || b.length !== 64) throw new Error('棋盘数据格式错误');
  return b.split('');
}
const parseEp = data => {
  const ep = Number(data.ep);
  return Number.isInteger(ep) && ep >= 0 && ep < 64 ? ep : -1;
};
const clampTime = data => Math.min(Math.max(Number(data.time) || 16, 0.3), 300) * 1000;
const pairMoves = ms => ms.map(m => [MF(m), MT(m)]);

function aiReply(board, ep, history, tMs) {
  let mv, depth;
  const probe = probePv(board, BLACK, ep, history);
  if (probe) { mv = probe[0]; depth = probe[1]; }
  else {
    const boardBefore = board.join('');
    const pen = repetitionPenalties(board, BLACK, ep, history);
    const dm = drawMovesOf(board, BLACK, ep, history);
    const r = searchBest(board, BLACK, ep, tMs, pen, dm, history);
    mv = r.move; depth = r.depth;
    storePv(boardBefore, BLACK, ep, r.pv, r.depth);
  }
  const [, newEp] = make(board, mv, ep);
  const aiKey = keyOf(board, WHITE, newEp);
  const checkW = inCheck(board, WHITE);
  let [over, msg] = gameEndAfter(board, newEp, BLACK, checkW);
  if (!over && countIn(history, aiKey) >= 2) { over = 'draw'; msg = '同一局面第三次出现，判和'; }
  if (!over && checkW) msg = '黑方将军！请应将';
  return { aiMove: { from: MF(mv), to: MT(mv) }, aiKey, checkWhite: checkW, depth,
           board: board.join(''), ep: newEp, gameOver: over, message: msg };
}

function applyUserMove(board, ep, history, side, frm, to) {
  const sname = side === WHITE ? '白方' : '黑方';
  if (sideOf(board[frm]) !== side) return ['请移动' + sname + '棋子', ep];
  const m = MV(frm, to);
  if (!legalMoves(board, side, ep).includes(m)) return ['不符合走棋规则', ep];
  const [, newEp] = make(board, m, ep);
  return [null, newEp];
}

const HANDLERS = {
  '/api/start': data => {
    const board = parseBoard(data);
    const err = validateSetup(board);
    return err ? { ok: false, error: err } : { ok: true };
  },
  '/api/moves': data => {
    const board = parseBoard(data), ep = parseEp(data);
    const side = data.side === 'b' ? BLACK : WHITE;
    return { ok: true, moves: pairMoves(legalMoves(board, side, ep)),
             check: inCheck(board, side) };
  },
  '/api/hint': data => {
    const board = parseBoard(data), ep = parseEp(data);
    const history = data.history || [];
    const side = data.side === 'b' ? BLACK : WHITE;
    const probe = probePv(board, side, ep, history);
    if (probe)
      return { ok: true, from: MF(probe[0]), to: MT(probe[0]), score: 0,
               depth: probe[1], cached: true };
    const pen = repetitionPenalties(board, side, ep, history);
    const dm = drawMovesOf(board, side, ep, history);
    const r = searchBest(board, side, ep, clampTime(data), pen, dm, history);
    if (!r) return { ok: false, error: '当前没有可走的棋' };
    storePv(board.join(''), side, ep, r.pv, r.depth);
    return { ok: true, from: MF(r.move), to: MT(r.move), score: r.score, depth: r.depth };
  },
  '/api/move': data => {
    const board = parseBoard(data), ep = parseEp(data);
    const history = data.history || [];
    const [err, newEp] = applyUserMove(board, ep, history, WHITE, data.from | 0, data.to | 0);
    if (err) return { ok: false, error: err };
    const playerKey = keyOf(board, BLACK, newEp);
    const checkB = inCheck(board, BLACK);
    const resp = { ok: true, playerKey, checkBlack: checkB, aiMove: null,
                   board: board.join(''), ep: newEp };
    let [over, msg] = gameEndAfter(board, newEp, WHITE, checkB);
    if (!over && countIn(history, playerKey) >= 2) { over = 'draw'; msg = '同一局面第三次出现，判和'; }
    if (over) { resp.gameOver = over; resp.message = msg; return resp; }
    Object.assign(resp, aiReply(board, newEp, history.concat([playerKey]), clampTime(data)));
    return resp;
  },
  '/api/usermove': data => {
    const board = parseBoard(data), ep = parseEp(data);
    const history = data.history || [];
    const side = data.side === 'b' ? BLACK : WHITE;
    const [err, newEp] = applyUserMove(board, ep, history, side, data.from | 0, data.to | 0);
    if (err) return { ok: false, error: err };
    const chk = inCheck(board, -side);
    const key = keyOf(board, -side, newEp);
    let [over, msg] = gameEndAfter(board, newEp, side, chk);
    if (!over && countIn(history, key) >= 2) { over = 'draw'; msg = '同一局面第三次出现，判和'; }
    return { ok: true, board: board.join(''), key, ep: newEp, check: chk,
             gameOver: over, message: msg };
  },
  '/api/aimove': data => {
    const board = parseBoard(data), ep = parseEp(data);
    const history = data.history || [];
    if (!legalMoves(board, BLACK, ep).length) return { ok: false, error: '黑方无棋可走' };
    const resp = { ok: true };
    Object.assign(resp, aiReply(board, ep, history, clampTime(data)));
    return resp;
  },
};

if (typeof self !== 'undefined' && typeof postMessage === 'function' &&
    typeof document === 'undefined') {
  self.onmessage = e => {
    const { id, path, data } = e.data;
    let result;
    try {
      const fn = HANDLERS[path];
      result = fn ? fn(data || {}) : { ok: false, error: '未知接口 ' + path };
    } catch (err) {
      result = { ok: false, error: String((err && err.message) || err) };
    }
    self.postMessage({ id, result });
  };
} else if (typeof module !== 'undefined' && module.exports) {
  module.exports = { HANDLERS, genPseudo, legalMoves, searchBest, inCheck, make, unmake,
                     evaluate, keyOf, MV, MF, MT, WHITE, BLACK, validateSetup,
                     insufficientMaterial };
}
