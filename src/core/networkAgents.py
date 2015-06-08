from game import Agent, Directions
from pacman import readCommand, runGames
from keyboardAgents import KeyboardAgent

from threading import Thread

import sys
from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketClientFactory, \
    WebSocketClientProtocol, \
    connectWS

class Dispatcher:
    def __init__(self):
        self.protocol = None
        self.listeners = []

    def register(self, listener):
        print "REGISTER"
        self.listeners.append(listener)

    def socketReceive(self, msg):
        print "RECEIVE"
        for listener in self.listeners:
            listener.socketReceive(payload.decode('utf8'))

    def socketSend(self, msg):
        if self.protocol is not None:
            print "SEND", msg
            self.protocol.socketSend(msg)

DISPATCHER = Dispatcher()

class ClientProtocol(WebSocketClientProtocol):
    def onOpen(self):
        print "PROTOCOL CREATED"
        assert DISPATCHER.protocol is None
        DISPATCHER.protocol = self

    def onMessage(self, payload, isBinary):
        DISPATCHER.socketReceive(payload.decode('utf8'))

    def socketSend(self, msg):
        print msg
        self.sendMessage(msg.encode('utf8'))

class NetworkMasterAgent(Agent):
    def __init__(self, wrapped, agentKey):
        self.wrapped = wrapped
        self.agentKey = agentKey
        DISPATCHER.register(self)

    def getAction(self, state):
        agentAction = self.wrapped.getAction(state)
        actionStr = '%s %s' % (self.agentKey, agentAction)
        DISPATCHER.socketSend(actionStr)
        return agentAction
        

class NetworkSlaveAgent(Agent):
    def __init__(self, agentKey):
        self.agentKey = agentKey
        self.buffer = []
        DISPATCHER.register(self)

    def getAction(self, state):
        if len(self.buffer) == 0:
            return Directions.STOP
        return self.buffer.pop()

    def socketReceive(actionStr):
        print "RECEIVE"
        parts = actionStr.split()
        if parts[0] == self.agentKey:
            self.buffer.push(actionStr)

class PlayerNetworkMasterAgent(NetworkMasterAgent):
    def __init__(self):
        NetworkMasterAgent.__init__(self, KeyboardAgent(), "PLAYER")

class PlayerNetworkSlaveAgent(NetworkSlaveAgent):
    def __init__(self):
        NetworkSlaveAgent.__init__(self, "PLAYER")

if __name__ == '__main__':
    factory = WebSocketClientFactory('ws://localhost:9000')
    factory.protocol = ClientProtocol
    connectWS(factory)
    #reactor.run()
    thread = Thread(target = reactor.run, args = (False,))
    thread.start()

    args = readCommand(sys.argv[1:])
    runner = lambda: runGames(**args)
    runner()
    #thread = Thread(target = runner)
    #thread.start()
