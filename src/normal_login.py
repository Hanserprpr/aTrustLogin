"""
Normal (non-CAS) aTrust login flow.
Uses Selenium to fill credentials on the aTrust login page directly.
"""

import time

from loguru import logger

from core import ATrustLogin, prompt_if_missing, load_credentials, save_credentials, set_vpn_ready


def run(portal_address=None, username=None, password=None, totp_key=None,
        cookie_tid=None, cookie_sig=None, keepalive=200,
        data_dir="./data", driver_type=None, driver_path=None,
        browser_path=None, interactive=True, wait_atrust=False):

    set_vpn_ready(False)
    saved = load_credentials(data_dir)
    portal_address = portal_address if portal_address is not None else saved.get("portal_address")
    username = username if username is not None else saved.get("username")
    password = password if password is not None else saved.get("password")
    totp_key = totp_key if totp_key is not None else saved.get("totp_key")
    cookie_tid = cookie_tid if cookie_tid is not None else saved.get("cookie_tid")
    cookie_sig = cookie_sig if cookie_sig is not None else saved.get("cookie_sig")

    portal_address = prompt_if_missing(portal_address, "VPN门户地址", interactive=interactive, required=True)
    username = prompt_if_missing(username, "用户名", interactive=interactive, required=True)
    password = prompt_if_missing(password, "密码", interactive=interactive, required=True, secure=True)
    totp_key = prompt_if_missing(totp_key, "TOTP密钥", interactive=interactive, default="", secure=True)
    cookie_tid = prompt_if_missing(cookie_tid, "cookie_tid", interactive=interactive, default="")
    cookie_sig = prompt_if_missing(cookie_sig, "cookie_sig", interactive=interactive, default="")

    save_credentials(data_dir, {
        "portal_address": portal_address or "",
        "username": username or "",
        "password": password or "",
        "totp_key": totp_key or "",
        "cookie_tid": cookie_tid or "",
        "cookie_sig": cookie_sig or "",
    })

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
                set_vpn_ready(False)
                logger.info("Session lost. Trying to login again ...")
                at.open_portal()
                at.delay_loading()
                if at.login(username=username, password=password, totp_key=totp_key) is True:
                    set_vpn_ready(True)
                    at.delay_loading()
                    at.delay_loading()
            else:
                set_vpn_ready(True)

            if keepalive <= 0:
                logger.info("Keepalive disabled, idling ...")
                while True:
                    time.sleep(86400)
            else:
                time.sleep(keepalive)
                at.open_portal()
                at.delay_loading()
        except Exception as e:
            logger.error("An error occurred when trying to login, retrying ...")
            logger.exception(e)
            at.delay_loading()
