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

from twisted.internet import reactor
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
            #msg = "{} from {}".format(payload.decode('utf8'), self.peer)
            #self.factory.broadcast(msg)
            msg = payload.decode('utf8')
            self.factory.receive(msg, self)

    def connectionLost(self, reason):
        WebSocketServerProtocol.connectionLost(self, reason)
        self.factory.unregister(self)


class PacmanServerFactory(WebSocketServerFactory):

    def __init__(self, url, debug=False, debugCodePaths=False):
        WebSocketServerFactory.__init__(self, url, debug=debug, debugCodePaths=debugCodePaths)
        self.clients = []
        self.pacman = pacmanAgents.InteractiveAgent(0)
        self.log = open("chat.log", "a")
        self.game = None

    def tick(self):
        if (self.game.gameOver):
            self.broadcastEnd(self.game.state.isWin())
            return
        reactor.callLater(0.2, self.tick)
        self.game.net_tick()

    def register(self, client):
        self.clients.append(client)

    def unregister(self, client):
        self.clients.remove(client)

    def receive(self, msg, client):
        msgType, msgBody = msg.split(":")

        if msgType == "PLAY":
            self.spawnGame()

        elif msgType == "CHAT":
            self.broadcastChat(msgBody)

        elif msgType == "MOVE":
            code = int(msgBody)
            if code == 37: # LEFT
                self.pacman.nextMove = Directions.WEST
            elif code == 38: # UP
                self.pacman.nextMove = Directions.NORTH
            elif code == 39: # RIGHT
                self.pacman.nextMove = Directions.EAST
            elif code == 40: # DOWN
                self.pacman.nextMove = Directions.SOUTH

    def broadcast(self, gameState):
        for v in self.clients:
            v.sendMessage("GAME:" + str(gameState).encode('utf8'))

    def broadcastChat(self, msg):
        for v in self.clients:
            v.sendMessage("CHAT:" + msg.encode('utf8'))
        if self.game is not None:
          print >>self.log, self.gameStep, msg

    def broadcastEnd(self, win):
        for v in self.clients:
            v.sendMessage("END:" + ("win" if win else "lose"))

    # pacman stuff

    LAYOUTS = ["smallClassic",
               "mediumClassic",
               #"alleyCapture",
               "bigHunt",
               #"bigSafeSearch",
               #"contest01Capture",
               #"openSearch",
               #"bloxCapture"]
               ]

    def spawnGame(self):
        TIMEOUT = 30
        #LAYOUT = layout.getLayout('mediumClassic')
        layoutName = self.LAYOUTS[random.randint(0, len(self.LAYOUTS) - 1)]
        LAYOUT = layout.getLayout(layoutName)
        #LAYOUT = layout.getLayout(self.LAYOUTS[3])
        PACMAN = self.pacman # pacmanAgents.GreedyAgent()
        #GHOSTS = [ghostAgents.RandomGhost(i+1) for i in range(2)]
        GHOSTS = [ghostAgents.RandomGhost(1), ghostAgents.DirectionalGhost(2)]
        RULES = ClassicGameRules(TIMEOUT)
        DISPLAY = self
        self.game = RULES.newGame(LAYOUT, PACMAN, GHOSTS, DISPLAY)
        self.game.net_start()
        self.tick()
        print >>self.log, ">>>", self.gameStep, layoutName
        #gameThread = Thread(target = game.run)
        #gameThread.start()


    # graphics stuff

    def initialize(self, state):
        self.gameStep = 0
        self.update(state)

    def update(self, state):
        self.gameStep += 1
        fullTurn = self.gameStep % len(state.agentStates) == 0
        if fullTurn:
            self.broadcast(state)

    def finish(self):
        pass

if __name__ == '__main__':

    # server setup

    DEBUG = True
    ServerFactory = PacmanServerFactory
    factory = ServerFactory("ws://jacobandreas.net:9000",
                            debug=DEBUG,
                            debugCodePaths=DEBUG)

    factory.protocol = PacmanServerProtocol
    factory.setProtocolOptions(allowHixie76 = True)
    listenWS(factory)

    webdir = File(".")
    web = Site(webdir)
    reactor.listenTCP(8080, web)
    
    reactor.run()
