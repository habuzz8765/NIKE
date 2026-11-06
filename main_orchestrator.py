import os
import json
import time
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------
# 설정 파일 로드
# ---------------------------------------------------------
def load_config():
    with open("sync_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------
# 한터차트 (Physical) API 다이렉트 크롤러
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n" + "="*50)
    print(f"[Hanteo] 피지컬(음반) 일간 차트 API 수집 시작...")
    print("="*50)
    
    hanteo_data = []
    scrape_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    
    # 🌟 브라우저(Selenium) 크래시를 원천 차단하기 위해 한터차트의 실제 API 주소를 직접 호출합니다.
    # (주의: date 파라미터를 빈칸으로 보내면 실시간 차트를 뱉어냅니다.)
    api_url = "https://www.hanteochart.com/api/chart/album/real"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.hanteochart.com/networkalbum/real"
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # 한터차트 API의 실제 데이터 배열(list) 접근
            items = data.get('data', [])[:limit]
            
            for idx, item in enumerate(items, 1):
                album_name = item.get('albumName', '정보 없음')
                artist_name = item.get('artistName', '정보 없음')
                # 한터 음반지수 (salesIndex)
                sales_index = str(item.get('salesIndex', '0'))
                
                if not album_name or album_name == "정보 없음":
                    continue
                    
                hanteo_data.append({
                    'tab_type': 'physical',
                    'platform': 'hanteo',
                    'rank': idx,
                    'album': album_name,
                    'artist': artist_name,
                    'sales_index': sales_index,
                    'scrape_time': scrape_time
                })
                print(f"  [{idx}/{limit}] {album_name[:15]}... - {artist_name} (지수: {sales_index})")
        else:
            print(f"[Hanteo] API 접근 거부 (Status Code: {response.status_code})")
            
    except Exception as e:
        print(f"[Hanteo] API 요청 에러 발생: {e}")
        
    return pd.DataFrame(hanteo_data)

# ---------------------------------------------------------
# 디지털 차트 통합 크롤러 (스켈레톤)
# ---------------------------------------------------------
def scrape_digital_charts(jobs):
    print("\n[Digital] 차트 수집기는 다음 페이즈에 병합됩니다.")
    pass

# ---------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------
def main():
    print("NIKE (New Insights for K-pop Explorers) 오케스트레이터 가동\n")
    config = load_config()
    
    physical_df = pd.DataFrame()
    
    for job in config.get("jobs", []):
        if not job.get("enabled", False):
            continue
            
        if job["service"] == "hanteo":
            physical_df = scrape_hanteo_daily(limit=job.get("entity_limit", 100))
        
        elif job["hype_group"] == "digital":
            pass
            
    # 수집 결과 요약 및 CSV 저장
    if not physical_df.empty:
        print(f"\n✅ 한터차트 수집 완료: 총 {len(physical_df)} 건")
        # CSV 저장 (Artifacts 업로드용)
        physical_df.to_csv("hanteo_test_result.csv", index=False, encoding="utf-8-sig")
        print("결과가 hanteo_test_result.csv 로 안전하게 저장되었습니다.")
    else:
        print("\n❌ 한터차트 데이터가 수집되지 않았습니다.")

if __name__ == "__main__":
    main()
