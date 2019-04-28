# -*- coding: utf-8 -*-
#
# Copyright (c) 2019~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import collections
import dataclasses
import decimal

_Immutable = frozenset([
    bool,
    int, float, complex, decimal.Decimal,
    str,
    tuple,
    frozenset
])


class _IRollbackable:
    type_map = {}
    all_subclass = []

    __slots__ = ('target', 'state')

    def __init__(self, target):
        self.target = target
        self.state = None

    def track(self):
        pass

    def rollback(self):
        pass

    def __init_subclass__(cls):
        _IRollbackable.all_subclass.append(cls)
        for tp in vars(cls).get('types', ()):
            _IRollbackable.type_map[tp] = cls

    @staticmethod
    def has_proto(target):
        return False


class _List(_IRollbackable):
    __slots__ = ()
    types = (list, )

    def track(self):
        self.state = self.target.copy()

    def rollback(self):
        self.target[:] = self.state


class _DataClass(_IRollbackable):
    __slots__ = ()

    def track(self):
        self.state = {}
        for f in dataclasses.fields(self.target):
            self.state[f.name] = getattr(self.target, f.name)

    def rollback(self):
        for f in dataclasses.fields(self.target):
            setattr(self.target, f.name, self.state[f.name])

    @staticmethod
    def has_proto(target):
        return dataclasses.is_dataclass(target)


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


def _get_slots_attrs(cls):
    attrs = set()
    for base in cls.__mro__:
        s = getattr(base, '__slots__', ())
        if isinstance(s, str):
            s = (s, ) # __slots__ == 'abc' equals __slots__ == ('abc', )
        attrs.update(s)
    return list(attrs)


class _Context:
    __slots__ = ('_tracked')

    def __init__(self):
        self._tracked = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.rollback()

    def _begin_track(self, rb: _IRollbackable):
        rb.track()
        self._tracked.append(rb)

    def track(self, item):
        cls = type(item)
        if cls in _Immutable:
            return

        rb_cls = _IRollbackable.type_map.get(cls)

        if rb_cls is not None:
            return self._begin_track(rb_cls(item))

        for prbcls in _IRollbackable.all_subclass:
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
            attrs = _get_slots_attrs(cls)
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
