# -*- coding: utf-8 -*-


# -- stdlib --
# -- third party --
# -- own --
from game.autoenv import user_input
from thb.actions import LaunchCard, UserAction, migrate_cards, random_choose_card
from thb.cards import AttackCard, Skill, TreatAs, VirtualCard, t_OtherOne
from thb.characters.base import Character, register_character_to
from thb.inputlets import ChooseOptionInputlet, ChoosePeerCardInputlet


# -- code --
class Daze(TreatAs, VirtualCard):
    treat_as = AttackCard


class BorrowAction(UserAction):
    def apply_action(self):
        src = self.source
        tgt = self.target
        g = self.game

        c = user_input([src], ChoosePeerCardInputlet(self, tgt, ('cards', 'showncards', 'equips')))
        c = c or random_choose_card([tgt.cards, tgt.showncards])
        if not c: return False
        src.reveal(c)
        migrate_cards([c], src.cards)
        src.tags['borrow_tag'] = src.tags['turn_count']

        if user_input([tgt], ChooseOptionInputlet(self, (False, True))):
            g.process_action(LaunchCard(tgt, [src], Daze(tgt), bypass_check=True))

        return True

    def is_valid(self):
        src = self.source
        tgt = self.target
        if src.tags['turn_count'] <= src.tags['borrow_tag']:
            return False

        if not (tgt.cards or tgt.showncards or tgt.equips):
            return False

        return True


class Borrow(Skill):
    associated_action = BorrowAction
    skill_category = ['character', 'active']
    target = t_OtherOne

    def check(self):
        if self.associated_cards: return False
        return True


@register_character_to('common')
class Marisa(Character):
    skills = [Borrow]
    maxlife = 4
