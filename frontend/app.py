import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from streamlit_javascript import st_javascript

st.set_page_config(page_title="NSBS P2P 플랫폼", layout="wide")

DB_API_URL = "http://localhost:8000"

def main():
    st.title("🌐 실제 위치 기반 P2P 네트워크 공유 플랫폼")

    coords = st_javascript("""
    new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        position => resolve([position.coords.latitude, position.coords.longitude]),
        error => resolve(null)
      );
    });
    """)

    if coords:
        lat, lon = coords
        st.success(f"현재 위치: 위도 {lat:.6f}, 경도 {lon:.6f}")
    else:
        st.warning("위치 권한을 허용하지 않았거나 위치를 가져올 수 없습니다. 기본 위치 (서울시청)로 설정합니다.")
        lat, lon = 37.5665, 126.9780

    if 'user_id' not in st.session_state:
        st.session_state.user_id = ""
        st.session_state.role = ""
        st.session_state.account = ""

    if not st.session_state.user_id:
        with st.form("register"):
            st.write("### 🆔 회원 정보 입력")
            user_id = st.text_input("사용자 ID")
            role = st.radio("역할 선택", ["provider", "borrower"])
            account = st.text_input("계좌 정보 (은행+계좌번호)")
            price = 0
            if role == "provider":
                price = st.number_input("시간당 요금 (원)", min_value=1000, value=3000)
            submitted = st.form_submit_button("가입 완료")
            if submitted:
                resp = requests.post(
                    f"{DB_API_URL}/api/register",
                    json={
                        "user_id": user_id,
                        "role": role,
                        "account": account,
                        "price_per_hour": price,
                        "lat": lat,
                        "lon": lon,
                    }
                )
                if resp.status_code == 200:
                    st.session_state.user_id = user_id
                    st.session_state.role = role
                    st.session_state.account = account
                    st.experimental_rerun()
                else:
                    st.error(f"등록 실패: {resp.json().get('detail')}")
        return

    st.sidebar.write(f"👤 사용자: {st.session_state.user_id} ({st.session_state.role})")

    if st.session_state.role == "borrower":
        st.header("📍 근처 공급자 찾기 (2km 이내)")

        if st.button("주변 공급자 검색"):
            res = requests.get(f"{DB_API_URL}/api/providers?lat={lat}&lon={lon}")
            if res.status_code == 200:
                providers = res.json().get("providers", [])
                if providers:
                    df = pd.DataFrame(providers)
                    st.dataframe(df[['id', 'account', 'price_per_hour', 'distance']])
                    st.pydeck_chart(pdk.Deck(
                        map_style="mapbox://styles/mapbox/streets-v11",
                        initial_view_state=pdk.ViewState(
                            latitude=lat,
                            longitude=lon,
                            zoom=13,
                        ),
                        layers=[
                            pdk.Layer(
                                "ScatterplotLayer",
                                data=providers,
                                get_position=["lon", "lat"],
                                get_radius=200,
                                get_fill_color=[255, 0, 0, 140],
                                pickable=True,
                            )
                        ],
                        tooltip={"text": "{id}\n계좌: {account}\n가격: {price_per_hour}원/시간"}
                    ))

                    provider_id = st.selectbox("공급자 선택", df['id'])
                    duration = st.slider("사용 시간 (분)", 10, 1440, 60)
                    tx_hash = st.text_input("입금 확인용 거래 해시")

                    if st.button("요청 보내기"):
                        req_resp = requests.post(
                            f"{DB_API_URL}/api/request",
                            json={
                                "provider_id": provider_id,
                                "borrower_id": st.session_state.user_id,
                                "duration": duration,
                                "tx_hash": tx_hash,
                            }
                        )
                        if req_resp.status_code == 200:
                            st.success("요청이 전송되었습니다. 공급자의 승인을 기다리세요.")
                        else:
                            st.error("요청 전송 실패")
                else:
                    st.warning("2km 이내 공급자가 없습니다.")
            else:
                st.error("공급자 조회 실패")
    else:
        st.header("🔌 공급자 대시보드")
        st.write("수요자의 요청을 기다리는 중입니다...")

        conn = sqlite3.connect(DB_API_URL.replace("http://", "").replace(":8000", "") + "/payments.db")
        # 권장: 별도 API 콜로 DB 상태 확인하는 것이 안전하지만 간단히...

        import sqlite3
        conn = sqlite3.connect("./payments.db")
        pending_txs = conn.execute(
            "SELECT tx_hash, borrower_id, start_time, end_time FROM transactions WHERE provider_id=? AND status='pending'",
            (st.session_state.user_id,)
        ).fetchall()
        conn.close()

        if pending_txs:
            st.write("### 승인 대기 중인 요청")
            for tx in pending_txs:
                tx_hash, borrower_id, start_time, end_time = tx
                st.write(f"- 요청자: {borrower_id}, 시작: {start_time}, 종료: {end_time}")
                if st.button(f"승인하기 {tx_hash}"):
                    approve_resp = requests.post(
                        f"{DB_API_URL}/api/approve",
                        json={"tx_hash": tx_hash}
                    )
                    if approve_resp.status_code == 200:
                        st.success(f"요청 {tx_hash} 승인 완료")
                    else:
                        st.error(f"승인 실패: {approve_resp.json().get('detail')}")
        else:
            st.write("현재 승인 대기 중인 요청이 없습니다.")

if __name__ == "__main__":
    main()
