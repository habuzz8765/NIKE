import os
import json
import time
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains

# ---------------------------------------------------------
# 설정 파일 로드
# ---------------------------------------------------------
def load_config():
    with open("sync_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------
# 한터차트 (Physical) 크롤러 (Buzz님 검증 코드 이식)
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n" + "="*50)
    print(f"[Hanteo] 피지컬 일간 차트 수집 시작...")
    print("="*50)
    
    driver = None
    hanteo_data = []
    scrape_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        print("🚀 한터차트 접속 중...")
        driver.get("https://www.hanteochart.com/ko/charts/album/daily")
        time.sleep(12) 
        
        # 1. '일간' 탭 명시적 클릭 (투명도 0%인 가짜 탭 무시)
        print("🔄 '일간' 탭 활성화 확인...")
        js_find_daily_tab = """
        var tabs = document.querySelectorAll('*');
        for (var i = 0; i < tabs.length; i++) {
            if (tabs[i].textContent && tabs[i].textContent.trim() === '일간') {
                var rect = tabs[i].getBoundingClientRect();
                var isVisible = true;
                var curr = tabs[i];
                while(curr && curr !== document.body) {
                    var compStyle = window.getComputedStyle(curr);
                    if(compStyle.display === 'none' || compStyle.visibility === 'hidden' || parseFloat(compStyle.opacity) === 0) {
                        isVisible = false;
                        break;
                    }
                    curr = curr.parentElement;
                }
                if (isVisible && rect.width > 0) return tabs[i];
            }
        }
        return null;
        """
        try:
            daily_tab = driver.execute_script(js_find_daily_tab)
            if daily_tab:
                ActionChains(driver).move_to_element(daily_tab).click().perform()
                time.sleep(4)
        except Exception:
            pass
            
        # 2. '더보기' 버튼 찾기 JS 로직 
        js_find_visible_more = """
        var buttons = document.querySelectorAll('button, a, div, span');
        var valid = [];
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            var text = (btn.textContent || '').replace(/\s+/g, '');
            if (text.includes('더보기')) {
                var rect = btn.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                
                var isVisible = true;
                var curr = btn;
                while(curr && curr !== document.body) {
                    var compStyle = window.getComputedStyle(curr);
                    if(compStyle.display === 'none' || compStyle.visibility === 'hidden' || parseFloat(compStyle.opacity) === 0) {
                        isVisible = false;
                        break;
                    }
                    curr = curr.parentElement;
                }
                
                if (isVisible) {
                    valid.push({ el: btn, y: rect.top + window.scrollY });
                }
            }
        }
        
        if (valid.length === 0) return null;
        
        valid.sort((a, b) => a.y - b.y);
        var target = valid[0].el;
        
        var getInnermost = function(node) {
            for (var j = 0; j < node.children.length; j++) {
                var child = node.children[j];
                var cText = (child.textContent || '').replace(/\s+/g, '');
                if (cText.includes('더보기')) {
                    return getInnermost(child);
                }
            }
            return node;
        };
        return getInnermost(target);
        """
        
        for i in range(1, 6):
            print(f"🔄 {i}번째 데이터 확장 시도 중...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.4);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.8);")
            time.sleep(2)
            
            target_el = driver.execute_script(js_find_visible_more)
            if target_el:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_el)
                time.sleep(2)
                try:
                    ActionChains(driver).move_to_element(target_el).click().perform()
                    print(f"✅ {i}번째 진짜 '일간 차트 더보기' 물리적 클릭 성공!")
                except Exception:
                    driver.execute_script("arguments[0].click();", target_el)
                    print(f"✅ {i}번째 진짜 '일간 차트 더보기' JS 보조 클릭 성공!")
                time.sleep(6) 
            else:
                print(f"⚠️ {i}번째: 화면에 활성화된 '더보기'가 없습니다.")
                break
                
        print("🔍 최종 데이터 수집 시작 (활성 탭 전용)...")
        # 3. 데이터 추출 JS 로직
        js_extract_data = """
        var rows = document.querySelectorAll('div.chart-item.rank-data');
        var result = [];
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            
            var isVisible = true;
            var curr = row;
            while(curr && curr !== document.body) {
                var compStyle = window.getComputedStyle(curr);
                if(compStyle.display === 'none' || compStyle.visibility === 'hidden' || parseFloat(compStyle.opacity) === 0) {
                    isVisible = false;
                    break;
                }
                curr = curr.parentElement;
            }
            
            if (!isVisible) continue;
            
            var leftEl = row.querySelector('div.left');
            var centerEl = row.querySelector('div.center');
            var rightEl = row.querySelector('div.right');
            
            if (!leftEl || !centerEl || !rightEl) continue;
            
            var rankTexts = leftEl.innerText.trim().split('\\n');
            var rank = rankTexts[0];
            if (isNaN(parseInt(rank))) continue;
            
            var centerTexts = centerEl.innerText.trim().split('\\n');
            var artist = centerTexts.length >= 1 ? centerTexts[centerTexts.length - 1] : '';
            var album = centerTexts.length >= 2 ? centerTexts[centerTexts.length - 2] : '';
            
            var rightTexts = rightEl.innerText.trim().split('\\n');
            var index_score = rightTexts.length >= 1 ? rightTexts[rightTexts.length - 1] : '0';
            var sales = rightTexts.length >= 2 ? rightTexts[rightTexts.length - 2] : '0';
            
            result.push([rank, album, artist, sales, index_score]);
            if (result.length >= 100) break;
        }
        return result;
        """
        
        extracted_rows = driver.execute_script(js_extract_data)
        
        if extracted_rows:
            for r in extracted_rows:
                hanteo_data.append({
                    'tab_type': 'physical',
                    'platform': 'hanteo',
                    'rank': r[0],
                    'album': r[1],
                    'artist': r[2],
                    # Buzz님의 코드는 r[3]에 판매량, r[4]에 지수가 저장됨
                    # Hype 계산용으로는 지수(index_score)를 사용합니다.
                    'sales_index': r[4], 
                    'scrape_time': scrape_time
                })
            
    except Exception as e:
        print(f"[Hanteo] 에러 발생: {e}")
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
