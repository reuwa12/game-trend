import os
import json
import time
from datetime import datetime
import requests
import pandas as pd

# 필수 모듈 임포트 검증
try:
    from yt_collector import YouTubeTrendCollector
    from data_processor import TrendProcessor
except ImportError as e:
    print("="*60)
    print(f"🚨 모듈 임포트 오류 발생: {e}")
    print("⚠️ 'data_processor.py'와 'yt_collector.py'가 현재 폴더에 있는지 확인해주세요.")
    print("="*60)
    exit()

class MainPipeline:
    def __init__(self):
        self.steam_key = os.getenv("STEAM_API_KEY")
        self.yt_collector = YouTubeTrendCollector()
        self.processor = TrendProcessor()
        
        # 공식 스팀 AppID 매핑 완료 (정확한 실데이터 수집용)
        self.target_games = {
            "Palworld": "2394300",
            "Enshrouded": "1203620",
            "Rust": "252490"
        }
        
        os.makedirs("sessions", exist_ok=True)

    def fetch_single_steam_ccu(self, app_id):
        """스팀 공식 API 엔드포인트를 호출하여 개별 게임의 실시간 CCU를 안전하게 가져옵니다."""
        if not self.steam_key:
            print("🚨 [Warning] STEAM_API_KEY 환경변수가 없어 스팀 라이브 데이터 수집을 건너뜁니다.")
            return 0
            
        url = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
        params = {
            "key": self.steam_key,
            "appid": app_id
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json().get("response", {}).get("player_count", 0)
        except Exception as e:
            print(f"[Error] 스팀 CCU 수집 실패 (AppID: {app_id}): {e}")
        return 0

    def run_pipeline(self):
        print("=" * 60)
        print("    🎮 REAL-TIME GAME TREND ANALYSIS PIPELINE (v1.0)    ")
        print("=" * 60)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_data = {
            "collected_at": datetime.now().isoformat(),
            "games": {}
        }

        # 1. 스팀 CCU 및 유튜브 실데이터 수집 연동
        print("\n[Step 1] 실시간 라이브 API 수집 파이프라인 가동 중...")
        for game_name, app_id in self.target_games.items():
            print(f" 🔄 '{game_name}' 라이브 데이터 추출 중...")
            
            # 진짜 실시간 스팀 동접자 확보
            ccu = self.fetch_single_steam_ccu(app_id)
            
            # 캐싱 및 게이밍 카테고리가 적용된 진짜 유튜브 지표 확보
            yt_metrics = self.yt_collector.fetch_game_metrics(game_name)
            
            raw_data["games"][game_name] = {
                "steam_appid": app_id,
                "current_ccu": ccu,
                "youtube_trend": yt_metrics
            }

        # 2. 데이터 통합 적재 (JSON 파일 저장)
        file_path = f"sessions/trend_raw_{timestamp}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=4, ensure_ascii=False)
        print(f"💾 [Success] 100% 라이브 원본 데이터가 적재되었습니다: {file_path}")
        
        time.sleep(0.5)

        # 3. 데이터 가공 및 Pandas 핵심 지표 연산
        print("\n[Step 2] 데이터 프로세싱 및 핵심 비즈니스 지표 연산 가동...")
        matrix_df = self.processor.get_latest_matrix()

        # 4. 최종 터미널 리포트 대시보드 출력
        print("\n[Step 3] 최종 의사결정 라이브 매트릭스 도출 완료\n")
        if matrix_df.empty:
            print("❌ 출력할 데이터가 존재하지 않습니다. 인프라를 점검하세요.")
        else:
            output_cols = ['game_name', 'current_ccu', 'yt_search_volume', 'hype_ratio', 'engagement_score']
            display_df = matrix_df[output_cols].rename(columns={
                'game_name': '게임 명',
                'current_ccu': '실시간 CCU',
                'yt_search_volume': '유튜브 버즈량',
                'hype_ratio': 'Hype Ratio',
                'engagement_score': '종합 관여도'
            })
            print(display_df.to_string(index=False))
            
        print("\n" + "=" * 60)
        print("⚙️ 분석 완료. 이 라이브 데이터를 지휘관(안티그래비티)에게 보고하십시오.")
        print("=" * 60)

if __name__ == "__main__":
    pipeline = MainPipeline()
    pipeline.run_pipeline()
