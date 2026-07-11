'use strict';
/* 中国象棋规则引擎 + AI（Web Worker 版，移植自 Python engine.py/server.py）
   走法编码: m = from*90 + to */

const RED = 1, BLACK = -1, EMPTY = '.';
const INF = 1e8;
const VALUES = { K: 10000, R: 900, C: 450, N: 400, P: 100, A: 110, B: 110 };
const K_DIRS = [[-1, 0], [1, 0], [0, -1], [0, 1]];
const A_DIRS = [[-1, -1], [-1, 1], [1, -1], [1, 1]];
const N_OFF = [[-2, -1, -1, 0], [-2, 1, -1, 0], [2, -1, 1, 0], [2, 1, 1, 0],
               [-1, -2, 0, -1], [1, -2, 0, -1], [-1, 2, 0, 1], [1, 2, 0, 1]];
const B_OFF = [[-2, -2, -1, -1], [-2, 2, -1, 1], [2, -2, 1, -1], [2, 2, 1, 1]];

const idx = (r, c) => r * 9 + c;
const inBoard = (r, c) => r >= 0 && r < 10 && c >= 0 && c < 9;
const inPalace = (r, c, s) =>
  c >= 3 && c <= 5 && (s === RED ? (r >= 7 && r <= 9) : (r >= 0 && r <= 2));
const isUpper = p => p >= 'A' && p <= 'Z';
const sideOf = p => p === EMPTY ? 0 : (isUpper(p) ? RED : BLACK);
const MV = (f, t) => f * 90 + t;
const MF = m => (m / 90) | 0;
const MT = m => m % 90;

/* ---------------- 走法生成 ---------------- */
function genPseudo(board, side) {
  const moves = [];
  for (let i = 0; i < 90; i++) {
    const p = board[i];
    if (p === EMPTY || (isUpper(p)) !== (side === RED)) continue;
    const r = (i / 9) | 0, c = i % 9, up = p.toUpperCase();
    if (up === 'K') {
      for (const [dr, dc] of K_DIRS) {
        const nr = r + dr, nc = c + dc;
        if (inPalace(nr, nc, side) && sideOf(board[idx(nr, nc)]) !== side)
          moves.push(MV(i, idx(nr, nc)));
      }
      for (const dr of [-1, 1]) {           // 飞将照面
        let nr = r + dr;
        while (nr >= 0 && nr <= 9) {
          const t = board[idx(nr, c)];
          if (t !== EMPTY) {
            if (t.toUpperCase() === 'K') moves.push(MV(i, idx(nr, c)));
            break;
          }
          nr += dr;
        }
      }
    } else if (up === 'A') {
      for (const [dr, dc] of A_DIRS) {
        const nr = r + dr, nc = c + dc;
        if (inPalace(nr, nc, side) && sideOf(board[idx(nr, nc)]) !== side)
          moves.push(MV(i, idx(nr, nc)));
      }
    } else if (up === 'B') {
      for (const [dr, dc, er, ec] of B_OFF) {
        const nr = r + dr, nc = c + dc;
        if (!inBoard(nr, nc)) continue;
        if (side === RED ? nr < 5 : nr > 4) continue;         // 不过河
        if (board[idx(r + er, c + ec)] !== EMPTY) continue;   // 塞象眼
        if (sideOf(board[idx(nr, nc)]) !== side) moves.push(MV(i, idx(nr, nc)));
      }
    } else if (up === 'N') {
      for (const [dr, dc, lr, lc] of N_OFF) {
        const nr = r + dr, nc = c + dc;
        if (!inBoard(nr, nc)) continue;
        if (board[idx(r + lr, c + lc)] !== EMPTY) continue;   // 蹩马腿
        if (sideOf(board[idx(nr, nc)]) !== side) moves.push(MV(i, idx(nr, nc)));
      }
    } else if (up === 'R') {
      for (const [dr, dc] of K_DIRS) {
        let nr = r + dr, nc = c + dc;
        while (inBoard(nr, nc)) {
          const j = idx(nr, nc), t = board[j];
          if (t === EMPTY) moves.push(MV(i, j));
          else { if (sideOf(t) !== side) moves.push(MV(i, j)); break; }
          nr += dr; nc += dc;
        }
      }
    } else if (up === 'C') {
      for (const [dr, dc] of K_DIRS) {
        let nr = r + dr, nc = c + dc, jumped = false;
        while (inBoard(nr, nc)) {
          const j = idx(nr, nc), t = board[j];
          if (!jumped) {
            if (t === EMPTY) moves.push(MV(i, j));
            else jumped = true;
          } else if (t !== EMPTY) {
            if (sideOf(t) !== side) moves.push(MV(i, j));
            break;
          }
          nr += dr; nc += dc;
        }
      }
    } else {  // P
      const fwd = side === RED ? -1 : 1;
      const crossed = side === RED ? r <= 4 : r >= 5;
      const cand = [[r + fwd, c]];
      if (crossed) { cand.push([r, c - 1]); cand.push([r, c + 1]); }
      for (const [nr, nc] of cand) {
        if (inBoard(nr, nc) && sideOf(board[idx(nr, nc)]) !== side)
          moves.push(MV(i, idx(nr, nc)));
      }
    }
  }
  return moves;
}

function make(board, m) {
  const f = MF(m), t = MT(m), cap = board[t];
  board[t] = board[f]; board[f] = EMPTY;
  return cap;
}
function unmake(board, m, cap) {
  const f = MF(m), t = MT(m);
  board[f] = board[t]; board[t] = cap;
}

function findKing(board, side) {
  const k = side === RED ? 'K' : 'k';
  return board.indexOf(k);
}

function isAttacked(board, sq, aside) {
  const r = (sq / 9) | 0, c = sq % 9;
  let rook, cannon, knight, king;
  if (aside === RED) {
    rook = 'R'; cannon = 'C'; knight = 'N'; king = 'K';
    if (r + 1 <= 9 && board[idx(r + 1, c)] === 'P') return true;
    if (r <= 4) for (const nc of [c - 1, c + 1])
      if (nc >= 0 && nc < 9 && board[idx(r, nc)] === 'P') return true;
  } else {
    rook = 'r'; cannon = 'c'; knight = 'n'; king = 'k';
    if (r - 1 >= 0 && board[idx(r - 1, c)] === 'p') return true;
    if (r >= 5) for (const nc of [c - 1, c + 1])
      if (nc >= 0 && nc < 9 && board[idx(r, nc)] === 'p') return true;
  }
  for (const [dr, dc] of N_OFF) {
    const nr = r + dr, nc = c + dc;
    if (!inBoard(nr, nc) || board[idx(nr, nc)] !== knight) continue;
    let lr, lc;
    if (Math.abs(dr) === 2) { lr = r + dr + (dr > 0 ? -1 : 1); lc = c + dc; }
    else { lr = r + dr; lc = c + dc + (dc > 0 ? -1 : 1); }
    if (board[idx(lr, lc)] === EMPTY) return true;
  }
  for (const [dr, dc] of K_DIRS) {
    let nr = r + dr, nc = c + dc, blocked = false;
    while (inBoard(nr, nc)) {
      const t = board[idx(nr, nc)];
      if (t !== EMPTY) {
        if (!blocked) {
          if (t === rook) return true;
          if (t === king && dc === 0) return true;   // 王照面
          blocked = true;
        } else {
          if (t === cannon) return true;
          break;
        }
      }
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

function legalMoves(board, side) {
  const res = [];
  for (const m of genPseudo(board, side)) {
    const cap = make(board, m);
    if (!inCheck(board, side)) res.push(m);
    unmake(board, m, cap);
  }
  return res;
}

/* ---------------- 评估 ---------------- */
function _pv(up, r, c) {
  let v = VALUES[up];
  if (up === 'P') {
    if (r <= 4) {
      v += 40 + (4 - r) * 12;
      if (c >= 3 && c <= 5 && r <= 3) v += 15;
      if (r === 0) v -= 20;
    }
  } else if (up === 'R') { if (c >= 3 && c <= 5) v += 8; }
  else if (up === 'C') { if (c === 4) v += 12; }
  else if (up === 'N') { v += (9 - r) * 2; if (c === 0 || c === 8) v -= 12; }
  return v;
}
const PV = {};
for (const up of Object.keys(VALUES)) {
  PV[up] = new Int32Array(90);
  PV[up.toLowerCase()] = new Int32Array(90);
  for (let i = 0; i < 90; i++) {
    const r = (i / 9) | 0, c = i % 9;
    PV[up][i] = _pv(up, r, c);
    PV[up.toLowerCase()][i] = -_pv(up, 9 - r, c);
  }
}
const PROX_W = { R: 3, N: 4, P: 5 };

function evaluate(board, side) {
  let s = 0, rk = -1, bk = -1;
  const redAtt = [], blkAtt = [];
  for (let i = 0; i < 90; i++) {
    const p = board[i];
    if (p === EMPTY) continue;
    s += PV[p][i];
    if (p === 'K') rk = i;
    else if (p === 'k') bk = i;
    else if ('RNCP'.includes(p)) redAtt.push(i);
    else if ('rncp'.includes(p)) blkAtt.push(i);
  }
  if (rk >= 0 && bk >= 0) {
    const bkr = (bk / 9) | 0, bkc = bk % 9, rkr = (rk / 9) | 0, rkc = rk % 9;
    for (const i of redAtt) {
      const w = PROX_W[board[i]];
      if (w) {
        const d = Math.abs(((i / 9) | 0) - bkr) + Math.abs(i % 9 - bkc);
        s += Math.max(0, 10 - d) * w;
      }
    }
    for (const i of blkAtt) {
      const w = PROX_W[board[i].toUpperCase()];
      if (w) {
        const d = Math.abs(((i / 9) | 0) - rkr) + Math.abs(i % 9 - rkc);
        s -= Math.max(0, 10 - d) * w;
      }
    }
  }
  if (!redAtt.length) s = Math.min(s, 0);   // 无攻击子力最多求和
  if (!blkAtt.length) s = Math.max(s, 0);
  return side === RED ? s : -s;
}

function hasAttacker(board, side) {
  const pieces = side === RED ? 'RNCP' : 'rncp';
  return board.some(p => pieces.includes(p));
}

/* ---------------- 搜索 ---------------- */
class Timeout extends Error {}
let TT = new Map();          // 跨请求保留的置换表（树缓存）

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
  quiesce(board, side, alpha, beta, ply) {
    this.tick();
    if (board.indexOf(side === RED ? 'K' : 'k') < 0) return -(INF - ply);
    const stand = evaluate(board, side);
    if (stand >= beta) return stand;
    if (stand > alpha) alpha = stand;
    const caps = genPseudo(board, side).filter(m => board[MT(m)] !== EMPTY);
    caps.sort((a, b) =>
      (VALUES[board[MF(a)].toUpperCase()] - 10 * VALUES[board[MT(a)].toUpperCase()]) -
      (VALUES[board[MF(b)].toUpperCase()] - 10 * VALUES[board[MT(b)].toUpperCase()]));
    for (const m of caps) {
      const victim = board[MT(m)];
      if (victim === 'K' || victim === 'k') return INF - ply;
      if (stand + VALUES[victim.toUpperCase()] + 200 < alpha) continue;
      const cap = make(board, m);
      const sc = -this.quiesce(board, -side, -beta, -alpha, ply + 1);
      unmake(board, m, cap);
      if (sc > alpha) { alpha = sc; if (alpha >= beta) break; }
    }
    return alpha;
  }
  negamax(board, side, depth, alpha, beta, ply, canNull) {
    this.tick();
    if (board.indexOf(side === RED ? 'K' : 'k') < 0) return -(INF - ply);
    const inChk = inCheck(board, side);
    const bstr = board.join('');
    // 树内重复：长将判负 / 循环判和
    for (let j = this.path.length - 1; j >= 0; j--) {
      const e = this.path[j];
      if (e[1] === side && e[0] === bstr) {
        const cycle = this.path.slice(j);
        let iKept = true, theyKept = inChk;
        for (const x of cycle) {
          if (x[1] === -side && !x[2]) iKept = false;
          if (x[1] === side && !x[2]) theyKept = false;
        }
        if (iKept && !theyKept) return -(INF - ply);
        if (theyKept && !iKept) return INF - ply;
        return 0;
      }
    }
    // 与对局历史三次重复：按长将裁决语义计分
    if (this.histcnt.size &&
        (this.histcnt.get(bstr + (side === RED ? 'r' : 'b')) || 0) >= 2) {
      let mineAll = inChk, theirsAll = false, hasOpp = false;
      for (const x of this.path) {
        if (x[1] === side && !x[2]) mineAll = false;
        if (x[1] === -side) { hasOpp = true; if (!x[2]) theirsAll = false; }
      }
      theirsAll = hasOpp && this.path.filter(x => x[1] === -side).every(x => x[2]);
      if (mineAll && !theirsAll) return INF - ply;
      if (theirsAll && !mineAll) return -(INF - ply);
      return 0;
    }
    let d = depth;
    if (inChk && ply < 32) d += 1;              // 将军延伸
    if (d <= 0) return this.quiesce(board, side, alpha, beta, ply);
    const key = bstr + side;
    const hit = TT.get(key);
    if (hit && hit[0] >= d) {
      const hs = hit[1], hf = hit[2];
      if (hf === 0) return hs;
      if (hf === 1 && hs >= beta) return hs;
      if (hf === 2 && hs <= alpha) return hs;
    }
    this.path.push([bstr, side, inChk]);
    try {
      return this._body(board, side, d, alpha, beta, ply, canNull, inChk, key, hit);
    } finally {
      this.path.pop();
    }
  }
  _body(board, side, depth, alpha, beta, ply, canNull, inChk, key, hit) {
    if (canNull && !inChk && depth >= 3 && beta < INF - 1000 && hasAttacker(board, side)) {
      const sc = -this.negamax(board, -side, depth - 3, -beta, -beta + 1, ply + 1, false);
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
    const moves = genPseudo(board, side);
    moves.sort((a, b) => okey(a) - okey(b));
    let best = -INF, bestm = 0;
    const a0 = alpha;
    let mi = 0;
    for (const m of moves) {
      const vict = board[MT(m)];
      if (vict === 'K' || vict === 'k') return INF - ply;
      const cap = make(board, m);
      let sc;
      if (mi >= 3 && depth >= 3 && cap === EMPTY && !inChk && alpha > -INF) {
        sc = -this.negamax(board, -side, depth - 2, -alpha - 1, -alpha, ply + 1, true);
        if (sc > alpha)
          sc = -this.negamax(board, -side, depth - 1, -beta, -alpha, ply + 1, true);
      } else {
        sc = -this.negamax(board, -side, depth - 1, -beta, -alpha, ply + 1, true);
      }
      unmake(board, m, cap);
      mi++;
      if (sc > best) {
        best = sc; bestm = m;
        if (best > alpha) {
          alpha = best;
          if (alpha >= beta) {
            if (cap === EMPTY && ply < 128) {
              if (ks[0] !== m) { ks[1] = ks[0]; ks[0] = m; }
              const hk = board[MF(m)] + MT(m);
              hist.set(hk, (hist.get(hk) || 0) + depth * depth);
            }
            break;
          }
        }
      }
    }
    if (!bestm) return -(INF - ply);
    const flag = best >= beta ? 1 : (best <= a0 ? 2 : 0);
    if (TT.size > 1500000) TT.clear();
    TT.set(key, [depth, best, flag, bestm]);
    return best;
  }
}

function pvWalk(board, side, limit) {
  const pv = [];
  const b = board.slice();
  let s = side;
  const seen = new Set();
  for (let i = 0; i < (limit || 24); i++) {
    const key = b.join('') + s;
    if (seen.has(key)) break;
    seen.add(key);
    const e = TT.get(key);
    if (!e || !e[3]) break;
    const m = e[3];
    if (!genPseudo(b, s).includes(m)) break;
    make(b, m);
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

function searchBest(board0, side, timeMs, banned, penalty, drawMoves, history) {
  let deadline = Date.now() + timeMs;
  const board = board0.slice();
  const moves = legalMoves(board, side);
  if (!moves.length) return null;
  banned = banned || new Set();
  penalty = penalty || new Map();
  drawMoves = drawMoves || new Set();
  const histcnt = new Map();
  for (const k of (history || [])) histcnt.set(k, (histcnt.get(k) || 0) + 1);
  let allowed = moves.filter(m => !banned.has(m));
  if (!allowed.length) allowed = moves;
  const draws = allowed.filter(m => drawMoves.has(m));
  const rest = allowed.filter(m => !drawMoves.has(m));
  if (!rest.length) return { move: draws[0], score: 0, depth: 1, pv: [] };
  if (rest.length === 1 && !draws.length)
    return { move: rest[0], score: 0, depth: 1, pv: [] };
  if (rest.length <= 3)
    deadline = Math.min(deadline, Date.now() + timeMs * 0.25 * rest.length);
  rest.sort((a, b) => {
    const va = board[MT(a)] === EMPTY ? 1e6 :
      VALUES[board[MF(a)].toUpperCase()] - 10 * VALUES[board[MT(a)].toUpperCase()];
    const vb = board[MT(b)] === EMPTY ? 1e6 :
      VALUES[board[MF(b)].toUpperCase()] - 10 * VALUES[board[MT(b)].toUpperCase()];
    return va - vb;
  });
  const seed = [[board.join(''), side, inCheck(board, side)]];
  const S = new Searcher(deadline, seed, histcnt);
  const minD = stableMinDepth(deadline - Date.now());
  const scores = new Map();
  let best = rest[0], bestSc = -INF, reached = 0, stable = 0;
  for (let depth = 1; depth < 26; depth++) {
    let curBest = 0, curSc = -INF;
    try {
      for (const m of rest) {
        const cap = make(board, m);
        const sc = -S.negamax(board, -side, depth - 1, -INF, -curSc, 1, true)
                   - (penalty.get(m) || 0);
        unmake(board, m, cap);
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
  make(bb, best);
  return { move: best, score: bestSc, depth: reached, pv: [best].concat(pvWalk(bb, -side)) };
}

/* ---------------- 规则辅助（对应原 server.py） ---------------- */
const keyOf = (board, side) => board.join('') + (side === RED ? 'r' : 'b');
const countIn = (arr, x) => { let n = 0; for (const v of arr) if (v === x) n++; return n; };

function perpetualBanned(board, side, history) {
  const banned = new Set();
  for (const m of legalMoves(board, side)) {
    const cap = make(board, m);
    if (inCheck(board, -side) && countIn(history, keyOf(board, -side)) >= 2) banned.add(m);
    unmake(board, m, cap);
  }
  return banned;
}
function repetitionPenalties(board, side, history) {
  const pen = new Map();
  if (!history.length) return pen;
  for (const m of legalMoves(board, side)) {
    const cap = make(board, m);
    if (countIn(history, keyOf(board, -side)) >= 1) pen.set(m, 45);
    unmake(board, m, cap);
  }
  return pen;
}
function drawMovesOf(board, side, history) {
  const dm = new Set();
  for (const m of legalMoves(board, side)) {
    const cap = make(board, m);
    if (countIn(history, keyOf(board, -side)) >= 2) dm.add(m);
    unmake(board, m, cap);
  }
  return dm;
}

function adjudicateRepetition(history, newKey) {
  const last = history.lastIndexOf(newKey);
  if (last < 0) return ['draw', '同一局面第三次出现，判和'];
  const cycle = history.slice(last).concat([newKey]);
  let redAll = true, blackAll = true;
  for (const k of cycle) {
    const bd = k.slice(0, 90).split('');
    const stm = k[90] === 'r' ? RED : BLACK;
    const chk = inCheck(bd, stm);
    if (stm === RED && !chk) redAll = false;
    if (stm === BLACK && !chk) blackAll = false;
  }
  if (redAll && !blackAll) return ['red', '黑方长将不变，判负——红方获胜！'];
  if (blackAll && !redAll) return ['black', '红方长将不变，判负——黑方获胜！'];
  return ['draw', '同一局面第三次出现（双方均无长将），判和'];
}

function gameEndAfter(board, moverSide, gaveCheck) {
  if (!legalMoves(board, -moverSide).length) {
    const winner = moverSide === RED ? 'red' : 'black';
    const wn = winner === 'red' ? '红方' : '黑方';
    const ln = winner === 'red' ? '黑方' : '红方';
    return [winner, wn + '获胜！' + ln + (gaveCheck ? '被将死' : '困毙（无子可动）')];
  }
  if (!hasAttacker(board, RED) && !hasAttacker(board, BLACK))
    return ['draw', '双方均无进攻子力，和棋'];
  return [null, ''];
}

/* ---------------- 主变例缓存 ---------------- */
const PV_CACHE = new Map();   // key -> [move, backing]
function storePv(boardStr, side, pv, reached) {
  if (!pv || !pv.length) return;
  const b = boardStr.split('');
  let s = side;
  if (PV_CACHE.size > 2000) PV_CACHE.clear();
  for (let i = 0; i < pv.length; i++) {
    const backing = reached - i;
    if (backing < 6) break;
    PV_CACHE.set(keyOf(b, s), [pv[i], backing]);
    make(b, pv[i]);
    s = -s;
  }
}
function probePv(board, side, history) {
  const hit = PV_CACHE.get(keyOf(board, side));
  if (!hit) return null;
  const [mv, backing] = hit;
  if (!legalMoves(board, side).includes(mv)) return null;
  const cap = make(board, mv);
  const key2 = keyOf(board, -side);
  unmake(board, mv, cap);
  if (countIn(history, key2) >= 2) return null;
  return [mv, backing];
}

/* ---------------- 摆盘校验 ---------------- */
const NAME_RED = { K: '帅', A: '仕', B: '相', N: '马', R: '车', C: '炮', P: '兵' };
const NAME_BLACK = { K: '将', A: '士', B: '象', N: '马', R: '车', C: '炮', P: '卒' };
const COUNTS = { K: 1, A: 2, B: 2, N: 2, R: 2, C: 2, P: 5 };
const ADV_RED = new Set([84, 86, 76, 66, 68]);
const ADV_BLACK = new Set([3, 5, 13, 21, 23]);
const ELE_RED = new Set([83, 87, 63, 67, 71, 47, 51]);
const ELE_BLACK = new Set([2, 6, 18, 22, 26, 38, 42]);

function validateSetup(board) {
  const cnt = {};
  for (const p of board) if (p !== EMPTY) cnt[p] = (cnt[p] || 0) + 1;
  if ((cnt['K'] || 0) !== 1) return '红方必须有且只有一个帅';
  if ((cnt['k'] || 0) !== 1) return '黑方必须有且只有一个将';
  for (const up of Object.keys(COUNTS)) {
    if ((cnt[up] || 0) > COUNTS[up]) return '红方' + NAME_RED[up] + '数量超过上限(' + COUNTS[up] + ')';
    if ((cnt[up.toLowerCase()] || 0) > COUNTS[up]) return '黑方' + NAME_BLACK[up] + '数量超过上限(' + COUNTS[up] + ')';
  }
  for (let i = 0; i < 90; i++) {
    const p = board[i];
    if (p === EMPTY) continue;
    const r = (i / 9) | 0, c = i % 9;
    if (p === 'K' && !(c >= 3 && c <= 5 && r >= 7)) return '帅必须在红方九宫内';
    if (p === 'k' && !(c >= 3 && c <= 5 && r <= 2)) return '将必须在黑方九宫内';
    if (p === 'A' && !ADV_RED.has(i)) return '仕只能放在红方九宫的斜线交点上';
    if (p === 'a' && !ADV_BLACK.has(i)) return '士只能放在黑方九宫的斜线交点上';
    if (p === 'B' && !ELE_RED.has(i)) return '相只能放在红方的七个象位上';
    if (p === 'b' && !ELE_BLACK.has(i)) return '象只能放在黑方的七个象位上';
    if (p === 'P' && (r > 6 || (r >= 5 && c % 2 === 1))) return '兵的位置不合法（未过河的兵只能在己方兵线的起始纵线上）';
    if (p === 'p' && (r < 3 || (r <= 4 && c % 2 === 1))) return '卒的位置不合法（未过河的卒只能在己方卒线的起始纵线上）';
  }
  if (inCheck(board, BLACK)) return '红方先行：开始时黑方不能已处于被将军状态';
  if (!legalMoves(board, RED).length) return '红方无棋可走，无法开始';
  return null;
}

/* ---------------- 接口处理（与原 HTTP API 同构） ---------------- */
function parseBoard(data) {
  const b = data.board;
  if (typeof b !== 'string' || b.length !== 90) throw new Error('棋盘数据格式错误');
  return b.split('');
}
const clampTime = data => Math.min(Math.max(Number(data.time) || 16, 0.3), 300) * 1000;
const pairMoves = ms => ms.map(m => [MF(m), MT(m)]);

function aiReply(board, history, tMs) {
  const boardBefore = board.join('');
  let mv, depth;
  const probe = probePv(board, BLACK, history);
  if (probe) {
    mv = probe[0]; depth = probe[1];
  } else {
    const banned = perpetualBanned(board, BLACK, history);
    const pen = repetitionPenalties(board, BLACK, history);
    const dm = drawMovesOf(board, BLACK, history);
    const r = searchBest(board, BLACK, tMs, banned, pen, dm, history);
    mv = r.move; depth = r.depth;
    storePv(boardBefore, BLACK, r.pv, r.depth);
  }
  make(board, mv);
  const aiKey = keyOf(board, RED);
  const checkRed = inCheck(board, RED);
  let [over, msg] = gameEndAfter(board, BLACK, checkRed);
  if (!over && countIn(history, aiKey) >= 2) [over, msg] = adjudicateRepetition(history, aiKey);
  if (!over && checkRed) msg = '黑方将军！请应将';
  return { aiMove: { from: MF(mv), to: MT(mv) }, aiKey, checkRed, depth,
           board: board.join(''), gameOver: over, message: msg };
}

function applyUserMove(board, history, side, frm, to) {
  const sname = side === RED ? '红方' : '黑方';
  if (sideOf(board[frm]) !== side) return '请移动' + sname + '棋子';
  const m = MV(frm, to);
  if (!legalMoves(board, side).includes(m)) return '不符合走棋规则';
  make(board, m);
  if (inCheck(board, -side) && countIn(history, keyOf(board, -side)) >= 2)
    return '禁止长将！同一将军局面不得反复出现（' + sname + '违规），请更换走法';
  return null;
}

const HANDLERS = {
  '/api/start': data => {
    const board = parseBoard(data);
    const err = validateSetup(board);
    return err ? { ok: false, error: err } : { ok: true };
  },
  '/api/moves': data => {
    const board = parseBoard(data);
    const side = data.side === 'b' ? BLACK : RED;
    return { ok: true, moves: pairMoves(legalMoves(board, side)), check: inCheck(board, side) };
  },
  '/api/hint': data => {
    const board = parseBoard(data);
    const history = data.history || [];
    const side = data.side === 'b' ? BLACK : RED;
    const probe = probePv(board, side, history);
    if (probe)
      return { ok: true, from: MF(probe[0]), to: MT(probe[0]), score: 0,
               depth: probe[1], cached: true };
    const banned = perpetualBanned(board, side, history);
    const pen = repetitionPenalties(board, side, history);
    const dm = drawMovesOf(board, side, history);
    const r = searchBest(board, side, clampTime(data), banned, pen, dm, history);
    if (!r) return { ok: false, error: '当前没有可走的棋' };
    storePv(board.join(''), side, r.pv, r.depth);
    return { ok: true, from: MF(r.move), to: MT(r.move), score: r.score, depth: r.depth };
  },
  '/api/move': data => {
    const board = parseBoard(data);
    const history = data.history || [];
    const err = applyUserMove(board, history, RED, data.from | 0, data.to | 0);
    if (err) return { ok: false, error: err };
    const playerKey = keyOf(board, BLACK);
    const checkBlack = inCheck(board, BLACK);
    const resp = { ok: true, playerKey, checkBlack, aiMove: null, board: board.join('') };
    let [over, msg] = gameEndAfter(board, RED, checkBlack);
    if (!over && countIn(history, playerKey) >= 2)
      [over, msg] = adjudicateRepetition(history, playerKey);
    if (over) { resp.gameOver = over; resp.message = msg; return resp; }
    Object.assign(resp, aiReply(board, history.concat([playerKey]), clampTime(data)));
    return resp;
  },
  '/api/usermove': data => {
    const board = parseBoard(data);
    const history = data.history || [];
    const side = data.side === 'b' ? BLACK : RED;
    const err = applyUserMove(board, history, side, data.from | 0, data.to | 0);
    if (err) return { ok: false, error: err };
    const chk = inCheck(board, -side);
    const key = keyOf(board, -side);
    let [over, msg] = gameEndAfter(board, side, chk);
    if (!over && countIn(history, key) >= 2) [over, msg] = adjudicateRepetition(history, key);
    return { ok: true, board: board.join(''), key, check: chk, gameOver: over, message: msg };
  },
  '/api/aimove': data => {
    const board = parseBoard(data);
    const history = data.history || [];
    if (!legalMoves(board, BLACK).length) return { ok: false, error: '黑方无棋可走' };
    const resp = { ok: true };
    Object.assign(resp, aiReply(board, history, clampTime(data)));
    return resp;
  },
};

/* ---------------- Worker / Node 双环境入口 ---------------- */
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
                     evaluate, adjudicateRepetition, keyOf, MV, MF, MT, RED, BLACK,
                     validateSetup, drawMovesOf, perpetualBanned, repetitionPenalties };
}
