"""
aTrustLogin - automated Sangfor aTrust VPN login tool.

Entry point. Use --cas for SDU CAS unified auth mode,
or the default mode for direct aTrust portal login.
"""

import os.path

def main(portal_address=None, username=None, password=None, totp_key=None,
         cookie_tid=None, cookie_sig=None, keepalive=200, data_dir="./data",
         driver_type=None, driver_path=None, browser_path=None,
         interactive=True, wait_atrust=False,
         cas=False, fingerprint=None):
    
    try:
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        if cas:
            from cas_login import run as cas_run
            from loguru import logger

            if not interactive :
                logger.warn("SDU CAS 登入暂不支持非交互式模式！")

            cas_run(
                username=username, password=password,
                keepalive=keepalive, data_dir=data_dir,
                driver_type=driver_type, driver_path=driver_path,
                browser_path=browser_path, interactive=True,
                fingerprint=fingerprint,
            )
        else:
            from normal_login import run as normal_run

            normal_run(
                portal_address=portal_address, username=username, password=password,
                totp_key=totp_key, cookie_tid=cookie_tid, cookie_sig=cookie_sig,
                keepalive=keepalive, data_dir=data_dir,
                driver_type=driver_type, driver_path=driver_path,
                browser_path=browser_path, interactive=interactive,
                wait_atrust=wait_atrust,
            )
    except KeyboardInterrupt:
        logger.info("Shutting down ...")
        exit(0)

if __name__ == "__main__":
    from fire import Fire
    Fire(main)
