import sys, time
from mecs import Scene, CommandBuffer
from server import SimpleServer

# https://www.python.org/dev/peps/pep-0257/
def trim(docstring):
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = 9999#sys.maxint
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < 9999:#sys.maxint:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)

def log(message):
    print(f"[{time.strftime('%d %b %Y %H:%M:%S', time.gmtime())}] {message}")

def maplink(scene, source, direction, destination):
    """Link a source location to a destination location via a direction."""

    reversemap = {"north": "south", "south": "north",
                  "west": "east", "east": "west",
                  "northeast": "southwest", "southwest": "northeast",
                  "southeast": "northwest", "northwest": "southeast",
                  "up": "down", "down": "up"}

    assert direction in reversemap, "unknown direction"
    assert scene.has(source, Map), "the source room is missing a Map component"
    assert scene.has(destination, Map), "the destination room is missing a Map component"

    scene.get(source, Map)[direction] = destination
    scene.get(destination, Map)[reversemap[direction]] = source

def move(scene, entity, container):
    """Move an entity from its location container to another container."""

    assert scene.has(container, Container), "the container is missing a Container component"

    if scene.has(entity, Location):
        location = scene.get(entity, Location)
        assert scene.has(location, Container), "the location of the entity is missing a Container component"

        scene.get(location, Container).remove(entity)

    scene.set(entity, Location(container))
    scene.get(container, Container).append(entity)

def enum(lst, connector="and"):
    """Enumerate entity names."""

    lst = list(lst)
    if not lst: return ""
    if len(lst) == 1: return lst[0]
    return f"{', '.join(lst[:-1])} {connector} {lst[-1]}"

def findByName(scene, name, container):
    """Return the first entity id that has a matching name component."""

    return next(iter(eid for eid in container if scene.has(eid, Name) and scene.get(eid, Name).match(name)), None)

class Player():
    def __init__(self, clientid):
        self.clientid = clientid
        self.input, self.output = [], []

class Name():
    def __init__(self, name, article=None):
        self.name, self.article = name, article

    def format(self, definite=False, capitalize=False):
        article = ""
        if self.article:
            article = "the " if definite else f"{self.article} "

        string = f"{article}{self.name}"
        if capitalize: string = string[0].upper() + string[1:]

        return string

    def match(self, string):
        parts = string.lower().split()
        if parts[0] in ("the", "a", "an"):
            parts.pop(0)
        return " ".join(parts) == self.name.lower()

class Description(str):
    """Description that can be seen when looking at/examining things."""
    pass

class Inscription(str):
    """An inscription that can be read."""
    pass

class Location(int):
    """An entity that can be moved into different container entities."""
    pass

class Container(list):
    """An entity that can contain other enitites."""
    pass

class Map(dict):
    """Map directions to locations."""
    pass

class Environment(str):
    """Mark an entity as belonging to the environment with an optional message
    that will be displayed alongside the destcription of the location.
    """
    pass

### --- ACTIONS --- ###

class Actor():
    def __init__(self):
        self.actions = []

class LookAction():
    def __init__(self, entity):
        self.entity = entity

    def perform(self, scene, actor, **kwargs):
        entity = self.entity

        message = []
        if scene.has(entity, Map):
            message.extend((scene.get(entity, Name).format(), "\n\n"))
            message.extend((scene.get(entity, Description), " "))
            for env in (env for env in scene.get(entity, Container) if scene.has(env, Environment)):
                message.extend((scene.get(env, Environment), " "))
            message.append("\n\n")
            if scene.get(entity, Container):
                x = "is" if len(scene.get(entity, Container)) == 1 else "are"
                message.extend((f"Here {x} ", enum([scene.get(eid, Name).format(definite=False) for eid in scene.get(entity, Container) if not scene.has(eid, Environment) and scene.has(eid, Name)], connector="and"), ".\n\n"))
            message.extend(("Exits: ", *scene.get(entity, Map).keys()))
            scene.new(Event(actor), ActionEvent(actor), LookActionEvent(entity), ActionSuccessEvent(),
                      MessageEvent(*message))
        else:
            if scene.has(entity, Description):
                message.extend((scene.get(entity, Description), " "))

            if scene.has(entity, Container):
                names = [scene.get(eid, Name).format(definite=False) for eid in scene.get(entity, Container) if scene.has(eid, Name)]
                if not names: names = ["nothing"]
                message.extend(("It contains ", enum(names, connector="and"), "."))

            if not message:
                message.extend(("There is nothing special about ", entity, "."))

            scene.new(Event(actor), ActionEvent(actor), LookActionEvent(entity), ActionSuccessEvent(),
                      MessageEvent(*message), ObservableEvent(actor, " looks at ", entity, "."))

class TakeAction():
    def __init__(self, entity):
        self.entity = entity

    def perform(self, scene, actor, **kwargs):
        entity = self.entity

        if scene.has(entity, Environment):
            scene.new(Event(actor), ActionEvent(actor), TakeActionEvent(entity), ActionFailureEvent(),
                      MessageEvent("You cannot do that."))
            return

        if scene.get(entity, Location) == actor:
            scene.new(Event(actor), ActionEvent(actor), TakeActionEvent(entity), ActionFailureEvent(),
                      MessageEvent("You already have ", entity, "."))
            return False, []

        if scene.get(entity, Location) != scene.get(actor, Location):
            scene.new(Event(actor), ActionEvent(actor), TakeActionEvent(entity), ActionFailureEvent(),
                      MessageEvent("You fail to take ", entity, " because it is not at the same location as you are."))
            return

        #if scene.has(entityLocation, Openable): pass

        move(scene, entity, actor)

        scene.new(Event(actor), ActionEvent(actor), TakeActionEvent(entity), ActionSuccessEvent(),
                  MessageEvent("You take ", entity, "."), ObservableEvent(actor, " takes ", entity, "."))
        return False, []

class DropAction():
    def __init__(self, entity):
        self.entity = entity

    def perform(self, scene, actor, **kwargs):
        entity = self.entity

        if scene.get(entity, Location) != actor:
            scene.new(Event(actor), ActionEvent(actor), DropActionEvent(entity), ActionFailureEvent(),
                      MessageEvent("You have to get hold of ", entity, " before you can drop it."))
            return False, []

        move(scene, entity, scene.get(actor, Location))

        scene.new(Event(actor), ActionEvent(actor), DropActionEvent(entity), ActionSuccessEvent(),
                  MessageEvent("You drop ", entity, "."), ObservableEvent(actor, " drops ", entity, "."))
        return False, []

class SayAction():
    def __init__(self, phrase):
        self.phrase = phrase

    def perform(self, scene, actor, **kwargs):
        phrase = self.phrase

        scene.new(Event(actor), ActionEvent(actor), SayActionEvent(phrase), ActionSuccessEvent(),
                  ObservableEvent(actor, f" says '{phrase}'"))
        return False, []

class ActorSystem():
    def onUpdate(self, scene, deltaTime, **kwargs):
            for eid, (actor,) in scene.select(Actor):
                while actor.actions:
                    action = actor.actions.pop(0)
                    result = action.perform(scene, eid, deltaTime=deltaTime)
                    if result is None: # failed
                        actor.actions = []
                        break
                    wait, alternatives = result
                    actor.actions = alternatives + actor.actions
                    if wait: break

### --- EVENTS --- ###

class Event():
    def __init__(self, sender):
        self.sender = sender

class MessageEvent():
    def __init__(self, *parts):
        self.parts = parts

class ObservableEvent():
    def __init__(self, *parts):
        self.parts = parts

class ActionEvent():
    def __init__(self, actor):
        self.actor = actor

class ActionSuccessEvent(): pass
class ActionFailureEvent(): pass

class LookActionEvent():
    def __init__(self, entity):
        self.entity = entity

class SayActionEvent():
    def __init__(self, phrase):
        self.phrase = phrase

class TakeActionEvent():
    def __init__(self, entity):
        self.entity = entity

class DropActionEvent():
    def __init__(self, entity):
        self.entity = entity

class ObserveEventSystem():
    def onUpdate(self, scene, **kwargs):
        for eid, (event, observable) in scene.select(Event, ObservableEvent):
            sender, parts = event.sender, observable.parts

            if not parts:
                continue

            message = []
            for part in parts:
                if isinstance(part, int):
                    name = scene.get(part, Name).format(definite=True)
                    message.append(name)
                else:
                    message.append(part)
            message = "".join(message)

            observers = [eid for eid in scene.get(scene.get(sender, Location), Container) if scene.has(eid, Player) and eid != sender]
            for observer in observers:
                scene.get(observer, Player).output.append(message)

class MessageEventSystem():
    def onUpdate(self, scene, **kwargs):
        for eid, (event, msg) in scene.select(Event, MessageEvent):
            sender, parts = event.sender, msg.parts

            if not parts or not scene.has(sender, Player):
                continue

            message = []
            for part in parts:
                if isinstance(part, int):
                    name = scene.get(part, Name).format(definite=True)
                    message.append(name)
                else:
                    message.append(part)

            scene.get(sender, Player).output.append("".join(message))

class CleanUpEventSystem():
    def onUpdate(self, scene, **kwargs):
        with CommandBuffer(scene) as buffer:
            for eid, _ in scene.select(Event):
                buffer.free(eid)

### --- NETWORKING --- ###

class NetworkingSystem():
    def __init__(self, startLocation):
        self.startLocation = startLocation

    def _createPlayer(self, scene, clientid):
        player = scene.new(
            Player(clientid),
            Name(f"Player({clientid})"),
            Description("This is you."),
            Actor(),
            Container(),
        )
        move(scene, player, self.startLocation)

    def onStart(self, scene, ip, port, **kwargs):
        self.server = SimpleServer(ip, port)
        log(f"server listening on {ip}:{port}")

    def onUpdate(self, scene, **kwargs):
        self.server.update()
        connects = [] # clientid
        disconnects = [] # clientid
        messages = {} # clientid : list(str)
        for event in self.server._events: # HACK
            if event.etype == SimpleServer.ETYPE.NEWPLAYER:
                clientid, = event.content
                connects.append(clientid)
                log(f"connected: {clientid}")
            elif event.etype == SimpleServer.ETYPE.PLAYERLEFT:
                clientid, = event.content
                disconnects.append(clientid)
                log(f"disconnected: {clientid}")
            elif event.etype == SimpleServer.ETYPE.MESSAGE:
                clientid, message = event.content
                if not clientid in messages:
                    messages[clientid] = []
                messages[clientid].append(message)
                log(f"message from {clientid}: {message}")
        self.server._events.clear()

        for clientid in connects:
            self._createPlayer(scene, clientid)

        with CommandBuffer(scene) as buffer:
            for eid, (player,) in scene.select(Player):
                clientid = player.clientid
                if clientid in disconnects:
                    buffer.free(eid)
                    continue

                if clientid in messages:
                    player.input.extend(messages[clientid])

                if player.output:
                    for msg in player.output:
                        self.server.send_message(clientid, msg)
                    player.output.clear()

class CommandSystem():
    def __init__(self):
        self._COMMANDS = {
            "help": self.cmdHelp,
            "look": self.cmdLook, "l": self.cmdLook,
            #"examine": self.cmdExamine, "x": self.cmdExamine,
            #"go": self.cmdGo,
            #"north": self.cmdNorth, "n": self.cmdNorth,
            #"south": self.cmdSouth, "s": self.cmdSouth,
            #"west": self.cmdWest, "w": self.cmdWest,
            #"east": self.cmdEast, "e": self.cmdEast,
            #"northwest": self.cmdNorthwest, "nw": self.cmdNorthwest,
            #"northeast": self.cmdNortheast, "ne": self.cmdNortheast,
            #"southwest": self.cmdSouthwest, "sw": self.cmdSouthwest,
            #"southeast": self.cmdSoutheast, "se": self.cmdSoutheast,
            #"up": self.cmdUp, "u": self.cmdUp,
            #"down": self.cmdDown, "d": self.cmdDown,
            #"inventory": self.cmdInventory, "i": self.cmdInventory,
            "take": self.cmdTake,
            "drop": self.cmdDrop,
            #"read": self.cmdRead,
            "say": self.cmdSay
        }

    def _normalize(self, string):
        if string is None: return None
        return string.strip().lower()

    def _normalizeObjects(self, string):
        return [self._normalize(o) for o in string.replace(" and ", ", ").split(", ")]

    def cmdHelp(self, scene, player, verb, directObjects, prepositionObjectsPairs, phrase):
        """Get help.

        help
          Print a list of commands.
        help <command>
          Print the documentation of a specific command.
        """

        if len(directObjects) == 0:
            scene.new(
                Event(player),
                MessageEvent(
                    "Get further help with 'help <command>'.\n",
                    "The following commands are available:\n  ",
                    "\n  ".join(self._COMMANDS.keys())
                )
            )
        elif len(directObjects) == 1:
            cmd, = directObjects
            if cmd not in self._COMMANDS:
                scene.new(Event(player), MessageEvent("There is no such command. Try 'help' for a list of commands."))
                return

            scene.new(Event(player), MessageEvent(trim(self._COMMANDS[cmd].__doc__)))
        else:
            scene.new(Event(player), MessageEvent("Invalid syntax."))

    def cmdLook(self, scene, player, verb, objects, prepositions, phrase):
        """Look at your surroundings.

        look
        look <thing> [in <container>]
        """
        #assert not directObjects and not phrase, "Invalid syntax."

        if len(objects) == 0: # look
            entity = scene.get(player, Location)
        elif len(objects) == 1: # look <thing> [in <container>]
            scope = scene.get(scene.get(player, Location), Container) + scene.get(player, Container)

            if "in" not in prepositions:
                entity = findByName(scene, objects[0], scope)
                if not entity:
                    scene.new(Event(player), MessageEvent("You can see no such thing."))
                    return
            else:
                containers = prepositions["in"]
                if len(containers) > 1:
                    scene.new(Event(player), MessageEvent("You can only look into one thing at once."))
                    return
                container = findByName(scene, containers[0], scope)

                if not scene.has(container, Container):
                    scene.new(Event(player), MessageEvent(container, " is not something you can look into."))
                    return

                scope = scene.get(container, Container)

                entity = findByName(scene, objects[0], scope)
                if not entity:
                    scene.new(Event(player), MessageEvent("You can see no such thing in ", container, "."))
                    return
        else:
            scene.new(Event(player), MessageEvent("You can only look at one thing at once."))

        scene.get(player, Actor).actions.append(LookAction(entity))

    def cmdSay(self, scene, player, verb, directObjects, prepositionObjectsPairs, phrase):
        """Say something.

        say: <phrase>
          Say something out loud so everyone at your location can hear it.
        """

        assert not directObjects and not prepositionObjectsPairs, "Invalid syntax."

        scene.get(player, Actor).actions.append(SayAction(phrase))

    def cmdTake(self, scene, player, verb, directObjects, prepositionObjectsPairs, phrase):
        """Add something to your inventory.

        take <thing>
          Take a thing that is at the same location as your are.
        take <thing> from <container>
          Take a thing from a container that is at the same location as your or in your inventory.
        """

        assert len(directObjects) <= 1 and not prepositionObjectsPairs and not phrase, "Invalid syntax."

        if len(directObjects) == 0:
            scene.new(Event(player), MessageEvent("You have to name a thing to take."))
            return

        directObject = directObjects[0]

        entity = findByName(scene, directObject, scene.get(scene.get(player, Location), Container) + scene.get(player, Container))
        if not entity:
            scene.new(Event(player), MessageEvent("You see no such thing."))
            return

        scene.get(player, Actor).actions.append(TakeAction(entity))

    def cmdDrop(self, scene, player, verb, directObjects, prepositionObjectsPairs, phrase):
        """Remove things from your inventory.

        drop <thing>
          Drop something from your inventory to your location.
        drop <thing> into <container>
          Drop something from your inventory into a container.
        """

        assert len(directObjects) == 1 and not prepositionObjectsPairs and not phrase, "Invalid syntax."

        directObject = directObjects[0]

        entity = findByName(scene, directObject, scene.get(scene.get(player, Location), Container) + scene.get(player, Container))
        if not entity:
            scene.new(Event(player), MessageEvent("You see no such thing."))
            return

        scene.get(player, Actor).actions.append(DropAction(entity))

    def parse(self, command):
        """Parse player input and return
        verb                     the (longest matching) verb
        directObjects            a list of direct objects, can be empty
        prepositionObjectsPairs  a list of tuples (preposition, indirect object), can be empty
        phrase                   a phrase or None
        """

        verbs = self._COMMANDS.keys()
        prepositions = ["in", "on", "into", "from", "with", "using", "to", "at"]

        # default values
        verb, directObjects, prepositionObjectsPairs, phrase = None, [], {}, None

        # extract phrase
        colonCount = command.count(":")
        if colonCount > 0:
            if colonCount > 1:
                raise ValueError(f"too many colons: {colonCount}")

            command, phrase = command.split(":")

        # find verb
        command = self._normalize(command)
        for v in sorted(verbs, key=lambda v: len(v), reverse=True):
            if command.startswith(v):
                verb = v
                break
        if not verb:
            raise ValueError("missing verb")
        command = self._normalize(command[len(verb):])

        # find objects
        directObject = None
        p = None # current preposition
        o = []   # current object (in parts)
        for w in command.split():
            if w in prepositions:
                if not p:
                    if o:
                        # collect the direct object
                        directObject = " ".join(o)
                        o = []
                else:
                    # collect preposition
                    if not o:
                        raise ValueError(f"no indirect object for preposition: {p}")
                    prepositionObjectsPairs[p] = " ".join(o)
                    o = []

                # begin new preposition
                p = w
            else:
                # collect the object
                o.append(w)
        if p:
            # collect the remaining preposition
            if not o:
                raise ValueError(f"no indirect object for preposition: {p}")
            prepositionObjectsPairs[p] = " ".join(o)
        elif o:
            # collect the remaining direct object
            directObject = " ".join(o)

        # normalize
        verb = self._normalize(verb)
        directObjects = self._normalizeObjects(directObject) if directObject else []
        prepositionObjectsPairs = {self._normalize(k): self._normalizeObjects(v) for k, v in prepositionObjectsPairs.items()}
        phrase = phrase.strip() if phrase else None # special case

        return verb, directObjects, prepositionObjectsPairs, phrase

    def onUpdate(self, scene, **kwargs):
        for eid, (player, actor) in scene.select(Player, Actor):
            while player.input:
                command = player.input.pop(0)

                try:
                    verb, directObjects, prepositionObjectsPairs, phrase = self.parse(command)
                except ValueError as e:
                    scene.new(Event(eid), MessageEvent("You input could not be parsed."))
                    log(f"error parsing '{command}': {e}")
                    continue

                if verb not in self._COMMANDS:
                    scene.new(Event(eid), MessageEvent("There is no such verb."))
                    log(f"unknown verb in '{command}': {verb}")
                    continue

                try:
                    self._COMMANDS[verb](scene, eid, verb, directObjects, prepositionObjectsPairs, phrase)
                    log(f"command executed for player {player.clientid}: {command}")
                except AssertionError as e:
                    scene.new(Event(eid), MessageEvent("Error: ", str(e)))
                    log(f"error while executing command '{command}' for player {player.clientid}: {e}")

def setup(scene):
    livingroom = scene.new(
        Name("The Living Room"),
        Description("This is the living room."),
        Container((
            scene.new(
                Name("plant", article="a"),
                Description("It has seen better days."),
                Environment("Over in the corner there is a plant.")
            ),
            scene.new(
                Name("picture", article="a"),
                Description("A boat on a lake."),
                Environment("There is a picture on the wall.")
            ),
            scene.new(
                Name("window", article="a"),
                Description("The sun is shining outside."),
                Environment("On the west side of the room there is a window.")
            ),
            scene.new(
                Name("rug", article="a"),
                Description("An antique oriental rug."),
                Environment("There is a rug on the floor.")
            )
        )),
        Map()
    )

    garden = scene.new(
        Name("The Garden"),
        Description("This is the garden."),
        Container((
            scene.new(
                Name("tree"),
                Description("It's an apple tree."),
                Environment("In the middle of the garden is a large tree.")
            ),
        )),
        Map()
    )

    maplink(scene, livingroom, "west", garden)

    book = scene.new(
        Name("book", article="a"),
        Description("The book is titled 'Der Zauberberg' by Thomas Mann."),
        Inscription("Die Geschichte Hans Castorps, die wir erzahlen wollen, - nicht um seinetwillen (denn der Leser wird einen einfachen, wenn auch ansprechenden jungen Mann in ihm kennenlemen), sondem um der Geschichte willen, die uns in hohem Grade erzahlenswert scheint (wobei zu Hans Castorps Gunsten denn doch erinnert werden sollte, dass es seine Geschichte ist, und dass nicht jedem jede Geschichte passiert): diese Gescruchte ist sehr lange her, sie ist sozusagen schon ganz mit historischem Edelrost uberzogen und unbedingt in der Zeitform der tiefsten Vergangenheit vorzutragen.")
    )
    move(scene, book, livingroom)

    box = scene.new(
        Name("box", article="a"),
        Description("A box."),
        Container()
    )
    move(scene, box, livingroom)

    dice = scene.new(
        Name("die", article="a"),
        Description("A small die.")
    )
    move(scene, dice, box)

    marble = scene.new(
        Name("marble", article="a"),
        Description("A white marble.")
    )
    move(scene, marble, livingroom)

    shovel = scene.new(
        Name("shovel", article="a"),
        Description("A small chrome shovel.")
    )
    move(scene, shovel, garden)

    return livingroom

def main(prog, args):
    ip, port = args

    scene = Scene()

    startLocation = setup(scene)

    systems = [
        CommandSystem(),
        ActorSystem(),

        MessageEventSystem(),
        ObserveEventSystem(),
        CleanUpEventSystem(),

        NetworkingSystem(startLocation)
    ]

    startSystems = [s for s in systems if hasattr(s, 'onStart')]
    updateSystems = [s for s in systems if hasattr(s, 'onUpdate')]
    stopSystems = [s for s in systems if hasattr(s, 'onStop')]

    try:
        scene.start(*startSystems, ip=ip, port=int(port))

        timer = time.time()
        while True:
            now = time.time()
            scene.update(*updateSystems, deltaTime=(now - timer))
            timer = now
    except KeyboardInterrupt:
        pass
    finally:
        scene.stop(*stopSystems)

if __name__ == "__main__":
    main(sys.argv[0], sys.argv[1:])
