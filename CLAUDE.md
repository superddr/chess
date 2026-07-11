# 项目记忆（供 Claude Code 在任何机器上续接工作）

中国象棋 + 国际象棋残局研究器。用户（薛师傅级棋力）用它研究残局并持续实战找 bug，
本文件记录架构、关键设计决策及其原因、已知坑。**改引擎时两个棋种默认同步。**

## 结构与运行

- 根目录 = 中国象棋（端口 8765）；`international/` = 国际象棋（8766）。零第三方依赖。
- 每套三个文件：`engine.py`（规则+搜索）、`server.py`（HTTP+任务系统）、`index.html`（Canvas 前端）。
- 本地跑：`python server.py [端口]`；Docker：`docker build -t xiangqi-endgame . && docker run -d --name xiangqi --restart unless-stopped -p 8765:8765 xiangqi-endgame`。
- 测试在 `tests/`（相对路径可直接跑）：`test_rules_aware.py`（棋力回归）、`test_adjudicate3.py`（长将裁决）、
  `test_speed_norepeat.py`、`test_chess.py`（国象 perft 20/400/8902 必须精确）、`bench_speed.py`。
- 象棋服务写对局监控日志 `game_log.jsonl`（每步 AI 的候选评分表/深度/禁着），复盘分析靠它。

## 引擎（两套同构）

负极大 α-β + 迭代加深 + 置换表（worker 进程各持一张、跨请求保留=树缓存）+ 静态搜索
+ 空着裁剪（国象王兵残局关闭防 zugzwang）+ LMR + killer/history + 将军延伸
+ 多核根分裂（进程池 cpu-1，根窗口 alpha0=上层最佳-150 裁剪，全体跌破则同层全窗重搜）。

提前收工规则（用户对速度极敏感）：绝杀已证深度≥4 即出手；最佳着连续 3 层不变且领先 250
（或连续 5 层不变）且深度≥min_d 即交卷；min_d 按时限分档 9/11/13（16s/64s/256s 档），
保留"长考=更深"。应法≤3 时按 0.25*个数 缩时限。

## 规则子系统（多轮实战教训的结晶，改动前先读）

- **树内路径重复检测**（negamax 内）：长将方判负 / 循环判和——规则必须进搜索树，
  只在根上检查会被 AI 钻空子（历史教训：它曾以为"连将永远安全"评+1396）。
- **三次重复裁决** `adjudicate_repetition`：回溯循环内每个局面，单方长将→判负，否则判和。
  曾因"一律判和"被 AI 用连将把必败局洗成和棋（用户实战抓出）。
- **回头路策略**：不做硬禁（曾因硬禁逼 AI 走怪棋——对方发起的重复跟着回头是正当应法）；
  仅 45 分轻罚引导；第三次重复走法在根上按精确 0 分（劣势可主动求和、优势自然回避）。
- **重复罚分绝不能大**：曾设 120/次且无封顶，AI 为避重复宁可送车。
- 象棋困毙=判负；国象逼和=和棋（negamax 里 pseudo 走法需专门复核 stalemate）。
- 国象：吃过路兵全链路（ep 随局面键/历史键传递）、自动升后、无王车易位（残局工具取舍）。

## 服务端任务系统（server.py，两套同构）

- 耗时接口（move/aimove/hint）任务化：任务 id = md5(path+请求JSON排序)。**id 由内容哈希
  是关键设计**：断线重发命中同一任务；玩家照提示走棋命中预思考任务。
- `submit_job` 短等 0.35s，算完直接随提交响应返回（快棋 0 轮询）；`/api/job` 支持
  `wait` 长轮询（前端用 10s 一轮：更长会被用户的 Mihomo TUN 代理掐掉）。
- **链式预思考 `_chain_after`**（chain≤2，命中缓存时真实请求把链深归 0 续链）：
  AI 走完→预算求助答案→预算"照提示走后的应招"。用户照提示走=全程秒回。
- **主变例缓存 `PV_CACHE`**：每次深算后从 worker 置换表提取整条 PV（引擎 out['pv']），
  沿线"局面→最佳应招"全部缓存；支撑深度=reached-i，<6 层的尾巴不存（依据太薄）。
  命中时求助/应招 0 秒直返（快过预思考完成）；链式预思考随后补全深度。
  服务 probe 时校验合法性与三次重复。两套缓存互补：PV 管"比预算还快"，链管"全深度"。
- 前端：轮询失败立即重试（不用会被浏览器省电节流的 setTimeout 退避）；每 0.9s rAF 补帧
  + focus/visibilitychange 重绘（省电模式渲染降频的保险丝）。localStorage 全量存档。

## 已知坑（重踩过的）

- **multiprocessing on Windows**：任何 import engine 并调用 search_best 的脚本必须有
  `if __name__ == '__main__'` 保护，否则 spawn 子进程重放整个脚本（曾致测试重复执行8遍）；
  也不能用 `python - <<EOF` 管道跑（子进程无法重导入 `<stdin>`）。测试一律写成 .py 文件跑。
- Git Bash 里 docker exec 的 `/app` 会被转义成 `C:/Program Files/Git/app`，加 `MSYS_NO_PATHCONV=1`。
- Windows 控制台 GBK：跑 python 前设 `PYTHONIOENCODING=utf-8`。
- 端口 8000 被 Windows 保留（WinError 10013），所以用 8765/8766。
- 用户机器 SSH 22 被代理挡，`~/.ssh/config` 已把 github.com 指到 ssh.github.com:443（新机器需重配）。
- 具名卷挂 `/app` 会让旧代码盖住新镜像，Docker 运行不要挂 /app。
- 着法记录同列≥3 个兵用 前/中/后 或 前/二/三/后（曾有全标"前"的歧义 bug）。

## 用户偏好与工作方式

- 全程中文交流。用户会**实战下棋抓 bug 并导出局面贴给你**（导出含 90/64 字符局面代码，
  可程序化解析复盘；着法文本由前端 moveText 生成，可用 DFS+终局盘面精确重放对局）。
- 结论必须先实测验证再说（引擎问题写 tests/ 下的脚本跑通）；修完 bug 主动 commit+push
  （仓库 github.com/superddr/chess，SSH 已配）；改完引擎要 docker rebuild+重启容器才生效。
- 对 AI 行为的哲学：无聊重复=没有存在意义；明显的棋想太久=令人失望；规则漏洞被 AI 利用
  =必须修规则而不是嘴上解释。

## 可能的后续方向

- Python 速度天花板（深度 11~15），根治需热点重写（Cython/位棋盘）或接 Pikafish 类引擎。
- 国象补王车易位/50 步规则；象棋接残局库；ponder 链加深或对多个候选走法分叉预算。
