"""
Normal (non-CAS) aTrust login flow.
Uses Selenium to fill credentials on the aTrust login page directly.
"""

import time

from loguru import logger

from core import ATrustLogin, prompt_params


def run(portal_address=None, username=None, password=None, totp_key=None,
        cookie_tid=None, cookie_sig=None, keepalive=200,
        data_dir="./data", driver_type=None, driver_path=None,
        browser_path=None, interactive=True, wait_atrust=False):

    args = prompt_params({
        "portal_address": portal_address, "username": username, "password": password,
        "totp_key": totp_key, "cookie_tid": cookie_tid, "cookie_sig": cookie_sig,
        "interactive": interactive,
    }, ["portal_address", "username", "password"],
      [("totp_key", "TOTP密钥", True),
       ("cookie_tid", "cookie_tid", False),
       ("cookie_sig", "cookie_sig", False)])

    portal_address = args["portal_address"]
    username = args["username"]
    password = args["password"]
    totp_key = args["totp_key"]
    cookie_tid = args.get("cookie_tid")
    cookie_sig = args.get("cookie_sig")

    logger.info("Opening Web Browser")

    if wait_atrust:
        ATrustLogin.wait_for_port(54631)

    at = ATrustLogin(data_dir=data_dir, portal_address=portal_address,
                     cookie_tid=cookie_tid, cookie_sig=cookie_sig,
                     driver_type=driver_type, driver_path=driver_path,
                     browser_path=browser_path, interactive=interactive)

    at.init()

    while True:
        try:
            if not at.is_logged():
                logger.info("Session lost. Trying to login again ...")
                at.open_portal()
                at.delay_loading()
                if at.login(username=username, password=password, totp_key=totp_key) is True:
                    at.delay_loading()
                    at.delay_loading()

            if keepalive <= 0:
                at.close()
                exit(0)
            else:
                time.sleep(keepalive)
                at.open_portal()
                at.delay_loading()
        except Exception as e:
            logger.error("An error occurred when trying to login, retrying ...")
            logger.exception(e)
            at.delay_loading()
