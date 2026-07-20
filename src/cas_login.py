"""
CAS (Central Authentication Service) login flow for SDU aTrust VPN.
Uses HTTP-based CAS authentication to obtain a ticket,
then Selenium to complete the browser-side login.

After login, browser is closed and session is kept alive via lightweight HTTP checks.
"""

import os
import pickle
import socket
import time

import requests
from loguru import logger

from core import ATrustLogin, prompt_if_missing, load_credentials, save_credentials, set_vpn_ready
from sdu_cas import SDUCAS, DeviceFingerprint, CasException

portal_addr = "https://vpn.sdu.edu.cn"
cas_service = "https://vpn.sdu.edu.cn:443/passport/v1/auth/cas"
online_url = "https://vpn.sdu.edu.cn/passport/v1/user/onlineInfo?clientType=SDPBrowserClient"


def _ssh_proxy_is_alive() -> bool:
    """Use the SSH dynamic forward as the effective VPN data-plane health check."""
    if not os.environ.get("SSH_PROXY_HOST"):
        return False

    try:
        port = int(os.environ.get("SSH_PROXY_LOCAL_PORT", "1081"))
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except (OSError, ValueError):
        return False


def _check_session(data_dir: str) -> bool:
    """HTTP GET to onlineInfo API — lightweight session check without browser."""
    path = os.path.join(data_dir, "ATrustLoginStorage.pkl")
    if not os.path.exists(path):
        return False

    try:
        with open(path, "rb") as f:
            storage = pickle.load(f)
        cookie_str = "; ".join(
            f"{c['name']}={c['value']}" for c in storage.cookies
            if any(domain in (c.get("domain") or "") for domain in [".sdu.edu.cn", "vpn.sdu.edu.cn"])
        )
        if not cookie_str:
            return False

        resp = requests.get(online_url, headers={"Cookie": cookie_str}, timeout=15)
        return resp.json().get("code") == 0
    except Exception:
        return False


def _login_browser(data_dir: str, portal_addr: str,
                   driver_type: str, driver_path: str, browser_path: str,
                   interactive: bool,
                   cas_client: SDUCAS, username: str, password: str) -> bool:
    """
    1. Open browser
    2. Try stored cookies → if valid, save & return
    3. CAS login flow → if success, update storage & return
    4. Close browser in all cases
    """
    at = None
    try:
        at = ATrustLogin(data_dir=data_dir, portal_address=portal_addr,
                         driver_type=driver_type, driver_path=driver_path,
                         browser_path=browser_path, interactive=interactive)

        logger.info("Authenticating via CAS ...")
        ticket_url = cas_client.get_ticket_url(cas_service, username, password, interactive)
        
        logger.debug("Navigating to ticket URL ...")
        at.navigate_and_wait(ticket_url)
        
        logged = False
        for _ in range(5):
            logger.debug("Detecting logged ...")
            logged = at.is_logged()
            if logged:
                break
            
            logger.debug("Detecting sms needed ...")
            if at.need_sms_bind():
                at.handle_trust_terminal()
                for _ in range(5):
                    at.delay_loading()
                    logger.debug("Detecting logged ...")
                    logged = at.is_logged()
                    if logged:
                        break
                break

            at.delay_loading()

        if logged:
            at.update_storage()
            logger.debug("Login success, cookies saved")
        else:
            logger.debug(f"Login completed but session not confirmed")
        return logged

    except (CasException, Exception) as e:
        logger.error(f"Browser login failed: {e}")
        return False
    finally:
        if at:
            try:
                url_snippet = str(at.driver.current_url)[:80] if at.driver.current_url else "about:blank"
                logger.debug(f"Browser remain at {url_snippet}")
                at.close()
            except Exception:
                pass


def run(username=None, password=None, keepalive=200, data_dir="./data",
        driver_type=None, driver_path=None, browser_path=None,
        interactive=True, fingerprint=None):

    set_vpn_ready(False)
    saved = load_credentials(data_dir)
    username = username if username is not None else saved.get("username")
    password = password if password is not None else saved.get("password")
    fingerprint = fingerprint if fingerprint is not None else saved.get("fingerprint")

    username = prompt_if_missing(username, "统一认证学号", interactive=interactive, required=True)
    password = prompt_if_missing(password, "统一认证密码", interactive=interactive, required=True, secure=True)
    fingerprint = prompt_if_missing(fingerprint, "设备指纹", interactive=interactive, default="aTrustLogin")

    # Python Fire converts numeric command-line values (such as student IDs)
    # to integers.  CAS encryption and length fields operate on the original
    # textual credentials, so normalize them before saving or encrypting them.
    username = str(username)
    password = str(password)
    fingerprint = str(fingerprint)

    save_credentials(data_dir, {
        "username": username,
        "password": password,
        "fingerprint": fingerprint,
    })

    fps = DeviceFingerprint(fingerprint)
    cas_client = SDUCAS(fingerprint=fps)

    if not _login_browser(data_dir, portal_addr,
                          driver_type, driver_path, browser_path,
                          interactive, cas_client, username, password):
        logger.error("Initial login failed, exiting")
        exit(1)

    logger.info("Login success!")
    set_vpn_ready(True)

    tolerance = 3
    while True:
        try:
            if keepalive <= 0:
                logger.info("Keepalive disabled, idling ...")
                while True:
                    time.sleep(86400)

            time.sleep(keepalive)

            if not _check_session(data_dir):
                if _ssh_proxy_is_alive():
                    logger.warning(
                        "Web session check failed, but the SSH SOCKS5 tunnel is active; "
                        "keeping the current VPN session"
                    )
                    continue

                logger.info("Session expired, re-authenticating via browser ...")
                for i in range(3):
                    ok = _login_browser(data_dir, portal_addr,
                                        driver_type, driver_path, browser_path,
                                        interactive, cas_client, username, password)
                    if ok:
                        logger.info("Session re-authenticated successfully")
                        tolerance = 3
                        set_vpn_ready(True)
                        break
                    else:
                        if i == 2:
                            logger.error(
                                "Re-authentication failed after 3 attempts; "
                                "keeping the SSH proxy and retrying on the next keepalive cycle"
                            )
                            break
                        logger.warning(f"Re-authentication failed, {2 - i} retries left")
            else:
                logger.debug("Session is active.")

        except Exception as e:
            logger.error(f"Keepalive error: {e}")
            tolerance -= 1
            if tolerance <= 0:
                logger.error("Too many errors, exiting")
                exit(1)
            time.sleep(30)
