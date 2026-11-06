import os
import json
import time
import re
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
# 한터차트 (Physical) 크롤러 (초고속 정규식 스나이핑 방식)
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n" + "="*50)
    print(f"[Hanteo] 피지컬 일간 차트 초고속 수집 시작...")
    print("="*50)
    
    hanteo_data = []
    scrape_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    
    url = "https://www.hanteochart.com/ko/charts/album/daily"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        # 1. Selenium 없이 순수 requests로 HTML 소스만 0.5초 만에 다운로드
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            html_content = response.text
            
            # 2. 한터차트(Next.js)가 숨겨둔 초기 데이터 보따리(__NEXT_DATA__) 찾기
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_content, re.DOTALL)
            
            if match:
                # 3. JSON 데이터를 파싱하여 우리가 원하는 차트 랭킹 배열만 추출
                next_data = json.loads(match.group(1))
                queries = next_data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
                
                chart_items = []
                # 여러 쿼리 데이터 중 'album'과 'daily'가 포함된 진짜 차트 데이터 찾기
                for q in queries:
                    q_key = str(q.get('queryKey', ''))
                    if 'album' in q_key and 'daily' in q_key:
                        chart_items = q.get('state', {}).get('data', {}).get('data', [])
                        break
                        
                if not chart_items:
                    print("[Hanteo] ⚠️ 차트 데이터 쿼리를 찾을 수 없습니다. (사이트 구조 변경 의심)")
                
                # 4. 추출한 100개의 데이터를 KMI 포맷에 맞게 정제
                chart_items = chart_items[:limit]
                for idx, item in enumerate(chart_items, 1):
                    album_name = item.get('albumName', '정보 없음')
                    artist_name = item.get('artistName', '정보 없음')
                    # 판매량 지수는 숫자로 올 수 있으므로 문자열 변환 및 천 단위 콤마 추가
                    sales_val = item.get('salesIndex', 0)
                    sales = f"{int(sales_val):,}" if sales_val else "0"
                    
                    if not album_name or album_name == "정보 없음":
                        continue
                        
                    hanteo_data.append({
                        'tab_type': 'physical',
                        'platform': 'hanteo',
                        'rank': idx,
                        'album': album_name,
                        'artist': artist_name,
                        'sales_index': sales,
                        'scrape_time': scrape_time
                    })
                    print(f"  [{idx}/{limit}] {album_name[:15]}... - {artist_name} (지수: {sales})")
            else:
                print("[Hanteo] ❌ __NEXT_DATA__ 스크립트 태그를 찾을 수 없습니다.")
        else:
            print(f"[Hanteo] ❌ 페이지 접근 거부 (Status: {response.status_code})")
            
    except Exception as e:
        print(f"[Hanteo] 파싱 에러 발생: {e}")
        
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
