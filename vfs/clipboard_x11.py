"""Serve clipboard selections directly on X11/XWayland without command-line tools."""
# OWN AN X11 SELECTION AND SERVE UNICODE AND INCREMENTAL PASTE REQUESTS [
import select
from threading import Event, Thread


class X11ClipboardOwner:
    def __init__(self, text, selection_name='CLIPBOARD'):
        self.text = text
        self.selection_name = selection_name
        self.ready = Event()
        self.stop = Event()
        self.success = False
        self.thread = Thread(target=self.run, name='drive-clipboard-x11', daemon=True)

    def start(self):
        self.thread.start()
        if not self.ready.wait(3):
            self.stop.set()
            return False
        return self.success

    def run(self):
        connection = None
        try:
            from Xlib import X, Xatom, display, protocol
            connection = display.Display()
            if self.stop.is_set():
                return
            window = connection.screen().root.create_window(
                0, 0, 1, 1, 0, X.CopyFromParent, X.InputOnly, X.CopyFromParent)
            selection = connection.intern_atom(self.selection_name)
            utf8 = connection.intern_atom('UTF8_STRING')
            text = connection.intern_atom('TEXT')
            targets = connection.intern_atom('TARGETS')
            incr = connection.intern_atom('INCR')
            mime = connection.intern_atom('text/plain;charset=utf-8')
            plain = connection.intern_atom('text/plain')
            supported = [targets, utf8, text, mime, plain, Xatom.STRING]
            window.set_selection_owner(selection, X.CurrentTime)
            connection.sync()
            owner = connection.get_selection_owner(selection)
            self.success = bool(owner and owner.id == window.id)
            self.ready.set()
            if not self.success:
                return
            if self.selection_name == 'CLIPBOARD':
                manager = connection.intern_atom('CLIPBOARD_MANAGER')
                if connection.get_selection_owner(manager):
                    # Let a desktop manager retain the selection after app exit.
                    window.convert_selection(manager, connection.intern_atom('SAVE_TARGETS'),
                                             connection.intern_atom('_DRIVE_CLIPBOARD_SAVE'), X.CurrentTime)
                    connection.flush()
            transfers = {}
            chunk_size = 16 * 1024 - 128
            while not self.stop.is_set():
                if not connection.pending_events():
                    select.select([connection.fileno()], [], [], .1)
                    continue
                event = connection.next_event()
                if event.type == X.SelectionClear:
                    return
                if event.type == X.PropertyNotify and event.state == X.PropertyDelete:
                    key = (event.window.id, event.atom)
                    if key in transfers:
                        requestor, prop, kind, data, offset = transfers[key]
                        chunk = data[offset:offset + chunk_size]
                        requestor.change_property(prop, kind, 8, chunk)
                        if chunk:
                            transfers[key] = (requestor, prop, kind, data, offset + len(chunk))
                        else:
                            del transfers[key]
                        connection.flush()
                if event.type != X.SelectionRequest:
                    continue
                prop = event.property or event.target
                target = event.target
                if event.selection != selection:
                    prop = X.NONE
                elif target == targets:
                    event.requestor.change_property(prop, Xatom.ATOM, 32, supported)
                elif target in (utf8, text, mime, plain, Xatom.STRING):
                    data = self.text.encode('latin-1', errors='replace') if target == Xatom.STRING else self.text.encode('utf-8')
                    kind = utf8 if target == text else target
                    if len(data) > chunk_size:
                        event.requestor.change_attributes(event_mask=X.PropertyChangeMask)
                        event.requestor.change_property(prop, incr, 32, [len(data)])
                        transfers[(event.requestor.id, prop)] = (event.requestor, prop, kind, data, 0)
                    else:
                        event.requestor.change_property(prop, kind, 8, data)
                else:
                    prop = X.NONE
                event.requestor.send_event(protocol.event.SelectionNotify(
                    time=event.time, requestor=event.requestor, selection=event.selection,
                    target=target, property=prop), propagate=False)
                connection.flush()
        except Exception:
            self.success = False
        finally:
            self.ready.set()
            if connection is not None:
                connection.close()


def copy_x11(text):
    return X11ClipboardOwner(text).start()
# OWN AN X11 SELECTION AND SERVE UNICODE AND INCREMENTAL PASTE REQUESTS ]
