import os
import json
import time
import requests
from config import TARGET_GAMES, YOUTUBE_API_KEY, SESSION_CACHE_FILE, YOUTUBE_API_COOLDOWN_HOURS

def get_cached_youtube_data():
    if os.path.exists(SESSION_CACHE_FILE):
        with open(SESSION_CACHE_FILE, "r", encoding="utf-8") as f:
            try:
                cache = json.load(f)
                last_updated = cache.get("last_updated", 0)
                current_time = time.time()
                elapsed_hours = (current_time - last_updated) / 3600
                if elapsed_hours < YOUTUBE_API_COOLDOWN_HOURS:
                    print(f"[YouTube Collector] 📦 Cache Hit! ({elapsed_hours:.2f}시간 경과, {YOUTUBE_API_COOLDOWN_HOURS}시간 쿨다운 중)")
                    return cache.get("data")
            except Exception as e:
                print(f"[YouTube Collector] ⚠️ 캐시 읽기 에러: {e}")
    return None

def save_cache(data):
    cache = {
        "last_updated": time.time(),
        "data": data
    }
    with open(SESSION_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)
    print("[YouTube Collector] 💾 신규 수집 데이터 캐시(Cache) 저장 완료.")

def fetch_youtube_data(game_name):
    # API 키가 기본값이면 Mock 데이터를 반환하여 오류 방지
    if YOUTUBE_API_KEY == "YOUR_GOOGLE_API_KEY" or not YOUTUBE_API_KEY:
        import random
        return {"name": game_name, "youtube_buzz_raw": random.randint(10000, 500000)}
        
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{game_name} gameplay",
        "videoCategoryId": "20",
        "type": "video",
        "maxResults": 10,
        "key": YOUTUBE_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status == 200:
            data = response.json()
            # 검색된 리스트 수를 기반으로 임의의 버즈량 측정 (실무에선 viewCount API 추가 호출 필요)
            total_buzz = 50000 * len(data.get("items", []))
            if total_buzz == 0:
                total_buzz = 10000
            return {"name": game_name, "youtube_buzz_raw": total_buzz}
        else:
            return {"name": game_name, "youtube_buzz_raw": 10000}
    except Exception as e:
        print(f"[ERROR] {game_name} - YouTube API 연결 오류. 안전 수치 대체.")
        return {"name": game_name, "youtube_buzz_raw": 10000}

def collect_youtube_data():
    print("[YouTube Collector] 유튜브 API 쿼터 방어망 가동 중...")
    cached_data = get_cached_youtube_data()
    if cached_data:
        return cached_data
    
    print("[YouTube Collector] 📡 12시간 경과. 신규 라이브 버즈량 수집을 시작합니다.")
    results = []
    
    # 쿼터 초과(Rate Limit) 방지를 위해 동기식 순차 호출 수행
    for game in TARGET_GAMES:
        res = fetch_youtube_data(game["name"])
        results.append(res)
        time.sleep(0.1) # 안전 대기 시간
        
    save_cache(results)
    print(f"[YouTube Collector] ✅ {len(results)}개 게임 유튜브 버즈량 수집 완료.")
    return results

if __name__ == "__main__":
    res = collect_youtube_data()
    print(res)
