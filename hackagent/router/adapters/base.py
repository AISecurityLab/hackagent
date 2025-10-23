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


from abc import ABC, abstractmethod
from typing import Any, Dict


class Agent(ABC):
    """
    Abstract Base Class for all agent implementations.
    It defines a common interface for the router to interact with various agents.
    """

    @abstractmethod
    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the agent.

        Args:
            id: A unique identifier for this specific agent instance or type.
            config: Configuration specific to this agent (e.g., API keys, model names).
        """
        self.id = id
        self.config = config
        pass

    @abstractmethod
    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming request and returns a standardized response.
        The response should be suitable for storage via the API and should ideally
        include enough information to reconstruct the interaction.

        Args:
            request_data: The data for the agent to process. This might include
                          the prompt, session information, user details, etc.

        Returns:
            A dictionary containing the standardized response. This could include:
            - 'raw_request': The original request sent to the underlying agent.
            - 'raw_response': The original response received from the underlying agent.
            - 'processed_response': The key information extracted/processed from the raw response.
            - 'status_code': If applicable, the HTTP status code of the interaction.
            - 'error_message': Any error message encountered.
            - 'metadata': Any other relevant metadata.
        """
        pass

    def get_identifier(self) -> str:
        """Returns the unique identifier for this agent instance or type."""
        return self.id
