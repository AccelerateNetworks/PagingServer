#!/usr/bin/env python
# $Id$
#
# SIP account and registration sample. In this sample, the program
# will block to wait until registration is complete
#
# Copyright (C) 2003-2008 Benny Prijono <benny@prijono.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
import sys
import pjsua as pj
import ConfigParser
try:
    from raven import Client
    raven = Client('http://dd2c825ff9b1417d88a99573903ebf80:91631495b10b45f8a1cdbc492088da6a@localhost:9000/1')
except:
    print("ZOMG INSTALL RAVEN YOU FUCK")
    print("protip: pip install raven")
    sys.exit(1)


config = ConfigParser.SafeConfigParser()
config.read('config.ini', 'callram.conf', '/etc/callram.conf')


# Logging callback
def log_cb(level, string, length):
    for line in string.split("\n"):
        print("[LOG ] [%s] [%s] %s" % (level, length, line))

# Callback to receive events from Call
class MyCallCallback(pj.CallCallback):
    number = None
    redial = 0

    def __init__(self, call=None, number=None, redial=0):
        pj.CallCallback.__init__(self, call)
        self.num = number
        self.redial = redial

    # Notification when call state has changed
    def on_state(self):
        try:
            print("[CALL] [%s] [%s] [STATE] [%s] %s" % (self.num, self.redial, self.call.info().state, self.call.info().state_text))

            if self.call.info().state == 5:
                print("omg lel holding call open")
                #time.sleep(5)
                self.call.hangup()
                #self.call.transfer(config.get('call', 'to'))

            if self.call.info().state == 6:
                # self.call.hangup()
                acc.make_call(config.get('call', 'to'),
                              MyCallCallback(number=self.num,
                                             redial=self.redial+1))
        except (pj.Error, TypeError) as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print("[CALL] [%s] [%s] [Line %s] Error: %s" % (self.num, self.redial, exc_tb.tb_lineno, str(e)))

    # Notification when call's media state has changed.
    def on_media_state(self):
        global lib
        if self.call.info().media_state == pj.MediaState.ACTIVE:
            # Connect the call to sound device
            call_slot = self.call.info().conf_slot
            lib.conf_connect(call_slot, 0)
            lib.conf_connect(0, call_slot)

try:
    # Create library instance
    lib = pj.Lib()

    # Create a user agent
    ua = pj.UAConfig()
    ua.max_calls = 100
    ua.user_agent = sys.argv[0]

    # Init library with default config
    lib.init(ua)

    # Create UDP transport which listens to any available port
    transport = lib.create_transport(pj.TransportType.UDP)

    # Start the library
    lib.start()

    # Create local/user-less account
    acc = lib.create_account(pj.AccountConfig(
        config.get("account", "domain"),
        config.get("account", "user"),
        config.get("account", "pass")
    ))

    # Make call
    for i in range(0, 1):
        call = acc.make_call(config.get('call', 'to'), MyCallCallback(number=i))

    # Wait for ENTER before quitting
    print("Press <ENTER> to quit")
    sys.stdin.readline().rstrip("\r\n")

    # We're done, shutdown the library
    lib.destroy()
    lib = None


except pj.Error as e:
    print("Exception: %s" % str(e))
    lib.destroy()
    lib = None
    sys.exit(1)
