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

    # A cursor holds the whole name, so a full-length name in any script must still page.
    long_names = ["项" * 119 + letter for letter in ("A", "B")]
    create_projects(client, csrf, [(name, "active") for name in long_names])
    by_long_name = "limit=1&sortBy=name&sortOrder=asc&search=%E9%A1%B9"
    long_first = list_projects(client, by_long_name)
    assert names(long_first) == [long_names[0]]
    long_next = list_projects(
        client, f"{by_long_name}&after={long_first['paging']['nextCursor']}"
    )
    assert names(long_next) == [long_names[1]]


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
    # Export CSV downloads what the list shows: the same search and filter.
    exported = client.get("/api/v1/projects/export?search=website&status=archived")
    assert exported.status_code == 200, exported.text
    assert "Website audit" in exported.text
    assert "Website redesign" not in exported.text
    assert "Mobile app" not in exported.text
    # The search text is literal: a % or _ does not match every name.
    assert names(listed("search=%25")) == []
    assert names(listed("search=_")) == []

    for query, field in (("status=gone", "status"), ("search=" + "a" * 201, "search")):
        refused = client.get(f"/api/v1/projects?{query}")
        assert refused.status_code == 400, refused.text
        fields = refused.json()["error"]["details"]["fieldErrors"]
        assert [error["field"] for error in fields] == [field]


FIRST_CHANGE = (
    "Name changed from Website redesign to Website relaunch; "
    "Status changed from active to archived"
)


def test_records_each_project_change_in_the_change_history(
    client: httpx.Client,
) -> None:
    # Audit: the twin of the React case. Each create, change and delete must write one
    # Change history row in the same commit, a replace that changes nothing writes none,
    # the changes route lists the newest 5 of this project only, and the organisation-wide
    # history names the project. Real HTTP and Postgres; no production test seam.
    owner, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    created = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Website redesign", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project = created.json()["data"]
    assert project["createdByEmail"] == project["modifiedByEmail"] == owner["email"]
    path = f"/api/v1/projects/{project['id']}"
    for _ in range(2):  # The second replace changes nothing and adds no row.
        replaced = client.put(
            path,
            headers=headers,
            json={"name": "Website relaunch", "status": "archived"},
        )
        assert replaced.status_code == 200, replaced.text

    changes = client.get(f"{path}/changes")
    assert changes.status_code == 200, changes.text
    assert [
        (entry["actorEmail"], entry["summary"]) for entry in changes.json()["data"]
    ] == [
        (owner["email"], FIRST_CHANGE),
        (owner["email"], "Created the project"),
    ]
    assert set(changes.json()["data"][0]) == {
        "id",
        "actorEmail",
        "summary",
        "createdAtUtc",
    }

    # The detail screen lists the newest 5 changes only.
    for name in ("Second", "Third", "Fourth", "Fifth"):
        renamed = client.put(
            path, headers=headers, json={"name": name, "status": "archived"}
        )
        assert renamed.status_code == 200, renamed.text
    recent = client.get(f"{path}/changes").json()["data"]
    assert [entry["summary"] for entry in recent] == [
        "Name changed from Fourth to Fifth",
        "Name changed from Third to Fourth",
        "Name changed from Second to Third",
        "Name changed from Website relaunch to Second",
        FIRST_CHANGE,
    ]

    deleted = client.delete(path, headers=headers)
    assert deleted.status_code == 200, deleted.text
    # The Change history screen names the project each change was made to.
    history = client.get("/api/v1/history").json()["data"]
    assert [entry["summary"] for entry in history] == [
        "Fifth: Deleted the project",
        "Fifth: Name changed from Fourth to Fifth",
        "Fourth: Name changed from Third to Fourth",
        "Third: Name changed from Second to Third",
        "Second: Name changed from Website relaunch to Second",
        f"Website relaunch: {FIRST_CHANGE}",
        "Website redesign: Created the project",
    ]
    exported = client.get("/api/v1/history/export")
    assert f",{owner['email']},Fifth: Deleted the project" in exported.text

    # A deleted project's changes, and another organisation's project's changes, are not found.
    assert client.get(f"{path}/changes").status_code == 404
    kept = client.post(
        "/api/v1/projects", headers=headers, json={"name": "Kept", "status": "active"}
    )
    assert kept.status_code == 201, kept.text
    with httpx.Client(base_url=client.base_url, timeout=15) as other:
        sign_up(other)
        refused = other.get(f"/api/v1/projects/{kept.json()['data']['id']}/changes")
        assert refused.status_code == 404, refused.text
        assert refused.json()["error"]["code"] == "PROJECT_NOT_FOUND"
