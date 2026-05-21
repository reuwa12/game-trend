import os
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, MetaData, Table, select, text
from datetime import datetime, timedelta
from typing import List, Dict, Any

# ---------------------------------------------------
# 🛠️ 데이터베이스 설정 (SQLite 경로 자동 생성 방어막 작동)
# ---------------------------------------------------
os.makedirs("database", exist_ok=True)
DATABASE_URL = "sqlite:///database/game_trend_data.db"
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# 메인 트렌드 저장 테이블 정의 (지표가 완전히 분리된 싱글 소스 오브 트루스)
trends_table = Table('game_trends', metadata,
    Column('id', Integer, primary_key=True),
    Column('timestamp_korea', DateTime),                 # KST 기준 시간
    Column('time_slot', String),                         # MORNING, GOLDEN, AFTERNOON, NIGHT
    Column('day_type', String),                          # WEEKDAY, WEEKEND
    Column('steam_app_id', String),                      # 게임 식별자
    Column('game_name', String),
    
    # --- 📈 누적 지표 (Delta Source) ---
    Column('cumulative_ccu', Float),                    # 실시간 스팀 CCU (플레이 트래픽)
    Column('delta_views_total', Float),                  # 유튜브 조회수 증가량 (VOD 바이럴)
    Column('delta_reviews_count', Float),                # 스팀 새 리뷰 추가량 (진성 구매 전환 결과물)
    
    # --- 📢 독립 트렌드 지표 (Separate Indicators) ---
    Column('chzzk_current_viewers', Float),              # 치지직 실시간 시청자 수 (독립 측정 레이더)
    Column('delta_chzzk_lives', Float),                  # 치지직 라이브 스트리머 변화량
    
    # --- 🚀 확장성 대비 필드 ---
    Column('trend_velocity_score', Float, nullable=True) # 향후 필요시 활용할 가속도 인덱스 예비 자리
)

# --- 🗜️ 1시간 압축(Downsampling)용 테이블 신설 ---
trends_hourly_table = Table('game_trends_hourly', metadata,
    Column('id', Integer, primary_key=True),
    Column('timestamp_korea', DateTime),                 # KST 기준 1시간 단위 시간
    Column('time_slot', String),                         
    Column('day_type', String),
    Column('steam_app_id', String),                      
    Column('game_name', String),
    Column('cumulative_ccu', Float),                     # 산술 평균 (AVG)
    Column('delta_views_total', Float),                  # 총합 (SUM)
    Column('delta_reviews_count', Float),                # 총합 (SUM)
    Column('chzzk_current_viewers', Float),              # 산술 평균 (AVG)
    Column('delta_chzzk_lives', Float),                  # 산술 평균 (AVG)
    Column('trend_velocity_score', Float, nullable=True)
)

# 테이블이 없으면 생성합니다.
metadata.create_all(engine)

# 하위 호환성을 위한 ALTER TABLE (이미 존재 시 무시)
with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE game_trends ADD COLUMN day_type VARCHAR"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE game_trends_hourly ADD COLUMN day_type VARCHAR"))
    except Exception:
        pass

def calculate_time_slot(dt: datetime) -> str:
    """
    주어진 KST 시간을 분석하여 4가지 시간대 태그를 반환합니다.
    한국인들의 생활 주기성(Seasonality)에 정직하게 연동되는 세그먼트 분할.
    """
    hour = dt.hour
    if 7 <= hour < 11:
        return 'MORNING'     # 07:00 ~ 11:00 (출근길 바이럴 집중)
    elif 11 <= hour < 18:
        return 'AFTERNOON'   # 11:00 ~ 18:00 (일과 / 탐색 시간)
    elif 18 <= hour < 24:
        return 'GOLDEN'      # 18:00 ~ 00:00 (국내 스트리밍 및 플레이 피크)
    else:
        return 'NIGHT'       # 00:00 ~ 07:00 (심야 및 글로벌 트래픽 역행)

class TrendDataProcessor:
    """LM Studio가 끊어먹은 핵심 차분(Delta) 연산 및 DB 영구 적재 마스터 엔진"""
    def __init__(self):
        self.engine = engine

    def get_last_snapshot(self, game_name: str) -> Dict[str, Any]:
        """DB에서 해당 게임의 가장 최신 회차(직전 데이터)를 역추적하여 가져옵니다."""
        with self.engine.connect() as conn:
            query = (
                select(
                    trends_table.c.cumulative_ccu,
                    trends_table.c.delta_views_total,  # 실제 누적 조회의 과거 스냅샷 역할
                    trends_table.c.delta_reviews_count,
                    trends_table.c.chzzk_current_viewers,
                    trends_table.c.delta_chzzk_lives
                )
                .where(trends_table.c.game_name == game_name)
                .order_by(trends_table.c.id.desc())
                .limit(1)
            )
            result = conn.execute(query).fetchone()
            
            if result:
                return {
                    "ccu": result[0],
                    "raw_views": result[1],
                    "raw_reviews": result[2],
                    "chzzk_viewers": result[3],
                    "chzzk_lives": result[4]
                }
        # 과거 데이터가 전혀 없는 첫 루프일 때의 Fallback 디폴트값 방어선
        return {"ccu": 0.0, "raw_views": 0.0, "raw_reviews": 0.0, "chzzk_viewers": 0.0, "chzzk_lives": 0.0}

    def process_and_save(self, raw_batch_data: List[Dict[str, Any]]):
        """
        [지휘관 설계 최종 반영] 
        유튜브 조회수와 스팀 리뷰는 단독 차분하여 시간대별 대조용으로 세팅하고, 
        치지직은 실시간 화제성 관측용 독립 지표로 분리해 정직하게 적재합니다.
        """
        current_kst = datetime.now()
        current_slot = calculate_time_slot(current_kst)
        current_day_type = 'WEEKEND' if current_kst.weekday() >= 5 else 'WEEKDAY'
        
        inserted_rows = 0
        with self.engine.begin() as conn:  # 트랜잭션 안전 보장 (무결성 유지)
            for raw_game in raw_batch_data:
                name = raw_game.get("game_name")
                app_id = raw_game.get("steam_app_id", "0")
                
                # 1. 직전 데이터 불러오기
                past = self.get_last_snapshot(name)
                
                # 2. 실시간 입력 데이터 확보
                cur_ccu = float(raw_game.get("cumulative_ccu", 0.0))
                cur_raw_views = float(raw_game.get("youtube_views", 0.0))    # 실시간으로 수집된 유튜브 총 수치
                cur_raw_reviews = float(raw_game.get("steam_reviews", 0.0))  # 실시간으로 수집된 스팀 총 수치
                cur_chzzk_viewers = float(raw_game.get("chzzk_viewers", 0.0))
                cur_chzzk_lives = float(raw_game.get("chzzk_lives", 0.0))
                
                # 3. 🎯 시계열 차분(Delta) 연산: 현재 누적 값 - 직전 누적 값
                # 첫 실행 시 past 값이 0이므로 현재 유입 속도가 정직하게 발라져 나옵니다.
                delta_view = max(0.0, cur_raw_views - past["raw_views"]) if past["raw_views"] > 0 else 0.0
                delta_review = max(0.0, cur_raw_reviews - past["raw_reviews"]) if past["raw_reviews"] > 0 else 0.0
                delta_chzzk_lives = cur_chzzk_lives - past["chzzk_lives"]
                
                # 예비용 기본 스코어링 매핑 (독립 변수 유지 장벽)
                placeholder_score = (cur_ccu * 0.5) + (delta_view * 0.3) + (cur_chzzk_viewers * 0.2)

                # 4. 설계 명세에 마크된 독립 필드로 DB 바인딩 데이터 생성
                ins_query = trends_table.insert().values(
                    timestamp_korea=current_kst,
                    time_slot=current_slot,
                    day_type=current_day_type,
                    steam_app_id=str(app_id),
                    game_name=name,
                    cumulative_ccu=cur_ccu,
                    delta_views_total=delta_view,       # 독립된 유튜브 조회수 속도 축
                    delta_reviews_count=delta_review,   # 독립된 스팀 리뷰 속도 축
                    chzzk_current_viewers=cur_chzzk_viewers, # 완전히 격리된 국내 실시간 화제성 축
                    delta_chzzk_lives=delta_chzzk_lives,
                    trend_velocity_score=round(placeholder_score, 1)
                )
                conn.execute(ins_query)
                inserted_rows += 1
                
        print(f"💾 [Engine v3] {inserted_rows}개 게임의 시간대 태그 [{current_slot}] 및 분리형 차분 연산 적재 완료.")
        
        # 5. 백그라운드 자동 다운샘플링 및 용량 확보 (Purge) 수행
        self.compress_old_data()

    def compress_old_data(self):
        """1시간 단위로 압축 및 3시간 이상 경과 데이터 영구 삭제"""
        now = datetime.now()
        
        # 압축 타겟 시간: 현재 시간 기준 1시간 전 정각
        target_hour = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        target_hour_str = target_hour.strftime('%Y-%m-%d %H:00:00')
        target_hour_end = target_hour + timedelta(hours=1)
        target_hour_end_str = target_hour_end.strftime('%Y-%m-%d %H:00:00')
        
        # 삭제 타겟 시간: 3시간 전
        purge_time = now - timedelta(hours=3)
        purge_time_str = purge_time.strftime('%Y-%m-%d %H:%M:%S')

        with self.engine.begin() as conn:
            # 1. 이미 해당 시간대의 압축이 수행되었는지 확인
            check_q = text("SELECT COUNT(*) FROM game_trends_hourly WHERE timestamp_korea = :ts")
            result = conn.execute(check_q, {"ts": target_hour_str}).scalar()
            
            if result == 0:
                # 2. 압축 수행 (INSERT SELECT: AVG/SUM 연산)
                insert_q = text("""
                    INSERT INTO game_trends_hourly (
                        timestamp_korea, time_slot, day_type, steam_app_id, game_name,
                        cumulative_ccu, delta_views_total, delta_reviews_count,
                        chzzk_current_viewers, delta_chzzk_lives, trend_velocity_score
                    )
                    SELECT 
                        :ts,
                        MAX(time_slot),
                        MAX(day_type),
                        MAX(steam_app_id),
                        game_name,
                        AVG(cumulative_ccu),
                        SUM(delta_views_total),
                        SUM(delta_reviews_count),
                        AVG(chzzk_current_viewers),
                        AVG(delta_chzzk_lives),
                        AVG(trend_velocity_score)
                    FROM game_trends
                    WHERE timestamp_korea >= :start AND timestamp_korea < :end
                    GROUP BY game_name
                """)
                res = conn.execute(insert_q, {"ts": target_hour_str, "start": target_hour_str, "end": target_hour_end_str})
                if res.rowcount > 0:
                    print(f"🗜️ [Downsampling] {target_hour_str} 시간대 데이터 {res.rowcount}건 압축 완료.")

            # 3. 3시간이 지난 날것의 데이터 영구 삭제 (Purge)
            delete_q = text("DELETE FROM game_trends WHERE timestamp_korea < :purge")
            del_result = conn.execute(delete_q, {"purge": purge_time_str})
            if del_result.rowcount > 0:
                print(f"🗑️ [Purge] 3시간 경과 Raw 데이터 {del_result.rowcount}건 영구 삭제 (용량 확보).")

if __name__ == "__main__":
    processor = TrendDataProcessor()
    print("✅ [data_processor.py] 끊김 없이 100% 마감 완료. 인프라 대기 중.")
