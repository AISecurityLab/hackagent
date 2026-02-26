# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from hackagent.api.organization import (
    organization_create,
    organization_destroy,
    organization_list,
    organization_me_retrieve,
    organization_partial_update,
    organization_retrieve,
    organization_update,
)
from hackagent.client import AuthenticatedClient
from hackagent.errors import UnexpectedStatus
from hackagent.api.models import Organization
from hackagent.api.models import OrganizationRequest
from hackagent.api.models import PaginatedOrganizationList
from hackagent.api.models import PatchedOrganizationRequest
from hackagent.types import UNSET


@pytest.fixture
def authenticated_client() -> AuthenticatedClient:
    return AuthenticatedClient(base_url="http://localhost:8000", token="test_token")


@pytest.fixture
def organization_request_body() -> OrganizationRequest:
    body = OrganizationRequest(name="Test Org")
    body.additional_properties["company"] = "Test Inc."
    body.additional_properties["website"] = "http://test.org"
    return body


TEST_ORG_REAL_UUID_STR = "123e4567-e89b-12d3-a456-426614174000"  # A valid UUID string


@pytest.fixture
def organization_response_data() -> dict:
    return {
        "id": TEST_ORG_REAL_UUID_STR,  # Use a valid UUID string
        "name": "Test Org",
        "owner": {
            "id": "user_abc",
            "username": "owner_user",
            "picture": None,
            "credits": 0,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
        "credits": "1000.00",  # Changed from int to string as per model: credits_ (str)
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "credits_last_updated": "2024-01-01T00:00:00Z",  # Added missing field
        "company": "Test Inc.",
        "website": "http://test.org",
        "github_url": None,
    }


def test_create_get_kwargs(organization_request_body: OrganizationRequest):
    # Testing request body encoding.
    kwargs = organization_create._get_kwargs(body=organization_request_body)
    assert kwargs["method"] == "post"
    assert kwargs["url"] == "/organization"
    assert "data" in kwargs or "json" in kwargs


def test_create_parse_response_success(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    http_response = Response(201, json=organization_response_data)
    parsed = organization_create._parse_response(
        client=authenticated_client, response=http_response
    )
    assert isinstance(parsed, Organization)
    assert parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)
    assert parsed.name == "Test Org"
    assert parsed.additional_properties["owner"]["id"] == "user_abc"


def test_create_parse_response_unexpected_status_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(500, content=b"Server Error")
    authenticated_client.raise_on_unexpected_status = True
    with pytest.raises(UnexpectedStatus) as excinfo:
        organization_create._parse_response(
            client=authenticated_client, response=http_response
        )
    assert excinfo.value.status_code == 500
    assert excinfo.value.content == b"Server Error"


def test_create_parse_response_unexpected_status_no_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(403, content=b"Forbidden")
    authenticated_client.raise_on_unexpected_status = False
    parsed = organization_create._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None


def test_create_sync_detailed_success(
    authenticated_client: AuthenticatedClient,
    organization_request_body: OrganizationRequest,
    organization_response_data: dict,
):
    mock_http_response = Response(201, json=organization_response_data)
    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = organization_create.sync_detailed(
            client=authenticated_client, body=organization_request_body
        )

    expected_kwargs = organization_create._get_kwargs(body=organization_request_body)
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 201
    assert isinstance(response.parsed, Organization)
    assert response.parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)


def test_create_sync_success(
    authenticated_client: AuthenticatedClient,
    organization_request_body: OrganizationRequest,
):
    mock_parsed_response = MagicMock(spec=Organization)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    with patch(
        "hackagent.api.organization.organization_create.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = organization_create.sync(
            client=authenticated_client, body=organization_request_body
        )

    mock_sync_detailed.assert_called_once_with(
        client=authenticated_client, body=organization_request_body
    )
    assert parsed == mock_parsed_response


@pytest.mark.asyncio
async def test_create_asyncio_detailed_success(
    authenticated_client: AuthenticatedClient,
    organization_request_body: OrganizationRequest,
    organization_response_data: dict,
):
    mock_http_response = Response(201, json=organization_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await organization_create.asyncio_detailed(
            client=authenticated_client, body=organization_request_body
        )

    expected_kwargs = organization_create._get_kwargs(body=organization_request_body)
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 201
    assert isinstance(response.parsed, Organization)
    assert response.parsed.name == "Test Org"


@pytest.mark.asyncio
async def test_create_asyncio_success(
    authenticated_client: AuthenticatedClient,
    organization_request_body: OrganizationRequest,
):
    mock_parsed_response = MagicMock(spec=Organization)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    async def mock_asyncio_detailed_func(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.organization.organization_create.asyncio_detailed",
        new=mock_asyncio_detailed_func,
    ) as _:
        parsed = await organization_create.asyncio(
            client=authenticated_client, body=organization_request_body
        )

    assert parsed == mock_parsed_response


# --- Tests for organization_destroy ---

TEST_ORG_UUID = uuid.uuid4()


def test_destroy_get_kwargs():
    kwargs = organization_destroy._get_kwargs(id=TEST_ORG_UUID)
    assert kwargs["method"] == "delete"
    assert kwargs["url"] == f"/organization/{TEST_ORG_UUID}"


def test_destroy_parse_response_success(authenticated_client: AuthenticatedClient):
    http_response = Response(204)  # No content for successful delete
    parsed = organization_destroy._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None


def test_destroy_parse_response_unexpected_status_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(404, content=b"Not Found")
    authenticated_client.raise_on_unexpected_status = True
    with pytest.raises(UnexpectedStatus) as excinfo:
        organization_destroy._parse_response(
            client=authenticated_client, response=http_response
        )
    assert excinfo.value.status_code == 404
    assert excinfo.value.content == b"Not Found"


def test_destroy_parse_response_unexpected_status_no_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(401, content=b"Unauthorized")
    authenticated_client.raise_on_unexpected_status = False
    parsed = organization_destroy._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None  # Should still be None as per _parse_response logic


def test_destroy_sync_detailed_success(authenticated_client: AuthenticatedClient):
    mock_http_response = Response(204)
    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = organization_destroy.sync_detailed(
            client=authenticated_client, id=TEST_ORG_UUID
        )

    expected_kwargs = organization_destroy._get_kwargs(id=TEST_ORG_UUID)
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 204
    assert response.parsed is None


@pytest.mark.asyncio
async def test_destroy_asyncio_detailed_success(
    authenticated_client: AuthenticatedClient,
):
    mock_http_response = Response(204)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await organization_destroy.asyncio_detailed(
            client=authenticated_client, id=TEST_ORG_UUID
        )

    expected_kwargs = organization_destroy._get_kwargs(id=TEST_ORG_UUID)
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 204
    assert response.parsed is None


# --- Tests for organization_list ---


@pytest.fixture
def paginated_organization_list_response_data(organization_response_data: dict) -> dict:
    return {
        "count": 1,
        "next": "http://localhost:8000/api/organization?page=2",
        "previous": None,
        "results": [organization_response_data],
    }


def test_list_get_kwargs():
    kwargs = organization_list._get_kwargs(page=1)
    assert kwargs["method"] == "get"
    assert kwargs["url"] == "/organization"
    assert kwargs["params"]["page"] == 1

    kwargs_no_page = organization_list._get_kwargs()
    assert "page" not in kwargs_no_page["params"]


def test_list_parse_response_success(
    authenticated_client: AuthenticatedClient,
    paginated_organization_list_response_data: dict,
):
    http_response = Response(200, json=paginated_organization_list_response_data)
    parsed = organization_list._parse_response(
        client=authenticated_client, response=http_response
    )
    assert isinstance(parsed, PaginatedOrganizationList)
    assert parsed.count == 1
    assert str(parsed.next) == "http://localhost:8000/api/organization?page=2"
    assert len(parsed.results) == 1
    assert parsed.results[0].id == uuid.UUID(TEST_ORG_REAL_UUID_STR)


def test_list_parse_response_unexpected_status_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(401, content=b"Unauthorized")
    authenticated_client.raise_on_unexpected_status = True
    with pytest.raises(UnexpectedStatus) as excinfo:
        organization_list._parse_response(
            client=authenticated_client, response=http_response
        )
    assert excinfo.value.status_code == 401
    assert excinfo.value.content == b"Unauthorized"


def test_list_parse_response_unexpected_status_no_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(403, content=b"Forbidden")
    authenticated_client.raise_on_unexpected_status = False
    parsed = organization_list._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None


def test_list_sync_detailed_success(
    authenticated_client: AuthenticatedClient,
    paginated_organization_list_response_data: dict,
):
    mock_http_response = Response(200, json=paginated_organization_list_response_data)
    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = organization_list.sync_detailed(client=authenticated_client, page=1)

    expected_kwargs = organization_list._get_kwargs(page=1)
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, PaginatedOrganizationList)
    assert response.parsed.count == 1


def test_list_sync_success(authenticated_client: AuthenticatedClient):
    mock_parsed_response = MagicMock(spec=PaginatedOrganizationList)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    with patch(
        "hackagent.api.organization.organization_list.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = organization_list.sync(client=authenticated_client, page=1)

    mock_sync_detailed.assert_called_once_with(client=authenticated_client, page=1)
    assert parsed == mock_parsed_response


@pytest.mark.asyncio
async def test_list_asyncio_detailed_success(
    authenticated_client: AuthenticatedClient,
    paginated_organization_list_response_data: dict,
):
    mock_http_response = Response(200, json=paginated_organization_list_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await organization_list.asyncio_detailed(
            client=authenticated_client, page=1
        )

    expected_kwargs = organization_list._get_kwargs(page=1)
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, PaginatedOrganizationList)
    assert len(response.parsed.results) == 1


@pytest.mark.asyncio
async def test_list_asyncio_success(authenticated_client: AuthenticatedClient):
    mock_parsed_response = MagicMock(spec=PaginatedOrganizationList)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_parsed_response

    async def mock_asyncio_detailed_func(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.organization.organization_list.asyncio_detailed",
        new=mock_asyncio_detailed_func,
    ) as _:
        parsed = await organization_list.asyncio(client=authenticated_client, page=1)

    assert parsed == mock_parsed_response


# --- Tests for organization_me_retrieve ---


def test_me_retrieve_get_kwargs():
    kwargs = organization_me_retrieve._get_kwargs()
    assert kwargs["method"] == "get"
    assert kwargs["url"] == "/organization/me"


def test_me_retrieve_parse_response_success(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    # Re-use organization_response_data fixture for this
    http_response = Response(200, json=organization_response_data)
    parsed = organization_me_retrieve._parse_response(
        client=authenticated_client, response=http_response
    )
    assert isinstance(parsed, Organization)
    assert parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)
    assert parsed.name == "Test Org"


def test_me_retrieve_parse_response_unexpected_status_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(404, content=b"Not Found")
    authenticated_client.raise_on_unexpected_status = True
    with pytest.raises(UnexpectedStatus) as excinfo:
        organization_me_retrieve._parse_response(
            client=authenticated_client, response=http_response
        )
    assert excinfo.value.status_code == 404
    assert excinfo.value.content == b"Not Found"


def test_me_retrieve_parse_response_unexpected_status_no_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(401, content=b"Unauthorized")
    authenticated_client.raise_on_unexpected_status = False
    parsed = organization_me_retrieve._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None


def test_me_retrieve_sync_detailed_success(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    mock_http_response = Response(200, json=organization_response_data)
    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = organization_me_retrieve.sync_detailed(client=authenticated_client)

    expected_kwargs = organization_me_retrieve._get_kwargs()
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, Organization)
    assert response.parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)


def test_me_retrieve_sync_success(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    # For sync, we need to mock sync_detailed to return a response with a parsed attribute
    mock_organization = Organization.model_validate(organization_response_data)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_organization

    with patch(
        "hackagent.api.organization.organization_me_retrieve.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = organization_me_retrieve.sync(client=authenticated_client)

    mock_sync_detailed.assert_called_once_with(client=authenticated_client)
    assert parsed == mock_organization
    assert parsed.name == "Test Org"


@pytest.mark.asyncio
async def test_me_retrieve_asyncio_detailed_success(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    mock_http_response = Response(200, json=organization_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await organization_me_retrieve.asyncio_detailed(
            client=authenticated_client
        )

    expected_kwargs = organization_me_retrieve._get_kwargs()
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, Organization)
    assert response.parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)


@pytest.mark.asyncio
async def test_me_retrieve_asyncio_success(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    mock_organization = Organization.model_validate(organization_response_data)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_organization

    async def mock_asyncio_detailed_func(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.organization.organization_me_retrieve.asyncio_detailed",
        new=mock_asyncio_detailed_func,
    ) as _:
        parsed = await organization_me_retrieve.asyncio(client=authenticated_client)

    assert parsed == mock_organization
    assert parsed.additional_properties["company"] == "Test Inc."


# --- Tests for organization_partial_update ---


@pytest.fixture
def patched_organization_request_body() -> PatchedOrganizationRequest:
    body = PatchedOrganizationRequest(name="Updated Test Org")
    body.additional_properties["website"] = "http://updated.org"
    return body


@pytest.fixture
def updated_organization_response_data(organization_response_data: dict) -> dict:
    # Simulate an update to the original data
    updated_data = organization_response_data.copy()
    updated_data["name"] = "Updated Test Org"
    updated_data["website"] = "http://updated.org"
    updated_data["updated_at"] = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1)
    ).isoformat()
    updated_data["credits_last_updated"] = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1)
    ).isoformat()  # Ensure this is also updated or present
    return updated_data


def test_partial_update_get_kwargs(
    patched_organization_request_body: PatchedOrganizationRequest,
):
    kwargs = organization_partial_update._get_kwargs(
        id=TEST_ORG_UUID, body=patched_organization_request_body
    )
    assert kwargs["method"] == "patch"
    assert kwargs["url"] == f"/organization/{TEST_ORG_UUID}"
    assert "data" in kwargs or "json" in kwargs
    assert "application/x-www-form-urlencoded" in kwargs["headers"]["Content-Type"]


def test_partial_update_parse_response_success(
    authenticated_client: AuthenticatedClient, updated_organization_response_data: dict
):
    http_response = Response(200, json=updated_organization_response_data)
    parsed = organization_partial_update._parse_response(
        client=authenticated_client, response=http_response
    )
    assert isinstance(parsed, Organization)
    assert parsed.id == uuid.UUID(updated_organization_response_data["id"])
    assert parsed.name == "Updated Test Org"
    assert parsed.additional_properties["website"] == "http://updated.org"


def test_partial_update_parse_response_unexpected_status_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(400, content=b"Bad Request")
    authenticated_client.raise_on_unexpected_status = True
    with pytest.raises(UnexpectedStatus) as excinfo:
        organization_partial_update._parse_response(
            client=authenticated_client, response=http_response
        )
    assert excinfo.value.status_code == 400
    assert excinfo.value.content == b"Bad Request"


def test_partial_update_parse_response_unexpected_status_no_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(404, content=b"Not Found")
    authenticated_client.raise_on_unexpected_status = False
    parsed = organization_partial_update._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None


def test_partial_update_sync_detailed_success(
    authenticated_client: AuthenticatedClient,
    patched_organization_request_body: PatchedOrganizationRequest,
    updated_organization_response_data: dict,
):
    mock_http_response = Response(200, json=updated_organization_response_data)
    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = organization_partial_update.sync_detailed(
            client=authenticated_client,
            id=TEST_ORG_UUID,
            body=patched_organization_request_body,
        )

    expected_kwargs = organization_partial_update._get_kwargs(
        id=TEST_ORG_UUID, body=patched_organization_request_body
    )
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, Organization)
    assert response.parsed.name == "Updated Test Org"


def test_partial_update_sync_success(
    authenticated_client: AuthenticatedClient,
    patched_organization_request_body: PatchedOrganizationRequest,
    updated_organization_response_data: dict,
):
    mock_organization = Organization.model_validate(updated_organization_response_data)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_organization

    with patch(
        "hackagent.api.organization.organization_partial_update.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = organization_partial_update.sync(
            client=authenticated_client,
            id=TEST_ORG_UUID,
            body=patched_organization_request_body,
        )

    mock_sync_detailed.assert_called_once_with(
        client=authenticated_client,
        id=TEST_ORG_UUID,
        body=patched_organization_request_body,
    )
    assert parsed == mock_organization
    assert parsed.additional_properties["website"] == "http://updated.org"


@pytest.mark.asyncio
async def test_partial_update_asyncio_detailed_success(
    authenticated_client: AuthenticatedClient,
    patched_organization_request_body: PatchedOrganizationRequest,
    updated_organization_response_data: dict,
):
    mock_http_response = Response(200, json=updated_organization_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await organization_partial_update.asyncio_detailed(
            client=authenticated_client,
            id=TEST_ORG_UUID,
            body=patched_organization_request_body,
        )

    expected_kwargs = organization_partial_update._get_kwargs(
        id=TEST_ORG_UUID, body=patched_organization_request_body
    )
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, Organization)
    assert response.parsed.name == "Updated Test Org"
    assert response.parsed.additional_properties["website"] == "http://updated.org"


@pytest.mark.asyncio
async def test_partial_update_asyncio_success(
    authenticated_client: AuthenticatedClient,
    patched_organization_request_body: PatchedOrganizationRequest,
    updated_organization_response_data: dict,
):
    mock_organization = Organization.model_validate(updated_organization_response_data)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_organization

    async def mock_asyncio_detailed_func(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.organization.organization_partial_update.asyncio_detailed",
        new=mock_asyncio_detailed_func,
    ) as _:
        parsed = await organization_partial_update.asyncio(
            client=authenticated_client,
            id=TEST_ORG_UUID,
            body=patched_organization_request_body,
        )

    assert parsed == mock_organization
    assert parsed.additional_properties["website"] == "http://updated.org"


# --- Tests for organization_retrieve ---


def test_retrieve_get_kwargs_specific_org():
    kwargs = organization_retrieve._get_kwargs(id=TEST_ORG_UUID)
    assert kwargs["method"] == "get"
    assert kwargs["url"] == f"/organization/{TEST_ORG_UUID}"


def test_retrieve_parse_response_success_specific_org(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    http_response = Response(200, json=organization_response_data)
    parsed = organization_retrieve._parse_response(
        client=authenticated_client, response=http_response
    )
    assert isinstance(parsed, Organization)
    assert parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)
    assert parsed.name == "Test Org"


def test_retrieve_parse_response_unexpected_status_raise_specific_org(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(404, content=b"Not Found")
    authenticated_client.raise_on_unexpected_status = True
    with pytest.raises(UnexpectedStatus) as excinfo:
        organization_retrieve._parse_response(
            client=authenticated_client, response=http_response
        )
    assert excinfo.value.status_code == 404
    assert excinfo.value.content == b"Not Found"


def test_retrieve_parse_response_unexpected_status_no_raise_specific_org(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(403, content=b"Forbidden")
    authenticated_client.raise_on_unexpected_status = False
    parsed = organization_retrieve._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None


def test_retrieve_sync_detailed_success_specific_org(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    mock_http_response = Response(200, json=organization_response_data)
    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = organization_retrieve.sync_detailed(
            client=authenticated_client, id=TEST_ORG_UUID
        )

    expected_kwargs = organization_retrieve._get_kwargs(id=TEST_ORG_UUID)
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, Organization)
    assert response.parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)


def test_retrieve_sync_success_specific_org(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    mock_organization = Organization.model_validate(organization_response_data)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_organization

    with patch(
        "hackagent.api.organization.organization_retrieve.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = organization_retrieve.sync(
            client=authenticated_client, id=TEST_ORG_UUID
        )

    mock_sync_detailed.assert_called_once_with(
        client=authenticated_client, id=TEST_ORG_UUID
    )
    assert parsed == mock_organization
    assert parsed.name == "Test Org"


@pytest.mark.asyncio
async def test_retrieve_asyncio_detailed_success_specific_org(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    mock_http_response = Response(200, json=organization_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await organization_retrieve.asyncio_detailed(
            client=authenticated_client, id=TEST_ORG_UUID
        )

    expected_kwargs = organization_retrieve._get_kwargs(id=TEST_ORG_UUID)
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, Organization)
    assert response.parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)
    assert response.parsed.name == "Test Org"


@pytest.mark.asyncio
async def test_retrieve_asyncio_success_specific_org(
    authenticated_client: AuthenticatedClient, organization_response_data: dict
):
    mock_organization = Organization.model_validate(organization_response_data)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_organization

    async def mock_asyncio_detailed_func(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.organization.organization_retrieve.asyncio_detailed",
        new=mock_asyncio_detailed_func,
    ) as _:
        parsed = await organization_retrieve.asyncio(
            client=authenticated_client, id=TEST_ORG_UUID
        )

    assert parsed == mock_organization
    assert parsed.name == "Test Org"


# --- Tests for organization_update ---


@pytest.fixture
def full_updated_organization_response_data(
    organization_request_body: OrganizationRequest, organization_response_data: dict
) -> dict:
    updated_data = organization_response_data.copy()
    updated_data["name"] = organization_request_body.name
    updated_data["company"] = organization_request_body.additional_properties.get(
        "company"
    )
    updated_data["website"] = organization_request_body.additional_properties.get(
        "website"
    )
    requested_github_url = organization_request_body.additional_properties.get(
        "github_url", UNSET
    )
    updated_data["github_url"] = (
        None if requested_github_url is UNSET else requested_github_url
    )
    current_time = datetime.datetime.now(datetime.timezone.utc)
    updated_data["updated_at"] = (
        current_time + datetime.timedelta(seconds=2)
    ).isoformat()
    updated_data["credits_last_updated"] = (
        current_time + datetime.timedelta(seconds=2)
    ).isoformat()  # Add/update this field
    # Ensure 'credits' field is present, matching what Organization model expects (string)
    if "credits" not in updated_data:
        updated_data["credits"] = (
            "1000.00"  # Default or carry over, ensure it's a string
        )
    return updated_data


def test_update_get_kwargs(organization_request_body: OrganizationRequest):
    kwargs = organization_update._get_kwargs(
        id=TEST_ORG_UUID, body=organization_request_body
    )
    assert kwargs["method"] == "put"
    assert kwargs["url"] == f"/organization/{TEST_ORG_UUID}"
    assert "data" in kwargs or "json" in kwargs


def test_update_parse_response_success(
    authenticated_client: AuthenticatedClient,
    full_updated_organization_response_data: dict,
):
    http_response = Response(200, json=full_updated_organization_response_data)
    parsed = organization_update._parse_response(
        client=authenticated_client, response=http_response
    )
    assert isinstance(parsed, Organization)
    assert parsed.id == uuid.UUID(TEST_ORG_REAL_UUID_STR)
    assert parsed.name == "Test Org"
    assert parsed.additional_properties["company"] == "Test Inc."
    assert parsed.additional_properties["website"] == "http://test.org"


def test_update_parse_response_unexpected_status_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(400, content=b"Invalid Data")
    authenticated_client.raise_on_unexpected_status = True
    with pytest.raises(UnexpectedStatus) as excinfo:
        organization_update._parse_response(
            client=authenticated_client, response=http_response
        )
    assert excinfo.value.status_code == 400
    assert excinfo.value.content == b"Invalid Data"


def test_update_parse_response_unexpected_status_no_raise(
    authenticated_client: AuthenticatedClient,
):
    http_response = Response(500, content=b"Server Error")
    authenticated_client.raise_on_unexpected_status = False
    parsed = organization_update._parse_response(
        client=authenticated_client, response=http_response
    )
    assert parsed is None


def test_update_sync_detailed_success(
    authenticated_client: AuthenticatedClient,
    organization_request_body: OrganizationRequest,
    full_updated_organization_response_data: dict,
):
    mock_http_response = Response(200, json=full_updated_organization_response_data)
    with patch.object(
        authenticated_client.get_httpx_client(),
        "request",
        return_value=mock_http_response,
    ) as mock_request:
        response = organization_update.sync_detailed(
            client=authenticated_client,
            id=TEST_ORG_UUID,
            body=organization_request_body,
        )

    expected_kwargs = organization_update._get_kwargs(
        id=TEST_ORG_UUID, body=organization_request_body
    )
    mock_request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, Organization)
    assert response.parsed.name == "Test Org"


def test_update_sync_success(
    authenticated_client: AuthenticatedClient,
    organization_request_body: OrganizationRequest,
    full_updated_organization_response_data: dict,
):
    mock_organization = Organization.model_validate(full_updated_organization_response_data)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_organization

    with patch(
        "hackagent.api.organization.organization_update.sync_detailed",
        return_value=mock_detailed_response,
    ) as mock_sync_detailed:
        parsed = organization_update.sync(
            client=authenticated_client,
            id=TEST_ORG_UUID,
            body=organization_request_body,
        )

    mock_sync_detailed.assert_called_once_with(
        client=authenticated_client, id=TEST_ORG_UUID, body=organization_request_body
    )
    assert parsed == mock_organization
    assert parsed.additional_properties["company"] == "Test Inc."


@pytest.mark.asyncio
async def test_update_asyncio_detailed_success(
    authenticated_client: AuthenticatedClient,
    organization_request_body: OrganizationRequest,
    full_updated_organization_response_data: dict,
):
    mock_http_response = Response(200, json=full_updated_organization_response_data)
    mock_async_httpx_client = AsyncMock()
    mock_async_httpx_client.request = AsyncMock(return_value=mock_http_response)

    with patch.object(
        AuthenticatedClient,
        "get_async_httpx_client",
        autospec=True,
        return_value=mock_async_httpx_client,
    ) as mock_get_client_method:
        response = await organization_update.asyncio_detailed(
            client=authenticated_client,
            id=TEST_ORG_UUID,
            body=organization_request_body,
        )

    expected_kwargs = organization_update._get_kwargs(
        id=TEST_ORG_UUID, body=organization_request_body
    )
    mock_get_client_method.assert_called_once_with(authenticated_client)
    mock_async_httpx_client.request.assert_called_once_with(**expected_kwargs)
    assert response.status_code == 200
    assert isinstance(response.parsed, Organization)
    assert response.parsed.name == "Test Org"


@pytest.mark.asyncio
async def test_update_asyncio_success(
    authenticated_client: AuthenticatedClient,
    organization_request_body: OrganizationRequest,
    full_updated_organization_response_data: dict,
):
    mock_organization = Organization.model_validate(full_updated_organization_response_data)
    mock_detailed_response = MagicMock()
    mock_detailed_response.parsed = mock_organization

    async def mock_asyncio_detailed_func(*args, **kwargs):
        return mock_detailed_response

    with patch(
        "hackagent.api.organization.organization_update.asyncio_detailed",
        new=mock_asyncio_detailed_func,
    ) as _:
        parsed = await organization_update.asyncio(
            client=authenticated_client,
            id=TEST_ORG_UUID,
            body=organization_request_body,
        )

    assert parsed == mock_organization
    assert parsed.additional_properties["company"] == "Test Inc."
