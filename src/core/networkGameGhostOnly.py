import sys
from threading import Thread
import time
import random

from pacman import *
from game import *
import pacmanAgents
import ghostAgents
import textDisplay
import layout

from twisted.internet import reactor, ssl
from twisted.python import log
from twisted.web.server import Site
from twisted.web.static import File

from autobahn.twisted.websocket import WebSocketServerFactory, \
    WebSocketServerProtocol, \
    listenWS

class PacmanServerProtocol(WebSocketServerProtocol):

    def onOpen(self):
        self.factory.register(self)

    def onMessage(self, payload, isBinary):
        if not isBinary:
            msg = payload.decode('utf8')
            self.factory.receive(msg, self)

    def connectionLost(self, reason):
        WebSocketServerProtocol.connectionLost(self, reason)
        self.factory.unregister(self)


class PacmanServerFactory(WebSocketServerFactory):

    def __init__(self, url, debug=False, debugCodePaths=False):
        WebSocketServerFactory.__init__(self, url, debug=debug, debugCodePaths=debugCodePaths)
        self.clients = []
        self.pacmen = {}
        self.traces = dict()
        self.games = dict()
        self.displays = dict()

	self.assignmentIds = dict()
 	self.hitIds = dict()

    def tick(self, client):
        if client not in self.clients:
            return
        if (self.games[client].gameOver or self.displays[client].gameStep == 120):
            if (self.displays[client].gameStep == 120):
              msg = "draw"
            elif self.games[client].state.isWin():
              msg = "win"
            else:
              msg = "lose"
            client.sendMessage("END:" + msg)
	    del self.traces[client]
            return
        reactor.callLater(0.6, lambda: self.tick(client))
        self.games[client].net_tick()

    def register(self, client):
        if client not in self.clients:
            self.clients.append(client)

    def unregister(self, client):
        if client in self.clients:
            self.clients.remove(client)

    def receive(self, msg, client):
        msgType, msgBody = msg.split(":", 1)

        if msgType == "PLAY":
            self.spawnGame(client, msgBody)

        elif msgType == "CHAT":
            #self.broadcastChat(msgBody)
            self.acceptChat(client, msgBody)

    def acceptChat(self, client, msg):
        if client not in self.traces:
            return
        client.sendMessage("CHAT:" + msg.encode('utf8'))
        self.traces[client].append((self.displays[client].gameStep, msg))

    LAYOUTS = [
               ("smallClassic", 2),
               ("mediumClassic", 2),
               ("mediumSurvival", 2),
               ("mediumScaryMaze", 2),
               #("openClassic", 1),
               ##("openHunt", 2),
               #("smallGrid", 1),
               #("mediumGrid", 1),
               #("smallHunt", 2),
               #("trapped2", 1)
               #("trickyClassic", 2),
               #("mediumCorners", 2)
              ]

    GHOSTS = [ghostAgents.DirectionalGhost(1),
              ghostAgents.RandomGhost(2),
              ghostAgents.DirectionalGhost(3),
              ghostAgents.RandomGhost(4),
              ghostAgents.DirectionalGhost(5),
              ghostAgents.RandomGhost(6)]

    def spawnGame(self, client, clientUrl):
	try:
		args = clientUrl.split("?")[1].split("&")
		clientKeys = dict([a.split("=") for a in args])
		self.assignmentIds[client] = clientKeys['assignmentId']
		self.hitIds[client] = clientKeys['hitId']
	except Exception as e:
		print e
		return

        TIMEOUT = 30
        layoutName, nGhosts = self.LAYOUTS[random.randint(0, len(self.LAYOUTS) - 1)]
        lyt = layout.getLayout(layoutName)
        self.pacmen[client] = pacmanAgents.GreedyAgent()
        pacman = self.pacmen[client] # pacmanAgents.GreedyAgent()
        #ghosts = [ghostAgents.RandomGhost(1), ghostAgents.DirectionalGhost(2)]
        ghosts = self.GHOSTS[:nGhosts]
        rules = ClassicGameRules(TIMEOUT)
        display = NetworkDisplay(client, layoutName)
        game = rules.newGame(lyt, pacman, ghosts, display, quiet=True)

        self.games[client] = game
        self.traces[client] = []
        self.displays[client] = display

        game.net_start()
        self.tick(client)


class NetworkDisplay:
    def __init__(self, client, layoutName):
        self.client = client
	self.layoutName = layoutName

    def initialize(self, state):
        self.gameStep = 0
        self.update(state)

    def update(self, state):
        if self.isFullTurn(state):
            serState = self.serialize(state)
            self.client.sendMessage(("GAME:" + serState).encode('utf8'))
        self.gameStep += 1

    def isFullTurn(self, state):
        return self.gameStep % len(state.agentStates) == 0

    def finish(self):
        pass

    def serialize(self, state):
        layout = state.layout
        food = state.food
        walls = state.layout.walls
        boardStr = ""
        boardStr += str(layout.height) + "\n";
        for y in range(layout.height-1, -1, -1):
            for x in range(layout.width):
                if walls[x][y]:
                    boardStr += "#"
                elif (x, y) in state.capsules:
                    boardStr += "o"
                elif food[x][y]:
                    boardStr += "."
                else:
                    boardStr += " "
            boardStr += "\n"

        boardStr += "\n"

        for gid, agentState in enumerate(state.agentStates):
            x, y = [int(i) for i in nearestPoint(agentState.configuration.pos)]
            agentStr = "P" if agentState.isPacman else "G%d" % gid
            if agentState.scaredTimer > 0:
                agentStr = "S"
            boardStr += "%s %d %d\n" % (agentStr, x, layout.height - y - 1)

	boardStr += self.layoutName
        return boardStr


if __name__ == '__main__':
    DEBUG = True
    ServerFactory = PacmanServerFactory
    factory = ServerFactory("wss://jacobandreas.net:9000",
                            debug=DEBUG,
                            debugCodePaths=DEBUG)

    contextFactory = ssl.DefaultOpenSSLContextFactory('/home/ec2-user/pacman/keys/ssl.unenc.key',
                                                      '/home/ec2-user/pacman/keys/ssl.crt')
    factory.protocol = PacmanServerProtocol
    factory.setProtocolOptions(allowHixie76 = True)
    listenWS(factory, contextFactory)

    webdir = File(".")
    web = Site(webdir)
    reactor.listenTCP(8080, web)
    
    reactor.run()
