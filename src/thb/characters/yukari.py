# -*- coding: utf-8 -*-

# -- stdlib --
# -- third party --
# -- own --
from game.autoenv import EventHandler, user_input
from thb.actions import GenericAction, PlayerTurn, UserAction, migrate_cards
from thb.actions import random_choose_card
from thb.cards import CardList, Skill, t_One
from thb.characters.baseclasses import Character, register_character_to
from thb.inputlets import ChoosePeerCardInputlet


# -- code --
class SpiritingAwayAction(UserAction):
    def apply_action(self):
        tgt = self.target
        src = self.source

        catnames = ('cards', 'showncards', 'equips', 'fatetell')
        cats = [getattr(tgt, i) for i in catnames]
        card = user_input([src], ChoosePeerCardInputlet(self, tgt, catnames))
        card = card or random_choose_card(cats)
        if not card:
            return False

        self.card = card
        src.reveal(card)

        src.tags['spirit_away_tag'] += 1

        cl = getattr(tgt, 'yukari_dimension', None)
        if cl is None:
            cl = CardList(tgt, 'yukari_dimension')
            tgt.yukari_dimension = cl
            tgt.showncardlists.append(cl)

        migrate_cards([card], cl)

        return True

    def is_valid(self):
        tgt = self.target
        catnames = ['cards', 'showncards', 'equips', 'fatetell']
        if not any(getattr(tgt, i) for i in catnames):
            return False

        return self.source.tags['spirit_away_tag'] < 2


class SpiritingAwayReturningAction(GenericAction):
    def apply_action(self):
        g = self.game
        for p in g.players:
            cl = getattr(p, 'yukari_dimension', None)
            cl and migrate_cards(cl, p.cards, unwrap=True)

        return True


class SpiritingAway(Skill):
    associated_action = SpiritingAwayAction
    skill_category = ['character', 'active']
    target = t_One

    def check(self):
        return not self.associated_cards


class SpiritingAwayHandler(EventHandler):
    interested = ['action_after', 'action_apply']

    def handle(self, evt_type, arg):
        if evt_type == 'action_apply' and isinstance(arg, PlayerTurn):
            tgt = arg.target
            if tgt.has_skill(SpiritingAway):
                tgt.tags['spirit_away_tag'] = 0

        elif evt_type == 'action_after' and isinstance(arg, PlayerTurn):
            tgt = arg.target
            if not tgt.has_skill(SpiritingAway):
                return arg

            g = self.game
            g.process_action(SpiritingAwayReturningAction(tgt, tgt))

        return arg


@register_character_to('common')
class Yukari(Character):
    skills = [SpiritingAway]
    eventhandlers_required = [SpiritingAwayHandler]
    maxlife = 4
