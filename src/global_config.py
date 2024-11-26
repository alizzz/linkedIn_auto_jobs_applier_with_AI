import argparse
import os
import yaml

class GlobalConfigSingle:
    _instance = None  # Class-level instance
    def __init__(self):
        self.config = {}

    @staticmethod
    def create(default_config_path='data_folder/hawk_al.config'):

        def expand_placeholders(data:dict, delim='%') -> dict:
            """
            Recursively replace placeholders in the values of a dictionary
            with their corresponding values based on the keys.

            :param data: Dictionary with potential placeholders in the values
            :return: Updated dictionary with all placeholders replaced
            """
            import re

            def replace_value(value, data):
                """
                Replace all placeholders in a value recursively.
                """
                pattern = re.compile(rf'{delim}(\w+){delim}')  # Matches placeholders like %abc%
                while True:
                    matches = pattern.findall(value)
                    if not matches:
                        break
                    for key in matches:
                        if key in data:
                            # Replace the placeholder with its value
                            value = value.replace(f"{delim}{key}{delim}", data[key])
                        else:
                            # If the key is not found, keep the placeholder
                            raise KeyError(f"Key '{key}' not found in dictionary")
                return value

            # Update the dictionary with replaced values
            updated_data = {}

            for key, value in data.items():
                if isinstance(value, str) and delim in value:  # Only replace in string values
                    updated_data[key] = replace_value(value, data)
                else:
                    updated_data[key] = value  # Non-string values are left untouched

            return updated_data

        # Step 1: Create argument parser and parse initial arguments
        parser = argparse.ArgumentParser(description="Global Config Parser", conflict_handler='resolve')
        parser.add_argument("--cfg_plain_resume", type=str, default='data_folder/plain_text_resume_al.yaml',
                            help="Path to the YAML plain resume file")
        parser.add_argument("--cfg", type=str, default='data_folder/config_al_SF_run_apply.yaml',
                            help="Path to the YAML configuration file")
        parser.add_argument("--cfg_secrets", type=str, default='data_folder/secrets_al.yaml',
                            help="Path to the YAML configuration file")
        parser.add_argument("--cfg_hawk", type=str, default=default_config_path,
                            help="Path to the YAML configuration file")

        initial_args, unknown_args = parser.parse_known_args()

        #parser = create_argparser(default_config_path)

        # Step 2: Initialize the global config
        global_config = GlobalConfigSingle()

        # Step 3: Load YAML configuration from the --config parameter
        global_config.load_from_yaml(initial_args.cfg_plain_resume)
        global_config.load_from_yaml(initial_args.cfg_secrets)
        global_config.load_from_yaml(initial_args.cfg)
        global_config.load_from_yaml(initial_args.cfg_hawk)

        # Step 4: Dynamically add arguments from YAML to argparse
        for key, value in global_config.config.items():
            if not hasattr(parser, key):  # Avoid duplicates
                if isinstance(value, bool):
                    parser.add_argument(f"--{key}", action="store_true", help=f"Flag for {key}")
                else:
                    parser.add_argument(f"--{key}", type=type(value), default=value, help=f"Config parameter: {key}")

        parser.add_argument(f"--base_path", type = str, default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), help='Base path')

        # Step 5: Add unknown command-line arguments dynamically
        for i in range(0, len(unknown_args), 2):  # Process key-value pairs
            key = unknown_args[i].lstrip('-')
            value = unknown_args[i + 1] if i + 1 < len(unknown_args) else None
            parser.add_argument(f"--{key}", default=value, help=f"Dynamically added parameter {key}")

        # Step 6: Parse all arguments and merge them into global config
        final_args = parser.parse_args()
        global_config.merge_with_args(final_args)

        global_config.config = expand_placeholders(global_config.config)

        return global_config

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GlobalConfigSingle, cls).__new__(cls)
            cls._instance.config = {}
        return cls._instance

    def load_from_yaml(self, path):
        """Load configuration from a YAML file."""
        try:
            with open(path, "r") as file:
                self.config.update(yaml.safe_load(file))
        except Exception as e:
            raise ValueError(f"Failed to load configuration from {path}: {e}")

    def merge_with_args(self, args):
        """Merge command-line arguments into the configuration."""
        for key, value in vars(args).items():
            if value is not None:  # Override only if an argument was explicitly provided
                self.config[key] = value

    def __getattr__(self, item):
        """Allow attribute-style access to configuration values."""
        return self.config.get(item)

    def get(self, key, default=None):
        """Get a configuration value with a default fallback."""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value."""
        self.config[key] = value



if __name__ == "__main__":
    gc = GlobalConfigSingle.create()