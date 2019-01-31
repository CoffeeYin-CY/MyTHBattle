# -*- coding: utf-8 -*-

# -- stdlib --
# -- third party --
# -- own --
from game.base import GameViralContext


# -- code --
UI_META = {}


def G():
    return GameViralContext().game


class UIMetaAccessor(object):
    def __init__(self, cls):
        self.cls = cls
        self.mro = cls.mro()

    def __getattr__(self, name):
        for cls in self.mro:
            try:
                val = getattr(UI_META[cls], name)
                return val
            except AttributeError:
                pass

        raise AttributeError('%s.%s' % (self.cls.__name__, name))


def ui_meta_for(for_module):
    def ui_meta(cls):
        name = cls.__name__
        if name in UI_META:
            raise Exception('%s ui_meta redefinition!' % name)
        for_cls = getattr(for_module, name)
        for_cls.ui_meta = UIMetaAccessor(for_cls)
        UI_META[for_cls] = cls()
        return cls
    return ui_meta


# -----BEGIN COMMON FUNCTIONS-----
def my_turn():
    g = G()

    try:
        act = g.action_stack[-1]
    except IndexError:
        return False

    from thb import actions
    if not isinstance(act, actions.ActionStage):
        return False

    if act.target is not g.me: return False

    if not act.in_user_input: return False

    return True


def limit1_skill_used(tag):
    t = G().me.tags
    return t[tag] >= t['turn_count']


def passive_clickable(self, g):
    return False


def passive_is_action_valid(self, g, cl, target_list):
    return (False, 'BUG!')


def card_desc(c):
    if isinstance(c, (list, tuple)):
        return '、'.join([card_desc(i) for i in c])

    from thb.cards import Card, HiddenCard
    if c.is_card(HiddenCard): return '一张牌'

    if c.suit == Card.SPADE:
        suit = '|r♠'
    elif c.suit == Card.HEART:
        suit = '|r|cb03a11ff♥'
    elif c.suit == Card.CLUB:
        suit = '|r♣'
    elif c.suit == Card.DIAMOND:
        suit = '|r|cb03a11ff♦'
    elif c.suit == Card.NOTSET:
        suit = '|r '
    else:
        suit = '|r错误'

    num = ' A23456789_JQK'[c.number]
    if num == '_': num = '10'
    return suit + num + ' |G%s|r' % c.ui_meta.name


def build_handcard(cardcls, p=None):
    from thb.cards import CardList
    cl = CardList(p or G().me, 'cards')
    c = cardcls()
    c.move_to(cl)
    return c


def char_desc(ch):
    m = ch.ui_meta

    if isinstance(ch, type):
        cls, obj = ch, None
    else:
        cls, obj = ch.__class__, ch

    rst = []
    rst.append('|DB%s %s 体力：%s|r' % (m.title, m.name, cls.maxlife))
    skills = list(cls.skills)
    if hasattr(cls, 'boss_skills'):
        skills.extend(cls.boss_skills)

    if obj:
        skills.extend([
            c for c in obj.skills
            if 'character' in c.skill_category and c not in skills
        ])

    for s in skills:
        sm = s.ui_meta
        rst.append('|G%s|r：%s' % (sm.name, sm.description))

    notes = getattr(m, 'notes', '')
    if notes:
        rst.append(notes)

    tail = [
        ('画师',     getattr(m, 'illustrator', '')),
        ('CV',       getattr(m, 'cv', '')),
        ('人物设计', getattr(m, 'designer', '')),
    ]

    tail = ['%s：%s' % i for i in tail if i[1]]
    if tail:
        rst.append('|DB（%s）|r' % '，'.join(tail))

    return '\n\n'.join(rst)
