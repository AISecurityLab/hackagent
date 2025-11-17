# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import abc
from typing import Any, Dict


class BaseAttack(abc.ABC):
    """
    Abstract base class for black-box attacks against language models.

    This class provides the foundational interface and structure that all
    attack implementations must follow. It handles common initialization
    patterns and enforces a consistent API across different attack types.

    Attributes:
        config: A dictionary containing configuration settings for the attack.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the attack with configuration parameters.

        Args:
            config: A dictionary containing configuration settings for the attack.
                Must include all required parameters for the specific attack type.

        Raises:
            TypeError: If config is not a dictionary.
            ValueError: If required configuration parameters are missing or invalid.
        """
        self.config = config
        self._validate_config()
        self._setup()

    def _validate_config(self):
        """
        Validates the provided configuration.

        This method performs basic validation of the configuration dictionary.
        Subclasses should override this method to enforce specific configuration
        requirements for their attack type.

        Raises:
            TypeError: If the configuration is not a dictionary.
            ValueError: If required configuration parameters are missing or invalid.
        """
        if not isinstance(self.config, dict):
            raise TypeError("Configuration must be a dictionary.")
        # Add more specific validation in subclasses as needed
        pass

    def _setup(self):
        """
        Performs any necessary setup based on the configuration.

        This method is called after configuration validation and provides
        an opportunity for subclasses to perform initialization tasks such
        as loading models, creating output directories, or setting up logging.

        Subclasses can override this for specific setup tasks.
        """
        # Add setup logic in subclasses (e.g., logging, directories)
        pass

    @abc.abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """
        Executes the attack logic.

        This abstract method must be implemented by all attack subclasses
        to define their specific attack methodology and execution flow.

        Args:
            **kwargs: Attack-specific arguments that vary by implementation.
                Common examples include:
                - input_prompts: List of prompts to test
                - goals: List of target goals for the attack
                - dataset: Input dataset for evaluation
                - target_model: The model to attack

        Returns:
            Attack-specific results. The format varies by implementation but
            typically includes:
            - adversarial_examples: Generated adversarial inputs
            - success_metrics: Attack success rates and statistics
            - detailed_results: Comprehensive result data (e.g., pandas DataFrame)
            - attack_report: Summary of attack performance

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.
            RuntimeError: If the attack execution fails due to configuration
                or runtime errors.
        """
        pass
