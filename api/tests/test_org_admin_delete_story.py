from app.models.story import Story
from app.models.organization import Organization


def _make_test_org(db):
    org = Organization(id="org-test", name="Test Org", slug="test-org")
    db.add(org)
    db.commit()
    return org


class TestDeleteStory:
    def test_org_admin_can_delete_any_story(self, client, db, org_admin, org_admin_header, reporter):
        _make_test_org(db)
        story = Story(id="story-pub", reporter_id=reporter.id, organization_id="org-test",
                      headline="Published", paragraphs=[], status="published")
        db.add(story)
        db.commit()
        resp = client.delete(f"/admin/stories/{story.id}", headers=org_admin_header)
        assert resp.status_code == 204
        # Soft delete — story still exists but has deleted_at set
        db.expire_all()
        deleted = db.query(Story).filter(Story.id == story.id).first()
        assert deleted is not None
        assert deleted.deleted_at is not None

    def test_reviewer_cannot_delete_story(self, client, db, reviewer, auth_header, reporter):
        _make_test_org(db)
        story = Story(id="story-pub2", reporter_id=reporter.id, organization_id="org-test",
                      headline="Published", paragraphs=[], status="published")
        db.add(story)
        db.commit()
        resp = client.delete(f"/admin/stories/{story.id}", headers=auth_header)
        assert resp.status_code == 403

    def test_delete_nonexistent_story(self, client, db, org_admin, org_admin_header):
        resp = client.delete("/admin/stories/nonexistent", headers=org_admin_header)
        assert resp.status_code == 404

    def test_cannot_delete_story_from_other_org(self, client, db, org_admin, org_admin_header, reporter):
        story = Story(id="story-other", reporter_id=reporter.id, organization_id="org-other",
                      headline="Other", paragraphs=[], status="published")
        db.add(story)
        db.commit()
        resp = client.delete(f"/admin/stories/{story.id}", headers=org_admin_header)
        assert resp.status_code == 404
