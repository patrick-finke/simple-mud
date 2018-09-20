#/usr/bin/env python3

import socket
import select
import time
import sys

from enum import Enum

class SimpleServer():
    """A simple server."""

    class _Client():
        """Container for client data."""
        def __init__(self, socket, address, buffer, lastcheck):
            self.socket = socket
            self.address = address
            self.buffer = buffer
            self.lastcheck = lastcheck

    class Event():
        """An event, like a player connects or disconnects."""
        def __init__(self, etype, content):
            self.etype = etype
            self.content = content

        def __repr__(self):
            return str(self)

        def __str__(self):
            return "<Event: " + str(self.etype) + ">"

    ETYPE = Enum("ETYPE", "NEWPLAYER PLAYERLEFT MESSAGE")
    _READSTATE = Enum("_READSTATE", "NORMAL MESSAGE SUBNEG")

    class _TN(Enum):
        """Codes used in the telnet protocol."""
        INTERPRET_AS_MESSAGE = 255
        ARE_YOU_THERE = 246
        WILL = 251
        WONT = 252
        DO = 253
        DONT = 254
        SUBNEG_START = 250
        SUBNEG_END = 240

    def __init__(self, ip, port, timeout=5.):
        self.ip = ip
        self.port = port
        self.timeout = timeout

        self._clients = {}
        self._nextid = 0
        self._events = []
        
        self._listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listen_socket.bind((ip, port))
        self._listen_socket.setblocking(False)
        self._listen_socket.listen(1)

    def get_ids(self):
        """Return a list of all client ids."""
        return list(self._clients.keys())

    def update(self):
        """Update the state of the server. This should be called once per game loop."""
        self._update_new_connections()
        self._update_disconnected()
        self._update_messages()

    def poll_event(self):
        """Poll the next event in the event queue. If there is no event left return ``None``"""
        try:
            return self._events.pop(0)
        except IndexError:
            return None

    def send_message(self, cid, message):
        """Send a message to a client."""
        self._attempt_send(cid, message + "\n\r")

    def _add_event(self, etype, *content):
        """Add an event to the queue."""
        event = self.Event(etype, content)
        self._events.append(event)

    def _update_new_connections(self):
        """Check for new connections."""
        rlist, wlist, xlist = select.select([self._listen_socket], [], [], 0)

        if self._listen_socket not in rlist:
            return

        client_socket, client_addr = self._listen_socket.accept()
        client_socket.setblocking(False)

        self._clients[self._nextid] = SimpleServer._Client(client_socket, client_addr[0], "", time.time())
        self._add_event(self.ETYPE.NEWPLAYER, self._nextid)

        self._nextid += 1

    def _update_disconnected(self):
        """Check for disconnected client."""
        for cid, cl in list(self._clients.items()):
            if time.time() - cl.lastcheck < self.timeout:
                continue

            self._attempt_send(cid, "\x00")
            cl.lastcheck = time.time()

    def _update_messages(self):
        """Check for new messages."""
        for cid, cl in self._clients.items():
            rlist, wlist, xlist = select.select([cl.socket], [], [], 0)

            if cl.socket not in rlist:
                continue

            try:
                data = cl.socket.recv(1024).decode("latin1")

                message = self._process_send_data(cl, data)
                if message:
                    message = message.strip()
                    self._add_event(self.ETYPE.MESSAGE, cid, message)
            except socket.error:
                self._handle_disconnect(cid)

    def _attempt_send(self, cid, data):
        """Try to send data. Disconnect the client of failure."""
        try:
            self._clients[cid].socket.sendall(bytearray(data, "latin1"))
        except KeyError:
            pass
        except socket.error:
            self._handle_disconnect(cid)

    def _handle_disconnect(self, cid):
        """Do the actual disconnect."""
        del(self._clients[cid])
        self._add_event(self.ETYPE.PLAYERLEFT, cid)

    def _process_send_data(self, cl, data):
        """Process the received data and filter any telnet commands."""
        message = None
        state = self._READSTATE.NORMAL

        for c in data:
            if state == self._READSTATE.NORMAL:
                if ord(c) == self._TN.INTERPRET_AS_MESSAGE:
                    state = self._READSTATE.MESSAGE
                elif c == "\n":
                    message = cl.buffer
                    cl.buffer = ""
                elif c == "\x08":
                    cl.buffer = cl.buffer[:-1]

                else:
                    cl.buffer += c
            elif state == self._READSTATE.MESSAGE:
                if ord(c) == self._TN.SUBNEG_START:
                    state = self._READSTATE.SUBNEG
                elif ord(c) in (self._TN.WILL, self._TN.WONT, self._TN.DO, self._TN.DONT):
                    state = self._READSTATE.MESSAGE
                else:
                    state = self._READSTATE.NORMAL
            elif state == self._READSTATE.SUBNEG:
                if ord(c) == self._TN.SUBNEG_END:
                    state = self._READSTATE.NORMAL

        return message
