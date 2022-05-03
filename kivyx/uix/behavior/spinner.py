__all__ = ('KXSpinnerLikeBehavior', )

import itertools
from functools import partial
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.properties import ListProperty, ObjectProperty, BooleanProperty, NumericProperty, VariableListProperty
from kivy.uix.dropdown import DropDown
from kivy.uix.spinner import SpinnerOption
import asynckivy as ak


class KXSpinnerLikeBehavior:
    '''Mix-in class that helps to create your own spinner.

    Unlike the official one, this one can be combined with any widget as long as an 'on_release' event is properly implemented. For example:

    .. code-block::

        class Spinner1(KXSpinnerLikeBehavior, Button):
            ...
        class Spinner2(KXSpinnerLikeBehavior, ButtonBehavior, Image):
            ...
        class Spinner3(KXSpinnerLikeBehavior, ButtonBehavior, BoxLayout):
            ...

    And the 'option_cls' doesn't have to have a 'text' property so the following classes are all valid.

    .. code-block::

        class SpinnerOption1(ButtonBehavior, Image):
            ...
        class SpinnerOption2(ButtonBehavior, BoxLayout):
            ...
        spinner.option_cls = SpinnerOption1
        spinner.option_cls = SpinnerOption2
    '''

    selection = ObjectProperty(None, allownone=True, rebind=True)
    '''(read-only) Currently selected option-widget. None if no one is selected.'''

    option_data = ListProperty()
    '''A list of dictionaries that works like 'RecycleView.data'. The number of elements in this list will be the
    number of the options within the dropdown list displayed under the spinner.
    '''

    option_spacing = VariableListProperty([0, 0], length=2)

    option_padding = VariableListProperty([0, 0, 0, 0])

    option_cls = ObjectProperty(SpinnerOption)
    '''Same as the official one except ``text`` property is not required.'''

    auto_select = NumericProperty(None, allownone=True)
    ''' The ``auto_select``-th option will automatically be selected if none of the options is selected.'''

    dropdown_cls = ObjectProperty(DropDown)
    '''Same as the official one. '''

    sync_height = BooleanProperty(False)
    '''Same as the official one. '''

    def __init__(self, **kwargs):
        self._main_task = ak.dummy_task
        self._previously_used_resources = {'dropdown': None, 'option_widgets': None, }
        super().__init__(**kwargs)
        fbind = self.fbind
        trigger = Clock.create_trigger(self._restart)
        for prop in ('option_data', 'option_cls', 'auto_select', 'dropdown_cls', 'sync_height', ):
            fbind(prop, trigger)

    def _restart(self, dt):
        self._main_task.cancel()
        self._main_task = ak.start(self._main())

    async def _main(self):
        res = self._previously_used_resources

        # Prepare a dropdown widget. Re-use the previous one if possible.
        dd: DropDown = res['dropdown']
        cls = self.dropdown_cls
        if not cls:
            return
        if isinstance(cls, str):
            cls = Factory.get(cls)
        if dd is None or cls is not dd.__class__:
            dd = cls()
            c = dd.container
            c.spacing = self.option_spacing
            c.padding = self.option_padding
            self.bind(
                option_spacing=c.setter("spacing"),
                option_padding=c.setter("padding"),
            )
            del c
        del cls

        # option_cls
        option_cls = self.option_cls
        if not option_cls:
            return
        if isinstance(option_cls, str):
            option_cls = Factory.get(option_cls)

        # Prepare option widgets. Re-use the previous ones if possible.
        w_factory = iter(option_cls, None)
        ws = res['option_widgets']
        if ws and ws[0].__class__ is option_cls:
            option_widgets = itertools.chain(ws, w_factory)
        else:
            option_widgets = w_factory
        del w_factory, ws

        # Add option widgets to the dropdown
        setattr_ = setattr
        on_release = partial(self._on_release_item, dd)
        for w, w_props in zip(option_widgets, self.option_data):
            for name, value in w_props.items():
                setattr_(w, name, value)
            w.bind(on_release=on_release)
            dd.add_widget(w)

        # sync_height
        if self.sync_height:
            _sync_height = partial(self._sync_height, dd.container)
            _sync_height(self, self.height)
            self.bind(height=_sync_height)
        else:
            _sync_height = None

        # auto_select
        auto = self.auto_select
        cs = dd.container.children
        if self.selection in cs:
            pass
        elif auto is None or len(cs) <= auto:
            self.selection = None
        else:
            self.selection = cs[-(auto + 1)]
        del auto, cs

        # Preparation is done. Start running.
        try:
            dd.bind(on_select=self._on_dropdown_select)
            ak_event = ak.event
            dd_open = dd.open
            while True:
                await ak_event(self, 'on_release')
                dd_open(self)
                await ak_event(dd, 'on_dismiss')
        finally:
            dd.unbind(on_select=self._on_dropdown_select)
            if _sync_height is not None:
                self.unbind(height=_sync_height)
            res['dropdown'] = dd
            res['option_widgets'] = dd.container.children[::-1]
            dd.clear_widgets()
            dd._real_dismiss()

    @staticmethod
    def _sync_height(container, spinner, height):
        for c in container.children:
            c.height = height

    @staticmethod
    def _on_release_item(dropdown, option_widget):
        dropdown.select(option_widget)

    def _on_dropdown_select(self, dropdown, option_widget, *__):
        self.selection = option_widget
        dropdown.dismiss()


Factory.register('KXSpinnerLikeBehavior', cls=KXSpinnerLikeBehavior)
