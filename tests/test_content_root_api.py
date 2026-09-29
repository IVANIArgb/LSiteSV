"""Смена папки контента и обзор каталогов для супер-админа."""


def test_browse_forbidden_for_plain_admin(client, mock_kerberos_and_ad, sample_admin, auth_headers_admin):
    resp = client.get("/api/admin/content-root/browse", headers=auth_headers_admin)
    assert resp.status_code == 403


def test_browse_lists_folder_for_super_admin(
    client, mock_kerberos_and_ad, sample_admin, db_session, auth_headers_admin, tmp_path
):
    sample_admin.role = "super_admin"
    db_session.commit()
    nested = tmp_path / "lessons"
    nested.mkdir()
    resp = client.get(
        "/api/admin/content-root/browse",
        query_string={"path": str(tmp_path)},
        headers=auth_headers_admin,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    names = [row["name"] for row in data.get("entries") or []]
    assert "lessons" in names
    assert data.get("current")
