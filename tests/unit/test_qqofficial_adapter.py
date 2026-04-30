"""Tests for QQ Official adapter _send_by_session_common msg_id handling.

Reproduces issue #7904: when no cached msg_id exists, FRIEND_MESSAGE
(私聊) sessions should send messages without requiring a msg_id.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType


def _make_mock_client():
    """Build a mock botClient with api methods needed for sending."""
    client = MagicMock()
    client.api = MagicMock()
    client.api.post_message = AsyncMock()
    client.api.post_group_message = AsyncMock()
    client.api.post_c2c_message = AsyncMock()
    client.set_platform = MagicMock()
    return client


def _make_friend_session(session_id="C894BAED205A6907A4F69265F5E2B4F6"):
    return MessageSession("qq_official", MessageType.FRIEND_MESSAGE, session_id)


def _make_group_session(session_id="G123456789"):
    return MessageSession("qq_official", MessageType.GROUP_MESSAGE, session_id)


def _make_plain_message(text="hello"):
    return MessageChain(chain=[Plain(text=text)])


@pytest.mark.asyncio
async def test_friend_message_sends_without_cached_msg_id():
    """issue #7904: 私聊主动推送不需要 msg_id，无缓存时也应正常发送。"""
    from astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter import (
        QQOfficialPlatformAdapter,
        QQOfficialMessageEvent,
    )

    mock_client = _make_mock_client()
    mock_post_c2c = AsyncMock()

    with (
        patch(
            "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter.botClient",
            return_value=mock_client,
        ),
        patch.object(
            QQOfficialPlatformAdapter,
            "_extract_message_id",
            return_value=None,
        ),
        patch(
            "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter.QQOfficialMessageEvent._parse_to_qqofficial",
            new_callable=AsyncMock,
            return_value=("hello", None, None, None, None, None, None),
        ),
        patch.object(
            QQOfficialMessageEvent, "post_c2c_message", mock_post_c2c
        ),
    ):
        adapter = QQOfficialPlatformAdapter(
            platform_config={
                "appid": "test_appid",
                "secret": "test_secret",
                "enable_group_c2c": True,
                "enable_guild_direct_message": False,
            },
            platform_settings={},
            event_queue=asyncio_get_queue(),
        )

        adapter._session_last_message_id = {}
        session = _make_friend_session()
        await adapter._send_by_session_common(session, _make_plain_message())

    # Fix verified: post_c2c_message 被正常调用，不再被提前 return 拦截
    assert mock_post_c2c.called, (
        "修复后：私聊场景下无缓存 msg_id 时消息应正常发送"
    )


@pytest.mark.asyncio
async def test_group_message_still_requires_cached_msg_id():
    """GROUP_MESSAGE 在无缓存 msg_id 时应跳过发送（确保不引入回归）。"""
    from astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter import (
        QQOfficialPlatformAdapter,
    )

    mock_client = _make_mock_client()

    with (
        patch(
            "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter.botClient",
            return_value=mock_client,
        ),
        patch.object(
            QQOfficialPlatformAdapter,
            "_extract_message_id",
            return_value=None,
        ),
        patch(
            "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter.QQOfficialMessageEvent._parse_to_qqofficial",
            new_callable=AsyncMock,
            return_value=("hello", None, None, None, None, None, None),
        ),
    ):
        adapter = QQOfficialPlatformAdapter(
            platform_config={
                "appid": "test_appid",
                "secret": "test_secret",
                "enable_group_c2c": True,
                "enable_guild_direct_message": False,
            },
            platform_settings={},
            event_queue=asyncio_get_queue(),
        )

        adapter._session_last_message_id = {}
        adapter._session_scene = {"G123456789": "group"}
        session = _make_group_session()
        await adapter._send_by_session_common(session, _make_plain_message())

    assert not mock_client.api.post_group_message.called, (
        "GROUP_MESSAGE 应在无缓存 msg_id 时跳过发送"
    )


@pytest.mark.asyncio
async def test_group_message_sends_with_cached_msg_id():
    """GROUP_MESSAGE 在有缓存 msg_id 时应正常发送。"""
    from astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter import (
        QQOfficialPlatformAdapter,
    )

    mock_client = _make_mock_client()

    with (
        patch(
            "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter.botClient",
            return_value=mock_client,
        ),
        patch.object(
            QQOfficialPlatformAdapter,
            "_extract_message_id",
            return_value=None,
        ),
        patch(
            "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter.QQOfficialMessageEvent._parse_to_qqofficial",
            new_callable=AsyncMock,
            return_value=("hello", None, None, None, None, None, None),
        ),
    ):
        adapter = QQOfficialPlatformAdapter(
            platform_config={
                "appid": "test_appid",
                "secret": "test_secret",
                "enable_group_c2c": True,
                "enable_guild_direct_message": False,
            },
            platform_settings={},
            event_queue=asyncio_get_queue(),
        )

        session = _make_group_session()
        adapter._session_last_message_id = {session.session_id: "fake-msg-id-123"}
        adapter._session_scene = {session.session_id: "group"}
        await adapter._send_by_session_common(session, _make_plain_message())

    assert mock_client.api.post_group_message.called, (
        "GROUP_MESSAGE 应在有缓存 msg_id 时正常发送"
    )


def asyncio_get_queue():
    import asyncio
    return asyncio.Queue()
