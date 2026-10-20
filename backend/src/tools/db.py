# PostgreSQL 연결: 부를 때마다 연결하고 닫는다
import os

import psycopg
from psycopg.rows import dict_row


class PostgreSqlDB:
    def _connect(self):
        # 계정 값은 서버 상자가 받는 환경 변수, 주소는 상자 안 이름 db · 포트 5432
        return psycopg.connect(
            host="db",
            port=5432,
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            dbname=os.environ["POSTGRES_DB"],
            row_factory=dict_row,  # 줄을 칸 이름 열쇠의 사전으로
        )

    def execute(self, query, params=None):
        # 바꾸는 쿼리: with 를 나갈 때 commit 하고 닫는다
        try:
            with self._connect() as conn:
                conn.execute(query, params)
            return True
        except Exception as e:
            print(f"DB 오류: {e}")
            return None

    def fetch_all(self, query, params=None):
        try:
            with self._connect() as conn:
                return conn.execute(query, params).fetchall()
        except Exception as e:
            print(f"DB 오류: {e}")
            return None

    def fetch_one(self, query, params=None):
        try:
            with self._connect() as conn:
                return conn.execute(query, params).fetchone()
        except Exception as e:
            print(f"DB 오류: {e}")
            return None
