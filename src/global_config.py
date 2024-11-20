import argparse
import pdfkit
import re
import os
import yaml

class GlobalConfig:
    _instance = None  # Class-level instance
    def __init__(self):
        self.config = {}

    @staticmethod
    def create(default_config_path='html2pdf.config'):
        # Step 1: Create argument parser and parse initial arguments
        parser = argparse.ArgumentParser(description="Global Config Parser")
        parser.add_argument("--config", type=str, default=default_config_path,
                            help="Path to the YAML configuration file")

        initial_args, unknown_args = parser.parse_known_args()

        #parser = create_argparser(default_config_path)

        # Step 2: Initialize the global config
        global_config = GlobalConfig()

        # Step 3: Load YAML configuration from the --config parameter
        global_config.load_from_yaml(initial_args.config)

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
        return global_config

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GlobalConfig, cls).__new__(cls)
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
