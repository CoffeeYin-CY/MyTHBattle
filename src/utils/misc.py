# -*- coding: utf-8 -*-
from __future__ import absolute_import

# -- stdlib --
from collections import deque
from contextlib import contextmanager
from functools import wraps
from weakref import WeakSet
import functools
import logging
import re

# -- third party --
from gevent.lock import Semaphore
from gevent.queue import Queue
import gevent

# -- own --

# -- code --
log = logging.getLogger('util.misc')
dbgvals = {}


class Packet(list):  # compare by identity list
    __slots__ = ('scan_count')

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return id(self) == id(other)

    def __ne__(self, other):
        return not self.__eq__(other)


class ObjectDict(dict):
    __slots__ = ()

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError

    def __setattr__(self, k, v):
        self[k] = v

    @classmethod
    def parse(cls, data):
        if isinstance(data, dict):
            return cls({k: cls.parse(v) for k, v in data.items()})
        elif isinstance(data, (BatchList, list, tuple, set, frozenset)):
            return type(data)([cls.parse(v) for v in data])

        return data


class BatchList(list):
    __slots__ = ()

    def __getattribute__(self, name):
        try:
            list_attr = list.__getattribute__(self, name)
            return list_attr
        except AttributeError:
            pass

        return list.__getattribute__(self, '__class__')(
            getattr(i, name) for i in self
        )

    def __call__(self, *a, **k):
        return list.__getattribute__(self, '__class__')(
            f(*a, **k) for f in self
        )

    def exclude(self, *elems):
        nl = list.__getattribute__(self, '__class__')(self)
        for e in elems:
            try:
                nl.remove(e)
            except ValueError:
                pass

        return nl

    def rotate_to(self, elem):
        i = self.index(elem)
        n = len(self)
        return self.__class__((self*2)[i:i+n])

    def replace(self, old, new):
        try:
            self[self.index(old)] = new
        except ValueError:
            pass

    def sibling(self, me, offset=1):
        i = self.index(me)
        n = len(self)
        return self[(i + offset) % n]


class CheckFailed(Exception):
    pass


def check(b):
    if not b:
        # import traceback
        # traceback.print_stack()
        raise CheckFailed


_ = Ellipsis


def check_type(pattern, obj):
    if isinstance(pattern, (list, tuple)):
        check(isinstance(obj, (list, tuple)))
        if len(pattern) == 2 and pattern[-1] is _:
            cls = pattern[0]
            for v in obj:
                check(isinstance(v, cls))
        else:
            check(len(pattern) == len(obj))
            for cls, v in zip(pattern, obj):
                check_type(cls, v)
    else:
        check(isinstance(obj, pattern))


class Framebuffer(object):
    current_fbo = None

    def __init__(self, texture=None):
        from pyglet import gl
        fbo_id = gl.GLuint(0)
        gl.glGenFramebuffersEXT(1, gl.byref(fbo_id))
        self.fbo_id = fbo_id
        self._texture = None
        if texture:
            self.bind()
            self.texture = texture
            self.unbind()

    def _get_texture(self):
        return self._texture

    def _set_texture(self, t):
        self._texture = t
        from pyglet import gl
        try:
            gl.glFramebufferTexture2DEXT(
                gl.GL_FRAMEBUFFER_EXT,
                gl.GL_COLOR_ATTACHMENT0_EXT,
                t.target, t.id, 0,
            )
        except gl.GLException:
            # HACK: Some Intel card return errno == 1286L
            # which means GL_INVALID_FRAMEBUFFER_OPERATION_EXT
            # but IT ACTUALLY WORKS FINE!!
            pass

        gl.glViewport(0, 0, t.width, t.height)

        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        gl.gluOrtho2D(0, t.width, 0, t.height)

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()

        # ATI cards hack
        gl.glBegin(gl.GL_LINES)
        gl.glEnd()
        # --------------

    texture = property(_get_texture, _set_texture)

    def __enter__(self):
        self.bind()

    def __exit__(self, exc_type, exc_value, tb):
        self.unbind()

    def bind(self):
        assert Framebuffer.current_fbo is None
        from pyglet import gl
        t = self.texture
        gl.glBindFramebufferEXT(gl.GL_FRAMEBUFFER_EXT, self.fbo_id)
        gl.glPushAttrib(gl.GL_VIEWPORT_BIT | gl.GL_TRANSFORM_BIT)
        if t:
            gl.glViewport(0, 0, t.width, t.height)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        if t:
            gl.glLoadIdentity()
            gl.gluOrtho2D(0, t.width, 0, t.height)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        if t:
            gl.glLoadIdentity()

        Framebuffer.current_fbo = self

    def unbind(self):
        from pyglet import gl
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glPopAttrib()
        gl.glBindFramebufferEXT(gl.GL_FRAMEBUFFER_EXT, 0)
        Framebuffer.current_fbo = None

    def __del__(self):
        from pyglet import gl
        try:
            gl.glDeleteFramebuffersEXT(1, self.fbo_id)
        except Exception:
            pass

    def blit_from_current_readbuffer(self, src_box, dst_box=None, mask=None, _filter=None):
        from pyglet import gl
        mask = mask if mask else gl.GL_COLOR_BUFFER_BIT
        _filter = _filter if _filter else gl.GL_LINEAR

        if not dst_box:
            dst_box = (0, 0, src_box[2] - src_box[0], src_box[3] - src_box[1])

        args = tuple(src_box) + tuple(dst_box) + (mask, _filter)
        gl.glBlitFramebufferEXT(*args)


def remove_dups(s):
    seen = set()
    for i in s:
        if i not in seen:
            yield i
            seen.add(i)


def classmix(*_classes):
    classes = []
    for c in _classes:
        if hasattr(c, '_is_mixedclass'):
            classes.extend(c.__bases__)
        else:
            classes.append(c)

    classes = tuple(remove_dups(classes))
    cached = cls_cache.get(classes, None)
    if cached: return cached

    clsname = ', '.join(cls.__name__ for cls in classes)
    new_cls = type('Mixed(%s)' % clsname, classes, {'_is_mixedclass': True})
    cls_cache[classes] = new_cls
    return new_cls

cls_cache = {}


def hook(module):
    def inner(hooker):
        funcname = hooker.__name__
        hookee = getattr(module, funcname)

        @wraps(hookee)
        def real_hooker(*args, **kwargs):
            return hooker(hookee, *args, **kwargs)
        setattr(module, funcname, real_hooker)
        return real_hooker
    return inner


def gif_to_animation(giffile):
    import pyglet
    from PIL import Image

    im = Image.open(giffile)

    dur = []
    framedata = []

    while True:
        dur.append(im.info['duration'])
        framedata.append(im.convert('RGBA').tostring())
        try:
            im.seek(im.tell()+1)
        except Exception:
            break

    dur[0] = 100

    w, h = im.size

    frames = []
    for d, data in zip(dur, framedata):
        img = pyglet.image.ImageData(w, h, 'RGBA', data, pitch=-w*4)
        img.anchor_x, img.anchor_y = img.width // 2, img.height // 2
        frames.append(
            pyglet.image.AnimationFrame(img, d/1000.0)
        )

    anim = pyglet.image.Animation(frames)
    anim.width, anim.height = w, h

    return anim


def extendclass(clsname, bases, _dict):
    for cls in bases:
        for key, value in _dict.items():
            if key == '__module__':
                continue
            setattr(cls, key, value)


def textsnap(text, font, l):
    tl = 0
    for i, g in enumerate(font.get_glyphs(text)):
        if tl + g.advance > l:
            break
        tl += g.advance
    else:
        return text

    return text[:i]


def partition(pred, lst):
    f, t = [], []
    for i in lst:
        (f, t)[pred(i)].append(i)

    return t, f


def track(f):
    @functools.wraps(f)
    def _wrapper(*a, **k):
        print '%s: %s %s' % (f.__name__, a, k)
        return f(*a, **k)
    return _wrapper


def flatten(l):
    rst = []

    def _flatten(sl):
        for i in sl:
            if isinstance(i, (list, tuple, deque)):
                _flatten(i)
            else:
                rst.append(i)

    _flatten(l)
    return rst


def group_by(l, keyfunc):
    if not l: return []

    grouped = []
    group = []

    lastkey = keyfunc(l[0])
    for i in l:
        k = keyfunc(i)
        if k == lastkey:
            group.append(i)
        else:
            grouped.append(group)
            group = [i]
            lastkey = k

    if group:
        grouped.append(group)

    return grouped


def instantiate(cls):
    return cls()


def surpress_and_restart(f):
    def wrapper(*a, **k):
        while True:
            try:
                return f(*a, **k)
            except Exception as e:
                import logging
                log = logging.getLogger('misc')
                log.exception(e)

    return wrapper


def swallow(f):
    def wrapper(*a, **k):
        try:
            return f(*a, **k)
        except Exception:
            pass

    return wrapper


def log_failure(logger):
    def decorate(f):
        def wrapper(*a, **k):
            try:
                return f(*a, **k)
            except Exception as e:
                logger.exception(e)
                raise

        return wrapper

    return decorate


def openurl(url):
    import sys
    import os

    if sys.platform == 'win32':
        os.startfile(url, 'open')

    elif sys.platform.startswith('linux'):
        os.system("xdg-open '%s'" % url)


class ObservableEvent(object):
    def __init__(self, weakref=False):
        self.listeners = WeakSet() if weakref else set()

    def __iadd__(self, ob):
        self.listeners.add(ob)
        return self

    def __isub__(self, ob):
        self.listeners.discard(ob)
        return self

    def notify(self, *a, **k):
        for ob in list(self.listeners):
            ob(*a, **k)


class GenericPool(object):
    def __init__(self, factory, size, container_class=Queue):
        self.factory = factory
        self.size = size
        self.container = container_class(size)
        self.inited = False

    def __call__(self):
        @contextmanager
        def manager():
            container = self.container

            if not self.inited:
                for i in xrange(self.size):
                    container.put(self.factory())

                self.inited = True

            try:
                item = container.get()
                yield item
            except Exception:
                item = self.factory()
                raise
            finally:
                try:
                    container.put_nowait(item)
                except Exception:
                    pass

        return manager()


def debounce(seconds):
    def decorate(f):
        lock = Semaphore(1)

        def bouncer(fire, *a, **k):
            gevent.sleep(seconds)
            wrapper.last = None
            fire and f(*a, **k)

        @wraps(f)
        def wrapper(*a, **k):
            rst = lock.acquire(blocking=False)
            if not rst:
                return

            try:
                run = False
                if wrapper.last is None:
                    wrapper.last = gevent.spawn(bouncer, False)
                    run = True
                else:
                    wrapper.last.kill()
                    wrapper.last = gevent.spawn(bouncer, True, *a, **k)
            finally:
                lock.release()

            run and f(*a, **k)

        wrapper.last = None
        wrapper.__name__ == f.__name__
        return wrapper

    return decorate


class ThrottleState(object):
    __slots__ = ('running', 'pending', 'args')

    def __init__(self):
        self.running = self.pending = False


def throttle(seconds):
    def decorate(f):
        state = ThrottleState()

        def after():
            gevent.sleep(seconds)
            if state.pending:
                state.pending = False
                a, k = state.args
                gevent.spawn(after)
                f(*a, **k)

            else:
                state.running = False

        @wraps(f)
        def wrapper(*a, **k):
            if state.running:
                state.pending = True
                state.args = (a, k)

            else:
                state.running = True
                gevent.spawn(after)
                f(*a, **k)

        wrapper.__name__ = f.__name__

        return wrapper

    return decorate


class InstanceHookMeta(type):
    # ABCMeta would use __subclasshook__ for instance check. Loses information.

    def __instancecheck__(cls, inst):
        return cls.instancecheck(inst)

    def __subclasscheck__(cls, C):
        return cls.subclasscheck(C)

    def instancecheck(cls, inst):
        return cls.subclasscheck(type(inst))


class ArgValidationError(Exception):
    pass


class ArgTypeError(ArgValidationError):
    __slots__ = ('position', 'expected', 'actual')

    def __init__(self, position, expected, actual):
        self.position = position
        self.expected = expected
        self.actual = actual

    def __unicode__(self):
        return 'Arg %s should be "%s" type, "%s" found' % (
            self.position,
            self.expected.__name__,
            self.actual.__name__,
        )

    def __str__(self):
        return self.__unicode__().encode('utf-8')


class ArgCountError(ArgValidationError):
    __slots__ = ('expected', 'actual')

    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual

    def __unicode__(self):
        return 'Expecting %s args, %s found' % (
            self.expected,
            self.actual,
        )

    def __str__(self):
        return self.__unicode__().encode('utf-8')


def validate_args(*typelist):
    def decorate(f):
        @wraps(f)
        def wrapper(*args):
            e, a = len(typelist), len(args)
            if e != a:
                raise ArgCountError(e, a)

            for i, e, v in zip(xrange(1000), typelist, args):
                if not isinstance(v, e):
                    raise ArgValidationError(i, e, v.__class__)

            return f(*args)

        wrapper.__name__ = f.__name__
        return wrapper

    return decorate


class BusinessException(Exception):
    pass


@instantiate
class exceptions(object):
    def __getattr__(self, k):
        snake_case = '_'.join([
            i.lower() for i in re.findall(r'[A-Z][a-z]+|[A-Z]+(?![a-z])', k)
        ])

        cls = type(k, (BusinessException,), {'snake_case': snake_case})
        setattr(self, k, cls)
        return cls


def first(l, pred=None):
    if pred:
        for i in l:
            if pred(i):
                return i
        else:
            return None
    else:
        return l[0] if len(l) else None


cached_images = {}


def is_url_cached(url):
    return url in cached_images


def imageurl2file(url):
    if url in cached_images:
        data = cached_images[url]
    else:
        import requests  # Mobile version don't have this
        resp = requests.get(url)
        if not resp.ok:
            log.warning('Image fetch not ok: %s -> %s', resp.status_code, url)
            return None, None

        data = resp.content
        cached_images[url] = data

    if data.startswith('GIF'):
        type = 'gif'
    elif data.startswith('\xff\xd8') and data.endswith('\xff\xd9'):
        type = 'jpg'
    elif data.startswith('\x89PNG'):
        type = 'png'

    from StringIO import StringIO
    f = StringIO(data)

    return type, f
