import os
import json
import requests
from datetime import datetime, timedelta

class YouTubeTrendCollector:
    def __init__(self, cache_file="youtube_cache.json", cache_duration_hours=6):
        self.cache_file = cache_file
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.api_key = os.getenv("YOUTUBE_API_KEY", "YOUR_ACTUAL_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3/search"

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self, cache_data):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Warning] 캐시 저장 실패: {e}")

    def fetch_game_metrics(self, game_name):
        cache = self._load_cache()
        now = datetime.now()

        if game_name in cache:
            cached_time = datetime.fromisoformat(cache[game_name]["collected_at"])
            if now - cached_time < self.cache_duration:
                print(f"📦 [Cache Hit] '{game_name}' 데이터는 캐시에서 불러옵니다. (할당량 절약)")
                return cache[game_name]["data"]

        if self.api_key == "YOUR_ACTUAL_API_KEY" or not self.api_key:
            print(f"⚠️ [Notice] YouTube API Key가 설정되지 않아 '{game_name}' 모의 데이터를 반환합니다.")
            return {"search_volume_score": 50, "recent_videos_count": 30}

        print(f"🌐 [API Call] YouTube Data API 호출 중: {game_name}")
        params = {
            "key": self.api_key,
            "q": f"{game_name} gameplay",
            "part": "snippet",
            "type": "video",
            "videoCategoryId": "20",
            "maxResults": 50,
            "order": "date"
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            if response.status_code == 200:
                result_data = response.json()
                total_results = result_data.get("pageInfo", {}).get("totalResults", 0)
                items_count = len(result_data.get("items", []))

                metrics = {
                    "search_volume_score": min(int(total_results / 1000), 100) if total_results else 50,
                    "recent_videos_count": items_count
                }

                cache[game_name] = {
                    "collected_at": now.isoformat(),
                    "data": metrics
                }
                self._save_cache(cache)
                return metrics
            else:
                print(f"[Error] 유튜브 API 응답 실패 ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"[Error] 유튜브 수집 중 에러 발생: {e}")

        return {"search_volume_score": 0, "recent_videos_count": 0}

if __name__ == "__main__":
    collector = YouTubeTrendCollector()
    test_game = "Palworld"
    data = collector.fetch_game_metrics(test_game)
    print(f"📊 테스트 결과 [{test_game}]: {data}")
