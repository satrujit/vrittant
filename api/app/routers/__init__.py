"""All routers, exposed as a single mount-table for main.py."""
from . import (
    admin, auth, editions, files, internal,
    news_articles, sarvam, speaker, stories, templates,
    webhooks_whatsapp, widgets,
)

ROUTERS = [
    (admin.router,            None,        None),
    (admin.config_router,     None,        None),
    (editions.router,         None,        None),
    (auth.router,             "/auth",     ["auth"]),
    (stories.router,          "/stories",  ["stories"]),
    (files.router,            "/files",    ["files"]),
    (sarvam.router,           None,        ["sarvam"]),
    (templates.router,        None,        None),
    (news_articles.router,    None,        None),
    (speaker.router,          None,        ["speaker"]),
    (widgets.router,          None,        None),
    (webhooks_whatsapp.router, None,       None),
    (internal.router,         None,        None),
]
