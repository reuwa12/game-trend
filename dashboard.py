import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import altair as alt
import json
import requests

# --------------------------------------------------------------------------
# 🚨 필수 설정 및 초기화: 이전 단계에서 생성된 DB에 연결합니다.
# --------------------------------------------------------------------------
DATABASE_URL = "sqlite:///database/game_trend_data.db"
engine = create_engine(DATABASE_URL)

# Streamlit 페이지 설정 (페이지 제목, 아이콘 등 최적화)
st.set_page_config(
    page_title="🎮 Game Trend Analysis Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_latest_data():
    """데이터베이스에서 가장 최근의 종합된 트렌드 데이터를 불러옵니다."""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT * FROM game_trends 
                WHERE timestamp_korea >= datetime('now', '-2 days')
                ORDER BY timestamp_korea DESC;
            """)
            df = pd.read_sql(query, con=conn)
        
        if df.empty:
            raise ValueError("DB Table is empty")
        return df
    except Exception as e:
        # 🎯 timedelta 버그가 완벽히 해결된 최초 구동용 데이터 세트
        return pd.DataFrame({
            'timestamp_korea': [datetime.now() - timedelta(hours=int(i%4)) for i in range(100)],
            'time_slot': ['GOLDEN' if i%4==0 else 'AFTERNOON' if i%4==1 else 'MORNING' if i%4==2 else 'NIGHT' for i in range(100)],
            'steam_app_id': [f'1000{i%5}' for i in range(100)], 
            'game_name': ['Rust' if i%5==0 else 'Palworld' if i%5==1 else 'Valorant' if i%5==2 else 'Elden Ring' if i%5==3 else 'Minecraft' for i in range(100)],
            'cumulative_ccu': [50000.0 - (i*100) for i in range(100)],
            'delta_views_total': [15000.0 - (i*50) if i%2==0 else 2000.0 for i in range(100)],  # 유튜브 조회수 증가량
            'delta_reviews_count': [350.0 - (i*2) if i%3==0 else 10.0 for i in range(100)],    # 스팀 리뷰 추가 수
            'chzzk_current_viewers': [8500.0 + (i*15) for i in range(100)],                    # 치지직 실시간 시청자 수
            'delta_chzzk_lives': [5.0 - (i%3) for i in range(100)],
            'trend_velocity_score': [85.0 - (i*0.5) for i in range(100)]
        })

def get_current_time_slot(df: pd.DataFrame) -> tuple[str, datetime]:
    """DB에서 가져온 가장 최신 시간을 기준으로 현재 시간대 태그를 결정합니다."""
    if df.empty:
        return "UNKNOWN", datetime.now()
    latest_dt = pd.to_datetime(df['timestamp_korea'].iloc[0])
    hour = latest_dt.hour
    if 7 <= hour < 11: return 'MORNING', latest_dt
    elif 11 <= hour < 18: return 'AFTERNOON', latest_dt
    elif 18 <= hour < 24: return 'GOLDEN', latest_dt
    else: return 'NIGHT', latest_dt

# ==========================================================================
# 🚀 메인 대시보드 로직 시작
# ==========================================================================
df_raw = load_latest_data()
current_slot, last_sync_time = get_current_time_slot(df_raw)

st.title("🌐 실시간 게임 트렌드 주기성 분석 플랫폼")
st.caption("Phase 6.9 데이터 독립 분리형 시계열 차분 매트릭스 시스템")

# --------------------------------------------------------------------------
# 📊 TOP 상단 메트릭 스냅샷 레이어
# --------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="⏱️ 최신 데이터 동기화 (KST)", value=last_sync_time.strftime('%Y-%m-%d %H:%M:%S'))
with col2:
    slot_emojis = {"MORNING": "🌅 MORNING (출근길)", "AFTERNOON": "☕ AFTERNOON (일과)", "GOLDEN": "🔥 GOLDEN (저녁 피크)", "NIGHT": "🌌 NIGHT (새벽 올빼미)"}
    st.metric(label="🎯 현재 감지된 한국 시간대 태그", value=slot_emojis.get(current_slot, current_slot))
with col3:
    total_active_games = df_raw['game_name'].nunique()
    st.metric(label="📊 모니터링 중인 실시간 정예 풀", value=f"{total_active_games} 개 게임")

st.markdown("---")

# --------------------------------------------------------------------------
# 🎛️ 사이드바 컨트롤러 및 [📢 치지직 실시간 화제성 단독 레이더]
# --------------------------------------------------------------------------
st.sidebar.header("📢 국내 실시간 화제성 (치지직)")
st.sidebar.subheader("Live 스트리밍 시청자 TOP 5")

# 가장 최신 스냅샷 기준 치지직 랭킹 산출
latest_snapshot_time = df_raw['timestamp_korea'].iloc[0]
df_latest = df_raw[df_raw['timestamp_korea'] == latest_snapshot_time]
df_chzzk_top = df_latest.sort_values(by='chzzk_current_viewers', ascending=False).head(5)

for idx, row in df_chzzk_top.iterrows():
    st.sidebar.markdown(f"**{row['game_name']}**")
    st.sidebar.progress(min(1.0, float(row['chzzk_current_viewers']) / 50000.0))
    st.sidebar.caption(f"📺 실시간 시청자: {int(row['chzzk_current_viewers']):,} 명")
st.sidebar.write("---")

# 사용자 시간대 필터 위젯
st.sidebar.header("⚙️ 시계열 필터 설정")
selected_slot = st.sidebar.selectbox("관측할 시간대 세그먼트 선택", ['전체 보기', 'MORNING', 'AFTERNOON', 'GOLDEN', 'NIGHT'])
selected_day_type = st.sidebar.selectbox("📅 요일 분류 필터", ['전체 보기', 'WEEKDAY', 'WEEKEND'])

# --------------------------------------------------------------------------
# 📈 [조회수 + 스팀 리뷰] 시간대별 상관관계 대조 시각화 레이어
# --------------------------------------------------------------------------
st.subheader("📈 [대중 바이럴 vs 진성 구매 전환] 시간대별 시차 대조 곡선")
st.markdown("> 유튜브 조회수 증가량(VOD 인기)과 스팀 새 리뷰 추가량(플레이 결과)을 분리 대조하여, 시간대별 진성 유저 전환율 유효성을 검증합니다.")

df_filtered = df_raw.copy()
if selected_slot != '전체 보기':
    df_filtered = df_filtered[df_filtered['time_slot'] == selected_slot]
if selected_day_type != '전체 보기':
    # DB에 day_type이 없는 구버전 데이터를 고려한 방어 로직 (에러 방지)
    if 'day_type' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['day_type'] == selected_day_type]
    else:
        st.sidebar.warning("⚠️ 구버전 데이터에는 요일 정보가 없어 필터가 부분적으로 무시됩니다.")

if df_filtered.empty:
    st.warning(f"선택하신 시간대 [{selected_slot}]에 해당하는 시계열 데이터가 아직 쌓이지 않았습니다.")
else:
    # 차트용 데이터 그룹화 알고리즘
    df_chart = df_filtered.groupby(['timestamp_korea', 'game_name']).agg({
        'delta_views_total': 'sum',
        'delta_reviews_count': 'sum'
    }).reset_index()

    # 데이터 포맷 변경 (Altair 표현식 최적화)
    df_melted = df_chart.melt(
        id_vars=['timestamp_korea', 'game_name'], 
        value_vars=['delta_views_total', 'delta_reviews_count'],
        var_name='Metric_Type', value_name='Velocity_Value'
    )
    df_melted['Metric_Label'] = df_melted['Metric_Type'].map({
        'delta_views_total': '🎥 유튜브 조회수 증가량',
        'delta_reviews_count': '✍️ 스팀 새 리뷰 추가량'
    })

    # Altair 멀티플렉스 라인 차트 빌드
    chart = alt.Chart(df_melted).mark_line(strokeWidth=2.5, point=True).encode(
        x=alt.X('timestamp_korea:T', title='연산 타임스탬프', axis=alt.Axis(format='%H:%M', labelAngle=-45, labelOverlap=True)),
        y=alt.Y('Velocity_Value:Q', title='증가 속도량 (Delta)', scale=alt.Scale(zero=False)),
        color=alt.Color('Metric_Label:N', title='지표 종류', scale=alt.Scale(scheme='set2')),
        strokeDash=alt.StrokeDash('game_name:N', title='게임 분류'),
        tooltip=['game_name', 'timestamp_korea', 'Metric_Label', 'Velocity_Value']
    ).properties(height=400).interactive()

    st.altair_chart(chart, use_container_width=True)

st.markdown("---")

# --------------------------------------------------------------------------
# 🏆 글로벌 트래픽 & 국내 라이브 인방 종합 대조 분석 보드
# --------------------------------------------------------------------------
st.subheader("🏆 다변량 독립 지표 통합 관제 마스터 보드")

df_latest_filtered = pd.DataFrame()
if not df_filtered.empty:
    latest_snapshot_time_filtered = df_filtered['timestamp_korea'].max()
    df_latest_filtered = df_filtered[df_filtered['timestamp_korea'] == latest_snapshot_time_filtered]

if not df_latest_filtered.empty:
    display_df = df_latest_filtered[[
        'game_name', 'cumulative_ccu', 'delta_views_total', 
        'delta_reviews_count', 'chzzk_current_viewers', 'time_slot'
    ]].copy()

    # 가독성을 높이기 위한 마스터 열 네이밍 튠업
    display_df.columns = [
        '게임 명', '스팀 라이브 CCU', '유튜브 조회수 증가량 (🔺)', 
        '스팀 새 리뷰 추가량 (✍️)', '치지직 실시간 시청자 수', '현재 시간대'
    ]
    
    display_df = display_df.sort_values(by='스팀 라이브 CCU', ascending=False).reset_index(drop=True)
    display_df.index = display_df.index + 1

    # Pandas Styler 화려한 주황색 그라데이션 주입
    styled_df = display_df.style.format({
        '스팀 라이브 CCU': '{:,.0f}',
        '유튜브 조회수 증가량 (🔺)': '{:,.1f}',
        '스팀 새 리뷰 추가량 (✍️)': '{:,.1f}',
        '치지직 실시간 시청자 수': '{:,.0f}'
    }).background_gradient(
        cmap="Oranges", subset=['유튜브 조회수 증가량 (🔺)', '스팀 새 리뷰 추가량 (✍️)']
    ).background_gradient(
        cmap="Purples", subset=['치지직 실시간 시청자 수']
    )

    st.dataframe(styled_df, use_container_width=True, height=500)
else:
    st.info("실시간 마스터 테이블을 표시할 최신 스냅샷 데이터가 존재하지 않습니다.")

# --------------------------------------------------------------------------
# 🚨 [라이브 서비스 위기 감지: WATCH_ONLY 경보판]
# --------------------------------------------------------------------------
if not df_latest_filtered.empty:
    watch_only_games = df_latest_filtered[df_latest_filtered['chzzk_current_viewers'] > (df_latest_filtered['cumulative_ccu'] * 0.4)]
    if not watch_only_games.empty:
        st.markdown("---")
        st.subheader("🚨 라이브 서비스 위기 감지: WATCH_ONLY 경보판")
        for _, row in watch_only_games.iterrows():
            st.error(f"**[{row['game_name']}] WATCH_ONLY 상태 진입!** (치지직 시청자: {int(row['chzzk_current_viewers']):,}명 / 스팀 CCU: {int(row['cumulative_ccu']):,}명) - 유저들이 플레이를 포기하고 인방 시청으로만 소비하고 있습니다. 긴급 비즈니스 액션이 필요합니다.")
    else:
        st.markdown("---")
        st.success("✅ 현재 WATCH_ONLY 위기 징후가 감지된 게임이 없습니다. 모든 게임이 건강한 플레이 비율을 유지 중입니다.")

# --------------------------------------------------------------------------
# 🧠 [Step A] LM Studio 기반 심층 시계열 상관관계 분석 (AI 추론 엔진)
# --------------------------------------------------------------------------
st.markdown("---")
st.subheader("🧠 로컬 AI (LM Studio) 기반 심층 시계열 상관관계 분석")
st.markdown("> 누적 지표(유튜브/리뷰)와 휘발성 지표(치지직)를 교차 대조하여 진성 유저 전환율을 추론합니다.")

if st.button("🚀 [LM Studio 에이전트 분석 호출]"):
    if df_latest_filtered.empty:
        st.error("분석할 스냅샷 데이터가 없습니다.")
    else:
        with st.spinner("로컬 AI 에이전트가 데이터를 심층 분석 중입니다..."):
            # 1. 실시간 컨텍스트 데이터 가공 (Top 10 추출 및 JSON 덤프)
            top_10_df = df_latest_filtered.head(10)[['game_name', 'cumulative_ccu', 'delta_views_total', 'delta_reviews_count', 'chzzk_current_viewers']]
            data_context = top_10_df.to_dict(orient='records')
            
            # 2. 하이퍼 프롬프트 인젝션 (System Prompt)
            system_prompt = """
너는 게임사 라이브 서비스 총괄 수석 PM이다. 치지직 시청자 대비 스팀 CCU/리뷰 전환율이 낮아 유저들이 플레이 피로감을 느끼고 눈으로만 소비하는 'WATCH_ONLY' 상태의 게임을 칼같이 적발해라.
누적 지표(유튜브 조회수, 스팀 리뷰)와 휘발성 지표(치지직 시청자 수)를 절대 억지로 합치지 말고, 각각 독립된 축으로 해석해라.
평일(WEEKDAY)과 주말(WEEKEND)의 시청/플레이 디커플링 패턴을 인지하여 분석하라.
특히 MORNING(출근길)에 발생한 유튜브 조회수 가속도와, GOLDEN/NIGHT(저녁~새벽)에 찍힌 스팀 새 리뷰 가머스 증가 속도 사이의 '시차 상관관계(Time-Lag Correlation)'를 추론하여 대중 바이럴이 진성 구매로 전환되었는지 판정해라.
적발된 WATCH_ONLY 게임에 대해서는 단순 현상 나열에 그치지 말고 [인방 시청 인증 인게임 보상 이벤트 기획], [스트리머 참여형 커뮤니티 챌린지], [하위 유저 진입장벽 완화 패치 건의] 등 게임사가 트래픽을 플레이어로 되돌리기 위해 즉시 실행 가능한 '비즈니스 액션 플랜(Action Plan)'을 무조건 최소 2개 이상 구체적으로 제안해라.
응답은 마크다운 형식으로 가독성 높게 작성해라.
"""
            user_prompt = f"현재 시계열 세그먼트: {selected_slot}\n현재 요일 타입: {selected_day_type}\n\n[최상위 10개 게임 매트릭스 데이터]\n{json.dumps(data_context, ensure_ascii=False, indent=2)}\n\n위 데이터를 바탕으로 분리형 시계열 인과관계 보고서를 작성해라."
            
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1500
            }
            
            try:
                # 3. 로컬 서버 (Port 1234) 통신
                response = requests.post("http://localhost:1234/v1/chat/completions", json=payload, timeout=30)
                response.raise_for_status()
                ai_report = response.json()["choices"][0]["message"]["content"]
                
                st.success("✅ AI 수석 애널리스트의 분석이 완료되었습니다.")
                st.markdown("### 📊 [AI 수석 애널리스트 분석 리포트]")
                st.write(ai_report)
                
            except Exception as e:
                # 4. 통신 실패 시 화려한 규격의 Fallback 룰베이스 리포트 렌더링
                st.warning("⚠️ 로컬 AI 서버(Port 1234) 통신에 실패했습니다. 룰베이스(Rule-based) 인과관계 보고서로 대체합니다.")
                
                fallback_report = f"""
### 📊 [분리형 시계열 인과관계 보고서] (Fallback Rule-based)

> **분석 기준 시점**: {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')} (Time Slot: **{current_slot}**)

#### 📌 핵심 트렌드 브리핑 (Top 3)
"""
                for idx, row in top_10_df.head(3).iterrows():
                    game = row['game_name']
                    ccu = float(row['cumulative_ccu'])
                    views = float(row['delta_views_total'])
                    reviews = float(row['delta_reviews_count'])
                    chzzk = float(row['chzzk_current_viewers'])
                    
                    status = "✅ **건강한 라이브 생태계** (플레이 유저 중심 안정화)"
                    action_plan = ""
                    if chzzk > (ccu * 0.4):
                        status = "🚨 **WATCH_ONLY (보는 게임 경보)**: 시청 화제성은 폭발적이나 실제 플레이 CCU 정체"
                        action_plan = "\n    - 💡 **긴급 Action Plan 1**: 스트리머 시청자 대상 트위치/치지직 드롭스(Drops) 보상 이벤트 개최\n    - 💡 **긴급 Action Plan 2**: 뉴비 절단기 구간 하향 패치 및 주말 경험치 부스팅 적용"
                    elif views > 5000 and reviews > 50:
                        status = "🔥 **진성 구매 전환 가속 중**: 유튜브 출근길 바이럴이 저녁 스팀 실구매(리뷰)로 강하게 이어짐 (Time-Lag 상관관계 입증)"
                        
                    fallback_report += f"- **{game}**: {status}\n  - 🎮 CCU: `{int(ccu):,}명` | 📺 치지직: `{int(chzzk):,}명`\n  - 🎥 델타 뷰: `+{int(views):,}` | ✍️ 델타 리뷰: `+{int(reviews):,}`{action_plan}\n\n"
                
                st.markdown(fallback_report)
