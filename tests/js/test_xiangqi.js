'use strict';
/* 中国象棋 JS 引擎测试（node 运行） */
const E = require('../../web/xiangqi-engine.js');

function B(...rows) {
  if (rows.length !== 10 || rows.some(r => r.length !== 9)) throw new Error('bad board');
  return rows.join('').split('');
}
let fail = 0;
const ok = (name, cond) => { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name); if (!cond) fail++; };

// 1) 标准开局 44 步
const start = B('rnbakabnr', '.........', '.c.....c.', 'p.p.p.p.p', '.........',
                '.........', 'P.P.P.P.P', '.C.....C.', '.........', 'RNBAKABNR');
ok('开局红方44步', E.legalMoves(start, E.RED).length === 44);
ok('开局黑方44步', E.legalMoves(start, E.BLACK).length === 44);

// 2) 马后炮杀: 红炮(4,0)->(4,4) 绝杀
const mate1 = B('....k....', '.........', '....N....', '.........', 'C........',
                '.........', '....p....', '.........', '.........', '....K....');
const r1 = E.searchBest(mate1, E.RED, 3000, null, null, null, []);
ok('马后炮杀 36->40 杀分', E.MF(r1.move) === 36 && E.MT(r1.move) === 40 && r1.score > 1e8 - 1000);

// 3) 王照面
const face = B('....k....', '.........', '.........', '.........', '.........',
               '.........', '.........', '.........', '.........', '....K....');
ok('王照面判定', E.inCheck(face, E.BLACK) === true);

// 4) 长将裁决
const b = B('....k....', '.........', '.........', '.........', '....r....',
            '.........', '.........', '.........', '.........', '.....K...');
// 注: 黑将(0,4) 黑车(4,4) 红帅(9,5)
const P = E.keyOf(b, E.BLACK);
E.make(b, E.MV(40, 41));           // 黑车平六将军
const Q1 = E.keyOf(b, E.RED);
if (!E.inCheck(b, E.RED)) throw new Error('构造失败: Q1 应为将军');
E.make(b, E.MV(86, 85));           // 红帅平五
const Q2 = E.keyOf(b, E.BLACK);
E.make(b, E.MV(41, 40));           // 黑车平五又将
const Q3 = E.keyOf(b, E.RED);
E.make(b, E.MV(85, 86));           // 红帅平六 → 回到 P
if (E.keyOf(b, E.BLACK) !== P) throw new Error('循环未闭合');
const [who] = E.adjudicateRepetition([P, Q1, Q2, Q3], P);
ok('黑长将判红胜', who === 'red');

// 5) 接口层: 双兵对双士完整回合
const H = E.HANDLERS;
const setup = B('...ak....', '....a....', '.........', '...P.P...', '.........',
                '.........', '.........', '.........', '.........', '...K.....');
const boardStr = setup.join('');
const st = H['/api/start']({ board: boardStr });
ok('摆盘校验通过', st.ok === true);
const mv = H['/api/move']({ board: boardStr, history: [boardStr + 'r'],
                            from: 30, to: 21, time: 2 });
ok('走子+AI应招', mv.ok === true && mv.aiMove && mv.depth >= 6);
console.log('   AI应招深度:', mv.depth);
// 立刻求助应命中主变例缓存
const hist2 = [boardStr + 'r', mv.playerKey, mv.aiKey];
const t0 = Date.now();
const h = H['/api/hint']({ board: mv.board, history: hist2, time: 8, side: 'r' });
ok('求助秒回(PV缓存)', h.ok && (h.cached === true || Date.now() - t0 < 1500));
console.log('   求助耗时: %dms cached=%s', Date.now() - t0, h.cached);

// 6) 速度基准: 四兵对双车 8 秒
const fp = B('..rr.k...', '....P....', '....P....', '....P....', '....P....',
             '.........', '.........', '.........', '.........', '....K....');
const t1 = Date.now();
const r2 = E.searchBest(fp, E.RED, 8000, null, null, null, []);
console.log('   四兵对双车 8s: 深度%d 评分%d 用时%dms', r2.depth, r2.score, Date.now() - t1);
ok('搜索正常完成', r2.depth >= 7);

process.exit(fail ? 1 : 0);
