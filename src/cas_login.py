"""
CAS (Central Authentication Service) login flow for SDU aTrust VPN.
Uses HTTP-based CAS authentication to obtain a ticket,
then Selenium to complete the browser-side login.
"""

import time

from loguru import logger

from core import ATrustLogin, prompt_if_missing, load_credentials, save_credentials
from sdu_cas import SDUCAS, DeviceFingerprint, CasException

portal_addr = "https://vpn.sdu.edu.cn"
cas_service = "https://vpn.sdu.edu.cn:443/passport/v1/auth/cas"


def run(username=None, password=None, keepalive=200, data_dir="./data",
        driver_type=None, driver_path=None, browser_path=None,
        interactive=True, fingerprint=None):

    saved = load_credentials(data_dir)
    username = username if username is not None else saved.get("username")
    password = password if password is not None else saved.get("password")
    fingerprint = fingerprint if fingerprint is not None else saved.get("fingerprint")

    username = prompt_if_missing(username, "统一认证学号", interactive=interactive, required=True)
    password = prompt_if_missing(password, "统一认证密码", interactive=interactive, required=True, secure=True)
    fingerprint = prompt_if_missing(fingerprint, "设备指纹", interactive=interactive, default="aTrustLogin")

    save_credentials(data_dir, {
        "username": username,
        "password": password,
        "fingerprint": fingerprint,
    })

    fps = DeviceFingerprint(fingerprint)
    cas_client = SDUCAS(fingerprint=fps)

    logger.debug("Opening Web Browser...")
    at = ATrustLogin(data_dir=data_dir, portal_address=portal_addr,
                     driver_type=driver_type, driver_path=driver_path,
                     browser_path=browser_path, interactive=interactive)

    def _do_cas_login():
        logger.debug("通过 CAS 获取 ticket ...")
        ticket_url = cas_client.get_ticket_url(cas_service, username, password, interactive)

        logger.debug("导航到 ticket URL ...")
        at.navigate_and_wait(ticket_url)

        logged = at.is_logged()
        if not logged and at.handle_trust_terminal():
            at.handle_sms_auth()

        logged = at.is_logged()
        url_snippet = str(at.driver.current_url)[:80] if at.driver.current_url else "about:blank"
        logger.debug(f"CAS 登录流程完成, logged={logged}, url={url_snippet}")
        return logged
    
    tolerance = 3
    while True:
        try:
            logged = at.is_logged()
            if not logged:
                logger.info("Login status is invalid, authenticating via CAS ...")
                logged = _do_cas_login()

                if not logged:
                    current_url = str(at.driver.current_url)[:100]
                    logger.warning(f"Authenticating failed, current_url={current_url}")
                    at.delay_loading()
                    continue
                else:
                    logger.info("Authenticating success.")
                    tolerance = 3

            logger.info(f"Session active.")

            if keepalive <= 0:
                logger.info("Keepalive disabled, idling ...")
                while True:
                    time.sleep(86400)

            time.sleep(keepalive)
            at.navigate_and_wait(portal_addr)
        
        except CasException as e:
            logger.error(f"CAS 登录错误: {e}")
            tolerance -= 1
            if tolerance == 0:
                exit(1)
            at.delay_loading()
        except Exception as e:
            logger.error("An error occurred, retrying ...")
            logger.exception(e)
            tolerance -= 1
            if tolerance == 0:
                exit(1)
            at.delay_loading()
