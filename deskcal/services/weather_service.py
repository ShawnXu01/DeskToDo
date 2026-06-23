"""和风天气服务：JWT 鉴权（凭证内置，用户只需配置城市定位）+ 实时天气查询。

网络请求由调用方负责放到后台线程执行，本模块本身不做线程切换；
失败时静默返回 None，调用方应保留上一次的展示数据，不弹错误。
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from cryptography.hazmat.primitives.serialization import load_pem_private_key

PROJECT_ID = "2JKQM9X634"
KID = "C6H2HVUXQC"
PRIVATE_KEY_PATH = Path(__file__).resolve().parent.parent.parent / "secrets" / "qweather" / "ed25519-private.pem"

API_URL = "https://devapi.qweather.com/v7/weather/now"
FORECAST_API_URL = "https://devapi.qweather.com/v7/weather/7d"
GEO_API_URL = "https://geoapi.qweather.com/v2/city/lookup"
FORECAST_DAYS = 4  # 今天 + 未来 3 天
REQUEST_TIMEOUT_SECONDS = 10


@dataclass
class WeatherInfo:
    temperature_c: str
    text: str
    update_time: str


@dataclass
class DayForecast:
    fx_date: str  # ISO 格式 YYYY-MM-DD
    icon_code: str
    text_day: str
    temp_max: str
    temp_min: str


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _build_jwt() -> str:
    header = {"alg": "EdDSA", "kid": KID}
    now = int(time.time())
    payload = {"sub": PROJECT_ID, "iat": now - 30, "exp": now + 900}

    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    private_key = load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    signature = private_key.sign(signing_input)
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"


def get_current_weather(location: str) -> Optional[WeatherInfo]:
    """location 为 经度,纬度 或 QWeather LocationID。"""
    try:
        token = _build_jwt()
        response = requests.get(
            API_URL,
            params={"location": location},
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != "200":
            return None
        now = data["now"]
        return WeatherInfo(temperature_c=now["temp"], text=now["text"], update_time=data["updateTime"])
    except Exception:
        return None


def get_forecast(location: str) -> Optional[list[DayForecast]]:
    """location 为 经度,纬度 或 QWeather LocationID。返回今天起 4 天（含今天）的逐日预报。"""
    try:
        token = _build_jwt()
        response = requests.get(
            FORECAST_API_URL,
            params={"location": location},
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != "200":
            return None
        return [
            DayForecast(
                fx_date=day["fxDate"],
                icon_code=day["iconDay"],
                text_day=day["textDay"],
                temp_max=day["tempMax"],
                temp_min=day["tempMin"],
            )
            for day in data["daily"][:FORECAST_DAYS]
        ]
    except Exception:
        return None


def get_city_name(location: str) -> Optional[str]:
    """location 为 经度,纬度 或 QWeather LocationID。返回城市名，查不到时静默返回 None。"""
    try:
        token = _build_jwt()
        response = requests.get(
            GEO_API_URL,
            params={"location": location},
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != "200" or not data.get("location"):
            return None
        return data["location"][0]["name"]
    except Exception:
        return None
