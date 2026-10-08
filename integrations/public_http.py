"""Bounded HTTPS requests with DNS addresses checked at connection time.

The resolver returns only vetted public IPs to aiohttp (no second DNS lookup).
Every redirect is validated before contacting its destination. No env proxies.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import unicodedata
from urllib.parse import urljoin, urlsplit

import aiohttp


def public_url(value: str, allowed_hosts: set[str] | None = None) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("INVALID_PUBLIC_URL")
    if (
        any(unicodedata.category(c) in {"Cc", "Cf"} for c in value)
        or "\\" in value
        or "#" in value
        or any(c.isspace() for c in value)
    ):
        raise ValueError("INVALID_PUBLIC_URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.fragment
    ):
        raise ValueError("INVALID_PUBLIC_URL")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("PRIVATE_HOST")
    if allowed_hosts is not None and host not in allowed_hosts:
        raise ValueError("UNTRUSTED_HOST")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not is_public_address(str(address)):
            raise ValueError("PRIVATE_ADDRESS")
    return value


def is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast and not address.is_unspecified


def public_addresses(host: str, port: int = 443) -> list[str]:
    records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not is_public_address(a) for a in addresses):
        raise ValueError("PRIVATE_DNS_ADDRESS")
    return addresses


class PublicResolver(aiohttp.abc.AbstractResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        addresses = await asyncio.wait_for(asyncio.to_thread(public_addresses, host, port), 5)
        return [
            dict(
                hostname=host,
                host=a,
                port=port,
                family=socket.AF_INET6 if ":" in a else socket.AF_INET,
                proto=socket.IPPROTO_TCP,
                flags=socket.AI_NUMERICHOST,
            )
            for a in addresses
        ]

    async def close(self):
        return None


async def fetch_public_response(
    url: str,
    *,
    allowed_hosts=None,
    headers=None,
    max_bytes=2 * 1024 * 1024,
    timeout=25,
    image=False,
    follow=True,
    raise_status=True,
):
    connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False)
    async with (
        asyncio.timeout(timeout),
        aiohttp.ClientSession(
            connector=connector,
            trust_env=False,
            timeout=aiohttp.ClientTimeout(total=timeout, connect=5, sock_connect=5, sock_read=5),
        ) as session,
    ):
        for _ in range(5):
            public_url(url, allowed_hosts)
            async with session.get(url, headers=headers, allow_redirects=False) as response:
                if follow and response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if (
                        not location
                        or any(
                            c.isspace() or unicodedata.category(c) in {"Cc", "Cf"} for c in location
                        )
                        or "\\" in location
                    ):
                        raise ValueError("INVALID_REDIRECT")
                    url = public_url(urljoin(url, location), allowed_hosts)
                    continue
                if raise_status:
                    response.raise_for_status()
                if response.headers.get("HX-Redirect") or response.status in {
                    301,
                    302,
                    303,
                    307,
                    308,
                }:
                    return b"", "", str(response.url), dict(response.headers), response.status
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0]
                if image and content_type not in {
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                    "image/gif",
                    "image/avif",
                }:
                    raise ValueError("INVALID_IMAGE_TYPE")
                if response.content_length is not None and response.content_length > max_bytes:
                    raise ValueError("RESPONSE_TOO_LARGE")
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise ValueError("RESPONSE_TOO_LARGE")
                return (
                    bytes(body),
                    content_type,
                    str(response.url),
                    dict(response.headers),
                    response.status,
                )
    raise ValueError("TOO_MANY_REDIRECTS")


async def fetch_public_bytes(url: str, **kwargs):
    body, content_type, final_url, _, _ = await fetch_public_response(url, **kwargs)
    return body, content_type, final_url
