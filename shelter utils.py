"""
main.py와 pages/1_지도.py가 공유하는 데이터 로딩 유틸리티.
CSV 파일은 이 파일과 같은 폴더(리포지토리 루트)에 있어야 합니다.
"""

import os

import pandas as pd
import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SHELTER_CSV_PATH = os.path.join(APP_DIR, "shade_shelters.csv")


@st.cache_data
def load_shelters() -> pd.DataFrame:
    if not os.path.exists(SHELTER_CSV_PATH):
        st.error(
            f"CSV 파일을 찾을 수 없습니다: `{SHELTER_CSV_PATH}`\n\n"
            "GitHub 리포지토리에 `shade_shelters.csv` 파일이 "
            "`main.py`와 같은 폴더(루트)에 커밋되어 있는지 확인해주세요."
        )
        st.stop()
    df = pd.read_csv(SHELTER_CSV_PATH)
    df = df.dropna(subset=["위도", "경도"])
    return df
