import getpass
import os.path
import pickle
import platform
import re
import json
import socket
import subprocess
import time
import urllib.request
from typing import Dict, List, Any
from urllib.parse import urlparse

import pyotp
from loguru import logger
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def prompt_if_missing(value, name, interactive=True, default=None, required=False, secure=False):
    if value is not None:
        return value

    if interactive:
        if default:
            prompt = f"请输入 {name} (可选): "
        else:
            prompt = f"请输入 {name}: "
        if secure:
            result = getpass.getpass(prompt).strip()
        else:
            result = input(prompt).strip()
        if not result:
            if default is not None:
                return default
            if required:
                logger.error(f"缺少必要参数: {name}")
                exit(1)
        return result

    if default is not None:
        return default
    if required:
        logger.error(f"缺少必要参数: {name}")
        exit(1)
    return ""


def load_credentials(data_dir):
    path = os.path.join(data_dir, "ATrustLoginCredential.pkl")
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def save_credentials(data_dir, creds):
    path = os.path.join(data_dir, "ATrustLoginCredential.pkl")
    with open(path, "wb") as f:
        pickle.dump(creds, f)


class ATrustLoginStorage(BaseModel):
    cookies: List[Dict[str, Any]]
    local_storage: Dict[str, Any]


class ATrustLogin:
    def __init__(self, portal_address, driver_path=None, browser_path=None, driver_type=None, 
                 data_dir="data", cookie_tid=None, cookie_sig=None, interactive=False):
        self.data_dir = data_dir
        self.interactive = interactive
        self.portal_address = portal_address
        self.portal_host = urlparse(portal_address).hostname
        self.cookie_tid = cookie_tid
        self.cookie_sig = cookie_sig

        self.must_be_logged_keywords = ['app_center', 'user_info', 'app_apply', 'device_manage']
        self.must_not_logged_keywords = ['login', 'totpAuth', 'captcha', 'page_auth_trust_terminal', 'smsAuth']

        if driver_type is None:
            system = platform.system()
            if system == "Windows":
                driver_type = "edge"
            else:
                driver_type = "chrome"

        logger.debug(f"Driver: {driver_type}: {driver_path}")

        if driver_type == "edge":
            from selenium.webdriver.edge.options import Options
            from selenium.webdriver.edge.service import Service

            self.options = Options()
            self.options.add_argument("--user-data-dir=/tmp/edge-data")
            self.options.add_argument('--profile-directory=ATrustLogin')
            self.options.add_argument("--ignore-certificate-errors")
            self.options.add_argument("--ignore-ssl-errors")
            self.options.add_argument("--no-sandbox")
            self.options.add_argument("--lang=zh-CN")
            self.options.add_argument("--disable-gpu")
            self.options.add_argument("--disable-extensions")
            self.options.add_argument("--disable-web-security")
            self.options.add_argument("--allow-insecure-localhost")
            self.options.add_argument("--window-size=896,672")

            if browser_path is not None:
                self.options.binary_location = browser_path

            self.driver = webdriver.Edge(service=Service(driver_path), options=self.options)
            
        else:
            from selenium.webdriver.chrome.options import Options

            DEBUG_PORT = "12345"
            PROFILE_DIR = "Default"

            binary_location = browser_path or "/usr/bin/chromium"
            chrome_data_dir = os.path.join("/tmp", "chrome-data")
            log_file = os.path.join(chrome_data_dir, "chrome.log")
            os.makedirs(chrome_data_dir, exist_ok=True)

            logger.info(f"Starting Chrome with debug port {DEBUG_PORT}")
            self.chrome_process = subprocess.Popen([
                    binary_location,
                    f"--remote-debugging-port={DEBUG_PORT}",
                    f"--user-data-dir={chrome_data_dir}",
                    f"--profile-directory={PROFILE_DIR}",
                    "--ignore-certificate-errors",
                    "--ignore-ssl-errors", 
                    "--no-sandbox", 
                    "--lang=zh-CN", 
                    "--disable-gpu", 
                    "--disable-extensions",
                    "--disable-web-security",
                    "--allow-insecure-localhost",
                    "--window-size=896,672",
                    "data:,"
                ], stdout=open(log_file, "w"), stderr=subprocess.STDOUT
            )

            logger.info(f"Chrome started, PID {self.chrome_process.pid}, waiting for DevTools ...")
            while True:
                if self.chrome_process.poll() is not None:
                    raise RuntimeError(f"Chrome exited with code {self.chrome_process.returncode}")
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version")
                    logger.info("DevTools ready.")
                    break
                except:
                    time.sleep(3)

            self.options = Options()
            self.options.debugger_address = f"127.0.0.1:{DEBUG_PORT}"
            self.driver = webdriver.Chrome(options=self.options)

        self.wait = WebDriverWait(self.driver, 10)
        logger.debug("Selenium init successfully.")

    def open_portal(self):
        self.driver.get(self.portal_address)

        if self.driver.get_cookie("language"):
            self.driver.delete_cookie("language")
        if self.driver.get_cookie("lang"):
            self.driver.delete_cookie("lang")

        self.driver.add_cookie({
            "name": "language", "value": "zh-CN",
            "domain": self.portal_host, "path": "/",
        })
        self.driver.add_cookie({
            "name": "lang", "value": "zh-cn",
            "domain": self.portal_host, "path": "/",
        })

    def wait_login_page(self):
        self.wait.until(EC.presence_of_element_located((By.ID, "sangfor_main_auth_container")))
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "login-panel")))
        self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    @staticmethod
    def delay_input():
        time.sleep(0.5)

    @staticmethod
    def delay_loading():
        time.sleep(3)

    def find_input_fields(self, element, inputs_found=None):
        if inputs_found is None:
            inputs_found = []

        if element.tag_name == "input":
            placeholder = element.get_attribute("placeholder")
            input_type = element.get_attribute("type")
            if placeholder and ("账号" in placeholder or "account" in placeholder.lower()
                                or "密码" in placeholder or "password" in placeholder.lower()) \
                    and input_type != "hidden":
                inputs_found.append(element)
                if len(inputs_found) == 2:
                    return inputs_found

        child_elements = element.find_elements(By.XPATH, "./*")
        for child in child_elements:
            result = self.find_input_fields(child, inputs_found)
            if result and len(result) == 2:
                return result
        return inputs_found

    def enter_credentials(self, username, password):
        try:
            element = self.driver.find_element(
                By.XPATH, "//div[contains(@class, 'server-name') and contains(text(), '本地密码')]")
            if element.is_displayed():
                self.delay_input()
                self.scroll_and_click(element)
        except Exception:
            pass

        main_auth_div = self.driver.find_element(By.ID, "sangfor_main_auth_container")
        input_fields = self.find_input_fields(main_auth_div)

        if len(input_fields) >= 2:
            username_input = input_fields[0]
            password_input = input_fields[1]

            self.scroll_and_click(self.wait.until(EC.element_to_be_clickable(username_input)))
            self.delay_input()
            username_input.clear()
            username_input.send_keys(username)

            self.scroll_and_click(self.wait.until(EC.element_to_be_clickable(password_input)))
            self.delay_input()
            password_input.clear()
            password_input.send_keys(password)

            checkbox = main_auth_div.find_element(By.XPATH, "//input[@type='checkbox']")
            if not checkbox.is_selected():
                self.delay_input()
                self.scroll_and_click(checkbox)

            logger.debug("Filled username and password")
        else:
            logger.info("未找到用户名或密码输入框")

    def click_login_button(self):
        login_panel = self.driver.find_element(By.CLASS_NAME, "login-panel")
        buttons = login_panel.find_elements(By.TAG_NAME, "button")

        for button in buttons:
            button_text = button.text.lower()
            if "登录" in button_text or "login" in button_text or "log in" in button_text:
                self.scroll_and_click(button)
                return
        logger.info("未找到符合条件的登录按钮")

    def load_storage(self):
        try:
            if os.path.exists(os.path.join(self.data_dir, "ATrustLoginStorage.pkl")):
                with open(os.path.join(self.data_dir, "ATrustLoginStorage.pkl"), "rb") as f:
                    data = pickle.load(f)
                    self.driver.delete_all_cookies()
                    for cookie in data.cookies:
                        self.driver.add_cookie(cookie)
                    for key, value in data.local_storage.items():
                        self.driver.execute_script(
                            f"window.localStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
                        )
                    logger.info("Loaded storage data")
        except FileNotFoundError:
            logger.info("未找到存储的数据")

        self.set_cli_cookie(force=False)

    def scroll_and_click(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView();", element)
        element.click()
        return element

    def set_cli_cookie(self, force=False):
        if self.cookie_tid and (force or not self.driver.get_cookie("tid")):
            self.driver.delete_cookie("tid")
            self.driver.add_cookie({
                "name": "tid", "value": self.cookie_tid,
                "domain": self.portal_host, "path": "/",
            })

        if self.cookie_sig and (force or not self.driver.get_cookie("tid.sig")):
            self.driver.delete_cookie("tid.sig")
            self.driver.add_cookie({
                "name": "tid.sig", "value": self.cookie_sig,
                "domain": self.portal_host, "path": "/",
            })

    def require_interact(self):
        if self.interactive:
            input("Press any key to continue")
        else:
            raise Exception("User Interact required")

    def init(self):
        self.open_portal()
        self.wait_login_page()
        self.delay_loading()
        self.load_storage()

    def login(self, username, password, totp_key, **kwargs):
        self.init()

        if self.is_logged():
            logger.info("Already logged in")
            return True

        self.enter_credentials(username=username, password=password)
        self.delay_input()
        self.click_login_button()

        logger.info("Performed basic login action")
        self.delay_loading()
        logger.debug("Checking captcha ...")

        if "图形校验码" in self.driver.page_source:
            if 'is_retried' not in kwargs:
                self.set_cli_cookie(force=True)
                self.driver.refresh()
                self.login(username, password, totp_key, is_retried=True)
                return
            else:
                logger.warning("Need to handle captcha, press any key to continue")
                self.require_interact()

        if "TOTP" in self.driver.page_source and "二次认证" in self.driver.page_source:
            if totp_key is not None:
                totp = pyotp.TOTP(totp_key)
                totp_code = totp.now()

                logger.info(f"TOTP code: {totp_code}")
                totp_input = self.driver.find_element(By.XPATH, "//input[contains(@class, 'totp')]")

                self.scroll_and_click(self.wait.until(EC.element_to_be_clickable(totp_input)))
                self.delay_input()
                totp_input.send_keys(totp_code)

                submit_button = self.driver.find_element(
                    By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
                self.wait.until(EC.element_to_be_clickable(submit_button))
                self.delay_input()
                self.scroll_and_click(submit_button)
                logger.info(f"Performed TOTP login action with code: {totp_code}")
                self.delay_loading()
            else:
                logger.info("Need to handle TOTP, press any key to continue")
                self.require_interact()

        logger.info("Performed verification code login action")

        if self.is_logged():
            logger.info("Login Success")
            self.update_storage()
            return True

    def is_logged(self):
        if self.driver.current_url.startswith('about:'):
            return None

        url = urlparse(self.driver.current_url)

        if any(keyword in url.fragment for keyword in self.must_be_logged_keywords):
            return True
        if any(keyword in url.fragment for keyword in self.must_not_logged_keywords):
            return False

        page = self.driver.page_source
        return "自动化工作台" in page and "本地密码" not in page and "Unknown error500" not in page

    def navigate_and_wait(self, url):
        self.driver.get(url)
        WebDriverWait(self.driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        self.delay_loading()

    def handle_trust_terminal(self):
        try:
            btn = WebDriverWait(self.driver, 3).until(EC.element_to_be_clickable((By.XPATH, 
                "//button[contains(@class, 'footer-btn') and (contains(., '立即绑定') or contains(., 'Bind Now'))]"
            )))
        except Exception:
            logger.debug("未检测到授信终端绑定按钮")
            return False

        answer = input("检测到授信终端绑定页面，是否绑定？(default y/n): ").strip().lower()
        if answer == 'n':
            logger.info("已取消授信终端绑定，登入失败")
            exit(0)

        self.scroll_and_click(btn)
        logger.info("等待跳转至验证码页面 ...")
        self.delay_loading()
        self.delay_loading()
        return True

    def handle_sms_auth(self):
        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.CLASS_NAME, "second-auth-template--main"))
            )
        except Exception:
            logger.debug("未检测到短信验证码页面")
            return

        hint_text = ""
        try:
            hint_elem = self.driver.find_element(By.CLASS_NAME, "auth-hint")
            hint_text = hint_elem.text.strip()
            logger.info(hint_text)
        except Exception:
            pass

        sms_input = self.driver.find_element(By.CLASS_NAME, "ix-input-inner")

        while True:
            code = input(f"请输入短信验证码 (或输入 'r' 重新发送): ").strip()

            if code.lower() == 'r':
                self._click_resend_sms()
                continue

            if not code:
                continue

            self.scroll_and_click(self.wait.until(EC.element_to_be_clickable(sms_input)))
            self.delay_input()
            sms_input.clear()
            sms_input.send_keys(code)
            self.delay_input()

            try:
                submit = WebDriverWait(self.driver, 3).until(EC.element_to_be_clickable((By.XPATH,
                    "//button[@type='submit' and contains(@class, 'ix-button-primary') and (contains(., '确定') or contains(., 'OK'))]"
                )))
                self.scroll_and_click(submit)
            except Exception:
                logger.warning("未找到提交按钮，请手动操作")
                self.require_interact()

            logger.info("已提交短信验证码")
            self.delay_loading()
            self.delay_loading()
            break

    def _click_resend_sms(self):
        try:
            resend_btn = self.driver.find_element(By.XPATH,
                "//button[contains(@class, 'ix-button-link') and (contains(., '重新获取') or contains(., 'Send Again'))]")
        except Exception:
            logger.warning("未找到重新获取按钮")
            return

        if resend_btn.is_enabled():
            self.scroll_and_click(resend_btn)
            logger.info("已请求重新发送验证码")
            self.delay_input()
        else:
            m = re.search(r'\((\d+)\)', resend_btn.text)
            remaining = m.group(1) if m else "?"
            logger.info(f"重新获取按钮仍在倒计时 ({remaining}秒)，请稍后再试")
            self.delay_input()

    def close(self):
        self.driver.quit()
        if hasattr(self, 'chrome_process') and self.chrome_process.poll() is None:
            self.chrome_process.terminate()
            try:
                self.chrome_process.wait(timeout=5)
            except:
                self.chrome_process.kill()
                self.chrome_process.wait()

    def __enter__(self):
        return self

    def update_storage(self):
        data = ATrustLoginStorage(
            cookies=self.driver.get_cookies(),
            local_storage=self.driver.execute_script("return window.localStorage")
        )
        with open(os.path.join(self.data_dir, "ATrustLoginStorage.pkl"), "wb") as f:
            pickle.dump(data, f)

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @staticmethod
    def wait_for_port(port, host='localhost'):
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                try:
                    s.connect((host, port))
                    logger.info(f"Detected aTrust is listening on port {port}")
                    s.close()
                    break
                except (socket.timeout, ConnectionRefusedError):
                    logger.info(f"aTrust Port {port} is not yet being listened on. Waiting for aTrust start ...")
                    ATrustLogin.delay_loading()
