# 国际象棋残局研究器
FROM python:3.12-slim

WORKDIR /app
COPY engine.py server.py index.html ./

EXPOSE 8766
CMD ["python", "server.py", "8766"]
