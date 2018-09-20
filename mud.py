#/usr/bin/env python3

import time
from server import SimpleServer

mudserver = SimpleServer("0.0.0.0", 1234)

while True:
    mudserver.update()

    while True:
        event = mudserver.poll_event()
        if event is None:
            break

        etype = event.etype
        if etype == SimpleServer.ETYPE.NEWPLAYER:
            print("new player" + str(event))
            pid, = event.content
            for targetid in mudserver.get_ids():
                if targetid != pid:
                    mudserver.send_message(targetid, str(pid) + " joined.")
        elif etype == SimpleServer.ETYPE.PLAYERLEFT:
            print("player left" + str(event))
            pid, = event.content
            for targetid in mudserver.get_ids():
                if targetid != pid:
                    mudserver.send_message(targetid, str(pid) + " left.")
        elif etype == SimpleServer.ETYPE.MESSAGE:
            print("new message" + str(event))
            fromid, message = event.content
            for pid in mudserver.get_ids():
                if pid != fromid:
                    mudserver.send_message(pid, str(fromid) + ": " + message)


        time.sleep(.5)
