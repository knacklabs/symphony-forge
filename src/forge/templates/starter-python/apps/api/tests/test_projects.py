"""The projects list, its paging and its filters at the HTTP boundary.

Audit: these cases own the projects API contracts, the twins of the React starter's
projects suite: CRUD, keyset paging with next and previous cursors, search and the
status filter. All data enters through HTTP against the running app and database.
"""

from typing import Any

import httpx
from test_api import sign_up


def create_projects(
    client: httpx.Client, csrf: str, projects: list[tuple[str, str]]
) -> None:
    for name, status in projects:
        response = client.post(
            "/api/v1/projects",
            headers={"x-csrf-token": csrf},
            json={"name": name, "status": status},
        )
        assert response.status_code == 201, response.text


def list_projects(client: httpx.Client, query: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/projects?{query}")
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


def names(data: dict[str, Any]) -> list[str]:
    return [project["name"] for project in data["items"]]


def test_creates_lists_reads_updates_and_deletes_a_project(
    client: httpx.Client,
) -> None:
    _, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    created = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "First project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]
    listed = client.get("/api/v1/projects?limit=20&sortBy=name&sortOrder=asc")
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["items"] == [created.json()["data"]]
    assert listed.json()["data"]["paging"] == {
        "limit": 20,
        "nextCursor": None,
        "previousCursor": None,
        "total": 1,
        "totalCapped": False,
    }
    assert (
        client.get(f"/api/v1/projects/{project_id}").json()["data"]["id"] == project_id
    )
    updated = client.put(
        f"/api/v1/projects/{project_id}",
        headers=headers,
        json={"name": "Renamed project", "status": "archived"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "Renamed project"
    assert updated.json()["data"]["status"] == "archived"
    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"success": True, "data": None, "error": None}
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_rejects_a_whitespace_only_project_name(client: httpx.Client) -> None:
    _, csrf = sign_up(client)
    response = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": csrf},
        json={"name": "   ", "status": "active"},
    )
    assert response.status_code == 400, response.text
    assert any(
        field["field"] == "name"
        for field in response.json()["error"]["details"]["fieldErrors"]
    )


def test_requires_sign_in_and_csrf_before_project_changes(client: httpx.Client) -> None:
    response = client.get("/api/v1/projects")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    _, csrf = sign_up(client)
    project = {"name": "No token", "status": "active"}
    assert client.post("/api/v1/projects", json=project).status_code == 403
    response = client.post(
        "/api/v1/projects", json=project, headers={"x-csrf-token": csrf + "wrong"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_CHECK_FAILED"


def test_pages_projects_with_next_and_previous_cursors(client: httpx.Client) -> None:
    _, csrf = sign_up(client)
    create_projects(
        client,
        csrf,
        [(name, "active") for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo")],
    )

    # The default order is the last change, newest first.
    assert names(list_projects(client, "")) == [
        "Echo",
        "Delta",
        "Charlie",
        "Bravo",
        "Alpha",
    ]

    by_name = "limit=2&sortBy=name&sortOrder=asc"
    first = list_projects(client, by_name)
    assert names(first) == ["Alpha", "Bravo"]
    assert first["paging"]["previousCursor"] is None
    assert first["paging"]["total"] == 5
    assert first["paging"]["totalCapped"] is False
    second = list_projects(client, f"{by_name}&after={first['paging']['nextCursor']}")
    assert names(second) == ["Charlie", "Delta"]
    last = list_projects(client, f"{by_name}&after={second['paging']['nextCursor']}")
    assert names(last) == ["Echo"]
    assert last["paging"]["nextCursor"] is None

    back = list_projects(client, f"{by_name}&before={last['paging']['previousCursor']}")
    assert names(back) == ["Charlie", "Delta"]
    assert back["paging"]["nextCursor"] is not None
    start = list_projects(
        client, f"{by_name}&before={back['paging']['previousCursor']}"
    )
    assert names(start) == ["Alpha", "Bravo"]
    assert start["paging"]["previousCursor"] is None

    descending = list_projects(client, "limit=2&sortBy=name&sortOrder=desc")
    following = list_projects(
        client,
        "limit=2&sortBy=name&sortOrder=desc"
        f"&after={descending['paging']['nextCursor']}",
    )
    assert names(following) == ["Charlie", "Bravo"]

    # A cursor of another sort, both cursors, or an unreadable cursor gets a field error.
    cursor = first["paging"]["nextCursor"]
    for query, field in (
        (f"sortBy=status&after={cursor}", "after"),
        (f"after={cursor}&before={cursor}", "before"),
        ("after=not+a+cursor", "after"),
        ("before=bm90LWpzb24", "before"),
    ):
        refused = client.get(f"/api/v1/projects?{query}")
        assert refused.status_code == 400, refused.text
        assert refused.json()["error"]["code"] == "VALIDATION_ERROR"
        fields = refused.json()["error"]["details"]["fieldErrors"]
        assert [error["field"] for error in fields] == [field]


def test_filters_projects_by_search_and_filters(client: httpx.Client) -> None:
    _, csrf = sign_up(client)
    create_projects(
        client,
        csrf,
        [
            ("Website redesign", "active"),
            ("Website audit", "archived"),
            ("Mobile app", "active"),
        ],
    )

    def listed(query: str) -> dict[str, Any]:
        return list_projects(client, f"sortBy=name&sortOrder=asc&{query}")

    assert names(listed("search=WEBSITE")) == ["Website audit", "Website redesign"]
    assert names(listed("search=%20site%20")) == ["Website audit", "Website redesign"]
    assert names(listed("status=active")) == ["Mobile app", "Website redesign"]
    both = listed("search=website&status=archived")
    assert names(both) == ["Website audit"]
    assert both["paging"]["total"] == 1
    # The search text is literal: a % or _ does not match every name.
    assert names(listed("search=%25")) == []
    assert names(listed("search=_")) == []

    for query, field in (("status=gone", "status"), ("search=" + "a" * 201, "search")):
        refused = client.get(f"/api/v1/projects?{query}")
        assert refused.status_code == 400, refused.text
        fields = refused.json()["error"]["details"]["fieldErrors"]
        assert [error["field"] for error in fields] == [field]
