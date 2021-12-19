#!/usr/bin/env python
import asyncio
from aiohttp import ClientSession
import logging
from os import environ
from pyhilo import API, Hilo
from pyhilo.const import LOG  # noqa

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)s:%(filename)s:%(lineno)d %(threadName)s %(levelname)s %(message)s",
)


async def async_main() -> None:
    # export hilo_username="moi@gmail.com"
    # export hilo_password="1234"
    username = environ.get("hilo_username", "")
    password = environ.get("hilo_password", "")
    api = await API.async_auth(username, password, session=ClientSession())
    h = Hilo(api)
    await h.async_init()


loop = asyncio.get_event_loop()
loop.create_task(async_main())
loop.run_forever()
