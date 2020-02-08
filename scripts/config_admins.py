import toml


def main():
    config = toml.load('../data/config.toml')
    if not type(config['base']['adminuser']) == int:
        print('Admin user entry has already been changed.')
        return

    config['base']['adminuser'] = [config['base']['adminuser']]
    with open("../data/config.toml", "w") as config_file:
            toml.dump(config, config_file)
    print("Admin user entry has successfully been changed to a list.")

if __name__ == "__main__":
    main()