import yaml


def test_yaml_load():
    def construct_scalar(loader, node):
        return node.value

    def construct_sequence(loader: yaml.FullLoader, node):
        seq = []
        for item in node.value:
            if isinstance(item, yaml.ScalarNode):
                seq.append(item.value)
            if isinstance(item, yaml.SequenceNode):
                seq.append(construct_sequence(loader, item))
            if isinstance(item, yaml.MappingNode):
                # let the yaml parser handle the mapping
                seq.append(loader.construct_object(item))
        return seq

    def construct_obj(loader, node):
        # get name parameter
        obj = {}
        for name, value in node.value:
            # print(name, value)
            if isinstance(value, yaml.ScalarNode):
                obj[name.value] = construct_scalar(loader, value)
            if isinstance(value, yaml.SequenceNode):
                obj[name.value] = construct_sequence(loader, value)
        return obj

    def construct_include(loader, node):
        obj = construct_obj(loader, node)
        # value = obj["value"]
        # load another yaml file
        with open(obj["file"], "r") as ymlfile:
            obj = yaml.load(ymlfile, Loader=yaml.FullLoader)

        # in the future we should set the initial value of the object/graph with the
        # specified values
        # obj.set_value(value)
        return obj

    # add custom tags for parsing
    yaml.FullLoader.add_constructor(
        "!Directory", lambda loader, node: construct_obj(loader, node)
    )
    yaml.FullLoader.add_constructor(
        "!Variable", lambda loader, node: construct_obj(loader, node)
    )
    yaml.FullLoader.add_constructor(
        "!Method", lambda loader, node: construct_obj(loader, node)
    )
    yaml.FullLoader.add_constructor(
        "!Include", lambda loader, node: construct_include(loader, node)
    )

    with open("template/data_model.yml", "r") as ymlfile:
        machine_data_model = yaml.load(ymlfile, Loader=yaml.FullLoader)
    print(machine_data_model)


def main():
    test_yaml_load()


if __name__ == "__main__":
    main()
