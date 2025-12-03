import streamlit as st
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import shutil

# Page Config
st.set_page_config(page_title="네이버 폐지줍기 Web App", page_icon="💰", layout="wide")

class NaverPayScraper:
    def __init__(self, log_callback):
        self.driver = None
        self.log_callback = log_callback
        self.is_running = True

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def setup_driver(self):
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--headless=new") # Always headless for Cloud
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument("--window-size=1920,1080")
        
        # Headless detection evasion
        options.add_argument("disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        user_agt = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
        options.add_argument(f"user-agent={user_agt}")

        # Check for Chromium binary (common in Linux/Streamlit Cloud)
        chromium_path = "/usr/bin/chromium"
        if os.path.exists(chromium_path):
            options.binary_location = chromium_path

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            self.log(f"❌ 드라이버 설정 중 오류: {e}")
            raise

        # CDP command to remove navigator.webdriver
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

    def login(self, naver_id, naver_pw):
        try:
            self.log("네이버 로그인 페이지 접속 중...")
            self.driver.get("https://nid.naver.com/nidlogin.login")

            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.ID, 'id')))

            # JS Injection for Login (Bypasses captcha/keyboard checks better in headless)
            self.driver.execute_script(f"document.getElementById('id').value = '{naver_id}';")
            time.sleep(0.5)
            self.driver.execute_script(f"document.getElementById('pw').value = '{naver_pw}';")
            time.sleep(0.5)

            login_btn = self.driver.find_element(By.CSS_SELECTOR, 'button.btn_login')
            login_btn.click()

            time.sleep(3) 
            if "nidlogin.login" in self.driver.current_url:
                 self.log("⚠ 로그인 페이지에 머물러 있습니다. 로그인이 실패했을 수 있습니다.")
            else:
                self.log("✅ 네이버 로그인 시도 완료")

        except Exception as e:
            self.log(f"❌ 로그인 중 오류 발생: {e}")
            raise

    def scrape_clien(self):
        try:
            self.log("클리앙 지름게시판 접속 중...")
            self.driver.get("https://www.clien.net/service/board/jirum")
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.list_content')))

            post_links = self.driver.find_elements(By.CSS_SELECTOR, 'div.list_title .list_subject')
            
            jirum_links = []
            for elem in post_links:
                if elem.tag_name == 'a':
                    link = elem
                else:
                    try:
                        link = elem.find_element(By.TAG_NAME, 'a')
                    except:
                        continue
                
                if "네이버" in elem.text:
                    href = link.get_attribute('href')
                    if href:
                        jirum_links.append(href)

            jirum_links = list(set(jirum_links))
            self.log(f"🔍 '네이버' 관련 게시물 {len(jirum_links)}개 수집 완료")
            return jirum_links

        except Exception as e:
            self.log(f"❌ 클리앙 수집 중 오류: {e}")
            return []

    def extract_npay_links(self, jirum_links):
        npay_links = []
        for url in jirum_links:
            if not self.is_running:
                break
            
            self.driver.get(url)
            try:
                article = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.post_view article"))
                )
                a_tags = article.find_elements(By.TAG_NAME, 'a')
                for a in a_tags:
                    href = a.get_attribute('href')
                    if href and 'naver' in href:
                        npay_links.append(href)
            except Exception as e:
                self.log(f"❌ 게시물 처리 실패: {url}, 에러: {e}")
        
        return list(set(npay_links))

    def visit_links(self, npay_links):
        self.log(f"✅ 네이버 링크 {len(npay_links)}개 수집 완료")
        
        progress_bar = st.progress(0)
        
        for i, link in enumerate(npay_links):
            if not self.is_running:
                self.log("🛑 링크 방문 중단됨")
                break
            
            self.log(f"▶ 링크 방문: {link}")
            self.driver.get(link)
            time.sleep(1)

            try:
                popup_close_btn = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div.layer_popup.type_no_points > div > a"))
                )
                popup_close_btn.click()
                self.log("⚡ 포인트 부족 팝업 닫음")
            except TimeoutException:
                 pass
            except Exception as e:
                self.log(f"⚡ 팝업 처리 오류: {e}")

            time.sleep(2)
            progress_bar.progress((i + 1) / len(npay_links))
        
        self.log("🎉 모든 링크 방문 완료!")

    def run(self, naver_id, naver_pw):
        try:
            self.setup_driver()
            self.login(naver_id, naver_pw)
            
            jirum_links = self.scrape_clien()
            if not jirum_links:
                self.log("수집된 게시물이 없습니다.")
                return

            npay_links = self.extract_npay_links(jirum_links)
            if not npay_links:
                self.log("수집된 네이버 페이 링크가 없습니다.")
                return

            self.visit_links(npay_links)

        except Exception as e:
            self.log(f"⚠ 오류 발생: {e}")
        finally:
            if self.driver:
                self.driver.quit()
            self.log("🚪 브라우저 종료")

def main():
    st.title("💰 네이버 폐지줍기 Web App")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("설정")
        naver_id = st.text_input("네이버 ID")
        naver_pw = st.text_input("비밀번호", type="password")
        
        if st.button("실행", type="primary"):
            if not naver_id or not naver_pw:
                st.warning("ID와 비밀번호를 입력해주세요.")
            else:
                st.session_state.logs = []
                st.session_state.is_running = True
                
                log_placeholder = st.empty()
                
                def log_callback(msg):
                    timestamp = time.strftime('%H:%M:%S')
                    formatted_msg = f"[{timestamp}] {msg}"
                    st.session_state.logs.append(formatted_msg)
                    # Use markdown for logs to avoid widget ID issues
                    with log_placeholder.container():
                        st.code("\n".join(st.session_state.logs), language="text")

                scraper = NaverPayScraper(log_callback)
                with st.spinner("작업 실행 중..."):
                    scraper.run(naver_id, naver_pw)
    
    with col2:
        st.subheader("사용 설명서")
        st.info("""
        **📌 사용 방법**
        1. 네이버 ID와 비밀번호를 입력하세요.
        2. '실행' 버튼을 누르면 작업이 시작됩니다.
        3. 로그 창을 통해 진행 상황을 확인할 수 있습니다.
        
        **⚠️ 주의사항**
        - **Streamlit Cloud** 환경에 최적화되었습니다.
        - 브라우저는 보이지 않게(Headless) 실행됩니다.
        - 보안 문자 입력이 뜰 경우 로그인이 실패할 수 있습니다.
        """)

    if 'logs' not in st.session_state:
        st.session_state.logs = []

if __name__ == "__main__":
    main()
