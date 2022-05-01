'''
KXDrawer
========

This widget needs to be a child of ``FloatLayout`` (or subclass thereof).
'''

__all__ = ('KXDrawer', )

from kivy.properties import (
    NumericProperty, ColorProperty, OptionProperty, BooleanProperty,
)
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget

import asynckivy as ak

KV_CODE = '''
<KXDrawerTab>:
    canvas.before:
        Color:
            rgba: self.background_color
        Rectangle:
            pos: self.pos
            size: self.size
    canvas:
        PushMatrix:
        Translate:
            xy: self.center
        Rotate:
            angle: self.icon_angle
        Color:
            rgba: self.foreground_color
        Triangle:
            points: (s := (min(*self.size) * 0.2), ) and [-s, -s, -s, s, s, 0]
        PopMatrix:

<KXDrawer>:
    _active: self.parent is not None or self._is_moving_to_the_top
    canvas.before:
        Color:
            rgba: root.background_color
        Rectangle:
            pos: 0, 0
            size: self.size
    KXDrawerTab:
        id: tab
        background_color: root.background_color
        foreground_color: root.foreground_color
'''
Builder.load_string(KV_CODE)


class KXDrawerTab(ButtonBehavior, Widget):
    background_color = ColorProperty()
    foreground_color = ColorProperty()
    icon_angle = NumericProperty(0)

    __ = {
        'l': {'x': 1, 'center_y': .5, },
        'r': {'right': 0, 'center_y': .5, },
        'b': {'y': 1, 'center_x': .5, },
        't': {'top': 0, 'center_x': .5, },
    }
    def update(self, anchor, *, __=__):
        from kivy.metrics import sp
        anchor = anchor[0]
        self.font_size = font_size = max(sp(15), 24)
        self.size = self.size_hint_min = (font_size, font_size, )
        self.size_hint = (.4, None) if anchor in 'tb' else (None, .4)
        self.pos_hint = __[anchor].copy()

    del __


class KXDrawer(RelativeLayout):
    __events__ = ('on_pre_open', 'on_open', 'on_pre_close', 'on_close', )

    auto_bring_to_front = BooleanProperty(False)
    '''If True, moves the drawer on top of the other siblings when it opens.'''

    anim_duration = NumericProperty(.3)
    '''Duration of the opening/closing animations.'''

    background_color = ColorProperty("#222222")
    foreground_color = ColorProperty("#AAAAAA")

    anchor = OptionProperty(
        'lm', options=r'lt lm lb rt rm rb bl bm br tl tm tr'.split())
    '''親のどの位置にくっつくか

        'l' stands for 'left'.
        'r' stands for 'right'.
        't' stands for 'top'.
        'b' stands for 'bottom'.
        'm' stands for 'middle'.
    '''

    _active = BooleanProperty(False)

    def __init__(self, **kwargs):
        self._is_moving_to_the_top = False
        self._open_event = ak.Event()
        self._close_event = ak.Event()
        super().__init__(**kwargs)
        ak.start(self._main())

    async def _main(self):
        import asynckivy as ak
        while True:
            await ak.sleep(-1)
            if not self._active:
                await ak.event(self, '_active')
            await ak.sleep(-1)
            if self._active:
                await ak.or_(ak.event(self, '_active'), self._main2())

    async def _main2(self):
        import asynckivy as ak
        while True:
            await ak.sleep(-1)
            await ak.or_(ak.event(self, 'anchor'), self._main3())


    def on_parent(self, __, parent):
        if parent is not None and (not isinstance(parent, FloatLayout)):
            raise ValueError("KXDrawer needs to be a child of FloatLayout!!")

    async def _main3(self):
        import asynckivy as ak
        anchor = self.anchor
        moves_vertically = anchor[0] in 'tb'
        moves_forward_direction = anchor[0] in 'lb'
        parent = self.parent
        tab = self.ids.tab
        tab.update(anchor)
        self.pos_hint = _get_initial_pos_hint(anchor)
        ph = self.pos_hint  # CAUTION: 上の行とまとめてはいけない
        # '_c'-suffix means 'close'.  '_o'-suffix means 'open'.
        icon_angle_c = _get_initial_icon_angle(anchor)
        icon_angle_o = icon_angle_c + 180.
        pos_key_c = _anchor_2_opposite_poskey(anchor)
        pos_key_o = _anchor_2_poskey(anchor)
        ph_value = 0. if moves_forward_direction else 1.
        def _get_pos_value_in_local_coordinates():
            pos_value = getattr(parent, pos_key_o)
            return parent.to_local(pos_value, pos_value)[moves_vertically]

        tab.icon_angle = icon_angle_c
        ph[pos_key_c] = ph_value
        self.property('pos_hint').dispatch(self)  # 何故か必要
        await ak.sleep(-1)

        close_event = self._close_event
        open_event = self._open_event
        while True:
            await ak.or_(ak.event(tab, 'on_press'), open_event.wait())
            open_event.clear()
            self.dispatch('on_pre_open')
            if self.auto_bring_to_front:
                self._is_moving_to_the_top = True
                parent.remove_widget(self)
                parent.add_widget(self)
                self._is_moving_to_the_top = False
            del ph[pos_key_c]
            await ak.animate(
                self, d=self.anim_duration,
                **{pos_key_o: _get_pos_value_in_local_coordinates()})
            await ak.animate(tab, d=self.anim_duration, icon_angle=icon_angle_o)
            ph[pos_key_o] = ph_value
            self.dispatch('on_open')
            await ak.or_(ak.event(tab, 'on_press'), close_event.wait())
            close_event.clear()
            self.dispatch('on_pre_close')
            del ph[pos_key_o]
            await ak.animate(
                self, d=self.anim_duration,
                **{pos_key_c: _get_pos_value_in_local_coordinates()})
            await ak.animate(tab, d=self.anim_duration, icon_angle=icon_angle_c)
            ph[pos_key_c] = ph_value
            self.dispatch('on_close')

    def open(self, *args, **kwargs):
        '''Opens the drawer. This method can take any number of arguments
        but doesn't use them at all, so you can bind the method to any event
        directly.

        .. code-block::

           drawer = KXDrawer()
           button = Button()
           button.bind(on_press=drawer.open)
        '''
        self._open_event.set()

    def close(self, *args, **kwargs):
        '''Closes the drawer. This method can take any number of arguments
        but doesn't use them at all, so you can bind the method to any event
        directly.

        .. code-block::

           drawer = KXDrawer()
           button = Button()
           button.bind(on_press=drawer.close)
        '''
        self._close_event.set()

    def on_pre_open(self):
        pass

    def on_open(self):
        pass

    def on_pre_close(self):
        pass

    def on_close(self):
        pass


__ = {'l': 'x', 't': 'top', 'r': 'right', 'b': 'y', }
def _anchor_2_poskey(anchor, *, __=__):
    return __[anchor[0]]


__ = {'l': 'right', 't': 'y', 'r': 'x', 'b': 'top', }
def _anchor_2_opposite_poskey(anchor, *, __=__):
    return __[anchor[0]]


__ = {
    'bl': {'x': 0., },
    'tl': {'x': 0., },
    'lb': {'y': 0., },
    'rb': {'y': 0., },
    'bm': {'center_x': .5, },
    'tm': {'center_x': .5, },
    'rm': {'center_y': .5, },
    'lm': {'center_y': .5, },
    'br': {'right': 1., },
    'tr': {'right': 1., },
    'lt': {'top': 1., },
    'rt': {'top': 1., },
}
def _get_initial_pos_hint(anchor, *, __=__):
    return __[anchor].copy()


__ = {'l': 0., 't': 270., 'r': 180., 'b': 90., }
def _get_initial_icon_angle(anchor, *, __=__):
    return __[anchor[0]]


del __
