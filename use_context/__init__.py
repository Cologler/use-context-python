# -*- coding: utf-8 -*-
#
# Copyright (c) 2019~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import collections
import dataclasses


class _IRollbackable:
    type_map = {}

    __slots__ = ('target', 'state')

    def __init__(self, target):
        self.target = target
        self.state = None

    def track(self):
        pass

    def rollback(self):
        pass

    def __init_subclass__(cls):
        for tp in vars(cls).get('types', ()):
            _IRollbackable.type_map[tp] = cls


class _Immutable(_IRollbackable):
    __slots__ = ()
    types = (tuple, str, int, float, frozenset)


class _List(_IRollbackable):
    __slots__ = ()
    types = (list, )

    def track(self):
        self.state = self.target.copy()

    def rollback(self):
        self.target[:] = self.state


class _GenericContainer(_IRollbackable):
    __slots__ = ()
    types = (
        set, dict, collections.defaultdict
    )

    def track(self):
        self.state = self.target.copy()

    def rollback(self):
        self.target.clear()
        self.target.update(self.state)

    @staticmethod
    def has_proto(target):
        for name in ('copy', 'clear', 'update'):
            if not callable(getattr(target, name, None)):
                return False
        return True


class _State(_IRollbackable):
    __slots__ = ()
    types = ()

    def track(self):
        self.state = self.target.get_state()

    def rollback(self):
        self.target.from_state(self.state)

    @staticmethod
    def has_proto(target):
        for name in ('get_state', 'from_state'):
            if not callable(getattr(target, name, None)):
                return False
        return True


class _Slots(_IRollbackable):
    __slots__ = ('attrs')

    def __init__(self, target, attrs):
        super().__init__(target)
        self.attrs = attrs

    def track(self):
        self.state = {}
        for attr in self.attrs:
            try:
                self.state[attr] = getattr(self.target, attr)
            except AttributeError:
                pass

    def rollback(self):
        for attr in self.attrs:
            if attr in self.state:
                setattr(self.target, attr, self.state[attr])
            else:
                delattr(self.target, attr)


class _DataClass(_IRollbackable):
    __slots__ = ()
    types = ()

    def track(self):
        self.state = {}
        for f in dataclasses.fields(self.target):
            self.state[f.name] = getattr(self.target, f.name)

    def rollback(self):
        for f in dataclasses.fields(self.target):
            setattr(self.target, f.name, self.state[f.name])


class _Context:
    __slots__ = ('_tracked')

    def __init__(self):
        self._tracked = []

    def __enter__(self):
        pass

    def __exit__(self, *_):
        self.rollback()

    def _begin_track(self, rb: _IRollbackable):
        rb.track()
        self._tracked.append(rb)

    def track(self, item):
        cls = type(item)
        rb_cls = _IRollbackable.type_map.get(cls)

        if rb_cls is not None:
            return self._begin_track(rb_cls(item))

        if dataclasses.is_dataclass(cls):
            return self._begin_track(_DataClass(item))

        for prbcls in (_GenericContainer, _State):
            if prbcls.has_proto(item):
                return self._begin_track(prbcls(item))

        # object with __dict__

        try:
            d = vars(item)
        except TypeError:
            d = None

        if isinstance(d, dict):
            return self._begin_track(_GenericContainer(d))

        if d is None:
            # object with __slots__
            attrs = []
            for base in cls.__mro__:
                s = getattr(base, '__slots__', ())
                if isinstance(s, str):
                    s = (s, ) # __slots__ == 'abc' equals __slots__ == ('abc', )
                attrs.extend(s)
            return self._begin_track(_Slots(item, attrs))

        raise TypeError(f'unknown type: {cls!r}')

    def rollback(self):
        while self._tracked:
            rb: _IRollbackable = self._tracked.pop()
            rb.rollback()


def use(*items):
    '''
    use some vars in current context.

    try rollback state when exit the context.
    '''
    ctx = _Context()
    for item in items:
        ctx.track(item)
    return ctx
