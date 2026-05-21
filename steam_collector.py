import asyncio
import aiohttp
from config import TARGET_GAMES, STEAM_FALLBACK_CCU

async def fetch_ccu(session, game):
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={game['appid']}"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                result = data.get('response', {}).get('player_count', 0)
                if result <= 0:
                    return {"name": game['name'], "current_ccu": STEAM_FALLBACK_CCU}
                return {"name": game['name'], "current_ccu": result}
            else:
                return {"name": game['name'], "current_ccu": STEAM_FALLBACK_CCU}
    except Exception as e:
        print(f"[ERROR] {game['name']} - Steam API Timeout. Fallback({STEAM_FALLBACK_CCU}) applied.")
        return {"name": game['name'], "current_ccu": STEAM_FALLBACK_CCU}

async def collect_steam_data_async():
    print("[Steam Collector] 🚀 aiohttp 비동기 CCU 병렬 수집 시작...")
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_ccu(session, game) for game in TARGET_GAMES]
        results = await asyncio.gather(*tasks)
        
    print(f"[Steam Collector] ✅ {len(results)}개 게임 CCU 초고속 수집 완료.")
    return results

def collect_steam_data():
    # 윈도우 환경 asyncio 에러 방지를 위한 이벤트 루프 정책 설정
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(collect_steam_data_async())

if __name__ == "__main__":
    res = collect_steam_data()
    print(res)
