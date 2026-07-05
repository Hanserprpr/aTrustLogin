"""
CAS (Central Authentication Service) login flow for SDU aTrust VPN.
Uses HTTP-based CAS authentication to obtain a ticket,
then Selenium to complete the browser-side login.
"""

import time

from loguru import logger

from core import ATrustLogin, prompt_params
from sdu_cas import SDUCAS, DeviceFingerprint, CasException

portal_addr = "https://vpn.sdu.edu.cn"
cas_service = "https://vpn.sdu.edu.cn:443/passport/v1/auth/cas"


def run(username=None, password=None, keepalive=200, data_dir="./data",
        driver_type=None, driver_path=None, browser_path=None,
        interactive=True, fingerprint=None):

    args = prompt_params({
        "username": username, "password": password,
        "interactive": interactive,
        "fingerprint": fingerprint,
    }, ["username", "password"], [("fingerprint", "设备指纹(details)", False)])

    username = args["username"]
    password = args["password"]
    fp_details = args.get("fingerprint") or "aTrustLogin-py-v1"

    fps = DeviceFingerprint(details=fp_details)
    cas_client = SDUCAS(fingerprint=fps)

    logger.info("Opening Web Browser")
    at = ATrustLogin(data_dir=data_dir, portal_address=portal_addr,
                     driver_type=driver_type, driver_path=driver_path,
                     browser_path=browser_path, interactive=interactive)

    def _do_cas_login():
        logger.info("通过 CAS 获取 ticket ...")
        ticket_url = cas_client.get_ticket_url(
            service_url=cas_service,
            username=username,
            password=password,
            interactive=interactive,
        )
        logger.info("导航到 ticket URL ...")
        at.navigate_and_wait(ticket_url)
        at.load_storage()
        at.handle_trust_terminal()
        at.handle_sms_auth()
        at.update_storage()
        at.delay_loading()

    _do_cas_login()

    while True:
        try:
            if not at.is_logged():
                logger.info("Session lost, re-authenticating via CAS ...")
                _do_cas_login()

            if not at.is_logged():
                logger.warning("登录状态未确认，稍后重试 ...")
                at.delay_loading()
                continue

            if keepalive <= 0:
                at.close()
                exit(0)
            else:
                time.sleep(keepalive)
                at.navigate_and_wait(portal_addr)
        except CasException as e:
            logger.error(f"CAS 登录错误: {e}")
            break
        except Exception as e:
            logger.error("An error occurred, retrying ...")
            logger.exception(e)
            at.delay_loading()
