"""
SDU CAS (Central Authentication Service) client.
Handles the HTTP-based CAS login flow to obtain a ticket URL for the VPN portal.

Flow:
    1. Try cached CASTGC → if 302, return ticket directly
    2. GET  /cas/login?service=...   → extract lt token
    3. POST /cas/device  (m=1)        → device status check
    4. POST /cas/device  (m=2)/(m=3)  → SMS binding (interactive)
    5. POST /cas/login                 → submit encrypted credentials, get ticket + CASTGC
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from loguru import logger

from des_util import str_enc


@dataclass
class DeviceFingerprint:
    details: str = "aTrustLogin-py-v1"
    browsers: str = "aTrustLogin-py-browser"

    def __init__(self, fingerprint):
        self.details = fingerprint + "-py-v1"
        self.browsers = fingerprint + "-py-browser"

    @property
    def details_md5(self) -> str:
        return str_enc(hashlib.md5(self.details.encode()).hexdigest())

    @property
    def browsers_md5(self) -> str:
        return str_enc(hashlib.md5(self.browsers.encode()).hexdigest())


class CasException(Exception):
    pass


class SDUCAS:
    CAS_BASE = "https://pass-sdu-edu-cn-s.atrust.sdu.edu.cn:81/cas"

    _EXECUTION = "e1s1"
    _EVENT_ID = "submit"

    def __init__(self, fingerprint: Optional[DeviceFingerprint] = None):
        self.fingerprint = fingerprint or DeviceFingerprint()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self._castgc_cache: dict[str, str] = {}

    def get_ticket_url(self, service_url: str, username: str, password: str, interactive: bool = True) -> str:
        cas_login_url = self.CAS_BASE + "/login?" + urlencode({"service": service_url})
        device_url = self.CAS_BASE + "/device"

        castgc = self._castgc_cache.get(username, "")
        if castgc:
            ticket = self._try_castgc_login(cas_login_url, castgc)
            if ticket:
                logger.debug("CASTGC 登入成功")
                return ticket
            else:
                logger.info("CASTGC 已过期，重新认证")
                self._castgc_cache.pop(username, None)

        self.session.cookies.clear()
        self._step1_get_login_page(cas_login_url)
        self._step2_device_verify(device_url, username, password, interactive)
        return self._step3_submit_login(cas_login_url, username, password)

    def _try_castgc_login(self, cas_login_url: str, castgc: str) -> Optional[str]:
        logger.info("使用 CASTGC 登录 ...")
        try:
            resp = self.session.post(
                cas_login_url,
                cookies={"CASTGC": castgc},
                allow_redirects=False,
                timeout=15,
            )
        except requests.RequestException as e:
            logger.warning(f"CASTGC 请求失败: {e}")
            return None

        if resp.status_code == 302:
            location = resp.headers.get("Location", "")
            if location:
                return location
        return None

    def _step1_get_login_page(self, url: str) -> None:
        logger.info("访问 CAS 登录页面 ...")
        resp = self.session.get(url, allow_redirects=False)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        lt_input = soup.select_one("input[name=lt]")
        if lt_input is None:
            raise CasException("登录页面未找到 lt 令牌")
        self._lt = lt_input.get("value", "")
        logger.debug(f"提取到 lt={self._lt[:20]}...")

    def _step2_device_verify(self, device_url: str, username: str, password: str, interactive: bool) -> None:
        logger.info("执行设备验证 ...")

        resp = self.session.post(device_url, data={
            "m": "1",
            "d_md5": self.fingerprint.details_md5,
            "d_browser_md5": self.fingerprint.browsers_md5,
            "u": str_enc(username),
            "p": str_enc(password),
        })
        resp.raise_for_status()

        result = resp.json()
        info = result.get("info", "")
        logger.debug(f"设备状态: {info}")

        if info in ("binded", "pass"):
            return

        if info in ("validErr", "notFound"):
            raise CasException("用户名或密码错误")
        if info == "mobileErr":
            raise CasException("尚未绑定手机号")

        if info == "bind":
            if not interactive:
                raise CasException("需要设备二次验证，但交互模式已禁用")
            self._handle_device_binding(device_url, username)
        else:
            raise CasException(f"未知设备验证结果: {info}")

    def _handle_device_binding(self, device_url: str, username: str) -> None:
        answer = input("需要设备二次验证，是否继续？(y/n, default y): ").strip().lower()
        if answer == "n":
            raise CasException("用户取消设备二次验证")

        last_send_time: float = 0

        while True:
            now = time.time()
            if now - last_send_time > 300:
                logger.info("向绑定的手机号发送验证码 ...")
                resp = self.session.post(device_url, data={"m": "2"})
                resp.raise_for_status()
                info = resp.json().get("info", "")
                if info == "send":
                    logger.info("验证码已发送至所绑定手机")
                elif info == "max":
                    logger.warning("发送过于频繁，请稍后再试")
                else:
                    raise CasException(f"验证码发送失败: {info}")
                last_send_time = now
            else:
                remaining = 300 - int(now - last_send_time)
                logger.info(f"距下次可发送还有 {remaining} 秒")

            code = input("请输入短信验证码 (输入 'r' 重新发送): ").strip()
            if code.lower() == "r":
                continue
            if not code:
                continue

            save_answer = input("是否信任该设备？(y/n): ").strip().lower()
            resp = self.session.post(device_url, data={
                "m": "3",
                "i": self.fingerprint.details,
                "u": username,
                "c": code,
                "s": "1" if save_answer == "y" else "0",
            })
            resp.raise_for_status()
            info = resp.json().get("info", "")

            if info == "ok":
                logger.info("验证码校验通过")
                return
            elif info == "codeErr":
                logger.warning("验证码有误，请重新输入")
            elif info == "timeout":
                logger.warning("验证码超时，请重新发送")
            elif info == "moreErr":
                logger.warning("错误次数过多，请重新获取验证码")
            elif info == "most":
                logger.warning("设备超过最大数量，已自动解除最早一台授信设备")
                return
            else:
                raise CasException(f"验证码校验失败: {info}")

    def _step3_submit_login(self, cas_login_url: str, username: str, password: str) -> str:
        logger.info("提交 CAS 统一认证 ...")

        rsa_value = str_enc(username + password + self._lt)

        resp = self.session.post(cas_login_url, data={
            "rsa": rsa_value,
            "ul": str(len(username)),
            "pl": str(len(password)),
            "lt": self._lt,
            "execution": self._EXECUTION,
            "_eventId": self._EVENT_ID,
        }, allow_redirects=False)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            error_elem = soup.select_one("#errormsg")
            msg = error_elem.text if error_elem else "状态码 200"
            raise CasException(f"CAS 登录失败: {msg}")

        if resp.status_code != 302:
            raise CasException(f"CAS 登录失败: 状态码 {resp.status_code}")

        location = resp.headers.get("Location", "")
        if not location:
            raise CasException("CAS 登录失败: 未获取到重定向地址")

        castgc_value = resp.cookies.get("CASTGC")
        if castgc_value:
            self._castgc_cache[username] = castgc_value
            logger.debug(f"已缓存 CASTGC")

        logger.info("CAS 认证通过")
        return location
