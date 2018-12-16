class ECS():
    def __init__(self):
        self._entities = {} # entity_id : {component_type, component_instance}
        self._next_entity_id = 0
        
        self._systems = {} # system_id : system_instance
        self._next_system_id = 0

    def create_entity(self):
        """ Create an entity and return its entity_id. """
        self._entities[self._next_entity_id] = {}

        self._next_entity_id += 1
        return self._next_entity_id-1

    def delete_entity(self, entity_id):
        """ Delete en entity by its entity_id. """
        try:
            del self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

    def add_system(self, system_type, *args, **kwargs):
        """ Add a system and return its system_id. """
        system = system_type(*args, **kwargs)
        self._systems[self._next_system_id] = system

        self._next_system_id += 1
        return self._next_system_id-1

    def remove_system(self, system_id):
        """ Remove a system by its system_id. """

        try:
            del self._systems[system_id]
        except KeyError:
            raise KeyError("unknown system_id {}".format(system_id))

    def add_component(self, entity_id, component_instance):
        """ Add a component to an entity. """
        try:
            entity_components = self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

        component_type = component_instance.__class__
        if component_type not in entity_components.keys():
            entity_components[component_type] = []

        entity_components[component_type].append(component_instance)

    def add_components(self, entity_id, *component_instances):
        """ Add multiple component_instances to an entity. """
        try:
            entity_components = self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

        for component_instance in component_instances:
            component_type = component_instance.__class__
            if component_type not in entity_components.keys():
                entity_components[component_type] = []

            entity_components[component_type].append(component_instance)

    def remove_component(self, entity_id, component_type):
        """ Remove all components of component_type from an entity. """
        try:
            entity_components = self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

        try:
            del entity_components[component_type]
        except KeyError:
            raise KeyError("unknown component_type {}".format(component_type))

    def remove_components(self, entity_id, *component_types):
        """ Remove all components of component_types form an entity. """
        try:
            entity_components = self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

        for component_type in component_types:
            try:
                del entity_components[component_type]
            except KeyError:
                raise KeyError("unknown component_type {}".format(component_type))

    def get_component_all(self, entity_id, component_type):
        """ Get all components of component_type from an entity. """
        try:
            entity_components = self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

        try:
            return entity_components[component_type]
        except KeyError:
            raise KeyError("unknown component_type {}".format(component_type))

    def get_component(self, entity_id, component_type):
        """ Get the first component of component_type from an entity. """
        return self.get_component_all(entity_id, component_type)[0]

    def get_components_all(self, entity_id, *component_types):
        """ Get all components of multiple component_types from an entity. """
        try:
            entity_components = self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

        components = []
        for component_type in component_types:
            try:
                components.append(entity_components[component_type])
            except KeyError:
                raise KeyError("unknown component_type {}".format(component_type))

        return components

    def get_components(self, entity_id, *component_types):
        """ Get the first components of component_types from an entity. """
        return [c[0] for c in self.get_components_all(entity_id, *component_types)]

    def has_component(self, entity_id, component_type):
        """ Check if an entity has a component. """
        try:
            entity_components = self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

        return component_type in entity_components.keys()

    def has_components(self, entity_id, *component_types):
        """ Check if an entity has multiple components. """
        try:
            entity_components = self._entities[entity_id]
        except KeyError:
            raise KeyError("unknown entity_id {}".format(entity_id))

        return set(component_types).issubset(entity_component.keys())

    def iterate_entities(self, *component_types):
        """ Iterate entities. """
        component_types_set = set(component_types)
        for entity_id, entity_components in self._entities.items():
            if component_types_set.issubset(entity_components.keys()):
                yield entity_id

    def iterate_entities_components(self, *component_types):
        """ Iterate entities and their components. """
        for entity_id in self.iterate_entities(*component_types):
            components = self.get_components(entity_id, *component_types)
            yield (entity_id, components)

    def process(self, *args, **kwargs):
        for system_id, system_instance in self._systems.items():
            system_instance.process(self, *args, **kwargs)


class System():
    def __init__(self):
        pass

    def process(self, ecs, *args, **kwargs):
        raise NotImplementedError()

class Component():
    def __init__(self):
        pass

if __name__ == "__main__":
    pass
