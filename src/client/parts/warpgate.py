# -*- coding: utf-8 -*-
# flake8: noqa

# For Unity


# -- stdlib --
import random
import sys

# -- third party --
from gevent.event import Event
import gevent
import gevent.hub

# -- own --
from .game.autoenv import EventHandler
from utils.misc import instantiate
import settings


# -- code --
'''
Emits:
    ['game_event', g -> Game, evt_name -> str, arg -> object]  // Game.emit_event
    ['system_event', evt_name -> str, args -> tuple]  // See Executive
'''


class UnityUIEventHook(EventHandler):
    def __init__(self, g, warpgate):
        EventHandler.__init__(self)
        self.warpgate = warpgate
        self.game = g
        self.live = False

    def evt_user_input(self, g, evt_name, arg):
        trans, ilet = arg
        evt = Event()
        self.warpgate.events.append(('game_event', self.game, evt_name, (trans, ilet, evt.set)))
        evt.wait()
        return ilet

    def handle(self, evt, data):
        if not self.live and evt not in ('game_begin', 'switch_character', 'reseat'):
            return data

        handler = getattr(self, 'evt_' + evt, None)
        if handler:
            handler(self.game, evt, data)
        else:
            self.warpgate.events.append(('game_event', self.game, evt, data))

        if random.random() < 0.01:
            gevent.sleep(0.005)

        return data

    def set_live(self):
        self.live = True
        self.warpgate.events.append(('game_event', self.game, 'game_live', None))


# from gevent.resolver_ares import Resolver
# hub = gevent.hub.get_hub()
# hub.resolver = Resolver(hub=hub)

import logging
import utils.log

sys.argv = []

utils.log.init_unity(logging.ERROR, settings.SENTRY_DSN, settings.VERSION)
utils.log.patch_gevent_hub_print_exception()


class ExecutiveWrapper(object):
    def __init__(self, executive, warpgate):
        object.__setattr__(self, "executive", executive)
        object.__setattr__(self, "warpgate", warpgate)

    def __getattr__(self, k):
        return getattr(self.executive, k)

    def __setattr__(self, k, v):
        setattr(self.executive, k, v)

    def connect_server(self, host, port):
        from UnityEngine import Debug
        Debug.Log(repr((host, port)))

        @gevent.spawn
        def do():
            Q = self.warpgate.queue_system_event
            Q('connect', self.executive.connect_server((host, port), Q))

    def start_replay(self, rep):
        self.executive.start_replay(rep, self.warpgate.queue_system_event)

    def update(self):
        Q = self.warpgate.queue_system_event

        def update_cb(name, p):
            Q('update', name, p)

        @gevent.spawn
        def do():
            Q('result', self.executive.update(update_cb))

    def get_account_data(self):
        return self.executive.gamemgr.accdata

    def ignite(self, g):
        g.event_observer = UnityUIEventHook(self.warpgate, g)

        @gevent.spawn
        def start():
            gevent.sleep(0.3)
            svr = g.me.server
            if svr.gamedata_piled():
                g.start()
                svr.wait_till_live()
                gevent.sleep(0.1)
                svr.wait_till_live()
                g.event_observer.set_live()
            else:
                g.event_observer.set_live()
                g.start()


@instantiate
class Warpgate(object):

    def init(self):
        import options
        from UnityEngine import Debug

        L = lambda s: Debug.Log("PyWrap: " + s)
        L("init")

        self.events = []

        # should set them
        options.no_update
        options.show_hidden_mode
        options.freeplay = False

        if options.no_update:
            import autoupdate
            autoupdate.Autoupdate = autoupdate.DummyAutoupdate

        L("before gevent")
        from gevent import monkey
        monkey.patch_socket()
        monkey.patch_os()
        monkey.patch_select()
        L("after gevent")

        from .game import autoenv
        autoenv.init('Client')

        import thb.meta  # noqa, init ui_meta

    def get_events(self):
        l = self.events
        self.events = []
        return l

    def start_backdoor(self):
        from gevent.backdoor import BackdoorServer
        import gevent
        self.bds = BackdoorServer(('127.0.0.1', 12345))
        self.gr_bds = gevent.spawn(self.bds.serve_forever)

    def stop_backdoor(self):
        self.gr_bds.kill()
        self.bds.close()

    def shutdown(self):
        from client.core.executive import Executive
        if Executive.state == 'connected':
            Executive.disconnect()

    def queue_system_event(self, evt_name, arg=None):
        self.events.append(('system_event', evt_name, arg))
