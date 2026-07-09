# 中国象棋残局研究器
FROM python:3.12-slim

WORKDIR /app
COPY engine.py server.py index.html ./

EXPOSE 8765
# 对局监控日志写在 /app/game_log.jsonl，如需持久化可挂载卷: -v xiangqi_log:/app
CMD ["python", "server.py", "8765"]
