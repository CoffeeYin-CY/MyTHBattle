# -*- coding: utf-8 -*-
from __future__ import absolute_import

# -- stdlib --
# -- third party --
# -- own --
from game.base import GameItem
from thb.characters.baseclasses import Character
from utils import exceptions


# -- code --
@GameItem.register
class ImperialChoice(GameItem):
    key = 'imperial-choice'
    args = [str]

    def init(self, char):
        if char == 'Akari' or char not in Character.character_classes:
            raise exceptions.CharacterNotFound

        self.char_cls = Character.character_classes[char]

    @property
    def title(self):
        return u'选将卡（%s）' % self.char_cls.ui_meta.name

    @property
    def description(self):
        return u'你可以选择%s出场。2v2模式不可用。' % self.char_cls.ui_meta.name

    def should_usable(self, g, u, items):
        from thb.thb2v2 import THBattle2v2
        if isinstance(g, THBattle2v2):
            raise exceptions.IncorrectGameMode

        for l in items.values():
            if self.sku in l:
                raise exceptions.ChooseCharacterConflict

    @classmethod
    def get_chosen(cls, items, pl):
        chosen = []
        for p in pl:
            uid = p.account.userid
            if uid not in items:
                continue

            for i in items[uid]:
                i = GameItem.from_sku(i)
                if not isinstance(i, cls):
                    continue

                chosen.append((p, i.char_cls))
                break

        return chosen


@GameItem.register
class ImperialIdentity(GameItem):
    key = 'imperial-id'
    args = [str]

    def init(self, id):
        if id not in ('attacker', 'accomplice', 'curtain', 'boss'):
            raise exceptions.InvalidIdentity

        self.id = id
        mapping = {
            'attacker':   u'城管',
            'boss':       u'BOSS',
            'accomplice': u'道中',
            'curtain':    u'黑幕',
        }
        self.disp_name = mapping[id]

    @property
    def title(self):
        return u'身份卡（%s）' % self.disp_name

    @property
    def description(self):
        return u'你可以选择%s身份。身份场可用。' % self.disp_name

    def should_usable(self, g, u, items):
        from thb.thbidentity import THBattleIdentity
        if not isinstance(g, THBattleIdentity):
            raise exceptions.IncorrectGameMode

        threshold = {
            'attacker': 4,
            'boss': 1,
            'accomplice': 2,
            'curtain': 1,
        }
        core = g.core
        params = core.game.params_of(g)
        if params['double_curtain']:
            threshold['curtain'] += 1
            threshold['attacker'] -= 1

        threshold[self.id] -= 1

        items = core.item.items_of(g)
        uid = core.auth.uid_of(u)
        for _uid, l in items:
            for i in l:
                i = GameItem.from_sku(i)
                if not isinstance(i, self.__class__):
                    continue

                if _uid == uid:
                    raise exceptions.IdentityAlreadyChosen

                assert i.id in threshold

                threshold[i.id] -= 1

        if any(i < 0 for i in threshold.values()):
            raise exceptions.ChooseIdentityConflict

    @classmethod
    def get_chosen(cls, items, pl):
        from thb.thbidentity import Identity

        mapping = {
            'boss':       Identity.TYPE.BOSS,
            'attacker':   Identity.TYPE.ATTACKER,
            'accomplice': Identity.TYPE.ACCOMPLICE,
            'curtain':    Identity.TYPE.CURTAIN,
        }

        rst = []
        for p in pl:
            uid = p.account.userid
            if uid not in items:
                continue

            for i in items[uid]:
                i = GameItem.from_sku(i)
                if not isinstance(i, cls):
                    continue

                rst.append((p, mapping[i.id]))

        return rst


@GameItem.register
class European(GameItem):
    key = 'european'
    args = []

    title = u'欧洲卡'
    description = u'Roll点保证第一。身份场不可用。'

    def should_usable(self, g, u, items):
        from thb.thbidentity import THBattleIdentity
        if isinstance(mgr.game, THBattleIdentity):
            raise exceptions.IncorrectGameMode

        for l in mgr.game_items.values():
            if self.key in l:
                raise exceptions.EuropeanConflict

    @classmethod
    def is_european(cls, g, items, p):
        uid = p.account.userid
        return uid in items and cls.key in items[uid]
