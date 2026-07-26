import pytest

from app.api.v1 import consents
from app.schemas.patient import ConsentIn

pytestmark = pytest.mark.asyncio


class _Scalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return _Scalars(self.value)


class _Db:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.commits = 0

    async def execute(self, _query):
        return _Result(self.existing)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1


async def test_sign_consent_is_idempotent():
    db = _Db(existing=object())

    result = await consents.sign(ConsentIn(), uid=7, db=db)

    assert result == {"code": 0, "signed": True}
    assert db.added == []
    assert db.commits == 0


async def test_sign_consent_persists_before_reporting_success():
    db = _Db()

    result = await consents.sign(ConsentIn(), uid=7, db=db)

    assert result["signed"] is True
    assert len(db.added) == 1
    assert db.added[0].user_id == 7
    assert db.commits == 1


async def test_consent_status_is_version_specific():
    db = _Db(existing=object())

    result = await consents.status(uid=7, db=db)

    assert result == {"signed": True, "version": "v1"}
