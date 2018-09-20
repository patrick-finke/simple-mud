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

        etype = event[0]
        if etype == SimpleServer.EVENT.NEWPLAYER:
            print("new player" + str(event))
            _, pid = event
            for targetid in mudserver.get_ids():
                if targetid != pid:
                    mudserver.send_message(targetid, str(pid) + " joined.")
        elif etype == SimpleServer.EVENT.PLAYERLEFT:
            print("player left" + str(event))
            _, pid = event
            for targetid in mudserver.get_ids():
                if targetid != pid:
                    mudserver.send_message(targetid, str(pid) + " left.")
        elif etype == SimpleServer.EVENT.MESSAGE:
            print("new message" + str(event))
            _, fromid, message = event
            for pid in mudserver.get_ids():
                if pid != fromid:
                    mudserver.send_message(pid, str(fromid) + ": " + message)


        time.sleep(.2)
