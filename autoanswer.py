#!/usr/bin/env python
import sys
import pjsua as pj
import ConfigParser
import time
import raven


dsn = 'https://0b915e29784f479f93db6ae2870515b6:b2fb7becafdc4c259b813a8f84f5b855@sentry.finn.io/2'
ravenclient = raven.Client(dsn)


totalcalls = 0


class AccountCallback(pj.AccountCallback):
    def __init__(self, account=None):
        try:
            pj.AccountCallback.__init__(self, account)
            self.totalcalls = 0
        except Exception as e:
            ravenclient.captureException()
            print(e)

    def on_incoming_call(self, call):
        try:
            self.totalcalls += 1
            print("At call #%0.d" % self.totalcalls)
            call.set_callback(CallCallback())
            if config.has_section('pa'):
                wav_player_id = pj.Lib.instance().create_player(config.get('pa', 'file'), loop=False)
                wav_slot = pj.Lib.instance().player_get_slot(wav_player_id)
                pj.Lib.instance().conf_connect(wav_slot, 0)
                time.sleep(config.getint('pa', 'filetime'))
                pj.Lib.instance().player_destroy(wav_player_id)
            call.answer(200)
        except Exception as e:
            ravenclient.captureException()
            print(e)


class CallCallback(pj.CallCallback):
    call = None

    def __init__(self, call=None, number=0):
        try:
            self.call = call
            self.number = number
            pj.CallCallback.__init__(self, call)
        except Exception as e:
            ravenclient.captureException()
            print(e)

    def on_state(self):
        try:
            print("Call with %s is %s (last code=%s: %s)" % (
                self.call.info().remote_uri,
                self.call.info().state_text,
                self.call.info().last_code,
                self.call.info().last_reason
            ))
            if self.call.info().state_text == "DISCONNCTD" and self.number > 30:
                sys.exit(0)
        except Exception as e:
            ravenclient.captureException()
            print(e)

    # Notification when call's media state has changed.
    def on_media_state(self):
        try:
            if self.call.info().media_state == pj.MediaState.ACTIVE:
                # Connect the call to sound device
                call_slot = self.call.info().conf_slot
                pj.Lib.instance().conf_connect(call_slot, 0)
                pj.Lib.instance().conf_connect(0, call_slot)
                print("Media is now active")
            else:
                print("Media is inactive")
        except Exception as e:
            ravenclient.captureException()
            print(e)


if __name__ == "__main__":
    config = ConfigParser.SafeConfigParser()
    config.read(['config.conf', '/etc/paging.conf', 'callpipe.conf', '/etc/callpipe.conf'] + sys.argv[1:])

    try:
        # Create library instance
        lib = pj.Lib()

        # A user agent cuz pjsip wants some shit
        ua = pj.UAConfig()
        ua.max_calls = 10
        ua.user_agent = " ".join(sys.argv)

        # Init library with default config
        lib.init(ua)

        # Create UDP transport which listens to any available port
        transport = lib.create_transport(pj.TransportType.UDP)

        # Start the library
        lib.start()

        # Create local/user-less account
        acc = lib.create_account(pj.AccountConfig(
            config.get("sip", "domain"),
            config.get("sip", "user"),
            config.get("sip", "pass")
        ), cb=AccountCallback())

        # Wait for ENTER before quitting
        print("Press <ENTER> to quit")
        sys.stdin.readline().rstrip("\r\n")

        # We're done, shutdown the library
        lib.destroy()
        lib = None

    except pj.Error as e:
        ravenclient.captureException()
        print("Exception: %s" % str(e))
