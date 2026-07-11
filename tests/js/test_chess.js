'use strict';
/* 国际象棋 JS 引擎测试（node 运行） */
const E = require('../../web/international/chess-engine.js');

function B(...rows) {
  if (rows.length !== 8 || rows.some(r => r.length !== 8)) throw new Error('bad board');
  return rows.join('').split('');
}
let fail = 0;
const ok = (name, cond) => { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name); if (!cond) fail++; };

function perft(board, side, ep, depth) {
  if (depth === 0) return 1;
  let n = 0;
  for (const m of E.legalMoves(board, side, ep)) {
    const [undo, nep] = E.make(board, m, ep);
    n += perft(board, -side, nep, depth - 1);
    E.unmake(board, m, undo);
  }
  return n;
}

const start = B('rnbqkbnr', 'pppppppp', '........', '........',
                '........', '........', 'PPPPPPPP', 'RNBQKBNR');
ok('perft(1)=20', perft(start.slice(), E.WHITE, -1, 1) === 20);
ok('perft(2)=400', perft(start.slice(), E.WHITE, -1, 2) === 400);
ok('perft(3)=8902', perft(start.slice(), E.WHITE, -1, 3) === 8902);

// 底线杀 Ra1-a8#
const m1 = B('......k.', '.....ppp', '........', '........',
             '........', '........', '........', 'R.....K.');
const r1 = E.searchBest(m1, E.WHITE, -1, 3000, null, null, []);
ok('底线杀 56->0', E.MF(r1.move) === 56 && E.MT(r1.move) === 0 && r1.score > 1e8 - 1000);

// 逼和识别
const stale = B('k.......', '........', '.QK.....', '........',
                '........', '........', '........', '........');
ok('逼和局面黑无合法步且未被将',
   E.legalMoves(stale, E.BLACK, -1).length === 0 && !E.inCheck(stale, E.BLACK));

// 吃过路兵
const epb = B('....k...', '...p....', '........', '....P...',
              '........', '........', '........', '....K...');
const [, nep] = E.make(epb, E.MV(11, 27), -1);          // 黑 d7-d5
ok('双步兵产生ep格19', nep === 19);
const wm = E.legalMoves(epb, E.WHITE, nep);
ok('exd6 可走', wm.includes(E.MV(28, 19)));
E.make(epb, E.MV(28, 19), nep);
ok('过路兵被移除', epb[27] === '.');

// 升变
const pro = B('....k...', 'P.......', '........', '........',
              '........', '........', '........', '....K...');
E.make(pro, E.MV(8, 0), -1);
ok('自动升后', pro[0] === 'Q');

// 接口层: KQK 完整回合
const H = E.HANDLERS;
const kqk = B('....k...', '........', '........', '........',
              '........', '........', '...Q....', '....K...');
const bs = kqk.join('');
ok('摆盘校验', H['/api/start']({ board: bs }).ok === true);
const mv = H['/api/move']({ board: bs, ep: -1, history: [bs + 'w-1'],
                            from: 51, to: 27, time: 2 });
ok('走子+AI应招', mv.ok === true && !!mv.aiMove);
console.log('   深度:', mv.depth);

// 速度基准: 中局 8 秒
const mid = B('....k...', 'pp...ppp', '..n.....', '...r....',
              '...R....', '..N.....', 'PP...PPP', '....K...');
const t0 = Date.now();
const r2 = E.searchBest(mid, E.WHITE, -1, 8000, null, null, []);
console.log('   中局 8s: 深度%d 评分%d 用时%dms', r2.depth, r2.score, Date.now() - t0);
ok('搜索正常完成', r2.depth >= 7);

process.exit(fail ? 1 : 0);
