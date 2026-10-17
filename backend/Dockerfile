FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 2-3 용 부품: create_agent 가 든 langchain 1.x 와 그림 도구용 pillow (위 층 캐시를 살리려 따로 설치)
RUN pip install --no-cache-dir "langchain>=1.0" pillow
COPY main.py .
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
