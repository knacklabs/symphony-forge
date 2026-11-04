"""Waiting records at the HTTP boundary."""

import json
from uuid import uuid4

import httpx
from conftest import call_notifications
from test_api import credentials, sign_up
from test_invites import invite


def test_a_person_sees_the_records_that_wait_for_them_with_a_count(
    client: httpx.Client,
) -> None:
    # Audit: this protects the list, count, recipient and organisation boundaries, resolution,
    # and transaction rollback through the running API and database. A missing scope, an
    # uncleared entry, or a service that ignores tx can expose or retain work. No existing test
    # covers notifications. The helper calls the real service in the app container; the route
    # and list are exercised over HTTP, with no test-only production seam.
    _, admin_csrf = sign_up(client)
    admin = client.get("/api/v1/auth/me")
    assert admin.status_code == 200, admin.text
    admin_id = admin.json()["data"]["id"]

    invited = credentials()
    token = invite(client, admin_csrf, invited["email"])
    with httpx.Client(base_url=client.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite", json={**invited, "token": token}
        )
        assert joined.status_code == 201, joined.text
        member_id = joined.json()["data"]["id"]

        with httpx.Client(base_url=client.base_url, timeout=15) as other_company:
            sign_up(other_company)
            other_account = other_company.get("/api/v1/auth/me")
            assert other_account.status_code == 200, other_account.text
            other_id = other_account.json()["data"]["id"]

            first_subject_id, second_subject_id = str(uuid4()), str(uuid4())
            assert (
                call_notifications(
                    f"""
                admin = OrganisationsService(db, HistoryService(db)).membership_for(
                    UUID({json.dumps(admin_id)})
                )
                if admin is None:
                    raise RuntimeError("The test admin has no organisation membership.")
                notifications = NotificationsService(db)
                notifications.notify(
                    admin,
                    UUID({json.dumps(member_id)}),
                    UUID({json.dumps(first_subject_id)}),
                    "project",
                    "First waiting record",
                )
                db.commit()
                notifications.notify(
                    admin,
                    UUID({json.dumps(member_id)}),
                    UUID({json.dumps(second_subject_id)}),
                    "project",
                    "Second waiting record",
                )
                db.commit()
                result = "created"
                """
                )
                == "created"
            )

            member_list = member.get("/api/v1/notifications")
            assert member_list.status_code == 200, member_list.text
            assert member_list.json()["data"]["count"] == 2
            assert [
                (item["subjectId"], item["subjectName"], item["message"])
                for item in member_list.json()["data"]["items"]
            ] == [
                (second_subject_id, "project", "Second waiting record"),
                (first_subject_id, "project", "First waiting record"),
            ]
            assert isinstance(
                member_list.json()["data"]["items"][0]["createdAtUtc"], str
            )
            admin_list = client.get("/api/v1/notifications")
            assert admin_list.status_code == 200, admin_list.text
            assert admin_list.json()["data"]["count"] == 0
            other_list = other_company.get("/api/v1/notifications")
            assert other_list.status_code == 200, other_list.text
            assert other_list.json()["data"]["count"] == 0

            with httpx.Client(base_url=client.base_url, timeout=15) as signed_out:
                refused = signed_out.get("/api/v1/notifications")
            assert refused.status_code == 401, refused.text
            assert refused.json()["error"]["code"] == "UNAUTHENTICATED"

            assert (
                call_notifications(
                    f"""
                other = OrganisationsService(db, HistoryService(db)).membership_for(
                    UUID({json.dumps(other_id)})
                )
                if other is None:
                    raise RuntimeError("The other test company has no membership.")
                NotificationsService(db).resolve(
                    other, UUID({json.dumps(second_subject_id)})
                )
                db.commit()
                result = "resolved"
                """
                )
                == "resolved"
            )
            still_waiting = member.get("/api/v1/notifications")
            assert still_waiting.status_code == 200, still_waiting.text
            assert still_waiting.json()["data"]["count"] == 2

            assert (
                call_notifications(
                    f"""
                admin = OrganisationsService(db, HistoryService(db)).membership_for(
                    UUID({json.dumps(admin_id)})
                )
                if admin is None:
                    raise RuntimeError("The test admin has no organisation membership.")
                NotificationsService(db).resolve(
                    admin, UUID({json.dumps(first_subject_id)})
                )
                db.commit()
                result = "resolved"
                """
                )
                == "resolved"
            )
            after_resolve = member.get("/api/v1/notifications")
            assert after_resolve.status_code == 200, after_resolve.text
            assert after_resolve.json()["data"]["count"] == 1
            assert [
                item["subjectId"] for item in after_resolve.json()["data"]["items"]
            ] == [second_subject_id]

            rolled_back_subject_id = str(uuid4())
            assert (
                call_notifications(
                    f"""
                admin = OrganisationsService(db, HistoryService(db)).membership_for(
                    UUID({json.dumps(admin_id)})
                )
                if admin is None:
                    raise RuntimeError("The test admin has no organisation membership.")
                notifications = NotificationsService(db)
                with session_factory() as tx:
                    try:
                        with tx.begin():
                            notifications.notify(
                                admin,
                                UUID({json.dumps(member_id)}),
                                UUID({json.dumps(rolled_back_subject_id)}),
                                "project",
                                "Rolled-back record",
                                tx=tx,
                            )
                            notifications.resolve(
                                admin, UUID({json.dumps(second_subject_id)}), tx=tx
                            )
                            raise RuntimeError("roll back notification changes")
                    except RuntimeError as error:
                        if str(error) != "roll back notification changes":
                            raise
                db.commit()
                result = "rolled back"
                """
                )
                == "rolled back"
            )
            after_rollback = member.get("/api/v1/notifications")
            assert after_rollback.status_code == 200, after_rollback.text
            assert after_rollback.json()["data"]["count"] == 1
            assert [
                (item["subjectId"], item["message"])
                for item in after_rollback.json()["data"]["items"]
            ] == [(second_subject_id, "Second waiting record")]
