import os
import json
import time
import re
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# ---------------------------------------------------------
# 설정 파일 로드
# ---------------------------------------------------------
def load_config():
    with open("sync_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------
# 한터차트 (Physical) 크롤러 (하드코어 텍스트 역추적 방식)
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n" + "="*50)
    print(f"[Hanteo] 피지컬 일간 차트 텍스트 역추적 수집 시작...")
    print("="*50)
    
    driver = None
    hanteo_data = []
    scrape_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        # 불필요한 미디어 로딩 전면 차단
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.cookies": 2,
            "profile.managed_default_content_settings.javascript": 1,
            "profile.managed_default_content_settings.plugins": 2,
            "profile.managed_default_content_settings.popups": 2,
            "profile.managed_default_content_settings.geolocation": 2,
            "profile.managed_default_content_settings.media_stream": 2,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_window_size(1920, 1080)
        
        url = "https://www.hanteochart.com/ko/charts/album/daily"
        driver.get(url)
        
        # DOM이 그려질 때까지 넉넉하게 무조건 10초 대기
        time.sleep(10)
        
        # 100위까지 모든 데이터가 렌더링되도록 끝까지 스크롤 다운
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
        print("  [Hanteo] 스크롤 및 렌더링 완료. 화면 텍스트 딥러닝 분석 시작...")
        
        # 🌟 핵심: HTML 구조나 클래스를 무시하고, 화면에 보이는 전체 텍스트 덩어리를 가져옵니다.
        body_element = driver.find_element(By.TAG_NAME, "body")
        page_text = body_element.text
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        rank_counter = 1
        i = 0
        
        while i < len(lines) and rank_counter <= limit:
            line = lines[i]
            
            # 1, 2, 3... 순서대로 정확히 순위 숫자만 있는 라인을 찾음
            if line == str(rank_counter):
                try:
                    # 해당 순위 번호 아래쪽으로 나타나는 10줄의 텍스트를 분석 
                    info_lines = []
                    for j in range(1, 15):
                        if i+j >= len(lines): break
                        txt = lines[i+j]
                        # '-', 'NEW', 'UP', 'DOWN' 등 차트 등락 관련 기호 및 단순 숫자(순위 상승/하락 폭) 제거
                        if txt not in ['NEW', '-', 'UP', 'DOWN'] and not txt.replace(',', '').isdigit() and txt != '앨범 정보':
                            info_lines.append(txt)
                        # 앨범명, 아티스트, 지수(판매량) 등 충분한 데이터(4~5줄)가 모이면 중단
                        if len(info_lines) >= 4:
                            break
                            
                    # info_lines 중 가장 처음 나오는 문자가 보통 앨범명, 그다음이 아티스트명
                    album_name = info_lines[0] if len(info_lines) > 0 else "정보 없음"
                    artist_name = info_lines[1] if len(info_lines) > 1 else "정보 없음"
                    
                    # 지수(판매량)는 콤마(,)가 포함된 숫자를 우선적으로 찾음
                    sales = "0"
                    for txt in lines[i:i+15]: # 원본 라인에서 다시 검색
                        if ',' in txt and any(c.isdigit() for c in txt) and txt != album_name and txt != artist_name:
                            sales = txt
                            break
                    
                    # 회사 소개나 상단 메뉴가 잘못 잡히는 것 방지
                    if album_name not in ["홈", "차트", "월드", "회사 소개"] and album_name != "정보 없음":
                        hanteo_data.append({
                            'tab_type': 'physical',
                            'platform': 'hanteo',
                            'rank': rank_counter,
                            'album': album_name,
                            'artist': artist_name,
                            'sales_index': sales,
                            'scrape_time': scrape_time
                        })
                        print(f"  [{rank_counter}/{limit}] {album_name[:15]}... - {artist_name} (지수: {sales})")
                        rank_counter += 1 # 1위를 찾으면 2위를 찾으러 감
                        i += 3 # 데이터 찾았으므로 인덱스 점프
                        continue
                        
                except Exception as e:
                    pass
            i += 1

        if not hanteo_data:
             print("  [Hanteo] ⚠️ 텍스트 분석 실패. 사이트 로딩 지연 또는 차단 의심.")
             
    except Exception as e:
        print(f"[Hanteo] 셀레니움 드라이버 에러 발생: {e}")
    finally:
        if driver: driver.quit()
        
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
        physical_df.to_csv("hanteo_test_result.csv", index=False, encoding="utf-8-sig")
        print("결과가 hanteo_test_result.csv 로 안전하게 저장되었습니다.")
    else:
        print("\n❌ 한터차트 데이터가 수집되지 않았습니다.")

if __name__ == "__main__":
    main()
