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

from unittest import mock

import pytest

from hackagent.client import AuthenticatedClient
from hackagent.models.paginated_prompt_list import PaginatedPromptList
from hackagent.models.prompt import Prompt
from hackagent.vulnerabilities.prompts import DEFAULT_PROMPTS, get_or_create_prompt


class TestDefaultPrompts:
    """Test suite for default prompts configuration."""

    def test_default_prompts_structure(self):
        """Test that DEFAULT_PROMPTS has expected keys and structure."""
        assert "sql_injection" in DEFAULT_PROMPTS
        assert "xss_basic" in DEFAULT_PROMPTS
        assert "command_injection_linux" in DEFAULT_PROMPTS

        for category, (name, text) in DEFAULT_PROMPTS.items():
            assert isinstance(category, str)
            assert isinstance(name, str)
            assert isinstance(text, str)
            assert len(name) > 0
            assert len(text) > 0


class TestGetOrCreatePrompt:
    """Test suite for get_or_create_prompt function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock AuthenticatedClient."""
        return mock.MagicMock(spec=AuthenticatedClient)

    @pytest.fixture
    def sample_prompt(self):
        """Create a sample Prompt object."""
        return Prompt.from_dict(
            {
                "id": "12345678-1234-5678-1234-567812345678",
                "name": "Test Prompt",
                "prompt_text": "Test text",
                "category": "test_category",
                "organization": "87654321-4321-8765-4321-876543218765",
                "organization_detail": {
                    "id": "87654321-4321-8765-4321-876543218765",
                    "name": "Test Org",
                },
                "owner_detail": None,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            }
        )

    @mock.patch("hackagent.vulnerabilities.prompts.prompt_list")
    def test_get_existing_prompt(self, mock_prompt_list, mock_client, sample_prompt):
        """Test that existing prompt is returned when found."""
        # Setup mock response for existing prompt
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.parsed = PaginatedPromptList.from_dict(
            {
                "count": 1,
                "results": [sample_prompt.to_dict()],
            }
        )
        mock_prompt_list.sync_detailed.return_value = mock_response

        result = get_or_create_prompt(
            client=mock_client,
            name="Test Prompt",
            text="Test text",
            category="test_category",
            organization_id=1,
        )

        assert str(result.id) == "12345678-1234-5678-1234-567812345678"
        assert result.name == "Test Prompt"
        mock_prompt_list.sync_detailed.assert_called_once_with(client=mock_client)

    @mock.patch("hackagent.vulnerabilities.prompts.prompt_create")
    @mock.patch("hackagent.vulnerabilities.prompts.prompt_list")
    def test_create_new_prompt_when_not_found(
        self, mock_prompt_list, mock_prompt_create, mock_client, sample_prompt
    ):
        """Test that new prompt is created when not found."""
        # Setup mock response for empty list
        mock_list_response = mock.MagicMock()
        mock_list_response.status_code = 200
        mock_list_response.parsed = PaginatedPromptList.from_dict(
            {
                "count": 0,
                "results": [],
            }
        )
        mock_prompt_list.sync_detailed.return_value = mock_list_response

        # Setup mock response for create
        mock_create_response = mock.MagicMock()
        mock_create_response.status_code = 201
        mock_create_response.parsed = sample_prompt
        mock_prompt_create.sync_detailed.return_value = mock_create_response

        result = get_or_create_prompt(
            client=mock_client,
            name="Test Prompt",
            text="Test text",
            category="test_category",
            organization_id=1,
        )

        assert str(result.id) == "12345678-1234-5678-1234-567812345678"
        assert result.name == "Test Prompt"
        mock_prompt_create.sync_detailed.assert_called_once()

    @mock.patch("hackagent.vulnerabilities.prompts.prompt_create")
    @mock.patch("hackagent.vulnerabilities.prompts.prompt_list")
    def test_create_prompt_with_extra_tags(
        self, mock_prompt_list, mock_prompt_create, mock_client, sample_prompt
    ):
        """Test that extra tags are properly included when creating prompt."""
        # Setup mock response for empty list
        mock_list_response = mock.MagicMock()
        mock_list_response.status_code = 200
        mock_list_response.parsed = PaginatedPromptList.from_dict(
            {
                "count": 0,
                "results": [],
            }
        )
        mock_prompt_list.sync_detailed.return_value = mock_list_response

        # Setup mock response for create
        mock_create_response = mock.MagicMock()
        mock_create_response.status_code = 201
        mock_create_response.parsed = sample_prompt
        mock_prompt_create.sync_detailed.return_value = mock_create_response

        result = get_or_create_prompt(
            client=mock_client,
            name="Test Prompt",
            text="Test text",
            category="test_category",
            organization_id=1,
            extra_tags=["custom_tag", "another_tag"],
        )

        # Verify the prompt was created
        assert str(result.id) == "12345678-1234-5678-1234-567812345678"
        call_args = mock_prompt_create.sync_detailed.call_args
        created_body = call_args.kwargs["body"]

        # Verify tags include both utility_created and extra tags
        assert "utility_created" in created_body.tags
        assert "custom_tag" in created_body.tags
        assert "another_tag" in created_body.tags

    @mock.patch("hackagent.vulnerabilities.prompts.logger")
    @mock.patch("hackagent.vulnerabilities.prompts.prompt_create")
    @mock.patch("hackagent.vulnerabilities.prompts.prompt_list")
    def test_create_prompt_failure_raises_error(
        self, mock_prompt_list, mock_prompt_create, mock_logger, mock_client
    ):
        """Test that RuntimeError is raised when prompt creation fails."""
        # Setup mock response for empty list
        mock_list_response = mock.MagicMock()
        mock_list_response.status_code = 200
        mock_list_response.parsed = PaginatedPromptList.from_dict(
            {
                "count": 0,
                "results": [],
            }
        )
        mock_prompt_list.sync_detailed.return_value = mock_list_response

        # Setup mock response for failed create
        mock_create_response = mock.MagicMock()
        mock_create_response.status_code = 400
        mock_create_response.parsed = None
        mock_create_response.content = b"Bad request error"
        mock_prompt_create.sync_detailed.return_value = mock_create_response

        with pytest.raises(RuntimeError, match="Failed to create prompt"):
            get_or_create_prompt(
                client=mock_client,
                name="Test Prompt",
                text="Test text",
                category="test_category",
                organization_id=1,
            )

    @mock.patch("hackagent.vulnerabilities.prompts.prompt_create")
    @mock.patch("hackagent.vulnerabilities.prompts.prompt_list")
    def test_create_prompt_with_custom_evaluation_criteria(
        self, mock_prompt_list, mock_prompt_create, mock_client, sample_prompt
    ):
        """Test that custom evaluation criteria is passed correctly."""
        # Setup mock response for empty list
        mock_list_response = mock.MagicMock()
        mock_list_response.status_code = 200
        mock_list_response.parsed = PaginatedPromptList.from_dict(
            {
                "count": 0,
                "results": [],
            }
        )
        mock_prompt_list.sync_detailed.return_value = mock_list_response

        # Setup mock response for create
        mock_create_response = mock.MagicMock()
        mock_create_response.status_code = 201
        mock_create_response.parsed = sample_prompt
        mock_prompt_create.sync_detailed.return_value = mock_create_response

        custom_criteria = "Custom evaluation logic here"
        result = get_or_create_prompt(
            client=mock_client,
            name="Test Prompt",
            text="Test text",
            category="test_category",
            organization_id=1,
            evaluation_criteria=custom_criteria,
        )

        # Verify the prompt was created
        assert str(result.id) == "12345678-1234-5678-1234-567812345678"
        call_args = mock_prompt_create.sync_detailed.call_args
        created_body = call_args.kwargs["body"]
        assert created_body.evaluation_criteria == custom_criteria
