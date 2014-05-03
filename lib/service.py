"""
Provides the DBus service.
"""
import dbus, dbus.service
from gi.repository import Gtk

DBUS_NAME = 'org.adamnew123456.lnsd'
DBUS_PATH = '/org/adamnew123456/lnsd'
class LNS_DBus(dbus.service.Object):
    def __init__(self, lnsd):
        bus_name = dbus.service.BusName(DBUS_NAME, bus=dbus.SessionBus())
        super().__init__(bus_name, DBUS_PATH)
        self.lnsd = lnsd

    @dbus.service.method(DBUS_NAME, in_signature='s')
    def QueryName(self, name):
        try:
            bytes_name = bytes(name, 'ascii')

            with self.lnsd.host_names_lock:
                names_hosts = ~self.lnsd.host_names
                return names_hosts.get(bytes_name, '')
        except UnicodeEncodeError:
            return ''

    @dbus.service.method(DBUS_NAME, in_signature='s')
    def QueryHost(self, ip_addr):
        with self.lnsd.host_names_lock:
            return self.lnsd.host_names.get(ip_addr, '')

    @dbus.service.method(DBUS_NAME, out_signature='a{ss}')
    def QueryAll(self):
        with self.lnsd.host_names_lock:
            return dict(self.lnsd.host_names)

    @dbus.service.method(DBUS_NAME)
    def Quit(self):
        self.lnsd.quit_event.set()
        Gtk.main_quit()
